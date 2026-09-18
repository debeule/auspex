import io
from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
from minio.error import S3Error

from auspex_backtesting.prices.price_fetcher import PriceFetcher


def _sample_normalised_df() -> pd.DataFrame:
    idx = pd.DatetimeIndex(["2023-01-03", "2023-01-04", "2023-01-05"], tz="UTC", name="date")
    return pd.DataFrame(
        {
            "open": [15.0, 16.0, 14.0],
            "high": [16.5, 17.0, 15.0],
            "low": [14.5, 15.5, 13.5],
            "close": [16.0, 14.5, 14.8],
            "volume": [100_000.0, 120_000.0, 90_000.0],
        },
        index=idx,
    )


def _sample_yfinance_df() -> pd.DataFrame:
    # yfinance returns tz-naive DatetimeIndex with PascalCase columns
    idx = pd.DatetimeIndex(["2023-01-03", "2023-01-04", "2023-01-05"], name="Date")
    return pd.DataFrame(
        {
            "Open": [15.0, 16.0, 14.0],
            "High": [16.5, 17.0, 15.0],
            "Low": [14.5, 15.5, 13.5],
            "Close": [16.0, 14.5, 14.8],
            "Volume": [100_000.0, 120_000.0, 90_000.0],
        },
        index=idx,
    )


def _s3_not_found() -> S3Error:
    return S3Error(MagicMock(), "NoSuchKey", "The specified key does not exist.", "/", "", "")


def _minio_empty() -> MagicMock:
    mock = MagicMock()
    mock.get_object.side_effect = _s3_not_found()
    return mock


def _minio_with_parquet(df: pd.DataFrame) -> MagicMock:
    buf = io.BytesIO()
    df.to_parquet(buf)
    response = MagicMock()
    response.read.return_value = buf.getvalue()
    mock = MagicMock()
    mock.get_object.return_value = response
    return mock


def test_ohlcv_maps_to_storage_schema() -> None:
    minio = _minio_empty()
    with patch("auspex_backtesting.prices.price_fetcher._from_yahoo", return_value=_sample_yfinance_df()):
        result = PriceFetcher(minio_client=minio).fetch("BEAM", date(2023, 1, 1), date(2023, 2, 1))

    assert list(result.columns) == ["open", "high", "low", "close", "volume"]
    assert result.index.tz is not None, "index must be timezone-aware"
    assert str(result.index.tz) == "UTC"
    assert result.index.name == "date"
    assert result.dtypes["open"] == "float64"
    assert result.dtypes["close"] == "float64"


def test_price_series_is_read_from_minio_when_present() -> None:
    stored = _sample_normalised_df()
    minio = _minio_with_parquet(stored)

    with patch("auspex_backtesting.prices.price_fetcher._from_yahoo") as mock_yf:
        result = PriceFetcher(minio_client=minio).fetch("BEAM", date(2023, 1, 1), date(2023, 2, 1))
        assert mock_yf.call_count == 0

    pd.testing.assert_frame_equal(result, stored)


def test_missing_ticker_returns_empty_not_exception() -> None:
    minio = _minio_empty()
    with (
        patch("auspex_backtesting.prices.price_fetcher._from_yahoo", return_value=pd.DataFrame()),
        patch("auspex_backtesting.prices.price_fetcher._from_stooq", return_value=pd.DataFrame()),
    ):
        result = PriceFetcher(minio_client=minio).fetch("XXXXXX", date(2023, 1, 1), date(2023, 2, 1))

    assert isinstance(result, pd.DataFrame)
    assert result.empty


def test_delisted_ticker_with_partial_history_is_handled() -> None:
    partial = _sample_yfinance_df().iloc[:1]
    minio = _minio_empty()
    with patch("auspex_backtesting.prices.price_fetcher._from_yahoo", return_value=partial):
        result = PriceFetcher(minio_client=minio).fetch("DELISTED", date(2010, 1, 1), date(2023, 12, 31))

    assert len(result) == 1
    assert not result.empty


def test_price_dates_are_stored_utc() -> None:
    minio = _minio_empty()
    stored_bytes: list[bytes] = []

    def capture_put(bucket: str, key: str, data: io.IOBase, length: int, **kwargs: object) -> None:
        stored_bytes.append(data.read())  # type: ignore[arg-type]

    minio.put_object.side_effect = capture_put

    with patch("auspex_backtesting.prices.price_fetcher._from_yahoo", return_value=_sample_yfinance_df()):
        PriceFetcher(minio_client=minio).fetch("BEAM", date(2023, 1, 1), date(2023, 2, 1))

    assert stored_bytes, "put_object must have been called"
    stored_df = pd.read_parquet(io.BytesIO(stored_bytes[0]))
    assert stored_df.index.tz is not None
    assert str(stored_df.index.tz) == "UTC"

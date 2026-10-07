import io
from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from minio.error import S3Error

from auspex_backtesting.prices.price_refresher import (
    PriceDataUnavailableError,
    PriceRefresher,
    SnapshotDiscontinuityError,
    price_universe,
)

_YAHOO = "auspex_backtesting.prices.price_refresher._from_yahoo"
_STOOQ = "auspex_backtesting.prices.price_refresher._from_stooq"


def _normalised(days: list[str], closes: list[float]) -> pd.DataFrame:
    idx = pd.DatetimeIndex(days, tz="UTC", name="date")
    return pd.DataFrame(
        {
            "open": closes,
            "high": closes,
            "low": closes,
            "close": closes,
            "volume": [1_000.0] * len(closes),
        },
        index=idx,
    )


def _yahoo(days: list[str], closes: list[float]) -> pd.DataFrame:
    idx = pd.DatetimeIndex(days, name="Date")
    return pd.DataFrame(
        {
            "Open": closes,
            "High": closes,
            "Low": closes,
            "Close": closes,
            "Volume": [1_000.0] * len(closes),
        },
        index=idx,
    )


def _minio_holding(df: pd.DataFrame | None) -> MagicMock:
    minio = MagicMock()
    if df is None:
        minio.get_object.side_effect = S3Error(
            MagicMock(), "NoSuchKey", "The specified key does not exist.", "/", "", ""
        )
    else:
        buf = io.BytesIO()
        df.to_parquet(buf)
        response = MagicMock()
        response.read.return_value = buf.getvalue()
        minio.get_object.return_value = response
    return minio


def _stored_frames(minio: MagicMock) -> list[pd.DataFrame]:
    return [
        pd.read_parquet(io.BytesIO(c.args[2].getvalue())) for c in minio.put_object.call_args_list
    ]


def _refresher(minio: MagicMock, today: date) -> PriceRefresher:
    return PriceRefresher(minio, history_start=date(2023, 1, 1), today=lambda: today)


def test_missing_snapshot_is_filled_with_full_history() -> None:
    minio = _minio_holding(None)
    with patch(_YAHOO, return_value=_yahoo(["2023-01-03", "2023-01-04"], [10.0, 11.0])) as yf:
        result = _refresher(minio, date(2026, 10, 7)).refresh("XBI")

    assert yf.call_args.args == ("XBI", date(2023, 1, 1), date(2026, 10, 8))
    assert result.rows_added == 2
    assert len(_stored_frames(minio)) == 1


def test_existing_snapshot_gains_only_new_bars_and_keeps_old_ones() -> None:
    stored = _normalised(["2026-10-05", "2026-10-06"], [20.0, 21.0])
    minio = _minio_holding(stored)
    fetched = _yahoo(["2026-10-06", "2026-10-07"], [21.0, 22.0])
    with patch(_YAHOO, return_value=fetched) as yf:
        result = _refresher(minio, date(2026, 10, 7)).refresh("XBI")

    assert yf.call_args.args == ("XBI", date(2026, 10, 6), date(2026, 10, 8))
    assert result.rows_added == 1
    (written,) = _stored_frames(minio)
    pd.testing.assert_frame_equal(written.iloc[:2], stored)
    assert written.index[-1] == pd.Timestamp("2026-10-07", tz="UTC")


def test_refresh_without_new_bars_writes_nothing() -> None:
    stored = _normalised(["2026-10-05", "2026-10-06"], [20.0, 21.0])
    minio = _minio_holding(stored)
    with patch(_YAHOO, return_value=_yahoo(["2026-10-06"], [21.0])):
        result = _refresher(minio, date(2026, 10, 6)).refresh("XBI")

    assert result.rows_added == 0
    minio.put_object.assert_not_called()


def test_rewritten_history_is_refused_and_snapshot_left_unchanged() -> None:
    # A 1:10 reverse split re-adjusts every earlier bar; appending would splice two scales.
    stored = _normalised(["2026-10-05", "2026-10-06"], [2.0, 2.1])
    minio = _minio_holding(stored)
    with (
        patch(_YAHOO, return_value=_yahoo(["2026-10-06", "2026-10-07"], [21.0, 22.0])),
        pytest.raises(SnapshotDiscontinuityError, match="CAPR"),
    ):
        _refresher(minio, date(2026, 10, 7)).refresh("CAPR")

    minio.put_object.assert_not_called()


def test_ticker_with_no_data_from_any_source_raises() -> None:
    minio = _minio_holding(None)
    with (
        patch(_YAHOO, return_value=pd.DataFrame()),
        patch(_STOOQ, return_value=pd.DataFrame()),
        pytest.raises(PriceDataUnavailableError, match="XXXX"),
    ):
        _refresher(minio, date(2026, 10, 7)).refresh("XXXX")

    minio.put_object.assert_not_called()


def test_price_universe_adds_benchmark_and_fx_once() -> None:
    assert price_universe("SRPT, BEAM,XBI") == ["SRPT", "BEAM", "XBI", "EURUSD=X"]

import io
from datetime import UTC, date, datetime, timedelta
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pandas as pd
import pytest
from minio.error import S3Error

from auspex_backtesting.market_sim.calendar import MarketCalendar
from auspex_backtesting.prices.price_refresher import (
    PriceDataUnavailableError,
    PriceRefresher,
    SnapshotDiscontinuityError,
    price_universe,
)
from auspex_backtesting.prices.snapshot_store import PriceSnapshotStore, adjusted_through

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


def _refresher(minio: MagicMock | _FakeMinio, now: datetime) -> PriceRefresher:
    return PriceRefresher(minio, history_start=date(2023, 1, 1), now=lambda: now)  # type: ignore[arg-type]


def _evening(day: date) -> datetime:
    """Late enough that the day's session has settled."""
    return datetime(day.year, day.month, day.day, 23, 30, tzinfo=UTC)


def _new_york(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=ZoneInfo("America/New_York"))


class _FakeMinio:
    """Keeps what was put, so a second refresh reads the first one's snapshot."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.puts = 0

    def put_object(self, bucket: str, key: str, data: io.BytesIO, length: int, **_: object) -> None:
        self.puts += 1
        self.objects[key] = data.read(length)

    def get_object(self, bucket: str, key: str) -> MagicMock:
        if key not in self.objects:
            raise S3Error(MagicMock(), "NoSuchKey", "missing", "/", "", "")
        response = MagicMock()
        response.read.return_value = self.objects[key]
        return response

    def closes(self, ticker: str) -> dict[str, float]:
        df = pd.read_parquet(io.BytesIO(self.objects[f"{ticker}.parquet"]))
        return {str(ts.date()): float(c) for ts, c in df["close"].items()}


def test_missing_snapshot_is_filled_with_full_history() -> None:
    minio = _minio_holding(None)
    with patch(_YAHOO, return_value=_yahoo(["2023-01-03", "2023-01-04"], [10.0, 11.0])) as yf:
        result = _refresher(minio, _evening(date(2026, 10, 7))).refresh("XBI")

    assert yf.call_args.args == ("XBI", date(2023, 1, 1), date(2026, 10, 8))
    assert result.rows_added == 2
    assert len(_stored_frames(minio)) == 1


def test_existing_snapshot_gains_only_new_bars_and_keeps_old_ones() -> None:
    stored = _normalised(["2026-10-05", "2026-10-06"], [20.0, 21.0])
    minio = _minio_holding(stored)
    fetched = _yahoo(["2026-10-06", "2026-10-07"], [21.0, 22.0])
    with patch(_YAHOO, return_value=fetched) as yf:
        result = _refresher(minio, _evening(date(2026, 10, 7))).refresh("XBI")

    assert yf.call_args.args == ("XBI", date(2026, 10, 6), date(2026, 10, 8))
    assert result.rows_added == 1
    (written,) = _stored_frames(minio)
    pd.testing.assert_frame_equal(written.iloc[:2], stored)
    assert written.index[-1] == pd.Timestamp("2026-10-07", tz="UTC")


def test_refresh_without_new_bars_writes_nothing() -> None:
    stored = _normalised(["2026-10-05", "2026-10-06"], [20.0, 21.0])
    minio = _minio_holding(stored)
    with patch(_YAHOO, return_value=_yahoo(["2026-10-06"], [21.0])):
        result = _refresher(minio, _evening(date(2026, 10, 6))).refresh("XBI")

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
        _refresher(minio, _evening(date(2026, 10, 7))).refresh("CAPR")

    minio.put_object.assert_not_called()


def test_ticker_with_no_data_from_any_source_raises() -> None:
    minio = _minio_holding(None)
    with (
        patch(_YAHOO, return_value=pd.DataFrame()),
        patch(_STOOQ, return_value=pd.DataFrame()),
        pytest.raises(PriceDataUnavailableError, match="XXXX"),
    ):
        _refresher(minio, _evening(date(2026, 10, 7))).refresh("XXXX")

    minio.put_object.assert_not_called()


def test_price_universe_adds_benchmark_and_fx_once() -> None:
    assert price_universe("SRPT, BEAM,XBI") == ["SRPT", "BEAM", "XBI", "EURUSD=X"]


# --- completed bars only -----------------------------------------------------------------------


def test_bar_of_an_open_session_is_not_stored() -> None:
    minio = _FakeMinio()
    fetched = _yahoo(["2026-10-06", "2026-10-07"], [20.0, 100.0])
    with patch(_YAHOO, return_value=fetched):
        result = _refresher(minio, _new_york("2026-10-07T15:00")).refresh("ALPH")

    assert minio.closes("ALPH") == {"2026-10-06": 20.0}
    assert result.last_date == "2026-10-06"


def test_unfinished_bar_is_stored_after_the_session_settles() -> None:
    minio = _FakeMinio()
    with patch(_YAHOO, return_value=_yahoo(["2026-10-06", "2026-10-07"], [20.0, 100.0])):
        _refresher(minio, _new_york("2026-10-07T15:00")).refresh("ALPH")
    with patch(_YAHOO, return_value=_yahoo(["2026-10-06", "2026-10-07"], [20.0, 101.0])):
        result = _refresher(minio, _new_york("2026-10-07T18:30")).refresh("ALPH")

    assert minio.closes("ALPH") == {"2026-10-06": 20.0, "2026-10-07": 101.0}
    assert result.rows_added == 1


def test_early_close_session_settles_from_its_early_close() -> None:
    # The day after Thanksgiving closes at 13:00; a full session would not settle until 18:00.
    minio = _FakeMinio()
    with patch(_YAHOO, return_value=_yahoo(["2024-11-27", "2024-11-29"], [20.0, 21.0])):
        _refresher(minio, _new_york("2024-11-29T15:30")).refresh("ALPH")

    assert minio.closes("ALPH") == {"2024-11-27": 20.0, "2024-11-29": 21.0}


def test_session_close_is_utc_across_the_dst_change() -> None:
    calendar = MarketCalendar()

    assert calendar.session_close(date(2024, 3, 8)) == datetime(2024, 3, 8, 21, 0, tzinfo=UTC)
    assert calendar.session_close(date(2024, 3, 11)) == datetime(2024, 3, 11, 20, 0, tzinfo=UTC)
    assert calendar.session_close(date(2024, 3, 11)).utcoffset() == timedelta(0)


def test_fx_bar_is_stored_only_after_its_utc_day_ends() -> None:
    fetched = _yahoo(["2026-10-06", "2026-10-07"], [1.10, 1.11])
    before, after = _FakeMinio(), _FakeMinio()
    with patch(_YAHOO, return_value=fetched):
        _refresher(before, datetime(2026, 10, 8, 1, 59, tzinfo=UTC)).refresh("EURUSD=X")
        _refresher(after, datetime(2026, 10, 8, 2, 0, tzinfo=UTC)).refresh("EURUSD=X")

    assert list(before.closes("EURUSD=X")) == ["2026-10-06"]
    assert list(after.closes("EURUSD=X")) == ["2026-10-06", "2026-10-07"]


# --- overlap required to append ----------------------------------------------------------------


def test_refresh_without_the_last_stored_bar_appends_nothing() -> None:
    minio = _FakeMinio()
    with patch(_YAHOO, return_value=_yahoo(["2026-10-05", "2026-10-06"], [100.0, 100.0])):
        _refresher(minio, _evening(date(2026, 10, 6))).refresh("ALPH")
    stored = dict(minio.objects)

    with (
        patch(_YAHOO, return_value=_yahoo(["2026-10-07", "2026-10-08"], [10.0, 10.0])),
        pytest.raises(SnapshotDiscontinuityError, match=r"ALPH.*2026-10-06"),
    ):
        _refresher(minio, _evening(date(2026, 10, 8))).refresh("ALPH")

    assert minio.objects == stored
    assert minio.puts == 1


def test_refresh_with_a_matching_overlap_appends_new_bars() -> None:
    minio = _FakeMinio()
    with patch(_YAHOO, return_value=_yahoo(["2026-10-05", "2026-10-06"], [100.0, 100.0])):
        _refresher(minio, _evening(date(2026, 10, 6))).refresh("ALPH")

    with patch(_YAHOO, return_value=_yahoo(["2026-10-06", "2026-10-07"], [100.5, 99.0])):
        result = _refresher(minio, _evening(date(2026, 10, 7))).refresh("ALPH")

    assert result.rows_added == 1
    assert minio.closes("ALPH") == {"2026-10-05": 100.0, "2026-10-06": 100.0, "2026-10-07": 99.0}
    # The appended bars stay on the split basis of the first download.
    snapshot = PriceSnapshotStore(minio).load("ALPH")  # type: ignore[arg-type]
    assert snapshot is not None and adjusted_through(snapshot) == date(2026, 10, 6)


def test_bar_dated_outside_a_session_settles_after_its_utc_day() -> None:
    # Stooq occasionally carries a bar on an exchange holiday; it has no session close.
    minio = _FakeMinio()
    fetched = _yahoo(["2026-11-25", "2026-11-26"], [20.0, 20.0])
    with patch(_YAHOO, return_value=fetched):
        _refresher(minio, datetime(2026, 11, 27, 1, 0, tzinfo=UTC)).refresh("ALPH")

    assert list(minio.closes("ALPH")) == ["2026-11-25"]

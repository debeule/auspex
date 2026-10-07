from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Final
from zoneinfo import ZoneInfo

import pandas as pd

from auspex_backtesting.market_sim.calendar import MarketCalendar

FORBIDDEN_FIELDS: Final = frozenset({"ingested_at", "retrieved_at", "first_detected_at"})

_ET: Final = ZoneInfo("America/New_York")
_MARKET_OPEN: Final = time(9, 30)
_CALENDAR: Final = MarketCalendar()


@dataclass(frozen=True)
class SignalRef:
    event_id: str
    published_date: datetime


@dataclass(frozen=True)
class CorroborationRef:
    entity_key: str
    corroborated_at: datetime
    first_detected_at: datetime
    superseded_by: str | None = None


def align(timestamp: datetime, timestamp_field: str, price_series: pd.DataFrame) -> pd.DataFrame:
    if timestamp_field in FORBIDDEN_FIELDS:
        raise ValueError(f"'{timestamp_field}' is not a public timestamp and cannot be used for alignment")
    cutoff = pd.Timestamp(entry_session(timestamp), tz="UTC")
    return price_series[price_series.index.normalize() >= cutoff]


def align_signal(ref: SignalRef, price_series: pd.DataFrame) -> pd.DataFrame:
    return align(ref.published_date, "published_date", price_series)


def align_corroboration(ref: CorroborationRef, price_series: pd.DataFrame) -> pd.DataFrame:
    return align(ref.corroborated_at, "corroborated_at", price_series)


def entry_session(ts: datetime) -> date:
    """First NYSE session whose open comes after the moment `ts` became public.

    A timestamp during market hours enters at the next session's open, not the current one, because
    that open had already traded. Connectors store a date-only `published_date` as midnight UTC; its
    time of day is unknown, so it is treated as known after that day's close.
    """
    if _is_date_only(ts):
        return _CALENDAR.next_trading_day(ts.astimezone(UTC).date() + timedelta(days=1))
    ts_et = ts.astimezone(_ET)
    d = ts_et.date()
    if ts_et.time() >= _MARKET_OPEN:
        d += timedelta(days=1)
    return _CALENDAR.next_trading_day(d)


def _is_date_only(ts: datetime) -> bool:
    return ts.astimezone(UTC).time() == time(0, 0)

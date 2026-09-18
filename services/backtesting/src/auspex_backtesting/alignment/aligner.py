from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Final
from zoneinfo import ZoneInfo

import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar

FORBIDDEN_FIELDS: Final = frozenset({"ingested_at", "retrieved_at", "first_detected_at"})

_ET: Final = ZoneInfo("America/New_York")
_MARKET_CLOSE: Final = time(16, 0)
# USFederalHolidayCalendar includes Columbus Day and Veterans Day, which NYSE does not observe.
# Neither falls in a typical biotech signal window, so this is an acceptable approximation.
_HOLIDAYS: Final = USFederalHolidayCalendar()


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
    cutoff = pd.Timestamp(_entry_date(timestamp), tz="UTC")
    return price_series[price_series.index.normalize() >= cutoff]


def align_signal(ref: SignalRef, price_series: pd.DataFrame) -> pd.DataFrame:
    return align(ref.published_date, "published_date", price_series)


def align_corroboration(ref: CorroborationRef, price_series: pd.DataFrame) -> pd.DataFrame:
    return align(ref.corroborated_at, "corroborated_at", price_series)


def _entry_date(ts: datetime) -> date:
    ts_et = ts.astimezone(_ET)
    d = ts_et.date()
    if ts_et.time() >= _MARKET_CLOSE:
        d += timedelta(days=1)
    return _next_trading_day(d)


def _next_trading_day(d: date) -> date:
    while _is_non_trading(d):
        d += timedelta(days=1)
    return d


def _is_non_trading(d: date) -> bool:
    if d.weekday() >= 5:
        return True
    return len(_HOLIDAYS.holidays(start=d.isoformat(), end=d.isoformat())) > 0

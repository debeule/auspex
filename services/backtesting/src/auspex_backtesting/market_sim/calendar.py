from datetime import date, timedelta
from functools import cache

import pandas_market_calendars as mcal

# Longest NYSE closure run (2001-09-11 to 09-14, next to a weekend) is under a week.
_SEARCH_HORIZON_DAYS = 14


class MarketCalendar:
    """NYSE sessions from pandas-market-calendars, cached per year."""

    def __init__(self, exchange: str = "NYSE") -> None:
        self._exchange = exchange

    def is_trading_day(self, d: date) -> bool:
        return d in _sessions_in_year(self._exchange, d.year)

    def next_trading_day(self, d: date) -> date:
        """`d` itself when it is a session, otherwise the next session after it."""
        for offset in range(_SEARCH_HORIZON_DAYS + 1):
            candidate = d + timedelta(days=offset)
            if self.is_trading_day(candidate):
                return candidate
        raise ValueError(f"no {self._exchange} session within {_SEARCH_HORIZON_DAYS} days of {d}")

    def trading_days_in(self, start: date, end: date) -> int:
        return len(self.sessions_between(start, end))

    def sessions_between(self, start: date, end: date) -> list[date]:
        """Sessions in `[start, end]`, inclusive, in order."""
        return [
            d
            for year in range(start.year, end.year + 1)
            for d in sorted(_sessions_in_year(self._exchange, year))
            if start <= d <= end
        ]


@cache
def _sessions_in_year(exchange: str, year: int) -> frozenset[date]:
    days = mcal.get_calendar(exchange).valid_days(date(year, 1, 1), date(year, 12, 31))
    return frozenset(ts.date() for ts in days)

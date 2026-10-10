"""FINRA's short interest schedule: which settlement dates exist and when each is published.

FINRA counts short positions as of two settlement dates a month, the 15th (or the settlement
day before it when the 15th is not one) and the last settlement day of the month, and
publishes them on the 7th business day after the settlement date. Business and settlement days
are taken to be NYSE sessions. Dates FINRA has published in its schedule
(`config/short_interest/finra_calendar.csv`) take precedence over the rule, month by month.
"""

import csv
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from auspex_backtesting.market_sim.calendar import MarketCalendar

PUBLICATION_LAG_SESSIONS = 7


@dataclass(frozen=True)
class SettlementPeriod:
    settlement_date: date
    publication_date: date


class FinraCalendar:
    def __init__(
        self,
        published: Mapping[date, date] | None = None,
        sessions: MarketCalendar | None = None,
    ) -> None:
        self._published = dict(published or {})
        self._sessions = sessions or MarketCalendar()

    @classmethod
    def from_csv(cls, path: Path, sessions: MarketCalendar | None = None) -> FinraCalendar:
        with path.open(newline="") as f:
            published = {
                date.fromisoformat(row["settlement_date"]): date.fromisoformat(
                    row["publication_date"]
                )
                for row in csv.DictReader(f)
            }
        return cls(published, sessions)

    @property
    def published(self) -> dict[date, date]:
        return dict(self._published)

    def publication_date(self, settlement_date: date) -> date:
        if settlement_date in self._published:
            return self._published[settlement_date]
        return self.rule_publication_date(settlement_date)

    def rule_publication_date(self, settlement_date: date) -> date:
        day = settlement_date
        for _ in range(PUBLICATION_LAG_SESSIONS):
            day = self._sessions.next_trading_day(day + timedelta(days=1))
        return day

    def settlement_dates(self, start: date, end: date) -> list[date]:
        """Settlement dates in `[start, end]`, in order."""
        published_months = {(d.year, d.month) for d in self._published}
        result: set[date] = set()
        year, month = start.year, start.month
        while (year, month) <= (end.year, end.month):
            next_month = date(year + month // 12, month % 12 + 1, 1)
            if (year, month) in published_months:
                candidates = [d for d in self._published if (d.year, d.month) == (year, month)]
            else:
                candidates = [
                    self._session_on_or_before(date(year, month, 15)),
                    self._session_on_or_before(next_month - timedelta(days=1)),
                ]
            result.update(d for d in candidates if start <= d <= end)
            year, month = next_month.year, next_month.month
        return sorted(result)

    def periods(self, start: date, published_by: date) -> list[SettlementPeriod]:
        """Periods settling on or after `start` whose data is published on or before
        `published_by`, oldest first."""
        periods = (
            SettlementPeriod(s, self.publication_date(s))
            for s in self.settlement_dates(start, published_by)
        )
        return [p for p in periods if p.publication_date <= published_by]

    def _session_on_or_before(self, d: date) -> date:
        while not self._sessions.is_trading_day(d):
            d -= timedelta(days=1)
        return d

"""Fetches FINRA settlement periods for a set of tickers into `ShortInterestStore`, once each."""

import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

from auspex_backtesting.short_interest.calendar import FinraCalendar, SettlementPeriod
from auspex_backtesting.short_interest.finra_client import ShortInterestSource
from auspex_backtesting.short_interest.model import ShortInterestRecord
from auspex_backtesting.short_interest.store import ShortInterestStore

log = logging.getLogger("auspex_backtesting.short_interest")

# Periods held in memory before they are appended to the ticker files; a failed run keeps
# everything flushed before it.
FLUSH_EVERY_PERIODS = 24


@dataclass(frozen=True)
class CoverageReport:
    tickers: int
    # Earliest settlement date stored with data for any ticker: where the history starts.
    first_available_settlement_date: date | None
    last_settlement_date: date | None
    periods_stored: int
    periods_fetched: int
    # Calendar periods FINRA returned no rows for in this run (none published, or outside the
    # history its API serves).
    unavailable_periods: list[date]
    # Calendar periods between the first and last stored one that are not stored.
    gaps: list[date]
    tickers_never_reported: list[str]

    def as_dict(self) -> dict[str, object]:
        def iso(d: date | None) -> str | None:
            return d.isoformat() if d else None

        return {
            "tickers": self.tickers,
            "first_available_settlement_date": iso(self.first_available_settlement_date),
            "last_settlement_date": iso(self.last_settlement_date),
            "periods_stored": self.periods_stored,
            "periods_fetched": self.periods_fetched,
            "unavailable_periods": [d.isoformat() for d in self.unavailable_periods],
            "gaps": [d.isoformat() for d in self.gaps],
            "tickers_never_reported": self.tickers_never_reported,
        }


class ShortInterestFetcher:
    def __init__(
        self, store: ShortInterestStore, source: ShortInterestSource, calendar: FinraCalendar
    ) -> None:
        self._store = store
        self._source = source
        self._calendar = calendar

    def fetch(self, tickers: Iterable[str], start: date, today: date) -> CoverageReport:
        """Stores every period settling on or after `start` and published by `today` that a
        ticker does not have yet, then reports coverage from what is stored."""
        wanted = sorted({t.upper() for t in tickers})
        stored = {t: self._store.settlement_dates(t) for t in wanted}
        periods = self._calendar.periods(start, today)
        pending: dict[str, list[ShortInterestRecord]] = {}
        unavailable: list[date] = []
        fetched = 0
        for period in periods:
            missing = [t for t in wanted if period.settlement_date not in stored[t]]
            if not missing:
                continue
            rows = self._source.records(period.settlement_date)
            fetched += 1
            if not rows:
                log.info("short interest %s: FINRA returned no rows", period.settlement_date)
                unavailable.append(period.settlement_date)
                continue
            by_symbol = _by_symbol(rows)
            for ticker in missing:
                pending.setdefault(ticker, []).append(_record(ticker, period, by_symbol))
                stored[ticker].add(period.settlement_date)
            if fetched % FLUSH_EVERY_PERIODS == 0:
                self._flush(pending)
        self._flush(pending)
        return self._report(wanted, periods, unavailable, fetched)

    def _flush(self, pending: dict[str, list[ShortInterestRecord]]) -> None:
        for ticker, records in pending.items():
            self._store.append(ticker, records)
        pending.clear()

    def _report(
        self,
        tickers: list[str],
        periods: list[SettlementPeriod],
        unavailable: list[date],
        fetched: int,
    ) -> CoverageReport:
        available: set[date] = set()
        reported: set[str] = set()
        for ticker in tickers:
            frame = self._store.read(ticker)
            available.update(frame["settlement_date"])
            if frame["reported"].any():
                reported.add(ticker)
        first = min(available, default=None)
        last = max(available, default=None)
        gaps = [
            p.settlement_date for p in periods
            if first is not None and last is not None
            and first < p.settlement_date < last and p.settlement_date not in available
        ]
        return CoverageReport(
            tickers=len(tickers),
            first_available_settlement_date=first,
            last_settlement_date=last,
            periods_stored=len(available),
            periods_fetched=fetched,
            unavailable_periods=unavailable,
            gaps=gaps,
            tickers_never_reported=[t for t in tickers if t not in reported],
        )


def _by_symbol(rows: Iterable[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    return {str(r["symbolCode"]).upper(): r for r in rows if r.get("symbolCode")}


def _record(
    ticker: str, period: SettlementPeriod, by_symbol: Mapping[str, Mapping[str, Any]]
) -> ShortInterestRecord:
    row = by_symbol.get(ticker)
    if row is None or row.get("currentShortPositionQuantity") is None:
        return ShortInterestRecord.absent(ticker, period.settlement_date, period.publication_date)
    adv = row.get("averageDailyVolumeQuantity")
    return ShortInterestRecord.from_counts(
        ticker, period.settlement_date, period.publication_date,
        short_interest_shares=int(row["currentShortPositionQuantity"]),
        average_daily_volume=None if adv is None else int(adv),
    )

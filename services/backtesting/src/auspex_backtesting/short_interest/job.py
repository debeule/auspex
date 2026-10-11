"""One short interest fetch for the universe's tickers: the job a backfill script or a scheduled
refresh runs. Safe to rerun: a period a ticker already has is not fetched again."""

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from auspex_backtesting.ownership.reference import FactorMissing, ShareCounts, SplitFactors
from auspex_backtesting.short_interest.calendar import FinraCalendar
from auspex_backtesting.short_interest.fetcher import CoverageReport, ShortInterestFetcher
from auspex_backtesting.short_interest.finra_client import ShortInterestSource
from auspex_backtesting.short_interest.store import ShortInterestStore
from auspex_backtesting.universe.model import ShareCount, UniverseMember
from auspex_backtesting.universe.store import UniverseStore


class ShortInterestConfigError(ValueError):
    """Short interest cannot be fetched from the current state (no universe yet)."""


@dataclass(frozen=True)
class ShortInterestConfig:
    data_url: str
    token_url: str
    client_id: str
    client_secret: str
    start: date

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> ShortInterestConfig:
        return cls(
            data_url=env["FINRA_SHORT_INTEREST_URL"],
            token_url=env["FINRA_TOKEN_URL"],
            client_id=env["FINRA_API_CLIENT_ID"],
            client_secret=env["FINRA_API_CLIENT_SECRET"],
            start=date.fromisoformat(env["SHORT_INTEREST_HISTORY_START"]),
        )


class UniverseShareBasis:
    """Share counts and split factors by ticker, through the ticker's universe company to the
    ownership panels' readers. A ticker that more than one universe company used maps to none
    of them: no count, and its factor is `ticker_history_uncertain`."""

    def __init__(
        self, members: Sequence[UniverseMember], counts: ShareCounts, splits: SplitFactors
    ) -> None:
        ciks: dict[str, set[str]] = {}
        for m in members:
            if m.ticker:
                ciks.setdefault(m.ticker.upper(), set()).add(m.cik)
        self._cik = {t: next(iter(c)) for t, c in ciks.items() if len(c) == 1}
        self._counts = counts
        self._splits = splits

    def share_count(self, ticker: str, as_of: date) -> ShareCount | None:
        cik = self._cik.get(ticker.upper())
        return self._counts.share_count(cik, as_of) if cik else None

    def factor(self, ticker: str, after: date, through: date) -> float | None:
        cik = self._cik.get(ticker.upper())
        return self._splits.factor(cik, after, through) if cik else None

    def missing_reason(self, ticker: str, after: date, through: date) -> FactorMissing | None:
        cik = self._cik.get(ticker.upper())
        if cik is None:
            return "ticker_history_uncertain"
        return self._splits.missing_reason(cik, after, through)


def universe_tickers(universe: UniverseStore, rules_version: int) -> list[str]:
    listings = universe.read_listings(rules_version)
    if listings is None:
        raise ShortInterestConfigError(
            f"no universe listings for rules version {rules_version}: build the universe first"
        )
    return sorted({m.ticker.upper() for m in listings[0] if m.ticker})


def fetch_short_interest(
    config: ShortInterestConfig,
    store: ShortInterestStore,
    source: ShortInterestSource,
    calendar_path: Path,
    tickers: Sequence[str],
    today: date,
) -> CoverageReport:
    calendar = FinraCalendar.from_csv(calendar_path)
    return ShortInterestFetcher(store, source, calendar).fetch(tickers, config.start, today)

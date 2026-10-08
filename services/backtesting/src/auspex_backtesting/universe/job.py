"""Builds every universe month that is due and not yet stored, then refreshes the coverage
report and backfill scope next to the snapshots. Safe to run repeatedly: when every due month
is stored it downloads nothing."""

import json
import logging
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

import pandas as pd
import yaml  # type: ignore[import-untyped]

from auspex_backtesting.market_sim.calendar import MarketCalendar
from auspex_backtesting.prices.price_refresher import (
    PriceDataUnavailableError,
    PriceRefresher,
    SnapshotDiscontinuityError,
)
from auspex_backtesting.prices.snapshot_store import PriceSnapshotStore
from auspex_backtesting.prices.splits import SplitStore
from auspex_backtesting.universe import sec_bulk
from auspex_backtesting.universe.builder import PriceSource, UniverseBuilder, rebalance_date
from auspex_backtesting.universe.model import CompanyRecord, ShareCount, UniverseSnapshot
from auspex_backtesting.universe.report import backfill_scope, coverage_report
from auspex_backtesting.universe.rules import UniverseRules
from auspex_backtesting.universe.store import UniverseStore

log = logging.getLogger("auspex_backtesting.universe")

# Liquidity looks back 20 sessions from the first rebalance, so prices are needed for names
# listed shortly before the window opens too.
_PRICE_LOOKBACK = timedelta(days=45)


class FilingSource(Protocol):
    def load(
        self, sic_codes: frozenset[str]
    ) -> tuple[Sequence[CompanyRecord], Mapping[str, Sequence[ShareCount]]]: ...


class PreparedPrices(PriceSource, Protocol):
    def prepare(self, tickers: Sequence[str]) -> dict[str, str]: ...


class SecBulkSource:
    def __init__(self, submissions_url: str, companyfacts_url: str, user_agent: str) -> None:
        self._submissions_url = submissions_url
        self._companyfacts_url = companyfacts_url
        self._user_agent = user_agent

    def load(
        self, sic_codes: frozenset[str]
    ) -> tuple[Sequence[CompanyRecord], Mapping[str, Sequence[ShareCount]]]:
        with tempfile.TemporaryDirectory() as tmp:
            submissions = sec_bulk.download(
                self._submissions_url, Path(tmp) / "submissions.zip", self._user_agent
            )
            companies = sec_bulk.read_submissions(submissions, sic_codes)
            submissions.unlink()
            facts = sec_bulk.download(
                self._companyfacts_url, Path(tmp) / "companyfacts.zip", self._user_agent
            )
            shares = sec_bulk.read_share_counts(facts, {c.cik for c in companies})
        log.info("SEC bulk data: %d filers with SIC %s", len(companies), sorted(sic_codes))
        return companies, shares


class SnapshotPrices:
    """Price snapshots and split histories from MinIO; `prepare` fills and extends them."""

    def __init__(
        self, refresher: PriceRefresher, snapshots: PriceSnapshotStore, splits: SplitStore
    ) -> None:
        self._refresher = refresher
        self._snapshots = snapshots
        self._splits = splits

    def prepare(self, tickers: Sequence[str]) -> dict[str, str]:
        """Refreshes each ticker's prices and split history; returns the failures by ticker."""
        failed: dict[str, str] = {}
        for ticker in tickers:
            try:
                self._refresher.refresh(ticker)
            except PriceDataUnavailableError as exc:
                failed[ticker] = str(exc)
                continue
            except SnapshotDiscontinuityError as exc:
                # The stored bars stay usable up to where they end.
                failed[ticker] = str(exc)
            self._splits.ensure(ticker)
        return failed

    def bars(self, ticker: str) -> pd.DataFrame | None:
        return self._snapshots.load(ticker)

    def splits(self, ticker: str) -> pd.Series:
        stored = self._splits.load(ticker)
        return stored if stored is not None else pd.Series(dtype=float)


@dataclass(frozen=True)
class BuildSummary:
    rules_version: int
    built: tuple[dict[str, Any], ...]
    already_stored: int
    price_failures: int
    coverage: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "rules_version": self.rules_version,
            "built": list(self.built),
            "already_stored": self.already_stored,
            "price_failures": self.price_failures,
            "coverage": self.coverage,
        }


def _utc_today() -> date:
    return datetime.now(UTC).date()


class UniverseBuildJob:
    def __init__(
        self,
        store: UniverseStore,
        rules_path: Path,
        filings: FilingSource,
        prices: PreparedPrices,
        *,
        today: Callable[[], date] = _utc_today,
        calendar: MarketCalendar | None = None,
    ) -> None:
        self._store = store
        self._rules_path = rules_path
        self._filings = filings
        self._prices = prices
        self._today = today
        self._calendar = calendar or MarketCalendar()

    def run(self) -> BuildSummary:
        rules = self._store.lock_rules(self._rules_path)
        today = self._today()
        months = months_due(rules, today, self._calendar)
        missing = [m for m in months if not self._store.exists(rules.version, m)]

        built: list[dict[str, Any]] = []
        failures: dict[str, str] = {}
        if missing:
            companies, shares = self._filings.load(rules.sic_codes)
            builder = UniverseBuilder(
                rules, companies, shares, self._prices, as_of=today, calendar=self._calendar
            )
            tickers = builder.tickers_listed_between(rules.window_start - _PRICE_LOOKBACK, today)
            failures = self._prices.prepare(tickers)
            log.info("prices for %d tickers, %d without data", len(tickers), len(failures))
            for month in missing:
                snapshot = builder.build(month)
                self._store.write(snapshot)
                built.append(_month_summary(snapshot))
                log.info("universe %s: %s", month, built[-1])
            self._store.write_listings(rules.version, builder.listings(), today)

        snapshots = [s for m in months if (s := self._store.read(rules.version, m)) is not None]
        stored_listings = self._store.read_listings(rules.version)
        report = coverage_report(snapshots, stored_listings[0] if stored_listings else ()).as_dict()
        self._store.put_report(
            rules.version, "coverage.json", json.dumps(report, indent=2).encode(), "application/json"
        )
        if months:
            scope = backfill_scope(snapshots, start=months[0], end=months[-1])
            self._store.put_report(
                rules.version,
                "backfill_scope.yaml",
                yaml.safe_dump(scope, sort_keys=False).encode(),
                "application/yaml",
            )
        return BuildSummary(
            rules.version, tuple(built), len(months) - len(missing), len(failures), report
        )


def months_due(rules: UniverseRules, today: date, calendar: MarketCalendar) -> list[str]:
    """`YYYY-MM` months in the rules window whose rebalance session is on or before `today`."""
    months = []
    y, m = rules.window_start.year, rules.window_start.month
    last = min(rules.window_end, today) if rules.window_end else today
    while (y, m) <= (last.year, last.month):
        month = f"{y:04d}-{m:02d}"
        if rebalance_date(month, calendar) <= today:
            months.append(month)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return months


def _month_summary(snapshot: UniverseSnapshot) -> dict[str, Any]:
    members = snapshot.members
    return {
        "month": snapshot.month,
        "members": len(members),
        "exiting": sum(m.exited_on is not None for m in members),
        "without_full_prices": sum(m.price_coverage != "complete" for m in members),
    }

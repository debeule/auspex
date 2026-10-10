"""Backfills and extends every ownership panel, then summarises coverage. Safe to rerun: a data
set, quarter or day already stored is read from MinIO, never fetched again."""

import logging
import os
import tempfile
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path

from auspex_backtesting.ownership.datasets import (
    FORM_13F_SUFFIX,
    INSIDER_SUFFIX,
    DatasetFile,
    latest_acceptance,
    list_dataset_files,
    quarter_of,
    quarters_between,
)
from auspex_backtesting.ownership.form13f import (
    Form13FDatasetStore,
    holdings_key,
    load_13f,
    specialists_key,
)
from auspex_backtesting.ownership.insider import InsiderTransactionStore, quarterly_key
from auspex_backtesting.ownership.issuers import IssuerDirectory, read_issuer_directory
from auspex_backtesting.ownership.reference import SHARES_OUTSTANDING_KEY, counts_frame
from auspex_backtesting.ownership.sec_client import SecFetcher
from auspex_backtesting.ownership.specialists import SpecialistClassifier
from auspex_backtesting.ownership.store import OwnershipStore
from auspex_backtesting.universe import sec_bulk
from auspex_backtesting.universe.store import UniverseStore

log = logging.getLogger("auspex_backtesting.ownership")


class OwnershipConfigError(ValueError):
    """The ownership panels cannot be built from the current state (no universe yet)."""


@dataclass(frozen=True)
class OwnershipConfig:
    form13f_page_url: str
    insider_page_url: str
    daily_index_url: str
    full_index_url: str
    archives_url: str
    submissions_bulk_url: str
    companyfacts_bulk_url: str
    start: date

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> OwnershipConfig:
        return cls(
            form13f_page_url=env["SEC_13F_DATASETS_URL"],
            insider_page_url=env["SEC_INSIDER_DATASETS_URL"],
            daily_index_url=env["SEC_DAILY_INDEX_URL"],
            full_index_url=env["SEC_FULL_INDEX_URL"],
            archives_url=env["SEC_ARCHIVES_URL"],
            submissions_bulk_url=env["SEC_SUBMISSIONS_BULK_URL"],
            companyfacts_bulk_url=env["SEC_COMPANYFACTS_BULK_URL"],
            start=date.fromisoformat(env["OWNERSHIP_HISTORY_START"]),
        )


@dataclass(frozen=True)
class Form13FCoverage:
    label: str
    filings: int
    universe_issuers_held: int
    cusips: int
    unmapped_cusips: int
    unmapped_value_share: float
    # Market-cap share of the universe month the data set ends in with no mapped 13F holder in
    # it: an upper bound on what CUSIP mapping missed, since small members can have no holder.
    universe_value_without_holder_share: float | None


@dataclass(frozen=True)
class InsiderCoverage:
    label: str
    filings: int
    transactions: int


@dataclass(frozen=True)
class CoverageSummary:
    universe_issuers: int
    form13f: list[Form13FCoverage] = field(default_factory=list)
    insider: list[InsiderCoverage] = field(default_factory=list)
    offering_quarters: int = 0
    offerings: int = 0
    daily_days: int = 0
    daily_transactions: int = 0
    share_count_issuers: int = 0

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


class OwnershipBackfill:
    def __init__(
        self,
        config: OwnershipConfig,
        store: OwnershipStore,
        universe: UniverseStore,
        rules_version: int,
        sec: SecFetcher,
        today: date,
        *,
        hypotheses_dir: Path | None = None,
        hypothesis_registry: Path | None = None,
    ) -> None:
        self._config = config
        self._store = store
        self._universe = universe
        self._rules_version = rules_version
        self._sec = sec
        self._today = today
        self._hypotheses_dir = hypotheses_dir
        self._hypothesis_registry = hypothesis_registry

    def run(self) -> CoverageSummary:
        listings = self._universe.read_listings(self._rules_version)
        if listings is None:
            raise OwnershipConfigError(
                f"no universe listings for rules version {self._rules_version}: build the "
                "universe first, the panels keep only its companies"
            )
        universe = frozenset(m.cik for m in listings[0])
        start = self._config.start

        form13f = Form13FDatasetStore(self._store, self._sec, self._directory, universe)
        f13_files = [
            f for f in self._list(self._config.form13f_page_url, FORM_13F_SUFFIX)
            if f.last_day >= start
        ]
        reports = [form13f.fetch(f) for f in f13_files]
        self._classify(f13_files)

        insider = InsiderTransactionStore(
            self._store, self._sec, universe,
            daily_index_url=self._config.daily_index_url,
            full_index_url=self._config.full_index_url,
            archives_url=self._config.archives_url,
        )
        insider_files = [
            f for f in self._list(self._config.insider_page_url, INSIDER_SUFFIX)
            if f.last_day >= start
        ]
        insider_coverage = []
        for f in insider_files:
            transactions = insider.fetch_quarter(f)
            stored = self._store.read(quarterly_key(f.label))
            filings = int(stored[0]["accession_number"].nunique()) if stored else 0
            insider_coverage.append(InsiderCoverage(f.label, filings, transactions))

        current = quarter_of(self._today)
        completed = [q for q in quarters_between(start, self._today) if q != current]
        offerings = sum(insider.fetch_offerings(y, q) for y, q in completed)

        first_day = max(
            (f.last_day + timedelta(days=1) for f in insider_files), default=start
        )
        days = daily = 0
        day = first_day
        while day < self._today:
            count = insider.fetch_day(day)
            if count is not None:
                days += 1
                daily += count
            day += timedelta(days=1)

        share_counts = self._share_counts(universe)

        return CoverageSummary(
            universe_issuers=len(universe),
            form13f=[
                Form13FCoverage(
                    r.label, r.filings, r.universe_issuers_held, r.cusips, r.unmapped_cusips,
                    r.unmapped_value_usd / r.total_value_usd if r.total_value_usd else 0.0,
                    self._value_without_holder(f),
                )
                for f, r in zip(f13_files, reports, strict=True)
            ],
            insider=insider_coverage,
            offering_quarters=len(completed),
            offerings=offerings,
            daily_days=days,
            daily_transactions=daily,
            share_count_issuers=share_counts,
        )

    def _list(self, page_url: str, suffix: str) -> list[DatasetFile]:
        html = self._sec.get(page_url).decode("utf-8", errors="replace")
        files = list_dataset_files(html, page_url, suffix)
        if not files:
            raise OwnershipConfigError(f"{page_url} links no *{suffix} data sets")
        return files

    def _directory(self) -> IssuerDirectory:
        with tempfile.TemporaryDirectory() as tmp:
            archive = self._sec.download(
                self._config.submissions_bulk_url, Path(tmp) / "submissions.zip"
            )
            return read_issuer_directory(archive)

    def _classify(self, files: list[DatasetFile]) -> None:
        """Stores, for each 13F data set, the specialist table as of just after its last
        filing could have been accepted."""
        missing = [f for f in files if not self._store.exists(specialists_key(f.label))]
        if not missing:
            return
        filings, _ = load_13f(self._store)
        classifier = SpecialistClassifier.from_hypothesis(
            filings, config_dir=self._hypotheses_dir, registry_path=self._hypothesis_registry
        )
        for f in missing:
            as_of = latest_acceptance(f.last_day) + timedelta(seconds=1)
            table = classifier.classify(as_of.to_pydatetime())
            self._store.replace(specialists_key(f.label), table, {
                "as_of": as_of.isoformat(),
                "healthcare_share": classifier.healthcare_share,
                "min_aum_usd": classifier.min_aum_usd,
            })

    def _value_without_holder(self, dataset: DatasetFile) -> float | None:
        snapshot = self._universe.read(self._rules_version, f"{dataset.last_day:%Y-%m}")
        stored = self._store.read(holdings_key(dataset.label))
        if snapshot is None or stored is None:
            return None
        held = set(stored[0]["issuer_cik"])
        caps = {m.cik: m.market_cap_usd for m in snapshot.members if m.market_cap_usd}
        total = sum(caps.values())
        if not total:
            return None
        return sum(v for cik, v in caps.items() if cik not in held) / total

    def _share_counts(self, universe: frozenset[str]) -> int:
        with tempfile.TemporaryDirectory() as tmp:
            archive = self._sec.download(
                self._config.companyfacts_bulk_url, Path(tmp) / "companyfacts.zip"
            )
            counts = sec_bulk.read_share_counts(archive, universe)
        self._store.replace(SHARES_OUTSTANDING_KEY, counts_frame(counts),
                            {"as_of": self._today.isoformat()})
        return len(counts)

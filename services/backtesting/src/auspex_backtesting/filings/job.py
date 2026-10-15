"""Fetches, cuts and scores the filings a universe needs, then writes its monthly snapshots."""

import logging
from collections import Counter, defaultdict
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any

from auspex_backtesting.catalysts.fetch import SourceBlockedError
from auspex_backtesting.catalysts.press_releases import quarters
from auspex_backtesting.filings.archive import FilingSectionArchive
from auspex_backtesting.filings.index import FilingIndex
from auspex_backtesting.filings.model import ArchivedSection
from auspex_backtesting.filings.score import RiskFactorChangeScore, TextChangeScore
from auspex_backtesting.market_sim.calendar import MarketCalendar
from auspex_backtesting.portfolio.scores import ScoreStore
from auspex_backtesting.universe.store import UniverseStore

log = logging.getLogger("auspex_backtesting.filings")

# A score on a rebalance date can come from a filing up to 120 days old, compared with one a
# year before that: filings are indexed from this long before the first universe month.
_INDEX_LEAD = timedelta(days=550)
# Months after its filing month in which a filing can still be scored on a rebalance date or be
# the comparison of one that is.
_FILING_RELEVANCE_MONTHS = 17


def score_version(hypothesis_version: int, universe: str | None) -> str:
    """Score snapshots of one hypothesis version are kept apart per universe, the default
    universe's under the plain version."""
    return str(hypothesis_version) if universe is None else f"{hypothesis_version}-{universe}"


def _utc_today() -> date:
    return datetime.now(UTC).date()


class FilingPanelBuild:
    def __init__(
        self,
        index: FilingIndex,
        archive: FilingSectionArchive,
        universe: UniverseStore,
        rules_version: int,
        scores: ScoreStore,
        hypothesis_id: str,
        version: str,
        *,
        calendar: MarketCalendar | None = None,
        today: Callable[[], date] = _utc_today,
    ) -> None:
        self._index = index
        self._archive = archive
        self._universe = universe
        self._rules_version = rules_version
        self._scores = scores
        self._hypothesis_id = hypothesis_id
        self._version = version
        self._calendar = calendar or MarketCalendar()
        self._today = today

    def run(self) -> dict[str, Any]:
        """Indexes and archives every 10-K and 10-Q of the universe's members, then writes a
        score snapshot for each stored universe month that has none and whose rebalance date
        has passed (a filing accepted before that day's open is in the next day's index).
        When SEC refuses a request the run stops before scoring, with what it archived kept,
        and reports `complete: false`."""
        months = self._universe.months(self._rules_version)
        if not months:
            raise ValueError(f"universe rules version {self._rules_version} has no snapshot yet")
        snapshots = [s for m in months if (s := self._universe.read(self._rules_version, m))]
        member_months: dict[str, set[str]] = defaultdict(set)
        for snapshot in snapshots:
            for m in snapshot.members:
                member_months[m.cik].add(snapshot.month)

        today = self._today()
        found: Counter[str] = Counter()
        statuses: Counter[str] = Counter()
        reasons: Counter[str] = Counter()
        sections: list[ArchivedSection] = []
        start = date.fromisoformat(f"{months[0]}-01") - _INDEX_LEAD
        try:
            for year, quarter, _, _ in quarters(start, today):
                for entry in self._index.quarter(year, quarter):
                    if not _relevant(member_months.get(entry.cik), entry.filed):
                        continue
                    found["filings"] += 1
                    if entry.form.endswith("/A"):
                        found["amendments_not_cut"] += 1
                        continue
                    section = self._archive.get(entry)
                    statuses[section.status] += 1
                    if section.reason:
                        reasons[section.reason] += 1
                    sections.append(section)
        except SourceBlockedError as exc:
            log.warning("SEC refused %s: stopping this run, no retry during a block", exc)
            return {
                "complete": False,
                **self._coverage(found, statuses, reasons),
            }

        result = TextChangeScore().score(sections)
        scorer = RiskFactorChangeScore(
            result.scores, self._universe, self._rules_version, self._hypothesis_id,
            self._version, self._calendar,
        )
        stored = set(self._scores.dates(self._hypothesis_id, self._version))
        written, per_month = 0, []
        for snapshot in snapshots:
            if snapshot.rebalance_date >= today or snapshot.rebalance_date in stored:
                continue
            month = scorer.compute(snapshot.rebalance_date)
            self._scores.write(month.snapshot)
            written += 1
            per_month.append({
                "month": snapshot.month,
                "members": month.members,
                "scored": len(month.snapshot.rows),
                "left_out": len(month.left_out),
            })
        return {
            "complete": True,
            **self._coverage(found, statuses, reasons),
            "scores": len(result.scores),
            "unscored": result.unscored,
            "snapshots_written": written,
            "snapshots_already_stored": len(stored),
            "months": per_month,
        }

    def _coverage(
        self, found: Counter[str], statuses: Counter[str], reasons: Counter[str]
    ) -> dict[str, Any]:
        return {
            "universe": self._universe.universe,
            "rules_version": self._rules_version,
            "score": {"hypothesis_id": self._hypothesis_id, "version": self._version},
            "filings_found": found["filings"],
            "amendments_not_cut": found["amendments_not_cut"],
            "sections": dict(statuses),
            "missing_by_reason": dict(reasons),
        }


def _relevant(months: set[str] | None, filed: date) -> bool:
    if not months:
        return False
    y, m = filed.year, filed.month
    for _ in range(_FILING_RELEVANCE_MONTHS + 1):
        if f"{y:04d}-{m:02d}" in months:
            return True
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return False

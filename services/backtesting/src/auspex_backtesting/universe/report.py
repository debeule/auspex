from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from auspex_backtesting.universe.model import PriceCoverage, UniverseMember, UniverseSnapshot


@dataclass(frozen=True)
class CoverageGap:
    cik: str
    ticker: str | None
    name: str
    exit_reason: str | None
    price_coverage: PriceCoverage
    note: str


@dataclass(frozen=True)
class CoverageReport:
    """Price coverage over every company that was a member in any of the snapshots, judged from
    its most recent snapshot row."""

    members: int
    complete: int
    delisted: int
    gaps: tuple[CoverageGap, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "members": self.members,
            "complete": self.complete,
            "partial": sum(g.price_coverage == "partial" for g in self.gaps),
            "none": sum(g.price_coverage == "none" for g in self.gaps),
            "delisted": self.delisted,
            "gaps": [g.__dict__ for g in self.gaps],
        }


def coverage_report(
    snapshots: Iterable[UniverseSnapshot], listings: Iterable[UniverseMember] = ()
) -> CoverageReport:
    """`listings`, when given, replace a member's snapshot row with the latest view of the same
    listing, so exits and price coverage are current."""
    latest = _latest_rows(snapshots)
    current = {(m.cik, m.entered_on): m for m in listings}
    latest = {cik: current.get((m.cik, m.entered_on), m) for cik, m in latest.items()}
    gaps = tuple(
        CoverageGap(m.cik, m.ticker, m.name, m.exit_reason, m.price_coverage, m.coverage_note)
        for m in latest.values()
        if m.price_coverage != "complete"
    )
    return CoverageReport(
        members=len(latest),
        complete=sum(m.price_coverage == "complete" for m in latest.values()),
        delisted=sum(m.exited_on is not None for m in latest.values()),
        gaps=gaps,
    )


def backfill_scope(
    snapshots: Iterable[UniverseSnapshot], *, start: str, end: str
) -> dict[str, Any]:
    """Companies that were members in any month of `[start, end]` (`YYYY-MM`, inclusive): the
    company list the historical backfill scopes EDGAR and ClinicalTrials.gov to."""
    in_window = [s for s in snapshots if start <= s.month <= end]
    versions = {s.rules_version for s in in_window}
    if len(versions) > 1:
        raise ValueError(f"snapshots from several rules versions: {sorted(versions)}")
    latest = _latest_rows(in_window)
    return {
        "rules_version": versions.pop() if versions else None,
        "window": {"start": start, "end": end},
        "companies": [{"cik": m.cik, "ticker": m.ticker, "name": m.name} for m in latest.values()],
    }


def _latest_rows(snapshots: Iterable[UniverseSnapshot]) -> dict[str, UniverseMember]:
    rows: dict[str, UniverseMember] = {}
    for snapshot in sorted(snapshots, key=lambda s: s.month):
        for member in snapshot.members:
            rows[member.cik] = member
    return dict(sorted(rows.items()))

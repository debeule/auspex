"""How a portfolio hypothesis turns ranked scores into a target set of names, and when it trades."""

from __future__ import annotations

import re
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

import pandas as pd

from auspex_backtesting.market_sim.calendar import MarketCalendar
from auspex_backtesting.protocol import quarterly_trade_date

Selection = Literal["top_n", "top_quintile", "exclude_bottom_quintile"]
Cadence = Literal["monthly", "quarterly_after_13f", "semi_annual_after_13f"]
GuardMode = Literal["none", "skip_entry", "exit_and_reenter", "exit_low_score_only"]

_QUARTER_ENDS = {
    "quarterly_after_13f": ((3, 31), (6, 30), (9, 30), (12, 31)),
    # 13F filings for the second and fourth quarters, filed by mid-August and mid-February.
    "semi_annual_after_13f": ((6, 30), (12, 31)),
}
_CADENCE_TOKEN = re.compile(r"(monthly|quarterly|semi_annual)_(?:top(\d+)|bands_(\d+)_(\d+))")
_CADENCES: dict[str, Cadence] = {
    "monthly": "monthly",
    "quarterly": "quarterly_after_13f",
    "semi_annual": "semi_annual_after_13f",
}
_VARIANT_SELECTIONS: dict[str, Selection] = {
    # The filing-text score ranks the least changed highest.
    "exclude_most_changed_quintile": "exclude_bottom_quintile",
    "least_changed_quintile": "top_quintile",
}


@dataclass(frozen=True)
class ScoreRef:
    """Score snapshots of one hypothesis and score version."""

    hypothesis_id: str
    version: str


@dataclass(frozen=True)
class PortfolioRule:
    """Selection, cadence, catalyst guard and exclusion filter for one evaluated cell.

    `top_n` keeps a held name while it ranks at or above `exit_rank` and buys names ranked at
    or above `enter_rank`; `enter_rank == exit_rank` is a hard cut. `exclusion` names a second
    score whose bottom quintile is neither bought nor kept. Decisions are taken on the
    `decision_dates` and filled at the open of the session after each.
    """

    score: ScoreRef
    selection: Selection = "top_n"
    enter_rank: int = 15
    exit_rank: int = 15
    cadence: Cadence = "monthly"
    trade_date_rule: Mapping[str, Any] | None = None
    catalyst_guard: GuardMode = "none"
    exclusion: ScoreRef | None = None
    volatility_sessions: int = 60
    catalyst_window_sessions: int = 5
    cell: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.exit_rank < self.enter_rank:
            raise ValueError("exit_rank must be at or below enter_rank")
        if self.cadence != "monthly" and self.trade_date_rule is None:
            raise ValueError(f"cadence {self.cadence} needs a trade_date_rule")

    @classmethod
    def from_hypothesis(
        cls,
        hypothesis: Mapping[str, Any],
        cell: Mapping[str, Any],
        score: ScoreRef,
        exclusion: ScoreRef | None = None,
    ) -> PortfolioRule:
        """The rule for one cell of a portfolio hypothesis's trial grid.

        A cadence token reads `<cadence>_top<n>` (a hard cut) or `<cadence>_bands_<enter>_<exit>`.
        """
        match = _CADENCE_TOKEN.fullmatch(str(cell["cadence"]))
        if match is None:
            raise ValueError(f"unsupported cadence {cell['cadence']!r}")
        cadence = _CADENCES[match.group(1)]
        if match.group(2) is not None:
            enter = exit_ = int(match.group(2))
        else:
            enter, exit_ = int(match.group(3)), int(match.group(4))
        selection: Selection = "top_n"
        if "variant" in cell:
            selection = _VARIANT_SELECTIONS[str(cell["variant"])]
        diagnostics = hypothesis.get("diagnostics") or {}
        return cls(
            score=score,
            selection=selection,
            enter_rank=enter,
            exit_rank=exit_,
            cadence=cadence,
            trade_date_rule=hypothesis.get("trade_date_rule") if cadence != "monthly" else None,
            catalyst_guard=cell.get("catalyst_guard", "none"),
            exclusion=exclusion,
            catalyst_window_sessions=int(diagnostics.get("catalyst_window_split_sessions", 5)),
            cell=dict(cell),
        )

    def decision_dates(self, start: date, end: date, calendar: MarketCalendar) -> list[date]:
        """Sessions in `[start, end]` on which this rule decides its next portfolio."""
        if self.cadence == "monthly":
            return [
                calendar.next_trading_day(month.date())
                for month in pd.date_range(date(start.year, start.month, 1), end, freq="MS")
                if start <= calendar.next_trading_day(month.date()) <= end
            ]
        assert self.trade_date_rule is not None
        dates = []
        for year in range(start.year - 1, end.year + 1):
            for month, day in _QUARTER_ENDS[self.cadence]:
                trade = quarterly_trade_date(
                    date(year, month, day), dict(self.trade_date_rule), calendar
                )
                if start <= trade <= end:
                    dates.append(trade)
        return sorted(dates)

    def target(self, ranks: Mapping[str, int], held: AbstractSet[str]) -> set[str]:
        """Names to hold after this decision, from ranks (1 is best) and the names held now."""
        n = len(ranks)
        if self.selection == "top_quintile":
            return {c for c, r in ranks.items() if r <= n // 5}
        if self.selection == "exclude_bottom_quintile":
            return {c for c, r in ranks.items() if r <= n - n // 5}
        kept = {c for c in held if ranks.get(c, n + 1) <= self.exit_rank}
        return kept | {c for c, r in ranks.items() if r <= self.enter_rank}

    def in_entry_band(self, rank: int | None, n: int) -> bool:
        if rank is None:
            return False
        if self.selection == "top_quintile":
            return rank <= n // 5
        if self.selection == "exclude_bottom_quintile":
            return rank <= n - n // 5
        return rank <= self.enter_rank


def rank_scores(scores: pd.DataFrame, members: AbstractSet[str]) -> dict[str, int]:
    """Rank 1 is the highest score among `members`; ties go to the lower CIK."""
    rows = scores[scores["cik"].isin(members) & scores["score"].notna()]
    ordered = sorted(zip(rows["score"], rows["cik"], strict=True), key=lambda r: (-r[0], r[1]))
    return {cik: i + 1 for i, (_, cik) in enumerate(ordered)}


def bottom_quintile(ranks: Mapping[str, int]) -> set[str]:
    n = len(ranks)
    return {c for c, r in ranks.items() if r > n - n // 5}

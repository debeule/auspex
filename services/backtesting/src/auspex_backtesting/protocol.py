"""The registered evaluation protocol applied to hypotheses before and after any evaluation.

Reads `config/hypotheses/protocol.yaml`: trial budgets per corpus family, instrument
ceilings, the forward-check branch for each evaluation kind, and the registered rules a
portfolio hypothesis trades by.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from auspex_backtesting.hypothesis import (
    hypothesis_views,
    load_hypothesis,
    validate_hypothesis,
    verify_hypothesis,
)
from auspex_backtesting.market_sim.calendar import MarketCalendar

_PROTOCOL_ID = "protocol"
_MONTHS_PER_YEAR = 12
_QUARTER_END_MONTHS = (3, 6, 9, 12)


class FamilyNotBudgetedError(Exception):
    pass


class NotPromotableError(Exception):
    pass


class ProtocolCeilingError(Exception):
    pass


class TrialBudgetExceededError(Exception):
    pass


def count_trials(hypotheses: Iterable[dict[str, Any]], protocol: dict[str, Any]) -> dict[str, int]:
    """Declared trial cells per family, over the roles the protocol counts."""
    counted_roles = set(protocol["trials"]["counts_roles"])
    counts: dict[str, int] = {}
    for hypothesis in hypotheses:
        for view in hypothesis_views(hypothesis):
            if view.get("role") not in counted_roles:
                continue
            family = _family(view, protocol)
            counts[family] = counts.get(family, 0) + int(view.get("trial_cells", 0))
    return counts


def check_trial_budgets(
    hypotheses: Iterable[dict[str, Any]], protocol: dict[str, Any]
) -> dict[str, int]:
    """Refuse a set of hypotheses whose declared cells exceed any family's own budget."""
    families = protocol["families"]
    counts = count_trials(hypotheses, protocol)
    for family, cells in counts.items():
        if family not in families:
            raise FamilyNotBudgetedError(f"family {family!r} has no registered budget")
        budget = families[family]["budget_cells"]
        if cells > budget:
            raise TrialBudgetExceededError(f"{family}: {cells} cells exceed the budget of {budget}")
    return counts


def check_promotable(hypothesis: dict[str, Any], use: str | None = None) -> None:
    """Raise NotPromotableError unless the hypothesis (or the named use) has role `promotable`."""
    view = _select_view(hypothesis, use, NotPromotableError)
    if view.get("role") != "promotable":
        raise NotPromotableError(
            f"{_name(view)} has role {view.get('role')!r}; only promotable hypotheses are promoted"
        )


def forward_check_branch(
    hypothesis: dict[str, Any], protocol: dict[str, Any], use: str | None = None
) -> dict[str, Any]:
    """The forward-check criteria for the hypothesis's evaluation kind."""
    view = _select_view(hypothesis, use, ValueError)
    forward_check = next(k for k in protocol["kill_criteria"] if k["id"] == "forward_check")
    return forward_check[view.get("evaluation", "event")]  # type: ignore[no-any-return]


@dataclass(frozen=True)
class PortfolioForwardRecord:
    """One capital tier's paper ledger against its backtest replay over the same months."""

    paper_monthly_net_excess: Sequence[float]
    replay_monthly_net_excess: Sequence[float]
    ledger_gap_sessions: Sequence[date]
    in_sample_mean_annual_net_excess: float
    in_sample_standard_error_annual: float


@dataclass(frozen=True)
class ForwardCheckVerdict:
    status: Literal["insufficient", "pass", "fail"]
    reasons: list[str] = field(default_factory=list)


def evaluate_portfolio_forward_check(
    record: PortfolioForwardRecord, protocol: dict[str, Any]
) -> ForwardCheckVerdict:
    """Apply the protocol's portfolio forward-check branch to one capital tier."""
    branch = next(k for k in protocol["kill_criteria"] if k["id"] == "forward_check")["portfolio"]
    paper = list(record.paper_monthly_net_excess)
    replay = list(record.replay_monthly_net_excess)
    if len(paper) != len(replay):
        raise ValueError("paper and replay must cover the same months")
    if len(paper) < branch["min_months"]:
        return ForwardCheckVerdict("insufficient")

    reasons: list[str] = []
    if len(record.ledger_gap_sessions) > branch["max_ledger_gaps"]:
        reasons.append("ledger_gap")
    tracking = _annualised_mean([p - r for p, r in zip(paper, replay, strict=True)])
    if abs(tracking) > branch["max_abs_tracking_difference_per_year"]:
        reasons.append("tracking_difference")
    bound = (
        record.in_sample_mean_annual_net_excess
        - branch["min_net_excess_standard_errors_below_in_sample_mean"]
        * record.in_sample_standard_error_annual
    )
    if _annualised_mean(paper) < bound:
        reasons.append("net_excess_below_bound")
    return ForwardCheckVerdict("fail" if reasons else "pass", reasons)


def is_data_gap(
    session_open: datetime, available_at: Mapping[str, datetime], protocol: dict[str, Any]
) -> bool:
    """True when any required input was missing, or arrived at or after the session's open."""
    branch = next(k for k in protocol["kill_criteria"] if k["id"] == "forward_check")["portfolio"]
    for required in branch["data_gap"]["required_inputs"]:
        arrived = available_at.get(required)
        if arrived is None or arrived >= session_open:
            return True
    return False


def quarterly_trade_date(quarter_end: date, rule: dict[str, Any], calendar: MarketCalendar) -> date:
    """The trade session a quarter's 13F filings feed, under a hypothesis's `trade_date_rule`.

    The deadline is counted in calendar days from the quarter end; the trade is the first NYSE
    session at least `min_calendar_days_after_deadline` after it.
    """
    if (
        rule.get("anchor") != "13f_deadline"
        or rule.get("session") != "first_nyse_session_on_or_after"
    ):
        raise ValueError(f"unsupported trade_date_rule: {rule}")
    if quarter_end.month not in _QUARTER_END_MONTHS or (quarter_end + timedelta(days=1)).day != 1:
        raise ValueError(f"{quarter_end} is not a calendar quarter end")
    deadline = quarter_end + timedelta(days=rule["deadline_days_after_quarter_end"])
    earliest = deadline + timedelta(days=rule["min_calendar_days_after_deadline"])
    return calendar.next_trading_day(earliest)


def select_component_variant(
    hypothesis: dict[str, Any], *, short_interest_history_start: date
) -> str:
    """The pre-registered component variant, chosen from data coverage dates alone."""
    selection = hypothesis["component_variants"]["selection"]
    if selection.get("two_component_when") != "short_interest_history_starts_after_in_sample_start":
        raise ValueError(f"unsupported component selection rule: {selection}")
    in_sample_start = date(hypothesis["in_sample_years"][0], 1, 1)
    if short_interest_history_start > in_sample_start:
        return "two_component"
    return str(selection["otherwise"])


class EvaluationProtocol:
    """The gate every evaluation passes before it reads returns.

    Admission verifies the hypothesis against its registration, then refuses anything the
    protocol does not budget or allow: an unknown family, a family over its trial budget once
    every registered hypothesis is counted, a role the family does not hold, or a short or
    options position above the instrument ceilings.
    """

    def __init__(
        self, *, config_dir: Path | None = None, registry_path: Path | None = None
    ) -> None:
        self._config_dir = config_dir if config_dir is not None else Path("config/hypotheses")
        self._registry_path = registry_path
        verify_hypothesis(_PROTOCOL_ID, config_dir=self._config_dir, registry_path=registry_path)
        self.protocol: dict[str, Any] = load_hypothesis(_PROTOCOL_ID, self._config_dir)

    def admit(self, hypothesis_id: str) -> dict[str, Any]:
        verify_hypothesis(
            hypothesis_id, config_dir=self._config_dir, registry_path=self._registry_path
        )
        hypothesis = load_hypothesis(hypothesis_id, self._config_dir)
        self.check_admissible(hypothesis)
        return hypothesis

    def check_admissible(self, hypothesis: dict[str, Any]) -> None:
        validate_hypothesis(hypothesis)
        families = self.protocol["families"]
        for view in hypothesis_views(hypothesis):
            family = _family(view, self.protocol)
            if family not in families:
                raise FamilyNotBudgetedError(
                    f"{_name(view)}: family {family!r} has no registered budget"
                )
            self._check_ceilings(view)

        others = [h for h in self._registered() if h.get("id") != hypothesis.get("id")]
        check_trial_budgets([*others, hypothesis], self.protocol)

        for view in hypothesis_views(hypothesis):
            allowed_roles = families[_family(view, self.protocol)].get("roles")
            if allowed_roles is not None and view.get("role") not in allowed_roles:
                raise FamilyNotBudgetedError(
                    f"{_name(view)}: family {_family(view, self.protocol)!r} holds only {allowed_roles}"
                )

    def _check_ceilings(self, view: dict[str, Any]) -> None:
        instruments = self.protocol["instruments"]
        if "short" in str(view.get("direction", "")) and not instruments["shorts_enabled"]:
            raise ProtocolCeilingError(
                f"{_name(view)}: short positions are disabled by the protocol"
            )
        if "option" in str(view.get("instrument", "")) and not instruments["options_enabled"]:
            raise ProtocolCeilingError(f"{_name(view)}: options are disabled by the protocol")

    def _registered(self) -> list[dict[str, Any]]:
        return [
            load_hypothesis(path.stem, self._config_dir)
            for path in sorted(self._config_dir.glob("*.yaml"))
            if path.stem != _PROTOCOL_ID
        ]


def _family(view: dict[str, Any], protocol: dict[str, Any]) -> str:
    return str(view.get("family") or protocol["default_event_family"])


def _annualised_mean(monthly: Sequence[float]) -> float:
    return sum(monthly) / len(monthly) * _MONTHS_PER_YEAR


def _name(view: dict[str, Any]) -> str:
    return str(view.get("id", "?")) + (f"/{view['use']}" if "use" in view else "")


def _select_view(
    hypothesis: dict[str, Any], use: str | None, error: type[Exception]
) -> dict[str, Any]:
    views = hypothesis_views(hypothesis)
    if use is None:
        if "uses" in hypothesis:
            raise error(f"{hypothesis.get('id')} declares several uses; name the use")
        return views[0]
    for view in views:
        if view.get("use") == use:
            return view
    raise error(f"{hypothesis.get('id')} has no use {use!r}")

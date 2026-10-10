"""The registered evaluation protocol applied to hypotheses before and after any evaluation.

Reads `config/hypotheses/protocol.yaml`: trial budgets per corpus family, instrument
ceilings, the forward-check branch for each evaluation kind, and the registered rules a
portfolio hypothesis trades by.
"""

from __future__ import annotations

import itertools
import math
import os
import re
import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd

from auspex_backtesting.evaluation import (
    AbnormalReturnCalculator,
    BootstrapCI,
    CellResult,
    ClusteredInference,
    DeflatedSharpe,
    EvaluationResult,
    HoldoutGuard,
    HypothesisSuspendedError,
    InsufficientEventsError,
    KillCriteria,
    KnownAtDelay,
    TradeCosts,
    TrialLedger,
    UnregisteredCellError,
    WalkForwardSegment,
    WalkForwardSplitter,
)
from auspex_backtesting.evaluation.results import is_primary_cell
from auspex_backtesting.hypothesis import (
    hypothesis_views,
    load_hypothesis,
    validate_hypothesis,
    verify_hypothesis,
)
from auspex_backtesting.market_sim._snapshots import price_on
from auspex_backtesting.market_sim.calendar import MarketCalendar
from auspex_backtesting.prices.snapshot_store import PriceSnapshotStore

_PROTOCOL_ID = "protocol"
_MONTHS_PER_YEAR = 12
_QUARTER_END_MONTHS = (3, 6, 9, 12)


class FamilyNotBudgetedError(Exception):
    pass


class EvaluationConfigError(Exception):
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
    """One capital tier's paper ledger against its backtest replay over the same months.

    Monthly returns are `(YYYY-MM, net excess return)` rows exactly as each ledger produced
    them, so a month the ledger wrote twice reaches the check as two rows.
    """

    paper_monthly_net_excess: Sequence[tuple[str, float]]
    replay_monthly_net_excess: Sequence[tuple[str, float]]
    ledger_gap_sessions: Sequence[date]
    in_sample_mean_annual_net_excess: float
    in_sample_standard_error_annual: float


@dataclass(frozen=True)
class ForwardCheckVerdict:
    """`invalid` means the record could not be evaluated: a data problem, not a kill."""

    status: Literal["invalid", "insufficient", "pass", "fail"]
    reasons: list[str] = field(default_factory=list)


def evaluate_portfolio_forward_check(
    record: PortfolioForwardRecord, protocol: dict[str, Any]
) -> ForwardCheckVerdict:
    """Apply the protocol's portfolio forward-check branch to one capital tier."""
    branch = next(k for k in protocol["kill_criteria"] if k["id"] == "forward_check")["portfolio"]
    problems = _forward_record_problems(record)
    if problems:
        return ForwardCheckVerdict("invalid", problems)
    paper = dict(record.paper_monthly_net_excess)
    replay = dict(record.replay_monthly_net_excess)
    if len(paper) < branch["min_months"]:
        return ForwardCheckVerdict("insufficient")

    reasons: list[str] = []
    if len(record.ledger_gap_sessions) > branch["max_ledger_gaps"]:
        reasons.append("ledger_gap")
    tracking = _annualised_mean([paper[month] - replay[month] for month in paper])
    if abs(tracking) > branch["max_abs_tracking_difference_per_year"]:
        reasons.append("tracking_difference")
    bound = (
        record.in_sample_mean_annual_net_excess
        - branch["min_net_excess_standard_errors_below_in_sample_mean"]
        * record.in_sample_standard_error_annual
    )
    if _annualised_mean(list(paper.values())) < bound:
        reasons.append("net_excess_below_bound")
    return ForwardCheckVerdict("fail" if reasons else "pass", reasons)


_MONTH_KEY = re.compile(r"[0-9]{4}-(0[1-9]|1[0-2])")


def _forward_record_problems(record: PortfolioForwardRecord) -> list[str]:
    problems: list[str] = []
    for name in ("in_sample_mean_annual_net_excess", "in_sample_standard_error_annual"):
        if not math.isfinite(getattr(record, name)):
            problems.append(f"non_finite_in_sample: {name}")
    if math.isfinite(record.in_sample_standard_error_annual) and (
        record.in_sample_standard_error_annual < 0
    ):
        problems.append("negative_standard_error")

    ledgers = {
        "paper": list(record.paper_monthly_net_excess),
        "replay": list(record.replay_monthly_net_excess),
    }
    for ledger, rows in ledgers.items():
        non_finite = [month for month, value in rows if not math.isfinite(value)]
        if non_finite:
            problems.append(f"non_finite_return: {ledger} {', '.join(map(str, non_finite))}")
        malformed = [m for m, _ in rows if not (isinstance(m, str) and _MONTH_KEY.fullmatch(m))]
        problems.extend(f"malformed_month: {ledger} {month!r}" for month in malformed)
        months = [month for month, _ in rows if month not in malformed]
        duplicated = sorted({month for month in months if months.count(month) > 1})
        if duplicated:
            problems.append(f"duplicate_month: {ledger} {', '.join(duplicated)}")
        missing = _missing_months(set(months))
        if missing:
            problems.append(f"months_not_consecutive: {ledger} {', '.join(missing)}")

    paper_months = {month for month, _ in ledgers["paper"]}
    replay_months = {month for month, _ in ledgers["replay"]}
    if paper_months != replay_months:
        paper_only = ", ".join(sorted(map(str, paper_months - replay_months))) or "none"
        replay_only = ", ".join(sorted(map(str, replay_months - paper_months))) or "none"
        problems.append(f"month_mismatch: paper only {paper_only}; replay only {replay_only}")
    return problems


def _missing_months(months: set[str]) -> list[str]:
    """Months absent between the earliest and latest of `months` (all `YYYY-MM`)."""
    if not months:
        return []
    indices = {int(month[:4]) * 12 + int(month[5:]) - 1 for month in months}
    return [
        f"{index // 12:04d}-{index % 12 + 1:02d}"
        for index in range(min(indices), max(indices) + 1)
        if index not in indices
    ]


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


@dataclass(frozen=True)
class WalkForwardSettings:
    in_sample_months: int = 18
    oos_months: int = 6
    embargo_days: int = 30


class EvaluationProtocol:
    """The gate every evaluation passes before it reads returns, and the event evaluation.

    Admission verifies the hypothesis against its registration, then refuses anything the
    protocol does not budget or allow: an unknown family, a family over its trial budget once
    every registered hypothesis is counted, a role the family does not hold, or a short or
    options position above the instrument ceilings.

    `run` needs `prices` and `costs`; admission alone does not.
    """

    def __init__(
        self,
        *,
        config_dir: Path | None = None,
        registry_path: Path | None = None,
        prices: PriceSnapshotStore | None = None,
        costs: TradeCosts | None = None,
        calendar: MarketCalendar | None = None,
        walk_forward: WalkForwardSettings | None = None,
    ) -> None:
        self._config_dir = config_dir if config_dir is not None else Path("config/hypotheses")
        self._registry_path = registry_path
        self._verify_protocol()
        self.protocol: dict[str, Any] = load_hypothesis(_PROTOCOL_ID, self._config_dir)
        self._prices = prices
        self._costs = costs
        self._calendar = calendar or MarketCalendar()
        self._walk_forward = walk_forward or WalkForwardSettings()

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

    def ledger(self) -> TrialLedger:
        return TrialLedger(
            self._config_dir / "trials",
            self.protocol,
            {str(h["id"]): h for h in self._registered()},
        )

    def run(
        self,
        hypothesis_id: str,
        events: pd.DataFrame,
        variant: str,
        *,
        holding_period_days: Sequence[int] | None = None,
        known_at_delay_days: Sequence[int] | None = None,
        run_id: str | None = None,
    ) -> EvaluationResult:
        """Evaluate an event hypothesis on the events before the holdout.

        `events` holds one row per event of `variant`, with `ticker` and `corroborated_at`.
        The cells are every requested horizon at every requested known-at delay (default: the
        hypothesis's declared grid). Every refusal comes before the cells are reserved in the
        trial ledger, and the reservation comes before any price is read.
        """
        self._verify_protocol()
        hypothesis = self.admit(hypothesis_id)
        if hypothesis.get("status") == "suspended":
            raise HypothesisSuspendedError(
                f"{hypothesis_id} is suspended: {hypothesis.get('suspended_reason', '')}".strip()
            )
        if hypothesis.get("evaluation", "event") != "event":
            raise ValueError(f"{hypothesis_id} is not an event hypothesis")
        windows = _windows(hypothesis, holding_period_days)
        delays = _requested(hypothesis, "known_at_delay_days", known_at_delay_days)
        _requested(hypothesis, "variants", [variant])
        if self._prices is None or self._costs is None:
            raise EvaluationConfigError("run() needs prices and costs")
        n_bootstrap = _required_int_env("N_BOOTSTRAP")

        run_id = run_id or str(uuid.uuid4())
        cells = [
            {**_cell_key(holding, window), "known_at_delay_days": delay, "variant": variant}
            for (holding, window), delay in itertools.product(windows, delays)
        ]
        ledger = self.ledger()
        reservation = ledger.reserve(hypothesis_id, cells, run_id)
        n_trials = max(reservation.family_trial_count, 1)

        splitter = WalkForwardSplitter(int(self.protocol["promotion"]["holdout_months"]))
        readable = splitter.before_holdout(events)
        n_holdout = len(events) - len(readable)
        known_at = KnownAtDelay(self._calendar)
        direction = -1 if str(hypothesis.get("direction", "")) == "short" else 1

        results = [
            self._evaluate_cell(
                known_at.apply(readable, delay),
                holding,
                window,
                delay,
                variant,
                direction,
                n_trials,
                n_bootstrap,
            )
            for (holding, window), delay in itertools.product(windows, delays)
        ]
        verdicts = tuple(
            KillCriteria(self.protocol, {hypothesis_id: hypothesis}).evaluate(
                hypothesis_id, results
            )
        )
        segments, note = self._segments(splitter, events)
        headline = next((r for r in results if is_primary_cell(r, hypothesis)), results[0])
        result = EvaluationResult(
            hypothesis_id=hypothesis_id,
            role=str(hypothesis.get("role")),
            variant=variant,
            holding_period_days=headline.holding_period_days,
            n_events=headline.n_events,
            n_independent_events=headline.n_independent_events,
            known_at_delay_days=headline.known_at_delay_days,
            mean_abnormal_return=headline.mean_abnormal_return,
            t_stat=headline.t_stat,
            p_value=headline.p_value,
            inference_method=headline.inference_method,
            n_estimation_fallback=headline.n_estimation_fallback,
            deflated_sharpe=headline.deflated_sharpe,
            n_trials=n_trials,
            is_primary_cell=is_primary_cell(headline, hypothesis),
            bootstrap_ci_95=headline.bootstrap_ci_95,
            hit_rate=headline.hit_rate,
            net_expectancy_eur=headline.net_expectancy_eur,
            kill_verdicts=verdicts,
            walk_forward_segments=segments,
            walk_forward_note=note,
            holdout_sealed=True,
            n_holdout_events=n_holdout,
            run_id=run_id,
            trades=headline.trades,
            cells=tuple(results),
        )
        return replace(result, holdout_sealed=HoldoutGuard(self.protocol).is_sealed(result))

    def _evaluate_cell(
        self,
        events: pd.DataFrame,
        holding: int | None,
        window: tuple[int, int],
        delay: int,
        variant: str,
        direction: int,
        n_trials: int,
        n_bootstrap: int,
    ) -> CellResult:
        assert self._prices is not None and self._costs is not None
        series = AbnormalReturnCalculator(self.protocol).compute(
            events, self._prices, window, direction=direction
        )
        trades = tuple(
            self._costs.trade(
                ticker,
                entry,
                end,
                price_on(self._prices, ticker, entry, "open"),
                direction * value,
            )
            for ticker, entry, end, value in zip(
                series.tickers, series.entry_dates, series.window_ends, series.values, strict=True
            )
        )
        net = series.with_values(
            [v - direction * t.cost_fraction for v, t in zip(series.values, trades, strict=True)]
        )
        inference = ClusteredInference(self.protocol)
        gross_inference = inference.t_stat(series)
        net_inference = inference.t_stat(net)
        return CellResult(
            holding_period_days=holding,
            window=window,
            known_at_delay_days=delay,
            variant=variant,
            n_events=series.n,
            n_independent_events=gross_inference.n_independent,
            mean_abnormal_return=series.mean,
            t_stat=gross_inference.t_stat,
            p_value=gross_inference.p_value,
            inference_method=gross_inference.method,
            n_estimation_fallback=series.n_fallback,
            hit_rate=series.hit_rate,
            mean_net_abnormal_return=net.mean,
            net_t_stat=net_inference.t_stat,
            median_cost_fraction=(
                float(np.median([t.cost_fraction for t in trades])) if trades else float("nan")
            ),
            deflated_sharpe=_deflated_sharpe(net.values, direction, n_trials),
            bootstrap_ci_95=BootstrapCI.compute(list(series.values), n_bootstrap=n_bootstrap),
            net_expectancy_eur=(
                float(np.mean([t.net_eur for t in trades])) if trades else float("nan")
            ),
            trades=trades,
        )

    def _segments(
        self, splitter: WalkForwardSplitter, events: pd.DataFrame
    ) -> tuple[tuple[WalkForwardSegment, ...], str | None]:
        wf = self._walk_forward
        try:
            segments = splitter.split(events, wf.in_sample_months, wf.oos_months, wf.embargo_days)
        except InsufficientEventsError as exc:
            return (), f"no walk-forward segment: {exc}"
        note = None
        if any(s.oos_truncated for s in segments):
            note = (
                "the last out-of-sample segment is cut short by the holdout; at this data "
                "volume walk-forward is a validation check, not a robust out-of-sample regime"
            )
        return tuple(segments), note

    def _verify_protocol(self) -> None:
        verify_hypothesis(
            _PROTOCOL_ID, config_dir=self._config_dir, registry_path=self._registry_path
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


def _windows(
    hypothesis: dict[str, Any], requested: Sequence[int] | None
) -> list[tuple[int | None, tuple[int, int]]]:
    """(holding period, return window) pairs; a horizon `h` is the window `[+1, +h]`."""
    if "holding_period_days_pre" in hypothesis:
        if requested is not None:
            raise UnregisteredCellError(
                f"{hypothesis.get('id')} declares pre- and post-event windows, not horizons"
            )
        return [
            (None, (int(w[0]), int(w[1])))
            for w in (hypothesis["holding_period_days_pre"], hypothesis["holding_period_days_post"])
        ]
    horizons = _requested(hypothesis, "holding_period_days", requested)
    return [(h, (1, h)) for h in horizons]


def _requested(
    hypothesis: dict[str, Any], field_name: str, requested: Sequence[Any] | None
) -> list[Any]:
    declared = hypothesis.get(field_name)
    if declared is None and field_name == "variants":
        declared = [hypothesis.get("signal_definition", {}).get("variant")]
    declared = list(declared or [])
    if requested is None:
        return declared
    outside = [v for v in requested if v not in declared]
    if outside:
        raise UnregisteredCellError(
            f"{hypothesis.get('id')}: {field_name} {outside} outside the declared {declared}"
        )
    return list(requested)


def _cell_key(holding: int | None, window: tuple[int, int]) -> dict[str, Any]:
    if holding is None:
        return {"window": list(window)}
    return {"holding_period_days": holding}


def _deflated_sharpe(values: Sequence[float], direction: int, n_trials: int) -> float:
    returns = pd.Series([direction * v for v in values], dtype=float)
    if len(returns) < 3 or not returns.std(ddof=1) > 0:
        return float("nan")
    return DeflatedSharpe.compute(
        sharpe_ratio=float(returns.mean() / returns.std(ddof=1)),
        n_obs=len(returns),
        n_trials=n_trials,
        skewness=float(returns.skew()),
        kurtosis=float(returns.kurt()) + 3.0,
    )


def _required_int_env(name: str) -> int:
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise EvaluationConfigError(f"{name} is not set; it is required in .env")
    return int(value)


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

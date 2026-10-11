"""The pass/fail decision for a portfolio hypothesis, from registered protocol values only."""

from __future__ import annotations

import json
import math
import os
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Literal, Protocol

import numpy as np

from auspex_backtesting.evaluation import DeflatedSharpe, KillVerdict
from auspex_backtesting.hypothesis import hypothesis_views
from auspex_backtesting.portfolio.engine import Benchmark, PortfolioBacktest, PortfolioResult
from auspex_backtesting.portfolio.rules import PortfolioRule
from auspex_backtesting.protocol import EvaluationProtocol, NotPromotableError, check_promotable

_MONTHS_PER_YEAR = 12
_BENCHMARKS: dict[str, Benchmark] = {"universe_equal_weight": "universe_equal_weight", "XBI": "xbi"}

VerdictStatus = Literal["in_sample_passed", "promoted", "killed", "not_usable", "not_promotable"]


class InputsNotPinnedError(Exception):
    """A final run would read a snapshot that carries no input manifest."""


class HoldoutAlreadyReadError(Exception):
    pass


class HoldoutSealedError(Exception):
    pass


class InputManifests(Protocol):
    def missing(self, keys: Sequence[str]) -> list[str]:
        """The keys among `keys` that have no input manifest."""
        ...


class NoInputManifests:
    """No snapshot carries an input manifest yet, so no run can be marked final."""

    def missing(self, keys: Sequence[str]) -> list[str]:
        return list(keys)


def newey_west_t(values: Sequence[float], lag: int) -> float:
    """t-statistic of the mean with Newey-West (Bartlett kernel) standard errors at `lag`."""
    x = np.asarray(values, dtype=float)
    n = len(x)
    if n < 2:
        return float("nan")
    e = x - x.mean()
    variance = float(e @ e) / n
    for k in range(1, min(lag, n - 1) + 1):
        variance += 2 * (1 - k / (lag + 1)) * float(e[k:] @ e[:-k]) / n
    if variance <= 0:
        return float("nan")
    return float(x.mean() / math.sqrt(variance / n))


@dataclass(frozen=True)
class PortfolioEvidence:
    """What the in-sample verdict reads from a run, as plain numbers.

    `top_quintile_net_excess_annual` is the long-only top quintile's net excess over the
    universe equal-weight, from a run of the same rule with `top_quintile` selection.
    """

    monthly_net_excess: Sequence[float]
    monthly_gross_excess: Sequence[float]
    quintile_spread: Sequence[float]
    top_quintile_net_excess_annual: float
    yearly_cost_drag: float
    unpriced_member_month_share: float

    @classmethod
    def from_results(
        cls, result: PortfolioResult, top_quintile: PortfolioResult, benchmark: Benchmark
    ) -> PortfolioEvidence:
        return cls(
            monthly_net_excess=result.monthly_net_excess(benchmark),
            monthly_gross_excess=result.monthly_gross_excess(benchmark),
            quintile_spread=[q.spread for q in result.quintiles],
            top_quintile_net_excess_annual=_annual(
                top_quintile.monthly_net_excess("universe_equal_weight")
            ),
            yearly_cost_drag=result.yearly_cost_drag,
            unpriced_member_month_share=result.unpriced_member_month_share,
        )


@dataclass(frozen=True)
class VerdictReport:
    hypothesis_id: str
    use: str | None
    status: VerdictStatus
    criteria: tuple[KillVerdict, ...]
    deflated_sharpe: float
    newey_west_t: float
    n_trials: int
    is_primary_cell: bool
    holdout_read: bool = False
    holdout: Mapping[str, Any] = field(default_factory=dict)

    @property
    def killed_by(self) -> str | None:
        fired = [
            v.criterion_id for v in self.criteria if v.fired and v.criterion_id != "survivorship"
        ]
        return fired[0] if fired else None

    def to_report(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "use": self.use,
            "status": self.status,
            "killed_by": self.killed_by,
            "criteria": [
                {
                    "criterion_id": v.criterion_id,
                    "fired": v.fired,
                    "inputs": dict(v.inputs),
                    "action": v.action,
                }
                for v in self.criteria
            ],
            "deflated_sharpe": self.deflated_sharpe,
            "newey_west_t": self.newey_west_t,
            "n_trials": self.n_trials,
            "is_primary_cell": self.is_primary_cell,
            "holdout_read": self.holdout_read,
            "holdout": dict(self.holdout),
        }


class PortfolioVerdict:
    """Applies `portfolio_inference` and `portfolio_kill_criteria` from the registered protocol.

    The protocol is verified against its registration when this is built, so an edited file
    that was not re-registered raises before any threshold is read.
    """

    def __init__(
        self, protocol: EvaluationProtocol, hypothesis_id: str, use: str | None = None
    ) -> None:
        self._hypothesis = protocol.admit(hypothesis_id)
        self._protocol = protocol.protocol
        self._id = hypothesis_id
        self._use = use
        self._view = next(
            v for v in hypothesis_views(self._hypothesis) if use is None or v.get("use") == use
        )
        if self._view.get("evaluation") != "portfolio":
            raise ValueError(f"{hypothesis_id} is not a portfolio hypothesis")
        inference = self._protocol["portfolio_inference"]
        if (
            inference["standard_errors"] != "newey_west"
            or inference["deflated_sharpe_on"] != "monthly_returns"
            or inference["deflated_sharpe_trials"] != "family_count"
        ):
            raise ValueError(f"unsupported portfolio inference settings: {inference}")
        self._lag = int(inference["newey_west_lag_months"])
        self._dsr_min = float(inference["deflated_sharpe_min"])
        self._criteria = {c["id"]: c for c in self._protocol["portfolio_kill_criteria"]}

    @property
    def view(self) -> Mapping[str, Any]:
        return self._view

    @property
    def family(self) -> str:
        return str(self._view["family"])

    @property
    def benchmark(self) -> Benchmark:
        declared = (self._view.get("benchmarks") or {}).get("excess", "universe_equal_weight")
        return _BENCHMARKS[str(declared)]

    @property
    def primary_cell(self) -> Mapping[str, Any]:
        return self._view.get("primary_cell") or {}

    def in_sample(
        self, evidence: PortfolioEvidence, *, n_trials: int, is_primary_cell: bool
    ) -> VerdictReport:
        criteria = (
            self._no_in_sample_spread(evidence),
            self._turnover_cost(evidence),
            self._survivorship(evidence),
        )
        net = np.asarray(evidence.monthly_net_excess, dtype=float)
        dsr = _deflated_sharpe(net, n_trials)
        t = newey_west_t(list(net), self._lag)
        try:
            check_promotable(self._hypothesis, self._use)
            promotable = True
        except NotPromotableError:
            promotable = False
        status: VerdictStatus
        if any(v.fired for v in criteria if v.criterion_id != "survivorship"):
            status = "killed"
        elif criteria[2].fired:
            status = "not_usable"
        elif not promotable or not is_primary_cell:
            status = "not_promotable"
        elif dsr >= self._dsr_min:
            status = "in_sample_passed"
        else:
            status = "not_promotable"
        return VerdictReport(
            hypothesis_id=self._id,
            use=self._use,
            status=status,
            criteria=criteria,
            deflated_sharpe=dsr,
            newey_west_t=t,
            n_trials=n_trials,
            is_primary_cell=is_primary_cell,
        )

    def holdout(
        self, in_sample: VerdictReport, monthly_net_excess: Sequence[float]
    ) -> VerdictReport:
        """The final verdict from the holdout's monthly net excess returns."""
        if in_sample.status != "in_sample_passed":
            raise HoldoutSealedError(f"{self._id}: in-sample verdict is {in_sample.status}")
        criterion = self._criteria["holdout_check"]
        annual = _annual(monthly_net_excess)
        t = newey_west_t(monthly_net_excess, self._lag)
        min_excess = float(criterion["min_annual_net_excess"])
        min_t = float(criterion["min_newey_west_t"])
        fired = not (annual >= min_excess and t >= min_t)
        verdict = KillVerdict(
            "holdout_check",
            fired,
            {
                "annual_net_excess": annual,
                "newey_west_t": t,
                "min_annual_net_excess": min_excess,
                "min_newey_west_t": min_t,
                "months": len(monthly_net_excess),
            },
            str(criterion["action"]),
        )
        return replace(
            in_sample,
            status="killed" if fired else "promoted",
            criteria=(*in_sample.criteria, verdict),
            holdout_read=True,
            holdout={"annual_net_excess": annual, "newey_west_t": t},
        )

    def _no_in_sample_spread(self, evidence: PortfolioEvidence) -> KillVerdict:
        c = self._criteria["no_in_sample_spread"]
        min_t = float(c["min_top_minus_bottom_quintile_newey_west_t"])
        min_excess = float(c["min_top_quintile_net_excess_over_universe_equal_weight"])
        t = newey_west_t(evidence.quintile_spread, self._lag)
        top = evidence.top_quintile_net_excess_annual
        fired = not (t >= min_t and top > min_excess)
        return KillVerdict(
            "no_in_sample_spread",
            fired,
            {
                "spread_newey_west_t": t,
                "min_t": min_t,
                "top_quintile_net_excess_annual": top,
                "min_top_quintile_net_excess": min_excess,
            },
            str(c["action"]),
        )

    def _turnover_cost(self, evidence: PortfolioEvidence) -> KillVerdict:
        c = self._criteria["turnover_cost"]
        ratio = float(c["max_cost_to_gross_excess_ratio"])
        gross = _annual(evidence.monthly_gross_excess)
        fired = evidence.yearly_cost_drag > ratio * gross
        return KillVerdict(
            "turnover_cost",
            fired,
            {
                "yearly_cost_drag": evidence.yearly_cost_drag,
                "annual_gross_excess": gross,
                "max_cost_to_gross_excess_ratio": ratio,
            },
            str(c["action"]),
        )

    def _survivorship(self, evidence: PortfolioEvidence) -> KillVerdict:
        c = self._criteria["survivorship"]
        limit = float(c["max_unpriced_member_month_share"])
        share = evidence.unpriced_member_month_share
        return KillVerdict(
            "survivorship",
            share > limit,
            {"unpriced_member_month_share": share, "max_unpriced_member_month_share": limit},
            str(c["action"]),
        )


class HoldoutRecord:
    """One file per hypothesis use, created exclusively when its holdout is read."""

    def __init__(self, directory: Path) -> None:
        self._dir = directory

    def was_read(self, hypothesis_id: str, use: str | None) -> bool:
        return self._path(hypothesis_id, use).exists()

    def claim(self, hypothesis_id: str, use: str | None, run_id: str) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        path = self._path(hypothesis_id, use)
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError:
            raise HoldoutAlreadyReadError(
                f"{path.stem}: the holdout was already read ({path.read_text(encoding='utf-8').strip()})"
            ) from None
        try:
            line = json.dumps({"run_id": run_id, "read_at": datetime.now(UTC).isoformat()})
            os.write(fd, (line + "\n").encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)

    def _path(self, hypothesis_id: str, use: str | None) -> Path:
        return self._dir / (f"{hypothesis_id}.{use}.json" if use else f"{hypothesis_id}.json")


@dataclass(frozen=True)
class PortfolioReport:
    """A run at every capital tier; the verdict is judged at the smallest, where fixed costs
    weigh most."""

    run_id: str
    cell: Mapping[str, Any]
    in_sample: Mapping[float, PortfolioResult]
    verdict: VerdictReport
    holdout: Mapping[float, PortfolioResult] = field(default_factory=dict)


class PortfolioEvaluation:
    """Admits a portfolio hypothesis, reserves its cell, runs it in-sample at each capital
    tier, and reads the holdout once, only on a final run whose in-sample verdict passed.

    Every refusal (an unregistered file, inputs without manifests on a final run, a holdout
    already read) comes before the cell is reserved, and the reservation before any return.
    """

    def __init__(
        self,
        protocol: EvaluationProtocol,
        engine: PortfolioBacktest,
        manifests: InputManifests,
        holdout_record: HoldoutRecord,
    ) -> None:
        self._protocol = protocol
        self._engine = engine
        self._manifests = manifests
        self._holdout = holdout_record

    def run(
        self,
        hypothesis_id: str,
        cell: Mapping[str, Any],
        rule: PortfolioRule,
        universe_version: int,
        tiers_eur: Sequence[float],
        *,
        use: str | None = None,
        final: bool = False,
        run_id: str | None = None,
    ) -> PortfolioReport:
        if not tiers_eur:
            raise ValueError("at least one capital tier is required")
        verdict = PortfolioVerdict(self._protocol, hypothesis_id, use)
        in_sample = _years(verdict.view["in_sample_years"])
        holdout = _years(verdict.view["holdout_years"])
        if final:
            keys = self._engine.input_keys(rule, universe_version, in_sample[0], holdout[1])
            missing = self._manifests.missing(keys)
            if missing:
                raise InputsNotPinnedError(
                    f"{len(missing)} snapshots have no input manifest, first {missing[0]}"
                )
            if self._holdout.was_read(hypothesis_id, use):
                raise HoldoutAlreadyReadError(f"{hypothesis_id}: the holdout was already read")
        run_id = run_id or str(uuid.uuid4())
        ledger = self._protocol.ledger()
        ledger.reserve(hypothesis_id, [dict(cell)], run_id, use)
        n_trials = max(ledger.family_trial_count(verdict.family), 1)

        tiers = sorted(tiers_eur)
        results = {t: self._engine.run(rule, universe_version, t, *in_sample) for t in tiers}
        top_rule = replace(rule, selection="top_quintile", catalyst_guard="none", exclusion=None)
        top = self._engine.run(top_rule, universe_version, tiers[0], *in_sample)
        evidence = PortfolioEvidence.from_results(results[tiers[0]], top, verdict.benchmark)
        is_primary = dict(cell) == dict(verdict.primary_cell)
        report = verdict.in_sample(evidence, n_trials=n_trials, is_primary_cell=is_primary)
        if not final or report.status != "in_sample_passed":
            return PortfolioReport(run_id, dict(cell), results, report)

        self._holdout.claim(hypothesis_id, use, run_id)
        holdout_results = {t: self._engine.run(rule, universe_version, t, *holdout) for t in tiers}
        final_report = verdict.holdout(
            report, holdout_results[tiers[0]].monthly_net_excess(verdict.benchmark)
        )
        return PortfolioReport(run_id, dict(cell), results, final_report, holdout_results)


def _years(window: Sequence[int]) -> tuple[date, date]:
    return date(int(window[0]), 1, 1), date(int(window[1]), 12, 31)


def _annual(monthly: Sequence[float]) -> float:
    values = list(monthly)
    return sum(values) / len(values) * _MONTHS_PER_YEAR if values else float("nan")


def _deflated_sharpe(returns: np.ndarray, n_trials: int) -> float:
    if len(returns) < 3 or not float(np.std(returns, ddof=1)) > 0:
        return float("nan")
    mean, std = float(returns.mean()), float(np.std(returns, ddof=1))
    centred = returns - mean
    skew = float(np.mean(centred**3) / np.mean(centred**2) ** 1.5)
    kurt = float(np.mean(centred**4) / np.mean(centred**2) ** 2)
    return DeflatedSharpe.compute(
        sharpe_ratio=mean / std, n_obs=len(returns), n_trials=n_trials, skewness=skew, kurtosis=kurt
    )

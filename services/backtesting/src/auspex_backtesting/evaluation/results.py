from __future__ import annotations

import dataclasses
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd

from auspex_backtesting.evaluation.walk_forward import WalkForwardSegment, WalkForwardSplitter


class HoldoutSealedError(Exception):
    pass


@dataclass(frozen=True)
class TradeRecord:
    """One event traded at a fixed EUR position: gross abnormal P&L, costs and the net."""

    ticker: str
    entry_date: date
    exit_date: date
    shares: int
    entry_price_usd: float
    abnormal_return: float
    gross_eur: float
    cost_eur: float
    net_eur: float
    costs: Mapping[str, float]

    @property
    def cost_fraction(self) -> float:
        """Round-trip cost as a fraction of the entry notional."""
        return sum(self.costs.values()) / (self.shares * self.entry_price_usd)


@dataclass(frozen=True)
class KillVerdict:
    criterion_id: str
    fired: bool
    inputs: Mapping[str, Any]
    action: str


@dataclass(frozen=True)
class CellResult:
    """One evaluated cell: a return window at one known-at delay and variant.

    `holding_period_days` is None for a diagnostic window that is not a holding period (H3's
    pre- and post-event windows). `t_stat` is for the gross mean, `net_t_stat` for the mean net
    of each trade's modelled cost.
    """

    holding_period_days: int | None
    window: tuple[int, int]
    known_at_delay_days: int
    variant: str
    n_events: int
    n_independent_events: int
    mean_abnormal_return: float
    t_stat: float
    p_value: float
    inference_method: str
    n_estimation_fallback: int
    hit_rate: float
    mean_net_abnormal_return: float
    net_t_stat: float
    median_cost_fraction: float
    deflated_sharpe: float
    bootstrap_ci_95: tuple[float, float]
    net_expectancy_eur: float
    trades: tuple[TradeRecord, ...]


@dataclass(frozen=True)
class EvaluationResult:
    """A run's headline cell (the primary cell when the run evaluated it), and every cell.

    Statistics cover the events before the holdout; `n_holdout_events` were left unread.
    """

    hypothesis_id: str
    role: str
    variant: str
    holding_period_days: int | None
    n_events: int
    n_independent_events: int
    known_at_delay_days: int
    mean_abnormal_return: float
    t_stat: float
    p_value: float
    inference_method: str
    n_estimation_fallback: int
    deflated_sharpe: float
    n_trials: int
    is_primary_cell: bool
    bootstrap_ci_95: tuple[float, float]
    hit_rate: float
    net_expectancy_eur: float
    kill_verdicts: tuple[KillVerdict, ...]
    walk_forward_segments: tuple[WalkForwardSegment, ...]
    walk_forward_note: str | None
    holdout_sealed: bool
    n_holdout_events: int
    run_id: str
    trades: tuple[TradeRecord, ...]
    cells: tuple[CellResult, ...]

    def to_report(self) -> dict[str, Any]:
        """The evaluation report as plain data, for `DECISIONS.md` and the strategy metrics."""
        headline = {
            f.name: getattr(self, f.name)
            for f in dataclasses.fields(self)
            if f.name not in {"kill_verdicts", "walk_forward_segments", "trades", "cells"}
        }
        return {
            **headline,
            "kill_verdicts": [dataclasses.asdict(v) for v in self.kill_verdicts],
            "walk_forward_segments": [
                {
                    "in_sample_start": s.in_sample_start,
                    "boundary": s.boundary,
                    "oos_end": s.oos_end,
                    "oos_truncated": s.oos_truncated,
                    "n_in_sample": len(s.in_sample),
                    "n_oos": len(s.oos),
                }
                for s in self.walk_forward_segments
            ],
            "trades": [_trade(t) for t in self.trades],
            "cells": [
                {
                    **{
                        f.name: getattr(c, f.name)
                        for f in dataclasses.fields(c)
                        if f.name != "trades"
                    },
                    "trades": [_trade(t) for t in c.trades],
                }
                for c in self.cells
            ],
        }


class KillCriteria:
    """The protocol's registered kill criteria that this module can judge from cell results.

    `mapping_quality` and `forward_check` are judged elsewhere (golden-set evaluation, forward
    paper trading); `thresholds()` gives those callers the same registered values.
    """

    def __init__(self, protocol: dict[str, Any], hypotheses: Mapping[str, dict[str, Any]]) -> None:
        self._criteria: dict[str, dict[str, Any]] = {c["id"]: c for c in protocol["kill_criteria"]}
        self._hypotheses = hypotheses

    def thresholds(self, criterion_id: str) -> Mapping[str, Any]:
        return self._criteria[criterion_id]

    def evaluate(self, hypothesis_id: str, results: Sequence[CellResult]) -> list[KillVerdict]:
        hypothesis = self._hypotheses[hypothesis_id]
        verdicts: list[KillVerdict] = []
        for criterion_id, judge in (
            ("lagging_signal", self._lagging_signal),
            ("no_in_sample_effect", self._no_in_sample_effect),
            ("cost_check", self._cost_check),
        ):
            criterion = self._criteria.get(criterion_id)
            if criterion is None or not _applies(criterion, hypothesis):
                continue
            fired, inputs = judge(criterion, hypothesis, results)
            verdicts.append(KillVerdict(criterion_id, fired, inputs, str(criterion["action"])))
        return verdicts

    def _lagging_signal(
        self, criterion: dict[str, Any], hypothesis: dict[str, Any], results: Sequence[CellResult]
    ) -> tuple[bool, dict[str, Any]]:
        def car(window: tuple[int, int]) -> float | None:
            return next(
                (
                    r.mean_abnormal_return
                    for r in results
                    if r.window == window and r.known_at_delay_days == 1
                ),
                None,
            )

        pre, post = car((-20, -1)), car((1, 20))
        inputs: dict[str, Any] = {"mean_car_pre": pre, "mean_car_post": post}
        if pre is None or post is None:
            return False, {**inputs, "evaluated": False}
        same_sign = math.copysign(1, pre) == math.copysign(1, post) and pre != 0 and post != 0
        return same_sign and abs(pre) >= abs(post), {**inputs, "evaluated": True}

    def _no_in_sample_effect(
        self, criterion: dict[str, Any], hypothesis: dict[str, Any], results: Sequence[CellResult]
    ) -> tuple[bool, dict[str, Any]]:
        primary = hypothesis.get("primary_cell") or {}
        sign = _direction(hypothesis)
        min_mean = float(criterion["min_mean_net_abnormal_return"])
        min_t = float(criterion["min_clustered_t"])
        horizons = {
            r.holding_period_days: (r.mean_net_abnormal_return, r.net_t_stat)
            for r in results
            if r.holding_period_days is not None
            and r.known_at_delay_days == primary.get("known_at_delay_days")
            and r.variant == primary.get("variant")
        }
        passing = [
            h for h, (mean, t) in horizons.items() if sign * mean > min_mean and sign * t >= min_t
        ]
        inputs = {
            "horizons": horizons,
            "min_mean_net_abnormal_return": min_mean,
            "min_clustered_t": min_t,
            "passing_horizons": passing,
        }
        return not passing, inputs

    def _cost_check(
        self, criterion: dict[str, Any], hypothesis: dict[str, Any], results: Sequence[CellResult]
    ) -> tuple[bool, dict[str, Any]]:
        primary = hypothesis.get("primary_cell") or {}
        cell = next((r for r in results if _is_primary(r, primary)), None)
        ratio = float(criterion["max_cost_to_gross_ratio"])
        if cell is None:
            return False, {"evaluated": False, "max_cost_to_gross_ratio": ratio}
        gross = _direction(hypothesis) * cell.mean_abnormal_return
        inputs = {
            "evaluated": True,
            "median_cost_fraction": cell.median_cost_fraction,
            "expected_gross_abnormal_return": gross,
            "max_cost_to_gross_ratio": ratio,
        }
        return cell.median_cost_fraction > ratio * gross, inputs


class HoldoutGuard:
    """Keeps the holdout unread until a result on the primary cell clears promotion."""

    def __init__(self, protocol: dict[str, Any]) -> None:
        promotion = protocol["promotion"]
        if promotion["judged_on"] != "primary_cell":
            raise ValueError(f"unsupported promotion basis: {promotion['judged_on']}")
        self._dsr_min = float(promotion["deflated_sharpe_min"])
        self._t_min = float(promotion["clustered_t_min"])
        self._splitter = WalkForwardSplitter(holdout_months=int(promotion["holdout_months"]))

    def is_promotable(self, result: EvaluationResult) -> bool:
        return (
            result.role == "promotable"
            and result.is_primary_cell
            and result.deflated_sharpe > self._dsr_min
            and result.t_stat > self._t_min
            and not any(v.fired for v in result.kill_verdicts)
        )

    def is_sealed(self, result: EvaluationResult) -> bool:
        return not self.is_promotable(result)

    def run_holdout(self, result: EvaluationResult, events: pd.DataFrame) -> pd.DataFrame:
        """The holdout events, released only for a promotable result."""
        if self.is_sealed(result):
            raise HoldoutSealedError(
                f"{result.hypothesis_id}: the holdout stays sealed until the primary cell is "
                "promoted"
            )
        return self._splitter.holdout(events)


def _applies(criterion: dict[str, Any], hypothesis: dict[str, Any]) -> bool:
    applies_to = criterion.get("applies_to")
    if isinstance(applies_to, list):
        return hypothesis.get("id") in applies_to
    return applies_to == hypothesis.get("role")


def _direction(hypothesis: dict[str, Any]) -> int:
    return -1 if str(hypothesis.get("direction", "")) == "short" else 1


def _is_primary(cell: CellResult, primary: Mapping[str, Any]) -> bool:
    return bool(primary) and (
        cell.holding_period_days == primary.get("holding_period_days")
        and cell.known_at_delay_days == primary.get("known_at_delay_days")
        and cell.variant == primary.get("variant")
    )


def is_primary_cell(cell: CellResult, hypothesis: dict[str, Any]) -> bool:
    return _is_primary(cell, hypothesis.get("primary_cell") or {})


def _trade(trade: TradeRecord) -> dict[str, Any]:
    return {**dataclasses.asdict(trade), "costs": dict(trade.costs)}

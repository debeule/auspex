"""Behaviour of the evaluation module beyond the spec's listed cases: the cost kill criterion,
the two-way clustered variance, the bootstrap p-value and interval, the trial count a run
reports, the N_BOOTSTRAP requirement, the walk-forward boundary and the holdout once released."""

import math
from datetime import date
from pathlib import Path

import numpy as np
import pytest
from evaluation_support import (
    KILL_HYPOTHESES,
    PROTOCOL,
    cell_result,
    evaluation_protocol,
    evaluation_result,
    event_frame,
    monthly_events,
    registered_config,
    return_series,
    run_fixture,
    verdict_for,
)

from auspex_backtesting.evaluation import (
    BootstrapCI,
    ClusteredInference,
    HoldoutGuard,
    InsufficientEventsError,
    KillCriteria,
    KillVerdict,
    WalkForwardSplitter,
)
from auspex_backtesting.protocol import EvaluationConfigError


def test_cost_check_kill_fires_when_median_cost_exceeds_half_the_gross_return() -> None:
    kill = KillCriteria(PROTOCOL, KILL_HYPOTHESES)

    def fired(gross: float, cost_fraction: float) -> bool:
        primary = cell_result((1, 20), gross, holding=20, cost_fraction=cost_fraction)
        return bool(verdict_for(kill.evaluate("h1", [primary]), "cost_check").fired)

    assert fired(gross=0.04, cost_fraction=0.025) is True
    assert fired(gross=0.04, cost_fraction=0.015) is False


def test_two_way_clustered_t_matches_hand_computation() -> None:
    rng = np.random.default_rng(23)
    values = list(rng.normal(0.01, 0.05, 40))
    series = return_series(
        values,
        [f"T{i}" for i in range(40)],
        [date(2021 + i // 12, 1 + i % 12, 2) for i in range(40)],
    )

    result = ClusteredInference(PROTOCOL).t_stat(series)

    # One event per ticker and per month: each one-way variance, and the intersection's, is
    # G / (G - 1) * sum(e^2) / n^2, so the two-way variance equals it once.
    x = np.array(values)
    variance = 40 / 39 * float(((x - x.mean()) ** 2).sum()) / 40**2
    assert result.t_stat == pytest.approx(x.mean() / math.sqrt(variance))


def test_wild_bootstrap_p_value_separates_an_effect_from_noise() -> None:
    rng = np.random.default_rng(29)
    tickers = [f"T{i % 8}" for i in range(80)]
    dates = [date(2023, 1 + i % 12, 2) for i in range(80)]
    inference = ClusteredInference(PROTOCOL)

    effect = inference.t_stat(return_series(list(rng.normal(0.05, 0.02, 80)), tickers, dates))
    noise = inference.t_stat(return_series(list(rng.normal(0.0, 0.02, 80)), tickers, dates))

    assert effect.method == noise.method == "wild_cluster_bootstrap"
    assert effect.p_value < 0.05
    assert noise.p_value > 0.05


def test_run_reports_the_family_trial_count_including_its_own_cells(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("N_BOOTSTRAP", "200")
    config_dir, registry = registered_config(tmp_path)
    prices, events, _ = run_fixture()
    protocol = evaluation_protocol(config_dir, registry, prices)

    first = protocol.run(
        "h1", events, "entity-only", holding_period_days=[20], known_at_delay_days=[1]
    )
    second = protocol.run(
        "h1", events, "full", holding_period_days=[10, 20], known_at_delay_days=[1]
    )

    assert (first.n_trials, second.n_trials) == (1, 3)
    assert len(second.cells) == 2


def test_run_without_n_bootstrap_is_refused_before_reserving(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("N_BOOTSTRAP", raising=False)
    config_dir, registry = registered_config(tmp_path)
    prices, events, _ = run_fixture()

    with pytest.raises(EvaluationConfigError, match="N_BOOTSTRAP"):
        evaluation_protocol(config_dir, registry, prices).run("h1", events, "entity-only")
    assert not (config_dir / "trials" / "h1.jsonl").exists()


def test_holdout_is_released_for_a_promotable_result() -> None:
    events = monthly_events(date(2023, 1, 1), 24)

    holdout = HoldoutGuard(PROTOCOL).run_holdout(evaluation_result(), events)

    assert len(holdout) == 3 * 3
    assert min(holdout["corroborated_at"]) >= date(2024, 10, 1)


def test_bootstrap_ci_matches_the_standard_error_of_the_mean() -> None:
    values = np.random.default_rng(31).normal(0.0, 0.05, 400)

    lo, hi = BootstrapCI.compute(list(values), n_bootstrap=4_000)

    expected = 2 * 1.96 * values.std(ddof=1) / math.sqrt(len(values))
    assert hi - lo == pytest.approx(expected, rel=0.1)


def test_walk_forward_split_needs_out_of_sample_time_before_the_holdout() -> None:
    events = event_frame(
        [("SRPT", date(2023, 1, 1)), ("SRPT", date(2023, 9, 1)), ("SRPT", date(2024, 6, 30))],
        "corroborated_at",
    )

    with pytest.raises(InsufficientEventsError):
        WalkForwardSplitter(holdout_months=0).split(
            events, in_sample_months=18, oos_months=6, embargo_days=0
        )


def test_a_fired_kill_criterion_blocks_promotion() -> None:
    fired = KillVerdict(
        "cost_check", True, {}, "raise the liquidity floor and re-register, or stop"
    )

    assert HoldoutGuard(PROTOCOL).is_promotable(evaluation_result(kill_verdicts=(fired,))) is False

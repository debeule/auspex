import copy
import json
import math
import multiprocessing
import statistics
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
from evaluation_support import (
    CALENDAR,
    FLAT_COSTS,
    KILL_HYPOTHESES,
    PROTOCOL,
    SESSIONS,
    TEST_HYPOTHESIS,
    Prices,
    bouncing_before,
    cell_result,
    closes_from,
    evaluation_protocol,
    evaluation_result,
    event_frame,
    ledger_cells,
    market_returns,
    monthly_events,
    price_frame,
    registered_config,
    return_series,
    run_fixture,
    trial_ledger,
    verdict_for,
)

from auspex_backtesting.evaluation import (
    AbnormalReturnCalculator,
    AbnormalReturnSeries,
    BootstrapCI,
    CellResult,
    ClusteredInference,
    DeflatedSharpe,
    HoldoutGuard,
    HoldoutSealedError,
    HypothesisSuspendedError,
    KillCriteria,
    TrialBudgetExhaustedError,
    TrialLedgerCorruptError,
    UnregisteredCellError,
    WalkForwardSplitter,
)
from auspex_backtesting.evaluation import ledger as ledger_module
from auspex_backtesting.hypothesis import HypothesisModifiedError
from auspex_backtesting.market_sim import (
    CostModel,
    SpreadEstimator,
)

# --- abnormal returns -----------------------------------------------------------------------


def test_market_model_abnormal_return_removes_beta_exposure() -> None:
    r_m = market_returns(len(SESSIONS))
    prices = Prices(
        {
            "XBI": price_frame(SESSIONS, closes_from(r_m)),
            "SRPT": price_frame(SESSIONS, closes_from(1.8 * r_m)),
        }
    )
    entry = SESSIONS[400]

    series = AbnormalReturnCalculator(PROTOCOL).compute(
        event_frame([("SRPT", entry)]), prices, window=(1, 20)
    )

    assert series.values[0] == pytest.approx(0.0, abs=1e-9)
    assert series.betas[0] == pytest.approx(1.8)
    raw_excess = float(np.sum(0.8 * r_m[401:421]))
    assert abs(raw_excess) > 1e-3


def test_market_model_estimation_excludes_event_and_gap_days() -> None:
    r_m = market_returns(len(SESSIONS))
    noise = np.random.default_rng(3).normal(0, 0.01, len(SESSIONS))
    calm = 1.3 * r_m + noise
    shocked = calm.copy()
    shocked[400 - 10] += 0.25
    calculator = AbnormalReturnCalculator(PROTOCOL)
    entry = SESSIONS[400]

    def run(returns: np.ndarray) -> AbnormalReturnSeries:
        prices = Prices(
            {
                "XBI": price_frame(SESSIONS, closes_from(r_m)),
                "SRPT": price_frame(SESSIONS, closes_from(returns)),
            }
        )
        return calculator.compute(event_frame([("SRPT", entry)]), prices, window=(-20, -1))

    before, after = run(calm), run(shocked)

    assert after.values[0] - before.values[0] == pytest.approx(0.25, rel=1e-6)
    assert after.alphas[0] == pytest.approx(before.alphas[0], abs=1e-12)
    assert after.betas[0] == pytest.approx(before.betas[0], abs=1e-12)


def test_market_model_falls_back_to_market_adjusted_with_short_history() -> None:
    r_m = market_returns(len(SESSIONS))
    r_i = 1.5 * r_m + np.random.default_rng(5).normal(0, 0.01, len(SESSIONS))
    listed = 300
    prices = Prices(
        {
            "XBI": price_frame(SESSIONS, closes_from(r_m)),
            "NEWCO": price_frame(SESSIONS[listed:], closes_from(r_i[listed:])),
        }
    )
    entry = SESSIONS[listed + 60]

    series = AbnormalReturnCalculator(PROTOCOL).compute(
        event_frame([("NEWCO", entry)]), prices, window=(1, 20)
    )

    i0 = listed + 60
    raw_excess = float(np.sum(r_i[i0 + 1 : i0 + 21] - r_m[i0 + 1 : i0 + 21]))
    assert series.values[0] == pytest.approx(raw_excess, abs=1e-12)
    assert series.fallback == (True,)
    assert series.n_fallback == 1


# --- inference ------------------------------------------------------------------------------


def test_clustered_t_stat_is_smaller_than_naive_for_overlapping_same_ticker_events() -> None:
    rng = np.random.default_rng(11)
    start = date(2023, 1, 2)
    dates = [start + timedelta(days=3 * i) for i in range(10)]
    # Each ticker's overlapping events share one shock, so they move together.
    values = [0.05 + e for e in rng.normal(0, 0.003, 10)] + [
        -0.01 + e for e in rng.normal(0, 0.003, 10)
    ]
    series = return_series(values, ["SRPT"] * 10 + ["BEAM"] * 10, dates + dates)

    clustered = ClusteredInference(PROTOCOL).t_stat(series)

    naive = statistics.mean(values) / (statistics.stdev(values) / math.sqrt(len(values)))
    assert abs(clustered.t_stat) < abs(naive)


def test_clustered_inference_uses_wild_bootstrap_below_minimum_clusters() -> None:
    rng = np.random.default_rng(13)
    inference = ClusteredInference(PROTOCOL)

    few = return_series(
        list(rng.normal(0.01, 0.05, 40)),
        [f"T{i % 8}" for i in range(40)],
        [date(2023, 1 + i % 12, 2) for i in range(40)],
    )
    many = return_series(
        list(rng.normal(0.01, 0.05, 40)),
        [f"T{i}" for i in range(40)],
        [date(2021 + i // 12, 1 + i % 12, 2) for i in range(40)],
    )

    few_result = inference.t_stat(few)
    many_result = inference.t_stat(many)

    assert few_result.method == "wild_cluster_bootstrap"
    assert few_result.n_clusters_ticker == 8
    assert many_result.method == "two_way_clustered"
    assert (many_result.n_clusters_ticker, many_result.n_clusters_month) == (40, 40)


def test_independent_event_count_merges_overlapping_same_ticker_windows() -> None:
    start = date(2024, 3, 4)
    series = return_series(
        [0.01, 0.02, 0.03, 0.04],
        ["SRPT", "SRPT", "SRPT", "BEAM"],
        [start, start + timedelta(days=5), start + timedelta(days=10), start],
    )

    inference = ClusteredInference(PROTOCOL)

    assert inference.independent_events(series) == 2
    assert inference.t_stat(series).n_independent == 2


# --- trial ledger ---------------------------------------------------------------------------


def test_family_trial_count_sums_cells_across_promotable_hypotheses(tmp_path: Path) -> None:
    ledger = trial_ledger(tmp_path / "trials")
    ledger.reserve("h1", ledger_cells(8), run_id="h1-a")
    ledger.reserve("h1", ledger_cells(8, "full"), run_id="h1-b")
    ledger.reserve("h4", ledger_cells(4), run_id="h4-a")
    ledger.reserve("h3", ledger_cells(2), run_id="h3-a")

    assert ledger.family_trial_count("event_backfill") == 20
    assert len((tmp_path / "trials" / "h3.jsonl").read_text().splitlines()) == 1


def test_run_refuses_when_family_trial_budget_would_be_exceeded(tmp_path: Path) -> None:
    ledger = trial_ledger(tmp_path / "trials")
    ledger.reserve("h1", ledger_cells(60), run_id="spent")
    before = (tmp_path / "trials" / "h1.jsonl").read_bytes()

    with pytest.raises(TrialBudgetExhaustedError):
        ledger.reserve("h1", ledger_cells(8), run_id="too-many")

    assert (tmp_path / "trials" / "h1.jsonl").read_bytes() == before
    assert ledger.remaining_budget("event_backfill") == 4


def test_run_logs_its_cells_before_reading_returns_and_counts_them_when_it_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("N_BOOTSTRAP", "200")
    config_dir, registry = registered_config(tmp_path)
    prices, events, _ = run_fixture()
    ledger_file = config_dir / "trials" / "h1.jsonl"
    seen_at_first_read: list[int] = []

    class _FailingPrices(Prices):
        def load(self, ticker: str) -> pd.DataFrame | None:
            seen_at_first_read.append(
                len(ledger_file.read_text().splitlines()) if ledger_file.exists() else 0
            )
            raise RuntimeError("price store unavailable")

    protocol = evaluation_protocol(config_dir, registry, _FailingPrices(prices.frames))

    with pytest.raises(RuntimeError):
        protocol.run(
            "h1", events, "entity-only", holding_period_days=[10, 20], known_at_delay_days=[1]
        )

    assert seen_at_first_read[0] == 1
    (line,) = ledger_file.read_text().splitlines()
    assert len(json.loads(line)["cells"]) == 2
    assert protocol.ledger().family_trial_count("event_backfill") == 2


def _reserve_eight(trials_dir: str, results: Any, start: Any) -> None:
    # Widens the gap between the budget check and the write, so an unlocked
    # check-then-write lets both runs through.
    write_line = ledger_module._write_line

    def slow_write(path: Path, line: bytes) -> None:
        time.sleep(0.3)
        write_line(path, line)

    ledger_module._write_line = slow_write
    start.wait()
    try:
        trial_ledger(Path(trials_dir)).reserve(
            "h1", ledger_cells(8), run_id=multiprocessing.current_process().name
        )
        results.put("reserved")
    except TrialBudgetExhaustedError:
        results.put("exhausted")


def test_concurrent_runs_cannot_both_reserve_the_last_cells(tmp_path: Path) -> None:
    trials_dir = tmp_path / "trials"
    trial_ledger(trials_dir).reserve("h4", ledger_cells(56), run_id="spent")
    ctx = multiprocessing.get_context("spawn")
    results = ctx.Queue()
    start = ctx.Barrier(2)
    workers = [
        ctx.Process(target=_reserve_eight, args=(str(trials_dir), results, start)) for _ in range(2)
    ]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=60)

    outcomes = sorted(results.get(timeout=5) for _ in workers)
    assert outcomes == ["exhausted", "reserved"]
    assert trial_ledger(trials_dir).family_trial_count("event_backfill") == 64


def test_torn_final_ledger_line_is_dropped_and_counted_nowhere(tmp_path: Path) -> None:
    trials_dir = tmp_path / "trials"
    ledger = trial_ledger(trials_dir)
    ledger.reserve("h1", ledger_cells(8), run_id="complete")
    ledger_file = trials_dir / "h1.jsonl"
    complete = ledger_file.read_bytes()
    with ledger_file.open("ab") as fh:
        fh.write(b'{"run_id": "torn", "hypothesis_id": "h1", "cells": [{"holding_pe')

    ledger.reserve("h1", ledger_cells(4), run_id="after")

    lines = ledger_file.read_bytes().split(b"\n")
    assert ledger_file.read_bytes().startswith(complete)
    assert [json.loads(line)["run_id"] for line in lines if line] == ["complete", "after"]
    assert ledger.family_trial_count("event_backfill") == 12


def test_read_only_count_skips_a_line_in_flight_and_leaves_the_file_alone(
    tmp_path: Path,
) -> None:
    trials_dir = tmp_path / "trials"
    ledger = trial_ledger(trials_dir)
    ledger.reserve("h1", ledger_cells(8), run_id="complete")
    ledger.reserve("h4", ledger_cells(2), run_id="other hypothesis")
    with (trials_dir / "h1.jsonl").open("ab") as fh:
        fh.write(b'{"run_id": "writing", "hypothesis_id": "h1", "cells": [{"holding_pe')
    before = (trials_dir / "h1.jsonl").read_bytes()
    (trials_dir / ".lock").unlink()
    trials_dir.chmod(0o555)
    try:
        assert ledger.observed_trial_count("event_backfill") == 10
    finally:
        trials_dir.chmod(0o755)
    assert (trials_dir / "h1.jsonl").read_bytes() == before
    assert not (trials_dir / ".lock").exists()


def test_unparseable_complete_ledger_line_refuses_reservations(tmp_path: Path) -> None:
    trials_dir = tmp_path / "trials"
    ledger = trial_ledger(trials_dir)
    ledger.reserve("h1", ledger_cells(8), run_id="complete")
    with (trials_dir / "h1.jsonl").open("ab") as fh:
        fh.write(b'{"run_id": "garbled", "cells": [\n')

    with pytest.raises(TrialLedgerCorruptError):
        ledger.reserve("h4", ledger_cells(1), run_id="refused")
    assert not (trials_dir / "h4.jsonl").exists()


# --- admission of a run ---------------------------------------------------------------------


def test_run_refuses_cell_outside_registered_grid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("N_BOOTSTRAP", "200")
    config_dir, registry = registered_config(tmp_path)
    prices, events, _ = run_fixture()
    protocol = evaluation_protocol(config_dir, registry, prices)

    with pytest.raises(UnregisteredCellError):
        protocol.run("h1", events, "entity-only", holding_period_days=[15])
    assert not (config_dir / "trials" / "h1.jsonl").exists()


def test_run_refuses_suspended_hypothesis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("N_BOOTSTRAP", "200")
    suspended = TEST_HYPOTHESIS.replace("status: pre-registered", "status: suspended")
    config_dir, registry = registered_config(tmp_path, suspended)
    prices, events, _ = run_fixture()

    with pytest.raises(HypothesisSuspendedError):
        evaluation_protocol(config_dir, registry, prices).run("h1", events, "entity-only")
    assert not (config_dir / "trials" / "h1.jsonl").exists()


def test_run_refuses_modified_protocol_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("N_BOOTSTRAP", "200")
    config_dir, registry = registered_config(tmp_path)
    prices, events, _ = run_fixture()
    protocol = evaluation_protocol(config_dir, registry, prices)
    path = config_dir / "protocol.yaml"
    path.write_text(
        path.read_text(encoding="utf-8").replace("clustered_t_min: 3.0", "clustered_t_min: 2.0"),
        encoding="utf-8",
    )

    with pytest.raises(HypothesisModifiedError):
        protocol.run("h1", events, "entity-only")
    with pytest.raises(HypothesisModifiedError):
        evaluation_protocol(config_dir, registry, prices)
    assert not (config_dir / "trials" / "h1.jsonl").exists()


# --- promotion and kill criteria ------------------------------------------------------------


def test_promotion_is_judged_on_primary_cell_only() -> None:
    guard = HoldoutGuard(PROTOCOL)
    strong_sensitivity_cell = evaluation_result(
        is_primary_cell=False, known_at_delay_days=3, t_stat=3.5, deflated_sharpe=0.97
    )
    weak_primary_cell = evaluation_result(is_primary_cell=True, t_stat=1.2, deflated_sharpe=0.97)

    assert guard.is_promotable(strong_sensitivity_cell) is False
    assert guard.is_promotable(weak_primary_cell) is False
    assert guard.is_promotable(evaluation_result(t_stat=3.5, deflated_sharpe=0.97)) is True


def test_lagging_signal_kill_fires_when_pre_window_dominates() -> None:
    kill = KillCriteria(PROTOCOL, KILL_HYPOTHESES)

    def fired(pre: float, post: float) -> bool:
        verdicts = kill.evaluate("h3", [cell_result((-20, -1), pre), cell_result((1, 20), post)])
        return bool(verdict_for(verdicts, "lagging_signal").fired)

    assert fired(0.06, 0.02) is True
    assert fired(0.01, 0.04) is False
    assert fired(-0.03, 0.02) is False


def _horizon_cells(net: dict[int, tuple[float, float]]) -> list[CellResult]:
    return [
        cell_result((1, h), mean, holding=h, net_mean=mean, net_t=t) for h, (mean, t) in net.items()
    ]


def test_no_in_sample_effect_kill_fires_without_a_positive_significant_horizon() -> None:
    kill = KillCriteria(PROTOCOL, KILL_HYPOTHESES)

    def fired(net: dict[int, tuple[float, float]]) -> bool:
        return bool(
            verdict_for(kill.evaluate("h1", _horizon_cells(net)), "no_in_sample_effect").fired
        )

    assert fired({5: (-0.01, -1.0), 10: (0.0, 0.0), 20: (-0.02, -2.0), 30: (-0.005, -0.4)}) is True
    assert fired({5: (-0.01, -1.0), 10: (0.0, 0.0), 20: (0.02, 1.6), 30: (-0.005, -0.4)}) is False
    assert fired({5: (-0.01, -1.0), 10: (0.0, 0.0), 20: (0.02, 1.4), 30: (-0.005, -0.4)}) is True


def test_kill_criteria_thresholds_come_from_registered_protocol() -> None:
    stricter = copy.deepcopy(PROTOCOL)
    (criterion,) = [k for k in stricter["kill_criteria"] if k["id"] == "no_in_sample_effect"]
    criterion["min_clustered_t"] = 2.5
    cells = _horizon_cells({5: (-0.01, -1.0), 10: (0.0, 0.0), 20: (0.02, 1.6), 30: (-0.005, -0.4)})

    registered = verdict_for(
        KillCriteria(PROTOCOL, KILL_HYPOTHESES).evaluate("h1", cells), "no_in_sample_effect"
    )
    edited = verdict_for(
        KillCriteria(stricter, KILL_HYPOTHESES).evaluate("h1", cells), "no_in_sample_effect"
    )

    assert registered.fired is False
    assert edited.fired is True


# --- statistics -----------------------------------------------------------------------------


def test_bootstrap_ci_width_narrows_with_larger_sample() -> None:
    rng = np.random.default_rng(17)
    small = pd.Series(rng.normal(0.01, 0.05, 20))
    large = pd.Series(rng.normal(0.01, 0.05, 200))

    lo_s, hi_s = BootstrapCI.compute(small, n_bootstrap=2_000)
    lo_l, hi_l = BootstrapCI.compute(large, n_bootstrap=2_000)

    assert lo_s < small.mean() < hi_s
    assert hi_l - lo_l < hi_s - lo_s


def test_walk_forward_splitter_produces_correct_segment_count() -> None:
    events = monthly_events(date(2023, 1, 1), 24)

    segments = WalkForwardSplitter(holdout_months=0).split(
        events, in_sample_months=18, oos_months=6, embargo_days=0
    )

    assert len(segments) == 1
    assert len(segments[0].in_sample) == 18 * 3
    assert len(segments[0].oos) == 6 * 3


def test_walk_forward_splitter_respects_embargo() -> None:
    first = date(2023, 1, 1)
    events = event_frame(
        [("SRPT", first + timedelta(days=d)) for d in range(0, 730, 2)], "corroborated_at"
    )

    (segment,) = WalkForwardSplitter(holdout_months=0).split(
        events, in_sample_months=18, oos_months=6, embargo_days=30
    )

    boundary = date(2024, 7, 1)
    for part in (segment.in_sample, segment.oos):
        gaps = [abs((d - boundary).days) for d in part["corroborated_at"]]
        assert min(gaps) >= 30
    assert (
        max(segment.in_sample["corroborated_at"]) < boundary <= min(segment.oos["corroborated_at"])
    )


def test_deflated_sharpe_is_lower_than_sharpe_for_multiple_trials() -> None:
    assert DeflatedSharpe.compute(sharpe_ratio=1.5, n_obs=100, n_trials=32) < 1.5
    # A per-observation Sharpe of 1.5 over 100 observations is certain at any trial count
    # (both probabilities round to 1.0); 0.15 shows the deflation.
    one = DeflatedSharpe.compute(sharpe_ratio=0.15, n_obs=100, n_trials=1)
    many = DeflatedSharpe.compute(sharpe_ratio=0.15, n_obs=100, n_trials=32)
    assert many < one
    assert abs(1.5 - one) < abs(1.5 - many)


def test_holdout_raises_error_before_promotion() -> None:
    guard = HoldoutGuard(PROTOCOL)
    unpromoted = evaluation_result(t_stat=1.2)
    events = monthly_events(date(2023, 1, 1), 24)

    assert guard.is_sealed(unpromoted) is True
    with pytest.raises(HoldoutSealedError):
        guard.run_holdout(unpromoted, events)


# --- a full run -----------------------------------------------------------------------------


def test_evaluation_result_includes_variant_field(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("N_BOOTSTRAP", "200")
    config_dir, registry = registered_config(tmp_path)
    prices, events, _ = run_fixture()
    protocol = evaluation_protocol(config_dir, registry, prices)

    entity_only = protocol.run(
        "h1", events, "entity-only", holding_period_days=[20], known_at_delay_days=[1]
    )
    full = protocol.run("h1", events, "full", holding_period_days=[20], known_at_delay_days=[1])

    assert entity_only.variant == "entity-only"
    assert full.variant == "full"
    assert entity_only.is_primary_cell is True
    assert full.is_primary_cell is False


def test_report_lists_cost_components_per_trade(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("N_BOOTSTRAP", "200")
    config_dir, registry = registered_config(tmp_path)
    r_m = market_returns(len(SESSIONS))
    corroborated = date(2023, 6, 1)
    i0 = SESSIONS.index(CALENDAR.next_trading_day(corroborated + timedelta(days=1)))
    prices = Prices(
        {
            "XBI": price_frame(SESSIONS, closes_from(r_m)),
            "WIDE": bouncing_before(
                price_frame(SESSIONS, closes_from(r_m)), i0, bid=9.50, ask=10.50
            ),
            "TIGHT": bouncing_before(
                price_frame(SESSIONS, closes_from(r_m)), i0, bid=9.995, ask=10.005
            ),
            "EURUSD=X": price_frame(SESSIONS, np.full(len(SESSIONS), 1.25)),
        }
    )
    events = event_frame(
        [("WIDE", corroborated), ("TIGHT", corroborated), ("TIGHT", date(2024, 6, 3))],
        "corroborated_at",
    )
    model = CostModel(FLAT_COSTS, spread_estimator=SpreadEstimator(prices))

    result = evaluation_protocol(config_dir, registry, prices, model).run(
        "h1", events, "entity-only", holding_period_days=[20], known_at_delay_days=[1]
    )

    assert [t.ticker for t in result.trades] == ["WIDE", "TIGHT"]
    for trade in result.trades:
        assert set(trade.costs) == {"commission", "spread", "tob", "fx_fee", "borrow_fee"}
    wide, tight = result.trades
    assert wide.costs["spread"] / (wide.shares * wide.entry_price_usd) > 10 * (
        tight.costs["spread"] / (tight.shares * tight.entry_price_usd)
    )
    assert result.to_report()["trades"][0]["costs"] == wide.costs


def test_net_expectancy_is_computed_net_of_costs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("N_BOOTSTRAP", "200")
    config_dir, registry = registered_config(tmp_path)
    prices, events, entry = run_fixture()

    result = evaluation_protocol(config_dir, registry, prices).run(
        "h1", events, "entity-only", holding_period_days=[20], known_at_delay_days=[1]
    )

    # 10,000 EUR at 0.8 EUR per USD is 12,500 USD: 1,250 shares at 10 USD.
    shares, notional_usd = 1_250, 12_500.0
    gross_eur = 0.10 * notional_usd * 0.8
    cost_usd = (
        2 * max(1.00, 0.005 * shares)
        + 2 * notional_usd * 0.0050
        + 2 * notional_usd * 0.0035
        + 2 * notional_usd * 0.0003
    )
    assert result.n_events == 1
    assert result.n_holdout_events == 1
    assert result.trades[0].entry_date == entry
    assert result.mean_abnormal_return == pytest.approx(0.10, abs=1e-9)
    assert result.net_expectancy_eur == pytest.approx(gross_eur - cost_usd * 0.8)

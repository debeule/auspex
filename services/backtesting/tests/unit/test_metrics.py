from datetime import date

import pytest

from auspex_backtesting.backtest.runner import BacktestReport, BacktestResult, WindowReturn
from auspex_backtesting.metrics.calculator import MetricsCalculator, MetricsReport, RunParameters


def _make_params(window_days: int = 5) -> RunParameters:
    return RunParameters(
        window_days=window_days,
        source_types=("biorxiv",),
        prompt_version="v1",
        prefilter_version="v1",
        extraction_model="gpt-4o",
    )


def _make_report(returns: list[float], window: int = 5) -> BacktestReport:
    results = tuple(
        BacktestResult(
            event_id=f"e{i}",
            ticker="BEAM",
            raw_object_key=f"raw/e{i}.json",
            entry_date=date(2023, 1, 9 + i),
            window_returns=(WindowReturn(days=window, pct=r),),
        )
        for i, r in enumerate(returns)
    )
    return BacktestReport(results=results)


def test_metrics_against_known_synthetic_series():
    # returns [0.10, -0.10, 0.30]: mean=0.10, std=0.20, hit_rate=2/3 — hand-verified
    report = _make_report([0.10, -0.10, 0.30])
    metrics = MetricsCalculator().compute(report, _make_params(), window_days=5)
    assert metrics.mean_return.n == 3
    assert metrics.mean_return.value == pytest.approx(0.10)
    assert metrics.std_return.value == pytest.approx(0.20)
    assert metrics.hit_rate.n == 3
    assert metrics.hit_rate.value == pytest.approx(2 / 3)


def test_zero_signal_run_metrics_are_defined():
    metrics = MetricsCalculator().compute(BacktestReport(results=()), _make_params(), window_days=5)
    assert isinstance(metrics, MetricsReport)
    assert metrics.mean_return.n == 0
    assert metrics.mean_return.value is None
    assert metrics.hit_rate.value is None


def test_single_observation_risk_stats_handled():
    report = _make_report([0.05])
    metrics = MetricsCalculator().compute(report, _make_params(), window_days=5)
    assert metrics.mean_return.value == pytest.approx(0.05)
    assert metrics.std_return.value is None
    assert metrics.std_return.n == 1


def test_sample_size_reported_alongside_every_metric():
    report = _make_report([0.10, -0.10, 0.30])
    metrics = MetricsCalculator().compute(report, _make_params(), window_days=5)
    assert metrics.hit_rate.n == 3
    assert metrics.mean_return.n == 3
    assert metrics.std_return.n == 3


def test_run_parameters_stored_with_results():
    params = RunParameters(
        window_days=5,
        source_types=("biorxiv", "clinicaltrials"),
        prompt_version="v2",
        prefilter_version="v1",
        extraction_model="gpt-4o",
    )
    metrics = MetricsCalculator().compute(_make_report([0.05]), params, window_days=5)
    assert metrics.run_parameters == params
    assert metrics.run_parameters.prompt_version == "v2"

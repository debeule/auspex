from datetime import UTC, date, datetime

import pandas as pd
import pytest

from auspex_backtesting.backtest.runner import (
    BacktestEvent,
    BacktestReport,
    BacktestResult,
    BacktestRunner,
    WindowReturn,
)
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


def _beam_prices() -> pd.DataFrame:
    dates = ["2023-01-09", "2023-01-10", "2023-01-11", "2023-01-12", "2023-01-13"]
    idx = pd.DatetimeIndex(dates, tz="UTC", name="date")
    closes = [15.0, 15.5, 16.0, 14.5, 17.0]
    return pd.DataFrame({"open": closes, "close": closes}, index=idx)


def _corr_event(
    event_id: str,
    source_type: str,
    directionality: str = "positive",
    published_date: datetime = datetime(2023, 1, 9, 10, tzinfo=UTC),
) -> BacktestEvent:
    return BacktestEvent(
        event_id=event_id,
        ticker="BEAM",
        published_date=published_date,
        raw_object_key=f"raw/{source_type}/{event_id}.json",
        gene_target="BCL11A",
        source_type=source_type,
        directionality=directionality,
        confidence_score=0.8,
    )


def test_metrics_output_includes_variant_field():
    metrics = MetricsCalculator().compute(_make_report([0.05]), _make_params(), window_days=5)
    assert metrics.variant in ("entity-only", "full")


def test_entity_only_and_full_variants_reported_side_by_side():
    report = BacktestRunner(windows=(1,)).run(
        [_corr_event("e1", "pubmed"), _corr_event("e2", "clinicaltrials")],
        {"BEAM": _beam_prices()},
    )
    entity_m, full_m = MetricsCalculator().compute_both_variants(report, _make_params(), window_days=1)
    assert entity_m.variant == "entity-only"
    assert full_m.variant == "full"


def test_entity_only_metrics_independent_of_directionality():
    # e1 positive, e2 negative: directions disagree, so the full variant weights the event at 0
    report = BacktestRunner(windows=(1,)).run(
        [_corr_event("e1", "pubmed", "positive"), _corr_event("e2", "clinicaltrials", "negative")],
        {"BEAM": _beam_prices()},
    )
    entity_m, full_m = MetricsCalculator().compute_both_variants(report, _make_params(), window_days=1)
    assert entity_m.mean_return.value is not None
    assert entity_m.mean_return.n == 1
    assert full_m.mean_return.value is None
    assert full_m.mean_return.n == 0


def test_member_signal_predating_its_corroboration_is_not_counted():
    # a on day 0, b on day 60: one event entering after b; a's own return must not count
    sessions = pd.bdate_range("2023-01-03", "2023-04-28", tz="UTC", name="date")
    prices = pd.DataFrame({"open": 10.0, "close": 10.0}, index=sessions)
    prices.loc[pd.Timestamp("2023-01-12", tz="UTC"), "close"] = 30.0  # a's 2-day exit
    prices.loc[pd.Timestamp("2023-03-13", tz="UTC"), "close"] = 11.0  # the event's 2-day exit
    report = BacktestRunner(windows=(2,)).run(
        [
            _corr_event("a", "pubmed", published_date=datetime(2023, 1, 9, tzinfo=UTC)),
            _corr_event("b", "clinicaltrials", published_date=datetime(2023, 3, 9, tzinfo=UTC)),
        ],
        {"BEAM": prices},
    )

    entity_m, full_m = MetricsCalculator().compute_both_variants(report, _make_params(), window_days=2)

    assert entity_m.mean_return.n == 1
    assert entity_m.mean_return.value == pytest.approx(0.1)
    assert full_m.mean_return.n == 1
    assert full_m.mean_return.value == pytest.approx(0.1)


def test_variant_metrics_are_empty_when_no_signal_carries_a_gene_target():
    report = BacktestRunner(windows=(1,)).run(
        [BacktestEvent(
            event_id="e1",
            ticker="BEAM",
            published_date=datetime(2023, 1, 9, 10, tzinfo=UTC),
            raw_object_key="raw/e1.json",
        )],
        {"BEAM": _beam_prices()},
    )
    entity_m, full_m = MetricsCalculator().compute_both_variants(report, _make_params(), window_days=1)
    assert entity_m.mean_return.n == 0
    assert full_m.mean_return.n == 0


def test_corroboration_event_without_a_return_is_left_out_of_the_sample():
    # prices end before the 20-day exit, so the event has no 20-day return
    report = BacktestRunner(windows=(20,)).run(
        [_corr_event("e1", "pubmed"), _corr_event("e2", "clinicaltrials")],
        {"BEAM": _beam_prices()},
    )
    entity_m, full_m = MetricsCalculator().compute_both_variants(report, _make_params(), window_days=20)
    assert entity_m.mean_return.n == 0
    assert full_m.mean_return.n == 0


def test_metrics_report_carries_the_survivorship_summary_per_variant() -> None:
    from auspex_backtesting.backtest.runner import CorroborationGroup, VariantReport

    def group(window: WindowReturn, weight: float = 1.0) -> CorroborationGroup:
        return CorroborationGroup(
            gene_target="DMD", ticker="BEAM", source_types=frozenset({"a", "b"}), weight=weight,
            participant_event_ids=("x",), corroborated_at=datetime(2024, 3, 4, tzinfo=UTC),
            entry_date=date(2024, 3, 5), window_returns=(window,),
        )

    kept = WindowReturn(days=5, pct=0.02)
    dropped = WindowReturn(days=5, pct=None, excluded=True, exit_reason="acquired")
    backtest = BacktestReport(
        results=(BacktestResult("e", "BEAM", "raw/e.json", date(2024, 3, 5), (dropped,)),),
        entity_only=VariantReport("entity-only", (group(kept), group(dropped))),
        full=VariantReport("full", (group(kept), group(dropped, weight=0.0))),
    )
    calc = MetricsCalculator()

    entity, full = calc.compute_both_variants(backtest, _make_params(), 5)
    single = calc.compute(backtest, _make_params(), 5)

    assert entity.survivorship is not None and entity.survivorship.excluded == 1
    assert full.survivorship is not None and full.survivorship.excluded == 0
    assert single.survivorship is not None
    assert single.survivorship.excluded_by_reason == {"acquired": 1}
    assert entity.mean_return.n == 1

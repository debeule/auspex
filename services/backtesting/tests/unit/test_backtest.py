from datetime import date

import pandas as pd

from auspex_backtesting.backtest.runner import BacktestEvent, BacktestReport, BacktestRunner


def _prices(closes: dict[str, float]) -> pd.DataFrame:
    dates = sorted(closes.keys())
    idx = pd.DatetimeIndex(dates, tz="UTC", name="date")
    return pd.DataFrame({"close": [closes[d] for d in dates]}, index=idx)


def _event(
    event_id: str = "e1",
    ticker: str = "BEAM",
    entry_date: date = date(2023, 1, 9),
    raw_object_key: str = "raw/biorxiv/ext-001/20240615T120000Z-abcdef12.json",
) -> BacktestEvent:
    return BacktestEvent(
        event_id=event_id,
        ticker=ticker,
        entry_date=entry_date,
        raw_object_key=raw_object_key,
    )


_BEAM_PRICES = _prices({
    "2023-01-09": 15.0,
    "2023-01-10": 15.5,
    "2023-01-11": 16.0,
    "2023-01-12": 14.5,
    "2023-01-13": 17.0,
})


def test_backtest_runs_with_sockets_disabled():
    report = BacktestRunner().run([_event()], {"BEAM": _BEAM_PRICES})
    assert isinstance(report, BacktestReport)
    assert len(report.results) == 1


def test_identical_inputs_produce_identical_output():
    runner = BacktestRunner(windows=(5, 20))
    events = [_event()]
    price_data = {"BEAM": _BEAM_PRICES}
    assert runner.run(events, price_data) == runner.run(events, price_data)


def test_no_corroborated_signals_produces_empty_report_not_crash():
    report = BacktestRunner().run([], {})
    assert isinstance(report, BacktestReport)
    assert report.results == ()


def test_reextraction_from_archive_resolves_the_correct_snapshot():
    key = "raw/biorxiv/ext-001/20240615T120000Z-abcdef12.json"
    report = BacktestRunner().run([_event(raw_object_key=key)], {"BEAM": _BEAM_PRICES})
    assert report.results[0].raw_object_key == key


def test_multiple_extractions_of_one_document_count_once():
    events = [
        _event(event_id="e1", raw_object_key="raw/first-extraction.json"),
        _event(event_id="e1", raw_object_key="raw/second-extraction.json"),
    ]
    report = BacktestRunner().run(events, {"BEAM": _BEAM_PRICES})
    assert len(report.results) == 1
    assert report.results[0].event_id == "e1"


def _corr_event(
    event_id: str,
    gene_target: str,
    source_type: str,
    directionality: str = "positive",
    confidence_score: float = 0.8,
) -> BacktestEvent:
    return BacktestEvent(
        event_id=event_id,
        ticker="BEAM",
        entry_date=date(2023, 1, 9),
        raw_object_key=f"raw/{source_type}/{event_id}.json",
        gene_target=gene_target,
        source_type=source_type,
        directionality=directionality,
        confidence_score=confidence_score,
    )


def test_entity_only_variant_ignores_directionality_and_confidence():
    runner = BacktestRunner()
    prices = {"BEAM": _BEAM_PRICES}
    e1 = _corr_event("e1", "BCL11A", "pubmed", directionality="positive")
    e2 = _corr_event("e2", "BCL11A", "clinicaltrials", directionality="negative")
    e2_flipped = _corr_event("e2", "BCL11A", "clinicaltrials", directionality="positive")

    report_a = runner.run([e1, e2], prices)
    report_b = runner.run([e1, e2_flipped], prices)

    assert report_a.entity_only is not None
    assert report_b.entity_only is not None
    assert report_a.entity_only.groups == report_b.entity_only.groups


def test_full_variant_uses_directionality_weighting():
    runner = BacktestRunner()
    prices = {"BEAM": _BEAM_PRICES}
    e1 = _corr_event("e1", "BCL11A", "pubmed", directionality="positive", confidence_score=0.8)
    e2_agree = _corr_event("e2", "BCL11A", "clinicaltrials", directionality="positive", confidence_score=0.6)
    e2_disagree = _corr_event("e2", "BCL11A", "clinicaltrials", directionality="negative", confidence_score=0.6)

    report_agree = runner.run([e1, e2_agree], prices)
    report_disagree = runner.run([e1, e2_disagree], prices)

    assert report_agree.full is not None
    assert report_disagree.full is not None
    assert report_agree.full.groups[0].weight != report_disagree.full.groups[0].weight


def test_both_variants_reported_side_by_side():
    runner = BacktestRunner()
    prices = {"BEAM": _BEAM_PRICES}
    e1 = _corr_event("e1", "BCL11A", "pubmed")
    e2 = _corr_event("e2", "BCL11A", "clinicaltrials")

    report = runner.run([e1, e2], prices)

    assert report.entity_only is not None
    assert report.full is not None
    assert report.entity_only.variant == "entity-only"
    assert report.full.variant == "full"

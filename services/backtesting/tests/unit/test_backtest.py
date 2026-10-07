from datetime import UTC, date, datetime

import pandas as pd
import pytest

from auspex_backtesting.backtest.runner import BacktestEvent, BacktestReport, BacktestRunner
from auspex_backtesting.market_sim.calendar import MarketCalendar


def _prices(closes: dict[str, float]) -> pd.DataFrame:
    dates = sorted(closes.keys())
    idx = pd.DatetimeIndex(dates, tz="UTC", name="date")
    values = [closes[d] for d in dates]
    return pd.DataFrame({"open": values, "close": values}, index=idx)


def _session_prices(start: date, end: date, opens: float = 10.0, closes: float = 10.0) -> pd.DataFrame:
    """Flat open and close on every NYSE session in `[start, end]`."""
    sessions = MarketCalendar().sessions_between(start, end)
    idx = pd.DatetimeIndex([pd.Timestamp(d) for d in sessions], tz="UTC", name="date")
    return pd.DataFrame({"open": opens, "close": closes}, index=idx)


def _dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso).replace(tzinfo=UTC)


_MORNING = datetime(2023, 1, 9, 10, tzinfo=UTC)  # 05:00 ET, before the open


def _event(
    event_id: str = "e1",
    ticker: str = "BEAM",
    published_date: datetime = _MORNING,
    raw_object_key: str = "raw/biorxiv/ext-001/20240615T120000Z-abcdef12.json",
) -> BacktestEvent:
    return BacktestEvent(
        event_id=event_id,
        ticker=ticker,
        published_date=published_date,
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


def test_after_close_8k_enters_at_the_next_sessions_open():
    # 2023-01-11 21:30 UTC is 16:30 ET, after the close
    prices = _prices({"2023-01-11": 16.0, "2023-01-12": 20.0, "2023-01-13": 22.0})
    prices.loc[pd.Timestamp("2023-01-12", tz="UTC"), "open"] = 18.0
    signal = _event(published_date=_dt("2023-01-11T21:30:00"))

    result = BacktestRunner(windows=(1,)).run([signal], {"BEAM": prices}).results[0]

    assert result.entry_date == date(2023, 1, 12)
    # entry at the 01-12 open (18.0), exit at the 01-13 close (22.0)
    assert result.window_returns[0].pct == pytest.approx(22.0 / 18.0 - 1)


def test_holding_window_counts_calendar_days_not_price_rows():
    prices = _session_prices(date(2023, 1, 3), date(2023, 3, 31))
    prices.loc[pd.Timestamp("2023-02-02", tz="UTC"), "close"] = 12.0  # entry + 20 calendar days
    prices.loc[pd.Timestamp("2023-02-13", tz="UTC"), "close"] = 99.0  # the 20th row after entry
    signal = _event(published_date=_dt("2023-01-13T13:00:00"))  # Friday, before the open

    result = BacktestRunner(windows=(20,)).run([signal], {"BEAM": prices}).results[0]

    assert result.entry_date == date(2023, 1, 13)
    assert result.window_returns[0].pct == pytest.approx(0.2)


def test_holding_window_ending_on_a_closed_day_exits_at_the_next_session():
    prices = _session_prices(date(2023, 1, 3), date(2023, 3, 31))
    prices.loc[pd.Timestamp("2023-01-17", tz="UTC"), "close"] = 11.0  # Tuesday after MLK Day
    signal = _event(published_date=_dt("2023-01-12T13:00:00"))  # entry Thu 12th, +4 = Mon 16th

    result = BacktestRunner(windows=(4,)).run([signal], {"BEAM": prices}).results[0]

    assert result.window_returns[0].pct == pytest.approx(0.1)


def test_window_return_is_none_when_prices_end_before_the_exit_session():
    prices = _session_prices(date(2023, 1, 3), date(2023, 1, 20))
    signal = _event(published_date=_dt("2023-01-09T13:00:00"))

    result = BacktestRunner(windows=(5, 20)).run([signal], {"BEAM": prices}).results[0]

    assert result.window_returns[0].pct == pytest.approx(0.0)
    assert result.window_returns[1].pct is None


def _corr_event(
    event_id: str,
    gene_target: str,
    source_type: str,
    directionality: str = "positive",
    confidence_score: float = 0.8,
    published_date: datetime = _MORNING,
    ticker: str = "BEAM",
) -> BacktestEvent:
    return BacktestEvent(
        event_id=event_id,
        ticker=ticker,
        published_date=published_date,
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


def test_corroboration_event_enters_after_its_latest_participant():
    prices = {"BEAM": _session_prices(date(2023, 1, 3), date(2023, 6, 30))}
    signal_a = _corr_event("a", "DMD", "pubmed", published_date=_dt("2023-01-09T00:00:00"))
    signal_b = _corr_event("b", "DMD", "clinicaltrials", published_date=_dt("2023-03-10T00:00:00"))

    report = BacktestRunner(windows=(5,)).run([signal_a, signal_b], prices)

    assert report.entity_only is not None
    (event,) = report.entity_only.groups
    assert event.corroborated_at == _dt("2023-03-10T00:00:00")
    assert event.entry_date == date(2023, 3, 13)  # date-only Friday: known after close, enters Monday
    assert event.participant_event_ids == ("a", "b")


def test_signals_more_than_90_days_apart_do_not_corroborate():
    prices = {"BEAM": _session_prices(date(2023, 1, 3), date(2023, 6, 30))}
    signal_a = _corr_event("a", "DMD", "pubmed", published_date=_dt("2023-01-09T00:00:00"))
    signal_b = _corr_event("b", "DMD", "clinicaltrials", published_date=_dt("2023-04-10T00:00:00"))

    report = BacktestRunner(windows=(5,)).run([signal_a, signal_b], prices)

    assert report.entity_only is not None
    assert report.entity_only.groups == ()


def test_signal_joining_an_existing_corroboration_does_not_add_an_event():
    prices = {"BEAM": _session_prices(date(2023, 1, 3), date(2023, 6, 30))}
    signals = [
        _corr_event("a", "DMD", "pubmed", published_date=_dt("2023-01-09T00:00:00")),
        _corr_event("b", "DMD", "clinicaltrials", published_date=_dt("2023-02-09T00:00:00")),
        _corr_event("c", "DMD", "patents", published_date=_dt("2023-03-09T00:00:00")),
    ]

    report = BacktestRunner(windows=(5,)).run(signals, prices)

    assert report.entity_only is not None
    (event,) = report.entity_only.groups
    assert event.participant_event_ids == ("a", "b")


def test_disjoint_later_corroboration_on_the_same_target_is_a_new_event():
    prices = {"BEAM": _session_prices(date(2023, 1, 3), date(2023, 12, 29))}
    signals = [
        _corr_event("a", "DMD", "pubmed", published_date=_dt("2023-01-09T00:00:00")),
        _corr_event("b", "DMD", "clinicaltrials", published_date=_dt("2023-02-09T00:00:00")),
        _corr_event("c", "DMD", "pubmed", published_date=_dt("2023-08-09T00:00:00")),
        _corr_event("d", "DMD", "patents", published_date=_dt("2023-08-21T00:00:00")),
    ]

    report = BacktestRunner(windows=(5,)).run(signals, prices)

    assert report.entity_only is not None
    assert [g.participant_event_ids for g in report.entity_only.groups] == [("a", "b"), ("c", "d")]


def test_corroboration_events_are_per_ticker():
    prices = {
        "BEAM": _session_prices(date(2023, 1, 3), date(2023, 6, 30)),
        "SRPT": _session_prices(date(2023, 1, 3), date(2023, 6, 30)),
    }
    signals = [
        _corr_event("a", "DMD", "pubmed", ticker="SRPT"),
        _corr_event("b", "DMD", "clinicaltrials", ticker="BEAM"),
    ]

    report = BacktestRunner(windows=(5,)).run(signals, prices)

    assert report.entity_only is not None
    assert report.entity_only.groups == ()


def test_corroboration_event_return_runs_from_its_own_entry_not_the_earliest_member():
    prices = _session_prices(date(2023, 1, 3), date(2023, 6, 30))
    prices.loc[pd.Timestamp("2023-01-17", tz="UTC"), "close"] = 50.0  # inside member a's window only
    prices.loc[pd.Timestamp("2023-03-13", tz="UTC"), "open"] = 20.0
    prices.loc[pd.Timestamp("2023-03-20", tz="UTC"), "close"] = 21.0
    signals = [
        _corr_event("a", "DMD", "pubmed", published_date=_dt("2023-01-09T00:00:00")),
        _corr_event("b", "DMD", "clinicaltrials", published_date=_dt("2023-03-10T00:00:00")),
    ]

    report = BacktestRunner(windows=(7,)).run(signals, {"BEAM": prices})

    assert report.entity_only is not None
    (event,) = report.entity_only.groups
    assert event.window_returns[0].pct == pytest.approx(0.05)


def test_window_return_is_none_when_the_entry_session_has_no_price():
    prices = _session_prices(date(2023, 1, 3), date(2023, 3, 31)).drop(pd.Timestamp("2023-01-09", tz="UTC"))
    signal = _event(published_date=_dt("2023-01-09T13:00:00"))

    result = BacktestRunner(windows=(5,)).run([signal], {"BEAM": prices}).results[0]

    assert result.window_returns[0].pct is None


def test_window_return_is_none_for_a_ticker_without_price_data():
    result = BacktestRunner(windows=(5,)).run([_event(ticker="GONE")], {"BEAM": _BEAM_PRICES}).results[0]

    assert result.window_returns[0].pct is None


def test_signals_exactly_90_days_apart_corroborate():
    prices = {"BEAM": _session_prices(date(2023, 1, 3), date(2023, 6, 30))}
    signal_a = _corr_event("a", "DMD", "pubmed", published_date=_dt("2023-01-09T00:00:00"))
    signal_b = _corr_event("b", "DMD", "clinicaltrials", published_date=_dt("2023-04-09T00:00:00"))

    report = BacktestRunner(windows=(5,)).run([signal_a, signal_b], prices)

    assert report.entity_only is not None
    (event,) = report.entity_only.groups
    assert event.participant_event_ids == ("a", "b")


def test_two_signals_from_one_source_type_do_not_corroborate():
    prices = {"BEAM": _session_prices(date(2023, 1, 3), date(2023, 6, 30))}
    signals = [
        _corr_event("a", "DMD", "pubmed", published_date=_dt("2023-01-09T00:00:00")),
        _corr_event("b", "DMD", "pubmed", published_date=_dt("2023-01-20T00:00:00")),
    ]

    report = BacktestRunner(windows=(5,)).run(signals, prices)

    assert report.entity_only is not None
    assert report.entity_only.groups == ()


def test_full_weight_ignores_signals_published_after_the_event():
    prices = {"BEAM": _session_prices(date(2023, 1, 3), date(2023, 6, 30))}
    signals = [
        _corr_event("a", "DMD", "pubmed", confidence_score=0.8, published_date=_dt("2023-01-09T00:00:00")),
        _corr_event("b", "DMD", "clinicaltrials", confidence_score=0.6, published_date=_dt("2023-02-09T00:00:00")),
        _corr_event(
            "c", "DMD", "patents", directionality="negative", confidence_score=0.1,
            published_date=_dt("2023-03-09T00:00:00"),
        ),
    ]

    report = BacktestRunner(windows=(5,)).run(signals, prices)

    assert report.full is not None
    (event,) = report.full.groups
    assert event.weight == pytest.approx(0.7)

from datetime import date, timedelta

import pytest

from auspex_strategy.runtime import BacktestReplayRunner, PassThroughRiskManager
from auspex_strategy.testing import InMemoryObjectStore
from auspex_strategy.trace import (
    DecisionTracer,
    TraceIncompleteError,
    TraceMode,
    TraceStore,
    TraceValidator,
)

from .runtime_fakes import broker, flat_bars, long_on_trigger, ohlcv, slot, utc
from .test_decision_trace import _ApproveAll, _documents, _record, _valid_trace

_SNAPSHOTS = {
    "SRPT": ohlcv(flat_bars(date(2026, 1, 1), date(2026, 3, 31), 100.0)),
    "EURUSD=X": ohlcv(flat_bars(date(2026, 1, 1), date(2026, 3, 31), 1.25)),
}


def test_trace_store_round_trips_and_filters_by_as_of() -> None:
    store = TraceStore(InMemoryObjectStore())
    early = _valid_trace()
    late = _valid_trace(as_of=early.as_of + timedelta(days=3))
    store.append(early)
    store.append(late)

    assert list(store.read("paper_long", TraceMode.BACKTEST)) == [early, late]
    assert list(store.read("paper_long", TraceMode.BACKTEST, since=late.as_of)) == [late]
    assert list(store.read("paper_long", TraceMode.PAPER)) == []


def test_trace_store_refuses_an_incomplete_trace() -> None:
    objects = InMemoryObjectStore()

    with pytest.raises(TraceIncompleteError):
        TraceStore(objects).append(_valid_trace(risk_checks=()))

    assert objects.keys() == []


def test_backtest_replay_with_fills_traces_every_intent() -> None:
    records = [_record(f"GENE{i}", utc(2026, 3, 2 + i, 14, 0)) for i in range(3)]
    store = TraceStore(InMemoryObjectStore())
    runner = BacktestReplayRunner(
        [slot("paper_long", "paper", long_on_trigger()),
         slot("research_only", "research", long_on_trigger())],
        broker=broker(InMemoryObjectStore(), _SNAPSHOTS),
        risk=_ApproveAll(),
        tracer=DecisionTracer(store.append, _documents(records), mode=TraceMode.BACKTEST),
    )

    result = runner.run(records)

    traces = list(store.read("paper_long", TraceMode.BACKTEST))
    assert [t.intent_id for t in traces] == [i.intent_id for i in result.intents["paper_long"]]
    for trace in traces:
        TraceValidator.validate(trace)
        assert len(trace.documents) == 2
    assert len(result.books["paper_long"].snapshot().open_positions) == 3
    assert list(store.read("research_only", TraceMode.BACKTEST)) == []


def test_intent_on_an_event_without_archived_documents_cannot_be_traced() -> None:
    records = [_record("SMN1")]
    runner = BacktestReplayRunner(
        [slot("paper_long", "paper", long_on_trigger())],
        broker=None,
        risk=_ApproveAll(),
        tracer=DecisionTracer(TraceStore(InMemoryObjectStore()).append, {},
                              mode=TraceMode.BACKTEST),
    )

    with pytest.raises(TraceIncompleteError) as raised:
        runner.run(records)

    assert "documents[0].raw_object_key" in raised.value.missing_fields


def test_pass_through_risk_decisions_cannot_be_traced() -> None:
    records = [_record("SMN1")]
    runner = BacktestReplayRunner(
        [slot("paper_long", "paper", long_on_trigger())],
        broker=None,
        risk=PassThroughRiskManager(position_eur=1_000.0),
        tracer=DecisionTracer(TraceStore(InMemoryObjectStore()).append, _documents(records),
                              mode=TraceMode.BACKTEST),
    )

    with pytest.raises(TraceIncompleteError) as raised:
        runner.run(records)

    assert raised.value.missing_fields == ["risk_checks", "shares_proposed"]

import json
import time
from datetime import date
from pathlib import Path

import pytest

from auspex_strategy.errors import PriceLookAheadError
from auspex_strategy.models import InputSource, StopLossPct
from auspex_strategy.registry import RegistryEntry
from auspex_strategy.runtime import (
    BacktestAsOfContext,
    BacktestReplayRunner,
    BookMode,
    CorroboratedSignal,
    InputHealthMonitor,
    LatencyTracer,
    OffsetCheckpoint,
    PassThroughRiskManager,
    SourceMessage,
    StrategySlot,
    StreamingRuntime,
    VirtualBook,
    known_at_delay_days,
)
from auspex_strategy.strategies.h1_structural_convergence import StructuralConvergenceStrategy
from auspex_strategy.testing import FakeInputHealthClient, InMemoryObjectStore

from .runtime_fakes import (
    FixedClock,
    broker,
    flat_bars,
    long_on_trigger,
    ohlcv,
    record,
    signal,
    slot,
    utc,
)

_REPO_ROOT = Path(__file__).resolve().parents[4]
_SNAPSHOTS = {
    "SRPT": ohlcv(flat_bars(date(2026, 1, 1), date(2026, 3, 31), 100.0)),
    "EURUSD=X": ohlcv(flat_bars(date(2026, 1, 1), date(2026, 3, 31), 1.25)),
}
_RISK = PassThroughRiskManager(position_eur=10_000.0)
_CORROBORATED_AT = utc(2026, 3, 5, 14, 0)


def _streaming(slots, objects, snapshots=_SNAPSHOTS, clock=None, **kwargs):
    return StreamingRuntime(
        slots,
        broker=broker(objects, snapshots),
        risk=_RISK,
        ticker_for=lambda entity_key: "SRPT",
        clock=clock or FixedClock(utc(2026, 3, 10, 22, 0)),
        timeout_seconds=kwargs.pop("timeout_seconds", 5.0),
        **kwargs,
    )


def test_decide_past_the_timeout_counts_as_a_failure() -> None:
    def slow(self, context, trigger):
        time.sleep(1.0)
        return long_on_trigger()(self, context, trigger)

    objects = InMemoryObjectStore()
    runtime = _streaming(
        [slot("slow", "paper", slow), slot("fast", "paper", long_on_trigger())],
        objects,
        timeout_seconds=0.05,
    )

    produced = runtime.process(signal("SMN1", _CORROBORATED_AT))

    assert runtime.failure_counts == {"slow": 1, "fast": 0}
    assert list(produced) == ["fast"]


def test_intent_on_a_ticker_outside_the_allowed_set_counts_as_a_failure() -> None:
    objects = InMemoryObjectStore()
    runtime = _streaming(
        [slot("off_list", "paper", long_on_trigger("XYZ")), slot("on_list", "paper", long_on_trigger())],
        objects,
        ticker_allowed=lambda ticker: ticker == "SRPT",
    )

    produced = runtime.process(signal("SMN1", _CORROBORATED_AT))

    assert runtime.failure_counts == {"off_list": 1, "on_list": 0}
    assert list(produced) == ["on_list"]
    assert VirtualBook(objects, "off_list", BookMode.PAPER).snapshot().is_empty()


def test_live_order_waits_for_its_entry_bar() -> None:
    objects = InMemoryObjectStore()
    snapshots = {
        "SRPT": ohlcv(flat_bars(date(2026, 3, 1), date(2026, 3, 6), 100.0)),
        "EURUSD=X": ohlcv(flat_bars(date(2026, 3, 1), date(2026, 3, 31), 1.25)),
    }
    clock = FixedClock(utc(2026, 3, 6, 15, 0))
    runtime = _streaming([slot("live", "paper", long_on_trigger())], objects, snapshots, clock)

    runtime.process(signal("SMN1", _CORROBORATED_AT))

    book = VirtualBook(objects, "live", BookMode.PAPER).snapshot()
    assert [o.entry_date for o in book.pending_orders] == [date(2026, 3, 9)]
    assert book.open_positions == []

    snapshots["SRPT"] = ohlcv(flat_bars(date(2026, 3, 1), date(2026, 3, 9), 100.0))
    clock.now = utc(2026, 3, 9, 22, 0)
    runtime.process(signal("SMN2", utc(2026, 3, 9, 14, 0)))

    book = VirtualBook(objects, "live", BookMode.PAPER).snapshot()
    assert [p.entry_date for p in book.open_positions] == [date(2026, 3, 9)]
    assert [o.entry_date for o in book.pending_orders] == [date(2026, 3, 11)]


def test_stop_loss_exits_at_the_market_simulation_stop_fill() -> None:
    snapshots = {
        "SRPT": ohlcv({
            "2026-03-09": (100.0, 101.0, 98.0, 99.0),
            "2026-03-10": (99.0, 100.0, 95.0, 96.0),
            "2026-03-11": (85.0, 88.0, 80.0, 82.0),
        }),
        "EURUSD=X": ohlcv(flat_bars(date(2026, 3, 1), date(2026, 3, 31), 1.25)),
    }
    objects = InMemoryObjectStore()
    paper = broker(objects, snapshots)
    runner = BacktestReplayRunner(
        [slot("stopped", "paper", long_on_trigger(holding_rule=StopLossPct(10.0)))],
        broker=paper,
        risk=_RISK,
    )

    result = runner.run([record("SMN1", _CORROBORATED_AT)])
    paper.settle(through=date(2026, 3, 11))

    [trade] = result.books["stopped"].closed_trades()
    # The stop at 90 is gapped through on 03-11, so it fills at that open.
    assert (trade.exit_date, trade.exit_price, trade.exit_reason) == (
        date(2026, 3, 11), 85.0, "stop_loss"
    )


def test_replay_of_ten_events_fills_a_virtual_book() -> None:
    class OneLongPerEvent(StructuralConvergenceStrategy):
        def decide(self, context, trigger):
            return long_on_trigger()(self, context, trigger)

    entry = RegistryEntry(
        name=OneLongPerEvent.name,
        module=__name__,
        class_name="OneLongPerEvent",
        version=OneLongPerEvent.version,
        hypothesis_id=OneLongPerEvent.hypothesis_id,
        status="paper",
        parameters_file=None,
        strategy_class=OneLongPerEvent,
    )
    records = [record(f"GENE{i}", utc(2026, 2, 2 + i, 14, 0)) for i in range(10)]
    runner = BacktestReplayRunner(
        [StrategySlot(entry=entry, known_at_delay_days=1)],
        broker=broker(InMemoryObjectStore(), _SNAPSHOTS),
        risk=_RISK,
    )

    result = runner.run(records)

    assert result.events_processed == 10
    assert len(result.intents["structural_convergence"]) == 10
    assert result.failure_counts == {"structural_convergence": 0}
    assert len(result.books["structural_convergence"].snapshot().open_positions) == 10


def test_corroborated_signal_reads_core_hub_wire_format() -> None:
    # The shape core-hub's CorroboratedWireFormatTest pins: snake_case, ISO-8601 instants.
    payload = json.dumps({
        "entity_key": "SMN1:Gene",
        "participants_hash": "abc",
        "participant_event_ids": ["e1", "e2"],
        "distinct_source_count": 2,
        "corroborated_at": "2026-03-05T14:00:00Z",
        "first_detected_at": "2026-03-05T20:00:00.250Z",
    }).encode()

    assert CorroboratedSignal.from_json(payload) == CorroboratedSignal(
        entity_key="SMN1:Gene",
        participants_hash="abc",
        participant_event_ids=("e1", "e2"),
        distinct_source_count=2,
        corroborated_at=utc(2026, 3, 5, 14, 0),
        first_detected_at=utc(2026, 3, 5, 20, 0, 0, 250_000),
    )


def test_corroborated_signal_refuses_camel_case_and_epoch_timestamps() -> None:
    camel = b'{"entityKey": "SMN1:Gene", "participantsHash": "abc", "participantEventIds": [],' \
        b' "distinctSourceCount": 2, "corroboratedAt": 1772719200.0, "firstDetectedAt": 1772719200.0}'
    epoch = json.dumps({
        "entity_key": "SMN1:Gene", "participants_hash": "abc", "participant_event_ids": [],
        "distinct_source_count": 2, "corroborated_at": 1772719200.0,
        "first_detected_at": 1772719200.0,
    }).encode()

    with pytest.raises(KeyError):
        CorroboratedSignal.from_json(camel)
    with pytest.raises(TypeError):
        CorroboratedSignal.from_json(epoch)


def test_consume_checkpoints_each_event_and_skips_unreadable_ones() -> None:
    objects = InMemoryObjectStore()
    runtime = _streaming([slot("live", "paper", long_on_trigger())], objects)
    good = json.dumps({
        "entity_key": "SMN1", "participants_hash": "h", "participant_event_ids": ["a", "b"],
        "distinct_source_count": 2, "corroborated_at": "2026-03-05T14:00:00Z",
        "first_detected_at": "2026-03-05T14:00:00Z",
    }).encode()
    messages = [
        SourceMessage("auspex.signals.corroborated", 3, 41, good),
        SourceMessage("auspex.signals.corroborated", 3, 42, b"{not json"),
    ]

    class Source:
        def poll(self, timeout_seconds):
            return messages.pop(0) if messages else None

    checkpoint = OffsetCheckpoint(objects, "auspex.signals.corroborated")

    assert runtime.consume(Source(), checkpoint)
    assert checkpoint.load() == {3: 42}
    assert runtime.consume(Source(), checkpoint)
    assert checkpoint.load() == {3: 43}
    assert runtime.rejected_events == 1
    assert not runtime.consume(Source(), checkpoint)
    assert objects.keys().count(
        "strategy/checkpoints/auspex-strategy-runtime/auspex.signals.corroborated.json"
    ) == 1


def test_recovered_input_ends_the_pause() -> None:
    objects = InMemoryObjectStore()
    needs_model = slot(
        "needs_model", "paper", long_on_trigger(), inputs=frozenset({InputSource.EXTRACTION_MODEL})
    )
    client = FakeInputHealthClient({InputSource.EXTRACTION_MODEL: False})
    clock = FixedClock(utc(2026, 3, 10, 22, 0))
    monitor = InputHealthMonitor(client, objects, clock=clock)

    monitor.poll([needs_model])
    monitor.poll([needs_model])
    client.health[InputSource.EXTRACTION_MODEL] = True
    clock.now = utc(2026, 3, 10, 23, 0)
    monitor.poll([needs_model])

    assert not monitor.is_paused("needs_model")
    events = [json.loads(line) for line in objects.lines("strategy/health/pauses.jsonl")]
    assert [(e["event"], e["at"]) for e in events] == [
        ("pause_start", "2026-03-10T22:00:00+00:00"),
        ("pause_end", "2026-03-10T23:00:00+00:00"),
    ]


def test_latency_median_is_checked_against_the_known_at_delay() -> None:
    objects = InMemoryObjectStore()
    tracer = LatencyTracer(objects)
    runtime = _streaming(
        [slot("traced", "paper", long_on_trigger())],
        objects,
        clock=FixedClock(utc(2026, 3, 7, 14, 0)),
        latency=tracer,
    )

    runtime.process(signal("SMN1", _CORROBORATED_AT))

    assert tracer.median_exceeds(1)
    assert not tracer.median_exceeds(2)


def test_backtest_context_refuses_a_close_that_is_not_final() -> None:
    context = BacktestAsOfContext(
        utc(2026, 3, 6, 14, 0),
        [record("SMN1", _CORROBORATED_AT)],
        known_at_delay_days=1,
        price_close=lambda ticker, d: 100.0,
    )

    assert context.price("SRPT", date(2026, 3, 5)) == 100.0
    with pytest.raises(PriceLookAheadError):
        context.price("SRPT", date(2026, 3, 6))


def test_backtest_context_hides_records_not_yet_known() -> None:
    known = record("SMN1", utc(2026, 3, 4, 14, 0))
    unknown = record("SMN2", utc(2026, 3, 5, 15, 0))
    context = BacktestAsOfContext(
        utc(2026, 3, 6, 14, 0), [known, unknown], known_at_delay_days=1
    )

    assert context.corroborations() == [known]


def test_known_at_delay_comes_from_the_registered_hypothesis() -> None:
    hypotheses = _REPO_ROOT / "config" / "hypotheses"

    assert known_at_delay_days("h1", hypotheses) == 1
    assert known_at_delay_days("h7", hypotheses) == 1


def test_streaming_flags_overlap_between_paper_strategies() -> None:
    objects = InMemoryObjectStore()
    runtime = _streaming(
        [slot("first", "paper", long_on_trigger()), slot("second", "paper", long_on_trigger())],
        objects,
    )

    produced = runtime.process(signal("SMN1", _CORROBORATED_AT))

    [first], [second] = produced["first"], produced["second"]
    assert first.rationale.overlap_with == (second.intent_id,)
    assert second.rationale.overlap_with == (first.intent_id,)


def test_settle_never_fills_an_order_before_its_entry_session() -> None:
    objects = InMemoryObjectStore()
    paper = broker(objects, _SNAPSHOTS)
    runner = BacktestReplayRunner(
        [slot("early", "research", long_on_trigger())], broker=paper, risk=_RISK
    )
    [intent] = runner.run([record("SMN1", _CORROBORATED_AT)]).intents["early"]
    paper.submit(_RISK.review([intent])[0], BookMode.PAPER)

    paper.settle(through=date(2026, 3, 6))

    book = paper.book("early", BookMode.PAPER).snapshot()
    assert [o.entry_date for o in book.pending_orders] == [date(2026, 3, 9)]
    assert book.open_positions == []


def test_runtime_writes_to_the_bucket_the_stack_creates() -> None:
    from auspex_backtesting.stack_bootstrap import stack_buckets

    from auspex_strategy.runtime import STRATEGY_BUCKET

    assert STRATEGY_BUCKET in stack_buckets("auspex-raw")

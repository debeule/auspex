import json
from datetime import date

from auspex_backtesting.market_sim import CostModel, CurrencyConverter, FillModel

from auspex_strategy.models import FixedDays, InputSource
from auspex_strategy.runtime import (
    BacktestReplayRunner,
    BookMode,
    HealthEndpoint,
    InputHealthMonitor,
    LatencyTracer,
    PassThroughRiskManager,
    StreamingRuntime,
    VirtualBook,
)
from auspex_strategy.testing import FakeInputHealthClient, InMemoryObjectStore

from .runtime_fakes import (
    COST_PARAMS,
    FixedClock,
    broker,
    crash,
    flat_bars,
    long_on_trigger,
    ohlcv,
    price_store,
    record,
    signal,
    slot,
    utc,
)

_SNAPSHOTS = {
    "SRPT": ohlcv(flat_bars(date(2026, 1, 1), date(2026, 3, 31), 100.0)),
    "EURUSD=X": ohlcv(flat_bars(date(2026, 1, 1), date(2026, 3, 31), 1.25)),
}
_RISK = PassThroughRiskManager(position_eur=10_000.0)
# Thursday 2026-03-05 14:00 UTC; with a one-day known-at delay the intent is as of Friday and
# enters at Monday's open.
_CORROBORATED_AT = utc(2026, 3, 5, 14, 0)
_AFTER_ENTRY = FixedClock(utc(2026, 3, 10, 22, 0))


def _streaming(slots, objects, **kwargs):
    return StreamingRuntime(
        slots,
        broker=broker(objects, _SNAPSHOTS),
        risk=_RISK,
        ticker_for=lambda entity_key: "SRPT",
        clock=kwargs.pop("clock", _AFTER_ENTRY),
        timeout_seconds=5.0,
        **kwargs,
    )


def test_research_strategy_does_not_run_in_streaming_mode() -> None:
    objects = InMemoryObjectStore()
    calls: list[str] = []

    def decide(self, context, trigger):
        calls.append(self.name)
        return long_on_trigger()(self, context, trigger)

    runtime = _streaming([slot("research_only", "research", decide)], objects)

    produced = runtime.process(signal("SMN1", _CORROBORATED_AT))

    assert calls == []
    assert produced == {}
    assert VirtualBook(objects, "research_only", BookMode.PAPER).snapshot().is_empty()
    assert objects.keys() == []


def test_paper_strategy_virtual_book_records_fill() -> None:
    objects = InMemoryObjectStore()
    runner = BacktestReplayRunner(
        [slot("paper_long", "paper", long_on_trigger())],
        broker=broker(objects, _SNAPSHOTS),
        risk=_RISK,
    )

    result = runner.run([record("SMN1", _CORROBORATED_AT)])

    assert [i.ticker for i in result.intents["paper_long"]] == ["SRPT"]
    snapshot = result.books["paper_long"].snapshot()
    assert len(snapshot.open_positions) == 1
    position = snapshot.open_positions[0]
    assert position.ticker == "SRPT"
    assert position.entry_date == date(2026, 3, 9)
    assert position.entry_price == 100.0
    # 10,000 EUR at 1.25 USD per EUR is 12,500 USD, 125 shares at 100 USD.
    assert position.shares == 125
    assert snapshot.closed_trades == []


def test_one_strategy_crash_does_not_affect_others() -> None:
    objects = InMemoryObjectStore()
    runtime = _streaming(
        [slot("crashes", "paper", crash), slot("healthy", "paper", long_on_trigger())],
        objects,
    )

    produced = runtime.process(signal("SMN1", _CORROBORATED_AT))

    assert runtime.failure_counts == {"crashes": 1, "healthy": 0}
    assert "crashes" not in produced
    assert [i.ticker for i in produced["healthy"]] == ["SRPT"]
    healthy_book = VirtualBook(objects, "healthy", BookMode.PAPER).snapshot()
    assert [p.ticker for p in healthy_book.open_positions] == ["SRPT"]
    assert VirtualBook(objects, "crashes", BookMode.PAPER).snapshot().is_empty()


def test_stale_input_source_pauses_strategy() -> None:
    objects = InMemoryObjectStore()
    model_slot = slot(
        "needs_model",
        "paper",
        long_on_trigger(),
        inputs=frozenset({InputSource.CORROBORATION_STORE, InputSource.EXTRACTION_MODEL}),
    )
    store_slot = slot("store_only", "paper", long_on_trigger())
    client = FakeInputHealthClient({
        InputSource.CORROBORATION_STORE: True,
        InputSource.PRICE_DATA: True,
        InputSource.GRAPH_QUERY: True,
        InputSource.EXTRACTION_MODEL: False,
    })
    monitor = InputHealthMonitor(client, objects, clock=_AFTER_ENTRY)
    runtime = _streaming([model_slot, store_slot], objects, health=monitor)

    monitor.poll([model_slot, store_slot])
    produced = runtime.process(signal("SMN1", _CORROBORATED_AT))

    assert "needs_model" not in produced
    assert [i.ticker for i in produced["store_only"]] == ["SRPT"]
    assert runtime.failure_counts["needs_model"] == 0
    pauses = [json.loads(line) for line in objects.lines("strategy/health/pauses.jsonl")]
    assert pauses == [{
        "strategy": "needs_model",
        "event": "pause_start",
        "at": "2026-03-10T22:00:00+00:00",
        "unhealthy_inputs": ["extraction_model"],
    }]


def test_intents_from_same_event_by_two_strategies_are_flagged_as_overlap() -> None:
    objects = InMemoryObjectStore()
    runner = BacktestReplayRunner(
        [slot("first", "paper", long_on_trigger()), slot("second", "paper", long_on_trigger())],
        broker=broker(objects, _SNAPSHOTS),
        risk=_RISK,
    )

    result = runner.run([record("SMN1", _CORROBORATED_AT)])

    [first] = result.intents["first"]
    [second] = result.intents["second"]
    assert first.rationale.overlap_with == (second.intent_id,)
    assert second.rationale.overlap_with == (first.intent_id,)


def test_latency_trace_records_corroboration_to_intent_gap() -> None:
    objects = InMemoryObjectStore()
    intent_time = FixedClock(utc(2026, 3, 6, 14, 0, 30))
    runtime = _streaming(
        [slot("traced", "paper", long_on_trigger())],
        objects,
        clock=intent_time,
        latency=LatencyTracer(objects),
    )

    produced = runtime.process(
        signal("SMN1", _CORROBORATED_AT, first_detected_at=utc(2026, 3, 5, 20, 0))
    )

    [entry] = [json.loads(line) for line in objects.lines("strategy/latency/distribution.jsonl")]
    assert entry == {
        "strategy": "traced",
        "strategy_version": "1.0",
        "intent_id": str(produced["traced"][0].intent_id),
        "corroborated_at": "2026-03-05T14:00:00+00:00",
        "ingested_at": "2026-03-05T20:00:00+00:00",
        "intent_time": "2026-03-06T14:00:30+00:00",
        "latency_corroboration_to_intent_ms": 86_430_000,
    }


def test_virtual_book_pnl_matches_market_simulation() -> None:
    entry_day, exit_day = date(2026, 3, 9), date(2026, 3, 16)
    snapshots = {
        "SRPT": ohlcv({
            "2026-03-06": (90.0, 90.0, 90.0, 90.0),
            "2026-03-09": (100.0, 104.0, 99.0, 103.0),
            "2026-03-10": (103.0, 106.0, 101.0, 105.0),
            "2026-03-16": (110.0, 113.0, 108.0, 112.0),
        }),
        "EURUSD=X": ohlcv(flat_bars(date(2026, 3, 1), date(2026, 3, 31), 1.25)),
    }
    objects = InMemoryObjectStore()
    paper = broker(objects, snapshots)
    runner = BacktestReplayRunner(
        [slot("pnl", "paper", long_on_trigger(holding_rule=FixedDays(7)))],
        broker=paper,
        risk=_RISK,
    )

    result = runner.run([record("SMN1", _CORROBORATED_AT)])
    paper.settle(through=exit_day)

    [trade] = result.books["pnl"].closed_trades()
    prices = price_store(snapshots)
    fills = FillModel(prices)
    entry_price = fills.entry_price("SRPT", entry_day)
    exit_price = fills.exit_price("SRPT", entry_day, 7)
    shares = 125
    costs = CostModel(COST_PARAMS).round_trip_cost_usd(
        "SRPT", entry_price, shares, is_short=False, holding_calendar_days=7, entry_date=entry_day
    )
    expected_usd = (exit_price - entry_price) * shares - costs
    assert (trade.entry_price, trade.exit_price, trade.shares) == (100.0, 112.0, 125)
    assert trade.exit_date == exit_day
    assert trade.costs_usd == costs
    assert trade.pnl_usd == expected_usd
    assert trade.pnl_eur == CurrencyConverter(prices).usd_to_eur(expected_usd, exit_day)


def test_backtest_replay_is_deterministic() -> None:
    records = [record(f"GENE{i}", utc(2026, 1, 5 + i, 14, 0)) for i in range(5)]

    def replay():
        runner = BacktestReplayRunner(
            [slot("deterministic", "research", long_on_trigger())],
            broker=broker(InMemoryObjectStore(), _SNAPSHOTS),
            risk=_RISK,
        )
        return runner.run(records).intents["deterministic"]

    first, second = replay(), replay()

    assert len(first) == len(second) == 5
    assert all(a.matches(b) and a.rationale == b.rationale for a, b in zip(first, second))
    assert [a.intent_id for a in first] == [b.intent_id for b in second]


def test_health_reports_per_strategy_failure_counts_and_pause_state() -> None:
    objects = InMemoryObjectStore()
    crashing = slot("crashes", "paper", crash)
    paused = slot(
        "paused", "paper", long_on_trigger(), inputs=frozenset({InputSource.EXTRACTION_MODEL})
    )
    client = FakeInputHealthClient({source: True for source in InputSource})
    client.health[InputSource.EXTRACTION_MODEL] = False
    monitor = InputHealthMonitor(client, objects, clock=_AFTER_ENTRY)
    runtime = _streaming([crashing, paused], objects, health=monitor)
    monitor.poll([crashing, paused])
    runtime.process(signal("SMN1", _CORROBORATED_AT))
    endpoint = HealthEndpoint(runtime)

    status, content_type, body = endpoint.handle("/health")
    assert status == 200
    assert content_type == "application/json"
    assert json.loads(body) == {
        "status": "ok",
        "strategies": {
            "crashes": {"failures": 1, "paused": False},
            "paused": {"failures": 0, "paused": True},
        },
    }

    status, _, metrics = endpoint.handle("/metrics")
    text = metrics.decode()
    assert status == 200
    assert 'auspex_strategy_decide_failures_total{strategy="crashes"} 1.0' in text
    assert 'auspex_strategy_decide_failures_total{strategy="paused"} 0.0' in text
    assert 'auspex_strategy_paused{strategy="crashes"} 0.0' in text
    assert 'auspex_strategy_paused{strategy="paused"} 1.0' in text

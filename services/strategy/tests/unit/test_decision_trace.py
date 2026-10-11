import dataclasses
from datetime import timedelta
from uuid import UUID

import pytest

from auspex_strategy.models import CorroborationRecord, Direction, TradeIntent
from auspex_strategy.runtime import BacktestReplayRunner
from auspex_strategy.runtime.risk import (
    ApprovalStatus,
    RiskCheckRecord,
    RiskDecision,
)
from auspex_strategy.testing import InMemoryObjectStore
from auspex_strategy.trace import (
    DecisionTracer,
    DocumentRecord,
    TraceIncompleteError,
    TraceMode,
    TraceRecord,
    TraceReplayer,
    TraceStore,
    TraceValidator,
)

from .runtime_fakes import FixedClock, long_on_trigger, slot, utc

_CORROBORATED_AT = utc(2026, 3, 5, 14, 0)
_KILL_SWITCH_OFF = RiskCheckRecord("KILL_SWITCH", {"global": False, "strategy": False}, True)


def _record(entity_key: str, corroborated_at=_CORROBORATED_AT) -> CorroborationRecord:
    return CorroborationRecord(
        entity_key=entity_key,
        ticker="SRPT",
        corroborated_at=corroborated_at,
        source_count=2,
        source_types=frozenset({"biorxiv", "clinicaltrials"}),
        participant_event_ids=(f"{entity_key}-a", f"{entity_key}-b"),
        participants_hash=f"hash-{entity_key}",
    )


def _documents(records: list[CorroborationRecord]) -> dict[str, DocumentRecord]:
    documents = {}
    for i, r in enumerate(records):
        for j, event_id in enumerate(r.participant_event_ids):
            documents[event_id] = DocumentRecord(
                event_id=event_id,
                raw_object_key=f"raw/biorxiv/{event_id}/20260305T120000Z-0000{i}{j}.json",
                extraction_id=UUID(int=100 * i + j + 1),
                extraction_model="llama3.1:8b-instruct-q8_0",
                prompt_version="v1",
                prefilter_version="v1",
                extracted_at=None,
            )
    return documents


def _approve(intent: TradeIntent) -> RiskDecision:
    return RiskDecision(
        intent=intent,
        status=ApprovalStatus.APPROVED,
        checks=(_KILL_SWITCH_OFF, RiskCheckRecord("GROSS_EXPOSURE", {"gross": 0.1}, True)),
        capital_eur=1_000.0,
        shares_proposed=12,
        kelly_inputs={"p_estimate": 0.55, "b_estimate": 1.2, "shrinkage_factor": 0.5},
    )


class _ScriptedRisk:
    """Decides by strategy name, so one replay yields approved, rejected and paused intents."""

    def review(self, intents: list[TradeIntent]) -> list[RiskDecision]:
        decisions = []
        for intent in intents:
            if intent.strategy_name == "rejected":
                decisions.append(RiskDecision(
                    intent=intent,
                    status=ApprovalStatus.REJECTED,
                    checks=(
                        _KILL_SWITCH_OFF,
                        RiskCheckRecord("GROSS_EXPOSURE", {"gross": 1.02, "limit": 1.0}, False),
                    ),
                    rejection_reason="gross exposure 1.02 above the 1.00 limit",
                ))
            elif intent.strategy_name == "paused":
                decisions.append(RiskDecision(
                    intent=intent,
                    status=ApprovalStatus.PAUSED,
                    checks=(RiskCheckRecord("KILL_SWITCH", {"strategy": True}, False),),
                    pause_reason="per-strategy kill switch: drawdown",
                ))
            else:
                decisions.append(_approve(intent))
        return decisions


class _ApproveAll:
    def review(self, intents: list[TradeIntent]) -> list[RiskDecision]:
        return [_approve(i) for i in intents]


class _NetOpposing:
    """Nets every later intent into the first one on the same ticker in the opposite direction."""

    def review(self, intents: list[TradeIntent]) -> list[RiskDecision]:
        survivor = intents[0]
        decisions = [dataclasses.replace(_approve(survivor), is_netted=True)]
        for intent in intents[1:]:
            assert intent.ticker == survivor.ticker and intent.direction != survivor.direction
            decisions.append(dataclasses.replace(
                _approve(intent), is_netted=True, netted_into_intent_id=survivor.intent_id,
            ))
        return decisions


def _short_on_trigger():
    long = long_on_trigger()

    def decide(self, context, trigger):
        [intent] = long(self, context, trigger)
        intent.direction = Direction.SHORT
        return [intent]

    return decide


def _valid_trace(mode: TraceMode = TraceMode.BACKTEST, **overrides) -> TraceRecord:
    record = _record("SMN1")
    [document_a, document_b] = _documents([record]).values()
    trace = TraceRecord(
        trace_id=UUID(int=1),
        mode=mode,
        documents=(document_a, document_b),
        entity_key=record.entity_key,
        participants_hash=record.participants_hash,
        corroborated_at=record.corroborated_at,
        source_types=("biorxiv", "clinicaltrials"),
        strategy_name="paper_long",
        strategy_version="1.0",
        strategy_code_hash="ab" * 32,
        hypothesis_id="h1",
        as_of=record.corroborated_at + timedelta(days=1),
        intent_id=UUID(int=2),
        rationale={"entity_key": "SMN1", "directionality": "positive"},
        risk_checks=(_KILL_SWITCH_OFF,),
        final_approval=ApprovalStatus.APPROVED,
        rejection_reason=None,
        rejection_check_name=None,
        is_paused=False,
        pause_reason=None,
        overlaps_with_intent_ids=(),
        is_netted=False,
        netted_into_intent_id=None,
        kelly_inputs={"p_estimate": 0.55, "b_estimate": 1.2, "shrinkage_factor": 0.5},
        shares_proposed=12,
        approved_at=utc(2026, 3, 6, 14, 0),
        approved_by="auto",
        order_id=None,
        order_submitted_at=None,
        fill_price_usd=None,
        fill_time=None,
        entry_date=None,
        exit_date=None,
        exit_reason=None,
        gross_pnl_usd=None,
        total_costs_usd=None,
        net_pnl_eur=None,
        estimated_tax_eur=None,
    )
    return dataclasses.replace(trace, **overrides)


def test_every_intent_gets_a_trace_record() -> None:
    records = [_record("SMN1")]
    store = TraceStore(InMemoryObjectStore())
    tracer = DecisionTracer(
        store.append, _documents(records), mode=TraceMode.BACKTEST,
        clock=FixedClock(utc(2026, 3, 6, 9, 0)),
    )
    runner = BacktestReplayRunner(
        [slot(name, "paper", long_on_trigger()) for name in ("approved", "rejected", "paused")],
        broker=None,
        risk=_ScriptedRisk(),
        tracer=tracer,
    )

    runner.run(records)

    traces = [
        trace
        for name in ("approved", "rejected", "paused")
        for trace in store.read(name, TraceMode.BACKTEST)
    ]
    assert len(traces) == 3
    assert [t.final_approval for t in traces] == [
        ApprovalStatus.APPROVED, ApprovalStatus.REJECTED, ApprovalStatus.PAUSED,
    ]
    for trace in traces:
        TraceValidator.validate(trace)


def test_trace_with_missing_extraction_id_fails_validation() -> None:
    trace = _valid_trace()
    broken = dataclasses.replace(trace.documents[0], extraction_id=None)
    trace = dataclasses.replace(trace, documents=(broken, *trace.documents[1:]))

    with pytest.raises(TraceIncompleteError) as raised:
        TraceValidator.validate(trace)

    assert raised.value.missing_fields == ["documents[0].extraction_id"]
    assert "extraction_id" in str(raised.value)


def test_trace_with_approved_approval_but_null_shares_fails_validation() -> None:
    trace = _valid_trace(final_approval=ApprovalStatus.APPROVED, shares_proposed=None)

    with pytest.raises(TraceIncompleteError) as raised:
        TraceValidator.validate(trace)

    assert raised.value.missing_fields == ["shares_proposed"]


def test_replaying_backtest_produces_identical_non_time_fields() -> None:
    records = [_record(f"GENE{i}", _CORROBORATED_AT + timedelta(days=i)) for i in range(5)]
    strategy = slot("paper_long", "paper", long_on_trigger())

    first = TraceReplayer(_documents(records), clock=FixedClock(utc(2026, 3, 20, 9, 0))).replay(
        records, strategy, _ApproveAll(),
    )
    second = TraceReplayer(_documents(records), clock=FixedClock(utc(2026, 9, 1, 9, 0))).replay(
        records, strategy, _ApproveAll(),
    )

    assert len(first) == len(second) == 5
    time_fields = {"trace_id", "approved_at", "fill_time"}
    for original, replayed in zip(first, second, strict=True):
        TraceValidator.validate(original)
        assert original.trace_id != replayed.trace_id
        for field in dataclasses.fields(TraceRecord):
            if field.name not in time_fields:
                assert getattr(original, field.name) == getattr(replayed, field.name), field.name


def test_rejected_intent_trace_has_rejection_reason() -> None:
    records = [_record("SMN1")]
    [trace] = TraceReplayer(_documents(records)).replay(
        records, slot("rejected", "paper", long_on_trigger()), _ScriptedRisk(),
    )

    assert trace.final_approval is ApprovalStatus.REJECTED
    assert trace.rejection_reason
    assert trace.rejection_check_name == "GROSS_EXPOSURE"
    TraceValidator.validate(trace)


def test_netted_intent_trace_has_netted_into_reference() -> None:
    records = [_record("SMN1")]
    store = TraceStore(InMemoryObjectStore())
    runner = BacktestReplayRunner(
        [slot("goes_long", "paper", long_on_trigger()),
         slot("goes_short", "paper", _short_on_trigger())],
        broker=None,
        risk=_NetOpposing(),
        tracer=DecisionTracer(store.append, _documents(records), mode=TraceMode.BACKTEST),
    )

    runner.run(records)

    [long_trace] = store.read("goes_long", TraceMode.BACKTEST)
    [short_trace] = store.read("goes_short", TraceMode.BACKTEST)
    assert long_trace.is_netted and short_trace.is_netted
    assert long_trace.netted_into_intent_id is None
    assert short_trace.netted_into_intent_id == long_trace.intent_id


def test_backtest_paper_live_traces_pass_same_validator() -> None:
    for mode in (TraceMode.BACKTEST, TraceMode.PAPER, TraceMode.LIVE):
        TraceValidator.validate(_valid_trace(mode))

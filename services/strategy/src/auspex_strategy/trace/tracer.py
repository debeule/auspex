from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import fields
from datetime import UTC, datetime
from functools import cache
from typing import Any
from uuid import UUID, uuid4

from auspex_strategy.models import CorroborationRecord, IntentRationale
from auspex_strategy.registry import module_code_hash
from auspex_strategy.runtime.risk import ApprovalStatus, RiskDecision
from auspex_strategy.runtime.slots import StrategySlot
from auspex_strategy.trace.records import DocumentRecord, TraceMode, TraceRecord

TraceSink = Callable[[TraceRecord], None]


class DecisionTracer:
    """Builds one `TraceRecord` per risk decision and hands it to `sink` (usually
    `TraceStore.append`, which refuses incomplete traces).

    `documents` maps each participant `event_id` to its archived document and extraction; an
    event it does not know leaves the trace without a chain of custody, and the sink raises.
    """

    def __init__(
        self,
        sink: TraceSink,
        documents: Mapping[str, DocumentRecord],
        *,
        mode: TraceMode,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._sink = sink
        self._documents = documents
        self.mode = mode
        self._clock = clock

    def record(
        self, corroboration: CorroborationRecord, decision: RiskDecision, slot: StrategySlot
    ) -> TraceRecord:
        intent = decision.intent
        approved = decision.status is ApprovalStatus.APPROVED
        trace = TraceRecord(
            trace_id=uuid4(),
            mode=self.mode,
            documents=tuple(self._document(e) for e in corroboration.participant_event_ids),
            entity_key=corroboration.entity_key,
            participants_hash=corroboration.participants_hash,
            corroborated_at=corroboration.corroborated_at,
            source_types=tuple(sorted(corroboration.source_types)),
            strategy_name=intent.strategy_name,
            strategy_version=intent.strategy_version,
            strategy_code_hash=_code_hash(slot.entry.module) or "",
            hypothesis_id=intent.hypothesis_id,
            as_of=intent.as_of,
            intent_id=intent.intent_id,
            rationale=_rationale(intent.rationale),
            risk_checks=decision.checks,
            final_approval=decision.status,
            rejection_reason=decision.rejection_reason,
            rejection_check_name=decision.rejection_check_name,
            is_paused=decision.status is ApprovalStatus.PAUSED,
            pause_reason=decision.pause_reason,
            overlaps_with_intent_ids=intent.rationale.overlap_with,
            is_netted=decision.is_netted,
            netted_into_intent_id=decision.netted_into_intent_id,
            kelly_inputs=decision.kelly_inputs,
            shares_proposed=decision.shares_proposed,
            approved_at=self._clock() if approved else None,
            approved_by=(decision.approved_by or "auto") if approved else None,
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
        self._sink(trace)
        return trace

    def _document(self, event_id: str) -> DocumentRecord:
        known = self._documents.get(event_id)
        if known is not None:
            return known
        return DocumentRecord(event_id, None, None, None, None, None, None)


@cache
def _code_hash(module_name: str) -> str | None:
    return module_code_hash(module_name)


def _rationale(rationale: IntentRationale) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for f in fields(rationale):
        value = getattr(rationale, f.name)
        if isinstance(value, datetime):
            value = value.isoformat()
        elif isinstance(value, frozenset):
            value = sorted(value)
        elif isinstance(value, tuple):
            value = [str(v) if isinstance(v, UUID) else v for v in value]
        out[f.name] = value
    return out

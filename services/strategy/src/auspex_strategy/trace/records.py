from __future__ import annotations

import enum
from dataclasses import dataclass, fields
from datetime import date, datetime
from typing import Any
from uuid import UUID

from auspex_strategy.runtime.risk import ApprovalStatus, RiskCheckRecord


class TraceMode(enum.Enum):
    BACKTEST = "backtest"
    PAPER = "paper"
    LIVE = "live"


@dataclass(frozen=True)
class DocumentRecord:
    """One participant document of the corroboration: enough to re-fetch the raw document from
    the archive and re-run the same extraction. Fields are None when the lookup had no record
    for the event, which leaves the trace invalid."""

    event_id: str
    raw_object_key: str | None
    extraction_id: UUID | None
    extraction_model: str | None
    prompt_version: str | None
    prefilter_version: str | None
    # Not on `ResearchSignalEvent` yet (DECISIONS.md 2026-09-20).
    extracted_at: datetime | None


@dataclass(frozen=True)
class TraceRecord:
    """The full decision chain of one intent, from raw documents to P&L. Never edited: a later
    stage of the same intent is a new line in the store."""

    trace_id: UUID
    mode: TraceMode

    # Raw document and extraction chain, one entry per participant event
    documents: tuple[DocumentRecord, ...]

    # Corroboration chain; (entity_key, participants_hash) is the corroboration's key
    entity_key: str
    participants_hash: str
    corroborated_at: datetime
    source_types: tuple[str, ...]

    # Strategy chain
    strategy_name: str
    strategy_version: str
    strategy_code_hash: str
    hypothesis_id: str
    as_of: datetime
    intent_id: UUID
    rationale: dict[str, Any]

    # Risk chain, in run order; the first failure ends it
    risk_checks: tuple[RiskCheckRecord, ...]
    final_approval: ApprovalStatus
    rejection_reason: str | None
    rejection_check_name: str | None
    is_paused: bool
    pause_reason: str | None

    overlaps_with_intent_ids: tuple[UUID, ...]
    is_netted: bool
    netted_into_intent_id: UUID | None

    # Sizing and approval chain (approved intents)
    kelly_inputs: dict[str, float] | None
    shares_proposed: int | None
    approved_at: datetime | None
    approved_by: str | None

    # Execution, position and P&L chain (after the fill)
    order_id: str | None
    order_submitted_at: datetime | None
    fill_price_usd: float | None
    fill_time: datetime | None
    entry_date: date | None
    exit_date: date | None
    exit_reason: str | None
    gross_pnl_usd: float | None
    total_costs_usd: float | None
    net_pnl_eur: float | None
    estimated_tax_eur: float | None

    def to_json_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {f.name: _encode(getattr(self, f.name)) for f in fields(self)}
        out["documents"] = [
            {f.name: _encode(getattr(d, f.name)) for f in fields(d)} for d in self.documents
        ]
        out["risk_checks"] = [
            {"check_name": c.check_name, "inputs_snapshot": c.inputs_snapshot, "passed": c.passed}
            for c in self.risk_checks
        ]
        return out

    @classmethod
    def from_json_dict(cls, raw: dict[str, Any]) -> TraceRecord:
        return cls(
            trace_id=UUID(raw["trace_id"]),
            mode=TraceMode(raw["mode"]),
            documents=tuple(
                DocumentRecord(
                    event_id=d["event_id"],
                    raw_object_key=d["raw_object_key"],
                    extraction_id=_uuid(d["extraction_id"]),
                    extraction_model=d["extraction_model"],
                    prompt_version=d["prompt_version"],
                    prefilter_version=d["prefilter_version"],
                    extracted_at=_datetime(d["extracted_at"]),
                )
                for d in raw["documents"]
            ),
            entity_key=raw["entity_key"],
            participants_hash=raw["participants_hash"],
            corroborated_at=datetime.fromisoformat(raw["corroborated_at"]),
            source_types=tuple(raw["source_types"]),
            strategy_name=raw["strategy_name"],
            strategy_version=raw["strategy_version"],
            strategy_code_hash=raw["strategy_code_hash"],
            hypothesis_id=raw["hypothesis_id"],
            as_of=datetime.fromisoformat(raw["as_of"]),
            intent_id=UUID(raw["intent_id"]),
            rationale=raw["rationale"],
            risk_checks=tuple(
                RiskCheckRecord(c["check_name"], c["inputs_snapshot"], c["passed"])
                for c in raw["risk_checks"]
            ),
            final_approval=ApprovalStatus(raw["final_approval"]),
            rejection_reason=raw["rejection_reason"],
            rejection_check_name=raw["rejection_check_name"],
            is_paused=raw["is_paused"],
            pause_reason=raw["pause_reason"],
            overlaps_with_intent_ids=tuple(UUID(i) for i in raw["overlaps_with_intent_ids"]),
            is_netted=raw["is_netted"],
            netted_into_intent_id=_uuid(raw["netted_into_intent_id"]),
            kelly_inputs=raw["kelly_inputs"],
            shares_proposed=raw["shares_proposed"],
            approved_at=_datetime(raw["approved_at"]),
            approved_by=raw["approved_by"],
            order_id=raw["order_id"],
            order_submitted_at=_datetime(raw["order_submitted_at"]),
            fill_price_usd=raw["fill_price_usd"],
            fill_time=_datetime(raw["fill_time"]),
            entry_date=_date(raw["entry_date"]),
            exit_date=_date(raw["exit_date"]),
            exit_reason=raw["exit_reason"],
            gross_pnl_usd=raw["gross_pnl_usd"],
            total_costs_usd=raw["total_costs_usd"],
            net_pnl_eur=raw["net_pnl_eur"],
            estimated_tax_eur=raw["estimated_tax_eur"],
        )


def _encode(value: Any) -> Any:
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, tuple):
        return [_encode(v) for v in value]
    return value


def _uuid(value: str | None) -> UUID | None:
    return None if value is None else UUID(value)


def _datetime(value: str | None) -> datetime | None:
    return None if value is None else datetime.fromisoformat(value)


def _date(value: str | None) -> date | None:
    return None if value is None else date.fromisoformat(value)

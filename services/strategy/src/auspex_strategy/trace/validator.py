from __future__ import annotations

from typing import Any

from auspex_strategy.runtime.risk import ApprovalStatus
from auspex_strategy.trace.records import TraceRecord

_REQUIRED = (
    "entity_key",
    "participants_hash",
    "corroborated_at",
    "strategy_name",
    "strategy_version",
    "strategy_code_hash",
    "hypothesis_id",
    "as_of",
    "intent_id",
)
_REQUIRED_PER_DOCUMENT = ("event_id", "raw_object_key", "extraction_id")


class TraceIncompleteError(Exception):
    def __init__(self, missing_fields: list[str]) -> None:
        super().__init__(f"trace is missing {', '.join(missing_fields)}")
        self.missing_fields = missing_fields


class TraceValidator:
    """One rule set for backtest, paper and live traces: a trace that cannot answer "why did
    it (not) trade?" from its own fields is incomplete."""

    @staticmethod
    def validate(record: TraceRecord) -> None:
        missing = [name for name in _REQUIRED if _empty(getattr(record, name))]
        if not record.documents:
            missing.append("documents")
        for i, document in enumerate(record.documents):
            missing += [
                f"documents[{i}].{name}"
                for name in _REQUIRED_PER_DOCUMENT
                if _empty(getattr(document, name))
            ]
        # At the least the kill switch runs on every intent.
        if not record.risk_checks:
            missing.append("risk_checks")
        match record.final_approval:
            case ApprovalStatus.APPROVED if record.shares_proposed is None:
                missing.append("shares_proposed")
            case ApprovalStatus.REJECTED if _empty(record.rejection_reason):
                missing.append("rejection_reason")
            case ApprovalStatus.PAUSED if _empty(record.pause_reason):
                missing.append("pause_reason")
        if missing:
            raise TraceIncompleteError(missing)


def _empty(value: Any) -> bool:
    return value is None or value == ""

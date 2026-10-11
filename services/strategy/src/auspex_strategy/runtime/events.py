from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class CorroboratedSignal:
    """One record from `auspex.signals.corroborated` (core-hub's `CorroboratedSignalEvent`):
    snake_case JSON with ISO-8601 timestamps."""

    entity_key: str
    participants_hash: str
    participant_event_ids: tuple[str, ...]
    distinct_source_count: int
    corroborated_at: datetime
    first_detected_at: datetime

    @classmethod
    def from_json(cls, payload: bytes) -> CorroboratedSignal:
        raw: dict[str, Any] = json.loads(payload)
        return cls(
            entity_key=str(raw["entity_key"]),
            participants_hash=str(raw["participants_hash"]),
            participant_event_ids=tuple(str(e) for e in raw["participant_event_ids"]),
            distinct_source_count=int(raw["distinct_source_count"]),
            corroborated_at=_utc(raw["corroborated_at"]),
            first_detected_at=_utc(raw["first_detected_at"]),
        )


def _utc(value: Any) -> datetime:
    if not isinstance(value, str):
        raise TypeError(f"timestamp {value!r} is not an ISO-8601 string")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp {value!r} has no offset")
    return parsed.astimezone(UTC)

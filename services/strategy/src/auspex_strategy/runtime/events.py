from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class CorroboratedSignal:
    """One record from `auspex.signals.corroborated` (core-hub's `CorroboratedSignalEvent`):
    snake_case JSON with ISO-8601 timestamps. `ticker` is empty on an entity record (STR-062)."""

    entity_key: str
    ticker: str
    participants_hash: str
    participant_event_ids: tuple[str, ...]
    distinct_source_count: int
    source_types: tuple[str, ...]
    corroborated_at: datetime
    episode_opened_at: datetime
    first_detected_at: datetime

    @classmethod
    def from_json(cls, payload: bytes) -> CorroboratedSignal:
        raw: dict[str, Any] = json.loads(payload)
        return cls(
            entity_key=str(raw["entity_key"]),
            ticker=str(raw["ticker"]),
            participants_hash=str(raw["participants_hash"]),
            participant_event_ids=tuple(str(e) for e in raw["participant_event_ids"]),
            distinct_source_count=int(raw["distinct_source_count"]),
            source_types=tuple(str(t) for t in raw["source_types"]),
            corroborated_at=_utc(raw["corroborated_at"]),
            episode_opened_at=_utc(raw["episode_opened_at"]),
            first_detected_at=_utc(raw["first_detected_at"]),
        )


def _utc(value: Any) -> datetime:
    if not isinstance(value, str):
        raise TypeError(f"timestamp {value!r} is not an ISO-8601 string")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp {value!r} has no offset")
    return parsed.astimezone(UTC)

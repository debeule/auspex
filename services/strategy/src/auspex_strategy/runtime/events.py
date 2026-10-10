from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class CorroboratedSignal:
    """One record from `auspex.signals.corroborated` (core-hub's `CorroboratedSignalEvent`)."""

    entity_key: str
    participants_hash: str
    participant_event_ids: tuple[str, ...]
    distinct_source_count: int
    corroborated_at: datetime
    first_detected_at: datetime

    @classmethod
    def from_json(cls, payload: bytes) -> CorroboratedSignal:
        """Parse snake_case or camelCase keys, and ISO-8601 or epoch-second timestamps.

        core-hub publishes this topic through Spring Kafka's default `JsonSerializer`, not the
        application's snake_case mapper, so both spellings are accepted (DECISIONS.md).
        """
        raw: dict[str, Any] = json.loads(payload, parse_float=Decimal)
        return cls(
            entity_key=str(_field(raw, "entity_key")),
            participants_hash=str(_field(raw, "participants_hash")),
            participant_event_ids=tuple(str(e) for e in _field(raw, "participant_event_ids")),
            distinct_source_count=int(_field(raw, "distinct_source_count")),
            corroborated_at=_utc(_field(raw, "corroborated_at")),
            first_detected_at=_utc(_field(raw, "first_detected_at")),
        )


def _field(raw: dict[str, Any], snake: str) -> Any:
    if snake in raw:
        return raw[snake]
    head, *rest = snake.split("_")
    return raw[head + "".join(part.capitalize() for part in rest)]


def _utc(value: Any) -> datetime:
    if isinstance(value, (int, Decimal)):
        seconds = Decimal(value)
        return datetime.fromtimestamp(int(seconds), UTC).replace(
            microsecond=int((seconds % 1) * 1_000_000)
        )
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp {value!r} has no offset")
    return parsed.astimezone(UTC)

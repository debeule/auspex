from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4


class SubscriptionType(enum.Enum):
    CORROBORATION_NEW = "corroboration_new"
    CORROBORATION_SUPERSEDED = "corroboration_superseded"
    SIGNAL_NEW = "signal_new"
    PRICE_TICK = "price_tick"
    CALENDAR_TICK = "calendar_tick"


class InputSource(enum.Enum):
    CORROBORATION_STORE = "corroboration_store"
    PRICE_DATA = "price_data"
    GRAPH_QUERY = "graph_query"
    EXTRACTION_MODEL = "extraction_model"


class Direction(enum.Enum):
    LONG = "long"
    SHORT = "short"


@dataclass(frozen=True)
class FixedDays:
    days: int


@dataclass(frozen=True)
class ExitOnSignal:
    pass


@dataclass(frozen=True)
class StopLossPct:
    pct: float


HoldingRule = FixedDays | ExitOnSignal | StopLossPct


@dataclass(frozen=True)
class ExitCondition:
    condition_type: str
    parameters: dict[str, Any]

    def __hash__(self) -> int:
        return hash((self.condition_type, tuple(sorted(self.parameters.items()))))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ExitCondition):
            return NotImplemented
        return self.condition_type == other.condition_type and self.parameters == other.parameters


@dataclass(frozen=True)
class IntentRationale:
    corroboration_id: str
    entity_key: str
    as_of: datetime
    source_types: frozenset[str]
    directionality: str
    confidence_scores: tuple[float, ...]


@dataclass
class TradeIntent:
    ticker: str
    direction: Direction
    conviction: float
    holding_rule: HoldingRule
    exit_conditions: tuple[ExitCondition, ...]
    rationale: IntentRationale
    strategy_name: str
    strategy_version: str
    hypothesis_id: str
    as_of: datetime
    intent_id: UUID = field(default_factory=uuid4)

    def matches(self, other: TradeIntent) -> bool:
        """Structural equality excluding intent_id."""
        return (
            self.ticker == other.ticker
            and self.direction == other.direction
            and self.conviction == other.conviction
            and self.holding_rule == other.holding_rule
            and self.exit_conditions == other.exit_conditions
            and self.strategy_name == other.strategy_name
            and self.strategy_version == other.strategy_version
            and self.hypothesis_id == other.hypothesis_id
            and self.as_of == other.as_of
        )


@dataclass(frozen=True)
class CorroborationRecord:
    entity_key: str
    ticker: str
    corroborated_at: datetime
    source_count: int
    source_types: frozenset[str]
    participant_event_ids: tuple[str, ...]


@dataclass(frozen=True)
class SignalRecord:
    event_id: str
    entity_key: str
    source_type: str
    published_at: datetime
    directionality: str
    confidence_score: float


@dataclass(frozen=True)
class StrategyParameters:
    raw: dict[str, Any]

    def get(self, key: str, default: Any = None) -> Any:
        return self.raw.get(key, default)


@dataclass(frozen=True)
class Trigger:
    trigger_type: SubscriptionType
    payload: Any = None

    def __hash__(self) -> int:
        return hash(self.trigger_type)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Trigger):
            return NotImplemented
        return self.trigger_type == other.trigger_type

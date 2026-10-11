from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from auspex_strategy.models import TradeIntent


@dataclass(frozen=True)
class ApprovedIntent:
    intent: TradeIntent
    capital_eur: float


class ApprovalStatus(enum.Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    # The strategy is gated (kill switch, loss limit), not this intent.
    PAUSED = "paused"


@dataclass(frozen=True)
class RiskCheckRecord:
    """One check the risk layer ran on an intent. `inputs_snapshot` holds the values the check
    compared, as JSON-native types, so the decision can be reproduced from the trace alone."""

    check_name: str
    inputs_snapshot: dict[str, Any]
    passed: bool


@dataclass(frozen=True)
class RiskDecision:
    """The risk layer's verdict on one intent, with every check it ran in run order.

    A netted pair has `is_netted` on both decisions; the one absorbed into the other names the
    survivor in `netted_into_intent_id` and is not submitted.
    """

    intent: TradeIntent
    status: ApprovalStatus
    checks: tuple[RiskCheckRecord, ...]
    capital_eur: float | None = None
    shares_proposed: int | None = None
    kelly_inputs: dict[str, float] | None = None
    # "auto" unless a person confirmed the order.
    approved_by: str | None = None
    rejection_reason: str | None = None
    pause_reason: str | None = None
    is_netted: bool = False
    netted_into_intent_id: UUID | None = None

    @property
    def rejection_check_name(self) -> str | None:
        return next((c.check_name for c in self.checks if not c.passed), None)

    @property
    def submits(self) -> bool:
        return self.status is ApprovalStatus.APPROVED and self.netted_into_intent_id is None

    def as_approved(self) -> ApprovedIntent:
        if not self.submits or self.capital_eur is None:
            raise ValueError(f"intent {self.intent.intent_id} has no capital to submit")
        return ApprovedIntent(self.intent, self.capital_eur)


class RiskManager(Protocol):
    """Reviews all intents produced on one event together: one decision per intent, in order."""

    def review(self, intents: list[TradeIntent]) -> list[RiskDecision]: ...


class PassThroughRiskManager:
    """Approves every intent at one fixed capital. Stands in until sizing, exposure limits and
    kill switches exist; it applies no risk check at all, so its decisions cannot be traced."""

    def __init__(self, position_eur: float) -> None:
        self._position_eur = position_eur

    def review(self, intents: list[TradeIntent]) -> list[RiskDecision]:
        return [
            RiskDecision(
                intent, ApprovalStatus.APPROVED, checks=(), capital_eur=self._position_eur,
                approved_by="auto",
            )
            for intent in intents
        ]

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from auspex_strategy.models import TradeIntent


@dataclass(frozen=True)
class ApprovedIntent:
    intent: TradeIntent
    capital_eur: float


class RiskManager(Protocol):
    """Turns a decision's intents into the ones that may trade, each with the capital it gets."""

    def review(self, intents: list[TradeIntent]) -> list[ApprovedIntent]: ...


class PassThroughRiskManager:
    """Approves every intent at one fixed capital. Stands in until sizing, exposure limits and
    kill switches exist; it applies no risk check at all."""

    def __init__(self, position_eur: float) -> None:
        self._position_eur = position_eur

    def review(self, intents: list[TradeIntent]) -> list[ApprovedIntent]:
        return [ApprovedIntent(intent, self._position_eur) for intent in intents]

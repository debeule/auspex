from __future__ import annotations

from auspex_strategy.abc import AsOfContext, Strategy
from auspex_strategy.models import InputSource, StrategyParameters, SubscriptionType, TradeIntent, Trigger


class NegativeAsymmetryStrategy(Strategy):
    name = "negative_asymmetry"
    version = "1.0"
    hypothesis_id = "h8"
    description = "Short on negative-directionality corroboration pair; draft pending tax/borrow prerequisites"

    @property
    def subscriptions(self) -> frozenset[SubscriptionType]:
        return frozenset({SubscriptionType.CORROBORATION_NEW})

    @property
    def declared_inputs(self) -> frozenset[InputSource]:
        return frozenset({InputSource.CORROBORATION_STORE, InputSource.PRICE_DATA})

    def decide(self, context: AsOfContext, trigger: Trigger) -> list[TradeIntent]:
        return []

    @classmethod
    def parameters(cls) -> StrategyParameters:
        return StrategyParameters(raw={})

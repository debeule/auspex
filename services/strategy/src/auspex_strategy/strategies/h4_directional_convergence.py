from __future__ import annotations

from auspex_strategy.abc import AsOfContext, Strategy
from auspex_strategy.models import InputSource, StrategyParameters, SubscriptionType, TradeIntent, Trigger


class DirectionalConvergenceStrategy(Strategy):
    name = "directional_convergence"
    version = "1.0"
    hypothesis_id = "h4"
    description = "Long/short on corroboration where both participants share the same directionality"

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

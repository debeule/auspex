from __future__ import annotations

from auspex_strategy.abc import AsOfContext, Strategy
from auspex_strategy.models import InputSource, StrategyParameters, SubscriptionType, TradeIntent, Trigger


class SourceCompositionStrategy(Strategy):
    name = "source_composition"
    version = "1.0"
    hypothesis_id = "h5"
    description = "Long on corroboration; filtered by configured source_type pair"

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

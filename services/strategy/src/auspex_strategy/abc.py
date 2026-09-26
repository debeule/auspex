from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import ClassVar

from auspex_strategy.models import (
    CorroborationRecord,
    InputSource,
    SignalRecord,
    StrategyParameters,
    SubscriptionType,
    TradeIntent,
    Trigger,
)


class AsOfContext(ABC):
    @property
    @abstractmethod
    def as_of(self) -> datetime: ...

    @abstractmethod
    def corroborations(
        self,
        *,
        ticker: str | None = None,
        entity_key: str | None = None,
        min_source_count: int = 2,
    ) -> list[CorroborationRecord]: ...

    @abstractmethod
    def signals(
        self,
        *,
        entity_key: str | None = None,
        source_type: str | None = None,
    ) -> list[SignalRecord]: ...

    @abstractmethod
    def price(self, ticker: str, date: date) -> float: ...

    @abstractmethod
    def prior_corroborations(self, ticker: str, entity_key: str) -> int: ...

    @abstractmethod
    def is_trading_day(self, date: date) -> bool: ...


class Strategy(ABC):
    name: ClassVar[str]
    version: ClassVar[str]
    hypothesis_id: ClassVar[str]
    description: ClassVar[str]

    @property
    @abstractmethod
    def subscriptions(self) -> frozenset[SubscriptionType]: ...

    @property
    @abstractmethod
    def declared_inputs(self) -> frozenset[InputSource]: ...

    @abstractmethod
    def decide(self, context: AsOfContext, trigger: Trigger) -> list[TradeIntent]: ...

    @classmethod
    @abstractmethod
    def parameters(cls) -> StrategyParameters: ...

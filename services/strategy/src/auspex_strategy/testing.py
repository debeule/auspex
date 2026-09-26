from __future__ import annotations

from datetime import date, datetime, timedelta

from auspex_strategy.abc import AsOfContext
from auspex_strategy.errors import AsOfViolationError
from auspex_strategy.models import CorroborationRecord, SignalRecord


class StubAsOfContext(AsOfContext):
    """Minimal AsOfContext for unit tests. Enforces the as-of boundary."""

    def __init__(
        self,
        as_of: datetime,
        corroborations: list[CorroborationRecord] | None = None,
        signals: list[SignalRecord] | None = None,
        known_at_delay_days: int = 1,
    ) -> None:
        self._as_of = as_of
        self._corroborations = corroborations or []
        self._signals = signals or []
        self._delay = timedelta(days=known_at_delay_days)

    @property
    def as_of(self) -> datetime:
        return self._as_of

    def corroborations(
        self,
        *,
        ticker: str | None = None,
        entity_key: str | None = None,
        min_source_count: int = 2,
    ) -> list[CorroborationRecord]:
        result = []
        for r in self._corroborations:
            known_at = r.corroborated_at + self._delay
            if known_at > self._as_of:
                raise AsOfViolationError(r.corroborated_at, self._as_of, known_at)
            if ticker is not None and r.ticker != ticker:
                continue
            if entity_key is not None and r.entity_key != entity_key:
                continue
            if r.source_count < min_source_count:
                continue
            result.append(r)
        return result

    def signals(
        self,
        *,
        entity_key: str | None = None,
        source_type: str | None = None,
    ) -> list[SignalRecord]:
        return [
            s for s in self._signals
            if (entity_key is None or s.entity_key == entity_key)
            and (source_type is None or s.source_type == source_type)
        ]

    def price(self, ticker: str, date: date) -> float:
        return 0.0

    def prior_corroborations(self, ticker: str, entity_key: str) -> int:
        return 0

    def is_trading_day(self, date: date) -> bool:
        return True

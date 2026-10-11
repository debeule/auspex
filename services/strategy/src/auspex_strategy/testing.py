from __future__ import annotations

from datetime import date, datetime, timedelta

from auspex_strategy.abc import AsOfContext
from auspex_strategy.errors import AsOfViolationError
from auspex_strategy.models import CorroborationRecord, InputSource, SignalRecord
from auspex_strategy.risk.catalysts import KnownCatalyst


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


class InMemoryObjectStore:
    """`ObjectStore` held in a dict, for tests that must not reach MinIO."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def get(self, key: str) -> bytes | None:
        return self.objects.get(key)

    def put(self, key: str, data: bytes) -> None:
        self.objects[key] = data

    def keys(self) -> list[str]:
        return sorted(self.objects)

    def lines(self, key: str) -> list[str]:
        return [line for line in self.objects.get(key, b"").decode("utf-8").splitlines() if line]


class FakeInputHealthClient:
    def __init__(self, health: dict[InputSource, bool]) -> None:
        self.health = dict(health)

    def fetch(self) -> dict[InputSource, bool]:
        return dict(self.health)


class StaticCatalysts:
    """A fixed list of known catalysts, filtered the way `CatalystSource.between` promises."""

    def __init__(self, catalysts: list[KnownCatalyst]) -> None:
        self._catalysts = list(catalysts)

    def between(self, ticker: str, start: date, end: date, as_of: datetime) -> list[KnownCatalyst]:
        return [
            c for c in self._catalysts
            if c.ticker == ticker and c.known_at <= as_of
            and c.period_start <= end and c.period_end >= start
        ]

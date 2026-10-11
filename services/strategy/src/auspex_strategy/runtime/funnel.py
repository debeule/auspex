from __future__ import annotations

import json
from dataclasses import dataclass

from auspex_strategy.runtime.book import BookMode
from auspex_strategy.runtime.store import ObjectStore


@dataclass(frozen=True)
class FunnelCounts:
    """How far a strategy version's corroborations got before the book: events its `decide()`
    ran on, intents it produced, and intents the risk layer approved."""

    inputs_seen: int = 0
    intents: int = 0
    passed_risk: int = 0


class FunnelCounter:
    """Counts per strategy, version and mode, kept in MinIO at
    `strategy/funnel/<strategy>/<mode>.json` so the totals survive restarts."""

    def __init__(self, store: ObjectStore) -> None:
        self._store = store

    def record(
        self,
        strategy_name: str,
        version: str,
        mode: BookMode,
        *,
        intents: int,
        passed_risk: int,
    ) -> None:
        counts = self._load(strategy_name, mode)
        current = counts.get(version, FunnelCounts())
        counts[version] = FunnelCounts(
            inputs_seen=current.inputs_seen + 1,
            intents=current.intents + intents,
            passed_risk=current.passed_risk + passed_risk,
        )
        body = {v: c.__dict__ for v, c in sorted(counts.items())}
        self._store.put(_key(strategy_name, mode), json.dumps(body).encode("utf-8"))

    def counts(self, strategy_name: str, version: str, mode: BookMode) -> FunnelCounts:
        return self._load(strategy_name, mode).get(version, FunnelCounts())

    def versions(self, strategy_name: str, mode: BookMode) -> set[str]:
        return set(self._load(strategy_name, mode))

    def _load(self, strategy_name: str, mode: BookMode) -> dict[str, FunnelCounts]:
        data = self._store.get(_key(strategy_name, mode))
        if data is None:
            return {}
        return {v: FunnelCounts(**c) for v, c in json.loads(data).items()}


def _key(strategy_name: str, mode: BookMode) -> str:
    return f"strategy/funnel/{strategy_name}/{mode.value}.json"

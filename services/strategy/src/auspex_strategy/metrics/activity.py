from __future__ import annotations

from dataclasses import dataclass

from auspex_strategy.runtime.book import BookMode, VirtualBook
from auspex_strategy.runtime.funnel import FunnelCounter
from auspex_strategy.runtime.store import ObjectStore


@dataclass(frozen=True)
class ActivityFunnel:
    """Where one strategy version's corroborations dropped out: decided on, produced an intent,
    passed risk, filled, closed. The first three come from the runtime's counters, the last two
    from the book."""

    inputs_seen: int
    intents: int
    passed_risk: int
    filled: int
    closed: int

    @classmethod
    def compute(
        cls, store: ObjectStore, strategy_name: str, version: str, mode: BookMode
    ) -> ActivityFunnel:
        counts = FunnelCounter(store).counts(strategy_name, version, mode)
        snapshot = VirtualBook(store, strategy_name, mode).snapshot()
        still_open = sum(1 for p in snapshot.open_positions if p.strategy_version == version)
        closed = sum(1 for t in snapshot.closed_trades if t.strategy_version == version)
        return cls(
            inputs_seen=counts.inputs_seen,
            intents=counts.intents,
            passed_risk=counts.passed_risk,
            filled=still_open + closed,
            closed=closed,
        )

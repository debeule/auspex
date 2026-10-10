from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from auspex_strategy.models import TradeIntent


class OverlapDetector:
    """Marks intents from different strategies that make the same bet on the same event.

    An overlap is not a rejection: each intent's `rationale.overlap_with` lists the others, and
    the capital allocator decides whether to net or stack them.
    """

    def flag(self, intents_by_strategy: Mapping[str, list[TradeIntent]]) -> None:
        everything = [
            (name, intent) for name, intents in intents_by_strategy.items() for intent in intents
        ]
        for name, intent in everything:
            others = tuple(
                other.intent_id
                for other_name, other in everything
                if other_name != name
                and other.ticker == intent.ticker
                and other.direction == intent.direction
            )
            if others:
                intent.rationale = replace(intent.rationale, overlap_with=others)

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from auspex_backtesting.hypothesis import load_hypothesis

from auspex_strategy.models import InputSource
from auspex_strategy.registry import RegistryEntry
from auspex_strategy.runtime.book import BookMode

# Lifecycle order. `draft` and `retired` strategies never run in the runtime.
_STATUS_RANK = {"research": 1, "paper": 2, "live-confirm": 3, "live-auto": 4}
_BOOK_MODES = {
    "paper": BookMode.PAPER,
    "live-confirm": BookMode.LIVE_CONFIRM,
    "live-auto": BookMode.LIVE_AUTO,
}


@dataclass(frozen=True)
class StrategySlot:
    """A registered strategy as the runtime runs it, with the known-at delay its hypothesis
    was registered with."""

    entry: RegistryEntry
    known_at_delay_days: int

    @property
    def name(self) -> str:
        return self.entry.name

    @property
    def declared_inputs(self) -> frozenset[InputSource]:
        return self.entry.strategy_class().declared_inputs

    def at_least(self, status: str) -> bool:
        return _STATUS_RANK.get(self.entry.status, 0) >= _STATUS_RANK[status]

    @property
    def live_mode(self) -> BookMode | None:
        """The forward book this strategy's status trades into; None below `paper`."""
        return _BOOK_MODES.get(self.entry.status)


def known_at_delay_days(hypothesis_id: str, hypotheses_dir: Path) -> int:
    """The delay a strategy's hypothesis was registered with: its primary cell's, or the only
    value it lists."""
    hypothesis: dict[str, Any] = load_hypothesis(hypothesis_id, hypotheses_dir)
    primary = hypothesis.get("primary_cell") or {}
    if "known_at_delay_days" in primary:
        return int(primary["known_at_delay_days"])
    declared = hypothesis.get("known_at_delay_days")
    if isinstance(declared, int):
        return declared
    if isinstance(declared, list) and len(declared) == 1:
        return int(declared[0])
    raise ValueError(
        f"hypothesis {hypothesis_id} declares no single known_at_delay_days for the runtime"
    )

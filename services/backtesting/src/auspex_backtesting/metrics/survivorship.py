"""How much the events that could not be priced might move a result.

An event is excluded from return statistics only when its holding window is not fully covered
by prices. Excluded events are counted by how the company's listing ended, and a sensitivity
row puts them back with an assumed return over the unpriced part of the window.
"""

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Final, Literal

from auspex_backtesting.backtest.runner import WindowReturn

# Average return on a performance delisting (Shumway 1997), assumed to carry over to biotech.
# An acquisition closes near the deal price, which the last trade already reflects. A listed
# company whose window is unpriced is a data gap with no direction, so it is assumed flat.
_ASSUMED_RETURN_AFTER_LAST_PRICE: Final = {"delisted": -0.30, "deregistered": -0.30}
_MATERIAL_EXCLUDED_SHARE: Final = 0.10


@dataclass(frozen=True)
class SurvivorshipSummary:
    events: int
    excluded: int
    excluded_by_reason: dict[str, int]
    excluded_share: float
    survivorship_gap: Literal["material", "immaterial"]
    bounded_mean_return: float | None
    bounded_n: int


def survivorship_summary(returns: Iterable[WindowReturn]) -> SurvivorshipSummary:
    """Counts over one holding window's returns. A window still running (no `pct`, not
    excluded) is neither kept nor excluded."""
    windows = list(returns)
    kept = [r.pct for r in windows if not r.excluded and r.pct is not None]
    excluded = [r for r in windows if r.excluded]
    events = len(kept) + len(excluded)
    bounded = kept + [
        (1 + (r.priced_pct or 0.0))
        * (1 + _ASSUMED_RETURN_AFTER_LAST_PRICE.get(r.exit_reason or "", 0.0))
        - 1
        for r in excluded
    ]
    share = len(excluded) / events if events else 0.0
    return SurvivorshipSummary(
        events=events,
        excluded=len(excluded),
        excluded_by_reason=dict(Counter(r.exit_reason or "listed" for r in excluded)),
        excluded_share=share,
        survivorship_gap="material" if share > _MATERIAL_EXCLUDED_SHARE else "immaterial",
        bounded_mean_return=sum(bounded) / len(bounded) if bounded else None,
        bounded_n=len(bounded),
    )

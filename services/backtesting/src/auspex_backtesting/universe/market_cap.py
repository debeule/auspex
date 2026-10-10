import math
import statistics
from collections.abc import Sequence
from datetime import date

import pandas as pd

from auspex_backtesting.prices.splits import SplitHistory
from auspex_backtesting.universe.model import ShareCount


class SplitHistoryUnavailableError(Exception):
    """A market cap needs a split history that is unknown for the price snapshot's basis."""


def market_cap_usd(
    shares: Sequence[ShareCount],
    close: float,
    as_of: date,
    splits: SplitHistory,
    adjusted_through: date | None,
) -> float | None:
    """Shares outstanding as last reported before `as_of`, times `close`; None when no count
    was public yet.

    Only counts filed strictly before `as_of` are used: filing dates carry no time of day, so a
    count filed on `as_of` may not have been public at the open. `close` is split-adjusted to
    the share basis of `adjusted_through`, the day its snapshot was first downloaded, so the
    count is restated through every split after the date it refers to, up to that day. Raises
    `SplitHistoryUnavailableError` when the history does not vouch for every split up to it.
    """
    known = [s for s in shares if s.filed < as_of]
    if not known:
        return None
    if (
        adjusted_through is None
        or splits.covered_through is None
        or splits.covered_through < adjusted_through
    ):
        raise SplitHistoryUnavailableError(
            f"split history covered through {splits.covered_through}, price basis "
            f"{adjusted_through}"
        )
    latest = max(known, key=lambda s: (s.filed, s.end))
    factor = math.prod(
        float(r)
        for ts, r in splits.ratios.items()
        if latest.end < pd.Timestamp(ts).date() <= adjusted_through
    )
    return latest.value * factor * close


def median_dollar_volume(bars_before: pd.DataFrame) -> float | None:
    """Median of close x volume over the given bars; None when there are none."""
    if bars_before.empty:
        return None
    return float(statistics.median(bars_before["close"] * bars_before["volume"]))

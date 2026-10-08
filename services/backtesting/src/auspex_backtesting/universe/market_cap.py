import math
import statistics
from collections.abc import Sequence
from datetime import date

import pandas as pd

from auspex_backtesting.universe.model import ShareCount


def market_cap_usd(
    shares: Sequence[ShareCount], close: float, as_of: date, splits: pd.Series
) -> float | None:
    """Shares outstanding as last reported before `as_of`, times `close`.

    Only counts filed strictly before `as_of` are used: filing dates carry no time of day, so a
    count filed on `as_of` may not have been public at the open. `close` is split-adjusted to
    today's share basis, so the count is restated through every split after the date it refers
    to (`splits` holds new-shares-per-old-share ratios indexed by split date).
    """
    known = [s for s in shares if s.filed < as_of]
    if not known:
        return None
    latest = max(known, key=lambda s: (s.filed, s.end))
    factor = math.prod(float(r) for ts, r in splits.items() if pd.Timestamp(ts).date() > latest.end)
    return latest.value * factor * close


def median_dollar_volume(bars_before: pd.DataFrame) -> float | None:
    """Median of close x volume over the given bars; None when there are none."""
    if bars_before.empty:
        return None
    return float(statistics.median(bars_before["close"] * bars_before["volume"]))

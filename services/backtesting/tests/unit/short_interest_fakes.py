"""Fakes shared by the short interest tests."""

import math
from collections.abc import Mapping, Sequence
from datetime import date

from auspex_backtesting.universe.model import ShareCount


class FixedShares:
    """Share counts by ticker, counted on `counted_on` and filed on `filed` (default: the same
    day), and split factors from a list of `(ticker, split_date, ratio)`. A ticker in
    `unknown_splits` has no known factor for intervals starting in
    `[unknown_after, unknown_before)`, by default all of them."""

    def __init__(
        self,
        shares: Mapping[str, float],
        splits: Sequence[tuple[str, date, float]] = (),
        unknown_splits: Sequence[str] = (),
        counted_on: date = date(2024, 12, 31),
        filed: date | None = None,
        unknown_after: date = date.min,
        unknown_before: date = date.max,
    ) -> None:
        self.shares = shares
        self.splits = splits
        self.unknown = set(unknown_splits)
        self.counted_on = counted_on
        self.filed = filed or counted_on
        self.unknown_after = unknown_after
        self.unknown_before = unknown_before

    def share_count(self, ticker: str, as_of: date) -> ShareCount | None:
        value = self.shares.get(ticker)
        return ShareCount(value, self.counted_on, self.filed) if value else None

    def factor(self, ticker: str, after: date, through: date) -> float | None:
        if self.missing_reason(ticker, after, through):
            return None
        return math.prod(r for t, d, r in self.splits if t == ticker and after < d <= through)

    def missing_reason(self, ticker: str, after: date, through: date) -> str | None:
        unknown = ticker in self.unknown and self.unknown_after <= after < self.unknown_before
        return "split_history_unavailable" if unknown else None

"""Shares outstanding, market capitalisation and split factors as known on a date, for
scaling the panels."""

import math
from collections.abc import Iterable, Mapping, Sequence
from datetime import date, timedelta
from typing import Literal, Protocol

import pandas as pd

from auspex_backtesting.ownership.store import OwnershipStore
from auspex_backtesting.prices.splits import SplitHistory
from auspex_backtesting.universe.model import ShareCount, UniverseSnapshot
from auspex_backtesting.universe.store import UniverseStore

SHARES_OUTSTANDING_KEY = "shares_outstanding.parquet"


FactorMissing = Literal["ticker_history_uncertain", "split_history_unavailable"]


class SharesOutstanding(Protocol):
    def shares_outstanding(self, cik: str, as_of: date) -> float | None: ...


class ShareCounts(Protocol):
    def share_count(self, cik: str, as_of: date) -> ShareCount | None: ...


class SplitFactors(Protocol):
    """The product of a company's split ratios dated in `(after, through]`: shares counted on
    `after` times the factor are shares on `through`'s basis. None when the basis is unknown,
    with the reason from `missing_reason`."""

    def factor(self, cik: str, after: date, through: date) -> float | None: ...

    def missing_reason(self, cik: str, after: date, through: date) -> FactorMissing | None: ...


class SplitHistories(Protocol):
    def ensure(self, ticker: str, through: date) -> SplitHistory: ...


class MarketCaps(Protocol):
    def market_cap_usd(self, cik: str, as_of: date) -> float | None: ...


class ShareCountPanel:
    """Cover-page share counts (`cik, value, end, filed`). A count is known from the day after
    it was filed: filing dates carry no time of day."""

    def __init__(self, counts: pd.DataFrame) -> None:
        self._by_cik: dict[str, list[tuple[date, date, float]]] = {}
        for row in counts.itertuples(index=False):
            self._by_cik.setdefault(str(row.cik), []).append((row.filed, row.end, float(row.value)))
        for rows in self._by_cik.values():
            rows.sort()

    @classmethod
    def from_counts(cls, counts: Mapping[str, Sequence[ShareCount]]) -> ShareCountPanel:
        return cls(counts_frame(counts))

    @classmethod
    def load(cls, store: OwnershipStore) -> ShareCountPanel:
        stored = store.read(SHARES_OUTSTANDING_KEY)
        return cls(stored[0] if stored else pd.DataFrame(columns=["cik", "value", "end", "filed"]))

    def shares_outstanding(self, cik: str, as_of: date) -> float | None:
        count = self.share_count(cik, as_of)
        return count.value if count else None

    def share_count(self, cik: str, as_of: date) -> ShareCount | None:
        """The latest count filed before `as_of`, with the date it refers to."""
        known = [r for r in self._by_cik.get(cik, []) if r[0] < as_of]
        if not known:
            return None
        filed, end, value = known[-1]
        return ShareCount(value, end, filed)


def counts_frame(counts: Mapping[str, Sequence[ShareCount]]) -> pd.DataFrame:
    return pd.DataFrame(
        [{"cik": cik, "value": s.value, "end": s.end, "filed": s.filed}
         for cik, rows in sorted(counts.items()) for s in rows],
        columns=["cik", "value", "end", "filed"],
    )


class UniverseMarketCaps:
    """A company's market cap from the latest universe month whose rebalance date is on or
    before the date asked about; None when it was not a member then."""

    def __init__(self, universe: UniverseStore, rules_version: int) -> None:
        self._caps: list[tuple[date, dict[str, float]]] = []
        for month in universe.months(rules_version):
            snapshot = universe.read(rules_version, month)
            if snapshot is None:
                continue
            self._caps.append((snapshot.rebalance_date, {
                m.cik: m.market_cap_usd for m in snapshot.members if m.market_cap_usd is not None
            }))
        self._caps.sort(key=lambda c: c[0])

    def market_cap_usd(self, cik: str, as_of: date) -> float | None:
        current = [caps for rebalance, caps in self._caps if rebalance <= as_of]
        return current[-1].get(cik) if current else None



class UniverseSplitFactors:
    """Split factors by CIK, through the ticker the universe resolves for it.

    Only a ticker the universe vouches for over the whole interval is used: the CIK is a member
    in every month the interval touches, under the same `current` ticker with `complete` price
    coverage. A continuous price series under that symbol is the evidence that the provider
    tracks this issuer under it, through any earlier symbol change. Anything less is
    `ticker_history_uncertain`; there is no ticker-history table to fall back on. The ticker's
    split history must then be known up to `through`, or the factor is
    `split_history_unavailable`.
    """

    def __init__(self, snapshots: Iterable[UniverseSnapshot], splits: SplitHistories) -> None:
        self._months = {s.month: {m.cik: m for m in s.members} for s in snapshots}
        self._splits = splits
        self._cache: dict[tuple[str, date, date], float | FactorMissing] = {}

    @classmethod
    def load(
        cls, universe: UniverseStore, rules_version: int, splits: SplitHistories
    ) -> UniverseSplitFactors:
        snapshots = (universe.read(rules_version, m) for m in universe.months(rules_version))
        return cls((s for s in snapshots if s is not None), splits)

    def factor(self, cik: str, after: date, through: date) -> float | None:
        result = self._resolve(cik, after, through)
        return None if isinstance(result, str) else result

    def missing_reason(self, cik: str, after: date, through: date) -> FactorMissing | None:
        result = self._resolve(cik, after, through)
        return result if isinstance(result, str) else None

    def _resolve(self, cik: str, after: date, through: date) -> float | FactorMissing:
        key = (cik, after, through)
        if key not in self._cache:
            self._cache[key] = self._compute(cik, after, through)
        return self._cache[key]

    def _compute(self, cik: str, after: date, through: date) -> float | FactorMissing:
        if through <= after:
            return 1.0
        members = [self._months.get(m, {}).get(cik) for m in _months_touching(after, through)]
        tickers = {m.ticker for m in members if m is not None}
        if (
            any(
                m is None or m.ticker_source != "current" or m.price_coverage != "complete"
                for m in members
            )
            or len(tickers) != 1
        ):
            return "ticker_history_uncertain"
        (ticker,) = tickers
        if ticker is None:
            return "ticker_history_uncertain"
        history = self._splits.ensure(ticker, through)
        if (
            history.status == "unavailable"
            or history.covered_through is None
            or history.covered_through < through
        ):
            return "split_history_unavailable"
        return math.prod(
            float(r)
            for ts, r in history.ratios.items()
            if after < pd.Timestamp(ts).date() <= through
        )


def _months_touching(after: date, through: date) -> list[str]:
    """`YYYY-MM` of every month with a day in `(after, through]`."""
    first = after + timedelta(days=1)
    year, month = first.year, first.month
    months = []
    while (year, month) <= (through.year, through.month):
        months.append(f"{year:04d}-{month:02d}")
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return months

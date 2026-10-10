"""Shares outstanding and market capitalisation as known on a date, for scaling the panels."""

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Protocol

import pandas as pd

from auspex_backtesting.ownership.store import OwnershipStore
from auspex_backtesting.universe.model import ShareCount
from auspex_backtesting.universe.store import UniverseStore

SHARES_OUTSTANDING_KEY = "shares_outstanding.parquet"


class SharesOutstanding(Protocol):
    def shares_outstanding(self, cik: str, as_of: date) -> float | None: ...


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
        known = [r for r in self._by_cik.get(cik, []) if r[0] < as_of]
        return known[-1][2] if known else None


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

from collections.abc import Iterable
from datetime import date

from auspex_backtesting.universe.model import UniverseMember, UniverseSnapshot
from auspex_backtesting.universe.store import UniverseStore


class UniverseMembership:
    """Which tickers a backtest may trade on a given day, and how each one's listing ended.

    Membership comes from the snapshot of the trading day's month, fixed before that month's
    first session. Exit and price coverage come from `listings`, the latest build's view of each
    listing span, because a snapshot is never rewritten and one built live cannot know a later
    delisting. `as_of` is the last day the price data can cover; a holding window ending after
    it is still running, not missing.
    """

    def __init__(
        self,
        snapshots: Iterable[UniverseSnapshot],
        listings: Iterable[UniverseMember],
        *,
        as_of: date,
    ) -> None:
        self._by_month = {
            s.month: {m.ticker: m for m in s.members if m.ticker} for s in snapshots
        }
        self._latest = {(m.cik, m.entered_on): m for m in listings}
        self.as_of = as_of

    def member(self, ticker: str, d: date) -> UniverseMember | None:
        row = self._by_month.get(f"{d:%Y-%m}", {}).get(ticker)
        if row is None:
            return None
        return self._latest.get((row.cik, row.entered_on), row)


def load_membership(store: UniverseStore, rules_version: int) -> UniverseMembership:
    """Every stored month of `rules_version` with the latest listings, as a backtest reads them."""
    listings = store.read_listings(rules_version)
    if listings is None:
        raise LookupError(f"no universe listings stored for rules version {rules_version}")
    rows, as_of = listings
    snapshots = [s for m in store.months(rules_version) if (s := store.read(rules_version, m))]
    return UniverseMembership(snapshots, rows, as_of=as_of)

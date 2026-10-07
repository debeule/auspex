from datetime import date, timedelta

from auspex_backtesting.market_sim._snapshots import price_on
from auspex_backtesting.market_sim.calendar import MarketCalendar
from auspex_backtesting.prices.snapshot_store import PriceSnapshotStore


class FillModel:
    """Fills at the open on entry and the close on exit, from MinIO snapshots only.

    The caller owns entry timing: `entry_date` must already be a session after the signal was
    public (T+1 open after `corroborated_at` plus the known-at delay), or the open precedes it.
    """

    def __init__(self, store: PriceSnapshotStore, calendar: MarketCalendar | None = None) -> None:
        self._store = store
        self._calendar = calendar or MarketCalendar()

    def entry_price(self, ticker: str, entry_date: date) -> float:
        return price_on(self._store, ticker, entry_date, "open")

    def exit_price(self, ticker: str, entry_date: date, holding_calendar_days: int) -> float:
        return price_on(self._store, ticker, self.exit_date(entry_date, holding_calendar_days), "close")

    def exit_date(self, entry_date: date, holding_calendar_days: int) -> date:
        return self._calendar.next_trading_day(entry_date + timedelta(days=holding_calendar_days))

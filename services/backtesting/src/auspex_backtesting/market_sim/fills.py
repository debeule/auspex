from datetime import date, timedelta

from auspex_backtesting.market_sim._snapshots import bar_on, price_on
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

    def stop_exit_price(
        self,
        ticker: str,
        d: date,
        stop_price: float,
        is_short: bool = False,
        binary_event: bool = False,
    ) -> float | None:
        """Fill for a resting stop on `d`, or None if the day's range never reached it.

        A stop is a market order once touched, so a gap through it fills at the open, not the
        stop. On a binary event day (readout, FDA decision) news can land mid-session behind a
        halt, which daily bars cannot place in time; a touched stop then fills at the day's
        worst price, the low for a long and the high for a short.
        """
        bar = bar_on(self._store, ticker, d)
        open_, high, low = float(bar["open"]), float(bar["high"]), float(bar["low"])
        if is_short:
            if high < stop_price:
                return None
            if binary_event:
                return high
            return max(open_, stop_price)
        if low > stop_price:
            return None
        if binary_event:
            return low
        return min(open_, stop_price)

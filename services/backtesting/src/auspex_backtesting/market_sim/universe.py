from datetime import date

import pandas as pd

from auspex_backtesting.market_sim.calendar import MarketCalendar
from auspex_backtesting.market_sim.errors import MissingPriceDataError
from auspex_backtesting.prices.snapshot_store import PriceSnapshotStore


class TradableUniverse:
    """Fails a backtest up front when a ticker's snapshot does not span the requested range,
    rather than letting it surface as a missing fill halfway through."""

    def __init__(self, store: PriceSnapshotStore, calendar: MarketCalendar | None = None) -> None:
        self._store = store
        self._calendar = calendar or MarketCalendar()

    def validate(self, tickers: list[str], start: date, end: date) -> None:
        sessions = self._calendar.sessions_between(start, end)
        if not sessions:
            return
        for ticker in tickers:
            df = self._store.load(ticker)
            if df is None or df.empty:
                raise MissingPriceDataError(_message(ticker, start, end, "no snapshot"))
            dates = pd.DatetimeIndex(df.index).date
            if min(dates) > sessions[0] or max(dates) < sessions[-1]:
                raise MissingPriceDataError(
                    _message(ticker, start, end, f"snapshot covers {min(dates)}..{max(dates)}")
                )


def _message(ticker: str, start: date, end: date, detail: str) -> str:
    return f"{ticker}: no price data for {start.isoformat()}..{end.isoformat()} ({detail})"

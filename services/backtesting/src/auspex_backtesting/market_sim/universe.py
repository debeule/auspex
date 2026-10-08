from collections.abc import Mapping
from datetime import date, timedelta

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

    def validate(
        self,
        tickers: list[str],
        start: date,
        end: date,
        spans: Mapping[str, tuple[date, date | None]] | None = None,
    ) -> None:
        """`spans` maps a ticker to its listing `(entered_on, exited_on)`; such a ticker needs
        prices only while listed: from the session after its exchange registration to the session
        before its delisting notice."""
        for ticker in tickers:
            span = (spans or {}).get(ticker)
            first, last = start, end
            if span is not None:
                entered_on, exited_on = span
                first = max(start, entered_on + timedelta(days=1))
                if exited_on is not None:
                    last = min(end, exited_on - timedelta(days=1))
            sessions = self._calendar.sessions_between(first, last)
            if not sessions:
                continue
            df = self._store.load(ticker)
            if df is None or df.empty:
                raise MissingPriceDataError(_message(ticker, first, last, "no snapshot"))
            dates = pd.DatetimeIndex(df.index).date
            if min(dates) > sessions[0] or max(dates) < sessions[-1]:
                raise MissingPriceDataError(
                    _message(ticker, first, last, f"snapshot covers {min(dates)}..{max(dates)}")
                )


def _message(ticker: str, start: date, end: date, detail: str) -> str:
    return f"{ticker}: no price data for {start.isoformat()}..{end.isoformat()} ({detail})"

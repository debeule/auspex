from datetime import date

import pandas as pd

from auspex_backtesting.market_sim.errors import PriceDataAbsentError
from auspex_backtesting.prices.snapshot_store import PriceSnapshotStore


def price_on(store: PriceSnapshotStore, ticker: str, d: date, column: str) -> float:
    return float(bar_on(store, ticker, d)[column])


def bar_on(store: PriceSnapshotStore, ticker: str, d: date) -> pd.Series:
    df = _load(store, ticker)
    rows = df[_row_dates(df) == d]
    if rows.empty:
        raise PriceDataAbsentError(f"no price bar for {ticker} on {d.isoformat()}")
    return rows.iloc[0]


def bars_before(store: PriceSnapshotStore, ticker: str, as_of: date, sessions: int) -> pd.DataFrame:
    """The last `sessions` bars strictly before `as_of`, oldest first; the as-of bar itself is
    not yet complete when an order is placed at its open."""
    df = _load(store, ticker)
    return df[_row_dates(df) < as_of].sort_index().tail(sessions)


def _load(store: PriceSnapshotStore, ticker: str) -> pd.DataFrame:
    df = store.load(ticker)
    if df is None or df.empty:
        raise PriceDataAbsentError(f"no price snapshot for {ticker}")
    return df


def _row_dates(df: pd.DataFrame) -> pd.Index:
    # Snapshots are stored with a UTC midnight index; .date drops the time without shifting the day.
    return pd.Index(pd.DatetimeIndex(df.index).date)

from datetime import date

import pandas as pd

from auspex_backtesting.market_sim.errors import PriceDataAbsentError
from auspex_backtesting.prices.snapshot_store import PriceSnapshotStore


def price_on(store: PriceSnapshotStore, ticker: str, d: date, column: str) -> float:
    df = store.load(ticker)
    if df is None or df.empty:
        raise PriceDataAbsentError(f"no price snapshot for {ticker}")
    rows = df[_row_dates(df) == d]
    if rows.empty:
        raise PriceDataAbsentError(f"no {column} price for {ticker} on {d.isoformat()}")
    return float(rows[column].iloc[0])


def _row_dates(df: pd.DataFrame) -> pd.Index:
    # Snapshots are stored with a UTC midnight index; .date drops the time without shifting the day.
    return pd.Index(pd.DatetimeIndex(df.index).date)

"""Keeps each OHLCV snapshot current by appending new daily bars.

A bar, once written, is never rewritten: backtests over any past window read the same rows
they read the first time. When the provider has re-adjusted history (a split, a large
special dividend), its value for the last stored bar no longer matches ours; the refresh is
refused instead of splicing two price scales into one series.
"""

import io
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import pandas as pd
from minio import Minio

from auspex_backtesting.market_sim.fx import FX_TICKER
from auspex_backtesting.prices.price_fetcher import _from_stooq, _from_yahoo, _normalize
from auspex_backtesting.prices.snapshot_store import PRICES_BUCKET, PriceSnapshotStore, snapshot_key

BENCHMARK_TICKER = "XBI"

# Relative close difference on the overlapping bar above which history counts as re-adjusted.
# Ordinary dividends move Yahoo's adjusted close by well under this.
_OVERLAP_TOLERANCE = 0.02


class PriceDataUnavailableError(Exception):
    pass


class SnapshotDiscontinuityError(Exception):
    pass


@dataclass(frozen=True)
class RefreshResult:
    ticker: str
    rows_added: int
    last_date: str


def price_universe(watched_tickers: str) -> list[str]:
    """Tickers the system needs prices for: the watchlist, the XBI benchmark and the EUR/USD
    rate, in that order and without duplicates. `watched_tickers` is comma-separated."""
    tickers = [t.strip() for t in watched_tickers.split(",") if t.strip()]
    return list(dict.fromkeys([*tickers, BENCHMARK_TICKER, FX_TICKER]))


def _utc_today() -> date:
    return datetime.now(UTC).date()


class PriceRefresher:
    def __init__(
        self,
        minio_client: Minio,
        history_start: date,
        bucket: str = PRICES_BUCKET,
        today: Callable[[], date] = _utc_today,
    ) -> None:
        self._minio = minio_client
        self._bucket = bucket
        self._snapshots = PriceSnapshotStore(minio_client, bucket)
        self._history_start = history_start
        self._today = today

    def refresh(self, ticker: str) -> RefreshResult:
        stored = self._snapshots.load(ticker)
        # Providers treat the end date as exclusive.
        end = self._today() + timedelta(days=1)

        if stored is None or stored.empty:
            fetched = _download(ticker, self._history_start, end)
            if fetched.empty:
                raise PriceDataUnavailableError(f"{ticker}: no data from Yahoo or Stooq")
            self._store(ticker, fetched)
            return RefreshResult(ticker, len(fetched), _last_day(fetched))

        last_stored = stored.index.max()
        fetched = _download(ticker, last_stored.date(), end)
        if last_stored in fetched.index:
            _check_continuity(ticker, stored.loc[last_stored], fetched.loc[last_stored])

        new_bars = fetched[fetched.index > last_stored]
        if new_bars.empty:
            return RefreshResult(ticker, 0, _last_day(stored))

        extended = pd.concat([stored, new_bars[stored.columns]])
        self._store(ticker, extended)
        return RefreshResult(ticker, len(new_bars), _last_day(extended))

    def _store(self, ticker: str, df: pd.DataFrame) -> None:
        buf = io.BytesIO()
        df.to_parquet(buf)
        length = buf.tell()
        buf.seek(0)
        self._minio.put_object(
            self._bucket, snapshot_key(ticker), buf, length,
            content_type="application/octet-stream",
        )


def _download(ticker: str, start: date, end: date) -> pd.DataFrame:
    df = _from_yahoo(ticker, start, end)
    if df is None or df.empty:
        # yfinance reports a blocked or failed download as an empty frame, not an exception
        df = _from_stooq(ticker, start, end)
    if df is None or df.empty:
        return pd.DataFrame()
    return _normalize(df)


def _check_continuity(ticker: str, stored_bar: pd.Series, fetched_bar: pd.Series) -> None:
    ours, theirs = float(stored_bar["close"]), float(fetched_bar["close"])
    if abs(theirs - ours) > _OVERLAP_TOLERANCE * abs(ours):
        raise SnapshotDiscontinuityError(
            f"{ticker}: provider close {theirs} on {stored_bar.name.date()} differs from the "
            f"stored {ours}; history was re-adjusted, so the snapshot must be rebuilt"
        )


def _last_day(df: pd.DataFrame) -> str:
    return str(df.index.max().date().isoformat())

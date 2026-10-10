"""Keeps each OHLCV snapshot current by appending new daily bars.

A bar, once written, is never rewritten: backtests over any past window read the same rows
they read the first time. So only completed bars are written: a bar whose session has not
closed and settled is dropped and fetched again by the next refresh. A refresh appends only
when the provider's response repeats the last stored bar at the same price. When the provider
has re-adjusted history (a split, a large special dividend), its value for that bar no longer
matches ours; when the response does not reach back to it there is no evidence either way.
Both refuse the refresh instead of risking two price scales in one series.

A snapshot records the UTC date of its first download (`ADJUSTED_THROUGH`): its closes are on
the share basis of that day, and stay there because a later re-adjustment stops the appends.
"""

import io
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import pandas as pd
from minio import Minio

from auspex_backtesting.market_sim.calendar import MarketCalendar
from auspex_backtesting.market_sim.fx import FX_TICKER
from auspex_backtesting.prices.price_fetcher import _from_stooq, _from_yahoo, _normalize
from auspex_backtesting.prices.snapshot_store import (
    PRICES_BUCKET,
    PriceSnapshotStore,
    adjusted_through,
    snapshot_key,
    snapshot_parquet,
)

BENCHMARK_TICKER = "XBI"

# Relative close difference on the overlapping bar above which history counts as re-adjusted.
# Ordinary dividends move Yahoo's adjusted close by well under this.
_OVERLAP_TOLERANCE = 0.02
# How long after a session closes its daily bar is taken as final: Yahoo revises the last bar
# for a while after the close.
_SETTLE_DELAY = timedelta(hours=2)


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


def _utc_now() -> datetime:
    return datetime.now(UTC)


class PriceRefresher:
    def __init__(
        self,
        minio_client: Minio,
        history_start: date,
        bucket: str = PRICES_BUCKET,
        now: Callable[[], datetime] = _utc_now,
        calendar: MarketCalendar | None = None,
    ) -> None:
        self._minio = minio_client
        self._bucket = bucket
        self._snapshots = PriceSnapshotStore(minio_client, bucket)
        self._history_start = history_start
        self._now = now
        self._calendar = calendar or MarketCalendar()

    def refresh(self, ticker: str) -> RefreshResult:
        stored = self._snapshots.load(ticker)
        now = self._now()
        # Providers treat the end date as exclusive.
        end = now.astimezone(UTC).date() + timedelta(days=1)

        if stored is None or stored.empty:
            fetched = self._completed(ticker, _download(ticker, self._history_start, end), now)
            if fetched.empty:
                raise PriceDataUnavailableError(
                    f"{ticker}: no completed bars from Yahoo or Stooq"
                )
            self._store(ticker, fetched, now.astimezone(UTC).date())
            return RefreshResult(ticker, len(fetched), _last_day(fetched))

        last_stored = stored.index.max()
        fetched = self._completed(ticker, _download(ticker, last_stored.date(), end), now)
        if fetched.empty:
            return RefreshResult(ticker, 0, _last_day(stored))
        if last_stored not in fetched.index:
            raise SnapshotDiscontinuityError(
                f"{ticker}: the provider's response does not include the last stored bar "
                f"{last_stored.date()}, so new bars cannot be checked against it"
            )
        _check_continuity(ticker, stored.loc[last_stored], fetched.loc[last_stored])

        new_bars = fetched[fetched.index > last_stored]
        if new_bars.empty:
            return RefreshResult(ticker, 0, _last_day(stored))

        extended = pd.concat([stored, new_bars[stored.columns]])
        self._store(ticker, extended, adjusted_through(stored))
        return RefreshResult(ticker, len(new_bars), _last_day(extended))

    def _completed(self, ticker: str, bars: pd.DataFrame, now: datetime) -> pd.DataFrame:
        if bars.empty:
            return bars
        final = [self._closes_at(ticker, ts.date()) + _SETTLE_DELAY <= now for ts in bars.index]
        return bars[final]

    def _closes_at(self, ticker: str, d: date) -> datetime:
        # EUR/USD trades around the clock, and a bar on a day with no NYSE session has no close:
        # both end with their UTC day.
        if ticker == FX_TICKER or not self._calendar.is_trading_day(d):
            return datetime(d.year, d.month, d.day, tzinfo=UTC) + timedelta(days=1)
        return self._calendar.session_close(d)

    def _store(self, ticker: str, df: pd.DataFrame, adjusted: date | None) -> None:
        data = snapshot_parquet(df, adjusted)
        self._minio.put_object(
            self._bucket, snapshot_key(ticker), io.BytesIO(data), len(data),
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

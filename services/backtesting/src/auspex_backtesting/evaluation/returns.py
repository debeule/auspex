from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd

from auspex_backtesting.market_sim.calendar import MarketCalendar
from auspex_backtesting.market_sim.errors import PriceDataAbsentError
from auspex_backtesting.prices.snapshot_store import PriceSnapshotStore


@dataclass(frozen=True)
class AbnormalReturnSeries:
    """One cumulative abnormal return per event over the same relative window.

    `window_starts` and `window_ends` are the first and last sessions of each event's window;
    `direction` is +1 for a long hypothesis and -1 for a short one, so `hit_rate` counts
    returns in the registered direction.
    """

    values: tuple[float, ...]
    tickers: tuple[str, ...]
    entry_dates: tuple[date, ...]
    window_starts: tuple[date, ...]
    window_ends: tuple[date, ...]
    alphas: tuple[float, ...]
    betas: tuple[float, ...]
    fallback: tuple[bool, ...]
    direction: int = 1

    @property
    def n(self) -> int:
        return len(self.values)

    @property
    def mean(self) -> float:
        return float(np.mean(self.values)) if self.values else float("nan")

    @property
    def std(self) -> float:
        return float(np.std(self.values, ddof=1)) if self.n > 1 else float("nan")

    @property
    def hit_rate(self) -> float:
        if not self.values:
            return float("nan")
        return sum(1 for v in self.values if v * self.direction > 0) / self.n

    @property
    def n_fallback(self) -> int:
        return sum(self.fallback)

    @property
    def event_months(self) -> tuple[str, ...]:
        return tuple(f"{d.year:04d}-{d.month:02d}" for d in self.entry_dates)

    def with_values(self, values: Sequence[float]) -> AbnormalReturnSeries:
        """The same events with other per-event values, such as returns net of costs."""
        if len(values) != self.n:
            raise ValueError(f"expected {self.n} values, got {len(values)}")
        return AbnormalReturnSeries(
            values=tuple(float(v) for v in values),
            tickers=self.tickers,
            entry_dates=self.entry_dates,
            window_starts=self.window_starts,
            window_ends=self.window_ends,
            alphas=self.alphas,
            betas=self.betas,
            fallback=self.fallback,
            direction=self.direction,
        )


class AbnormalReturnCalculator:
    """Market-model abnormal returns against the protocol's benchmark.

    For each event, OLS of the ticker's daily close-to-close return on the benchmark's over the
    registered estimation window (in sessions relative to the entry date) gives `alpha` and
    `beta`; the abnormal return over `window` is the sum of `R - (alpha + beta * R_benchmark)`.
    Sessions are the benchmark's. With fewer than the registered minimum of estimation days the
    event falls back to the market-adjusted model (`alpha = 0`, `beta = 1`) and is flagged.
    """

    def __init__(self, protocol: dict[str, Any]) -> None:
        settings = protocol["abnormal_return"]
        if settings["model"] != "market_model" or settings["fallback"] != "market_adjusted":
            raise ValueError(f"unsupported abnormal_return settings: {settings}")
        self.benchmark = str(settings["benchmark"])
        first, last = settings["estimation_window_trading_days"]
        self._estimation = (int(first), int(last))
        self._min_obs = int(settings["min_estimation_obs"])

    def compute(
        self,
        events: pd.DataFrame,
        prices: PriceSnapshotStore,
        window: tuple[int, int],
        *,
        direction: int = 1,
    ) -> AbnormalReturnSeries:
        """`events` needs `ticker` and `entry_date` (session 0) columns."""
        bench_close = _closes(prices, self.benchmark)
        sessions = bench_close.index
        bench_returns = bench_close.pct_change(fill_method=None).to_numpy()
        ticker_returns: dict[str, np.ndarray] = {}

        rows: list[tuple[float, str, date, date, date, float, float, bool]] = []
        for ticker, entry in zip(events["ticker"], events["entry_date"], strict=True):
            ticker = str(ticker)
            entry = _as_date(entry)
            if ticker not in ticker_returns:
                closes = _closes(prices, ticker).reindex(sessions)
                ticker_returns[ticker] = closes.pct_change(fill_method=None).to_numpy()
            r_i = ticker_returns[ticker]
            i0 = int(sessions.searchsorted(entry))
            if i0 >= len(sessions):
                raise PriceDataAbsentError(f"{self.benchmark}: no session on or after {entry}")

            alpha, beta, fallback = self._fit(r_i, bench_returns, i0)
            first, last = i0 + window[0], i0 + window[1]
            if first < 0 or last >= len(sessions):
                raise PriceDataAbsentError(
                    f"{ticker}: window {window} around {entry} runs past the price history"
                )
            ri, rm = r_i[first : last + 1], bench_returns[first : last + 1]
            if np.isnan(ri).any() or np.isnan(rm).any():
                raise PriceDataAbsentError(
                    f"{ticker}: missing returns in window {window} around {entry}"
                )
            car = float(np.sum(ri - (alpha + beta * rm)))
            rows.append(
                (car, ticker, entry, sessions[first], sessions[last], alpha, beta, fallback)
            )

        return AbnormalReturnSeries(
            values=tuple(r[0] for r in rows),
            tickers=tuple(r[1] for r in rows),
            entry_dates=tuple(r[2] for r in rows),
            window_starts=tuple(r[3] for r in rows),
            window_ends=tuple(r[4] for r in rows),
            alphas=tuple(r[5] for r in rows),
            betas=tuple(r[6] for r in rows),
            fallback=tuple(r[7] for r in rows),
            direction=direction,
        )

    def _fit(self, r_i: np.ndarray, r_m: np.ndarray, i0: int) -> tuple[float, float, bool]:
        lo = max(i0 + self._estimation[0], 0)
        hi = max(i0 + self._estimation[1], 0)
        y, x = r_i[lo : hi + 1], r_m[lo : hi + 1]
        usable = ~(np.isnan(y) | np.isnan(x))
        y, x = y[usable], x[usable]
        if len(y) < self._min_obs:
            return 0.0, 1.0, True
        beta = float(np.cov(x, y, ddof=1)[0, 1] / np.var(x, ddof=1))
        alpha = float(y.mean() - beta * x.mean())
        return alpha, beta, False


class KnownAtDelay:
    """The entry session of an event first known `delay_days` after it was corroborated."""

    def __init__(self, calendar: MarketCalendar) -> None:
        self._calendar = calendar

    def entry_date(self, corroborated_at: date | datetime, delay_days: int) -> date:
        return self._calendar.next_trading_day(
            _as_date(corroborated_at) + timedelta(days=delay_days)
        )

    def apply(self, events: pd.DataFrame, delay_days: int) -> pd.DataFrame:
        """A copy of `events` with an `entry_date` column from `corroborated_at`."""
        out = events.copy()
        out["entry_date"] = [self.entry_date(d, delay_days) for d in events["corroborated_at"]]
        return out


def _closes(prices: PriceSnapshotStore, ticker: str) -> pd.Series:
    df = prices.load(ticker)
    if df is None or df.empty:
        raise PriceDataAbsentError(f"no price snapshot for {ticker}")
    closes = df["close"].astype(float)
    # Snapshots carry a UTC-midnight index; the session is its calendar date.
    closes.index = pd.Index(pd.DatetimeIndex(df.index).date)
    return closes.sort_index()


def _as_date(value: Any) -> date:
    if isinstance(value, pd.Timestamp):
        timestamp_date: date = value.date()
        return timestamp_date
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raise TypeError(f"not a date: {value!r}")

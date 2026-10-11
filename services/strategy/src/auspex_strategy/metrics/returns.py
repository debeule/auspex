from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
from auspex_backtesting.evaluation import AbnormalReturnCalculator, BootstrapCI, DeflatedSharpe
from auspex_backtesting.prices.snapshot_store import PriceSnapshotStore

from auspex_strategy.metrics.trades import InsufficientTradeDataError, trades_per_year
from auspex_strategy.models import Direction
from auspex_strategy.runtime.book import ClosedTrade


def trade_abnormal_returns(
    trades: Sequence[ClosedTrade], prices: PriceSnapshotStore, protocol: dict[str, Any]
) -> list[float]:
    """Each trade's abnormal return against the protocol's benchmark, in the trade's direction
    and net of its costs as a fraction of the entry notional.

    The market-model return window runs from the session after entry to the exit session, the
    protocol's `[+1, +h]` convention for an `h`-session hold; a same-session exit uses `[+1, +1]`.
    """
    calculator = AbnormalReturnCalculator(protocol)
    benchmark = prices.load(calculator.benchmark)
    if benchmark is None or benchmark.empty:
        raise ValueError(f"no price snapshot for the benchmark {calculator.benchmark}")
    sessions = pd.Index(pd.DatetimeIndex(benchmark.index).date).sort_values()

    values = []
    for trade in trades:
        held = int(sessions.searchsorted(trade.exit_date) - sessions.searchsorted(trade.entry_date))
        events = pd.DataFrame({"ticker": [trade.ticker], "entry_date": [trade.entry_date]})
        car = calculator.compute(events, prices, (1, max(held, 1))).values[0]
        sign = 1 if trade.direction is Direction.LONG else -1
        values.append(sign * car - trade.costs_usd / (trade.entry_price * trade.shares))
    return values


@dataclass(frozen=True)
class ReturnMetrics:
    """Trade-level abnormal-return statistics for one strategy version and mode.

    `sharpe` is annualised by trades per year. `deflated_sharpe` is a probability (Bailey and
    López de Prado) computed from the per-trade Sharpe ratio, with `n_trials` the cells already
    evaluated on the hypothesis's corpus family. `max_drawdown_pct` is the largest fall of
    `capital + cumulative P&L` from its running peak, in percent, where `capital` is the most the
    risk layer allocated to one position.
    """

    n: int
    n_trials: int | None
    mean_abnormal_return: float | None
    bootstrap_ci_95: tuple[float, float] | None
    cumulative_abnormal_return_series: list[dict[str, Any]] | None
    sharpe: float | None
    deflated_sharpe: float | None
    max_drawdown_pct: float | None
    insufficient_data: bool = False
    abnormal_returns: tuple[float, ...] = field(default=(), repr=False)

    @classmethod
    def compute(
        cls,
        trades: Sequence[ClosedTrade],
        abnormal_returns: Sequence[float],
        *,
        n_trials: int,
        min_trades: int,
    ) -> ReturnMetrics:
        n = len(trades)
        if n < min_trades or n == 0:
            raise InsufficientTradeDataError(n, min_trades)
        if len(abnormal_returns) != n:
            raise ValueError(f"{n} trades but {len(abnormal_returns)} abnormal returns")
        returns = pd.Series(list(abnormal_returns), dtype=float)
        cumulative = returns.cumsum()
        per_trade = _per_trade_sharpe(returns)
        per_year = trades_per_year(trades)
        return cls(
            n=n,
            n_trials=n_trials,
            mean_abnormal_return=float(returns.mean()),
            bootstrap_ci_95=BootstrapCI.compute(returns),
            cumulative_abnormal_return_series=[
                {"exit_date": t.exit_date.isoformat(), "cumulative_abnormal_return": float(c)}
                for t, c in zip(trades, cumulative, strict=True)
            ],
            sharpe=(
                per_trade * math.sqrt(per_year)
                if per_trade is not None and per_year is not None else None
            ),
            deflated_sharpe=_deflated_sharpe(returns, per_trade, n_trials),
            max_drawdown_pct=_max_drawdown_pct(trades),
            abnormal_returns=tuple(float(v) for v in returns),
        )

    @classmethod
    def insufficient(cls, n: int) -> ReturnMetrics:
        return cls(
            n=n,
            n_trials=None,
            mean_abnormal_return=None,
            bootstrap_ci_95=None,
            cumulative_abnormal_return_series=None,
            sharpe=None,
            deflated_sharpe=None,
            max_drawdown_pct=None,
            insufficient_data=True,
        )

    @classmethod
    def from_values(
        cls,
        *,
        n: int,
        mean_abnormal_return: float,
        bootstrap_ci_95: tuple[float, float] | None = None,
    ) -> ReturnMetrics:
        """Metrics known only by their summary values, such as a reported backtest."""
        return cls(
            n=n,
            n_trials=None,
            mean_abnormal_return=mean_abnormal_return,
            bootstrap_ci_95=bootstrap_ci_95,
            cumulative_abnormal_return_series=None,
            sharpe=None,
            deflated_sharpe=None,
            max_drawdown_pct=None,
        )


def _per_trade_sharpe(returns: pd.Series) -> float | None:
    std = float(returns.std(ddof=1)) if len(returns) > 1 else float("nan")
    if not std > 0:
        return None
    return float(returns.mean()) / std


def _deflated_sharpe(returns: pd.Series, per_trade: float | None, n_trials: int) -> float | None:
    if per_trade is None or len(returns) < 3:
        return None
    deflated: float = DeflatedSharpe.compute(
        sharpe_ratio=per_trade,
        n_obs=len(returns),
        n_trials=n_trials,
        skewness=float(returns.skew()),
        kurtosis=float(returns.kurt()) + 3.0,
    )
    return deflated


def _max_drawdown_pct(trades: Sequence[ClosedTrade]) -> float | None:
    capital = max(t.capital_eur for t in trades)
    if not capital > 0:
        return None
    peak = equity = capital
    worst = 0.0
    for trade in trades:
        equity += trade.pnl_eur
        peak = max(peak, equity)
        worst = max(worst, (peak - equity) / peak)
    return worst * 100

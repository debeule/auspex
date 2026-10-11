from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from auspex_backtesting.evaluation import BootstrapCI

from auspex_strategy.runtime.book import BookMode, ClosedTrade, VirtualBook
from auspex_strategy.runtime.store import ObjectStore

_DAYS_PER_YEAR = 365.25


class InsufficientTradeDataError(Exception):
    def __init__(self, n: int, min_trades: int) -> None:
        super().__init__(f"{n} closed trades; metrics need at least {min_trades}")
        self.n = n
        self.min_trades = min_trades


def version_trades(
    store: ObjectStore, strategy_name: str, version: str, mode: BookMode
) -> list[ClosedTrade]:
    """The closed trades of one strategy version in one mode, in exit order. Trades opened by
    any other version of the same strategy are never included."""
    trades = [
        t for t in VirtualBook(store, strategy_name, mode).closed_trades()
        if t.strategy_version == version
    ]
    return sorted(trades, key=lambda t: t.exit_date)


@dataclass(frozen=True)
class TradeMetrics:
    """Per-trade statistics in EUR, net of costs. A loss is any trade that did not make money.
    `bootstrap_ci_95` is the interval for `expectancy_eur`, the mean P&L per trade."""

    n: int
    n_wins: int
    n_losses: int
    hit_rate: float | None
    avg_win_eur: float | None
    avg_loss_eur: float | None
    expectancy_eur: float | None
    avg_holding_days: float | None
    trades_per_year: float | None
    bootstrap_ci_95: tuple[float, float] | None
    insufficient_data: bool = False

    @classmethod
    def compute(cls, trades: Sequence[ClosedTrade], min_trades: int) -> TradeMetrics:
        """Raises `InsufficientTradeDataError` below `min_trades`: no statistic is ever
        reported over a smaller sample."""
        n = len(trades)
        if n < min_trades or n == 0:
            raise InsufficientTradeDataError(n, min_trades)
        pnl = [t.pnl_eur for t in trades]
        wins = [p for p in pnl if p > 0]
        losses = [p for p in pnl if p <= 0]
        hit_rate = len(wins) / n
        avg_win = sum(wins) / len(wins) if wins else None
        avg_loss = sum(losses) / len(losses) if losses else None
        expectancy = hit_rate * (avg_win or 0.0) - (1 - hit_rate) * abs(avg_loss or 0.0)
        return cls(
            n=n,
            n_wins=len(wins),
            n_losses=len(losses),
            hit_rate=hit_rate,
            avg_win_eur=avg_win,
            avg_loss_eur=avg_loss,
            expectancy_eur=expectancy,
            avg_holding_days=sum((t.exit_date - t.entry_date).days for t in trades) / n,
            trades_per_year=trades_per_year(trades),
            bootstrap_ci_95=BootstrapCI.compute(pnl),
        )

    @classmethod
    def insufficient(cls, trades: Sequence[ClosedTrade]) -> TradeMetrics:
        return cls(
            n=len(trades),
            n_wins=sum(1 for t in trades if t.pnl_eur > 0),
            n_losses=sum(1 for t in trades if t.pnl_eur <= 0),
            hit_rate=None,
            avg_win_eur=None,
            avg_loss_eur=None,
            expectancy_eur=None,
            avg_holding_days=None,
            trades_per_year=None,
            bootstrap_ci_95=None,
            insufficient_data=True,
        )


def trades_per_year(trades: Sequence[ClosedTrade]) -> float | None:
    """Closed trades per calendar year, from the first entry to the last exit."""
    if not trades:
        return None
    span = (max(t.exit_date for t in trades) - min(t.entry_date for t in trades)).days
    if span <= 0:
        return None
    return len(trades) / (span / _DAYS_PER_YEAR)

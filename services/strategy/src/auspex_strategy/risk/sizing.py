from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from auspex_backtesting.market_sim import PositionSizer, PositionTooSmallError

from auspex_strategy.models import TradeIntent
from auspex_strategy.risk.limits import RiskLimits
from auspex_strategy.runtime.book import ClosedTrade

_P_PRIOR = 0.5


@dataclass(frozen=True)
class KellyEstimates:
    """Win probability `p` and win/loss ratio `b` (mean win over mean loss, EUR) from
    `n_trades` closed trades. `b` is infinite when no trade has lost."""

    p: float
    b: float
    n_trades: int

    @classmethod
    def from_trades(cls, trades: Sequence[ClosedTrade]) -> KellyEstimates:
        if not trades:
            return cls(p=_P_PRIOR, b=1.0, n_trades=0)
        wins = [t.pnl_eur for t in trades if t.pnl_eur > 0]
        losses = [-t.pnl_eur for t in trades if t.pnl_eur <= 0]
        mean_loss = sum(losses) / len(losses) if losses else 0.0
        mean_win = sum(wins) / len(wins) if wins else 0.0
        b = mean_win / mean_loss if mean_loss > 0 else math.inf
        return cls(p=len(wins) / len(trades), b=b, n_trades=len(trades))


@dataclass(frozen=True)
class SizingResult:
    method: str  # "kelly" or "fallback"
    fraction: float  # of capital, before the per-name cap
    capital_eur: float  # after the cap
    shares: int
    estimates: KellyEstimates


class KellySizer:
    """Fractional Kelly on a shrunk win probability, capped per name.

    Only `p` is shrunk toward 0.5; `b` is used as estimated. Below `min_trades_for_kelly`
    closed trades there is no estimate worth shrinking, and the position is a fixed
    `fallback_position_pct` of capital.
    """

    def __init__(self, limits: RiskLimits, shares: PositionSizer | None = None) -> None:
        self._limits = limits
        self._shares = shares or PositionSizer()

    def kelly_fraction(self, estimates: KellyEstimates) -> float:
        """The fraction of capital before the per-name cap; zero or less means no bet."""
        if estimates.n_trades < self._limits.min_trades_for_kelly:
            return self._limits.fallback_position_pct
        p = _P_PRIOR + self._limits.kelly_shrinkage_factor * (estimates.p - _P_PRIOR)
        full = p if math.isinf(estimates.b) else (p * (estimates.b + 1) - 1) / estimates.b
        return self._limits.kelly_fraction * full

    def sizing(
        self,
        intent: TradeIntent,
        estimates: KellyEstimates,
        capital_eur: float,
        fx_rate: float,
        price_usd: float,
    ) -> SizingResult:
        fraction = self.kelly_fraction(estimates)
        if fraction <= 0:
            raise PositionTooSmallError(
                f"{intent.strategy_name}: no Kelly edge on its record (p={estimates.p:.3f}, "
                f"b={estimates.b:.3f}, n={estimates.n_trades})"
            )
        amount = min(fraction, self._limits.max_position_pct) * capital_eur
        shares = self._shares.size_shares(amount, fx_rate, price_usd)
        method = "fallback" if estimates.n_trades < self._limits.min_trades_for_kelly else "kelly"
        return SizingResult(method, fraction, amount, shares, estimates)

    def size(
        self,
        intent: TradeIntent,
        estimates: KellyEstimates,
        capital_eur: float,
        fx_rate: float,
        price_usd: float,
    ) -> int:
        """Whole shares; `fx_rate` is EUR per USD. Raises `PositionTooSmallError` at zero."""
        return self.sizing(intent, estimates, capital_eur, fx_rate, price_usd).shares

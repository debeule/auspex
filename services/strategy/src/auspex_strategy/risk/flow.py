from __future__ import annotations

from datetime import date

from auspex_strategy.risk.decision import MarketState
from auspex_strategy.risk.kill_switch import KillSwitch
from auspex_strategy.risk.limits import RiskLimits
from auspex_strategy.runtime.risk import RiskCheckRecord


class DrawdownAndFlowLimits:
    """Book-wide loss and flow limits.

    A breach of the daily loss limit blocks every intent for the rest of that trading day,
    even if P&L recovers. A drawdown past `max_drawdown_pct` from the peak book value turns
    on the global kill switch, which stays on until it is reset by hand.
    """

    def __init__(self, limits: RiskLimits, kill_switch: KillSwitch) -> None:
        self._limits = limits
        self._kill_switch = kill_switch
        self._loss_breached_on: date | None = None

    def drawdown(self, market: MarketState) -> RiskCheckRecord:
        peak = market.peak_book_value_eur
        drawdown = (peak - market.book_value_eur) / peak if peak > 0 else 0.0
        passed = drawdown <= self._limits.max_drawdown_pct
        if not passed and not self._kill_switch.is_active():
            self._kill_switch.trigger(
                f"drawdown {drawdown:.1%} exceeds MAX_DRAWDOWN_PCT "
                f"{self._limits.max_drawdown_pct:.1%}",
                triggered_by="risk:MAX_DRAWDOWN",
            )
        return RiskCheckRecord(
            "MAX_DRAWDOWN",
            {"drawdown": drawdown, "max": self._limits.max_drawdown_pct},
            passed,
        )

    def check(self, notional_eur: float, market: MarketState) -> list[RiskCheckRecord]:
        today = market.as_of.date()
        if market.day_pnl_eur < self._limits.daily_loss_limit_eur:
            self._loss_breached_on = today
        loss = RiskCheckRecord(
            "DAILY_LOSS_LIMIT",
            {"day_pnl_eur": market.day_pnl_eur, "limit": self._limits.daily_loss_limit_eur,
             "breached_on": self._loss_breached_on.isoformat() if self._loss_breached_on else None},
            self._loss_breached_on != today,
        )
        if not loss.passed:
            return [loss]
        turnover = (market.turnover_today_eur + notional_eur) / market.capital_eur
        return [loss, RiskCheckRecord(
            "DAILY_TURNOVER",
            {"turnover": turnover, "max": self._limits.daily_turnover_ceiling_pct},
            turnover <= self._limits.daily_turnover_ceiling_pct,
        )]

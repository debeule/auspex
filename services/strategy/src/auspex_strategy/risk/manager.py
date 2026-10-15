from __future__ import annotations

import math
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from auspex_backtesting.market_sim import CostModel, MarketCalendar, PositionTooSmallError

from auspex_strategy.models import TradeIntent
from auspex_strategy.risk.catalysts import BinaryEventGuard, CatalystSource, CatalystTypes
from auspex_strategy.risk.decision import (
    ApprovalDecision,
    BookState,
    ExitIntent,
    MarketState,
    signed,
)
from auspex_strategy.risk.flow import DrawdownAndFlowLimits
from auspex_strategy.risk.kill_switch import KillSwitch
from auspex_strategy.risk.limits import RiskLimits
from auspex_strategy.risk.shorts import ShortGuard, ShortInterestReader
from auspex_strategy.risk.sizing import KellyEstimates, KellySizer, SizingResult
from auspex_strategy.risk.themes import ThemeMap
from auspex_strategy.runtime.risk import RiskCheckRecord
from auspex_strategy.runtime.store import ObjectStore


class RiskManager:
    """Sizes an intent and runs it through every risk check; the first failure rejects it.

    Order: drawdown (which can turn on the global kill switch), kill switch, sizing, position
    limits, binary-event guard, short guard (shorts only), daily loss and turnover. The
    drawdown runs first so that a breach stops trading even when the intent in hand would
    have failed a later check anyway.
    """

    def __init__(
        self,
        limits: RiskLimits,
        *,
        store: ObjectStore,
        themes: ThemeMap,
        catalysts: CatalystSource,
        catalyst_types: CatalystTypes,
        costs: CostModel,
        short_interest: ShortInterestReader | None = None,
        calendar: MarketCalendar | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._limits = limits
        self._themes = themes
        self.kill_switch = KillSwitch(store, clock)
        self._sizer = KellySizer(limits)
        self._catalysts = BinaryEventGuard(
            limits, catalysts, catalyst_types, store, calendar=calendar, clock=clock
        )
        self._shorts = ShortGuard(limits, costs, short_interest)
        self._flow = DrawdownAndFlowLimits(limits, self.kill_switch)

    def evaluate(
        self, intent: TradeIntent, book: BookState, market: MarketState
    ) -> ApprovalDecision:
        checks: list[RiskCheckRecord] = []

        def rejected(sizing: SizingResult | None = None) -> ApprovalDecision:
            failed = checks[-1]
            return ApprovalDecision(False, failed.check_name, failed.inputs_snapshot,
                                    tuple(checks), sizing)

        checks.append(self._flow.drawdown(market))
        if not checks[-1].passed:
            return rejected()
        checks.append(RiskCheckRecord(
            "KILL_SWITCH",
            {"strategy_name": intent.strategy_name},
            not self.kill_switch.is_active(intent.strategy_name),
        ))
        if not checks[-1].passed:
            return rejected()

        sizing, sizing_check = self._size(intent, book, market)
        checks.append(sizing_check)
        if sizing is None:
            return rejected()

        shares = sizing.shares
        adjusted: int | None = None
        try:
            position_checks = self._position_limits(intent, shares, book, market)
        except LookupError as exc:
            checks.append(RiskCheckRecord("PRICE_UNAVAILABLE", {"error": str(exc)}, False))
            return rejected(sizing)
        for check, capped in position_checks:
            checks.append(check)
            if not check.passed:
                return rejected(sizing)
            if capped is not None and capped < shares:
                shares = adjusted = capped

        checks.append(self._catalysts.check(intent))
        if not checks[-1].passed:
            return rejected(sizing)
        if signed(intent.direction) < 0:
            for check in self._shorts.check(intent):
                checks.append(check)
                if not check.passed:
                    return rejected(sizing)
        for check in self._flow.check(market.value_eur(intent.ticker, shares), market):
            checks.append(check)
            if not check.passed:
                return rejected(sizing)
        return ApprovalDecision(True, None, {}, tuple(checks), sizing, adjusted)

    def catalyst_exits(self, book: BookState, as_of: datetime) -> list[ExitIntent]:
        return self._catalysts.exits(
            [(h.strategy_name, h.position.position_id, h.position.ticker, h.position.direction)
             for h in book.positions],
            as_of,
        )

    def short_exits(self, book: BookState, market: MarketState) -> list[ExitIntent]:
        return self._shorts.exits(book.positions, market)

    def _size(
        self, intent: TradeIntent, book: BookState, market: MarketState
    ) -> tuple[SizingResult | None, RiskCheckRecord]:
        estimates = KellyEstimates.from_trades(book.closed_trades.get(intent.strategy_name, []))
        inputs: dict[str, Any] = {
            "p": estimates.p, "b": estimates.b, "n_trades": estimates.n_trades,
            "capital_eur": market.capital_eur, "eur_per_usd": market.eur_per_usd,
        }
        price = market.prices_usd.get(intent.ticker)
        if price is None:
            return None, RiskCheckRecord("PRICE_UNAVAILABLE", inputs, False)
        inputs["price_usd"] = price
        try:
            sizing = self._sizer.sizing(
                intent, estimates, market.capital_eur, market.eur_per_usd, price
            )
        except PositionTooSmallError as exc:
            return None, RiskCheckRecord("POSITION_TOO_SMALL", {**inputs, "error": str(exc)},
                                         False)
        inputs.update(method=sizing.method, fraction=sizing.fraction, shares=sizing.shares)
        return sizing, RiskCheckRecord("SIZING", inputs, True)

    def _position_limits(
        self, intent: TradeIntent, shares: int, book: BookState, market: MarketState
    ) -> list[tuple[RiskCheckRecord, int | None]]:
        """Each limit with the share count it allows (only the per-name cap can lower it).
        The caller stops at the first failure, so later entries may be computed in vain."""
        limits = self._limits
        capital = market.capital_eur
        mine = [h for h in book.positions if h.strategy_name == intent.strategy_name]
        results: list[tuple[RiskCheckRecord, int | None]] = [(RiskCheckRecord(
            "STRATEGY_POSITION_LIMIT",
            {"open_positions": len(mine), "max": limits.max_positions_per_strategy},
            len(mine) < limits.max_positions_per_strategy,
        ), None)]

        theme = self._themes.theme(intent.ticker)
        if theme is None:
            results.append((RiskCheckRecord("THEME_UNMAPPED", {"ticker": intent.ticker}, False),
                            None))
            return results
        in_theme = [h for h in book.positions if self._themes.theme(h.position.ticker) == theme]
        results.append((RiskCheckRecord(
            "THEME_LIMIT",
            {"theme": theme, "open_positions": [
                f"{h.strategy_name}:{h.position.ticker}" for h in in_theme],
             "max": limits.max_positions_per_theme},
            len(in_theme) < limits.max_positions_per_theme,
        ), None))

        held_eur = sum(market.value_eur(h.position.ticker, h.position.shares)
                       for h in book.positions if h.position.ticker == intent.ticker)
        room_eur = limits.max_position_pct * capital - held_eur
        per_share_eur = market.value_eur(intent.ticker, 1)
        allowed = min(shares, max(0, math.floor(room_eur / per_share_eur)))
        results.append((RiskCheckRecord(
            "POSITION_LIMIT",
            {"held_eur": held_eur, "requested_shares": shares, "allowed_shares": allowed,
             "max_pct": limits.max_position_pct},
            allowed >= 1,
        ), allowed))

        new_eur = market.value_eur(intent.ticker, allowed)
        gross = (sum(market.value_eur(h.position.ticker, h.position.shares)
                     for h in book.positions) + new_eur) / capital
        results.append((RiskCheckRecord(
            "GROSS_EXPOSURE", {"gross": gross, "max": limits.max_gross_exposure},
            gross <= limits.max_gross_exposure,
        ), None))
        net = (sum(signed(h.position.direction)
                   * market.value_eur(h.position.ticker, h.position.shares)
                   for h in book.positions) + signed(intent.direction) * new_eur) / capital
        results.append((RiskCheckRecord(
            "NET_EXPOSURE", {"net": net, "max": limits.max_net_exposure},
            abs(net) <= limits.max_net_exposure,
        ), None))
        return results

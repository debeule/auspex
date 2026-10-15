from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from auspex_strategy.models import TradeIntent
from auspex_strategy.risk.decision import BookState, HeldPosition, MarketState
from auspex_strategy.risk.manager import RiskManager
from auspex_strategy.runtime.book import OpenPosition
from auspex_strategy.runtime.risk import RiskDecision

StateReader = Callable[[], tuple[BookState, MarketState]]


class PortfolioRiskReview:
    """The runtime's `review()` over `RiskManager.evaluate`.

    `state` returns the book across all strategies and the market as of now. Intents from one
    event are reviewed in order, and each approved one counts toward the exposure, theme and
    turnover the next one is checked against, as if it had already filled at the current price.
    """

    def __init__(self, manager: RiskManager, state: StateReader) -> None:
        self._manager = manager
        self._state = state

    def review(self, intents: list[TradeIntent]) -> list[RiskDecision]:
        book, market = self._state()
        decisions = []
        for intent in intents:
            approval = self._manager.evaluate(intent, book, market)
            decision = approval.to_risk_decision(intent, market)
            decisions.append(decision)
            if decision.capital_eur is None or approval.shares is None:
                continue
            book = replace(book, positions=[*book.positions, _assumed_fill(intent, approval.shares,
                                                                           market)])
            market = replace(market,
                             turnover_today_eur=market.turnover_today_eur + decision.capital_eur)
        return decisions


def _assumed_fill(intent: TradeIntent, shares: int, market: MarketState) -> HeldPosition:
    return HeldPosition(intent.strategy_name, OpenPosition(
        position_id=f"pending-{intent.intent_id}",
        order_id=f"pending-{intent.intent_id}",
        intent_id=str(intent.intent_id),
        ticker=intent.ticker,
        direction=intent.direction,
        holding_rule=intent.holding_rule,
        shares=shares,
        entry_date=market.as_of.date(),
        entry_price=market.prices_usd[intent.ticker],
    ))

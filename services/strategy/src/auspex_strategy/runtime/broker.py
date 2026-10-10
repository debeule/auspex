from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date, datetime, timedelta

from auspex_backtesting.market_sim import (
    CostModel,
    CurrencyConverter,
    FillModel,
    MarketCalendar,
    PositionSizer,
    PositionTooSmallError,
    PriceDataAbsentError,
)

from auspex_strategy.models import Direction, FixedDays, StopLossPct
from auspex_strategy.runtime.book import BookMode, OpenPosition, PendingOrder, VirtualBook
from auspex_strategy.runtime.risk import ApprovedIntent
from auspex_strategy.runtime.store import ObjectStore

log = logging.getLogger(__name__)

BinaryEventCheck = Callable[[str, date], bool]


class PaperBroker:
    """Fills approved intents into virtual books with the market simulation's prices and costs.

    An order enters at the open of the first session after its `as_of` date. Until that bar is
    in the price snapshots the order stays pending, so the live runtime never fills from a price
    it could not have had.
    """

    def __init__(
        self,
        store: ObjectStore,
        *,
        fills: FillModel,
        costs: CostModel,
        fx: CurrencyConverter,
        calendar: MarketCalendar | None = None,
        sizer: PositionSizer | None = None,
        is_binary_event: BinaryEventCheck | None = None,
    ) -> None:
        self._store = store
        self._fills = fills
        self._costs = costs
        self._fx = fx
        self._calendar = calendar or MarketCalendar()
        self._sizer = sizer or PositionSizer()
        self._is_binary_event = is_binary_event or (lambda ticker, d: False)
        self._books: dict[tuple[str, BookMode], VirtualBook] = {}

    def book(self, strategy_name: str, mode: BookMode) -> VirtualBook:
        key = (strategy_name, mode)
        if key not in self._books:
            self._books[key] = VirtualBook(self._store, strategy_name, mode)
        return self._books[key]

    def entry_date(self, as_of: datetime) -> date:
        entry: date = self._calendar.next_trading_day(as_of.date() + timedelta(days=1))
        return entry

    def submit(self, approved: ApprovedIntent, mode: BookMode) -> date:
        intent = approved.intent
        entry = self.entry_date(intent.as_of)
        self.book(intent.strategy_name, mode).place_order(intent, approved.capital_eur, entry)
        return entry

    def settle(self, through: date) -> None:
        """Fill pending orders and close positions whose exit falls on or before `through`."""
        for book in self._books.values():
            snapshot = book.snapshot()
            for order in snapshot.pending_orders:
                if order.entry_date <= through:
                    self._fill(book, order)
            for position in book.open_positions():
                self._close_if_due(book, position, through)

    def _fill(self, book: VirtualBook, order: PendingOrder) -> None:
        try:
            price = self._fills.entry_price(order.ticker, order.entry_date)
            fx_rate = self._fx.eur_per_usd(order.entry_date)
        except PriceDataAbsentError:
            log.warning("no %s bar on %s yet; order %s stays pending",
                        order.ticker, order.entry_date, order.order_id)
            return
        try:
            shares = self._sizer.size_shares(order.capital_eur, fx_rate, price)
        except PositionTooSmallError as exc:
            book.reject_order(order, str(exc))
            return
        book.open_position(order, shares, price)

    def _close_if_due(self, book: VirtualBook, position: OpenPosition, through: date) -> None:
        rule = position.holding_rule
        try:
            if isinstance(rule, FixedDays):
                exit_date = self._fills.exit_date(position.entry_date, rule.days)
                if exit_date <= through:
                    price = self._fills.exit_price(position.ticker, position.entry_date, rule.days)
                    self._close(book, position, exit_date, price, "holding_period")
            elif isinstance(rule, StopLossPct):
                self._close_on_stop(book, position, rule, through)
        except PriceDataAbsentError:
            log.warning("no %s bar to exit position %s yet", position.ticker, position.position_id)

    def _close_on_stop(
        self, book: VirtualBook, position: OpenPosition, rule: StopLossPct, through: date
    ) -> None:
        is_short = position.direction is Direction.SHORT
        move = rule.pct / 100
        stop = position.entry_price * (1 + move if is_short else 1 - move)
        for session in self._calendar.sessions_between(position.entry_date, through):
            price = self._fills.stop_exit_price(
                position.ticker,
                session,
                stop,
                is_short=is_short,
                binary_event=self._is_binary_event(position.ticker, session),
            )
            if price is not None:
                self._close(book, position, session, price, "stop_loss")
                return

    def _close(
        self, book: VirtualBook, position: OpenPosition, exit_date: date, price: float, reason: str
    ) -> None:
        costs = self._costs.round_trip_cost_usd(
            position.ticker,
            position.entry_price,
            position.shares,
            is_short=position.direction is Direction.SHORT,
            holding_calendar_days=(exit_date - position.entry_date).days,
            entry_date=position.entry_date,
        )
        book.close_position(
            position,
            exit_date=exit_date,
            exit_price=price,
            exit_reason=reason,
            costs_usd=costs,
            eur_per_usd=self._fx.eur_per_usd(exit_date),
        )

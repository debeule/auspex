from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Protocol

from auspex_backtesting.market_sim import CostModel
from auspex_backtesting.short_interest.store import SharesOutstandingByTicker, ShortInterestStore

from auspex_strategy.models import Direction, TradeIntent
from auspex_strategy.risk.decision import ExitIntent, HeldPosition, MarketState
from auspex_strategy.risk.limits import RiskLimits
from auspex_strategy.runtime.risk import RiskCheckRecord

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ShortInterestView:
    """Short interest as a percentage (0-100) of shares outstanding, and days to cover; either
    is None when the source does not know it."""

    pct_of_shares: float | None
    days_to_cover: float | None


class ShortInterestReader(Protocol):
    def view(self, ticker: str, as_of: date) -> ShortInterestView | None: ...


class StoreShortInterest:
    """FINRA short interest from `ShortInterestStore`, as published by the session before
    `as_of`: FINRA's publication time of day is not known, so the same day is not safe."""

    def __init__(
        self, store: ShortInterestStore, shares: SharesOutstandingByTicker | None
    ) -> None:
        self._store = store
        self._shares = shares

    def view(self, ticker: str, as_of: date) -> ShortInterestView | None:
        features = self._store.features(ticker, as_of - timedelta(days=1), self._shares)
        if features is None or not features.record.reported:
            return None
        return ShortInterestView(features.short_interest_pct_of_shares,
                                 features.record.days_to_cover)


class ShortGuard:
    """Entry checks for short intents and forced exits for open shorts."""

    def __init__(
        self,
        limits: RiskLimits,
        costs: CostModel,
        short_interest: ShortInterestReader | None,
    ) -> None:
        self._limits = limits
        self._costs = costs
        self._short_interest = short_interest

    def check(self, intent: TradeIntent) -> list[RiskCheckRecord]:
        """The checks run in order; the list stops at the first failure."""
        ticker = intent.ticker
        if not self._limits.shorts_enabled:
            return [RiskCheckRecord("SHORTS_DISABLED", {"ticker": ticker}, False)]
        fee = self._costs.borrow_fee_annual_pct(ticker)
        records = [RiskCheckRecord(
            "BORROW_FEE",
            {"borrow_fee_annual_pct": fee, "max": self._limits.max_borrow_fee_annual_pct},
            fee <= self._limits.max_borrow_fee_annual_pct,
        )]
        if not records[-1].passed:
            return records
        view = self._short_interest.view(ticker, intent.as_of.date()) if self._short_interest else None
        if view is None:
            log.warning("no short interest known for %s; its short-interest checks are skipped",
                        ticker)
            return records
        if view.pct_of_shares is not None:
            records.append(RiskCheckRecord(
                "SHORT_INTEREST",
                {"short_interest_pct": view.pct_of_shares,
                 "max": self._limits.max_short_interest_pct},
                view.pct_of_shares <= self._limits.max_short_interest_pct,
            ))
            if not records[-1].passed:
                return records
        if view.days_to_cover is not None:
            records.append(RiskCheckRecord(
                "DAYS_TO_COVER",
                {"days_to_cover": view.days_to_cover, "max": self._limits.max_days_to_cover},
                view.days_to_cover <= self._limits.max_days_to_cover,
            ))
        return records

    def exits(self, positions: Sequence[HeldPosition], market: MarketState) -> list[ExitIntent]:
        """Shorts past the hard stop or the EUR loss cap, closed at the next close."""
        exits = []
        for held in positions:
            p = held.position
            if p.direction is not Direction.SHORT or p.ticker not in market.prices_usd:
                continue
            price = market.prices_usd[p.ticker]
            move_pct = (price - p.entry_price) / p.entry_price * 100
            loss_eur = (price - p.entry_price) * p.shares * market.eur_per_usd
            if move_pct >= self._limits.short_hard_stop_pct:
                check, reason = "SHORT_HARD_STOP", f"price up {move_pct:.1f}% from entry"
            elif loss_eur >= self._limits.max_loss_per_short_eur:
                check, reason = "SHORT_LOSS_CAP", f"loss of EUR {loss_eur:.0f}"
            else:
                continue
            exits.append(ExitIntent(held.strategy_name, p.position_id, p.ticker,
                                    market.as_of.date(), check, reason))
        return exits

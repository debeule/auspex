from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from auspex_strategy.models import Direction
from auspex_strategy.risk.sizing import SizingResult
from auspex_strategy.runtime.book import ClosedTrade, OpenPosition


@dataclass(frozen=True)
class RiskCheckRecord:
    check_name: str
    inputs_snapshot: dict[str, Any]
    passed: bool


@dataclass(frozen=True)
class ApprovalDecision:
    """The outcome for one intent. `checks` lists every check that ran, in order; on a
    rejection the last one is the failure named by `check_name`. `adjusted_shares` is set when
    the per-name limit cut the sized position down."""

    approved: bool
    check_name: str | None
    check_inputs: dict[str, Any]
    checks: tuple[RiskCheckRecord, ...]
    sizing_result: SizingResult | None = None
    adjusted_shares: int | None = None

    @property
    def shares(self) -> int | None:
        if not self.approved or self.sizing_result is None:
            return None
        return self.adjusted_shares if self.adjusted_shares is not None else self.sizing_result.shares


@dataclass(frozen=True)
class ExitIntent:
    """A position the risk layer closes: at the close of `exit_on`."""

    strategy_name: str
    position_id: str
    ticker: str
    exit_on: date
    check_name: str
    reason: str


@dataclass(frozen=True)
class HeldPosition:
    strategy_name: str
    position: OpenPosition


@dataclass(frozen=True)
class BookState:
    """Open positions across every strategy, and each strategy's closed trades."""

    positions: list[HeldPosition] = field(default_factory=list)
    closed_trades: Mapping[str, list[ClosedTrade]] = field(default_factory=dict)


@dataclass(frozen=True)
class MarketState:
    """Prices are the latest closes available at `as_of` (USD); `eur_per_usd` converts them.
    `book_value_eur` and `peak_book_value_eur` are across all strategies; `day_pnl_eur` is
    today's realised plus unrealised P&L."""

    as_of: datetime
    capital_eur: float
    eur_per_usd: float
    prices_usd: Mapping[str, float]
    day_pnl_eur: float
    book_value_eur: float
    peak_book_value_eur: float
    turnover_today_eur: float

    def value_eur(self, ticker: str, shares: int) -> float:
        """Raises `LookupError` without a price: valuing a holding at zero would hide it."""
        if ticker not in self.prices_usd:
            raise LookupError(f"no price for {ticker}; its exposure cannot be valued")
        return shares * self.prices_usd[ticker] * self.eur_per_usd


def signed(direction: Direction) -> int:
    return 1 if direction is Direction.LONG else -1

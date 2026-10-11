import os
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import date
from typing import Any, Literal, Self, cast

from auspex_backtesting.market_sim.liquidity import SpreadEstimator


@dataclass(frozen=True)
class CostParameters:
    """Friction constants, read from the environment so a schedule change needs no code change.
    Defaults match the cost estimates in docs/strategy-research.md.

    `pricing` picks IBKR's commission schedule: `fixed` charges `ibkr_rate_per_share` with a
    `usd_min_commission` minimum per order; `tiered` charges `tiered_rate_per_share` with a
    `tiered_min_commission` minimum, plus exchange and clearing fees per share
    (`tiered_pass_through_per_share`) that the minimum does not absorb.
    `max_commission_rate` is IBKR's cap on commission as a fraction of trade value; the
    model does not apply it, so an order small enough to reach it is skipped instead.

    `spread_bps` is the flat half-spread per leg, used only when `CostModel` has no
    `SpreadEstimator`. `min_half_spread_bps` floors an estimated half-spread, since the
    estimator reads zero on quiet sessions where a real order still pays a tick.
    `fx_fee_rate` is the EUR/USD conversion fee as a fraction of notional per leg; an account
    that holds USD converts on deposit, not per trade, and pays none.
    """

    usd_min_commission: float = 1.00
    ibkr_rate_per_share: float = 0.005
    spread_bps: float = 50.0
    tob_rate: float = 0.0035
    borrow_fee_annual_pct: float = 3.0
    fx_fee_rate: float = 0.0
    min_half_spread_bps: float = 10.0
    pricing: Literal["fixed", "tiered"] = "fixed"
    tiered_rate_per_share: float = 0.0035
    tiered_min_commission: float = 0.35
    tiered_pass_through_per_share: float = 0.0032
    max_commission_rate: float = 0.01

    def __post_init__(self) -> None:
        if self.pricing not in ("fixed", "tiered"):
            raise ValueError(f"IBKR_PRICING must be fixed or tiered, not {self.pricing!r}")

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Self:
        source = os.environ if env is None else env
        defaults = cls()
        return cls(
            usd_min_commission=float(source.get("USD_MIN_COMMISSION", defaults.usd_min_commission)),
            ibkr_rate_per_share=float(source.get("IBKR_RATE_PER_SHARE", defaults.ibkr_rate_per_share)),
            spread_bps=float(source.get("SPREAD_BPS", defaults.spread_bps)),
            tob_rate=float(source.get("TOB_RATE", defaults.tob_rate)),
            borrow_fee_annual_pct=float(
                source.get("BORROW_FEE_ANNUAL_PCT", defaults.borrow_fee_annual_pct)
            ),
            fx_fee_rate=float(source.get("FX_FEE_RATE", defaults.fx_fee_rate)),
            min_half_spread_bps=float(
                source.get("MIN_HALF_SPREAD_BPS", defaults.min_half_spread_bps)
            ),
            pricing=cast(Literal["fixed", "tiered"], source.get("IBKR_PRICING", defaults.pricing)),
            tiered_rate_per_share=float(
                source.get("IBKR_TIERED_RATE_PER_SHARE", defaults.tiered_rate_per_share)
            ),
            tiered_min_commission=float(
                source.get("IBKR_TIERED_MIN_COMMISSION", defaults.tiered_min_commission)
            ),
            tiered_pass_through_per_share=float(
                source.get(
                    "IBKR_TIERED_PASS_THROUGH_PER_SHARE", defaults.tiered_pass_through_per_share
                )
            ),
            max_commission_rate=float(
                source.get("IBKR_MAX_COMMISSION_RATE", defaults.max_commission_rate)
            ),
        )

    def with_overrides(self, **changes: Any) -> Self:
        return replace(self, **changes)


class RoundTripCost(float):
    """Total friction in USD, usable as a float, with each component kept for per-trade reporting."""

    commission: float
    spread: float
    tob: float
    fx_fee: float
    borrow_fee: float

    def __new__(
        cls, commission: float, spread: float, tob: float, fx_fee: float, borrow_fee: float
    ) -> Self:
        total = super().__new__(cls, commission + spread + tob + fx_fee + borrow_fee)
        total.commission = commission
        total.spread = spread
        total.tob = tob
        total.fx_fee = fx_fee
        total.borrow_fee = borrow_fee
        return total

    def components(self) -> dict[str, float]:
        return {
            "commission": self.commission,
            "spread": self.spread,
            "tob": self.tob,
            "fx_fee": self.fx_fee,
            "borrow_fee": self.borrow_fee,
        }


class CostModel:
    """Round-trip friction for one position. Every notional-based component is charged on the
    entry notional for both legs.

    With a `SpreadEstimator` the spread is per ticker, as of the entry date; without one it is
    the flat `spread_bps`, which understates micro-cap costs and overstates large-cap ones.
    """

    def __init__(
        self,
        params: CostParameters | None = None,
        spread_estimator: SpreadEstimator | None = None,
    ) -> None:
        self._params = params or CostParameters.from_env()
        self._spread_estimator = spread_estimator

    def round_trip_cost_usd(
        self,
        ticker: str,
        price_usd: float,
        shares: int,
        is_short: bool,
        holding_calendar_days: int,
        entry_date: date | None = None,
    ) -> RoundTripCost:
        p = self._params
        notional = price_usd * shares
        commission_per_leg = self.commission_usd(shares)
        borrow_fee = (
            notional * p.borrow_fee_annual_pct / 100 * holding_calendar_days / 365
            if is_short
            else 0.0
        )
        return RoundTripCost(
            commission=commission_per_leg * 2,
            spread=notional * self._half_spread(ticker, entry_date) * 2,
            tob=notional * p.tob_rate * 2,
            fx_fee=notional * p.fx_fee_rate * 2,
            borrow_fee=borrow_fee,
        )

    def leg_cost_usd(
        self, ticker: str, price_usd: float, shares: int, trade_date: date | None = None
    ) -> RoundTripCost:
        """Friction for one order, a buy or a sell, of `shares` at `price_usd`. No borrow fee."""
        p = self._params
        notional = price_usd * abs(shares)
        return RoundTripCost(
            commission=self.commission_usd(abs(shares)),
            spread=notional * self._half_spread(ticker, trade_date),
            tob=notional * p.tob_rate,
            fx_fee=notional * p.fx_fee_rate,
            borrow_fee=0.0,
        )

    def commission_usd(self, shares: int) -> float:
        """One order's commission under the configured IBKR schedule."""
        p = self._params
        if p.pricing == "tiered":
            return (
                max(p.tiered_min_commission, p.tiered_rate_per_share * shares)
                + p.tiered_pass_through_per_share * shares
            )
        return max(p.usd_min_commission, p.ibkr_rate_per_share * shares)

    def min_ticket_usd(self) -> float:
        """Smallest order value whose minimum commission stays within IBKR's commission cap."""
        p = self._params
        minimum = p.tiered_min_commission if p.pricing == "tiered" else p.usd_min_commission
        return minimum / p.max_commission_rate

    def _half_spread(self, ticker: str, entry_date: date | None) -> float:
        p = self._params
        if self._spread_estimator is None:
            return p.spread_bps / 10_000
        if entry_date is None:
            raise ValueError("entry_date is required to estimate a per-ticker spread")
        estimated = self._spread_estimator.half_spread(ticker, as_of=entry_date)
        return max(estimated, p.min_half_spread_bps / 10_000)

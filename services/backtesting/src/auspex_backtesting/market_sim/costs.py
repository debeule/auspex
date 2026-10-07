import os
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import date
from typing import Self

from auspex_backtesting.market_sim.liquidity import SpreadEstimator


@dataclass(frozen=True)
class CostParameters:
    """Friction constants, read from the environment so a schedule change needs no code change.
    Defaults match the cost estimates in docs/strategy-research.md.

    `spread_bps` is the flat half-spread per leg, used only when `CostModel` has no
    `SpreadEstimator`. `min_half_spread_bps` floors an estimated half-spread, since the
    estimator reads zero on quiet sessions where a real order still pays a tick.
    `fx_fee_rate` is IBKR's EUR/USD conversion fee as a fraction of notional per leg.
    """

    usd_min_commission: float = 1.00
    ibkr_rate_per_share: float = 0.005
    spread_bps: float = 50.0
    tob_rate: float = 0.0035
    borrow_fee_annual_pct: float = 3.0
    fx_fee_rate: float = 0.0003
    min_half_spread_bps: float = 2.0

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
        )

    def with_overrides(self, **changes: float) -> Self:
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
        commission_per_leg = max(p.usd_min_commission, p.ibkr_rate_per_share * shares)
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

    def _half_spread(self, ticker: str, entry_date: date | None) -> float:
        p = self._params
        if self._spread_estimator is None:
            return p.spread_bps / 10_000
        if entry_date is None:
            raise ValueError("entry_date is required to estimate a per-ticker spread")
        estimated = self._spread_estimator.half_spread(ticker, as_of=entry_date)
        return max(estimated, p.min_half_spread_bps / 10_000)

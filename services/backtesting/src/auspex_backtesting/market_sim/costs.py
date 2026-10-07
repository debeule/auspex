import os
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Self


@dataclass(frozen=True)
class CostParameters:
    """Friction constants, read from the environment so a schedule change needs no code change.
    Defaults match the cost estimates in docs/strategy-research.md."""

    usd_min_commission: float = 1.00
    ibkr_rate_per_share: float = 0.005
    spread_bps: float = 50.0
    tob_rate: float = 0.0035
    borrow_fee_annual_pct: float = 3.0

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
        )

    def with_overrides(self, **changes: float) -> Self:
        return replace(self, **changes)


class RoundTripCost(float):
    """Total friction in USD, usable as a float, with each component kept for debugging."""

    commission: float
    spread: float
    tob: float
    borrow_fee: float

    def __new__(cls, commission: float, spread: float, tob: float, borrow_fee: float) -> Self:
        total = super().__new__(cls, commission + spread + tob + borrow_fee)
        total.commission = commission
        total.spread = spread
        total.tob = tob
        total.borrow_fee = borrow_fee
        return total


class CostModel:
    def __init__(self, params: CostParameters | None = None) -> None:
        self._params = params or CostParameters.from_env()

    def round_trip_cost_usd(
        self,
        ticker: str,
        price_usd: float,
        shares: int,
        is_short: bool,
        holding_calendar_days: int,
    ) -> RoundTripCost:
        # `ticker` is unused until spread is set per ticker; micro-caps run well past 50 bps.
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
            spread=notional * p.spread_bps / 10_000 * 2,
            tob=notional * p.tob_rate * 2,
            borrow_fee=borrow_fee,
        )

from collections.abc import Mapping
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from auspex_backtesting.market_sim import CostModel

from auspex_strategy.models import Direction, FixedDays, IntentRationale, TradeIntent
from auspex_strategy.risk import (
    CatalystSource,
    HeldPosition,
    KnownCatalyst,
    MarketState,
    RiskLimits,
    RiskManager,
    ShortInterestReader,
    ThemeMap,
)
from auspex_strategy.runtime import ClosedTrade, ObjectStore, OpenPosition
from auspex_strategy.testing import InMemoryObjectStore, StaticCatalysts

from .runtime_fakes import COST_PARAMS

# tests/unit/ -> tests/ -> strategy/ -> services/ -> auspex/
REPO_ROOT = Path(__file__).resolve().parents[4]

# Monday 2026-03-09, during the session.
AS_OF = datetime(2026, 3, 9, 14, 0, tzinfo=UTC)

_LIMITS: dict[str, float] = {
    "KELLY_SHRINKAGE_FACTOR": 0.5,
    "KELLY_FRACTION": 0.25,
    "MIN_TRADES_FOR_KELLY": 20,
    "FALLBACK_POSITION_PCT": 0.01,
    "MAX_POSITION_PCT": 0.03,
    "MAX_GROSS_EXPOSURE": 1.0,
    "MAX_NET_EXPOSURE": 1.0,
    "MAX_POSITIONS_PER_STRATEGY": 10,
    "MAX_POSITIONS_PER_THEME": 1,
    "CATALYST_GUARD_DAYS": 3,
    "MAX_BORROW_FEE_ANNUAL_PCT": 10.0,
    "MAX_SHORT_INTEREST_PCT": 20.0,
    "MAX_DAYS_TO_COVER": 5.0,
    "SHORT_HARD_STOP_PCT": 15.0,
    "MAX_LOSS_PER_SHORT_EUR": 2_000.0,
    "DAILY_LOSS_LIMIT_EUR": -5_000.0,
    "MAX_DRAWDOWN_PCT": 0.2,
    "DAILY_TURNOVER_CEILING_PCT": 0.5,
}

THEMES = ThemeMap({"SRPT": "genetic_medicine", "BEAM": "genetic_medicine", "OTHR": "other"})


def limits(*, shorts_enabled: bool = False, **overrides: float) -> RiskLimits:
    values = {**_LIMITS, **overrides}
    return RiskLimits(
        **{name.lower(): value for name, value in values.items()},  # type: ignore[arg-type]
        shorts_enabled=shorts_enabled,
    )


def limits_env(**overrides: str) -> dict[str, str]:
    return {**{name: str(value) for name, value in _LIMITS.items()}, **overrides}


def intent(
    ticker: str,
    *,
    strategy: str = "strategy_a",
    direction: Direction = Direction.LONG,
    as_of: datetime = AS_OF,
) -> TradeIntent:
    return TradeIntent(
        ticker=ticker,
        direction=direction,
        conviction=0.5,
        holding_rule=FixedDays(20),
        exit_conditions=(),
        rationale=IntentRationale(
            corroboration_id="c-1",
            entity_key="entity-1",
            as_of=as_of,
            source_types=frozenset({"biorxiv", "clinicaltrials"}),
            directionality="positive",
            confidence_scores=(0.9,),
        ),
        strategy_name=strategy,
        strategy_version="1.0",
        hypothesis_id="h1",
        as_of=as_of,
    )


def held(
    strategy: str,
    ticker: str,
    *,
    shares: int,
    direction: Direction = Direction.LONG,
    entry_price: float = 25.0,
) -> HeldPosition:
    return HeldPosition(
        strategy_name=strategy,
        position=OpenPosition(
            position_id=f"{strategy}-{ticker}",
            order_id=f"order-{strategy}-{ticker}",
            intent_id=f"intent-{strategy}-{ticker}",
            ticker=ticker,
            direction=direction,
            holding_rule=FixedDays(20),
            shares=shares,
            entry_date=date(2026, 3, 2),
            entry_price=entry_price,
        ),
    )


def market(
    *,
    prices: Mapping[str, float] | None = None,
    capital_eur: float = 100_000.0,
    eur_per_usd: float = 0.8,
    day_pnl_eur: float = 0.0,
    book_value_eur: float = 100_000.0,
    peak_book_value_eur: float = 100_000.0,
    turnover_today_eur: float = 0.0,
    as_of: datetime = AS_OF,
) -> MarketState:
    return MarketState(
        as_of=as_of,
        capital_eur=capital_eur,
        eur_per_usd=eur_per_usd,
        prices_usd=dict(prices or {"SRPT": 25.0, "BEAM": 25.0, "OTHR": 25.0}),
        day_pnl_eur=day_pnl_eur,
        book_value_eur=book_value_eur,
        peak_book_value_eur=peak_book_value_eur,
        turnover_today_eur=turnover_today_eur,
    )


def manager(
    *,
    limits: RiskLimits | None = None,
    store: ObjectStore | None = None,
    catalysts: CatalystSource | None = None,
    catalyst_types: Mapping[str, frozenset[str]] | None = None,
    costs: CostModel | None = None,
    short_interest: ShortInterestReader | None = None,
) -> RiskManager:
    declared = dict(catalyst_types or {})
    return RiskManager(
        limits if limits is not None else globals()["limits"](),
        store=store if store is not None else InMemoryObjectStore(),
        themes=THEMES,
        catalysts=catalysts if catalysts is not None else StaticCatalysts([]),
        catalyst_types=lambda name: declared.get(name, frozenset()),
        costs=costs if costs is not None else CostModel(COST_PARAMS),
        short_interest=short_interest,
        clock=lambda: AS_OF,
    )


def known_catalyst(
    ticker: str, catalyst_type: str, on: date, *, known_at: datetime | None = None, **extra: Any
) -> KnownCatalyst:
    return KnownCatalyst(
        ticker=ticker,
        catalyst_type=catalyst_type,
        period_start=on,
        period_end=extra.get("period_end", on),
        known_at=known_at if known_at is not None else AS_OF - timedelta(days=1),
    )


def closed_trades(*, wins: int, losses: int, win_eur: float = 200.0,
                  loss_eur: float = 100.0) -> list[ClosedTrade]:
    trades = []
    for i, pnl in enumerate([win_eur] * wins + [-loss_eur] * losses):
        trades.append(ClosedTrade(
            position_id=f"p{i}",
            ticker="SRPT",
            direction=Direction.LONG,
            shares=10,
            entry_date=date(2025, 1, 2),
            entry_price=25.0,
            exit_date=date(2025, 2, 3),
            exit_price=25.0 + pnl / 10 / 0.8,
            exit_reason="holding_period",
            costs_usd=0.0,
            pnl_usd=pnl / 0.8,
            pnl_eur=pnl,
        ))
    return trades

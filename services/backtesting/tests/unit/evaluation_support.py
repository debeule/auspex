"""Price, ledger, config and result fixtures shared by the evaluation tests."""

from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from auspex_backtesting.evaluation import (
    AbnormalReturnSeries,
    CellResult,
    EvaluationResult,
    TradeCosts,
    TrialLedger,
)
from auspex_backtesting.hypothesis import register_hypothesis
from auspex_backtesting.market_sim import (
    CostModel,
    CostParameters,
    CurrencyConverter,
    MarketCalendar,
)
from auspex_backtesting.protocol import EvaluationProtocol

CONFIG_DIR = Path(__file__).resolve().parents[4] / "config" / "hypotheses"
PROTOCOL: dict[str, Any] = yaml.safe_load(
    (CONFIG_DIR / "protocol.yaml").read_text(encoding="utf-8")
)
CALENDAR = MarketCalendar()
SESSIONS = CALENDAR.sessions_between(date(2022, 1, 3), date(2024, 12, 31))

FLAT_COSTS = CostParameters(
    usd_min_commission=1.00,
    ibkr_rate_per_share=0.005,
    spread_bps=50.0,
    tob_rate=0.0035,
    borrow_fee_annual_pct=3.0,
    fx_fee_rate=0.0003,
    min_half_spread_bps=2.0,
)

TEST_HYPOTHESIS = """\
id: h1
version: 1
description: "Test event hypothesis on the full declared grid"
role: promotable
signal_definition:
  variant: entity-only
  filter: none
  join_field: corroborated_at
entry_timing_days: 1
holding_period_days: [5, 10, 20, 30]
variants: [entity-only, full]
known_at_delay_days: [0, 1, 3, 5]
primary_cell:
  holding_period_days: 20
  known_at_delay_days: 1
  variant: entity-only
trial_cells: 32
benchmark: XBI
exit: fixed_horizon_close
direction: long
status: pre-registered
registered_at: "2026-10-07T00:00:00Z"
"""


class Prices:
    """Stands in for `PriceSnapshotStore`: ticker -> stored OHLCV frame, None when absent."""

    def __init__(self, frames: dict[str, pd.DataFrame]) -> None:
        self.frames = frames

    def load(self, ticker: str) -> pd.DataFrame | None:
        return self.frames.get(ticker)


def price_frame(sessions: list[date], closes: np.ndarray) -> pd.DataFrame:
    idx = pd.DatetimeIndex([pd.Timestamp(d) for d in sessions], tz="UTC", name="date")
    closes = np.asarray(closes, dtype=float)
    return pd.DataFrame(
        {
            "open": closes,
            "high": closes,
            "low": closes,
            "close": closes,
            "volume": 1_000_000.0,
        },
        index=idx,
    )


def bouncing_before(
    frame: pd.DataFrame, entry_index: int, bid: float, ask: float, sessions: int = 25
) -> pd.DataFrame:
    """Closes alternating between bid and ask over a [bid, ask] range in the sessions before
    entry, so the spread estimate there is ln(ask / bid). Those sessions sit in the gap between
    the estimation window and the event, so the market model is unaffected."""
    frame = frame.copy()
    for k, row in enumerate(range(entry_index - sessions, entry_index)):
        frame.iloc[row, frame.columns.get_indexer(["open", "high", "low", "close"])] = [
            ask if k % 2 == 0 else bid,
            ask,
            bid,
            ask if k % 2 == 0 else bid,
        ]
    return frame


def closes_from(returns: np.ndarray, start: float = 100.0) -> np.ndarray:
    return start * np.cumprod(1 + np.asarray(returns, dtype=float))


def market_returns(n: int, seed: int = 7) -> np.ndarray:
    return np.random.default_rng(seed).normal(0.0005, 0.015, n)


def event_frame(rows: list[tuple[str, date]], column: str = "entry_date") -> pd.DataFrame:
    return pd.DataFrame({"ticker": [t for t, _ in rows], column: [d for _, d in rows]})


def return_series(
    values: list[float],
    tickers: list[str],
    entry_dates: list[date],
    holding_calendar_days: int = 28,
) -> AbnormalReturnSeries:
    n = len(values)
    return AbnormalReturnSeries(
        values=tuple(values),
        tickers=tuple(tickers),
        entry_dates=tuple(entry_dates),
        window_starts=tuple(entry_dates),
        window_ends=tuple(d + timedelta(days=holding_calendar_days) for d in entry_dates),
        alphas=(0.0,) * n,
        betas=(1.0,) * n,
        fallback=(False,) * n,
        direction=1,
    )


LEDGER_HYPOTHESES = {
    "h1": {"id": "h1", "role": "promotable"},
    "h4": {"id": "h4", "role": "promotable"},
    "h3": {"id": "h3", "role": "diagnostic"},
}


def ledger_cells(n: int, variant: str = "entity-only") -> list[dict[str, Any]]:
    return [
        {"holding_period_days": 5 + i, "known_at_delay_days": 1, "variant": variant}
        for i in range(n)
    ]


def trial_ledger(trials_dir: Path) -> TrialLedger:
    return TrialLedger(trials_dir, PROTOCOL, LEDGER_HYPOTHESES)


def registered_config(tmp_path: Path, hypothesis_yaml: str = TEST_HYPOTHESIS) -> tuple[Path, Path]:
    config_dir = tmp_path / "hypotheses"
    config_dir.mkdir()
    registry = config_dir / "registry.jsonl"
    registry.write_text("", encoding="utf-8")
    register_hypothesis(
        "protocol",
        (CONFIG_DIR / "protocol.yaml").read_text(encoding="utf-8"),
        config_dir=config_dir,
        registry_path=registry,
    )
    register_hypothesis("h1", hypothesis_yaml, config_dir=config_dir, registry_path=registry)
    return config_dir, registry


def evaluation_protocol(
    config_dir: Path, registry: Path, prices: Any, cost_model: CostModel | None = None
) -> EvaluationProtocol:
    costs = TradeCosts(
        cost_model or CostModel(FLAT_COSTS),
        CurrencyConverter(prices),
        position_eur=10_000.0,
    )
    return EvaluationProtocol(
        config_dir=config_dir,
        registry_path=registry,
        prices=prices,
        costs=costs,
        calendar=CALENDAR,
    )


def run_fixture() -> tuple[Prices, pd.DataFrame, date]:
    """One in-sample SRPT event whose 20-day window gains 10% over XBI on its first day, and
    one later event that falls in the holdout. Prices: XBI, SRPT, EURUSD=X at 1.25."""
    r_m = market_returns(len(SESSIONS))
    corroborated = date(2023, 6, 1)
    entry = CALENDAR.next_trading_day(corroborated + timedelta(days=1))
    i0 = SESSIONS.index(entry)
    r_i = r_m.copy()
    r_i[i0 + 1] += 0.10
    srpt = closes_from(r_i)
    srpt = srpt * 10.0 / srpt[i0]
    prices = Prices(
        {
            "XBI": price_frame(SESSIONS, closes_from(r_m)),
            "SRPT": price_frame(SESSIONS, srpt),
            "EURUSD=X": price_frame(SESSIONS, np.full(len(SESSIONS), 1.25)),
        }
    )
    events = event_frame([("SRPT", corroborated), ("SRPT", date(2024, 6, 3))], "corroborated_at")
    return prices, events, entry


def evaluation_result(**overrides: Any) -> EvaluationResult:
    fields: dict[str, Any] = {
        "hypothesis_id": "h1",
        "role": "promotable",
        "variant": "entity-only",
        "holding_period_days": 20,
        "n_events": 120,
        "n_independent_events": 80,
        "known_at_delay_days": 1,
        "mean_abnormal_return": 0.03,
        "t_stat": 3.4,
        "p_value": 0.001,
        "inference_method": "wild_cluster_bootstrap",
        "n_estimation_fallback": 0,
        "deflated_sharpe": 0.97,
        "n_trials": 32,
        "is_primary_cell": True,
        "bootstrap_ci_95": (0.01, 0.05),
        "hit_rate": 0.6,
        "net_expectancy_eur": 120.0,
        "kill_verdicts": (),
        "walk_forward_segments": (),
        "walk_forward_note": None,
        "holdout_sealed": True,
        "n_holdout_events": 10,
        "run_id": "run",
        "trades": (),
        "cells": (),
    }
    fields.update(overrides)
    return EvaluationResult(**fields)


def cell_result(
    window: tuple[int, int],
    mean: float,
    *,
    holding: int | None = None,
    delay: int = 1,
    variant: str = "entity-only",
    net_mean: float | None = None,
    net_t: float = 0.0,
    cost_fraction: float = 0.01,
) -> CellResult:
    return CellResult(
        holding_period_days=holding,
        window=window,
        known_at_delay_days=delay,
        variant=variant,
        n_events=50,
        n_independent_events=40,
        mean_abnormal_return=mean,
        t_stat=net_t,
        p_value=0.5,
        inference_method="wild_cluster_bootstrap",
        n_estimation_fallback=0,
        hit_rate=0.5,
        mean_net_abnormal_return=mean if net_mean is None else net_mean,
        net_t_stat=net_t,
        median_cost_fraction=cost_fraction,
        deflated_sharpe=0.5,
        bootstrap_ci_95=(0.0, 0.0),
        net_expectancy_eur=0.0,
        trades=(),
    )


KILL_HYPOTHESES = {
    "h3": yaml.safe_load((CONFIG_DIR / "h3.yaml").read_text(encoding="utf-8")),
    "h1": yaml.safe_load(TEST_HYPOTHESIS),
}


def verdict_for(verdicts: list[Any], criterion_id: str) -> Any:
    (verdict,) = [v for v in verdicts if v.criterion_id == criterion_id]
    return verdict


def monthly_events(first: date, months: int) -> pd.DataFrame:
    dates = [
        (pd.Timestamp(first) + pd.DateOffset(months=m, days=d)).date()
        for m in range(months)
        for d in (0, 10, 20)
    ]
    return event_frame([("SRPT", d) for d in dates], "corroborated_at")

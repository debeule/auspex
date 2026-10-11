"""Synthetic universes, prices, scores and catalysts for the portfolio backtest tests."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from auspex_backtesting.hypothesis import register_hypothesis
from auspex_backtesting.market_sim import CostModel, CostParameters, MarketCalendar
from auspex_backtesting.portfolio import (
    EqualRiskSizer,
    PortfolioBacktest,
    PortfolioRule,
    ScoreRef,
    ScoreSnapshot,
)
from auspex_backtesting.protocol import EvaluationProtocol
from auspex_backtesting.universe.model import UniverseMember, UniverseSnapshot

CONFIG_DIR = Path(__file__).resolve().parents[4] / "config" / "hypotheses"
PROTOCOL_YAML = (CONFIG_DIR / "protocol.yaml").read_text(encoding="utf-8")
CALENDAR = MarketCalendar()
HISTORY_START = date(2019, 6, 3)
RUN_START = date(2020, 1, 1)
RUN_END = date(2021, 12, 31)
SESSIONS = CALENDAR.sessions_between(HISTORY_START, date(2023, 3, 31))
SCORE = ScoreRef("h9", "test")
FILTER = ScoreRef("h10", "test")
# A wide zigzag gives every name the same daily volatility without drift.
ZIGZAG = 0.01

COSTS = CostParameters(
    usd_min_commission=1.00,
    ibkr_rate_per_share=0.005,
    spread_bps=10.0,
    tob_rate=0.0035,
    borrow_fee_annual_pct=3.0,
    fx_fee_rate=0.0,
    min_half_spread_bps=10.0,
)


def cik(i: int) -> str:
    return f"{i + 1:010d}"


def ticker(i: int) -> str:
    return f"T{i:03d}"


def first_sessions(start: date, end: date) -> list[date]:
    return [
        CALENDAR.next_trading_day(m.date())
        for m in pd.date_range(date(start.year, start.month, 1), end, freq="MS")
    ]


def next_session(d: date) -> date:
    return CALENDAR.next_trading_day(d + timedelta(days=1))


def frame_from_log_returns(
    sessions: Sequence[date], log_returns: Sequence[float], start: float = 20.0
) -> pd.DataFrame:
    """Opens at the previous close, so a position held open to open earns the close-to-close
    returns of the sessions in between."""
    closes = start * np.exp(np.cumsum(log_returns))
    opens = np.concatenate([[start], closes[:-1]])
    idx = pd.DatetimeIndex([pd.Timestamp(d) for d in sessions], tz="UTC", name="date")
    return pd.DataFrame(
        {
            "open": opens,
            "high": np.maximum(opens, closes),
            "low": np.minimum(opens, closes),
            "close": closes,
            "volume": 1_000_000.0,
        },
        index=idx,
    )


def zigzag(n: int, phase: int = 0, size: float = ZIGZAG) -> np.ndarray:
    return np.array([size if (k + phase) % 2 == 0 else -size for k in range(n)])


class Prices:
    def __init__(self, frames: dict[str, pd.DataFrame]) -> None:
        self.frames = frames

    def load(self, ticker: str) -> pd.DataFrame | None:
        return self.frames.get(ticker)


class Universe:
    def __init__(self, members: Sequence[UniverseMember], months: Sequence[str]) -> None:
        self.members = list(members)
        self.months = list(months)
        self.excluded: dict[str, set[str]] = {}

    def read(self, rules_version: int, month: str) -> UniverseSnapshot | None:
        if month not in self.months:
            return None
        drop = self.excluded.get(month, set())
        members = tuple(m for m in self.members if m.cik not in drop)
        rebalance = CALENDAR.next_trading_day(date.fromisoformat(f"{month}-01"))
        return UniverseSnapshot(rules_version, month, rebalance, members)

    def read_listings(self, rules_version: int) -> tuple[list[UniverseMember], date]:
        return self.members, date(2023, 3, 31)


class Scores:
    """Score snapshots by (hypothesis id, version) and date."""

    def __init__(self) -> None:
        self.snapshots: dict[tuple[str, str], dict[date, pd.DataFrame]] = {}

    def put(
        self, ref: ScoreRef, d: date, scores: Mapping[str, float], known_at: datetime | None = None
    ) -> None:
        known = known_at or CALENDAR.session_open(d) - timedelta(hours=12)
        self.snapshots.setdefault((ref.hypothesis_id, ref.version), {})[d] = pd.DataFrame(
            {
                "cik": list(scores),
                "ticker": [ticker(int(c) - 1) for c in scores],
                "score": [float(v) for v in scores.values()],
                "known_at_max": [pd.Timestamp(known)] * len(scores),
            }
        )

    def dates(self, hypothesis_id: str, version: str) -> list[date]:
        return sorted(self.snapshots.get((hypothesis_id, version), {}))

    def read(self, hypothesis_id: str, version: str, rebalance_date: date) -> ScoreSnapshot | None:
        rows = self.snapshots.get((hypothesis_id, version), {}).get(rebalance_date)
        return None if rows is None else ScoreSnapshot(hypothesis_id, version, rebalance_date, rows)


@dataclass(frozen=True)
class Binary:
    cik: str
    period_start: date
    period_end: date
    known_at: datetime
    precision: str = "day"


class Catalysts:
    def __init__(self, rows: Sequence[Binary] = ()) -> None:
        self.rows = list(rows)

    def binaries_between(self, cik: str, start: date, end: date, as_of: datetime) -> list[Binary]:
        return [
            r
            for r in self.rows
            if r.cik == cik
            and r.known_at <= as_of
            and r.period_start <= end
            and r.period_end >= start
        ]


def member(
    i: int,
    *,
    exited_on: date | None = None,
    exit_reason: str | None = None,
    coverage: str = "complete",
) -> UniverseMember:
    return UniverseMember(
        cik=cik(i),
        ticker=ticker(i),
        ticker_source="current",
        name=f"Company {i}",
        sic="2836",
        exchange="Nasdaq",
        market_cap_usd=1e9,
        median_dollar_volume_20d=5e6,
        entered_on=date(2015, 1, 2),
        exited_on=exited_on,
        exit_reason=exit_reason,  # type: ignore[arg-type]
        price_coverage=coverage,  # type: ignore[arg-type]
        coverage_note="",
    )


@dataclass
class World:
    n: int
    prices: Prices
    universe: Universe
    scores: Scores
    catalysts: Catalysts = field(default_factory=Catalysts)

    def engine(
        self,
        costs: CostParameters = COSTS,
        *,
        max_weight: float = 0.05,
        min_names: int = 15,
        catalysts: bool = True,
    ) -> PortfolioBacktest:
        return PortfolioBacktest(
            prices=self.prices,  # type: ignore[arg-type]
            universe=self.universe,
            scores=self.scores,
            cost_model=CostModel(costs),
            sizer=EqualRiskSizer(max_weight, min_names),
            catalysts=self.catalysts if catalysts else None,
            calendar=CALENDAR,
        )

    def set_returns(self, i: int, log_returns: np.ndarray) -> None:
        self.prices.frames[ticker(i)] = frame_from_log_returns(SESSIONS, log_returns)


def world(n: int, *, score_fn: Callable[[int, date], float] | None = None, seed: int = 1) -> World:
    """`n` names with equal zigzag volatility and no drift, monthly scores from `score_fn`
    (random when absent), XBI and a flat EURUSD rate of 1.25."""
    rng = np.random.default_rng(seed)
    frames = {
        ticker(i): frame_from_log_returns(SESSIONS, zigzag(len(SESSIONS), i)) for i in range(n)
    }
    frames["XBI"] = frame_from_log_returns(SESSIONS, zigzag(len(SESSIONS), 0, 0.005), 80.0)
    frames["EURUSD=X"] = frame_from_log_returns(SESSIONS, np.zeros(len(SESSIONS)), 1.25)
    months = sorted({d.strftime("%Y-%m") for d in SESSIONS})
    scores = Scores()
    for d in first_sessions(HISTORY_START, SESSIONS[-1]):
        values = {cik(i): (score_fn(i, d) if score_fn else float(rng.random())) for i in range(n)}
        scores.put(SCORE, d, values)
    return World(n, Prices(frames), Universe([member(i) for i in range(n)], months), scores)


def plant_top_quintile_edge(w: World, monthly: float, start: date, end: date) -> None:
    """Names in each decision's top score quintile earn `monthly` from that decision's fill
    open to the next fill open; the zigzag of every name is kept."""
    logs = {i: np.log(w.prices.frames[ticker(i)]["close"].to_numpy() / 20.0) for i in range(w.n)}
    returns = {i: np.diff(np.concatenate([[0.0], logs[i]])) for i in range(w.n)}
    decisions = first_sessions(start, end)
    fills = [next_session(d) for d in decisions]
    for k, d in enumerate(decisions):
        rows = w.scores.read(SCORE.hypothesis_id, SCORE.version, d)
        assert rows is not None
        ranked = rows.rows.sort_values(["score", "cik"], ascending=[False, True])["cik"].tolist()
        top = ranked[: w.n // 5]
        lo = SESSIONS.index(fills[k])
        hi = (
            SESSIONS.index(fills[k + 1])
            if k + 1 < len(fills)
            else SESSIONS.index(next_session(end))
        )
        for c in top:
            i = int(c) - 1
            returns[i][lo:hi] += math.log(1 + monthly) / (hi - lo)
    for i, r in returns.items():
        w.set_returns(i, r)


def monthly_rule(**overrides: Any) -> PortfolioRule:
    return replace(PortfolioRule(score=SCORE), **overrides)


def h9_quarterly_rule(**overrides: Any) -> PortfolioRule:
    h9 = yaml.safe_load((CONFIG_DIR / "h9.yaml").read_text(encoding="utf-8"))
    rule = PortfolioRule.from_hypothesis(h9, dict(h9["primary_cell"]), SCORE)
    return replace(rule, **overrides)


PORTFOLIO_HYPOTHESIS = """\
id: h9
version: 1
description: "Test portfolio hypothesis"
evaluation: portfolio
family: holdings_panel
role: promotable
direction: long
score: rank_mean
benchmarks:
  abnormal_return: XBI
  excess: universe_equal_weight
trial_grid:
  cadence: [monthly_top15, quarterly_bands_15_30]
  catalyst_guard: [none, skip_entry]
primary_cell:
  cadence: monthly_top15
  catalyst_guard: none
trial_cells: 4
in_sample_years: [2020, 2021]
holdout_years: [2022, 2022]
status: pre-registered
registered_at: "2026-10-09T00:00:00Z"
"""

FILTER_HYPOTHESIS = """\
id: h10
version: 1
description: "Test filter hypothesis"
evaluation: portfolio
direction: long
uses:
  - id: biotech_exclusion_filter
    role: filter
    family: holdings_panel
    host: h9
    trial_grid:
      filter: [on, off]
    trial_cells: 2
    in_sample_years: [2020, 2021]
    holdout_years: [2022, 2022]
status: pre-registered
registered_at: "2026-10-09T00:00:00Z"
"""


def registered_config(
    tmp_path: Path, protocol_yaml: str = PROTOCOL_YAML, *, with_filter: bool = False
) -> tuple[Path, Path]:
    config_dir = tmp_path / "hypotheses"
    config_dir.mkdir()
    registry = config_dir / "registry.jsonl"
    registry.write_text("", encoding="utf-8")
    register_hypothesis("protocol", protocol_yaml, config_dir=config_dir, registry_path=registry)
    register_hypothesis("h9", PORTFOLIO_HYPOTHESIS, config_dir=config_dir, registry_path=registry)
    if with_filter:
        register_hypothesis("h10", FILTER_HYPOTHESIS, config_dir=config_dir, registry_path=registry)
    return config_dir, registry


def evaluation_protocol(config_dir: Path, registry: Path) -> EvaluationProtocol:
    return EvaluationProtocol(config_dir=config_dir, registry_path=registry, calendar=CALENDAR)


def utc(d: date, hour: int = 0) -> datetime:
    return datetime(d.year, d.month, d.day, hour, tzinfo=UTC)

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
from auspex_backtesting.evaluation import DeflatedSharpe

from auspex_strategy.metrics import (
    BacktestPaperComparison,
    CorrelationMatrix,
    InsufficientTradeDataError,
    MetricsApi,
    ReturnMetrics,
    TradeMetrics,
    version_trades,
)
from auspex_strategy.models import Direction
from auspex_strategy.runtime import BookMode

from .metrics_fakes import ToyMarket, minio_store, registry, write_trials

# Net abnormal return of each toy trade: the step in its close (the benchmark is flat), in the
# trade's direction, less its round-trip costs over the entry notional of 100 x 100 USD.
_TOY_TRADES = [
    # ticker, direction, exit price, costs USD
    ("AAA", Direction.LONG, 110.0, 20.0),   # +0.10 - 0.002 = +0.098, P&L +980 USD
    ("BBB", Direction.LONG, 95.0, 20.0),    # -0.05 - 0.002 = -0.052, P&L -520 USD
    ("CCC", Direction.LONG, 104.0, 20.0),   # +0.04 - 0.002 = +0.038, P&L +380 USD
    ("DDD", Direction.SHORT, 90.0, 30.0),   # +0.10 - 0.003 = +0.097, P&L +970 USD
    ("EEE", Direction.LONG, 99.0, 20.0),    # -0.01 - 0.002 = -0.012, P&L -120 USD
]


def _toy_market(strategy: str = "toy", version: str = "1.0") -> ToyMarket:
    market = ToyMarket()
    for ticker, direction, exit_price, costs in _TOY_TRADES:
        market.trade(
            strategy, version, BookMode.BACKTEST,
            ticker=ticker, direction=direction, exit_price=exit_price, costs_usd=costs,
        )
    return market


def _many_trades(market: ToyMarket, strategy: str, version: str, mode: BookMode, n: int,
                 seed: int = 7) -> None:
    rng = np.random.default_rng(seed)
    for i in range(n):
        market.trade(
            strategy, version, mode,
            ticker=f"{strategy[:3].upper()}{version.replace('.', '')}{mode.value[:2]}{i}",
            exit_price=float(round(100 + rng.normal(2.0, 6.0), 2)),
            entry=date(2026, 3, 2) + timedelta(weeks=i % 20),
        )


def test_metrics_reproduce_hand_computed_on_toy_trade_set(tmp_path: Path) -> None:
    market = _toy_market()
    service = market.service(registry(("toy", "1.0", "h1", "paper")), tmp_path / "trials",
                             min_trades=5)

    summary = service.summary("toy", "1.0", BookMode.BACKTEST)

    trades = summary.trade_metrics
    assert trades.n == 5
    assert trades.hit_rate == pytest.approx(0.6, abs=1e-4)
    # P&L in EUR at 0.8 EUR per USD: +784, -416, +304, +776, -96.
    assert trades.avg_win_eur == pytest.approx(621.3333, abs=1e-4)
    assert trades.avg_loss_eur == pytest.approx(-256.0, abs=1e-4)
    assert trades.expectancy_eur == pytest.approx(270.4, abs=1e-4)
    assert summary.return_metrics.n == 5
    assert summary.return_metrics.mean_abnormal_return == pytest.approx(0.0338, abs=1e-4)


def test_versions_are_never_mixed(tmp_path: Path) -> None:
    market = ToyMarket()
    for i in range(3):
        market.trade("toy", "1.0", BookMode.PAPER, ticker=f"OLD{i}", exit_price=105.0)
    for i in range(2):
        market.trade("toy", "1.1", BookMode.PAPER, ticker=f"NEW{i}", exit_price=95.0)

    old = version_trades(market.objects, "toy", "1.0", BookMode.PAPER)
    new = version_trades(market.objects, "toy", "1.1", BookMode.PAPER)

    assert TradeMetrics.compute(old, min_trades=1).n == 3
    assert TradeMetrics.compute(new, min_trades=1).n == 2
    assert {t.ticker for t in old} == {"OLD0", "OLD1", "OLD2"}
    service = market.service(registry(("toy", "1.1", "h1", "paper")), tmp_path / "trials",
                             min_trades=1)
    assert service.summary("toy", "1.0", BookMode.PAPER).trade_metrics.n == 3
    assert service.summary("toy", "1.0", BookMode.PAPER).version == "1.0"


def test_insufficient_data_raises_not_silently_zero(tmp_path: Path) -> None:
    market = ToyMarket()
    for i in range(3):
        market.trade("toy", "1.0", BookMode.PAPER, ticker=f"T{i}", exit_price=110.0)
    trades = version_trades(market.objects, "toy", "1.0", BookMode.PAPER)

    with pytest.raises(InsufficientTradeDataError):
        TradeMetrics.compute(trades, min_trades=20)

    service = market.service(registry(("toy", "1.0", "h1", "paper")), tmp_path / "trials",
                             min_trades=20)
    body = service.summary("toy", "1.0", BookMode.PAPER).to_dict()
    assert body["insufficient_data"] is True
    for group in ("trade_metrics", "return_metrics"):
        assert body[group]["n"] == 3
        assert body[group]["insufficient_data"] is True
        statistics = {k: v for k, v in body[group].items() if k not in _COUNT_FIELDS}
        assert statistics and all(v is None for v in statistics.values()), statistics


def test_deflated_sharpe_reads_trial_count_from_registry(tmp_path: Path) -> None:
    trials = tmp_path / "trials"
    write_trials(trials, "h1", n_cells=4)
    write_trials(trials, "h4", n_cells=1)
    market = ToyMarket()
    _many_trades(market, "toy", "1.0", BookMode.BACKTEST, 30)
    service = market.service(registry(("toy", "1.0", "h1", "paper")), trials, min_trades=20)

    metrics = service.summary("toy", "1.0", BookMode.BACKTEST).return_metrics

    returns = pd.Series(metrics.abnormal_returns)
    per_trade_sharpe = float(returns.mean() / returns.std(ddof=1))

    def deflated(n_trials: int) -> float:
        return DeflatedSharpe.compute(
            sharpe_ratio=per_trade_sharpe,
            n_obs=len(returns),
            n_trials=n_trials,
            skewness=float(returns.skew()),
            kurtosis=float(returns.kurt()) + 3.0,
        )

    assert metrics.n_trials == 5
    assert metrics.deflated_sharpe == pytest.approx(deflated(5), abs=1e-12)
    assert metrics.deflated_sharpe != pytest.approx(deflated(1), abs=1e-6)
    assert metrics.deflated_sharpe != pytest.approx(metrics.sharpe, abs=1e-6)
    assert metrics.deflated_sharpe != pytest.approx(per_trade_sharpe, abs=1e-6)


def test_backtest_paper_comparison_flags_deviation_outside_ci() -> None:
    paper = ReturnMetrics.from_values(n=25, mean_abnormal_return=0.01)
    backtest = ReturnMetrics.from_values(n=40, mean_abnormal_return=0.05,
                                         bootstrap_ci_95=(0.03, 0.07))

    comparison = BacktestPaperComparison.compute(paper, backtest)

    assert BacktestPaperComparison.is_inside_backtest_ci(paper, backtest) is False
    assert comparison.is_inside_backtest_ci is False
    assert comparison.deviation_from_backtest_ci == pytest.approx(-0.02)
    assert comparison.paper_tracking_deviation is True
    assert (comparison.n_paper, comparison.n_backtest) == (25, 40)


def test_correlation_matrix_covers_all_active_versions() -> None:
    rng = np.random.default_rng(11)
    closes = [date(2026, 1, 5) + timedelta(days=7 * i) for i in range(30)]
    base = rng.normal(0.0, 0.05, len(closes))
    series = {
        "alpha@1.0": [(d, float(v)) for d, v in zip(closes, base, strict=True)],
        "beta@1.0": [(d, float(v + rng.normal(0, 0.02))) for d, v in zip(closes, base,
                                                                          strict=True)],
        "gamma@2.0": [(d, float(rng.normal(0, 0.05))) for d in closes[:26]],
        # Below the minimum sample: left out of the matrix.
        "delta@1.0": [(d, 0.01) for d in closes[:5]],
    }

    matrix = CorrelationMatrix.compute(series, min_trades=20)

    assert list(matrix.index) == ["alpha@1.0", "beta@1.0", "gamma@2.0"]
    assert list(matrix.columns) == list(matrix.index)
    assert matrix.shape == (3, 3)
    np.testing.assert_allclose(matrix.to_numpy(), matrix.to_numpy().T)
    np.testing.assert_allclose(np.diag(matrix.to_numpy()), 1.0)
    assert matrix.loc["alpha@1.0", "beta@1.0"] > 0.8


def test_metrics_api_returns_computed_not_raw(tmp_path: Path) -> None:
    market = ToyMarket(objects=minio_store())
    _many_trades(market, "toy", "1.0", BookMode.PAPER, 20)
    service = market.service(registry(("toy", "1.0", "h1", "paper")), tmp_path / "trials",
                             min_trades=20)
    api = MetricsApi(service)

    status, content_type, body = api.handle("/api/v1/metrics/strategies")

    assert status == 200
    assert content_type == "application/json"
    text = body.decode("utf-8")
    payload = json.loads(text)
    assert [(s["strategy_name"], s["version"], s["mode"]) for s in payload] == [
        ("toy", "1.0", "paper")
    ]
    assert payload[0]["trade_metrics"]["hit_rate"] is not None
    assert payload[0]["return_metrics"]["mean_abnormal_return"] is not None
    for raw_field in ("position_id", "entry_price", "exit_price", "shares", "pnl_usd", "ticker"):
        assert raw_field not in text

    one = json.loads(api.handle("/api/v1/metrics/strategies/toy/1.0")[2])
    assert [s["mode"] for s in one] == ["paper"]
    assert api.handle("/api/v1/metrics/strategies/toy/9.9")[0] == 404


# Fields that are themselves sample sizes or flags, not statistics needing an `n`.
_COUNT_FIELDS = {
    "n", "insufficient_data", "inputs_seen", "intents", "passed_risk", "filled", "closed",
    "n_wins", "n_losses", "n_trials", "n_paper", "n_backtest", "n_exceeding_known_at_delay",
    "known_at_delay_days",
}


def _metric_groups(body: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    return [(k, v) for k, v in body.items() if isinstance(v, dict)]


def test_sample_size_next_to_every_metric(tmp_path: Path) -> None:
    market = ToyMarket()
    _many_trades(market, "toy", "1.0", BookMode.BACKTEST, 25)
    _many_trades(market, "toy", "1.0", BookMode.PAPER, 22, seed=3)
    service = market.service(registry(("toy", "1.0", "h1", "paper")), tmp_path / "trials",
                             min_trades=20)

    body = service.summary("toy", "1.0", BookMode.PAPER).to_dict()

    groups = _metric_groups(body)
    assert {name for name, _ in groups} >= {
        "activity_funnel", "trade_metrics", "return_metrics", "backtest_paper_comparison",
    }
    for name, group in groups:
        for field_name, value in group.items():
            if field_name in _COUNT_FIELDS or field_name.startswith("n_"):
                continue
            has_n = "n" in group or f"n_{field_name}" in group
            assert has_n, f"{name}.{field_name} has no sample size next to it"
            assert value is not None or group.get("insufficient_data"), f"{name}.{field_name}"
    assert body["n_strategies_ever_tested"] >= 1

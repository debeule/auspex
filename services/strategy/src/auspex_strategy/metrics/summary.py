from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from auspex_backtesting.evaluation import TrialLedger
from auspex_backtesting.hypothesis import hypothesis_views
from auspex_backtesting.prices.snapshot_store import PriceSnapshotStore

from auspex_strategy.metrics.activity import ActivityFunnel
from auspex_strategy.metrics.comparison import BacktestPaperComparison
from auspex_strategy.metrics.correlation import CorrelationMatrix
from auspex_strategy.metrics.latency import LatencyMetrics
from auspex_strategy.metrics.returns import ReturnMetrics, trade_abnormal_returns
from auspex_strategy.metrics.trades import TradeMetrics, version_trades
from auspex_strategy.registry import StrategyRegistry
from auspex_strategy.runtime.book import BookMode, ClosedTrade, VirtualBook
from auspex_strategy.runtime.funnel import FunnelCounter
from auspex_strategy.runtime.slots import known_at_delay_from
from auspex_strategy.runtime.store import ObjectStore


@dataclass(frozen=True)
class StrategyMetricsSummary:
    """Everything reported for one strategy version in one mode. `n_strategies_ever_tested`
    counts every (strategy, version) pair ever registered or booked, retired ones included, so
    a reader can see how many tries stand behind a good-looking Sharpe."""

    strategy_name: str
    version: str
    mode: BookMode
    hypothesis_id: str
    activity_funnel: ActivityFunnel
    trade_metrics: TradeMetrics
    return_metrics: ReturnMetrics
    backtest_paper_comparison: BacktestPaperComparison | None
    latency: LatencyMetrics | None
    insufficient_data: bool
    paper_tracking_deviation: bool | None
    n_strategies_ever_tested: int
    computed_at: datetime

    def to_dict(self) -> dict[str, Any]:
        returns = asdict(self.return_metrics)
        del returns["abnormal_returns"]
        body: dict[str, Any] = _plain({
            "strategy_name": self.strategy_name,
            "version": self.version,
            "mode": self.mode.value,
            "hypothesis_id": self.hypothesis_id,
            "activity_funnel": asdict(self.activity_funnel),
            "trade_metrics": asdict(self.trade_metrics),
            "return_metrics": returns,
            "backtest_paper_comparison": (
                self.backtest_paper_comparison.to_dict()
                if self.backtest_paper_comparison is not None else None
            ),
            "latency": asdict(self.latency) if self.latency is not None else None,
            "insufficient_data": self.insufficient_data,
            "paper_tracking_deviation": self.paper_tracking_deviation,
            "n_strategies_ever_tested": self.n_strategies_ever_tested,
            "computed_at": self.computed_at.isoformat(),
        })
        return body


class MetricsService:
    """Computes strategy metrics from the runtime's state in MinIO and the price snapshots.

    It only reads: books, funnel counters and latency from the strategy bucket, prices from
    the prices bucket, and the trial ledger without taking its lock. Nothing runs a strategy.
    """

    def __init__(
        self,
        store: ObjectStore,
        prices: PriceSnapshotStore,
        registry: StrategyRegistry,
        *,
        protocol: dict[str, Any],
        hypotheses: Mapping[str, dict[str, Any]],
        ledger: TrialLedger,
        min_trades: int,
        clock: Callable[[], datetime],
        versions_dir: Path | None = None,
    ) -> None:
        self._store = store
        self._prices = prices
        self._registry = registry
        self._protocol = protocol
        self._hypotheses = hypotheses
        self._ledger = ledger
        self._min_trades = min_trades
        self._clock = clock
        self._versions_dir = versions_dir

    def summaries(self) -> list[StrategyMetricsSummary]:
        """Every booked version of every strategy that is not retired, in every mode."""
        result = []
        for entry in self._registry.all():
            if entry.status == "retired":
                continue
            for mode in BookMode:
                for version in sorted(self._versions(entry.name, mode)):
                    result.append(self.summary(entry.name, version, mode))
        return result

    def version_summaries(self, strategy_name: str, version: str) -> list[StrategyMetricsSummary]:
        if self._registry.get(strategy_name) is None:
            return []
        return [
            self.summary(strategy_name, version, mode)
            for mode in BookMode if version in self._versions(strategy_name, mode)
        ]

    def summary(self, strategy_name: str, version: str, mode: BookMode) -> StrategyMetricsSummary:
        entry = self._registry.get(strategy_name)
        if entry is None:
            raise KeyError(f"{strategy_name} is not a registered strategy")
        trades = version_trades(self._store, strategy_name, version, mode)
        trade_metrics, return_metrics = self._trade_and_return_metrics(
            trades, entry.hypothesis_id
        )

        comparison = latency = None
        if mode is not BookMode.BACKTEST:
            backtest_trades = version_trades(
                self._store, strategy_name, version, BookMode.BACKTEST
            )
            _, backtest_returns = self._trade_and_return_metrics(
                backtest_trades, entry.hypothesis_id
            )
            comparison = BacktestPaperComparison.compute(return_metrics, backtest_returns)
            latency = LatencyMetrics.compute(
                self._store,
                strategy_name,
                version,
                known_at_delay_from(self._hypotheses[entry.hypothesis_id]),
            )

        return StrategyMetricsSummary(
            strategy_name=strategy_name,
            version=version,
            mode=mode,
            hypothesis_id=entry.hypothesis_id,
            activity_funnel=ActivityFunnel.compute(self._store, strategy_name, version, mode),
            trade_metrics=trade_metrics,
            return_metrics=return_metrics,
            backtest_paper_comparison=comparison,
            latency=latency,
            insufficient_data=trade_metrics.insufficient_data or return_metrics.insufficient_data,
            paper_tracking_deviation=(
                comparison.paper_tracking_deviation if comparison is not None else None
            ),
            n_strategies_ever_tested=self.n_strategies_ever_tested(),
            computed_at=self._clock(),
        )

    def correlation(self, mode: BookMode) -> pd.DataFrame:
        """`CorrelationMatrix` over every booked version of the strategies that are not
        retired, labelled `<strategy>@<version>`."""
        series = {}
        for entry in self._registry.all():
            if entry.status == "retired":
                continue
            for version in sorted(self._versions(entry.name, mode)):
                trades = version_trades(self._store, entry.name, version, mode)
                if len(trades) < self._min_trades:
                    continue
                returns = trade_abnormal_returns(trades, self._prices, self._protocol)
                series[f"{entry.name}@{version}"] = [
                    (t.exit_date, r) for t, r in zip(trades, returns, strict=True)
                ]
        return CorrelationMatrix.compute(series, self._min_trades)

    def trial_count(self, hypothesis_id: str) -> int:
        """Cells evaluated so far on the corpus family of the hypothesis's promotable use."""
        hypothesis = self._hypotheses[hypothesis_id]
        views = hypothesis_views(hypothesis)
        view = next((v for v in views if v.get("role") == "promotable"), views[0])
        family = str(view.get("family") or self._protocol["default_event_family"])
        count: int = self._ledger.observed_trial_count(family)
        return count

    def n_strategies_ever_tested(self) -> int:
        pairs = set()
        for entry in self._registry.all():
            pairs.add((entry.name, entry.version))
            for mode in BookMode:
                pairs.update((entry.name, v) for v in self._versions(entry.name, mode))
        if self._versions_dir is not None and self._versions_dir.is_dir():
            pairs.update(
                (record.parent.name, record.stem)
                for record in self._versions_dir.glob("*/*.json")
            )
        return len(pairs)

    def _trade_and_return_metrics(
        self, trades: list[ClosedTrade], hypothesis_id: str
    ) -> tuple[TradeMetrics, ReturnMetrics]:
        if len(trades) < self._min_trades or not trades:
            return TradeMetrics.insufficient(trades), ReturnMetrics.insufficient(len(trades))
        returns = trade_abnormal_returns(trades, self._prices, self._protocol)
        return (
            TradeMetrics.compute(trades, self._min_trades),
            ReturnMetrics.compute(
                trades,
                returns,
                # The deflated Sharpe needs at least one trial: this strategy's own.
                n_trials=max(self.trial_count(hypothesis_id), 1),
                min_trades=self._min_trades,
            ),
        )

    def _versions(self, strategy_name: str, mode: BookMode) -> set[str]:
        snapshot = VirtualBook(self._store, strategy_name, mode).snapshot()
        versions = {o.strategy_version for o in snapshot.pending_orders}
        versions.update(p.strategy_version for p in snapshot.open_positions)
        versions.update(t.strategy_version for t in snapshot.closed_trades)
        versions.update(FunnelCounter(self._store).versions(strategy_name, mode))
        return versions


def _plain(value: Any) -> Any:
    """JSON-ready: tuples become lists and a non-finite float becomes None."""
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, BookMode):
        return value.value
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value

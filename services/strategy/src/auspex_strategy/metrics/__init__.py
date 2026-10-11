"""Strategy metrics computed from the runtime's books and counters in MinIO, served over HTTP.
Nothing here runs a strategy or writes state."""

from auspex_strategy.metrics.activity import ActivityFunnel
from auspex_strategy.metrics.api import MetricsApi
from auspex_strategy.metrics.comparison import BacktestPaperComparison
from auspex_strategy.metrics.correlation import CorrelationMatrix
from auspex_strategy.metrics.latency import LatencyMetrics
from auspex_strategy.metrics.returns import ReturnMetrics, trade_abnormal_returns
from auspex_strategy.metrics.summary import MetricsService, StrategyMetricsSummary
from auspex_strategy.metrics.trades import (
    InsufficientTradeDataError,
    TradeMetrics,
    version_trades,
)

__all__ = [
    "ActivityFunnel",
    "BacktestPaperComparison",
    "CorrelationMatrix",
    "InsufficientTradeDataError",
    "LatencyMetrics",
    "MetricsApi",
    "MetricsService",
    "ReturnMetrics",
    "StrategyMetricsSummary",
    "TradeMetrics",
    "trade_abnormal_returns",
    "version_trades",
]

"""Runs registered strategies on corroborations: replayed for backtests, streamed from Kafka for
paper and live books."""

from auspex_strategy.runtime.book import (
    BookMode,
    BookSnapshot,
    ClosedTrade,
    OpenPosition,
    PendingOrder,
    VirtualBook,
)
from auspex_strategy.runtime.broker import PaperBroker
from auspex_strategy.runtime.context import BacktestAsOfContext, LiveAsOfContext
from auspex_strategy.runtime.events import CorroboratedSignal
from auspex_strategy.runtime.health import (
    HttpInputHealthClient,
    InputHealthClient,
    InputHealthMonitor,
)
from auspex_strategy.runtime.http import HealthEndpoint
from auspex_strategy.runtime.latency import LatencyTracer
from auspex_strategy.runtime.overlap import OverlapDetector
from auspex_strategy.runtime.replay import BacktestReplayRunner, BacktestResult
from auspex_strategy.runtime.risk import ApprovedIntent, PassThroughRiskManager, RiskManager
from auspex_strategy.runtime.slots import StrategySlot, known_at_delay_days
from auspex_strategy.runtime.store import STRATEGY_BUCKET, MinioObjectStore, ObjectStore
from auspex_strategy.runtime.streaming import (
    CONSUMER_GROUP,
    EventSource,
    OffsetCheckpoint,
    SourceMessage,
    StreamingRuntime,
)

__all__ = [
    "CONSUMER_GROUP",
    "STRATEGY_BUCKET",
    "ApprovedIntent",
    "BacktestAsOfContext",
    "BacktestReplayRunner",
    "BacktestResult",
    "BookMode",
    "BookSnapshot",
    "ClosedTrade",
    "CorroboratedSignal",
    "EventSource",
    "HealthEndpoint",
    "HttpInputHealthClient",
    "InputHealthClient",
    "InputHealthMonitor",
    "LatencyTracer",
    "LiveAsOfContext",
    "MinioObjectStore",
    "ObjectStore",
    "OffsetCheckpoint",
    "OpenPosition",
    "OverlapDetector",
    "PaperBroker",
    "PassThroughRiskManager",
    "PendingOrder",
    "RiskManager",
    "SourceMessage",
    "StrategySlot",
    "StreamingRuntime",
    "VirtualBook",
    "known_at_delay_days",
]

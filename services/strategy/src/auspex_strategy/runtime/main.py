"""Container entry point: consume `auspex.signals.corroborated` and run the registered strategies.

Settings come from the environment (`.env`, through compose); nothing here names a host or port.
"""

from __future__ import annotations

import logging
import os
import signal
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from types import FrameType

from auspex_backtesting.hypothesis import load_hypothesis, verify_hypothesis
from auspex_backtesting.market_sim import (
    CostModel,
    CurrencyConverter,
    FillModel,
    MarketCalendar,
    PriceSnapshotStore,
)
from auspex_backtesting.protocol import EvaluationProtocol
from confluent_kafka import Consumer, KafkaError, TopicPartition
from minio import Minio

from auspex_strategy.metrics import MetricsApi, MetricsService
from auspex_strategy.registry import StrategyRegistry
from auspex_strategy.risk.kill_switch import KillSwitch
from auspex_strategy.runtime.broker import PaperBroker
from auspex_strategy.runtime.context import SnapshotPrices
from auspex_strategy.runtime.funnel import FunnelCounter
from auspex_strategy.runtime.health import HttpInputHealthClient, InputHealthMonitor
from auspex_strategy.runtime.http import HealthEndpoint, serve
from auspex_strategy.runtime.latency import LatencyTracer
from auspex_strategy.runtime.risk import PassThroughRiskManager
from auspex_strategy.runtime.slots import StrategySlot, known_at_delay_days
from auspex_strategy.runtime.store import MinioObjectStore
from auspex_strategy.runtime.streaming import (
    CONSUMER_GROUP,
    OffsetCheckpoint,
    SourceMessage,
    StreamingRuntime,
)

log = logging.getLogger("auspex_strategy.runtime")


class KafkaEventSource:
    """Reads one topic from the offsets in the MinIO checkpoint; Kafka's own group offsets are
    never committed, so the checkpoint is the only resume position."""

    def __init__(self, bootstrap_servers: str, topic: str, checkpoint: OffsetCheckpoint) -> None:
        self._consumer = Consumer({
            "bootstrap.servers": bootstrap_servers,
            "group.id": CONSUMER_GROUP,
            "enable.auto.commit": False,
            "auto.offset.reset": "earliest",
        })
        self._checkpoint = checkpoint

        def on_assign(consumer: Consumer, partitions: list[TopicPartition]) -> None:
            saved = self._checkpoint.load()
            for tp in partitions:
                if tp.partition in saved:
                    tp.offset = saved[tp.partition]
            consumer.assign(partitions)

        self._consumer.subscribe([topic], on_assign=on_assign)

    def poll(self, timeout_seconds: float) -> SourceMessage | None:
        message = self._consumer.poll(timeout_seconds)
        if message is None:
            return None
        error = message.error()
        if error is not None:
            if error.code() != KafkaError._PARTITION_EOF:
                log.error("kafka error: %s", error)
            return None
        return SourceMessage(
            topic=message.topic() or "",
            partition=message.partition() or 0,
            offset=message.offset() or 0,
            value=message.value(),
        )

    def close(self) -> None:
        self._consumer.close()


def load_registry(config_dir: Path) -> StrategyRegistry:
    return StrategyRegistry.load(
        config_dir / "strategies" / "registry.yaml",
        hypothesis_registry_path=config_dir / "hypotheses" / "registry.jsonl",
    )


def load_slots(config_dir: Path, registry: StrategyRegistry) -> list[StrategySlot]:
    hypotheses = config_dir / "hypotheses"
    slots = []
    for entry in registry.all():
        probe = StrategySlot(entry=entry, known_at_delay_days=0)
        if not probe.at_least("paper"):
            continue
        verify_hypothesis(
            entry.hypothesis_id,
            config_dir=hypotheses,
            registry_path=hypotheses / "registry.jsonl",
        )
        slots.append(StrategySlot(
            entry=entry,
            known_at_delay_days=known_at_delay_days(entry.hypothesis_id, hypotheses),
        ))
    return slots


def main(env: Mapping[str, str] = os.environ) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    minio = Minio(
        env["MINIO_ENDPOINT"],
        access_key=env["MINIO_ACCESS_KEY"],
        secret_key=env["MINIO_SECRET_KEY"],
        secure=False,
    )
    objects = MinioObjectStore(minio)
    prices = PriceSnapshotStore(minio)
    calendar = MarketCalendar()
    broker = PaperBroker(
        objects,
        fills=FillModel(prices, calendar),
        costs=CostModel(),
        fx=CurrencyConverter(prices),
        calendar=calendar,
    )
    config_dir = Path(env["STRATEGY_CONFIG_DIR"])
    registry = load_registry(config_dir)
    slots = load_slots(config_dir, registry)
    clock = lambda: datetime.now(UTC)
    monitor = InputHealthMonitor(
        HttpInputHealthClient(env["HEALTH_CHECK_BASE_URL"], timeout_seconds=5.0),
        objects,
        clock=clock,
    )
    latency = LatencyTracer(objects)
    runtime = StreamingRuntime(
        slots,
        broker=broker,
        risk=PassThroughRiskManager(float(env["PASS_THROUGH_POSITION_EUR"])),
        # No core-hub endpoint maps a corroboration's entity to a ticker yet (DECISIONS.md).
        ticker_for=lambda entity_key: None,
        clock=clock,
        timeout_seconds=float(env["STRATEGY_TIMEOUT_SECONDS"]),
        health=monitor,
        latency=latency,
        funnel=FunnelCounter(objects),
        price_close=SnapshotPrices(prices).close,
        is_trading_day=calendar.is_trading_day,
        kill_switch=KillSwitch(objects),
    )
    log.info("running %d strategies: %s", len(slots), ", ".join(s.name for s in slots) or "none")
    for delay in sorted({s.known_at_delay_days for s in slots}):
        if latency.median_exceeds(delay):
            log.warning("median corroboration-to-intent latency exceeds the %d-day known-at delay",
                        delay)

    metrics = metrics_service(config_dir, registry, objects, prices, clock, env)
    serve(HealthEndpoint(runtime, MetricsApi(metrics).handle), int(env["STRATEGY_RUNTIME_PORT"]))
    topic = env["KAFKA_CORROBORATED_TOPIC"]
    checkpoint = OffsetCheckpoint(objects, topic)
    source = KafkaEventSource(env["KAFKA_BOOTSTRAP_SERVERS"], topic, checkpoint)
    interval = float(env["HEALTH_CHECK_INTERVAL_SECONDS"])

    stopping = False

    def stop(signum: int, frame: FrameType | None) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    next_health_check = 0.0
    try:
        while not stopping:
            if time.monotonic() >= next_health_check:
                monitor.poll(runtime.slots)
                next_health_check = time.monotonic() + interval
            runtime.consume(source, checkpoint)
    finally:
        source.close()


def metrics_service(
    config_dir: Path,
    registry: StrategyRegistry,
    objects: MinioObjectStore,
    prices: PriceSnapshotStore,
    clock: Callable[[], datetime],
    env: Mapping[str, str],
) -> MetricsService:
    hypotheses_dir = config_dir / "hypotheses"
    protocol = EvaluationProtocol(
        config_dir=hypotheses_dir, registry_path=hypotheses_dir / "registry.jsonl"
    )
    return MetricsService(
        objects,
        prices,
        registry,
        protocol=protocol.protocol,
        hypotheses={
            entry.hypothesis_id: load_hypothesis(entry.hypothesis_id, hypotheses_dir)
            for entry in registry.all()
        },
        ledger=protocol.ledger(),
        min_trades=int(env["MIN_TRADES_FOR_METRICS"]),
        clock=clock,
        versions_dir=config_dir / "strategies" / "versions",
    )


if __name__ == "__main__":
    main()

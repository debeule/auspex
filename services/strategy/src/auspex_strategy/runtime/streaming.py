from __future__ import annotations

import json
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from auspex_strategy.models import CorroborationRecord, SubscriptionType, TradeIntent, Trigger
from auspex_strategy.runtime.broker import PaperBroker
from auspex_strategy.runtime.context import LiveAsOfContext, PriceReader, TradingDayCheck
from auspex_strategy.runtime.engine import IsolatedDecider, TickerCheck, as_of_for
from auspex_strategy.runtime.events import CorroboratedSignal
from auspex_strategy.runtime.funnel import FunnelCounter
from auspex_strategy.runtime.health import InputHealthMonitor
from auspex_strategy.runtime.latency import LatencyTracer
from auspex_strategy.runtime.overlap import OverlapDetector
from auspex_strategy.runtime.risk import RiskManager
from auspex_strategy.runtime.slots import StrategySlot
from auspex_strategy.runtime.store import ObjectStore

log = logging.getLogger(__name__)

CONSUMER_GROUP = "auspex-strategy-runtime"

TickerResolver = Callable[[str], str | None]


@dataclass(frozen=True)
class SourceMessage:
    topic: str
    partition: int
    offset: int
    value: bytes | None


class EventSource(Protocol):
    def poll(self, timeout_seconds: float) -> SourceMessage | None: ...


class OffsetCheckpoint:
    """The next offset to read per partition, kept in MinIO so a restart resumes where the
    last processed event left off."""

    def __init__(self, store: ObjectStore, topic: str, group: str = CONSUMER_GROUP) -> None:
        self._store = store
        self.key = f"strategy/checkpoints/{group}/{topic}.json"

    def load(self) -> dict[int, int]:
        data = self._store.get(self.key)
        if data is None:
            return {}
        return {int(p): int(o) for p, o in json.loads(data).items()}

    def save(self, partition: int, next_offset: int) -> None:
        offsets = self.load()
        offsets[partition] = next_offset
        self._store.put(self.key, json.dumps({str(p): o for p, o in sorted(offsets.items())})
                        .encode("utf-8"))


class StreamingRuntime:
    """Runs every `paper`-or-above strategy on each corroboration from Kafka.

    `research` strategies never run here. Each `decide()` is isolated (`IsolatedDecider`);
    paused strategies are skipped; intents from the same event are checked for overlap, passed
    to risk, and approved ones go to the strategy's forward book.
    """

    def __init__(
        self,
        slots: Sequence[StrategySlot],
        *,
        broker: PaperBroker,
        risk: RiskManager,
        ticker_for: TickerResolver,
        clock: Callable[[], datetime],
        timeout_seconds: float,
        health: InputHealthMonitor | None = None,
        latency: LatencyTracer | None = None,
        funnel: FunnelCounter | None = None,
        ticker_allowed: TickerCheck | None = None,
        price_close: PriceReader | None = None,
        is_trading_day: TradingDayCheck | None = None,
    ) -> None:
        self.slots = [s for s in slots if s.at_least("paper")]
        self._broker = broker
        self._risk = risk
        self._ticker_for = ticker_for
        self._clock = clock
        self._health = health
        self._latency = latency
        self._funnel = funnel
        self._price_close = price_close
        self._is_trading_day = is_trading_day
        self._decider = IsolatedDecider(
            self.slots, timeout_seconds=timeout_seconds, ticker_allowed=ticker_allowed
        )
        self._overlap = OverlapDetector()
        self._history: list[CorroborationRecord] = []
        self.rejected_events = 0
        for slot in self.slots:
            mode = slot.live_mode
            if mode is not None:
                broker.book(slot.name, mode)

    @property
    def failure_counts(self) -> dict[str, int]:
        return dict(self._decider.failure_counts)

    def is_paused(self, strategy_name: str) -> bool:
        return self._health is not None and self._health.is_paused(strategy_name)

    def process(self, signal: CorroboratedSignal) -> dict[str, list[TradeIntent]]:
        record = CorroborationRecord(
            entity_key=signal.entity_key,
            ticker=self._ticker_for(signal.entity_key) or "",
            corroborated_at=signal.corroborated_at,
            source_count=signal.distinct_source_count,
            source_types=frozenset(),
            participant_event_ids=signal.participant_event_ids,
        )
        self._history.append(record)
        trigger = Trigger(SubscriptionType.CORROBORATION_NEW, payload=record)

        produced: dict[str, list[TradeIntent]] = {}
        decided_at: dict[str, datetime] = {}
        decided: list[StrategySlot] = []
        for slot in self.slots:
            if self.is_paused(slot.name):
                continue
            context = LiveAsOfContext(
                as_of_for(slot, signal.corroborated_at),
                self._history,
                known_at_delay_days=slot.known_at_delay_days,
                price_close=self._price_close,
                is_trading_day=self._is_trading_day,
            )
            intents = self._decider.decide(slot, context, trigger)
            decided_at[slot.name] = self._clock()
            decided.append(slot)
            if intents:
                produced[slot.name] = intents
        self._overlap.flag(produced)

        approved_counts: dict[str, int] = {}
        for name, intents in produced.items():
            if self._latency is not None:
                for intent in intents:
                    self._latency.record(signal, intent, decided_at[name])
            mode = next(s.live_mode for s in self.slots if s.name == name)
            if mode is None:
                continue
            approved_intents = self._risk.review(intents)
            approved_counts[name] = len(approved_intents)
            for approved in approved_intents:
                self._broker.submit(approved, mode)
        if self._funnel is not None:
            for slot in decided:
                if slot.live_mode is not None:
                    self._funnel.record(
                        slot.name,
                        slot.entry.version,
                        slot.live_mode,
                        intents=len(produced.get(slot.name, [])),
                        passed_risk=approved_counts.get(slot.name, 0),
                    )
        self._broker.settle(self._clock().date())
        return produced

    def consume(self, source: EventSource, checkpoint: OffsetCheckpoint,
                poll_timeout_seconds: float = 1.0) -> bool:
        """Process at most one message; returns whether one arrived.

        The offset is checkpointed after the event is fully processed. A payload that does not
        parse is logged and counted, then skipped: it can never become valid by retrying.
        """
        message = source.poll(poll_timeout_seconds)
        if message is None:
            return False
        try:
            signal = CorroboratedSignal.from_json(message.value or b"")
        except (ValueError, KeyError, TypeError):
            self.rejected_events += 1
            log.exception("unreadable event at %s[%d]@%d",
                          message.topic, message.partition, message.offset)
        else:
            self.process(signal)
        checkpoint.save(message.partition, message.offset + 1)
        return True

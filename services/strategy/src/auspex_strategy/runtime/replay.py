from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import TYPE_CHECKING

from auspex_strategy.models import (
    CorroborationRecord,
    SignalRecord,
    SubscriptionType,
    TradeIntent,
    Trigger,
)
from auspex_strategy.runtime.book import BookMode, VirtualBook
from auspex_strategy.runtime.broker import PaperBroker
from auspex_strategy.runtime.context import BacktestAsOfContext, PriceReader, TradingDayCheck
from auspex_strategy.runtime.engine import IsolatedDecider, as_of_for
from auspex_strategy.runtime.funnel import FunnelCounter
from auspex_strategy.runtime.overlap import OverlapDetector
from auspex_strategy.runtime.risk import ApprovalStatus, RiskManager
from auspex_strategy.runtime.slots import StrategySlot

if TYPE_CHECKING:
    from auspex_strategy.trace.tracer import DecisionTracer


@dataclass
class BacktestResult:
    intents: dict[str, list[TradeIntent]]
    books: dict[str, VirtualBook]
    failure_counts: dict[str, int]
    events_processed: int
    first_as_of: datetime | None = None
    last_as_of: datetime | None = None
    wall_seconds: float = 0.0
    decide_seconds: dict[str, float] = field(default_factory=dict)


class BacktestReplayRunner:
    """Replays corroborations in `corroborated_at` order through every `research`-or-above
    strategy. Intents of `paper`-or-above strategies go to risk together per event; with a
    broker the approved ones trade into `backtest` books, and with a tracer every decision is
    traced. `research` strategies only produce intents."""

    def __init__(
        self,
        slots: Sequence[StrategySlot],
        *,
        broker: PaperBroker | None,
        risk: RiskManager,
        tracer: DecisionTracer | None = None,
        signals: Sequence[SignalRecord] = (),
        price_close: PriceReader | None = None,
        is_trading_day: TradingDayCheck | None = None,
        funnel: FunnelCounter | None = None,
    ) -> None:
        self._slots = [s for s in slots if s.at_least("research")]
        self._broker = broker
        self._risk = risk
        self._tracer = tracer
        self._signals = signals
        self._price_close = price_close
        self._is_trading_day = is_trading_day
        self._funnel = funnel
        self._overlap = OverlapDetector()

    def run(self, records: Sequence[CorroborationRecord]) -> BacktestResult:
        ordered = sorted(records, key=lambda r: (r.corroborated_at, r.entity_key))
        decider = IsolatedDecider(self._slots, timeout_seconds=None)
        intents: dict[str, list[TradeIntent]] = {s.name: [] for s in self._slots}
        decide_seconds = {s.name: 0.0 for s in self._slots}
        traded = {s.name: s for s in self._slots if s.at_least("paper")}
        books = (
            {name: self._broker.book(name, BookMode.BACKTEST) for name in traded}
            if self._broker is not None else {}
        )
        as_ofs: list[datetime] = []
        settled_through: date | None = None
        started = time.monotonic()

        for i, record in enumerate(ordered):
            trigger = Trigger(SubscriptionType.CORROBORATION_NEW, payload=record)
            produced: dict[str, list[TradeIntent]] = {}
            for slot in self._slots:
                as_of = as_of_for(slot, record.corroborated_at)
                as_ofs.append(as_of)
                context = BacktestAsOfContext(
                    as_of,
                    ordered[: i + 1],
                    known_at_delay_days=slot.known_at_delay_days,
                    signals=self._signals,
                    price_close=self._price_close,
                    is_trading_day=self._is_trading_day,
                )
                t0 = time.monotonic()
                result = decider.decide(slot, context, trigger)
                decide_seconds[slot.name] += time.monotonic() - t0
                if result:
                    produced[slot.name] = result
            self._overlap.flag(produced)

            approved_counts: dict[str, int] = {}
            for name, produced_intents in produced.items():
                intents[name].extend(produced_intents)
            to_review = [i for name, p in produced.items() if name in traded for i in p]
            decisions = self._risk.review(to_review) if to_review else []
            for decision in decisions:
                if decision.status is ApprovalStatus.APPROVED:
                    name = decision.intent.strategy_name
                    approved_counts[name] = approved_counts.get(name, 0) + 1
                if self._tracer is not None:
                    self._tracer.record(record, decision, traded[decision.intent.strategy_name])
                if self._broker is not None and decision.submits:
                    entry = self._broker.submit(decision.as_approved(), BookMode.BACKTEST)
                    settled_through = max(settled_through or entry, entry)
            if self._funnel is not None:
                for slot in self._slots:
                    self._funnel.record(
                        slot.name,
                        slot.entry.version,
                        BookMode.BACKTEST,
                        intents=len(produced.get(slot.name, [])),
                        passed_risk=approved_counts.get(slot.name, 0),
                    )
            if self._broker is not None and settled_through is not None:
                self._broker.settle(settled_through)

        return BacktestResult(
            intents=intents,
            books=books,
            failure_counts=dict(decider.failure_counts),
            events_processed=len(ordered),
            first_as_of=min(as_ofs, default=None),
            last_as_of=max(as_ofs, default=None),
            wall_seconds=time.monotonic() - started,
            decide_seconds=decide_seconds,
        )

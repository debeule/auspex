from __future__ import annotations

import json
import statistics
from datetime import datetime, timedelta

from auspex_strategy.models import TradeIntent
from auspex_strategy.runtime.events import CorroboratedSignal
from auspex_strategy.runtime.store import ObjectStore, append_line

LATENCY_KEY = "strategy/latency/distribution.jsonl"


class LatencyTracer:
    """Records how long after a corroboration formed each live intent was produced.

    `corroborated_at` is the latest publication date among the participants; `ingested_at` is
    when core-hub first detected the corroboration. The distribution is the evidence for the
    known-at delay the backtests assume.
    """

    def __init__(self, store: ObjectStore) -> None:
        self._store = store

    def record(
        self, signal: CorroboratedSignal, intent: TradeIntent, intent_time: datetime
    ) -> None:
        gap = intent_time - signal.corroborated_at
        append_line(self._store, LATENCY_KEY, json.dumps({
            "strategy": intent.strategy_name,
            "strategy_version": intent.strategy_version,
            "intent_id": str(intent.intent_id),
            "corroborated_at": signal.corroborated_at.isoformat(),
            "ingested_at": signal.first_detected_at.isoformat(),
            "intent_time": intent_time.isoformat(),
            "latency_corroboration_to_intent_ms": gap // timedelta(milliseconds=1),
        }))

    def median_exceeds(self, known_at_delay_days: int) -> bool:
        """True when the recorded median latency is longer than the delay backtests assume."""
        data = self._store.get(LATENCY_KEY)
        if not data:
            return False
        gaps = [
            json.loads(line)["latency_corroboration_to_intent_ms"]
            for line in data.decode("utf-8").splitlines()
            if line.strip()
        ]
        limit_ms = timedelta(days=known_at_delay_days) // timedelta(milliseconds=1)
        return bool(statistics.median(gaps) > limit_ms)

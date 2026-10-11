from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import timedelta

import numpy as np

from auspex_strategy.runtime.latency import LATENCY_KEY
from auspex_strategy.runtime.store import ObjectStore


@dataclass(frozen=True)
class LatencyMetrics:
    """Corroboration-to-intent latency of one strategy version's forward intents, in ms.
    `n_exceeding_known_at_delay` counts intents later than the delay its backtests assume."""

    n: int
    p50_ms: float | None
    p95_ms: float | None
    p99_ms: float | None
    n_exceeding_known_at_delay: int
    known_at_delay_days: int
    insufficient_data: bool

    @classmethod
    def compute(
        cls, store: ObjectStore, strategy_name: str, version: str, known_at_delay_days: int
    ) -> LatencyMetrics:
        data = store.get(LATENCY_KEY) or b""
        rows = [json.loads(line) for line in data.decode("utf-8").splitlines() if line.strip()]
        gaps = [
            float(r["latency_corroboration_to_intent_ms"]) for r in rows
            if r.get("strategy") == strategy_name and r.get("strategy_version") == version
        ]
        limit_ms = timedelta(days=known_at_delay_days) / timedelta(milliseconds=1)
        if not gaps:
            return cls(0, None, None, None, 0, known_at_delay_days, True)
        p50, p95, p99 = (float(v) for v in np.percentile(gaps, [50, 95, 99]))
        return cls(
            n=len(gaps),
            p50_ms=p50,
            p95_ms=p95,
            p99_ms=p99,
            n_exceeding_known_at_delay=sum(1 for g in gaps if g > limit_ms),
            known_at_delay_days=known_at_delay_days,
            insufficient_data=False,
        )

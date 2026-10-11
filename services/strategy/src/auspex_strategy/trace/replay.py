from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime

from auspex_strategy.models import CorroborationRecord
from auspex_strategy.runtime.replay import BacktestReplayRunner
from auspex_strategy.runtime.risk import RiskManager
from auspex_strategy.runtime.slots import StrategySlot
from auspex_strategy.trace.records import DocumentRecord, TraceMode, TraceRecord
from auspex_strategy.trace.tracer import DecisionTracer
from auspex_strategy.trace.validator import TraceValidator


class TraceReplayer:
    """Re-runs archived corroborations through one `paper`-or-above strategy and a risk stub,
    without fills, and returns the traces. Run against the same events, every field but
    `trace_id`, `approved_at` and `fill_time` matches the original run's traces."""

    def __init__(
        self,
        documents: Mapping[str, DocumentRecord],
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._documents = documents
        self._clock = clock

    def replay(
        self,
        events: Sequence[CorroborationRecord],
        strategy: StrategySlot,
        risk_manager_stub: RiskManager,
    ) -> list[TraceRecord]:
        traces: list[TraceRecord] = []

        def keep(trace: TraceRecord) -> None:
            TraceValidator.validate(trace)
            traces.append(trace)

        tracer = DecisionTracer(keep, self._documents, mode=TraceMode.BACKTEST, clock=self._clock)
        BacktestReplayRunner(
            [strategy], broker=None, risk=risk_manager_stub, tracer=tracer
        ).run(events)
        return traces

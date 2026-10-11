from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from uuid import UUID, uuid5

from auspex_strategy.abc import AsOfContext
from auspex_strategy.models import CorroborationRecord, TradeIntent, Trigger
from auspex_strategy.runtime.slots import StrategySlot

log = logging.getLogger(__name__)

ContextFactory = Callable[[StrategySlot, datetime], AsOfContext]
TickerCheck = Callable[[str], bool]

# Fixed forever: changing it renames every intent and breaks trace replay against old traces.
_INTENT_NAMESPACE = UUID("6f1d3c2a-8a4e-5b7f-9c31-2e64d0a9b815")


class InvalidIntentError(Exception):
    pass


class DecideTimeoutError(Exception):
    pass


class IsolatedDecider:
    """Calls each strategy's `decide()` so that no strategy can affect another.

    A crash, a call running past the timeout, or output that is not a valid intent for that
    strategy is logged at ERROR, counted in `failure_counts`, and discards that strategy's
    output for the event. A timed-out call keeps running in its daemon thread; it cannot be
    killed, but its result is never used. Valid intents get their ids from `name_intents`.
    """

    def __init__(
        self,
        slots: Sequence[StrategySlot],
        *,
        timeout_seconds: float | None,
        ticker_allowed: TickerCheck | None = None,
    ) -> None:
        self._timeout = timeout_seconds
        self._ticker_allowed = ticker_allowed or (lambda ticker: True)
        self.failure_counts: dict[str, int] = {slot.name: 0 for slot in slots}

    def decide(
        self, slot: StrategySlot, context: AsOfContext, trigger: Trigger
    ) -> list[TradeIntent] | None:
        try:
            intents = self._call(slot, context, trigger)
            self._validate(slot, intents)
            name_intents(slot, context.as_of, trigger, intents)
        except Exception:
            self.failure_counts[slot.name] = self.failure_counts.get(slot.name, 0) + 1
            log.exception("strategy %s failed on as_of=%s", slot.name, context.as_of.isoformat())
            return None
        return intents

    def _call(
        self, slot: StrategySlot, context: AsOfContext, trigger: Trigger
    ) -> list[TradeIntent]:
        if self._timeout is None:
            return slot.entry.decide(context, trigger)
        outcome: dict[str, object] = {}

        def run() -> None:
            try:
                outcome["result"] = slot.entry.decide(context, trigger)
            except Exception as exc:  # noqa: BLE001 (re-raised in the calling thread)
                outcome["error"] = exc

        worker = threading.Thread(target=run, name=f"decide-{slot.name}", daemon=True)
        worker.start()
        worker.join(self._timeout)
        if worker.is_alive():
            raise DecideTimeoutError(f"decide() ran past {self._timeout}s")
        if "error" in outcome:
            raise outcome["error"]  # type: ignore[misc]
        return outcome["result"]  # type: ignore[return-value]

    def _validate(self, slot: StrategySlot, intents: object) -> None:
        if not isinstance(intents, list):
            raise InvalidIntentError(f"decide() returned {type(intents).__name__}, not a list")
        for intent in intents:
            if not isinstance(intent, TradeIntent):
                raise InvalidIntentError(f"decide() returned a {type(intent).__name__}")
            if intent.strategy_name != slot.name:
                raise InvalidIntentError(f"intent names strategy {intent.strategy_name!r}")
            if not intent.ticker or not self._ticker_allowed(intent.ticker):
                raise InvalidIntentError(f"intent on ticker {intent.ticker!r} is not allowed")


def as_of_for(slot: StrategySlot, corroborated_at: datetime) -> datetime:
    return corroborated_at + timedelta(days=slot.known_at_delay_days)


def name_intents(
    slot: StrategySlot, as_of: datetime, trigger: Trigger, intents: list[TradeIntent]
) -> None:
    """Give each intent an id derived from the strategy, the corroboration and its position in
    the output, so replaying the same events names the same intents and traces compare equal."""
    record = trigger.payload
    if not isinstance(record, CorroborationRecord):
        return
    for i, intent in enumerate(intents):
        intent.intent_id = uuid5(_INTENT_NAMESPACE, "|".join((
            slot.name,
            slot.entry.version,
            record.entity_key,
            record.participants_hash,
            record.corroborated_at.isoformat(),
            as_of.isoformat(),
            str(i),
        )))

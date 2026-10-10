from __future__ import annotations

import json
import logging
import urllib.request
from collections.abc import Callable, Iterable, Mapping
from datetime import datetime
from typing import Protocol

from auspex_strategy.models import InputSource
from auspex_strategy.runtime.slots import StrategySlot
from auspex_strategy.runtime.store import ObjectStore, append_line

log = logging.getLogger(__name__)

PAUSES_KEY = "strategy/health/pauses.jsonl"
INPUTS_PATH = "/api/v1/health/inputs"


class InputHealthClient(Protocol):
    def fetch(self) -> Mapping[InputSource, bool]: ...


class HttpInputHealthClient:
    """Reads core-hub's per-input health: `{"inputs": {"<input_source>": "UP" | "DOWN"}}`.

    A source missing from the answer, or no answer at all, counts as unhealthy: a strategy must
    not trade on inputs nobody vouched for.
    """

    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        self._url = base_url.rstrip("/") + INPUTS_PATH
        self._timeout = timeout_seconds

    def fetch(self) -> Mapping[InputSource, bool]:
        try:
            with urllib.request.urlopen(self._url, timeout=self._timeout) as response:
                body = json.loads(response.read())
        except (OSError, ValueError) as exc:
            log.error("input health check at %s failed: %s", self._url, exc)
            return {source: False for source in InputSource}
        reported = body.get("inputs", {}) if isinstance(body, dict) else {}
        return {source: reported.get(source.value) == "UP" for source in InputSource}


class InputHealthMonitor:
    """Pauses each strategy that declares an unhealthy input, and records every pause and resume.

    A paused strategy sees no new events rather than events built from stale inputs.
    """

    def __init__(
        self, client: InputHealthClient, store: ObjectStore, *, clock: Callable[[], datetime]
    ) -> None:
        self._client = client
        self._store = store
        self._clock = clock
        self._paused: dict[str, frozenset[InputSource]] = {}

    def poll(self, slots: Iterable[StrategySlot]) -> None:
        health = self._client.fetch()
        now = self._clock()
        for slot in slots:
            name = slot.entry.name
            unhealthy = frozenset(
                s for s in slot.declared_inputs if not health.get(s, False)
            )
            was_paused = name in self._paused
            if unhealthy and not was_paused:
                self._paused[name] = unhealthy
                self._record(name, "pause_start", now, unhealthy)
                log.warning("strategy %s paused: unhealthy inputs %s",
                            name, sorted(s.value for s in unhealthy))
            elif not unhealthy and was_paused:
                del self._paused[name]
                self._record(name, "pause_end", now, frozenset())
                log.info("strategy %s resumed", name)
            elif unhealthy:
                self._paused[name] = unhealthy

    def is_paused(self, strategy_name: str) -> bool:
        return strategy_name in self._paused

    def _record(
        self, name: str, event: str, at: datetime, unhealthy: frozenset[InputSource]
    ) -> None:
        append_line(self._store, PAUSES_KEY, json.dumps({
            "strategy": name,
            "event": event,
            "at": at.isoformat(),
            "unhealthy_inputs": sorted(s.value for s in unhealthy),
        }))

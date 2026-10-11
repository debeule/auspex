from __future__ import annotations

import getpass
import json
import re
from collections.abc import Callable
from datetime import UTC, datetime

from auspex_strategy.runtime.store import ObjectStore, append_line

EVENTS_KEY = "strategy/killswitch/events.jsonl"
_NAME = re.compile(r"[A-Za-z0-9_.-]+")


class KillSwitch:
    """Stops new intents, globally or for one strategy; open positions are left to their own
    exit conditions.

    The state is a flag object in MinIO (`strategy/killswitch/global.json` or
    `strategy/killswitch/<strategy>.json`), so the command line can set it while the runtime
    reads it. Every trigger and reset is appended to `strategy/killswitch/events.jsonl`.
    """

    def __init__(
        self, store: ObjectStore, clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    ) -> None:
        self._store = store
        self._clock = clock

    def trigger(
        self, reason: str, strategy_name: str | None = None, triggered_by: str | None = None
    ) -> None:
        self._set(True, reason, strategy_name, triggered_by)

    def reset(
        self, reason: str, strategy_name: str | None = None, triggered_by: str | None = None
    ) -> None:
        self._set(False, reason, strategy_name, triggered_by)

    def is_active(self, strategy_name: str | None = None) -> bool:
        """True when the global switch is on, or, given a strategy, when its own switch is."""
        if self._flag(None):
            return True
        return strategy_name is not None and self._flag(strategy_name)

    def _flag(self, strategy_name: str | None) -> bool:
        data = self._store.get(_key(strategy_name))
        return data is not None and bool(json.loads(data).get("active"))

    def _set(
        self, active: bool, reason: str, strategy_name: str | None, triggered_by: str | None
    ) -> None:
        record = {
            "active": active,
            "scope": strategy_name or "global",
            "reason": reason,
            "triggered_at": self._clock().isoformat(),
            "triggered_by": triggered_by or getpass.getuser(),
        }
        self._store.put(_key(strategy_name), json.dumps(record).encode("utf-8"))
        append_line(self._store, EVENTS_KEY,
                    json.dumps({"action": "trigger" if active else "reset", **record}))


def _key(strategy_name: str | None) -> str:
    if strategy_name is None:
        return "strategy/killswitch/global.json"
    if not _NAME.fullmatch(strategy_name):
        raise ValueError(f"not a strategy name: {strategy_name!r}")
    return f"strategy/killswitch/{strategy_name}.json"

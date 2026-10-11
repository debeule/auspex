from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime

from auspex_strategy.runtime.store import ObjectStore, append_line
from auspex_strategy.trace.records import TraceMode, TraceRecord
from auspex_strategy.trace.validator import TraceValidator


class TraceStore:
    """Append-only JSONL of traces per strategy and mode, in the strategy bucket. Only traces
    that pass `TraceValidator` are written; existing lines are never rewritten."""

    def __init__(self, store: ObjectStore) -> None:
        self._store = store

    @staticmethod
    def key(strategy_name: str, mode: TraceMode) -> str:
        return f"strategy/traces/{strategy_name}/{mode.value}/traces.jsonl"

    def append(self, record: TraceRecord) -> None:
        TraceValidator.validate(record)
        line = json.dumps(record.to_json_dict(), sort_keys=True, allow_nan=False)
        append_line(self._store, self.key(record.strategy_name, record.mode), line)

    def read(
        self, strategy_name: str, mode: TraceMode, since: datetime | None = None
    ) -> Iterator[TraceRecord]:
        """Traces in write order; with `since`, only those decided as of `since` or later."""
        data = self._store.get(self.key(strategy_name, mode)) or b""
        for line in data.decode("utf-8").splitlines():
            if not line.strip():
                continue
            record = TraceRecord.from_json_dict(json.loads(line))
            if since is None or record.as_of >= since:
                yield record

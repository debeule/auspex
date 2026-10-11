from __future__ import annotations

import fcntl
import json
import logging
import os
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from auspex_backtesting.hypothesis import hypothesis_views

logger = logging.getLogger(__name__)

LOCK_FILE = ".lock"


class TrialBudgetExhaustedError(Exception):
    pass


class TrialLedgerCorruptError(Exception):
    pass


@dataclass(frozen=True)
class Reservation:
    run_id: str
    hypothesis_id: str
    family: str
    role: str
    cells: tuple[dict[str, Any], ...]
    family_trial_count: int


class TrialLedger:
    """Every cell evaluated on each corpus family, one append-only JSON line per run.

    `config/hypotheses/trials/<hypothesis id>.jsonl` holds a line per run listing the cells it
    evaluated. A run reserves its cells before it reads any return, so a run that fails or is
    interrupted afterwards still counts; nothing is ever released. The deflated Sharpe ratio
    takes its trial count from here, summed over every hypothesis in the family whose role the
    protocol counts.

    `reserve` reads every ledger, checks the family budget and appends the line while holding
    an exclusive lock on `trials/.lock`, so two runs racing for the last cells cannot both pass
    the check. A final line without its newline is a write that never finished (its `reserve`
    never returned, so its run read nothing): it is truncated and logged. Any other line that
    does not parse stops every reservation, because guessing its cells could undercount.
    """

    def __init__(
        self,
        trials_dir: Path,
        protocol: dict[str, Any],
        hypotheses: Mapping[str, dict[str, Any]],
    ) -> None:
        self._dir = trials_dir
        self._protocol = protocol
        self._hypotheses = hypotheses
        self._counted_roles = frozenset(protocol["trials"]["counts_roles"])

    def family_trial_count(self, family: str) -> int:
        with self._locked():
            return self._count(self._read_all(), family)

    def observed_trial_count(self, family: str) -> int:
        """`family_trial_count` for a reader that cannot write to `trials/`, such as a service
        with the config mounted read-only: no lock, and a final line still being written is
        skipped rather than truncated. A run reserving at the same moment may be missed."""
        entries: list[tuple[Path, dict[str, Any]]] = []
        for path in sorted(self._dir.glob("*.jsonl")):
            data = path.read_bytes()
            complete = data[: data.rfind(b"\n") + 1]
            entries.extend((path, entry) for entry in _parse_ledger(path, complete))
        return self._count(entries, family)

    def remaining_budget(self, family: str) -> int:
        return self._budget(family) - self.family_trial_count(family)

    def reserve(
        self,
        hypothesis_id: str,
        cells: Sequence[Mapping[str, Any]],
        run_id: str,
        use: str | None = None,
    ) -> Reservation:
        """Record `cells` for this run, or raise `TrialBudgetExhaustedError` and record nothing.

        Returns only once the line is on disk (`fsync`).
        """
        if not cells:
            raise ValueError("a run evaluates at least one cell")
        family, role = self._family_and_role(hypothesis_id, use)
        budget = self._budget(family)
        entry: dict[str, Any] = {
            "run_id": run_id,
            "hypothesis_id": hypothesis_id,
            "family": family,
            "role": role,
            "cells": [dict(c) for c in cells],
            "reserved_at": datetime.now(UTC).isoformat(),
        }
        if use is not None:
            entry["use"] = use
        with self._locked():
            used = self._count(self._read_all(), family)
            if role in self._counted_roles and used + len(cells) > budget:
                raise TrialBudgetExhaustedError(
                    f"{family}: {used} of {budget} cells used; run {run_id} of {hypothesis_id} "
                    f"asks for {len(cells)}"
                )
            line = (json.dumps(entry, sort_keys=True) + "\n").encode("utf-8")
            _write_line(self._dir / f"{hypothesis_id}.jsonl", line)
            counted = used + (len(cells) if role in self._counted_roles else 0)
        return Reservation(run_id, hypothesis_id, family, role, tuple(entry["cells"]), counted)

    def _budget(self, family: str) -> int:
        families = self._protocol["families"]
        if family not in families:
            raise TrialBudgetExhaustedError(f"family {family!r} has no registered budget")
        return int(families[family]["budget_cells"])

    def _family_and_role(self, hypothesis_id: str, use: str | None) -> tuple[str, str]:
        hypothesis = self._hypotheses.get(hypothesis_id)
        if hypothesis is None:
            raise KeyError(f"{hypothesis_id} is not a registered hypothesis")
        views = hypothesis_views(hypothesis)
        if use is None and len(views) > 1:
            raise ValueError(f"{hypothesis_id} declares several uses; name the use")
        view = next((v for v in views if use is None or v.get("use") == use), None)
        if view is None:
            raise ValueError(f"{hypothesis_id} has no use {use!r}")
        family = str(view.get("family") or self._protocol["default_event_family"])
        return family, str(view.get("role"))

    def _count(self, entries: list[tuple[Path, dict[str, Any]]], family: str) -> int:
        total = 0
        for path, entry in entries:
            hypothesis_id = str(entry.get("hypothesis_id", path.stem))
            if hypothesis_id in self._hypotheses:
                entry_family, role = self._family_and_role(hypothesis_id, entry.get("use"))
            else:
                entry_family, role = str(entry.get("family")), str(entry.get("role"))
            if entry_family == family and role in self._counted_roles:
                total += len(entry["cells"])
        return total

    def _read_all(self) -> list[tuple[Path, dict[str, Any]]]:
        entries: list[tuple[Path, dict[str, Any]]] = []
        for path in sorted(self._dir.glob("*.jsonl")):
            for entry in _read_ledger(path):
                entries.append((path, entry))
        return entries

    @contextmanager
    def _locked(self) -> Iterator[None]:
        self._dir.mkdir(parents=True, exist_ok=True)
        with (self._dir / LOCK_FILE).open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)


def _read_ledger(path: Path) -> list[dict[str, Any]]:
    """The ledger's entries, after truncating a torn final line. Caller holds the lock."""
    data = path.read_bytes()
    if data and not data.endswith(b"\n"):
        keep = data.rfind(b"\n") + 1
        logger.warning(
            "trial ledger %s: dropped a torn final line of %d bytes", path, len(data) - keep
        )
        os.truncate(path, keep)
        data = data[:keep]
    return _parse_ledger(path, data)


def _parse_ledger(path: Path, data: bytes) -> list[dict[str, Any]]:
    entries = []
    for number, raw in enumerate(data.splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            entry = json.loads(raw)
        except ValueError as exc:
            raise TrialLedgerCorruptError(f"{path}:{number} does not parse: {exc}") from exc
        if not isinstance(entry, dict) or not isinstance(entry.get("cells"), list):
            raise TrialLedgerCorruptError(f"{path}:{number} lists no cells")
        entries.append(entry)
    return entries


def _write_line(path: Path, line: bytes) -> None:
    """Append one whole line with a single `write`, then `fsync`."""
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        written = os.write(fd, line)
        if written != len(line):
            raise OSError(f"{path}: wrote {written} of {len(line)} bytes")
        os.fsync(fd)
    finally:
        os.close(fd)

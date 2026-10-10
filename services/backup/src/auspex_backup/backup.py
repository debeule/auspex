"""One backup run: every store into the backup folder, then the manifest, then pruning.

The backup only reads from Postgres, Neo4j and MinIO (Invariants 1 and 2); writing them back is
`restore`'s job, run by hand with core-hub stopped.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from auspex_backup.graph import Driver, export_graph
from auspex_backup.minio_mirror import MinioReader, mirror_bucket
from auspex_backup.postgres import CommandRunner, dump_databases
from auspex_backup.prune import prune_dated

MANIFEST = "last_success.json"
DATED_PARENTS = ("postgres", "neo4j")


@dataclass(frozen=True)
class Store:
    """A named part of the backup; `run` gets the run's UTC date and returns counts and sizes."""

    name: str
    run: Callable[[str], Mapping[str, int]]


class StoreFailedError(RuntimeError):
    def __init__(self, failures: Mapping[str, BaseException]) -> None:
        self.stores = list(failures)
        super().__init__(
            "; ".join(f"{name}: {type(exc).__name__}: {exc}" for name, exc in failures.items())
        )


class Backup:
    def __init__(
        self,
        root: Path,
        stores: Sequence[Store],
        keep_days: int,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        close: Callable[[], None] = lambda: None,
    ) -> None:
        self._root = root
        self._close = close
        self._stores = stores
        self._keep_days = keep_days
        self._now = now

    def run(self) -> dict[str, Any]:
        """Runs every store, even after one fails, so a partial copy is still taken.

        `last_success.json` is replaced only when every store succeeded; otherwise the previous
        one stays and `StoreFailedError` names the failed stores.
        """
        try:
            return self._run()
        finally:
            self._close()

    def _run(self) -> dict[str, Any]:
        started = self._now().astimezone(UTC)
        day = started.date().isoformat()
        results: dict[str, dict[str, int]] = {}
        failures: dict[str, BaseException] = {}
        for store in self._stores:
            try:
                results[store.name] = dict(store.run(day))
            except Exception as exc:  # noqa: BLE001 - every store gets its turn
                failures[store.name] = exc
        if failures:
            raise StoreFailedError(failures)
        manifest = {
            "date": day,
            "started_at": _utc(started),
            "finished_at": _utc(self._now()),
            "stores": results,
        }
        partial = self._root / (MANIFEST + ".partial")
        self._root.mkdir(parents=True, exist_ok=True)
        partial.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(partial, self._root / MANIFEST)
        for parent in DATED_PARENTS:
            prune_dated(self._root / parent, self._keep_days, started.date())
        return manifest


def build_stores(
    root: Path,
    *,
    runner: CommandRunner,
    pg_environment: Mapping[str, str],
    databases: Sequence[str],
    driver: Driver,
    minio: MinioReader,
    buckets: Sequence[str],
) -> list[Store]:
    def postgres(day: str) -> Mapping[str, int]:
        sizes = dump_databases(runner, databases, root / "postgres" / day, pg_environment)
        return {f"{database}_bytes": size for database, size in sizes.items()}

    def neo4j(day: str) -> Mapping[str, int]:
        return asdict(export_graph(driver, root / "neo4j" / day / "graph.jsonl"))

    def minio_mirror(day: str) -> Mapping[str, int]:
        counts: dict[str, int] = {}
        for bucket in buckets:
            result = mirror_bucket(minio, bucket, root / "minio")
            counts[f"{bucket}_objects"] = result.objects
            counts[f"{bucket}_copied"] = result.copied
            counts[f"{bucket}_bytes"] = result.bytes
        return counts

    return [Store("postgres", postgres), Store("neo4j", neo4j), Store("minio", minio_mirror)]


def _utc(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

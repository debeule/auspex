"""Restores one dated backup into empty stores: `docker compose --profile restore run --rm restore
--date YYYY-MM-DD`. Run with the `app` profile stopped; see `docs/backup-restore.md`.

Every target is checked before anything is written, and a target that already holds data is
refused, so a restore can never merge into or overwrite a live store.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Protocol

from neo4j import GraphDatabase

from auspex_backup.api import BACKUP_ROOT, minio_from_env
from auspex_backup.graph import Driver, node_count, replay_graph
from auspex_backup.minio_mirror import MinioReader
from auspex_backup.postgres import CommandRunner, pg_env, restore_database, run_command, table_count


class MinioRestorer(MinioReader, Protocol):
    def fput_object(self, bucket_name: str, object_name: str, file_path: str) -> object: ...


class TargetNotEmptyError(RuntimeError):
    """A store to restore into already holds data."""


def restore(
    root: Path,
    day: str,
    *,
    runner: CommandRunner,
    pg_environment: Mapping[str, str],
    databases: Sequence[str],
    driver: Driver,
    minio: MinioRestorer,
    buckets: Sequence[str],
) -> None:
    dumps = {database: root / "postgres" / day / f"{database}.dump" for database in databases}
    graph = root / "neo4j" / day / "graph.jsonl"
    for path in [*dumps.values(), graph]:
        if not path.is_file():
            raise FileNotFoundError(f"backup of {day} has no {path.relative_to(root)}")

    occupied = [
        f"postgres database {database}"
        for database in databases
        if table_count(runner, database, pg_environment) > 0
    ]
    if node_count(driver) > 0:
        occupied.append("neo4j")
    occupied += [
        f"minio bucket {bucket}"
        for bucket in buckets
        if next(iter(minio.list_objects(bucket, recursive=True)), None) is not None
    ]
    if occupied:
        raise TargetNotEmptyError(
            "refusing to restore into stores that hold data: " + ", ".join(occupied)
        )

    for database, dump in dumps.items():
        restore_database(runner, database, dump, pg_environment)
    replay_graph(driver, graph)
    upload_mirror(minio, root / "minio", buckets)


def upload_mirror(minio: MinioRestorer, mirror: Path, buckets: Sequence[str]) -> int:
    """Uploads every mirrored object of `buckets` from `mirror/<bucket>/`; returns the count."""
    uploaded = 0
    for bucket in buckets:
        folder = mirror / bucket
        if not folder.is_dir():
            continue
        for path in sorted(p for p in folder.rglob("*") if p.is_file()):
            minio.fput_object(bucket, path.relative_to(folder).as_posix(), str(path))
            uploaded += 1
    return uploaded


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="restore", description=__doc__)
    parser.add_argument("--date", required=True, help="dated backup folder, YYYY-MM-DD (UTC)")
    args = parser.parse_args(argv)
    env = os.environ
    driver = GraphDatabase.driver(env["NEO4J_URI"], auth=(env["NEO4J_USER"], env["NEO4J_PASSWORD"]))
    try:
        restore(
            BACKUP_ROOT,
            args.date,
            runner=run_command,
            pg_environment=pg_env(env),
            databases=env["BACKUP_DATABASES"].split(","),
            driver=driver,
            minio=minio_from_env(),
            buckets=env["BACKUP_BUCKETS"].split(","),
        )
    except (TargetNotEmptyError, FileNotFoundError) as exc:
        print(f"restore refused: {exc}", file=sys.stderr)
        return 1
    finally:
        driver.close()
    print(f"restored the backup of {args.date}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

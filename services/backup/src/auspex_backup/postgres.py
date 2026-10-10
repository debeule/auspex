"""`pg_dump` and `pg_restore` through an injectable command runner.

The password reaches the client tools only through `PGPASSWORD` in their environment, never on
their command line, where any process listing would show it.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Protocol

_PG_VARIABLES = ("PGHOST", "PGPORT", "PGUSER", "PGPASSWORD", "PATH", "HOME", "LANG")


class CommandRunner(Protocol):
    """Runs `argv` with exactly `env`; returns its stdout unless `stdout` names a file for it."""

    def __call__(
        self,
        argv: Sequence[str],
        env: Mapping[str, str],
        *,
        stdin: Path | None = None,
        stdout: Path | None = None,
    ) -> bytes: ...


def run_command(
    argv: Sequence[str],
    env: Mapping[str, str],
    *,
    stdin: Path | None = None,
    stdout: Path | None = None,
) -> bytes:
    with (
        open(stdin, "rb") if stdin else open(os.devnull, "rb") as source,
        open(stdout, "wb") if stdout else open(os.devnull, "wb") as sink,
    ):
        completed = subprocess.run(
            list(argv),
            env=dict(env),
            stdin=source,
            stdout=sink if stdout else subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    if completed.returncode != 0:
        raise RuntimeError(
            f"{argv[0]} exited {completed.returncode}: {completed.stderr.decode(errors='replace')}"
        )
    return completed.stdout or b""


def pg_env(environ: Mapping[str, str]) -> dict[str, str]:
    """The libpq connection variables (and nothing else) from `environ`."""
    return {k: environ[k] for k in _PG_VARIABLES if k in environ}


def dump_databases(
    runner: CommandRunner, databases: Iterable[str], dest: Path, env: Mapping[str, str]
) -> dict[str, int]:
    """Writes `<database>.dump` (custom format) into `dest` for each database; returns bytes."""
    dest.mkdir(parents=True, exist_ok=True)
    sizes: dict[str, int] = {}
    for database in databases:
        final = dest / f"{database}.dump"
        partial = dest / f"{database}.dump.partial"
        try:
            runner(["pg_dump", "--format=custom", f"--dbname={database}"], env, stdout=partial)
        except BaseException:
            partial.unlink(missing_ok=True)
            raise
        os.replace(partial, final)
        sizes[database] = final.stat().st_size
    return sizes


def table_count(runner: CommandRunner, database: str, env: Mapping[str, str]) -> int:
    query = (
        "SELECT count(*) FROM pg_catalog.pg_tables "
        "WHERE schemaname NOT IN ('pg_catalog', 'information_schema')"
    )
    out = runner(["psql", "--no-psqlrc", "-At", f"--dbname={database}", "-c", query], env)
    return int(out.decode().strip())


def restore_database(
    runner: CommandRunner, database: str, dump: Path, env: Mapping[str, str]
) -> None:
    runner(["pg_restore", "--exit-on-error", f"--dbname={database}"], env, stdin=dump)

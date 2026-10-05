from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from .pipeline import RunResult
from .sources import SourceEntry, SourcesConfig


@dataclass(frozen=True)
class DagConfig:
    dag_id: str
    schedule: str
    catchup: bool
    max_active_runs: int
    source_type: str
    task_callable: Callable[[], None]


def build_dags(
    config: SourcesConfig,
    pipeline_factory: Callable[[SourceEntry], Any],
    *,
    get_var: Callable[[str, str | None], str | None] | None = None,
    set_var: Callable[[str, str], None] | None = None,
    now: Callable[[], datetime] | None = None,
) -> list[DagConfig]:
    # dags/auspex_dags.py wraps each DagConfig into an airflow.DAG; this module never imports Airflow.
    _get = get_var or _airflow_get_var
    _set = set_var or _airflow_set_var
    _now = now or (lambda: datetime.now(UTC))

    return [
        DagConfig(
            dag_id=f"auspex_{entry.source_type}",
            schedule=entry.schedule,
            catchup=False,
            max_active_runs=1,
            source_type=entry.source_type,
            task_callable=_make_task(entry, pipeline_factory(entry), _get, _set, _now),
        )
        for entry in config.sources
    ]


def _make_task(
    entry: SourceEntry,
    pipeline: Any,
    get_var: Callable[[str, str | None], str | None],
    set_var: Callable[[str, str], None],
    now: Callable[[], datetime],
) -> Callable[[], None]:
    def _task() -> None:
        run_with_cursor(
            source_type=entry.source_type,
            initial_lookback=entry.initial_lookback,
            pipeline=pipeline,
            get_var=get_var,
            set_var=set_var,
            now=now,
        )

    return _task


def run_with_cursor(
    *,
    source_type: str,
    initial_lookback: int,
    pipeline: Any,
    get_var: Callable[[str, str | None], str | None],
    set_var: Callable[[str, str], None],
    now: Callable[[], datetime],
) -> RunResult:
    cursor_key = f"cursor:{source_type}"
    cursor_str = get_var(cursor_key, None)
    cursor = (
        datetime.fromisoformat(cursor_str)
        if cursor_str
        else now() - timedelta(days=initial_lookback)
    )

    result: RunResult = pipeline.run(source_type, cursor)

    if result.max_published_date_processed is not None:
        set_var(cursor_key, result.max_published_date_processed.isoformat())

    return result


def load_sources_config(path: Path) -> SourcesConfig:
    data = yaml.safe_load(path.read_text())
    return SourcesConfig.model_validate(data)


def _airflow_get_var(key: str, default_var: str | None) -> str | None:
    from airflow.sdk import Variable  # type: ignore[import-not-found]  # deferred: not in dev deps
    value = Variable.get(key, default_var=default_var)
    return str(value) if value is not None else None


def _airflow_set_var(key: str, value: str) -> None:
    from airflow.sdk import Variable  # deferred: not in dev deps
    Variable.set(key, value)

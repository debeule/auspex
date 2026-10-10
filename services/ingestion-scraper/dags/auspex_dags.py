"""One DAG per `sources.yaml` entry, each calling the scraper's `/ingest/<source_type>`.

The task owns the cursor (Variable `cursor:{source_type}`): it saves the `next_cursor` the scraper
reports, which never passes a document that failed, and then fails the run if any document
failed, so it retries and alerts. A request that errors leaves the Variable untouched.
"""
from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import requests
import yaml
from airflow import DAG  # type: ignore[import-untyped]
from airflow.operators.python import PythonOperator  # type: ignore[import-untyped]
from airflow.sdk import Variable  # type: ignore[import-untyped]

_CONFIG_PATH = Path(os.environ.get("AUSPEX_SOURCES_YAML", "/opt/airflow/config/sources.yaml"))
_SCRAPER_URL = os.environ.get("SCRAPER_API_URL", "http://ingestion-scraper:8000")
# One slot, created by the airflow service's start command: one run at a time talks to the
# model server, also when every missed run fires at once after the Mac wakes.
_POOL = "ingestion"
# A run's extraction cap (`max_documents_per_run`) is sized to finish inside this.
_TASK_TIMEOUT = timedelta(hours=3)


def _load_sources() -> list[dict]:
    return yaml.safe_load(_CONFIG_PATH.read_text()).get("sources", [])


def _make_http_task(source_type: str, initial_lookback: int) -> None:
    cursor = Variable.get(f"cursor:{source_type}", default_var=None)
    if cursor is None:
        cursor = (datetime.now(UTC) - timedelta(days=initial_lookback)).isoformat()
    resp = requests.post(
        f"{_SCRAPER_URL}/ingest/{source_type}",
        json={"cursor": cursor},
        timeout=_TASK_TIMEOUT.total_seconds(),
    )
    resp.raise_for_status()
    result = resp.json()
    if result.get("next_cursor"):
        Variable.set(f"cursor:{source_type}", result["next_cursor"])
    if result.get("failed"):
        raise RuntimeError(
            f"{result['failed']} documents failed; cursor kept at {result.get('next_cursor')}"
        )


for _source in _load_sources():
    _source_type = _source["source_type"]
    _initial_lookback = _source.get("initial_lookback", 7)

    with DAG(
        dag_id=f"auspex_{_source_type}",
        schedule=_source.get("schedule"),
        catchup=False,
        max_active_runs=1,
        start_date=datetime(2024, 1, 1, tzinfo=UTC),
        tags=["auspex"],
    ) as _dag:
        PythonOperator(
            task_id="run_ingestion",
            python_callable=_make_http_task,
            op_kwargs={"source_type": _source_type, "initial_lookback": _initial_lookback},
            pool=_POOL,
            retries=2,
            retry_delay=timedelta(minutes=15),
            execution_timeout=_TASK_TIMEOUT,
        )
    globals()[f"auspex_{_source_type}"] = _dag

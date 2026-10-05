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


def _load_sources() -> list[dict]:
    return yaml.safe_load(_CONFIG_PATH.read_text()).get("sources", [])


def _make_http_task(source_type: str, initial_lookback: int) -> None:
    cursor = Variable.get(f"cursor:{source_type}", default_var=None)
    if cursor is None:
        cursor = (datetime.now(UTC) - timedelta(days=initial_lookback)).isoformat()
    resp = requests.post(
        f"{_SCRAPER_URL}/ingest/{source_type}",
        json={"cursor": cursor},
        timeout=3600,
    )
    resp.raise_for_status()
    result = resp.json()
    if result.get("max_published_date_processed"):
        Variable.set(f"cursor:{source_type}", result["max_published_date_processed"])


for _source in _load_sources():
    _source_type = _source["source_type"]
    _initial_lookback = _source.get("initial_lookback", 7)

    with DAG(
        dag_id=f"auspex_{_source_type}",
        schedule=_source["schedule"],
        catchup=False,
        max_active_runs=1,
        start_date=datetime(2024, 1, 1, tzinfo=UTC),
        tags=["auspex"],
    ) as _dag:
        PythonOperator(
            task_id="run_ingestion",
            python_callable=_make_http_task,
            op_kwargs={"source_type": _source_type, "initial_lookback": _initial_lookback},
        )
    globals()[f"auspex_{_source_type}"] = _dag

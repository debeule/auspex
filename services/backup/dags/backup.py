"""Backs up Postgres, Neo4j and MinIO into the host backup folder every night.

The backup service does the work; a failed store fails the run, which is retried and shows red in
Airflow, and the previous `last_success.json` stays in place.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import requests
from airflow import DAG  # type: ignore[import-untyped]
from airflow.operators.python import PythonOperator  # type: ignore[import-untyped]


def _run_backup() -> None:
    # The first run copies the whole raw archive; later runs copy only what changed.
    resp = requests.post(f"{os.environ['BACKUP_API_URL']}/backup", timeout=7200)
    if resp.status_code >= 400:
        raise RuntimeError(f"backup failed with HTTP {resp.status_code}: {resp.text}")


with DAG(
    dag_id="auspex_backup",
    schedule="0 3 * * *",
    catchup=False,
    max_active_runs=1,
    start_date=datetime(2026, 1, 1, tzinfo=UTC),
    is_paused_upon_creation=False,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=30)},
    tags=["auspex"],
) as auspex_backup:
    PythonOperator(task_id="run_backup", python_callable=_run_backup)

"""Builds the month's point-in-time stock universe once its first trading session has come.

Runs in the first week of every month, early UTC, before the US open. The first run after the
stack starts also builds every earlier month still missing; later runs that find the month
already stored return without downloading anything.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import requests
from airflow import DAG  # type: ignore[import-untyped]
from airflow.operators.python import PythonOperator  # type: ignore[import-untyped]


def _build_universe() -> None:
    # The first build downloads SEC's bulk archives and every member's price history.
    resp = requests.post(f"{os.environ['PRICE_API_URL']}/universe/build", json={}, timeout=6 * 3600)
    if resp.status_code >= 400:
        raise RuntimeError(f"universe build failed with HTTP {resp.status_code}: {resp.text}")


with DAG(
    dag_id="auspex_universe_build",
    schedule="0 6 1-7 * *",
    catchup=False,
    max_active_runs=1,
    start_date=datetime(2026, 1, 1, tzinfo=UTC),
    is_paused_upon_creation=False,
    default_args={"retries": 3, "retry_delay": timedelta(hours=1)},
    tags=["auspex"],
) as auspex_universe_build:
    PythonOperator(task_id="build_universe", python_callable=_build_universe)

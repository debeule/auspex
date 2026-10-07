"""Extends the price snapshots (watchlist, XBI benchmark, EUR/USD) with each trading day's bar.

Runs after the US close in both summer and winter time. A failed ticker fails the run, so it is
retried and shows red in Airflow; the tickers that did refresh keep their new bars.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import requests
from airflow import DAG  # type: ignore[import-untyped]
from airflow.operators.python import PythonOperator  # type: ignore[import-untyped]


def _refresh_prices() -> None:
    resp = requests.post(f"{os.environ['PRICE_API_URL']}/prices/refresh", json={}, timeout=1800)
    if resp.status_code >= 400:
        raise RuntimeError(f"price refresh failed with HTTP {resp.status_code}: {resp.text}")


with DAG(
    dag_id="auspex_price_refresh",
    schedule="30 22 * * 1-5",
    catchup=False,
    max_active_runs=1,
    start_date=datetime(2026, 1, 1, tzinfo=UTC),
    is_paused_upon_creation=False,
    default_args={"retries": 3, "retry_delay": timedelta(minutes=30)},
    tags=["auspex"],
) as auspex_price_refresh:
    PythonOperator(task_id="refresh_prices", python_callable=_refresh_prices)

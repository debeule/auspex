"""Sends the daily health summary at 07:00 UTC (`health_summary.py`)."""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml
from airflow import DAG  # type: ignore[import-untyped]
from airflow.operators.python import PythonOperator  # type: ignore[import-untyped]

# The folder is mounted below Airflow's DAG folder, which is the only one on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import health_summary


def _send_summary() -> None:
    config = Path(os.environ.get("AUSPEX_SOURCES_YAML", "/opt/airflow/config/sources.yaml"))
    sources = [s["source_type"] for s in yaml.safe_load(config.read_text()).get("sources", [])]
    query = health_summary.prometheus_query(os.environ["PROMETHEUS_URL"])
    summary = health_summary.build_summary(sources, query, datetime.now(UTC))
    subject, body = health_summary.render(summary)
    health_summary.deliver(subject, body, os.environ)


with DAG(
    dag_id="auspex_daily_health",
    schedule="0 7 * * *",
    catchup=False,
    max_active_runs=1,
    start_date=datetime(2026, 1, 1, tzinfo=UTC),
    is_paused_upon_creation=False,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=10)},
    tags=["auspex"],
) as auspex_daily_health:
    PythonOperator(task_id="send_summary", python_callable=_send_summary)

"""Runs the Grafana alert rules' PromQL against synthetic series with `promtool test rules`.

Each Grafana rule is query A, reduced to its last value, firing above 0. Here A becomes a
Prometheus alert `(A) > 0` with the `.env.example` thresholds filled in, so promtool can show it
fires on the failure it names and stays quiet otherwise. Grafana's `for:` is not part of this;
the static config tests check it. CI installs promtool (`.github/workflows/python.yml`); set
`PROMTOOL` to its path to run this elsewhere.
"""

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

# tests/unit/ -> tests/ -> ingestion-scraper/ -> services/ -> auspex/
REPO_ROOT = Path(__file__).resolve().parents[4]
ALERTING = REPO_ROOT / "docker" / "grafana" / "provisioning" / "alerting"

_PROMTOOL = os.environ.get("PROMTOOL") or shutil.which("promtool")
pytestmark = pytest.mark.skipif(
    _PROMTOOL is None and not os.environ.get("CI"),
    reason="promtool not installed; CI runs this",
)

_EXTRACTION = 'dag_id="auspex_biorxiv", task_id="ingest"'


def _env_example() -> dict[str, str]:
    values: dict[str, str] = {}
    for line in (REPO_ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            values[key] = value
    return values


def _prometheus_rules() -> dict[str, Any]:
    env = _env_example()
    rules = []
    for path in sorted(ALERTING.glob("*.yaml")):
        for group in (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("groups", []):
            for rule in group["rules"]:
                (query,) = [q for q in rule["data"] if q["refId"] == "A"]
                expr = re.sub(r"\$\{(\w+)\}", lambda m: env[m.group(1)], query["model"]["expr"])
                rules.append({"alert": rule["title"], "expr": f"({expr}) > 0"})
    return {"groups": [{"name": "grafana", "rules": rules}]}


def _case(
    alert: str, series: dict[str, str], *, at: str, fires: list[dict[str, str]]
) -> dict[str, Any]:
    return {
        "interval": "1m",
        "input_series": [{"series": s, "values": v} for s, v in series.items()],
        "alert_rule_test": [
            {"eval_time": at, "alertname": alert, "exp_alerts": [{"exp_labels": f} for f in fires]}
        ],
    }


_CASES = [
    _case(
        "Scrape Target Down",
        {
            'up{job="postgres", instance="postgres-exporter:9187"}': "0x10",
            'up{job="mac-host", instance="host.docker.internal:9100"}': "0x10",
            'up{job="blackbox-http", instance="http://neo4j:7474/"}': "0x10",
            'up{job="kafka", instance="kafka-exporter:9308"}': "1x10",
        },
        at="5m",
        fires=[{"job": "postgres", "instance": "postgres-exporter:9187"}],
    ),
    _case(
        "Probe Target Down",
        {
            'probe_success{job="blackbox-tcp", instance="postgres:5432"}': "0x10",
            'probe_success{job="blackbox-ollama", instance="http://host.docker.internal:11434/api/version"}': "0x10",
            'probe_success{job="blackbox-http", instance="http://neo4j:7474/"}': "1x10",
        },
        at="5m",
        fires=[{"job": "blackbox-tcp", "instance": "postgres:5432"}],
    ),
    _case(
        "Mac Host Exporter Down",
        {'up{job="mac-host", instance="host.docker.internal:9100"}': "0x10"},
        at="5m",
        fires=[{"job": "mac-host", "instance": "host.docker.internal:9100"}],
    ),
    _case(
        "Docker Disk Low",
        {
            'node_filesystem_avail_bytes{job="node-exporter", fstype="ext4", mountpoint="/var/lib/docker"}': "14x10",
            'node_filesystem_size_bytes{job="node-exporter", fstype="ext4", mountpoint="/var/lib/docker"}': "100x10",
            'node_filesystem_avail_bytes{job="node-exporter", fstype="tmpfs", mountpoint="/tmp"}': "1x10",
            'node_filesystem_size_bytes{job="node-exporter", fstype="tmpfs", mountpoint="/tmp"}': "100x10",
        },
        at="5m",
        fires=[{}],
    ),
    _case(
        "Docker Disk Low",
        {
            'node_filesystem_avail_bytes{job="node-exporter", fstype="ext4", mountpoint="/var/lib/docker"}': "16x10",
            'node_filesystem_size_bytes{job="node-exporter", fstype="ext4", mountpoint="/var/lib/docker"}': "100x10",
        },
        at="5m",
        fires=[],
    ),
    _case(
        "Mac Disk Low",
        {
            'node_filesystem_avail_bytes{job="mac-host", mountpoint="/"}': "9x10",
            'node_filesystem_size_bytes{job="mac-host", mountpoint="/"}': "100x10",
            'node_filesystem_avail_bytes{job="node-exporter", fstype="ext4", mountpoint="/"}': "50x10",
            'node_filesystem_size_bytes{job="node-exporter", fstype="ext4", mountpoint="/"}': "100x10",
        },
        at="5m",
        fires=[{}],
    ),
    _case(
        "VM Memory High",
        {
            'node_memory_MemAvailable_bytes{job="node-exporter"}': "9x10",
            'node_memory_MemTotal_bytes{job="node-exporter"}': "100x10",
        },
        at="5m",
        fires=[{"job": "node-exporter"}],
    ),
    _case(
        "VM Memory High",
        {
            'node_memory_MemAvailable_bytes{job="node-exporter"}': "11x10",
            'node_memory_MemTotal_bytes{job="node-exporter"}': "100x10",
        },
        at="5m",
        fires=[],
    ),
    _case(
        "Container Restarting",
        {
            # Four new start times inside the hour versus three.
            'container_start_time_seconds{name="auspex-core-hub"}': "0x10 1x10 2x10 3x10 4x10",
            'container_start_time_seconds{name="auspex-kafka"}': "0x10 1x10 2x10 3x20",
        },
        at="50m",
        fires=[{"name": "auspex-core-hub"}],
    ),
    _case(
        "Airflow DAG Run Failed",
        {
            # A DAG's first failure creates the series; increase() alone would never see it.
            'airflow_dagrun_duration_seconds_count{dag_id="auspex_price_refresh", state="failed"}': "_x30 1x30",
            'airflow_dagrun_duration_seconds_count{dag_id="auspex_biorxiv", state="success"}': "1x60",
        },
        at="40m",
        fires=[{"dag_id": "auspex_price_refresh"}],
    ),
    _case(
        "Airflow DAG Run Failed",
        {
            'airflow_dagrun_duration_seconds_count{dag_id="auspex_price_refresh", state="failed"}': "1x60 2x60",
        },
        at="90m",
        fires=[{"dag_id": "auspex_price_refresh"}],
    ),
    _case(
        "Airflow DAG Run Failed",
        {
            # An old failure, nothing new for over an hour.
            'airflow_dagrun_duration_seconds_count{dag_id="auspex_price_refresh", state="failed"}': "1x150",
        },
        at="140m",
        fires=[],
    ),
    _case(
        "Price Refresh Stale",
        {'auspex_price_refresh_sessions_since_success{job="price-service"}': "2x10"},
        at="5m",
        fires=[{}],
    ),
    _case(
        "Price Refresh Stale",
        {'auspex_price_refresh_sessions_since_success{job="price-service"}': "1x10"},
        at="5m",
        fires=[],
    ),
    _case(
        "Ollama Down During Extraction",
        {
            'probe_success{job="blackbox-ollama"}': "0x10",
            f"airflow_task_start_total{{{_EXTRACTION}}}": "1x10",
        },
        at="5m",
        fires=[{}],
    ),
    _case(
        "Ollama Down During Extraction",
        {
            # Down while only the price DAG runs, after extraction finished: not an extraction.
            'probe_success{job="blackbox-ollama"}': "0x10",
            f"airflow_task_start_total{{{_EXTRACTION}}}": "1x10",
            f"airflow_task_finish_total{{{_EXTRACTION}, state=\"success\"}}": "1x10",
            'airflow_task_start_total{dag_id="auspex_price_refresh", task_id="refresh_prices"}': "1x10",
        },
        at="5m",
        fires=[],
    ),
    _case(
        "Ollama Down During Extraction",
        {
            # A manual /ingest call outside Airflow still counts as extraction.
            'probe_success{job="blackbox-ollama"}': "0x30",
            'auspex_llm_extraction_calls_total{source_type="biorxiv", result="error"}': "0+1x30",
        },
        at="20m",
        fires=[{}],
    ),
    _case(
        "Ollama Down During Extraction",
        {
            'probe_success{job="blackbox-ollama"}': "1x10",
            f"airflow_task_start_total{{{_EXTRACTION}}}": "1x10",
        },
        at="5m",
        fires=[],
    ),
]


def test_alert_expressions_fire_on_their_failure_and_stay_quiet_otherwise(tmp_path: Path) -> None:
    assert _PROMTOOL, "promtool is required in CI"
    rules = tmp_path / "rules.yml"
    rules.write_text(yaml.safe_dump(_prometheus_rules()), encoding="utf-8")
    tests = tmp_path / "tests.yml"
    tests.write_text(
        yaml.safe_dump({"rule_files": [rules.name], "evaluation_interval": "1m", "tests": _CASES}),
        encoding="utf-8",
    )

    result = subprocess.run(
        [_PROMTOOL, "test", "rules", tests.name],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_every_new_alert_has_a_promtool_case() -> None:
    covered = {c["alert_rule_test"][0]["alertname"] for c in _CASES}
    titles = {r["alert"] for r in _prometheus_rules()["groups"][0]["rules"]}
    preexisting = {"DLT Backlog", "Source Silence", "Kafka Lag Critical", "LLM Extraction Errors"}
    assert titles - preexisting == covered

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
    alert: str,
    series: dict[str, str],
    *,
    at: str,
    fires: list[dict[str, str]],
    interval: str = "1m",
) -> dict[str, Any]:
    return {
        "interval": interval,
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


def _promtool(tmp_path: Path, cases: list[dict[str, Any]]) -> None:
    assert _PROMTOOL, "promtool is required in CI"
    rules = tmp_path / "rules.yml"
    rules.write_text(yaml.safe_dump(_prometheus_rules()), encoding="utf-8")
    tests = tmp_path / "tests.yml"
    # Hour-spaced cases are evaluated hourly; promtool would otherwise step through days by minute.
    intervals = {c["interval"] for c in cases}
    evaluation = intervals.pop() if len(intervals) == 1 else "1m"
    tests.write_text(
        yaml.safe_dump({"rule_files": [rules.name], "evaluation_interval": evaluation, "tests": cases}),
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


def test_alert_expressions_fire_on_their_failure_and_stay_quiet_otherwise(tmp_path: Path) -> None:
    _promtool(tmp_path, _CASES)


# Pipeline rules. A run sets auspex_pipeline_run_last_timestamp to its own time; here a source ran
# at the epoch (value 0), and edgar ran again 24 h later.
_BIORXIV_RUN = 'auspex_pipeline_run_last_timestamp{source_type="biorxiv"}'
_EDGAR_RUN = 'auspex_pipeline_run_last_timestamp{source_type="edgar"}'

_SOURCE_SILENCE_WITHIN_A_DAY = [
    _case("Source Silence", {_BIORXIV_RUN: "0x40"}, at="24h", fires=[], interval="1h"),
]
_SOURCE_SILENCE_AFTER_THIRTY_HOURS = [
    _case(
        "Source Silence",
        {_BIORXIV_RUN: "0x40", _EDGAR_RUN: "0x23 86400x16"},
        at="31h",
        fires=[{"source_type": "biorxiv"}],
        interval="1h",
    ),
]
_SOURCE_SILENCE_GAUGE_MISSING = [
    # The scraper restarted 2 h after biorxiv's last run and has not run it since: no gauge.
    _case("Source Silence", {_BIORXIV_RUN: "0x2 _x40"}, at="20h", fires=[], interval="1h"),
    _case(
        "Source Silence",
        {_BIORXIV_RUN: "0x2 _x40"},
        at="31h",
        fires=[{"source_type": "biorxiv"}],
        interval="1h",
    ),
]
_DOCUMENTS_FAILED = [
    _case(
        "Documents Failed",
        {
            'auspex_pipeline_documents_failed_total{source_type="edgar"}': "0x30 1x30",
            'auspex_pipeline_documents_failed_total{source_type="biorxiv"}': "0x60",
        },
        at="40m",
        fires=[{"source_type": "edgar"}],
    ),
    # A source's first failure creates its series.
    _case(
        "Documents Failed",
        {'auspex_pipeline_documents_failed_total{source_type="edgar"}': "_x30 1x30"},
        at="40m",
        fires=[{"source_type": "edgar"}],
    ),
    # A failure more than a day ago, none since.
    _case(
        "Documents Failed",
        {'auspex_pipeline_documents_failed_total{source_type="edgar"}': "0x60 1x1560"},
        at="1560m",
        fires=[],
    ),
]
_SOURCE_QUIET = [
    _case(
        "Source Quiet",
        {
            'auspex_source_latest_signal_age_seconds{source_type="edgar"}': "518400x10",
            'auspex_source_latest_signal_age_seconds{source_type="biorxiv"}': "345600x10",
        },
        at="5m",
        fires=[{"source_type": "edgar"}],
    ),
]


def _extraction_buckets(slowest_fast_bucket: str) -> dict[str, str]:
    """Every extraction lands in the bucket above `slowest_fast_bucket`."""
    bounds = ["10", "20", "30", "60", "120", "300", "+Inf"]
    first = bounds.index(slowest_fast_bucket) + 1
    return {
        f'auspex_llm_extraction_duration_seconds_bucket{{source_type="biorxiv", le="{le}"}}': (
            "0+1x70" if i >= first else "0x70"
        )
        for i, le in enumerate(bounds)
    }


_EXTRACTION_SLOW = [
    _case("Extraction Slow", _extraction_buckets("60"), at="65m", fires=[{}]),
    _case("Extraction Slow", _extraction_buckets("10"), at="65m", fires=[]),
]
_RAW_TOPIC_LAG = [
    _case(
        "Raw Topic Lag",
        {
            'kafka_consumergroup_lag{consumergroup="corehub", topic="auspex.raw.ingested", partition="0"}': "800x10",
            'kafka_consumergroup_lag{consumergroup="corehub", topic="auspex.raw.ingested", partition="1"}': "700x10",
        },
        at="5m",
        fires=[{}],
    ),
    _case(
        "Raw Topic Lag",
        {
            'kafka_consumergroup_lag{consumergroup="corehub", topic="auspex.raw.ingested", partition="0"}': "900x10",
            'kafka_consumergroup_lag{consumergroup="corehub", topic="auspex.signals.extracted", partition="0"}': "5000x10",
        },
        at="5m",
        fires=[],
    ),
]
_DLT_NOT_EMPTY = [
    _case(
        "DLT Not Empty",
        {
            'auspex_dlt_depth{topic="auspex.signals.extracted.dlt"}': "3x10",
            'auspex_dlt_depth{topic="auspex.raw.ingested.dlt"}': "0x10",
        },
        at="5m",
        fires=[{"topic": "auspex.signals.extracted.dlt"}],
    ),
]
_ES_HEALTH = "elasticsearch_cluster_health_status"
_ES_READ_ONLY = "elasticsearch_indices_settings_stats_read_only_indices"
_ELASTICSEARCH_UNHEALTHY = [
    _case(
        "Elasticsearch Unhealthy",
        {f'{_ES_HEALTH}{{color="red"}}': "1x10", f'{_ES_HEALTH}{{color="green"}}': "0x10", _ES_READ_ONLY: "0x10"},
        at="5m",
        fires=[{}],
    ),
    _case(
        "Elasticsearch Unhealthy",
        {f'{_ES_HEALTH}{{color="red"}}': "0x10", _ES_READ_ONLY: "2x10"},
        at="5m",
        fires=[{}],
    ),
    # A single-node cluster is yellow on any index with replicas; that is normal here.
    _case(
        "Elasticsearch Unhealthy",
        {f'{_ES_HEALTH}{{color="red"}}': "0x10", f'{_ES_HEALTH}{{color="yellow"}}': "1x10", _ES_READ_ONLY: "0x10"},
        at="5m",
        fires=[],
    ),
]
_CORROBORATION_SCAN_FAILING = [
    _case(
        "Corroboration Scan Failing",
        {"auspex_corroboration_scan_failures_total": "0x10 1x10"},
        at="15m",
        fires=[{}],
    ),
    _case("Corroboration Scan Failing", {"auspex_corroboration_scan_failures_total": "0x30"}, at="25m", fires=[]),
    _case("Corroboration Scan Failing", {"auspex_corroboration_scan_failures_total": "1x60"}, at="50m", fires=[]),
]
# promtool evaluates from 1970-01-01T00:00Z, so 168h is 1970-01-08, day 8 of January 1970.
_UNIVERSE_MONTH_MISSING = [
    _case("Universe Month Missing", {"auspex_universe_latest_month": "196912x200"}, at="167h", fires=[], interval="1h"),
    _case("Universe Month Missing", {"auspex_universe_latest_month": "196912x200"}, at="168h", fires=[{}], interval="1h"),
    _case("Universe Month Missing", {"auspex_universe_latest_month": "0x200"}, at="168h", fires=[{}], interval="1h"),
    _case("Universe Month Missing", {"auspex_universe_latest_month": "197001x200"}, at="168h", fires=[], interval="1h"),
]

_PIPELINE_CASES = (
    _SOURCE_SILENCE_WITHIN_A_DAY
    + _SOURCE_SILENCE_AFTER_THIRTY_HOURS
    + _SOURCE_SILENCE_GAUGE_MISSING
    + _DOCUMENTS_FAILED
    + _SOURCE_QUIET
    + _EXTRACTION_SLOW
    + _RAW_TOPIC_LAG
    + _DLT_NOT_EMPTY
    + _ELASTICSEARCH_UNHEALTHY
    + _CORROBORATION_SCAN_FAILING
    + _UNIVERSE_MONTH_MISSING
)


def test_source_silence_stays_quiet_within_a_day_of_the_last_run(tmp_path: Path) -> None:
    _promtool(tmp_path, _SOURCE_SILENCE_WITHIN_A_DAY)


def test_source_silence_fires_after_thirty_hours_without_a_run(tmp_path: Path) -> None:
    _promtool(tmp_path, _SOURCE_SILENCE_AFTER_THIRTY_HOURS)


def test_source_silence_fires_when_the_run_gauge_has_been_missing_for_thirty_hours(
    tmp_path: Path,
) -> None:
    _promtool(tmp_path, _SOURCE_SILENCE_GAUGE_MISSING)


def test_documents_failed_fires_on_any_failed_document_in_a_day(tmp_path: Path) -> None:
    _promtool(tmp_path, _DOCUMENTS_FAILED)


def test_source_quiet_fires_after_the_configured_days_without_a_signal(tmp_path: Path) -> None:
    assert _env_example()["ALERT_SOURCE_QUIET_DAYS"] == "5"
    _promtool(tmp_path, _SOURCE_QUIET)


def test_extraction_slow_fires_above_the_configured_p95(tmp_path: Path) -> None:
    assert _env_example()["ALERT_EXTRACTION_P95_SECONDS"] == "60"
    _promtool(tmp_path, _EXTRACTION_SLOW)


def test_raw_topic_lag_fires_above_one_thousand(tmp_path: Path) -> None:
    _promtool(tmp_path, _RAW_TOPIC_LAG)


def test_dlt_not_empty_fires_after_an_hour_of_depth(tmp_path: Path) -> None:
    _promtool(tmp_path, _DLT_NOT_EMPTY)
    # The hour is Grafana's pending period, which promtool does not model.
    assert _grafana_rules()["DLT Not Empty"]["for"] == "1h"


def test_elasticsearch_unhealthy_fires_on_red_or_read_only(tmp_path: Path) -> None:
    _promtool(tmp_path, _ELASTICSEARCH_UNHEALTHY)


def test_corroboration_scan_failing_fires_on_any_failure(tmp_path: Path) -> None:
    _promtool(tmp_path, _CORROBORATION_SCAN_FAILING)


def test_universe_month_missing_fires_from_day_eight(tmp_path: Path) -> None:
    _promtool(tmp_path, _UNIVERSE_MONTH_MISSING)


def _grafana_rules() -> dict[str, dict[str, Any]]:
    return {
        rule["title"]: rule
        for path in sorted(ALERTING.glob("*.yaml"))
        for group in (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("groups", [])
        for rule in group["rules"]
    }


def test_every_new_alert_has_a_promtool_case() -> None:
    covered = {c["alert_rule_test"][0]["alertname"] for c in _CASES + _PIPELINE_CASES}
    titles = {r["alert"] for r in _prometheus_rules()["groups"][0]["rules"]}
    preexisting = {"DLT Backlog", "Kafka Lag Critical", "LLM Extraction Errors"}
    assert titles - preexisting == covered

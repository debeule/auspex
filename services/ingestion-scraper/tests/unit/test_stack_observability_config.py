"""Static checks on the compose stack's monitoring: exporters, scrape jobs, alerts and routing.

Parses `docker/docker-compose.yml`, `docker/prometheus/` and `docker/grafana/provisioning/`;
no container is started. What only a running stack can show is in
`docker/grafana/test_provisioning.sh`.
"""

import json
import re
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

# tests/unit/ -> tests/ -> ingestion-scraper/ -> services/ -> auspex/
REPO_ROOT = Path(__file__).resolve().parents[4]
DOCKER = REPO_ROOT / "docker"
ALERTING = DOCKER / "grafana" / "provisioning" / "alerting"

# Docker Desktop's VM allocation (SETUP.md step 2), less what the VM's own kernel and daemons use.
_DOCKER_DESKTOP_MIB = 8 * 1024
_VM_RESERVE_MIB = 512

# A bare `${VAR}`: the value lives only in `.env.example`, never as a second copy in compose.
_PLACEHOLDER = re.compile(r"^\$\{(?P<var>[A-Z0-9_]+)\}$")
# What Grafana's provisioning passes to os.ExpandEnv after splitting on the `$$` escape.
_ENV_REF = re.compile(r"\$\{?(?P<var>[A-Za-z_][A-Za-z0-9_]*)\}?")
_EXACT_TAG = re.compile(r"\d+\.\d+|\d{4}-\d{2}-\d{2}")


def _compose() -> dict[str, Any]:
    return yaml.safe_load((DOCKER / "docker-compose.yml").read_text(encoding="utf-8"))


def _services() -> dict[str, dict[str, Any]]:
    return _compose()["services"]


def _env_example() -> dict[str, str]:
    values: dict[str, str] = {}
    for line in (REPO_ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    return values


def _resolve(value: str) -> str:
    """A compose value with `${VAR}` / `${VAR:-default}` replaced from `.env.example`."""
    env = _env_example()

    def sub(m: re.Match[str]) -> str:
        var, _, default = m.group(1).partition(":-")
        return env.get(var) or default

    return re.sub(r"\$\{([^}]+)\}", sub, value)


def _prometheus() -> dict[str, Any]:
    return yaml.safe_load((DOCKER / "prometheus" / "prometheus.yml").read_text(encoding="utf-8"))


def _jobs() -> dict[str, dict[str, Any]]:
    return {job["job_name"]: job for job in _prometheus()["scrape_configs"]}


def _targets(job: dict[str, Any]) -> list[str]:
    return [t for sc in job.get("static_configs", []) for t in sc["targets"]]


def _target_host(target: str) -> str:
    if "://" in target:
        return urlparse(target).hostname or ""
    return target.rsplit(":", 1)[0]


def _long_running(service: dict[str, Any]) -> bool:
    return service.get("restart") != "no"


def _rules() -> dict[str, dict[str, Any]]:
    rules: dict[str, dict[str, Any]] = {}
    for path in sorted(ALERTING.glob("*.yaml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for group in doc.get("groups", []):
            for rule in group["rules"]:
                rules[rule["title"]] = rule
    return rules


def _rule_exprs(rule: dict[str, Any]) -> str:
    return " ".join(q["model"].get("expr", "") for q in rule["data"])


def _mib(size: str) -> int:
    m = re.fullmatch(r"(\d+)([mg])", size.strip().lower())
    assert m, f"memory size {size!r} is not like 512m or 2g"
    return int(m.group(1)) * (1024 if m.group(2) == "g" else 1)


def _provisioning_doc(name: str) -> dict[str, Any]:
    return yaml.safe_load((ALERTING / name).read_text(encoding="utf-8"))


def _dashboard(uid: str) -> dict[str, Any]:
    for path in (DOCKER / "grafana" / "provisioning" / "dashboards").glob("*.json"):
        doc = json.loads(path.read_text(encoding="utf-8"))
        if doc.get("uid") == uid:
            return doc
    raise AssertionError(f"no provisioned dashboard with uid {uid}")


def _panel_exprs(panel: dict[str, Any]) -> str:
    return " ".join(t.get("expr", "") for t in panel.get("targets", []))


def test_every_compose_service_with_a_healthcheck_is_scraped_or_probed() -> None:
    covered = {_target_host(t) for job in _jobs().values() for t in _targets(job)}
    services = _services()
    exporters = {
        name for name, svc in services.items()
        if "exporter" in name or "cadvisor" in name
    }
    must_be_seen = {name for name, svc in services.items() if "healthcheck" in svc} | exporters

    assert {"neo4j", "kafka", "postgres", "elasticsearch", "airflow"} <= must_be_seen
    assert sorted(must_be_seen - covered) == []
    # A health probe does not read a service's own metrics; these three expose /metrics.
    jobs = _jobs()
    assert _targets(jobs["price-service"]) == ["price-service:8001"]
    assert jobs["price-service"]["metrics_path"] == "/metrics"
    assert _targets(jobs["ingestion-scraper"]) == ["ingestion-scraper:8000"]
    assert _targets(jobs["core-hub"]) == ["core-hub:8080"]


def test_every_new_image_is_pinned_to_an_exact_tag() -> None:
    for name, svc in _services().items():
        if "build" in svc:
            continue
        image = _resolve(svc["image"])
        _, _, tag = image.rpartition(":")
        assert ":" in image and "@" not in tag, f"{name}: {image} has no tag"
        assert tag not in {"latest", "master", "main", "stable"}, f"{name}: {image} floats"
        assert _EXACT_TAG.search(tag), f"{name}: {image} is not an exact version"
        versions = (REPO_ROOT / "VERSIONS.md").read_text(encoding="utf-8")
        assert tag in versions, f"{name}: {image} missing from VERSIONS.md"


def _limit_var(name: str, svc: dict[str, Any]) -> str:
    limit = svc.get("mem_limit")
    assert limit is not None, f"{name} has no mem_limit"
    m = _PLACEHOLDER.match(str(limit))
    assert m, f"{name}: mem_limit {limit!r} is not an .env placeholder"
    return m.group("var")


def test_every_service_has_a_memory_limit() -> None:
    env = _env_example()
    for name, svc in _services().items():
        var = _limit_var(name, svc)
        assert env.get(var), f"{name}: {var} not set in .env.example"


def test_long_running_memory_limits_fit_the_vm_budget() -> None:
    env = _env_example()
    services = _services()
    long_running = {name: _mib(env[_limit_var(name, svc)])
                    for name, svc in services.items() if _long_running(svc)}

    assert "dashboard" in long_running
    assert sum(long_running.values()) <= _DOCKER_DESKTOP_MIB - _VM_RESERVE_MIB, (
        f"long-running services may use {sum(long_running.values())} MiB, more than the Docker Desktop VM"
    )


def test_prometheus_retention_is_bounded_by_time_and_size() -> None:
    command = " ".join(_services()["prometheus"]["command"])
    env = _env_example()

    time_flag = re.search(r"--storage\.tsdb\.retention\.time=(\S+)", command)
    size_flag = re.search(r"--storage\.tsdb\.retention\.size=(\S+)", command)
    assert time_flag and size_flag
    for flag, var in ((time_flag, "PROMETHEUS_RETENTION_TIME"), (size_flag, "PROMETHEUS_RETENTION_SIZE")):
        m = _PLACEHOLDER.match(flag.group(1))
        assert m and m.group("var") == var and env.get(var), f"{flag.group(0)} not from .env"
    assert re.fullmatch(r"\d+[dwy]", env["PROMETHEUS_RETENTION_TIME"])
    assert re.fullmatch(r"\d+(MB|GB)", env["PROMETHEUS_RETENTION_SIZE"])
    # A command override drops the image's defaults, so the config file must be named again.
    assert "--config.file=/etc/prometheus/prometheus.yml" in command


def test_mac_host_job_targets_host_docker_internal_node_exporter() -> None:
    job = _jobs()["mac-host"]
    assert _targets(job) == ["host.docker.internal:9100"]
    assert "host.docker.internal:host-gateway" in _services()["prometheus"]["extra_hosts"]
    # The job may be down: only the info alert names it, the general target-down rule does not.
    down = _rules()["Scrape Target Down"]
    assert 'job!~"mac-host' in _rule_exprs(down).replace(" ", "")
    info = _rules()["Mac Host Exporter Down"]
    assert 'up{job="mac-host"}' in _rule_exprs(info)
    assert info["labels"]["severity"] == "info"


def test_ollama_is_probed_by_blackbox() -> None:
    job = _jobs()["blackbox-ollama"]
    assert job["metrics_path"] == "/probe"
    assert _targets(job) == ["http://host.docker.internal:11434/api/version"]
    relabels = job["relabel_configs"]
    assert {"source_labels": ["__address__"], "target_label": "__param_target"} in relabels
    assert {"target_label": "__address__", "replacement": "blackbox-exporter:9115"} in relabels
    assert "host.docker.internal:host-gateway" in _services()["blackbox-exporter"]["extra_hosts"]


def test_contact_point_and_default_policy_are_provisioned() -> None:
    contact = _provisioning_doc("contactpoints.yaml")["contactPoints"]
    assert [c["name"] for c in contact] == ["auspex-default"]

    policies = _provisioning_doc("policies.yaml")["policies"]
    assert len(policies) == 1
    assert policies[0]["receiver"] == "auspex-default"
    assert policies[0]["orgId"] == 1


def test_contact_point_settings_come_from_env_placeholders() -> None:
    (contact,) = _provisioning_doc("contactpoints.yaml")["contactPoints"]
    (receiver,) = contact["receivers"]
    env = _env_example()
    grafana_env = _services()["grafana"]["environment"]

    assert receiver["type"] == "${ALERT_CONTACT_TYPE}"
    assert env["ALERT_CONTACT_TYPE"] == "email"
    for value in receiver["settings"].values():
        m = _PLACEHOLDER.match(value)
        assert m, f"contact setting {value!r} is not an env placeholder"
    referenced = {_PLACEHOLDER.match(v).group("var") for v in receiver["settings"].values()}  # type: ignore[union-attr]
    assert {"ALERT_EMAIL_ADDRESSES", "ALERT_WEBHOOK_URL"} <= referenced
    for var in referenced | {"ALERT_CONTACT_TYPE"}:
        assert var in env, f"{var} not in .env.example"
        assert grafana_env[var] == f"${{{var}}}", f"grafana does not receive {var} from .env"
    for smtp in ("GF_SMTP_HOST", "GF_SMTP_USER", "GF_SMTP_PASSWORD", "GF_SMTP_FROM_ADDRESS"):
        m = _PLACEHOLDER.match(grafana_env[smtp])
        assert m and m.group("var") in env, f"{smtp} not from .env"


def test_alert_rules_exist_for_target_down_disk_memory_restarts_dag_failure_and_price_refresh() -> (
    None
):
    rules = _rules()
    expected = {
        "Scrape Target Down": "up{",
        "Probe Target Down": "probe_success",
        "Docker Disk Low": "node_filesystem_avail_bytes",
        "Mac Disk Low": 'node_filesystem_avail_bytes{job="mac-host"',
        "VM Memory High": "node_memory_MemAvailable_bytes",
        "Container Restarting": "container_start_time_seconds",
        "Airflow DAG Run Failed": 'airflow_dagrun_duration_seconds_count{state="failed"}',
        "Price Refresh Stale": "auspex_price_refresh_sessions_since_success",
        "Ollama Down During Extraction": 'probe_success{job="blackbox-ollama"}',
    }
    for title, metric in expected.items():
        assert title in rules, f"missing alert rule {title!r}"
        assert metric in _rule_exprs(rules[title]), f"{title} does not query {metric}"

    assert rules["Scrape Target Down"]["for"] == "5m"
    assert rules["Probe Target Down"]["for"] == "5m"
    assert rules["VM Memory High"]["for"] == "10m"
    assert "[1h]" in _rule_exprs(rules["Container Restarting"])
    assert "airflow_task_start_total" in _rule_exprs(rules["Ollama Down During Extraction"])
    # Ollama has its own rule; the general probe rule must not page twice for it.
    assert 'job!="blackbox-ollama"' in _rule_exprs(rules["Probe Target Down"])

    env = _env_example()
    thresholds = {
        "Docker Disk Low": "ALERT_DOCKER_DISK_FREE_MIN_PCT",
        "Mac Disk Low": "ALERT_MAC_DISK_FREE_MIN_PCT",
        "VM Memory High": "ALERT_VM_MEMORY_MAX_PCT",
        "Container Restarting": "ALERT_CONTAINER_RESTARTS_MAX_PER_HOUR",
        "Price Refresh Stale": "ALERT_PRICE_REFRESH_MAX_MISSED_SESSIONS",
    }
    grafana_env = _services()["grafana"]["environment"]
    for title, var in thresholds.items():
        assert f"${{{var}}}" in _rule_exprs(rules[title]), f"{title} threshold not from {var}"
        assert env[var].isdigit(), f"{var} must be a number in .env.example"
        assert grafana_env[var] == f"${{{var}}}", f"grafana does not receive {var}"
    assert (env["ALERT_DOCKER_DISK_FREE_MIN_PCT"], env["ALERT_MAC_DISK_FREE_MIN_PCT"]) == ("15", "10")
    assert (env["ALERT_VM_MEMORY_MAX_PCT"], env["ALERT_CONTAINER_RESTARTS_MAX_PER_HOUR"]) == ("90", "3")
    assert env["ALERT_PRICE_REFRESH_MAX_MISSED_SESSIONS"] == "2"


def test_alert_expressions_reference_only_env_vars_grafana_receives() -> None:
    """Grafana expands `$VAR` in provisioned rules; an unknown name silently becomes empty."""
    grafana_env = set(_services()["grafana"]["environment"])
    for title, rule in _rules().items():
        text = " ".join([_rule_exprs(rule), *rule.get("annotations", {}).values()])
        for var in _ENV_REF.findall(text.replace("$$", "")):
            assert var in grafana_env, f"{title} references ${var}, which grafana is not given"


def test_infrastructure_dashboard_is_provisioned_with_service_grid_and_disk_panels() -> None:
    dash = _dashboard("auspex-infrastructure")
    assert dash["title"] == "Auspex Infrastructure"
    panels = {p["title"]: p for p in dash["panels"]}

    grid = panels["Service status"]
    assert "probe_success" in _panel_exprs(grid) and "up{" in _panel_exprs(grid)
    assert 'job="mac-host"' in _panel_exprs(panels["Mac disk free"])
    assert 'job="node-exporter"' in _panel_exprs(panels["Docker disk free"])
    assert "auspex_volume_bytes" in _panel_exprs(panels["Volume size"])
    for title, metric in {
        "Mac CPU": 'node_cpu_seconds_total{job="mac-host"',
        "Mac memory": 'node_memory_total_bytes{job="mac-host"',
        "VM CPU": 'node_cpu_seconds_total{job="node-exporter"',
        "VM memory": 'node_memory_MemAvailable_bytes{job="node-exporter"',
        "Container memory": "container_memory_working_set_bytes",
        "Container restarts": "container_start_time_seconds",
        "Postgres connections": "pg_stat_database_numbackends",
        "Postgres database size": "pg_database_size_bytes",
        "Kafka consumer lag": "kafka_consumergroup_lag",
        "Elasticsearch disk free": "elasticsearch_filesystem_data_available_bytes",
        "Airflow DAG runs": "airflow_dagrun_duration_seconds_count",
    }.items():
        assert metric in _panel_exprs(panels[title]), f"{title} does not query {metric}"
    for panel in dash["panels"]:
        for target in panel.get("targets", []):
            assert target["datasource"]["uid"] == "prometheus", f"{panel['title']}: datasource"


def test_airflow_statsd_is_enabled_and_mapped_to_dag_outcome_metrics() -> None:
    env = _services()["airflow"]["environment"]
    assert env["AIRFLOW__METRICS__STATSD_ON"] == "true"
    assert env["AIRFLOW__METRICS__STATSD_HOST"] == "statsd-exporter"
    assert env["AIRFLOW__METRICS__STATSD_PREFIX"] == "airflow"

    exporter = _services()["statsd-exporter"]
    port = env["AIRFLOW__METRICS__STATSD_PORT"]
    assert f"--statsd.listen-udp=:{port}" in exporter["command"]
    assert "--statsd.mapping-config=/etc/statsd/mapping.yml" in exporter["command"]
    assert _targets(_jobs()["airflow"]) == ["statsd-exporter:9102"]

    mappings = {
        m["match"]: m
        for m in yaml.safe_load(
            (DOCKER / "statsd-exporter" / "mapping.yml").read_text(encoding="utf-8")
        )["mappings"]
    }
    for state in ("success", "failed"):
        m = mappings[f"airflow.dagrun.duration.{state}.*"]
        assert m["name"] == "airflow_dagrun_duration_seconds"
        assert m["labels"] == {"dag_id": "$1", "state": state}
    finish = mappings["airflow.ti.finish.*.*.*"]
    assert finish["name"] == "airflow_task_finish_total"
    assert finish["labels"] == {"dag_id": "$1", "task_id": "$2", "state": "$3"}
    start = mappings["airflow.ti.start.*.*"]
    assert start["name"] == "airflow_task_start_total"
    assert start["labels"] == {"dag_id": "$1", "task_id": "$2"}


def test_every_service_is_labelled_for_log_shipping() -> None:
    for name, svc in _services().items():
        labels = svc.get("labels") or {}
        assert labels.get("co.elastic.logs/enabled") in {"true", "false"}, f"{name} not labelled"


def test_exporter_credentials_are_a_monitoring_role_not_the_app_owner() -> None:
    exporter = _services()["postgres-exporter"]["environment"]
    assert exporter["DATA_SOURCE_USER"] == "${POSTGRES_MONITOR_USER}"
    assert exporter["DATA_SOURCE_PASS"] == "${POSTGRES_MONITOR_PASSWORD}"
    role_init = _services()["postgres-monitor-role"]
    assert role_init["restart"] == "no"
    assert _services()["postgres-exporter"]["depends_on"]["postgres-monitor-role"] == {
        "condition": "service_completed_successfully"
    }
    script = (DOCKER / "postgres-monitor" / "create-role.sh").read_text(encoding="utf-8")
    assert "GRANT pg_monitor TO" in script
    assert "SUPERUSER" not in script.upper().replace("NOSUPERUSER", "")


def test_minio_metrics_are_public_on_the_internal_network_only() -> None:
    minio = _services()["minio"]
    assert minio["environment"]["MINIO_PROMETHEUS_AUTH_TYPE"] == "public"
    job = _jobs()["minio"]
    assert job["metrics_path"] == "/minio/v2/metrics/cluster"
    assert _targets(job) == ["minio:9000"]


def test_new_exporters_publish_no_host_ports() -> None:
    for name in (
        "node-exporter", "cadvisor", "postgres-exporter", "kafka-exporter",
        "elasticsearch-exporter", "blackbox-exporter", "statsd-exporter", "volume-usage",
    ):
        for port in _services()[name].get("ports", []):
            assert str(port).startswith("127.0.0.1:"), f"{name} publishes {port} beyond localhost"


def test_volume_usage_reports_each_mounted_volume_in_bytes(tmp_path: Path) -> None:
    volumes = tmp_path / "volumes"
    (volumes / "postgres_data").mkdir(parents=True)
    (volumes / "postgres_data" / "base").write_bytes(b"x" * 5000)
    (volumes / "minio_data").mkdir()
    out = tmp_path / "textfile" / "volumes.prom"
    out.parent.mkdir()

    subprocess.run(
        ["sh", str(DOCKER / "volume-usage" / "collect.sh"), "--once"],
        env={"VOLUMES_DIR": str(volumes), "OUTPUT_FILE": str(out), "PATH": "/usr/bin:/bin"},
        check=True,
        timeout=30,
    )

    lines = out.read_text(encoding="utf-8").splitlines()
    assert "# TYPE auspex_volume_bytes gauge" in lines
    samples = {
        m.group(1): int(m.group(2))
        for line in lines
        if (m := re.fullmatch(r'auspex_volume_bytes\{volume="([^"]+)"\} (\d+)', line))
    }
    assert set(samples) == {"postgres_data", "minio_data"}
    assert samples["postgres_data"] >= 5000
    assert samples["minio_data"] < samples["postgres_data"]
    assert not list(out.parent.glob("*.tmp")), "partial file left next to the output"


def test_volume_usage_mounts_every_named_volume() -> None:
    compose = _compose()
    mounts = _services()["volume-usage"]["volumes"]
    mounted = {m.split(":")[0] for m in mounts}
    assert set(compose["volumes"]) - {"volume_usage_textfile"} <= mounted
    for m in mounts:
        if m.split(":")[0] in compose["volumes"] and m.split(":")[0] != "volume_usage_textfile":
            assert m.endswith(":ro"), f"{m} must be read-only"
    node = _services()["node-exporter"]
    assert "--collector.textfile.directory=/textfile" in node["command"]
    assert "volume_usage_textfile:/textfile:ro" in node["volumes"]


# Every rotated file is kept at most this long per container: max-size x max-file.
_LOG_CAP_MIB = 60
# Paths only health checks and probes request; their access-log lines carry no information.
_HEALTH_PATHS = (
    "/health",
    "/actuator/health",
    "/api/v2/monitor/health",
    "/-/healthy",
    "/api/health",
    "/minio/health/live",
)


def _logging_options(name: str, svc: dict[str, Any]) -> dict[str, str]:
    logging = svc.get("logging")
    assert logging, f"{name} has no logging setting"
    return {key: _resolve(str(value)) for key, value in logging.get("options", {}).items()}


def _filebeat() -> dict[str, Any]:
    return yaml.safe_load((DOCKER / "filebeat" / "filebeat.yml").read_text(encoding="utf-8"))


def _matches(condition: dict[str, Any], event: dict[str, str]) -> bool:
    """Evaluates the subset of Filebeat conditions the drop processor uses: `or` and `regexp`."""
    if "or" in condition:
        return any(_matches(c, event) for c in condition["or"])
    if "regexp" in condition:
        return all(re.search(pattern, event.get(field, "")) is not None
                   for field, pattern in condition["regexp"].items())
    raise AssertionError(f"unsupported condition {condition}")


def _dropped(event: dict[str, str]) -> bool:
    drops = [p["drop_event"] for p in _filebeat()["processors"] if "drop_event" in p]
    assert drops, "filebeat has no drop_event processor"
    return any(_matches(d["when"], event) for d in drops)


def test_every_service_uses_the_shared_rotating_log_driver() -> None:
    compose = _compose()
    shared = compose["x-logging"]
    assert shared["driver"] == "json-file"
    for name, svc in compose["services"].items():
        assert svc.get("logging") == shared, f"{name} does not use the shared x-logging setting"
    text = (DOCKER / "docker-compose.yml").read_text(encoding="utf-8")
    assert text.count("logging: *logging") == len(compose["services"])


def test_log_rotation_caps_each_container_at_sixty_megabytes() -> None:
    for name, svc in _services().items():
        options = _logging_options(name, svc)
        size = re.fullmatch(r"(\d+)m", options["max-size"])
        assert size, f"{name}: max-size {options['max-size']!r} is not in megabytes"
        assert int(size.group(1)) * int(options["max-file"]) <= _LOG_CAP_MIB, name


def test_neo4j_heap_and_page_cache_fit_within_its_limit() -> None:
    env = _env_example()
    neo4j = _services()["neo4j"]
    environment = neo4j["environment"]
    heap = _resolve(environment["NEO4J_server_memory_heap_max__size"])
    assert _resolve(environment["NEO4J_server_memory_heap_initial__size"]) == heap
    pagecache = _resolve(environment["NEO4J_server_memory_pagecache_size"])
    limit = _mib(env[_limit_var("neo4j", neo4j)])

    assert (_mib(heap) + _mib(pagecache)) * 4 <= limit * 3


def test_airflow_runs_one_api_worker_and_at_most_four_tasks() -> None:
    environment = _services()["airflow"]["environment"]

    assert _resolve(environment["AIRFLOW__API__WORKERS"]) == "1"
    assert 1 <= int(_resolve(environment["AIRFLOW__CORE__PARALLELISM"])) <= 4


def test_log_indices_are_deleted_after_thirty_days() -> None:
    policy = json.loads((DOCKER / "elasticsearch" / "ilm_policy.json").read_text(encoding="utf-8"))
    delete = policy["policy"]["phases"]["delete"]

    assert delete["min_age"] == "30d"
    assert "delete" in delete["actions"]


def test_filebeat_drops_healthcheck_access_lines() -> None:
    for path in _HEALTH_PATHS:
        assert _dropped({"message": f'172.18.0.5 - - "GET {path} HTTP/1.1" 200 15'}), path
        assert _dropped({"message": "request completed", "url.path": path}), path
    # Real traffic, and paths that merely start like a health path, are kept.
    assert not _dropped({"message": '172.18.0.5 - - "POST /ingest/biorxiv HTTP/1.1" 200 812'})
    assert not _dropped({"message": '"GET /api/v1/signals/BEAM HTTP/1.1" 200 2048'})
    assert not _dropped({"message": "request completed", "url.path": "/healthcare/report"})
    assert not _dropped({"message": '"GET /healthcare/report HTTP/1.1" 200 512'})
    assert not _dropped({"message": "health check of neo4j failed"})


def test_prometheus_keeps_up_to_six_gigabytes() -> None:
    assert _env_example()["PROMETHEUS_RETENTION_SIZE"] == "6GB"


def test_every_limit_variable_is_documented_in_env_example() -> None:
    env = _env_example()
    services = _services()
    referenced: set[str] = set()
    for name, svc in services.items():
        referenced.add(_limit_var(name, svc))
        for value in svc["logging"].get("options", {}).values():
            referenced.update(_PLACEHOLDER.findall(str(value)) or re.findall(r"\$\{([A-Z0-9_]+)\}", str(value)))
    for key in ("NEO4J_server_memory_heap_max__size", "NEO4J_server_memory_heap_initial__size",
                "NEO4J_server_memory_pagecache_size"):
        referenced.update(re.findall(r"\$\{([A-Z0-9_]+)\}", services["neo4j"]["environment"][key]))
    for key in ("AIRFLOW__API__WORKERS", "AIRFLOW__CORE__PARALLELISM"):
        referenced.update(re.findall(r"\$\{([A-Z0-9_]+)\}", services["airflow"]["environment"][key]))

    assert {"LOG_MAX_SIZE", "LOG_MAX_FILE", "NEO4J_HEAP_SIZE", "NEO4J_PAGECACHE_SIZE",
            "AIRFLOW_API_WORKERS", "AIRFLOW_PARALLELISM"} <= referenced
    assert sorted(var for var in referenced if not env.get(var)) == []


def test_source_silence_counts_missing_data_as_alerting() -> None:
    rules = _rules()
    assert rules["Source Silence"]["noDataState"] == "Alerting"
    assert rules["Raw Topic Lag"]["for"] == "15m"


def test_daily_health_summary_reaches_prometheus_and_the_alert_contact() -> None:
    env = _services()["airflow"]["environment"]
    for var in (
        "PROMETHEUS_URL",
        "ALERT_CONTACT_TYPE",
        "ALERT_EMAIL_ADDRESSES",
        "ALERT_WEBHOOK_URL",
        "SMTP_HOST",
        "SMTP_USER",
        "SMTP_PASSWORD",
        "SMTP_FROM_ADDRESS",
    ):
        assert env[var] == f"${{{var}}}", var
    assert _env_example()["PROMETHEUS_URL"] == "http://prometheus:9090"
    # Grafana's alert counts come from its own /metrics.
    jobs = {j["job_name"]: j for j in _prometheus()["scrape_configs"]}
    assert jobs["grafana"]["static_configs"][0]["targets"] == ["grafana:3000"]


def test_elasticsearch_exporter_reports_read_only_indices() -> None:
    assert "--es.indices_settings" in _services()["elasticsearch-exporter"]["command"]


def test_pipeline_dashboard_shows_signal_age_dead_letters_and_scan_failures() -> None:
    panels = {p["title"]: p for p in _dashboard("auspex-pipeline")["panels"]}
    for title, metric in {
        "Days since latest stored signal": "auspex_source_latest_signal_age_seconds",
        "Dead letters not replayed": "auspex_dlt_depth",
        "Corroboration scan failures per hour": "auspex_corroboration_scan_failures_total",
    }.items():
        assert metric in _panel_exprs(panels[title]), f"{title} does not query {metric}"

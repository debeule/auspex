# Grafana Dashboards

**Status:** done
**Blocked by:** [Metrics](metrics.md) — Prometheus must be populated before metric panels are buildable; [Centralised logging](centralised-logging.md) — Elasticsearch must be populated before log panels are buildable
**Branch:** `feature/grafana-dashboards`

---

## Context

Grafana is the unified observability UI for this project. It reads from two data sources simultaneously:
- **Prometheus** — metrics (Kafka consumer lag, JVM heap, pipeline throughput, LLM error rate)
- **Elasticsearch** — logs (pipeline run summaries, DLT events, extraction errors)

Kibana is not used. The centralised-logging spec originally included Kibana; this spec replaces it. Kibana is removed from docker-compose.

This is the standard observability stack in modern enterprise Java environments. It is what platform engineering teams build for Spring Boot services at scale: Prometheus scrapes Actuator endpoints, Grafana reads Prometheus and log backends, one URL gives the full picture.

**Grafana provisioning** is the key mechanism. Grafana supports fully automated configuration via YAML and JSON files mounted at `/etc/grafana/provisioning/`. On startup, Grafana reads:
- `provisioning/datasources/` — data source definitions (auto-creates on first start)
- `provisioning/dashboards/` — a provider config + dashboard JSON files (auto-imports)

This means there is no setup script, no manual clicking, no `curl` calls. `docker compose up` gives a fully configured Grafana. All configuration is in `docker/grafana/` and version-controlled.

ILM policy (previously applied via Kibana API in the logging spec) is now applied directly to Elasticsearch via `docker/elasticsearch/setup.sh`, which runs as a short-lived compose init container at startup.

## What this builds

### 1. Grafana in docker-compose (replaces Kibana)

```yaml
grafana:
  image: grafana/grafana-oss:${GRAFANA_VERSION}
  container_name: auspex-grafana
  depends_on:
    elasticsearch:
      condition: service_healthy
    prometheus:
      condition: service_healthy
  environment:
    GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_ADMIN_PASSWORD}
    GF_USERS_ALLOW_SIGN_UP: "false"
    GF_ANALYTICS_REPORTING_ENABLED: "false"
  volumes:
    - ./grafana/provisioning:/etc/grafana/provisioning:ro
    - grafana_data:/var/lib/grafana
  ports:
    - "127.0.0.1:3000:3000"
  restart: unless-stopped
  healthcheck:
    test: ["CMD-SHELL", "curl -sf http://localhost:3000/api/health"]
    interval: 10s
    timeout: 5s
    retries: 10
    start_period: 30s
```

Add `grafana_data` to the volumes section. Add `GRAFANA_VERSION` and `GRAFANA_ADMIN_PASSWORD` to `VERSIONS.md` and `.env.example`.

### 2. Data source provisioning

`docker/grafana/provisioning/datasources/prometheus.yaml`:
```yaml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    uid: prometheus
    url: http://prometheus:9090
    isDefault: true
    jsonData:
      timeInterval: "15s"
```

`docker/grafana/provisioning/datasources/elasticsearch.yaml`:
```yaml
apiVersion: 1
datasources:
  - name: Elasticsearch
    type: elasticsearch
    uid: elasticsearch
    url: http://elasticsearch:9200
    jsonData:
      index: "auspex-logs-*"
      timeField: "@timestamp"
      logMessageField: message
      logLevelField: log.level
      esVersion: "8.0.0"
```

UIDs (`prometheus`, `elasticsearch`) are stable identifiers referenced by dashboard JSON. If they change, all dashboards break. Keep them short and fixed.

### 3. Dashboard provisioning provider

`docker/grafana/provisioning/dashboards/provider.yaml`:
```yaml
apiVersion: 1
providers:
  - name: Auspex
    folder: Auspex
    type: file
    options:
      path: /etc/grafana/provisioning/dashboards
      foldersFromFilesStructure: false
```

### 4. Dashboards

Three JSON files in `docker/grafana/provisioning/dashboards/`. **These are built in Grafana's UI first, then exported as JSON and committed** — do not hand-craft dashboard JSON.

---

**`operations.json` — "Auspex Operations"**

The primary monitoring dashboard. Default time range: last 6 hours.

Row 1 — Current state (single-stat panels):
- **Signals published today** — `sum(increase(auspex_pipeline_signals_published_total[24h]))` (Prometheus)
- **Kafka consumer lag** — `sum(kafka_consumer_records_lag{topic="auspex.signals.extracted"})` (Prometheus) — red if > 100
- **DLT events in last hour** — Elasticsearch count query on `auspex.topic: *.dlt` in the last 1h — red if > 0
- **Error logs in last hour** — Elasticsearch count on `log.level: ERROR` in the last 1h

Row 2 — Pipeline throughput (time series, Prometheus):
- Signals published per source over time: `rate(auspex_pipeline_signals_published_total[5m])` split by `source_type`
- LLM extraction results: `rate(auspex_llm_extraction_calls_total[5m])` split by `result` (signal / not_signal / error) — stacked bars

Row 3 — Infrastructure health (time series, Prometheus):
- JVM heap used: `jvm_memory_used_bytes{area="heap", service="core-hub"}` — with a soft threshold line at 80% of `jvm_memory_max_bytes`
- Kafka consumer lag over time: `kafka_consumer_records_lag{topic="auspex.signals.extracted"}` per partition
- Pipeline run duration: `histogram_quantile(0.95, rate(auspex_pipeline_run_duration_seconds_bucket[10m]))` split by `source_type`

---

**`pipeline.json` — "Auspex Pipeline"**

Metrics-only. For understanding pipeline behaviour per source over time.

- Document funnel table: `fetched`, `published`, `not_signal`, `failed` as time-averaged rates per source (Prometheus counters)
- Per-source published rate: one panel per source_type showing `rate(auspex_pipeline_signals_published_total[1h])`
- LLM error rate: `rate(auspex_llm_extraction_calls_total{result="error"}[1h]) / rate(auspex_llm_extraction_calls_total[1h])` — percentage
- Run duration p50/p95/p99 per source

---

**`errors.json` — "Auspex Error Drill-Down"**

Log-focused, for incident investigation. Uses Elasticsearch data source via Grafana's Logs panel.

- DLT events log panel — query: `auspex.topic: *.dlt` — columns: `@timestamp`, `auspex.topic`, `auspex.event_id`, `auspex.source_type`, `message`
- Extraction errors log panel — `service.name: ingestion-scraper AND log.level: ERROR`
- Signal consumer errors log panel — `service.name: core-hub AND log.level: ERROR`
- Per-source error count over time (Elasticsearch aggregation): error log count grouped by `auspex.source_type`

---

### 5. Alert rules

Three rules in `docker/grafana/provisioning/alerting/rules.yaml` (Grafana's provisioned alerting — same mechanism as datasources and dashboards):

```yaml
apiVersion: 1
groups:
  - name: auspex-operational
    folder: Auspex
    interval: 1m
    rules:
      - title: DLT Backlog
        condition: C
        data:
          - refId: A
            datasourceUid: prometheus
            model:
              expr: sum(increase(auspex_dlt_events_total[1h]))
        noDataState: OK
        execErrState: Alerting
        for: 0s

      - title: Source Silence
        condition: C
        data:
          - refId: A
            datasourceUid: prometheus
            model:
              expr: time() - max by(source_type)(auspex_pipeline_run_last_timestamp) > 21600
        for: 5m

      - title: Kafka Lag Critical
        condition: C
        data:
          - refId: A
            datasourceUid: prometheus
            model:
              expr: sum(kafka_consumer_records_lag{topic="auspex.signals.extracted"}) > 1000
        for: 5m
```

Add `auspex_pipeline_run_last_timestamp` as a Gauge in the Python metrics module — set to `time.time()` at the end of each successful run. This powers the source-silence alert.

All alerts use the **Grafana-managed alerting** backend and notify via the built-in "Grafana" contact point (logs to Grafana's own log — no external dependency). Wire up email or Slack in the watchlist-alerts spec when that is built.

### 6. ILM policy via Elasticsearch API

Move ILM setup out of a Kibana script (no longer applicable) into a direct Elasticsearch call. Add a `elasticsearch-setup` init container to docker-compose:

```yaml
elasticsearch-setup:
  image: curlimages/curl:latest
  depends_on:
    elasticsearch:
      condition: service_healthy
  volumes:
    - ./elasticsearch:/setup:ro
  command: /setup/setup.sh
  restart: "no"
```

`docker/elasticsearch/setup.sh`:
```bash
#!/bin/sh
curl -sf -X PUT "http://elasticsearch:9200/_ilm/policy/auspex-logs-policy" \
  -H "Content-Type: application/json" \
  -d @/setup/ilm-policy.json
echo "ILM policy applied"
```

`docker/elasticsearch/ilm-policy.json` contains the policy definition (same content as previously scoped in the logging spec).

## Out of scope

- Email or Slack notifications for alerts — external connectors require credentials; covered by watchlist-alerts spec
- Grafana authentication beyond admin password — single-user local setup
- Grafana plugins beyond built-in Elasticsearch and Prometheus support — the Elasticsearch datasource ships with Grafana OSS
- Metrics-based alerting for individual signal quality — that is signal-level logic, not infrastructure monitoring
- cAdvisor / node-exporter for container CPU/memory metrics — the three key metrics (Kafka lag, JVM heap, LLM throughput) are sufficient; full container stats are a separate decision

## Constraints

- Dashboard JSON files are **exported from Grafana after building in the UI**, not hand-written. The correct workflow: bring up the stack, build dashboards visually, export via Dashboard → Share → Export → Save to file, commit. Provisioned dashboards loaded from files cannot be edited in the UI — to update, edit the JSON file and restart Grafana (or reload provisioning via the Admin API).
- Data source UIDs (`prometheus`, `elasticsearch`) are hardcoded in the provisioning YAML and referenced inside dashboard JSON. They must match exactly. If you rename a UID, all dashboards break — update the JSON files as well.
- `GRAFANA_ADMIN_PASSWORD` must be set in `.env`. Default Grafana password `admin` is not acceptable even for local prod-sim — it is the first thing to change on any Grafana instance.
- `GF_ANALYTICS_REPORTING_ENABLED: "false"` — Grafana phones home by default. Disable it.
- Grafana's Elasticsearch datasource uses Lucene query syntax in Log panels. `auspex.topic: *.dlt` is Lucene, not Elasticsearch Query DSL. Use Lucene throughout for consistency with Kibana Discover syntax (same syntax, familiar if you've used Kibana before).
- `GRAFANA_VERSION` must be pinned and must be resolved at spec start. Grafana releases frequently — do not use `latest`.

## Required tests

Smoke tests against the running compose stack using Grafana's HTTP API (no user interaction needed):

`docker/grafana/test_provisioning.sh` — assertions run after compose up:

- `GET /api/health` → `{"database":"ok"}` — Grafana is healthy
- `GET /api/datasources` → response contains both `Prometheus` and `Elasticsearch` datasource names
- `GET /api/dashboards/search?folderTitle=Auspex` → response contains "Auspex Operations", "Auspex Pipeline", "Auspex Error Drill-Down"
- `GET /api/ruler/grafana/api/v1/rules` → response contains "DLT Backlog", "Source Silence", "Kafka Lag Critical"
- `GET /api/datasources/uid/prometheus/resources/api/v1/query?query=up` → proxied Prometheus query returns results — confirms Prometheus data source is reachable through Grafana

## Definition of done

```bash
docker compose -f docker/docker-compose.yml --env-file .env up -d --wait
docker/grafana/test_provisioning.sh
```

All assertions pass.

Manual verification:
1. Open `http://localhost:3000` → Dashboards → Auspex folder → open "Auspex Operations"
2. Run one pipeline source: `uv run python scripts/run_pipeline.py --sources biorxiv --days 1`
3. Refresh dashboard. Metric panels show data (signals published, run duration). Log count panels show data (DLT events: 0, error logs: 0 if run was clean).
4. Open "Auspex Error Drill-Down". Log panels render with the correct columns.
5. Open Alerting → Alert rules. Three rules are present and in "Normal" state.

## Notes

- **Build dashboards manually first, then export.** Same rule as the Kibana spec: run the stack, populate data by running a source, build in the Grafana UI, export JSON, commit. Dashboard JSON is approximately 200–400 lines of Grafana-specific schema per dashboard — it is not human-readable or hand-maintainable.
- Grafana's Elasticsearch log panels use the **Logs** visualization type (not Table or Time series). Set the datasource to Elasticsearch, the log message field to `message`, and the log level field to `log.level`. Grafana will colour-code by level automatically.
- Provisioned dashboards are read-only in the UI by default. To allow editing (for development), set `allowUiUpdates: true` in the provider YAML. Remove this for prod-sim to prevent accidental changes from being lost on container restart.
- The `auspex_pipeline_run_last_timestamp` gauge (needed for the source-silence alert) is a new metric not in the metrics spec. Add it in this spec's implementation: `Gauge("auspex_pipeline_run_last_timestamp", "Unix timestamp of last successful pipeline run", ["source_type"])` set at the end of `IngestionPipeline.run()`.
- `GRAFANA_VERSION` — resolve from `grafana/grafana-oss` on Docker Hub at spec start. Grafana OSS (not Enterprise) is the correct image for this use case.

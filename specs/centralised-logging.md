# Centralised Logging

**Status:** ready
**Blocked by:** —
**Branch:** `feature/centralised-logging`

---

## Context

Neither service has structured logging today. `ingestion-scraper` uses `print()` in scripts with no logging in library code. `core-hub` has SLF4J loggers in `SignalListener`, `RawListener`, `ScheduledCorroborationService`, and `GraphUpdateService` using plain-text string interpolation — no structured fields, no MDC context, no JSON format. `application.yml` has only level configuration.

The failure mode this spec addresses: a signal stops being corroborated, or a DLT starts filling, and there is no way to find the cause without attaching a debugger. Structured, searchable logs with consistent context fields make this diagnosable in minutes.

**Stack: Elastic Stack (Elasticsearch + Filebeat + Kibana).** This is the industry-standard centralized logging stack used across enterprise software and large-scale systems. The components:

- **Elasticsearch** — stores and indexes log events; all queries go here.
- **Filebeat** — lightweight log shipper that reads Docker container stdout/stderr and forwards to Elasticsearch. No Logstash — Filebeat's ingest pipeline is sufficient for this project.
- **Kibana** — UI for searching logs, building dashboards, and setting up index lifecycle policies.

Log format: **Elastic Common Schema (ECS)**. ECS is the field-naming standard used by all Elastic products and most enterprise integrations. Using it means Kibana dashboards, alerting, and third-party tools work without field mapping customisation.

## What this builds

### 1. ingestion-scraper — structlog with ECS JSON output

Add `structlog` to `pyproject.toml`. Configure it once at import time in `src/auspex_ingest/logging_config.py`:

- JSON renderer for production; `ConsoleRenderer` in development (controlled by env var `LOG_FORMAT=json|console`, default `json`).
- ECS field names: `@timestamp` (UTC ISO-8601), `log.level`, `service.name` (`ingestion-scraper`), `message`.
- Custom fields prefixed `auspex.*`: `auspex.source_type`, `auspex.event_id`, `auspex.external_id`, `auspex.run_id`.
- A `SensitiveFieldDrop` processor that removes `raw_content`, `api_key`, `access_key`, `secret_key`, and any field whose name contains `password` or `secret` before serialization.

`IngestionPipeline.run()` binds `auspex.source_type` and a generated `auspex.run_id` (UUID) at entry. Each document's `auspex.external_id` and `auspex.event_id` (once computed) are bound for that document's log events. The run-summary log event emits all `RunResult` counter fields.

Connector errors log `source_type`, `external_id`, and the exception class — never the full `raw_content`.

`scripts/run_pipeline.py` and `scripts/reextract.py` call `configure_logging()` at startup and emit structured run summaries instead of `print()` statements.

### 2. core-hub — Spring Boot 4.1 native ECS structured logging

Enable Spring Boot 4.1's built-in ECS structured logging in `application.yml`:

```yaml
logging:
  structured:
    format:
      console: ecs
```

This replaces the default Logback pattern with ECS JSON on stdout. No additional dependency needed — Spring Boot 4.1 bundles `spring-boot-starter-logging` with ECS support.

In `SignalListener` and `RawListener`: populate MDC with `auspex.event_id` and `auspex.source_type` at listener entry, clear in a `finally` block. MDC fields are automatically included in every log line emitted within that listener invocation, including inside `GraphUpdateService` and `PostgresWriteService`.

In `ScheduledCorroborationService`: bind `auspex.run_id` (UUID) at the start of each scheduled scan and log the watermark before and after.

DLT routing: log `exception_class`, `auspex.event_id`, and `auspex.topic` so every dead-letter is triageable from Kibana without reading the Kafka topic.

### 3. docker/docker-compose.yml — Elasticsearch, Kibana, Filebeat

Three new services added to the compose file:

**Elasticsearch:**
- Image: `elasticsearch:${ELASTIC_VERSION}` (pin in `VERSIONS.md` and `.env.example`)
- `xpack.security.enabled=false` (dev only — no TLS/auth for local compose)
- `discovery.type=single-node`
- `ES_JAVA_OPTS=-Xms512m -Xmx512m` (dev sizing)
- Port `9200` bound to `127.0.0.1`

**Kibana:**
- Image: `kibana:${ELASTIC_VERSION}` (same version as Elasticsearch — they must match)
- Depends on Elasticsearch health check
- Port `5601` bound to `127.0.0.1`

**Filebeat:**
- Image: `elastic/filebeat:${ELASTIC_VERSION}`
- Mounts: `/var/lib/docker/containers:/var/lib/docker/containers:ro` and `/var/run/docker.sock:/var/run/docker.sock:ro`
- Config file: `docker/filebeat/filebeat.yml` — Docker autodiscovery, forwards to Elasticsearch, sets `index: "auspex-logs-%{+yyyy.MM.dd}"`.

### 4. Index Lifecycle Policy

A Kibana saved object (exported to `docker/kibana/auspex_ilm_policy.ndjson`) defines the ILM policy for `auspex-logs-*`:

| Phase | Trigger | Action |
|---|---|---|
| Hot | From creation | Rollover at 5 GB or 7 days |
| Warm | After 7 days | Shrink to 1 shard, force-merge |
| Cold | After 30 days | Freeze |
| Delete | After 180 days | Delete |

Apply with `kibana/setup_kibana.sh` (idempotent script using Kibana's saved objects import API).

## Out of scope

- Metrics and dashboards (Prometheus, Grafana) — separate concern.
- Distributed tracing (OpenTelemetry) — separate concern.
- Airflow log aggregation — Airflow has its own log backend.
- Log-based alerting rules — covered by the watchlist-alerts spec.
- Security/TLS for Elasticsearch — this spec targets local dev + staging. Production security is a deployment concern, not a code concern.

## Constraints

- **Invariant 6**: `raw_content`, API keys, and credentials must never appear in log output. The `SensitiveFieldDrop` processor (Python) and MDC exclusion discipline (Java) are the enforcement mechanisms. Two tests assert on this for each service.
- All log lines written by application code are JSON. No human-readable format in production. The `LOG_FORMAT=console` path is for local development only and must not be set in Docker.
- ECS field names are fixed. Do not invent custom top-level fields — use the `auspex.*` namespace. This keeps Kibana auto-discovery working without manual index template changes.
- `@timestamp` is always UTC. The `SensitiveFieldDrop` processor runs last, after the timestamp is set, so it cannot accidentally drop it.
- Elasticsearch version must match Kibana and Filebeat versions exactly. Pin all three to the same `ELASTIC_VERSION` in `.env.example`.
- `vm.max_map_count=262144` is required on Linux hosts for Elasticsearch. Add to `docs/PREREQUISITES.md` under "Infrastructure".

## Required tests

**Python unit (`tests/unit/test_logging.py`):**

- `test_pipeline_run_summary_log_contains_all_counters` — `IngestionPipeline.run()` emits a log event with `RunResult` counter fields; use `structlog.testing.capture_logs()`.
- `test_pipeline_run_log_contains_source_type_and_run_id` — the run-summary event carries `auspex.source_type` and `auspex.run_id`.
- `test_connector_error_log_includes_source_type_and_external_id` — an exception during document processing produces a log event with both fields.
- `test_sensitive_field_drop_removes_raw_content` — a log event with a `raw_content` key is scrubbed before output; the field does not appear in the captured JSON.
- `test_sensitive_field_drop_removes_api_key_variants` — fields named `api_key`, `access_key`, `secret_key`, `password`, `secret` are dropped.
- `test_all_captured_log_events_are_valid_json` — every event captured by `capture_logs()` serialises to valid JSON with no `TypeError`.

**Java unit (`src/test/java/.../LoggingTest.java`):**

- `test_signal_listener_mdc_contains_event_id_and_source_type` — use a `ListAppender<ILoggingEvent>` attached to the `SignalListener` logger; assert MDC keys `auspex.event_id` and `auspex.source_type` are present on the log event emitted during processing.
- `test_mdc_cleared_after_listener_returns` — after the listener method returns, MDC is empty (no bleed between messages).
- `test_dlt_routing_log_contains_exception_class_and_event_id` — when a `UnknownMajorVersionException` routes to DLT, the error log event carries both fields.
- `test_log_output_does_not_contain_raw_content_field` — log events do not carry a field named `raw_content` (the field is not present in any captured event).

**Integration (`tests/integration/test_logging_integration.py`):**

- `test_filebeat_delivers_log_line_to_elasticsearch` — start Elasticsearch via testcontainers, configure Filebeat to forward a test log file, emit one structured log line, poll Elasticsearch until the document appears (awaitility-style with timeout); assert ECS fields `@timestamp`, `log.level`, `service.name`, `message` are present.

## Definition of done

```bash
cd services/ingestion-scraper && uv run pytest tests/unit/test_logging.py -q
cd services/core-hub && ./gradlew test --tests '*LoggingTest'
cd services/ingestion-scraper && uv run pytest tests/integration/test_logging_integration.py -v -m integration
```

All pass.

```bash
docker compose -f docker/docker-compose.yml --env-file .env up -d --wait
```

`http://localhost:5601` opens Kibana. Navigate to Discover, select the `auspex-logs-*` index pattern. Run the ingestion pipeline for one source. Log events appear with fields `auspex.source_type`, `auspex.run_id`, and the `RunResult` counters.

## Notes

- Spring Boot 4.1's native ECS logging (`logging.structured.format.console=ecs`) was introduced in Boot 3.4. Verify it works correctly on 4.1 before writing any tests that depend on the output format. If it does not produce standard ECS, fall back to `logstash-logback-encoder` (net.logstash.logback, BOM-managed in Boot 4.1) and record the decision in `DECISIONS.md`.
- Filebeat Docker autodiscovery reads container labels to decide which logs to ship. Add `co.elastic.logs/enabled: "true"` to the `core-hub` and relevant Python containers in docker-compose. Containers without the label are not shipped — this prevents Filebeat from forwarding its own logs into Elasticsearch and creating a feedback loop.
- Elasticsearch's Docker image requires `vm.max_map_count=262144` on Linux. On macOS and Windows (Docker Desktop), the VM that runs Docker sets this automatically. Add a note to `docs/PREREQUISITES.md` for Linux users.
- `ES_JAVA_OPTS=-Xms512m -Xmx512m` is deliberately small for local dev. The default is to use half of available RAM, which on a developer machine starves other processes.
- The ILM setup script (`docker/kibana/setup_kibana.sh`) should be idempotent — running it twice must not fail. Use Kibana's saved objects import with `overwrite: true`.
- `structlog` requires adding it to `pyproject.toml`. Pin the version in `VERSIONS.md`. As of 2026, structlog 24.x is current — resolve the exact version at spec start and record it.

# Metrics Instrumentation

**Status:** done
**Blocked by:** [Centralised logging](centralised-logging.md) — structlog and MDC context must be in place so metric labels (`auspex.source_type`, `auspex.event_id`) are consistent with log fields
**Branch:** `feature/metrics`

---

## Context

Neither service currently exposes metrics. `spring-boot-starter-actuator` is not in `build.gradle.kts`. `prometheus-client` is not in `pyproject.toml`. The Flask API (scraper-api spec) has a `/health` route but no `/metrics`.

Spring Boot's Micrometer integration is the standard instrumentation layer for enterprise Java. When `micrometer-registry-prometheus` is on the classpath, Micrometer auto-registers JVM, GC, thread, and HTTP metrics and exposes them at `/actuator/prometheus` in the Prometheus text format. Spring Kafka 4.1 also auto-registers Kafka consumer metrics via Micrometer's `KafkaMetrics` binder — consumer lag is exposed without any custom code.

Three metrics matter most for a multi-week prod-sim run of this system:

1. **Kafka consumer lag on `auspex.signals.extracted`** — tells you whether core-hub is keeping up with signal ingestion. Logs tell you a message was processed; lag tells you how many are queued. This is the first thing to check if signals stop appearing.
2. **JVM heap used over time** — a slow memory leak in core-hub won't crash it immediately but shows up as growing heap over days. One graph over two weeks tells you more than any point-in-time check.
3. **LLM extraction throughput and error rate** — signals extracted per source per run, and the ratio of `not_signal` to `published`. If a connector starts returning irrelevant documents, this ratio shifts visibly before it shows up in data quality.

Relevant existing code:
- `services/core-hub/build.gradle.kts` — no actuator dependency; `management.endpoints.web.exposure.include: health,info` in `application.yml`
- `services/core-hub/src/main/java/dev/auspex/corehub/kafka/SignalListener.java` — processes signals; this is where the published-per-source counter increments
- `services/ingestion-scraper/src/auspex_ingest/pipeline.py` — `IngestionPipeline.run()` returns `RunResult`; counters should increment here, or be emitted from the run summary
- `services/ingestion-scraper/src/auspex_ingest/api.py` — Flask app (from scraper-api spec); `/metrics` route added here

## What this builds

### 1. core-hub — Micrometer + Prometheus registry

Add to `build.gradle.kts`:
```kotlin
implementation("org.springframework.boot:spring-boot-starter-actuator")
implementation("io.micrometer:micrometer-registry-prometheus")
```

Both are BOM-managed by Spring Boot 4.1 — no version needed.

Update `application.yml`:
```yaml
management:
  endpoints:
    web:
      exposure:
        include: health,info,prometheus
  metrics:
    tags:
      service: core-hub
```

**Auto-exposed by Micrometer (no code changes):**
- `jvm_memory_used_bytes{area="heap"}` — heap usage over time
- `jvm_gc_pause_seconds` — GC pressure
- `jvm_threads_live_threads` — thread count
- `kafka_consumer_records_lag{topic, partition}` — consumer lag per partition (auto-registered by Spring Kafka's Micrometer binder)
- `http_server_requests_seconds{uri, method, status}` — REST API request latency and rate

**Custom counters** injected into `SignalListener` and `GraphUpdateService`:

```java
// SignalListener — increment on each successful signal processed
Counter.builder("auspex.signals.processed.total")
    .tag("source_type", event.sourceType())
    .register(meterRegistry)
    .increment();

// KafkaConfig's DLT recovery — increment when a message routes to DLT
Counter.builder("auspex.dlt.events.total")
    .tag("topic", record.topic())
    .register(meterRegistry)
    .increment();
```

`MeterRegistry` is injected via constructor; do not use `Metrics.globalRegistry` static accessor.

### 2. ingestion-scraper — prometheus-client + `/metrics` route

Add to `pyproject.toml` dependencies:
```
prometheus-client==0.21.1
```
Pin version in `VERSIONS.md`.

In `src/auspex_ingest/metrics.py` — module-level registry with named collectors:

```python
from prometheus_client import Counter, Histogram, REGISTRY

documents_fetched = Counter(
    "auspex_pipeline_documents_fetched_total",
    "Documents fetched from source",
    ["source_type"],
)
signals_published = Counter(
    "auspex_pipeline_signals_published_total",
    "Signals published to Kafka",
    ["source_type"],
)
llm_calls = Counter(
    "auspex_llm_extraction_calls_total",
    "LLM extraction calls",
    ["source_type", "result"],  # result: signal | not_signal | error
)
run_duration = Histogram(
    "auspex_pipeline_run_duration_seconds",
    "Pipeline run wall-clock duration",
    ["source_type"],
    buckets=[30, 60, 120, 300, 600, 1800, 3600],
)
```

`IngestionPipeline.run()` increments counters from `RunResult` at the end of each run and records the histogram observation. Metrics module is imported at API startup; counters accumulate across runs for the lifetime of the process.

Add to Flask API (`src/auspex_ingest/api.py`):
```python
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

@app.route("/metrics")
def metrics():
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}
```

### 3. docker-compose — Prometheus service

Add to `docker/docker-compose.yml`:

```yaml
prometheus:
  image: prom/prometheus:${PROMETHEUS_VERSION}
  container_name: auspex-prometheus
  volumes:
    - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
    - prometheus_data:/prometheus
  ports:
    - "127.0.0.1:9090:9090"
  restart: unless-stopped
  healthcheck:
    test: ["CMD-SHELL", "wget -qO- http://localhost:9090/-/healthy"]
    interval: 10s
    timeout: 5s
    retries: 5
```

`docker/prometheus/prometheus.yml`:
```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: core-hub
    static_configs:
      - targets: ['core-hub:8080']
    metrics_path: /actuator/prometheus

  - job_name: ingestion-scraper
    static_configs:
      - targets: ['ingestion-scraper:8000']
    metrics_path: /metrics
```

Prometheus runs without a profile — it is part of the observability infrastructure, not the application layer. App services (`core-hub`, `ingestion-scraper`) are profile `app` and only exist in the compose network when that profile is active. Prometheus scrapes them when they are present and shows them as DOWN when they are not — this is expected and not an error.

Add `prometheus_data` to the volumes section.
Add `PROMETHEUS_VERSION` to `VERSIONS.md` and `.env.example`.

## Out of scope

- Grafana (separate spec — consumes these metrics)
- Alerting rules (Grafana spec)
- Distributed tracing / OpenTelemetry
- Airflow metrics
- Infrastructure metrics (CPU, memory per container) — available from Docker's built-in stats; adding cAdvisor or node-exporter is a separate decision

## Constraints

- `MeterRegistry` must be constructor-injected into `SignalListener` and any other class that registers metrics. Do not use `Metrics.globalRegistry` — it is a static accessor that makes tests fragile and couples the class to the global state.
- Counter labels (`source_type`, `topic`) must use the same values as the corresponding log fields (`auspex.source_type`, `auspex.topic`). If they diverge, Grafana dashboards cannot correlate logs and metrics.
- `prometheus-client`'s default `REGISTRY` is process-global. Tests that register metrics must either use a fresh `CollectorRegistry()` per test or use `prometheus_client.REGISTRY.unregister()` in teardown. The module-level collectors in `metrics.py` must not be re-registered on import.
- The `/metrics` route must not require authentication. It is on the internal Docker network only.
- Prometheus scrape interval of 15s is appropriate for this workload. Do not reduce it below 10s — it adds load without meaningful resolution improvement for runs measured in minutes.

## Required tests

**Java unit (`src/test/java/.../MetricsTest.java`):**

- `test_prometheus_endpoint_returns_200` — `GET /actuator/prometheus` returns HTTP 200 with `Content-Type: text/plain` (use `MockMvc`, no Spring context required for the counter tests below)
- `test_signals_processed_counter_increments_per_source_type` — call `SignalListener.onSignal()` with a stubbed event; assert `auspex.signals.processed.total{source_type=...}` in the `MeterRegistry` incremented by 1
- `test_dlt_counter_increments_on_routing` — trigger the DLT recovery path; assert `auspex.dlt.events.total{topic=...}` incremented
- `test_kafka_consumer_lag_metric_is_registered` — assert `kafka.consumer.records.lag` is present in the `MeterRegistry` after Spring Kafka context starts (integration test — requires Kafka container)

**Python unit (`tests/unit/test_metrics.py`):**

- `test_metrics_route_returns_prometheus_format` — Flask test client GET `/metrics` returns 200, `Content-Type` contains `text/plain`
- `test_pipeline_run_increments_published_counter` — run `IngestionPipeline` with stubbed components; assert `auspex_pipeline_signals_published_total{source_type=...}` incremented by the number of published signals
- `test_pipeline_run_increments_fetched_counter` — same run; assert `auspex_pipeline_documents_fetched_total` incremented
- `test_llm_error_increments_error_label` — extractor raises; assert `auspex_llm_extraction_calls_total{result="error"}` incremented
- `test_run_duration_histogram_records_observation` — histogram `auspex_pipeline_run_duration_seconds_count` is 1 after one run

## Definition of done

```bash
cd services/core-hub && ./gradlew test --tests '*MetricsTest' && ./gradlew integrationTest --tests '*MetricsIT'
cd services/ingestion-scraper && uv run pytest tests/unit/test_metrics.py -q
```

All pass.

```bash
docker compose --profile app -f docker/docker-compose.yml --env-file .env up -d --wait
curl -s http://localhost:8080/actuator/prometheus | grep kafka_consumer_records_lag
curl -s http://localhost:8000/metrics | grep auspex_pipeline_signals_published_total
curl -s http://localhost:9090/api/v1/targets | python3 -m json.tool | grep '"health":"up"'
```

Both service targets show `health: up` in Prometheus. Kafka consumer lag metric is present in the core-hub scrape.

## Notes

- Spring Kafka's Micrometer binder exposes `kafka.consumer.records.lag` automatically when `micrometer-registry-prometheus` is on the classpath. No additional configuration needed. The metric uses dots (Micrometer convention); Prometheus converts dots to underscores on export — so the Prometheus metric name is `kafka_consumer_records_lag`.
- `prometheus-client` default `REGISTRY` is a module singleton. Tests that instantiate the Flask app multiple times will get "duplicated timeseries" errors unless counters are registered once. Use a module-level `metrics.py` that guards against double-registration with `try/except ValueError`.
- Prometheus running without the `app` profile means it starts even in infra-only dev mode. This is intentional — it has negligible resource use and its scrape targets simply show DOWN until the app services start. The alternative (putting Prometheus in the `app` profile) means Grafana has no metrics data source in dev mode, which is more confusing.
- `PROMETHEUS_VERSION` — resolve from `prom/prometheus` on Docker Hub at spec start and pin to exact version in `VERSIONS.md`.

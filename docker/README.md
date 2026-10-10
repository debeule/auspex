# docker/

Docker Compose stack for the full Auspex infrastructure.

---

## Services

| Service | Image | Port(s) | Purpose |
|---|---|---|---|
| `auspex-kafka` | `apache/kafka:4.3.0` | 9092 | Message broker (KRaft, no Zookeeper) |
| `auspex-postgres` | `postgres:18.6` | 5432 | Application DB + Airflow metadata DB |
| `auspex-neo4j` | `neo4j:2026.05-community` | 7474 / 7687 | Signal graph |
| `auspex-minio` | `minio/minio:RELEASE.2025-09-07T16-13-09Z` | 9000 / 9001 | Raw document archive (S3-compatible) |
| `auspex-elasticsearch` | `docker.elastic.co/elasticsearch/elasticsearch:8.17.3` | 9200 | Log storage (ECS format) |
| `auspex-filebeat` | `docker.elastic.co/beats/filebeat:8.17.3` | — | Log shipper; Docker autodiscovery |
| `auspex-prometheus` | `prom/prometheus:v3.14.0` | 9090 | Metrics scraper and storage |
| `auspex-grafana` | `grafana/grafana-oss:13.0.2` | 3000 | Observability UI (logs + metrics) |
| `auspex-kafka-init` | `apache/kafka:4.3.0` | — | One-shot init: creates every topic in `topics.yaml` (`--if-not-exists`) |
| `auspex-minio-init` | built from `services/backtesting` | — | One-shot init: creates the `auspex-raw` and `auspex-prices` buckets |
| `auspex-price-bootstrap` | built from `services/backtesting` | — | One-shot init: fills missing price snapshots (watchlist, `XBI`, `EURUSD=X`) from `PRICE_HISTORY_START` and appends bars since the last run; fails `up --wait` if a ticker has no data at all |
| `auspex-price-service` | built from `services/backtesting` | 8001 | HTTP API the price DAGs call: `POST /prices/refresh` (`auspex_price_refresh`) and `POST /universe/build` (`auspex_universe_build`, which also needs the `SEC_*` variables and mounts `config/universe/`) |
| `auspex-elasticsearch-setup` | `curlimages/curl:8.15.0` | — | One-shot init: applies the `auspex-logs-ilm` retention policy (delete after 180 days) and attaches it to existing log indices |
| `auspex-ingestion-scraper` | built from `services/ingestion-scraper` | 8000 | Scraper HTTP API (profile `app`) |
| `auspex-core-hub` | built from `services/core-hub` | 8080 | Signal processor (profile `app`) |
| `auspex-dashboard` | built from `services/dashboard` | 3001 (`DASHBOARD_PORT`) | Control and research UI behind a single-user login; its server forwards to core-hub, the scraper and price-service (profile `app`) |
| `auspex-airflow` | `apache/airflow:3.3.1` | 8082 | DAG scheduler: ingestion DAGs (paused at creation) `auspex_price_refresh` (active, Mon–Fri 22:30 UTC) and `auspex_universe_build` (active, days 1–7 of each month 06:00 UTC). Sends statsd metrics to `statsd-exporter` |
| `auspex-node-exporter` | `prom/node-exporter:v1.12.1` | — | Docker VM CPU, memory and filesystems (read through PID 1, no host mounts), plus the volume sizes from `volume-usage` |
| `auspex-volume-usage` | `busybox:1.37.0` | — | Measures every named volume with `du` every `VOLUME_USAGE_INTERVAL_SECONDS` (`volume-usage/collect.sh`) |
| `auspex-cadvisor` | `ghcr.io/google/cadvisor:0.57.0` | — | Per-container CPU, memory and start times |
| `auspex-postgres-monitor-role` | `postgres:18.6` | — | One-shot init: creates or updates the read-only `auspex_monitor` role (`pg_monitor`) on every `up` |
| `auspex-postgres-exporter` | `prometheuscommunity/postgres-exporter:v0.20.1` | — | Connections, database sizes, as `auspex_monitor` |
| `auspex-kafka-exporter` | `danielqsj/kafka-exporter:v1.10.0` | — | Brokers, topic offsets, consumer-group lag including `*.dlt` |
| `auspex-elasticsearch-exporter` | `prometheuscommunity/elasticsearch-exporter:v1.11.0` | — | Cluster health and data disk |
| `auspex-blackbox-exporter` | `prom/blackbox-exporter:v0.28.0` | — | Probes every health endpoint, Neo4j's HTTP port, Kafka and Postgres over TCP, and Ollama on the host |
| `auspex-statsd-exporter` | `prom/statsd-exporter:v0.31.0` | — | Turns Airflow's statsd metrics into DAG run and task outcomes per `dag_id` (`statsd-exporter/mapping.yml`) |

All ports bound to `127.0.0.1` — local only, intentional; the exporters publish none. Services in the `app` profile (`ingestion-scraper`, `core-hub`) only start with `--profile app`.

Every service has a `mem_limit` from `.env` (`*_MEM_LIMIT`, values in `.env.example` only). The long-running services' limits add up to at most 7.5 GB, inside Docker Desktop's 8 GB VM with 512 MB left for the VM; `test_stack_observability_config.py` enforces both. A container that reaches its limit is OOM-killed and restarted, which raises **Container Restarting**; raise its variable in `.env` and look at **Container memory** on the infrastructure dashboard.

---

## Commands

```bash
docker compose -f docker/docker-compose.yml --env-file .env up -d --wait   # bring up
docker compose -f docker/docker-compose.yml --env-file .env down            # keep volumes
docker compose -f docker/docker-compose.yml --env-file .env down -v         # wipe volumes
```

`--wait` blocks until all healthchecks pass and every one-shot init has exited 0. `auspex-airflow` healthcheck is slow (~60s) — normal. Manual steps that remain (secrets, the local model, sign-offs) are in [`SETUP.md`](../SETUP.md).

---

## Kafka topics

Created by the `kafka-init` one-shot on every `up` from `topics.yaml`; existing topics are left alone.

| Topic | Partitions | Retention | Notes |
|---|---|---|---|
| `auspex.raw.ingested` | 6 | 7 days | All fetched documents |
| `auspex.signals.extracted` | 6 | 90 days | Extracted signals only |
| `auspex.signals.corroborated` | 6 | 90 days | Corroboration events |
| `auspex.raw.ingested.dlt` | 6 | 30 days | Dead-letter for raw topic |
| `auspex.signals.extracted.dlt` | 6 | 30 days | Dead-letter for extracted topic |
| `auspex.signals.corroborated.dlt` | 6 | 30 days | Dead-letter for corroborated topic |

DLT partition count must match the source topic — Spring's `DeadLetterPublishingRecoverer` publishes to the same partition number.

`--if-not-exists` never alters an existing topic. If partition counts are wrong: `down -v` then `up` again.

---

## Postgres databases

Two databases share one container:

| Database | Role | Created by |
|---|---|---|
| `auspex` | `auspex_app` | `postgres-init/01_airflow.sh` on first volume init |
| `airflow` | `airflow` | `postgres-init/01_airflow.sh` on first volume init |

Flyway runs schema migrations against `auspex` on every `core-hub` startup (`ddl-auto: validate`).

---

## Observability

Grafana at `http://localhost:3000` (folder **Auspex**), Prometheus at `:9090`, Elasticsearch at `:9200`. Both app services log JSON with ECS field names (`message`, `log.level`, `@timestamp`), which Filebeat ships to daily `auspex-logs-YYYY.MM.DD` indices.

| Dashboard | Shows |
|---|---|
| Auspex Pipeline | fetched / published per source, failed documents, LLM extraction latency (p50, p95, mean), LLM error ratio, run duration, hours since last run |
| Auspex Operations | scrape targets up, core-hub throughput, Kafka consumer lag, listener time per record, DLT events, JVM heap, scraper memory, HTTP 5xx |
| Auspex Error Drill-Down | error log lines by container, DLT events, error log stream, failed-document log stream |
| Auspex Infrastructure | service up/down grid (health probes and scrape targets), container restarts and memory, Mac CPU/memory/disk, Docker VM CPU/memory/disk, volume sizes, Postgres connections and size, Elasticsearch disk, Kafka lag per group, dead-letter topic size, MinIO capacity, Airflow DAG runs by outcome, price refresh sessions behind |

| Alert | Fires when |
|---|---|
| DLT Backlog | any record dead-lettered in the last hour |
| Source Silence | a source has not completed a run for 6 h |
| Kafka Lag Critical | lag on `auspex.signals.extracted` above 1000 for 5 min |
| Scrape Target Down | any scrape target except the Mac's exporter is unscrapeable for 5 min |
| LLM Extraction Errors | more than 20% of extraction calls fail over 15 min |
| Probe Target Down | a health probe fails for 5 min (Ollama excluded) |
| Mac Host Exporter Down (info) | the Mac's `node_exporter` is unreachable for 15 min |
| Docker Disk Low | the VM disk holding images and volumes is below `ALERT_DOCKER_DISK_FREE_MIN_PCT` (15) % free |
| Mac Disk Low | the Mac's disk is below `ALERT_MAC_DISK_FREE_MIN_PCT` (10) % free |
| VM Memory High | VM memory above `ALERT_VM_MEMORY_MAX_PCT` (90) % for 10 min |
| Container Restarting | a container started more than `ALERT_CONTAINER_RESTARTS_MAX_PER_HOUR` (3) times in an hour |
| Airflow DAG Run Failed | a DAG run failed in the last hour |
| Price Refresh Stale | no fully successful price refresh for `ALERT_PRICE_REFRESH_MAX_MISSED_SESSIONS` (2) NYSE sessions |
| Ollama Down During Extraction | Ollama is unreachable for 5 min while an ingestion DAG task runs or extraction calls are being made |

Every alert goes to one contact point, `auspex-default` (`grafana/provisioning/alerting/contactpoints.yaml`), set by `ALERT_CONTACT_TYPE` in `.env`: `email` (default; `ALERT_EMAIL_ADDRESSES` and the `SMTP_*` variables) or `webhook` (`ALERT_WEBHOOK_URL`). A firing alert repeats every 4 hours until it resolves. Grafana expands `$VAR` in the alerting files from its environment, so a literal `$` there is written `$$`.

Prometheus keeps metrics for `PROMETHEUS_RETENTION_TIME` (30 days) or `PROMETHEUS_RETENTION_SIZE` (4 GB), whichever is hit first.

**Mac vs VM.** On Docker Desktop, `node-exporter` sees the Linux VM: its memory (8 GB) and the disk that holds images and volumes. The Mac itself (Ollama's memory, the Mac's disk) comes from a `node_exporter` installed on the Mac with Homebrew (`SETUP.md` step 2), scraped as job `mac-host` at `host.docker.internal:9100`. Each covers a failure the other cannot see. The stack does not need the Mac exporter: without it the Mac panels are empty and one info alert fires.

Key metrics: `auspex_price_refresh_runs_total{outcome}`, `auspex_price_tickers_refreshed_total`, `auspex_price_tickers_failed_total`, `auspex_price_refresh_last_success_timestamp_seconds`, `auspex_price_refresh_sessions_since_success` (price-service); `auspex_pipeline_documents_fetched_total`, `auspex_pipeline_documents_failed_total`, `auspex_pipeline_signals_published_total`, `auspex_llm_extraction_calls_total{result}`, `auspex_llm_extraction_duration_seconds`, `auspex_pipeline_run_duration_seconds`, `auspex_pipeline_run_last_timestamp` (scraper); `auspex_signals_processed_total`, `auspex_dlt_events_total{topic}`, `kafka_consumer_fetch_manager_records_lag`, `spring_kafka_listener_seconds` (core-hub).

Smoke test after `up` (give Prometheus a minute for its first scrapes): `GRAFANA_ADMIN_PASSWORD=... sh docker/grafana/test_provisioning.sh`. It checks the dashboards, alert rules, contact point and policy, that every target except `mac-host` is up, every probe except Ollama succeeds, and that the Postgres, Kafka, Elasticsearch, cAdvisor and volume metrics arrive.

## Environment

All credentials come from root `.env`. Copy from `.env.example` and fill in:
- `SEC_USER_AGENT` — required for SEC EDGAR requests (format: `Name email@example.com`)
- `EXTRACTION_API_KEY` — API key for the extraction model endpoint
- `EXTRACTION_MODEL` — registry key matching an entry in `config/models/registry.yaml`
- `EPO_OPS_KEY` / `EPO_OPS_SECRET` — for patent connector
- `POSTGRES_MONITOR_PASSWORD` — the exporter's read-only Postgres role
- `ALERT_CONTACT_TYPE` and its settings (`ALERT_EMAIL_ADDRESSES` + `SMTP_*`, or `ALERT_WEBHOOK_URL`) — where alerts go; Grafana does not start without them

No variable has a default in `docker-compose.yml`: values live only in `.env.example`, so an `.env` copied before a variable existed needs it added (step 1 of `specs/first-run-on-stack-machine.md` does this).

---

## Local model backend (Ollama on macOS)

Docker Desktop on macOS cannot access Metal/GPU. The model server must run on the host; the
scraper reaches it via `host.docker.internal`.

```
EXTRACTION_BASE_URL=http://host.docker.internal:11434/v1
EXTRACTION_API_KEY=ollama
EXTRACTION_MODEL=<registry key matching the Ollama digest>
```

The scraper service maps `host.docker.internal` to the host gateway (`extra_hosts`), so the same
value works on Linux. `config/models/` is mounted read-only at `/app/models` so the registry and
gate records are read from the repo, not baked into the image.

**Context length:** Ollama's OpenAI-compatible endpoint ignores per-request `num_ctx`; the server
default is 4096 tokens and longer prompts are silently truncated. Start Ollama with
`OLLAMA_CONTEXT_LENGTH` ≥ the registry's `num_ctx` (8192). Full steps: `docs/local-model-runbook.md`.

### Memory budget

The Docker stack and the Ollama model server share the host's RAM. On the 24 GB M4 Pro backfill machine:

| Component | Estimated usage |
|---|---|
| Docker Desktop allocation | 8 GB (configured in Docker Desktop → Resources); container limits sum to 7.5 GB, see Services |
| Model weights | ~8.5 GB (llama3.1 8B Q8) · ~4.9 GB (8B Q4) |
| KV cache at `num_ctx=8192` | ~1 GB |
| OS + other processes | ~4–5 GB |

Recommended Docker Desktop memory limit: **8 GB**. 24B+ models do not fit next to the stack on 24 GB.
Reduce `num_ctx` in `registry.yaml` to lower KV cache if headroom is tight.

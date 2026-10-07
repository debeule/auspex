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
| `auspex-elasticsearch` | `elasticsearch:8.17.3` | 9200 | Log storage (ECS format) |
| `auspex-filebeat` | `elastic/filebeat:8.17.3` | — | Log shipper; Docker autodiscovery |
| `auspex-prometheus` | `prom/prometheus:v3.14.0` | 9090 | Metrics scraper and storage |
| `auspex-grafana` | `grafana/grafana-oss:13.0.2` | 3000 | Observability UI (logs + metrics) |
| `auspex-elasticsearch-setup` | `curlimages/curl:latest` | — | One-shot init: applies Elasticsearch ILM policy |
| `auspex-ingestion-scraper` | built from `services/ingestion-scraper` | 8000 | Scraper HTTP API (profile `app`) |
| `auspex-core-hub` | built from `services/core-hub` | 8080 | Signal processor (profile `app`) |
| `auspex-airflow` | `apache/airflow:3.3.1` | 8082 | DAG scheduler |

All ports bound to `127.0.0.1` — local only, intentional. Services in the `app` profile (`ingestion-scraper`, `core-hub`) only start with `--profile app`.

---

## Commands

```bash
docker compose -f docker/docker-compose.yml --env-file .env up -d --wait   # bring up
docker compose -f docker/docker-compose.yml --env-file .env down            # keep volumes
docker compose -f docker/docker-compose.yml --env-file .env down -v         # wipe volumes
```

`--wait` blocks until all healthchecks pass. `auspex-airflow` healthcheck is slow (~60s) — normal.

---

## Kafka topics

Provisioned by `provision.sh` on first startup from `topics.yaml`.

| Topic | Partitions | Retention | Notes |
|---|---|---|---|
| `auspex.raw.ingested` | 6 | 7 days | All fetched documents |
| `auspex.signals.extracted` | 6 | 90 days | Extracted signals only |
| `auspex.signals.corroborated` | 6 | 90 days | Corroboration events |
| `auspex.raw.ingested.dlt` | 6 | 30 days | Dead-letter for raw topic |
| `auspex.signals.extracted.dlt` | 6 | 30 days | Dead-letter for extracted topic |
| `auspex.signals.corroborated.dlt` | 6 | 30 days | Dead-letter for corroborated topic |

DLT partition count must match the source topic — Spring's `DeadLetterPublishingRecoverer` publishes to the same partition number.

If topic counts are wrong after a compose restart: `down -v` then `up` again to reprovision.

---

## Postgres databases

Two databases share one container:

| Database | Role | Created by |
|---|---|---|
| `auspex` | `auspex_app` | `postgres-init/01_airflow.sh` on first volume init |
| `airflow` | `airflow` | `postgres-init/01_airflow.sh` on first volume init |

Flyway runs schema migrations against `auspex` on every `core-hub` startup (`ddl-auto: validate`).

---

## Environment

All credentials come from root `.env`. Copy from `.env.example` and fill in:
- `SEC_USER_AGENT` — required for SEC EDGAR requests (format: `Name email@example.com`)
- `EXTRACTION_API_KEY` — API key for the extraction model endpoint
- `EXTRACTION_MODEL` — registry key matching an entry in `config/models/registry.yaml`
- `EPO_OPS_KEY` / `EPO_OPS_SECRET` — for patent connector

No defaults are baked into `docker-compose.yml`.

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

The Docker stack and the Ollama model server share the host's RAM. With a 36 GB MacBook:

| Component | Estimated usage |
|---|---|
| Docker Desktop allocation | 12–16 GB (configured in Docker Desktop → Resources) |
| Model weights | ~14 GB (mistral-small 24B Q4) · ~8.5 GB (llama3.1 8B Q8) · ~17 GB (gemma3 27B Q4) |
| KV cache at `num_ctx=8192` | ~1–3 GB |
| OS + other processes | ~4 GB |

Recommended Docker Desktop memory limit: **14 GB**. Leave ≥ 20 GB for the model server + OS.
Reduce `num_ctx` in `registry.yaml` to lower KV cache if headroom is tight.

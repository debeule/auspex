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
| `auspex-airflow` | `apache/airflow:3.3.1` | 8082 | DAG scheduler (Phase 2+) |

All ports bound to `127.0.0.1` — local only, intentional.

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
- `OPENAI_API_KEY` — for LLM extraction
- `EPO_OPS_KEY` / `EPO_OPS_SECRET` — for patent connector (currently blocked, Step 2.3)

No defaults are baked into `docker-compose.yml`.

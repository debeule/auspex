# Auspex

Local biotech signal research pipeline. Convergence of evidence across sources is the signal — no single document is.

---

## Architecture

Five public sources feed into `ingestion-scraper` (Python), which archives raw documents to MinIO and publishes extracted signals to Kafka. `core-hub` (Java/Spring) is the sole database writer: it consumes from Kafka, writes to Postgres (audit trail, signal state, corroborations) and Neo4j (signal graph), runs windowed corroboration, and exposes a REST API. The `dashboard` (Next.js) is the application's interface: the browser talks only to the dashboard's own server, which checks the single-user session and forwards to core-hub, the scraper and price-service. core-hub accepts writes only with the dashboard's bearer token and serves no CORS headers.

**Hard boundary:** `ingestion-scraper` writes only to MinIO and Kafka — never the database. `core-hub` is the only process that touches Postgres or Neo4j.

---

## Services

| Service | Stack | Role |
|---|---|---|
| [`ingestion-scraper`](services/ingestion-scraper/README.md) | Python 3.14, uv, Airflow-scheduled | Fetch → archive → pre-filter → LLM extract → publish. Stateless — no DB access. 5 connectors. |
| [`core-hub`](services/core-hub/README.md) | Java 25, Spring Boot 4.1 | Kafka consumer, sole DB writer, corroboration engine, confidence scoring, REST API. |
| [`dashboard`](services/dashboard/README.md) | Node 22, Next.js 16 | Control and research UI behind a single-user login; its route handlers forward to the backend services. Holds no data. |

---

## Infrastructure

Kafka 4.3 (KRaft, no Zookeeper), PostgreSQL 18, Neo4j 2026.05, MinIO, Airflow 3.3. All local, all via Docker Compose. See [`docker/README.md`](docker/README.md) for details.

---

## Quick start

```bash
cp .env.example .env          # fill in secrets and API keys — see SETUP.md
docker compose --profile app -f docker/docker-compose.yml --env-file .env up -d --build --wait
cd services/ingestion-scraper && uv sync --all-extras
uv run python scripts/run_pipeline.py --days 30 --sources clinicaltrials pubmed
curl http://localhost:8080/api/v1/signals/BEAM
```

---

## Development commands

| Purpose | Command |
|---|---|
| Bring up infra | `docker compose -f docker/docker-compose.yml --env-file .env up -d --wait` |
| Tear down (keep volumes) | `docker compose -f docker/docker-compose.yml --env-file .env down` |
| Tear down (wipe volumes) | `docker compose -f docker/docker-compose.yml --env-file .env down -v` |
| Python: install | `cd services/ingestion-scraper && uv sync --all-extras` |
| Python: unit tests | `cd services/ingestion-scraper && uv run pytest tests/unit -q` |
| Python: full suite | `cd services/ingestion-scraper && uv run pytest -q` |
| Python: lint + types | `cd services/ingestion-scraper && uv run ruff check . && uv run mypy src` |
| Java: unit tests | `cd services/core-hub && ./gradlew test` |
| Java: container tests | `cd services/core-hub && ./gradlew integrationTest` |
| Java: everything | `cd services/core-hub && ./gradlew check` |
| Backtesting: unit tests | `cd services/backtesting && uv run pytest tests/unit -q` |
| Dashboard: lint, types, tests | `cd services/dashboard && npm ci && npm run lint && npx tsc --noEmit && npm run test:ci` |
| Dashboard: build + bundle secret check | `cd services/dashboard && npm run build && npm run test:bundle` |
| Smoke test | `./verify_pipeline.sh` |

---

## Project structure

```
auspex/
├── services/
│   ├── ingestion-scraper/   Python scraper — fetch, archive, extract, publish
│   ├── core-hub/            Java Spring Boot — sole DB writer, corroboration, REST
│   └── backtesting/         Prices, market simulation, backtests; price refresh API
├── orchestration/          Airflow notes (DAGs live with their services)
├── docker/                  Docker Compose stack + startup data bootstrap
├── docs/                    Reference docs: requirements, prerequisites, runbooks
├── SETUP.md                 The manual steps, in order; everything else fills itself on `up`
├── CLAUDE.md                Claude Code operational context (auto-loaded)
├── PROGRESS.md              Execution ledger (test counts, step status)
├── VERSIONS.md              Pinned versions — single source of truth
└── DECISIONS.md             Append-only flag/choice log
```

---

## Current status

Phase 3 complete. Extraction precision 100% (golden set, 50 docs). Corroboration precision 86.7% (30 live samples, seed=42). Phase 4 (historical backfill + backtesting) is next. Step 2.3 (EPO OPS patent connector) blocked on credentials — register at developers.epo.org.

---

## Key constraints

- `ingestion-scraper` writes **only** to MinIO and Kafka — never the database
- `core-hub` is the **sole** writer to Postgres and Neo4j
- The MinIO archive is **unconditional and first** — before any other side effect
- Write order in `core-hub`: Neo4j → Postgres → acknowledge (ack-mode RECORD)
- Every `@Transactional` must be qualified — two transaction managers are on the classpath

---

## Watched tickers

SRPT, SPRB, BEAM, CRSP, CAPR, ABVX, RCKT, QURE (gene therapy / editing focus)

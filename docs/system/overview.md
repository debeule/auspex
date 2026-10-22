# System overview

Domain: SYS · Code: `services/`, `docker/docker-compose.yml`, `.env.example` · Last reviewed against: develop @ b7582c3

## Scope

What Auspex is as a whole: its name, the fixed identifiers of its parts and where each is set, the single-user premise, and the fact that it has no legacy system to preserve. The component map and glossary below orient the reader and link to the owners; they define nothing.

Not in this file: what logs may carry ([observability.md](../operations/observability.md)); the rule against plan-step names in code ([conventions.md](../engineering/conventions.md)); the invariants ([invariants.md](invariants.md)); the Kafka contracts ([contracts.md](contracts.md)).

## Component map

Descriptive and non-normative. Each arrow names the owner that states its rules.

| Component | Directory | Role |
|---|---|---|
| ingestion-scraper | `services/ingestion-scraper/` | Fetches source documents, archives them, extracts signals ([connectors.md](../ingestion/connectors.md), [pipeline.md](../ingestion/pipeline.md), [extraction.md](../ingestion/extraction.md)) |
| core-hub | `services/core-hub/` | Consumes the scraper's events, writes Postgres and Neo4j, corroborates, serves the HTTP API ([consumption.md](../core-hub/consumption.md), [storage.md](../core-hub/storage.md), [corroboration.md](../core-hub/corroboration.md), [http-api.md](../core-hub/http-api.md)) |
| price-service | `services/backtesting/` | Market and reference data, the universe, research panels, backtests ([market-data.md](../research/market-data.md), [backtesting.md](../research/backtesting.md)) |
| strategy-runtime | `services/strategy/` | Runs registered strategies on corroborated events into virtual books ([runtime.md](../strategy/runtime.md)) |
| backup and restore | `services/backup/` | Nightly backup and the restore one-shot ([backup.md](../operations/backup.md); restore's write access: INV-2) |
| dashboard | `services/dashboard/` | The researcher's browser interface and its server layer ([dashboard.md](../dashboard.md)) |
| Airflow | `services/*/dags/` | Schedules calls to the service HTTP APIs ([orchestration.md](../operations/orchestration.md)) |
| MinIO, Kafka, Postgres, Neo4j | `docker/docker-compose.yml` | The stores and the event backbone ([topology.md](../operations/topology.md)) |

Data flow:

- sources → ingestion-scraper: [connectors.md](../ingestion/connectors.md)
- ingestion-scraper → MinIO (archive first) and Kafka: INV-1, INV-13, [pipeline.md](../ingestion/pipeline.md), CON-002
- Kafka → core-hub → Postgres and Neo4j: INV-2, [consumption.md](../core-hub/consumption.md), [storage.md](../core-hub/storage.md)
- core-hub → corroborated topic → strategy runtime: CON-032, [corroboration.md](../core-hub/corroboration.md), [runtime.md](../strategy/runtime.md)
- browser → dashboard server layer → core-hub: [dashboard.md](../dashboard.md), [http-api.md](../core-hub/http-api.md)

## Naming table

Each identifier kind is fixed by SYS-002 and set in its authority. Names are read there, not here.

| Identifier | Authority | What it holds |
|---|---|---|
| Compose project | `.env.example` `COMPOSE_PROJECT_NAME`; `name:` in `docker/docker-compose.yml` | Prefix of every container, volume and network |
| Kafka topics | `docker/topics.yaml` | The raw-pointer, signal and corroborated topics and their dead-letter topics (roles: CON-002) |
| Java root package | `services/core-hub/src/main/java/dev/auspex/corehub/` | core-hub's code |
| Python import packages | each `pyproject.toml` and its `src/` package directory: `services/ingestion-scraper/src/`, `services/backtesting/src/`, `services/backup/src/`, `services/strategy/src/` | One package per Python service |
| MinIO buckets | `.env.example` `MINIO_BUCKET`; the `minio-init` service and `BACKUP_BUCKETS` in `docker/docker-compose.yml` | Three buckets: archived signal documents; market and reference data snapshots (prices, splits, universe, ownership, short interest, catalysts); strategy runtime state (virtual books, pauses, latency, offsets) |
| Postgres databases | `.env.example` `POSTGRES_DB`; `docker/postgres-init/` | The application database and Airflow's metadata database |
| Postgres roles | `.env.example` `POSTGRES_USER` and `AIRFLOW_DB_USER`; `docker/airflow-db-role/` | One role per database, no cross-grants |

## Requirements

- <a id="SYS-001"></a>**SYS-001** — The project is named Auspex. Its components keep descriptive names (`ingestion-scraper`, `core-hub`), never themed ones.
- <a id="SYS-002"></a>**SYS-002** — The identifiers in the naming table are fixed. Renaming one changes its authority file and the naming table in the same PR.
- <a id="SYS-003"></a>**SYS-003** — There is no legacy system: no prior schema, data or release behaviour to preserve. The Flyway migrations are the scripts that create the schema on an empty database.
- <a id="SYS-004"></a>**SYS-004** — Auspex is a single-user installation: one researcher, no per-user data and no per-user authorization. The schema consequence (no `user_id`) is in [storage.md](../core-hub/storage.md); the login is in [dashboard.md](../dashboard.md).

## Verification

| ID | Source | Verified by | Status |
|---|---|---|---|
| SYS-001 | `## 2026-10-22 — Living docs — PENDING — system ratification batch` (`CLAUDE.md:31`) | — | `pending-decision` |
| SYS-002 | `## 2026-10-22 — Living docs — PENDING — system ratification batch` (`CLAUDE.md:18-29`) | — | `pending-decision` |
| SYS-003 | `## 2026-10-22 — Living docs — PENDING — system ratification batch` (`CLAUDE.md:46-47`) | — | `pending-decision` |
| SYS-004 | `## 2026-09-20 — Watchlist backend — CHOICE — No user_id column; single-user installation, extensible`; `## 2026-10-08 — Control-surface scoping — CHOICE — dashboard runs in the stack behind its own server layer` | no test asserts the absence of per-user data | `untested` |

## Glossary

Definitions only; each links to the requirement that governs the term.

- **Signal** — one extracted research finding about one document, carried as a `ResearchSignalEvent` (CON-008).
- **Raw pointer** — the message that tells core-hub a document was archived, without its content (CON-005).
- **Corroboration** — signals from distinct sources about the same entity within the window ([corroboration.md](../core-hub/corroboration.md)), published as a `CorroboratedSignalEvent` (CON-032).
- **Entity key** — the normalized entity a corroboration is about; the corroborated topic's message key (CON-003).
- **Participant set** — the signals in one corroboration, identified by `participants_hash` (CON-025).
- **DLT** — a dead-letter topic, `<source topic>.dlt` (CON-035).
- **Natural key** — the declared key a store path is idempotent on (INV-10, CON-021 to CON-027).
- **As-of** — the point in time a research or strategy read is evaluated at; nothing published later is visible ([contract.md](../strategy/contract.md), [backtesting.md](../research/backtesting.md)).
- **Known-at delay** — the delay added to a publication or corroboration time before a strategy may act on it ([evaluation-protocol.md](../research/evaluation-protocol.md)).

## Rationale

Non-normative. Sources: `CLAUDE.md:19` (the name) and requirements §14 ("Settled — do not relitigate").

- **The name.** The Roman auspex read scattered signs for meaning, which is the job: no single source is evidence, convergence is.
- **Settled choices** (requirements §14), each now stated by its owner:
  - sync-only execution: INV-8;
  - Airflow as scheduler with Kafka as backbone, and Airflow metadata in a separate logical database: [orchestration.md](../operations/orchestration.md), [topology.md](../operations/topology.md);
  - a first-class signal node in the graph: [storage.md](../core-hub/storage.md);
  - `confidence_score` as a 0.0–1.0 float: CON-012;
  - UTC everywhere: INV-9;
  - Testcontainers over mocks at the store boundary: [verification.md](../engineering/verification.md);
  - test-first: INV-15.
- **Free-tier-first tooling** (requirements §14). Free sources, libraries and services are preferred over paid ones. It is a preference, not a requirement, and lives only here.

## Retired requirements

None.

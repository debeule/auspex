# core-hub

Consumes `auspex.raw.ingested` and `auspex.signals.extracted` from Kafka, writes Postgres (audit trail, signal state, extraction history, source observations, corroborations) and Neo4j (signal graph), runs the corroboration scan, publishes `auspex.signals.corroborated`, and serves a REST API. It is the only writer of both stores (INV-2 in [docs/system/invariants.md](../../docs/system/invariants.md)).

Commands: [AGENTS.md](AGENTS.md).

---

## Where the rules are

| Subject | Owner |
|---|---|
| Listeners, write order and offset commit, retries, dead letters and their replay, store-outage pause, health reporter | [docs/core-hub/consumption.md](../../docs/core-hub/consumption.md) |
| Postgres tables, Flyway, the graph model, company tickers, transactions | [docs/core-hub/storage.md](../../docs/core-hub/storage.md) |
| Corroboration: definition, record, scan, scorer | [docs/core-hub/corroboration.md](../../docs/core-hub/corroboration.md) |
| REST endpoints, write token, CORS | [docs/core-hub/http-api.md](../../docs/core-hub/http-api.md) |
| Payloads, keys, dead-letter topics | [docs/system/contracts.md](../../docs/system/contracts.md) |

---

## Data model

**Postgres tables:** `raw_fetch_audit`, `signal_current`, `signal_extraction_history`, `source_observation`, `corroboration`, plus the watchlist tables. What each holds and its natural key: [storage.md](../../docs/core-hub/storage.md).

**Neo4j:** `(:Signal)` nodes and the entity nodes `(:GeneTarget)`, `(:Mechanism)`, `(:Company)`, joined by `TARGETS`, `USES_MECHANISM` and `MENTIONS`; the model is in [storage.md](../../docs/core-hub/storage.md).

---

## Build layout

- Gradle Kotlin DSL (`build.gradle.kts`) with a committed wrapper; versions in `gradle/libs.versions.toml` (ENG-053 in [conventions.md](../../docs/engineering/conventions.md)).
- Root package `dev.auspex.corehub` under `src/main/java/`; Flyway scripts in `src/main/resources/db/migration/` (HUB-019 and HUB-020 in [storage.md](../../docs/core-hub/storage.md)).

## Testing layout

| Path | Task | Holds |
|---|---|---|
| `src/test/java/**/*Test.java` | `test` | unit tests, no Spring context |
| `src/integrationTest/java/**/*IT.java` | `integrationTest` | container-backed tests (Postgres, Neo4j, Kafka) |

How the container tests are run is ENG-006 and ENG-007 in [verification.md](../../docs/engineering/verification.md). Every `CorroborationService` implementation runs the abstract `CorroborationServiceContractTest` unmodified (COR-001 in [corroboration.md](../../docs/core-hub/corroboration.md)).

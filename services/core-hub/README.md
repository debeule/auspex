# core-hub

Sole database writer. Consumes `auspex.raw.ingested` and `auspex.signals.extracted` from Kafka, writes Postgres (audit trail, signal state, corroborations) and Neo4j (signal graph), runs windowed corroboration, and exposes a REST API.

---

## Architecture

```
Kafka listeners → service layer → Neo4j → Postgres → acknowledge
```

Write order is **Neo4j → Postgres → acknowledge** (ack-mode RECORD). Never commit the Kafka offset before both stores have returned. `core-hub` is the only process that writes to Postgres or Neo4j.

---

## Data model

**Postgres tables**

| Table | Purpose |
|---|---|
| `raw_fetch_audit` | Every document fetched, regardless of signal outcome |
| `signal_current` | Latest extracted state per event_id |
| `signal_extraction_history` | Full extraction history per event_id |
| `source_observation` | One row per (event_id, source_type) |
| `corroboration` | Active corroboration records |
| `corroboration_watermark` | Scan progress for the scheduled corroboration job |

**Neo4j nodes and relationships**

| Node | Key property |
|---|---|
| `(:Signal)` | `event_id` |
| `(:Company)` | `ticker` or normalized `name` |
| `(:GeneTarget)` | `symbol` |
| `(:Mechanism)` | `name` |

Relationships: `[:OBSERVED_BY]`, `[:TARGETS]`, `[:IMPLICATES]`

Flyway owns the Postgres schema (`ddl-auto: validate`). Never use `update`.

---

## Corroboration

Two signals from different `source_type` values, same entity, within a 90-day window. One active row per entity per participant set; superseded by new participants via `<@` array containment.

Scorer: `score = 0.7 × diversity_factor + 0.3 × recency_factor`, clamped [0, 1].
- `diversity_factor = min(1, (source_count − 1) / 4)`
- `recency_factor` decays linearly to 0 at the 90-day boundary

`CorroborationService` is abstract — `CorroborationServiceContractTest` re-runs at steps 2.8 and 6.4 against new implementations without modification.

---

## REST API

`GET /api/v1/signals/{ticker}` — returns direct signals + corroborated signals for the ticker.

- Ticker must be in the configured allowlist.
- Returns 404 if no signals found.
- Cypher query returns both direct observations and corroborated neighbors.
- Injection test verifies both Cypher-injection and MATCH DELETE payloads are rejected.

`GET /api/v1/extractions/models?source_type=&from=YYYY-MM-DD&to=YYYY-MM-DD` — per `extraction_model`, the number of signals of that source whose `published_date` falls in the inclusive window. Used by the historical backfill's dry run to report lineage overlap (the scraper never reads Postgres).

---

## Development commands

```bash
./gradlew test                              # unit only — inner loop
./gradlew integrationTest                   # container-backed only
./gradlew check                             # everything (unit + integration + archunit)
./gradlew test --tests '*SomeTest'          # one class
./gradlew timezoneCheck                     # forked JVM, non-UTC default TZ
./gradlew test --rerun-tasks                # defeat up-to-date caching
```

---

## Build layout

- **Kotlin DSL** (`build.gradle.kts`), Gradle 9.7.0, committed wrapper.
- Versions in `gradle/libs.versions.toml` (version catalog) — must match `VERSIONS.md`.
- Spring Boot 4.1 Gradle plugin applies the BOM. Do not add `io.spring.dependency-management`.
- Java 25 toolchain pinned explicitly in the build script.
- Integration tests use the **JVM Test Suite** plugin: separate `integrationTest` source set at `src/integrationTest/java`, wired into `check`.

---

## Testing layout

| Path | Runs with | Notes |
|---|---|---|
| `src/test/java/**/*Test.java` | `./gradlew test` | Unit tests — no Spring context |
| `src/integrationTest/java/**/*IT.java` | `./gradlew integrationTest` | Container-backed (Postgres, Neo4j, Kafka) |

Containers are **static singletons** — one JVM start per suite run. Truncate between tests, never restart. Target: container suite under 3 minutes.

`CorroborationServiceContractTest` is **abstract** — do not inline its test cases into any concrete test.

---

## Key constraints

- `@Transactional` must always be qualified — two transaction managers are on the classpath
- `MERGE`, never `CREATE`, for signal and entity nodes
- Parameterized queries only — ArchUnit enforces this at build time
- `confidence_score` is `BigDecimal` in DTOs, `NUMERIC(4,3)` in Postgres, `double` in Neo4j via an explicit converter
- Java 25 records, no Lombok

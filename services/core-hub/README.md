# core-hub

Sole database writer. Consumes `auspex.raw.ingested` and `auspex.signals.extracted` from Kafka, writes Postgres (audit trail, signal state, corroborations) and Neo4j (signal graph), runs windowed corroboration, and exposes a REST API.

---

## Architecture

```
Kafka listeners → service layer → Neo4j → Postgres → acknowledge
```

Write order is **Neo4j → Postgres → acknowledge** (ack-mode RECORD). Never commit the Kafka offset before both stores have returned. `core-hub` is the only process that writes to Postgres or Neo4j.

### Failures and dead letters

- **Store outages pause the listeners.** `StoreAvailabilityGuard` probes Postgres (`SELECT 1`) and Neo4j (`verifyConnectivity`) every `auspex.kafka.store-check-interval-ms` (5 s). While either is unreachable the signal and raw listener containers are paused, so records wait on the topic instead of spending their retries; they resume when both stores answer. Pause and resume are logged as warnings.
- **Transient failures** get 1 attempt + 2 retries with exponential back-off, then the DLT: 5 s, then 30 s by default (`AUSPEX_KAFKA_RETRY_INITIAL_MS`, `AUSPEX_KAFKA_RETRY_MULTIPLIER`). Deserialization, validation and unknown-major-version failures go to the DLT at once.
- **Dead letters keep their wire form.** The `.dlt` record carries the original key and headers plus Spring's `kafka_dlt-*` diagnostics; the value is the original bytes, the original string, or the signal re-serialized as snake_case JSON, so it can be replayed.

---

## Data model

**Postgres tables**

| Table | Purpose |
|---|---|
| `raw_fetch_audit` | Every document fetched, regardless of signal outcome |
| `signal_current` | Latest extracted state per event_id, including the company-level fields |
| `signal_extraction_history` | Full extraction history per event_id |
| `source_observation` | One row per (event_id, source_type) |
| `corroboration` | Active corroboration records |
| `corroboration_watermark` | Scan progress for the scheduled corroboration job |

**Neo4j nodes and relationships**

| Node | Key property |
|---|---|
| `(:Signal)` | `event_id` |
| `(:Company)` | `name` (merge key); `ticker` set when known |
| `(:GeneTarget)` | `name` |
| `(:Mechanism)` | `name` |

Relationships (requirements §9): `(:Signal)-[:TARGETS]->(:GeneTarget)`, `(:Signal)-[:USES_MECHANISM]->(:Mechanism)`, `(:Signal)-[:MENTIONS]->(:Company)`. An ArchUnit rule fails the build if `persistence` writes any other type.

**Company tickers.** `CompanyTickerService` matches a company's normalized name (`CompanyNameNormalizer`: lower-case, punctuation removed, trailing `inc`/`corp`/`corporation`/`co`/`ltd`/`plc`/`nv`/`sa`/`ag`/`holdings` stripped) against the normalized SEC filer titles in `SecTickerCache`. `ticker` is set only when exactly one SEC ticker matches; an unmatched or ambiguous merge never clears an existing ticker. Adding a ticker to the watchlist sets it on tickerless `Company` nodes whose normalized name matches that ticker's SEC title.

Flyway owns the Postgres schema (`ddl-auto: validate`). Never use `update`.

---

## Corroboration

Two signals from different `source_type` values, same entity, within a 90-day window. One active row per entity per participant set; superseded by new participants via `<@` array containment.

Scorer: `score = 0.7 × diversity_factor + 0.3 × recency_factor`, clamped [0, 1].
- `diversity_factor = min(1, (source_count − 1) / 4)`
- `recency_factor` decays linearly to 0 at the 90-day boundary

The scheduled scan reads signals ingested after the watermark in `corroboration_state` (full timestamp comparison) and publishes to `auspex.signals.corroborated` inside one Postgres transaction: the inserts and the new watermark commit only after every send is acknowledged, so a failed send leaves the batch for the next scan.

`CorroborationService` is abstract — `CorroborationServiceContractTest` re-runs at steps 2.8 and 6.4 against new implementations without modification.

---

## REST API

Every request under `/api` that is not a GET or HEAD needs `Authorization: Bearer ${CORE_HUB_WRITE_TOKEN}`; without it, or with no token configured, the answer is 401. Only the dashboard's server sends the token. There are no CORS mappings: browsers reach core-hub through the dashboard, never directly.

`GET /api/v1/watchlist/{ticker}/summary` — the watchlist entry's gene-target stats, the signals that mention the company (newest first), the corroborations on its tracked targets, and totals.

`POST /api/dlt/{topic}/replay` — re-publishes the records on `auspex.signals.extracted.dlt` or `auspex.raw.ingested.dlt` (any other topic is 404) to their source topic with the original key, value and headers (minus `kafka_dlt-*`), and returns `{"replayed": n}`. Only records already on the DLT when the call starts are replayed. Progress is committed per record in consumer group `corehub-dlt-replay`, so a record is replayed at most once; writes are idempotent on their natural keys, so replaying a record that was already stored is safe. Needs the write token.

`GET /api/v1/signals/{ticker}` — returns direct signals + corroborated signals for the ticker.

- Ticker must be in the configured allowlist.
- Returns 404 if no signals found.
- Cypher query returns both direct observations and corroborated neighbors.
- Injection test verifies both Cypher-injection and MATCH DELETE payloads are rejected.

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
- Writes under `/api` require the bearer write token (`WriteTokenInterceptor`); no CORS

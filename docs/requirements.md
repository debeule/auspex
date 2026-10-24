# Auspex — Technical Requirements & Constraints

Not authoritative. Superseded by `docs/` at the living-docs cutover. Kept so that citations in `specs/done/` and `DECISIONS.md` resolve. Owners are listed in [docs/README.md](README.md).

| Legacy § | Original heading or label | Now owned by | IDs |
|---|---|---|---|
| §0 | Assumptions (unresolved questions) | the rows §0.1 to §0.7 | ING-026 EXT-007 CON-008 COR-002 HUB-036 |
| §0.1 | Live monitor or historical research instrument? | [evaluation-protocol.md](research/evaluation-protocol.md); the amendment stays with `specs/live-trading.md` (`## 2026-10-17 — Living docs — CHOICE — historical-instrument amendment out of scope`) | EVA-028 |
| §0.2 | Where does cursor state live? | [pipeline.md](ingestion/pipeline.md), [orchestration.md](operations/orchestration.md) | ING-026 OPS-032 |
| §0.3 | Backfill depth | [connectors.md](ingestion/connectors.md) (lookback); the backfill is `specs/historical-backfill.md` | ING-004 |
| §0.4 | LLM budget | [extraction.md](ingestion/extraction.md); the backfill budget is `specs/historical-backfill.md` | EXT-007 |
| §0.5 | One gene target per document? | [contracts.md](system/contracts.md) | CON-008 |
| §0.6 | Kafka Streams: requirement or learning goal? | [corroboration.md](core-hub/corroboration.md) | COR-002 |
| §0.7 | Signals with no resolvable ticker | [storage.md](core-hub/storage.md), [http-api.md](core-hub/http-api.md) | HUB-036 HUB-046 |
| §0 · On 0.3 | Note on 0.3: forward-only collection cannot support a backtest | [backtesting.md](research/backtesting.md) | rationale: [backtesting.md Rationale](research/backtesting.md#rationale) |
| §1 | System Stack & Dependencies | [conventions.md](engineering/conventions.md); versions in `VERSIONS.md` | ENG-048 ENG-053 |
| §1 · Runtime | Runtime (Python; Java, Spring Boot, Gradle, no Lombok) | [conventions.md](engineering/conventions.md) | ENG-048 ENG-053 ENG-054 |
| §1 · Execution model | Execution model: fully synchronous | [invariants.md](system/invariants.md), [connectors.md](ingestion/connectors.md) | INV-8 ING-001 |
| §1 · Core Libraries | Core libraries; `httpx` only via `RateLimitedClient` | [connectors.md](ingestion/connectors.md); the list is `pyproject.toml` | ING-005 |
| §1 · Test Libraries (§13) | Test libraries | [verification.md](engineering/verification.md) | ENG-004 ENG-006 |
| §1 · Dependencies | core-hub dependencies | [conventions.md](engineering/conventions.md); the list is `gradle/libs.versions.toml` | ENG-053 |
| §1 · Test | core-hub test stack | [verification.md](engineering/verification.md) | ENG-006 ENG-007 |
| §1 · Kafka 4.3 (KRaft) | Kafka: topics from `topics.yaml` | [contracts.md](system/contracts.md), [topology.md](operations/topology.md) | CON-001 OPS-009 |
| §1 · PostgreSQL 18.6 | PostgreSQL: contents, Airflow database, Flyway | [topology.md](operations/topology.md), [storage.md](core-hub/storage.md) | OPS-012 HUB-019 |
| §1 · Neo4j 2026.05 (Community) | Neo4j: versioned startup constraints | [storage.md](core-hub/storage.md) | HUB-032 |
| §1 · MinIO | MinIO: credentials without defaults, ports on 127.0.0.1 | [topology.md](operations/topology.md) | OPS-005 OPS-006 |
| §2 | Kafka Topic Design (topic table) | [contracts.md](system/contracts.md) | CON-002 CON-003 CON-005 CON-006 CON-037 |
| §2 · Partitioning | Partitioning: keys are document identity | [contracts.md](system/contracts.md) | CON-003 |
| §2 · Partitions and replication | Partitions and replication; DLT partition count | [contracts.md](system/contracts.md); counts in `docker/topics.yaml` | CON-004 |
| §2 · DLT naming | DLT naming: lowercase `.dlt`, partition `-1` | [contracts.md](system/contracts.md) | CON-035 CON-036 |
| §2 · Retention | Retention per topic | [contracts.md](system/contracts.md); values in `docker/topics.yaml` | CON-001 |
| §3 | Architectural Boundaries & Rules | [invariants.md](system/invariants.md) | INV-1 INV-2 INV-6 INV-7 INV-8 INV-9 INV-10 INV-11 INV-12 |
| §3.1 | Strict event-driven decoupling | [invariants.md](system/invariants.md) | INV-1 |
| §3.2 | Single database writer | [invariants.md](system/invariants.md) | INV-2 |
| §3.3 | Environment security | [invariants.md](system/invariants.md), [observability.md](operations/observability.md) (log contract) | INV-6 OPS-041 |
| §3.4 | Schema symmetry | [invariants.md](system/invariants.md), [contracts.md](system/contracts.md) | INV-7 CON-008 |
| §3.5 | Synchronous throughout | [invariants.md](system/invariants.md) | INV-8 |
| §3.6 | Timestamps are UTC, always | [invariants.md](system/invariants.md), [contracts.md](system/contracts.md) | INV-9 CON-011 |
| §3.7 | Idempotent writes, per declared natural key | [invariants.md](system/invariants.md), [contracts.md](system/contracts.md) | INV-10 CON-021 CON-022 CON-023 CON-024 CON-025 CON-026 CON-027 |
| §3.8 | Write ordering and offset commit | [consumption.md](core-hub/consumption.md), [storage.md](core-hub/storage.md) | HUB-014 HUB-024 HUB-026 HUB-040 |
| §3.9 | Consumer semantics | [consumption.md](core-hub/consumption.md) | HUB-001 |
| §3.10 | Dead-letter handling | [invariants.md](system/invariants.md), [contracts.md](system/contracts.md), [consumption.md](core-hub/consumption.md) | INV-11 CON-037 HUB-002 HUB-004 HUB-005 HUB-006 HUB-007 HUB-008 HUB-009 HUB-012 |
| §3.11 | Parameterized queries only | [invariants.md](system/invariants.md), [storage.md](core-hub/storage.md), [http-api.md](core-hub/http-api.md) | INV-12 HUB-027 HUB-044 |
| §3.12 | Nothing dies silently | [invariants.md](system/invariants.md), [consumption.md](core-hub/consumption.md) | INV-11 HUB-052 |
| §4 | Correlation / Linking | [corroboration.md](core-hub/corroboration.md) | COR-003 |
| §4.1 | The corroboration record | [corroboration.md](core-hub/corroboration.md), [backtesting.md](research/backtesting.md) | COR-005 COR-006 COR-007 CON-025 HUB-046 RES-067 RES-071 |
| §4.2 | Scan strategy | [invariants.md](system/invariants.md), [corroboration.md](core-hub/corroboration.md) | INV-5 COR-002 COR-008 COR-009 COR-010 COR-011 |
| §5 | Orchestration and Cursor State | [orchestration.md](operations/orchestration.md), [pipeline.md](ingestion/pipeline.md) | INV-3 OPS-024 OPS-025 OPS-032 ING-026 |
| §5 · Airflow 3.3 | Airflow 3.3 changes; Airflow owns when, Kafka what after | [orchestration.md](operations/orchestration.md) | OPS-025 |
| §5 · The pipeline is stateless with respect to cursors | The pipeline is stateless with respect to cursors | [pipeline.md](ingestion/pipeline.md) | ING-026 |
| §5 · The DAG task owns the cursor | The DAG task owns the cursor | [orchestration.md](operations/orchestration.md) | OPS-032 OPS-035 |
| §5 item 1 | Read the Variable; default `now − initial_lookback` | [orchestration.md](operations/orchestration.md), [connectors.md](ingestion/connectors.md) | OPS-034 ING-004 |
| §5 item 2 | Call the pipeline | [orchestration.md](operations/orchestration.md) | OPS-035 INV-3 |
| §5 item 3 | Write back `next_cursor`, never now; fail after writing | [orchestration.md](operations/orchestration.md) | OPS-035 |
| §5 item 4 | Failed request leaves the Variable untouched; backfill never writes the live cursor | [orchestration.md](operations/orchestration.md); the backfill is `specs/historical-backfill.md` | OPS-036 |
| §5 · DAG configuration is not optional | DAG configuration: `catchup`, `max_active_runs`, staggered schedules | [orchestration.md](operations/orchestration.md) | OPS-025 OPS-028 |
| §6 | Source Connector Architecture | [connectors.md](ingestion/connectors.md), [pipeline.md](ingestion/pipeline.md) | INV-4 ING-001 ING-022 |
| §6.1 | The connector contract is pure | [connectors.md](ingestion/connectors.md) | ING-001 INV-4 |
| §6.2 | The pipeline is a named component | [pipeline.md](ingestion/pipeline.md) | ING-022 ING-023 |
| §6.2 · Per-document error isolation | Per-document error isolation; `RunResult` counts | [pipeline.md](ingestion/pipeline.md), [orchestration.md](operations/orchestration.md) | ING-024 ING-025 ING-041 OPS-035 |
| §6.2 · Publish is not fire-and-forget | Publish is not fire-and-forget | [pipeline.md](ingestion/pipeline.md) | ING-029 |
| §6.3 | `RawDocument` | [connectors.md](ingestion/connectors.md) | ING-001 ING-016 |
| §6.4 | Entity normalization seam | [pipeline.md](ingestion/pipeline.md) | ING-038 |
| §6.5 | Rate limiting is shared and configured | [connectors.md](ingestion/connectors.md), [topology.md](operations/topology.md) | ING-005 ING-006 ING-007 ING-020 OPS-023 |
| §6.6 | Pre-filter before extraction | [pipeline.md](ingestion/pipeline.md), [extraction.md](ingestion/extraction.md) | ING-037 ING-025 EXT-007 EXT-015 |
| §6.7 | Per-source timestamp mapping | [connectors.md](ingestion/connectors.md), [backtesting.md](research/backtesting.md) | ING-009 RES-068 |
| §6.7 · Rule: `published_date` is always the date the information became public | `published_date` is the date the information became public; per-source table | [connectors.md](ingestion/connectors.md), [backtesting.md](research/backtesting.md) | ING-009 ING-010 ING-011 ING-012 ING-013 ING-014 ING-015 RES-067 RES-068 |
| §6.8 | Verified source APIs | [connectors.md](ingestion/connectors.md) | ING-006 |
| §6.9 | Regulatory connector rescoped | [connectors.md](ingestion/connectors.md) | ING-020 |
| §6.9 · Verified: openFDA has no designations endpoint | openFDA has no designations endpoint | [connectors.md](ingestion/connectors.md#known-traps) (Known traps) | ING-020 |
| §6.9 · `fda_approval` | `fda_approval` source | [connectors.md](ingestion/connectors.md) | ING-020 |
| §6.9 · `fda_designation` | Optional `fda_designation` source | [connectors.md](ingestion/connectors.md) (retired) | ING-021 |
| §7 | Raw Storage, Deduplication, and Precedence | [invariants.md](system/invariants.md), [pipeline.md](ingestion/pipeline.md) | INV-13 ING-030 |
| §7 · The archive is unconditional | The archive is unconditional | [invariants.md](system/invariants.md) | INV-13 |
| §7 · Object key | Archive object key | [pipeline.md](ingestion/pipeline.md) | ING-030 INV-9 |
| §7.1 | Precedence rule | [pipeline.md](ingestion/pipeline.md) | ING-031 ING-032 ING-033 ING-034 ING-035 ING-036 |
| §7.1 item 1 | Archive always | [invariants.md](system/invariants.md) | INV-13 |
| §7.1 item 2 | Dedup gates extraction and publish only | [pipeline.md](ingestion/pipeline.md) | ING-031 |
| §7.1 item 3 | Within a document: same hash skips, new hash is an amendment | [pipeline.md](ingestion/pipeline.md) | ING-032 ING-033 |
| §7.1 item 4 | An amendment publishes under the same `event_id` | [pipeline.md](ingestion/pipeline.md) | ING-033 |
| §7.1 item 5 | Across sources: the `canonical_id` marker | [pipeline.md](ingestion/pipeline.md) | ING-034 ING-035 |
| §7.1 item 6 | No `canonical_id`: cross-source duplicates accepted | [pipeline.md](ingestion/pipeline.md) | ING-036 |
| §7.1 · Embedding-similarity dedup is cut | Embedding-similarity dedup is cut | [pipeline.md](ingestion/pipeline.md) | rationale: [pipeline.md Rationale](ingestion/pipeline.md#rationale) |
| §7.1 · Downstream | Postgres warehouse; DuckDB as a next step | [storage.md](core-hub/storage.md) | history: a possible next step, no requirement; tables in [storage.md](core-hub/storage.md) |
| §8 | Historical Price Data | [market-data.md](research/market-data.md) | RES-001 |
| §8 · Fetch once, then never again | Fetch once, then never again; Stooq fallback | [market-data.md](research/market-data.md), [panels.md](research/panels.md) | RES-001 RES-003 RES-029 |
| §9 | Neo4j Graph Data Model | [storage.md](core-hub/storage.md) | HUB-030 HUB-031 HUB-033 |
| §9 · `Company` MERGEs on normalized `name`, not `ticker` | `Company` merges on name, not ticker | [storage.md](core-hub/storage.md) | HUB-034 |
| §9 · `confidence_score` is a `double` in the graph | `confidence_score` is a double in the graph | [storage.md](core-hub/storage.md) | HUB-029 |
| §9 · Constraints and indexes (from Step 1.3) | Graph constraints and indexes | [storage.md](core-hub/storage.md) | HUB-032 |
| §9 · The corroboration pattern is typed | The corroboration pattern is typed | [corroboration.md](core-hub/corroboration.md) | COR-003 |
| §10 | Identity, Versioning, Value Contracts | [contracts.md](system/contracts.md) | INV-14 CON-018 |
| §10.1 | Document identity | [invariants.md](system/invariants.md), [contracts.md](system/contracts.md), [connectors.md](ingestion/connectors.md), [storage.md](core-hub/storage.md) | INV-14 CON-018 CON-019 CON-020 ING-008 HUB-028 |
| §10.2 | `ResearchSignalEvent` | [contracts.md](system/contracts.md) | CON-008 CON-013 CON-014 CON-015 CON-016 CON-017 |
| §10.3 | `confidence_score` | [contracts.md](system/contracts.md), [consumption.md](core-hub/consumption.md) | CON-012 HUB-007 HUB-008 |
| §10.3 · Java uses `BigDecimal` with `@NotNull @DecimalMin("0.0") @DecimalMax("1.0")`, not a primitive `double` | Java `BigDecimal` with bean constraints; `@Valid`; storage types | [contracts.md](system/contracts.md), [consumption.md](core-hub/consumption.md), [storage.md](core-hub/storage.md) | CON-012 HUB-011 HUB-029 |
| §10.4 | Schema versioning | [contracts.md](system/contracts.md), [consumption.md](core-hub/consumption.md) | CON-028 CON-029 CON-030 CON-031 HUB-003 HUB-006 |
| §10.4 · Re-extraction is an explicit operation | Re-extraction is an explicit operation | [extraction.md](ingestion/extraction.md), [corroboration.md](core-hub/corroboration.md) | EXT-019 COR-011 |
| §11 | Extraction Contract | [extraction.md](ingestion/extraction.md) | EXT-001 |
| §11.1 | "Not a signal" is a first-class outcome | [extraction.md](ingestion/extraction.md) | EXT-001 EXT-002 |
| §11.2 | Untrusted input | [extraction.md](ingestion/extraction.md) | EXT-003 EXT-004 EXT-005 EXT-006 |
| §11.3 | Extraction quality is measured | [extraction.md](ingestion/extraction.md) | EXT-007 EXT-013 EXT-015 |
| §12 | Observability | [observability.md](operations/observability.md) | OPS-040 OPS-059 |
| §12 · Structured JSON logs | Structured JSON logs | [observability.md](operations/observability.md) | OPS-040 |
| §12 · Run summary | Run summary per run | [pipeline.md](ingestion/pipeline.md) | ING-040 |
| §12 · A `@Scheduled` health reporter | core-hub health reporter | [consumption.md](core-hub/consumption.md) | HUB-052 |
| §12 · Cursor position is visible | Cursor position visible in the Airflow UI | [orchestration.md](operations/orchestration.md) | OPS-033 |
| §13 | Testing Strategy — TDD | [invariants.md](system/invariants.md), [verification.md](engineering/verification.md) | INV-15 ENG-003 |
| §13 · `ingestion-scraper` — pytest | ingestion-scraper test rules | [verification.md](engineering/verification.md) | ENG-003 ENG-004 ENG-005 ENG-006 |
| §13 · `core-hub` — JUnit 5 + Testcontainers | core-hub test rules | [verification.md](engineering/verification.md) | ENG-005 ENG-006 ENG-007 ENG-008 |
| §13 · The contract fixture is generated | The contract fixture is generated (the path given was stale: the fixture is `signal_event_v1.json`) | [invariants.md](system/invariants.md), [contracts.md](system/contracts.md) | INV-7 CON-009 |
| §13 · Named guards | Named guards; `verify_pipeline.sh` is a smoke test | [verification.md](engineering/verification.md) | ENG-009 |
| §14 | Settled — do not relitigate | [change-workflow.md](engineering/change-workflow.md) and the Rationale sections | ENG-023; rationale: [overview](system/overview.md#rationale), [orchestration](operations/orchestration.md#rationale), [storage](core-hub/storage.md#rationale), [verification](engineering/verification.md#rationale) |

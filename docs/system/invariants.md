# System invariants

Domain: INV · Code: `services/`, `docker/docker-compose.yml` · Last reviewed against: develop @ b7582c3

## Scope

The fifteen rules that hold across every service. Numbering follows the invariants list of the root `CLAUDE.md`, so a citation "Invariant N" in a spec means `INV-N` here. Each item carries its current text and, under it, scope lines that clarify it, the only text of each approved exception, and the amendment record when the text changed. A scope line never narrows an invariant; only an exception line does, and only with a cited `CHOICE`.

Not in this file: what each invariant requires in detail on Kafka ([contracts.md](contracts.md), CON), and how each domain applies it (the owner docs listed in [the docs index](../README.md)). Requirement IDs of other namespaces never restate an invariant; they apply it.

## Requirements

- <a id="INV-1"></a>**INV-1** — `ingestion-scraper` writes only to MinIO and Kafka. Nothing else. Ever.
  - Scope: covers the service's code and its scripts. Writing an Airflow Variable or a local state file is a write outside MinIO and Kafka, so cursor state belongs to the orchestrator, which reads and writes it around the scraper's HTTP call ([orchestration.md](../operations/orchestration.md), [pipeline.md](../ingestion/pipeline.md)).
  - Scope (pending: `## 2026-10-22 — Living docs — PENDING — system ratification batch`): reading is not writing. `services/ingestion-scraper/scripts/sample_corroborations.py` reads Postgres and Neo4j (SELECT and MATCH only) to sample corroborations for review; that read is within INV-1, which restricts writes. This replaces the stricter "no DB access" wording of the nested service agent files.
- <a id="INV-2"></a>**INV-2** — `core-hub` is the sole writer to the application DB and Neo4j.
  - Scope: the application database and Neo4j. The Airflow metadata database belongs to Airflow. The backup service only reads ([backup.md](../operations/backup.md)).
  - Exception (approved by `## 2026-10-17 — Living docs — CHOICE — restore exception to invariant 2`, with `## 2026-10-09 — Stack backup — CHOICE — nightly backup to a folder on the Mac` and `## 2026-10-10 — Stack backup — CHOICE — client tools from the server image, memory and restore semantics`): the `restore` one-shot (compose profile `restore`, module `services/backup/src/auspex_backup/restore.py`) writes both Postgres databases, Neo4j and the backed-up MinIO buckets, and only into stores that hold no data: no table outside the system schemas in either database, no Neo4j node, no object in any backed-up bucket. Every target is checked before anything is written, with the `app` profile stopped; if any target holds data, it refuses and writes nothing. The procedure is the runbook [backup-restore.md](../backup-restore.md).
- <a id="INV-3"></a>**INV-3** — DAG code calls the scraper HTTP API (`/ingest/<source_type>`). No ingestion logic in DAGs; no pipeline logic in `fetch_since()`.
  - Scope: the ingestion DAG and the connectors. Other DAGs follow the same pattern (call a service HTTP API, no logic in the DAG); that policy is in [orchestration.md](../operations/orchestration.md).
- <a id="INV-4"></a>**INV-4** — New source = a `SourceConnector` + a `sources.yaml` entry. No `if source_type == ...` anywhere in shared code.
  - Scope: market and reference snapshots (prices, short interest, SEC ownership, the catalyst panel, filing text) are not sources under INV-4; they are research data with their own fetch paths ([market-data.md](../research/market-data.md), [panels.md](../research/panels.md)).
  - Exception (approved by `## 2026-09-20 — Watchlist backend — CHOICE — core-hub calls ClinicalTrials.gov directly`; placed under INV-4 pending `## 2026-10-22 — Living docs — PENDING — system ratification batch`): core-hub's watchlist preview calls the ClinicalTrials.gov API directly for one interactive lookup. Nothing it returns is archived, published or stored as a signal. This is the only place the exception is written; [http-api.md](../core-hub/http-api.md) links here.
- <a id="INV-5"></a>**INV-5** — All corroboration sits behind `CorroborationService`.
  - Scope: the interface, its contract test and the scan are in [corroboration.md](../core-hub/corroboration.md).
- <a id="INV-6"></a>**INV-6** — No credentials, URLs, or ports in source. Credentials live in `.env` only and are read by the service that uses them.
  - Scope: source code, scripts and committed config files. Compose passes values in from `.env` as `${VAR}` ([topology.md](../operations/topology.md)); `.env.example` names each variable with an empty or example value.
  - Amended 2026-10-17 by `## 2026-10-17 — Living docs — CHOICE — invariant 6 wording`: previous text "No credentials, URLs, or ports in source. `.env` only; API keys are Airflow Connections."
- <a id="INV-7"></a>**INV-7** — Python model and Java record stay field-for-field identical; snake_case on the wire; the contract fixture is **generated** by pytest.
  - Scope: every event on a Kafka topic. The signal event and the raw pointer each have a generated fixture; the corroborated event has none yet. The per-event requirements are CON-005 to CON-010 and CON-034.
- <a id="INV-8"></a>**INV-8** — Synchronous Python throughout. No `async`, no `aiokafka`.
  - Scope: concurrency, if ever needed, comes from Airflow task parallelism, never from an async connector contract.
- <a id="INV-9"></a>**INV-9** — UTC everywhere, including derived strings like MinIO keys.
  - Scope: wire timestamps (CON-011), MinIO object keys ([pipeline.md](../ingestion/pipeline.md)), and the Java forked-timezone test task ([verification.md](../engineering/verification.md)).
- <a id="INV-10"></a>**INV-10** — Idempotent writes on each path's **declared** natural key (requirements §3.7) — not one global key.
  - Scope: the declared keys of the Kafka-fed store paths are CON-021 to CON-027. Every other path declares its key in its owner doc.
- <a id="INV-11"></a>**INV-11** — Nothing dies silently: DLT with headers, never blocking a partition.
  - Scope: dead-letter naming, partition and headers are CON-035 to CON-037; which failures dead-letter, retries and pause are in [consumption.md](../core-hub/consumption.md); DLT depth and signal age reporting are in [http-api.md](../core-hub/http-api.md) and [observability.md](../operations/observability.md).
- <a id="INV-12"></a>**INV-12** — Parameterized queries only. Enforced by ArchUnit + behavioural injection tests.
  - Scope: SQL and Cypher in core-hub, the backup service and any script. Labels and relationship types, which Cypher cannot bind, are checked against an identifier pattern before use ([backup.md](../operations/backup.md)).
- <a id="INV-13"></a>**INV-13** — The MinIO archive is unconditional — written before any other side effect.
  - Scope: the stage order is in [pipeline.md](../ingestion/pipeline.md). The raw pointer (CON-006) is the first side effect after the archive write.
- <a id="INV-14"></a>**INV-14** — `event_id` is document identity. It never varies with schema version, prompt, model, or which source saw it.
  - Scope: the formula is CON-018.
- <a id="INV-15"></a>**INV-15** — Test-first, subject to the rule above.
  - Scope: "the rule above" is the stop-and-flag rule kept in the root agent instructions: before writing a test, check it against the approved requirements, and if it can only pass by violating one, stop and record a flag instead of writing it.
  - Exception (pending: `## 2026-10-22 — Living docs — PENDING — system ratification batch`): creating `pyproject.toml`, `pom.xml`, `docker-compose.yml`, directory trees and `.env.example` is scaffolding, not behaviour, and needs no prior test; everything else does. This is the only place the exemption is written; [verification.md](../engineering/verification.md) links here.

## Verification

| ID | Source | Verified by | Status |
|---|---|---|---|
| INV-1 | `CLAUDE.md:55`; requirements §3.1; read-only scope note: `## 2026-10-22 — Living docs — PENDING — system ratification batch` | `services/ingestion-scraper/tests/unit/test_connector_contract.py::test_fetch_since_performs_no_io_beyond_http` covers the connectors only; no test covers the rest of the service or its scripts | `untested` (partial) |
| INV-2 | `CLAUDE.md:56`; requirements §3.2; `## 2026-10-09 — Stack backup — CHOICE — nightly backup to a folder on the Mac`; `## 2026-10-10 — Stack backup — CHOICE — client tools from the server image, memory and restore semantics`; `## 2026-10-17 — Living docs — CHOICE — restore exception to invariant 2` | `services/core-hub/src/test/java/dev/auspex/corehub/arch/ArchRulesTest.java::test_rest_package_has_no_direct_database_imports` covers one package; the exception: `services/backup/tests/unit/test_restore.py::test_restore_refuses_a_target_store_that_is_not_empty`. No test shows that no other process writes the stores | `untested` (partial) |
| INV-3 | `CLAUDE.md:57`; requirements §5 | `services/ingestion-scraper/tests/unit/test_ingestion_dag.py::test_dag_task_posts_the_cursor_to_the_scraper_ingest_endpoint` | `tested` |
| INV-4 | `CLAUDE.md:58`; requirements §6.1; `## 2026-10-07 — Second-wave specs — CHOICE — short interest is a market-data snapshot, not a connector`; `## 2026-10-07 — Edge research scoping — CHOICE — ownership and insider data are snapshots, not connectors`; `## 2026-09-20 — Watchlist backend — CHOICE — core-hub calls ClinicalTrials.gov directly`; placement of that exception: `## 2026-10-22 — Living docs — PENDING — system ratification batch` | `services/ingestion-scraper/tests/unit/test_connector_registry.py::test_no_source_type_equality_branch_in_shared_modules` | `tested` |
| INV-5 | `CLAUDE.md:59`; requirements §4.2 | none directly; the abstract contract test in [corroboration.md](../core-hub/corroboration.md) covers the one implementation | `untested` |
| INV-6 | `CLAUDE.md:60`; requirements §3.3 (first sentence); `## 2026-10-17 — Living docs — CHOICE — invariant 6 wording` | `services/ingestion-scraper/tests/unit/test_repo_scaffolding.py::test_no_credential_has_a_source_default` passes, but defaults remain in source: `services/core-hub/src/main/resources/application.yml` (lines 6-8 and 21-27), `services/core-hub/src/main/java/dev/auspex/corehub/watchlist/WatchlistService.java:46`, `services/ingestion-scraper/scripts/sample_corroborations.py:90` | `divergent` (`## 2026-10-22 — Living docs — FLAG — invariant conflicts found while writing the system docs`) |
| INV-7 | `CLAUDE.md:61`; requirements §3.4 | `services/ingestion-scraper/tests/unit/test_contract_fixture.py::test_contract_fixture_carries_the_current_schema_version`; CI drift step in `.github/workflows/python.yml`. The Java side does not detect a field missing from its record (CON-010), and the corroborated event has no fixture (CON-034) | `untested` (partial; the CON rows carry the detail) |
| INV-8 | `CLAUDE.md:62`; requirements §1, §3.5 | `services/ingestion-scraper/tests/unit/test_connector_contract.py::test_fetch_since_is_not_a_coroutine_and_returns_an_iterator` covers the connectors only | `untested` (partial) |
| INV-9 | `CLAUDE.md:63`; requirements §3.6 | `services/ingestion-scraper/tests/unit/test_connector_contract.py::test_minio_key_converts_offset_timestamp_to_utc_wall_time` and the `timezoneCheck` Gradle task cover parts | `untested` (partial) |
| INV-10 | `CLAUDE.md:64`; requirements §3.7 | per CON-021 to CON-027; CON-027 (entity nodes) has no test here | `untested` (partial) |
| INV-11 | `CLAUDE.md:65`; requirements §3.10, §3.12; `## 2026-10-10 — Strategy runtime — CHOICE — state placement, timing and the pass-through stub` (item 5) | `services/core-hub/src/integrationTest/java/dev/auspex/corehub/KafkaErrorHandlingIT.java::test_poison_message_does_not_block_partition`; the strategy runtime logs, counts and skips an unreadable record with no DLT (`services/strategy/src/auspex_strategy/runtime/streaming.py`) | `divergent` (`## 2026-10-22 — Living docs — FLAG — invariant conflicts found while writing the system docs`) |
| INV-12 | `CLAUDE.md:66`; requirements §3.11 | `services/core-hub/src/test/java/dev/auspex/corehub/arch/ArchRulesTest.java::test_no_query_built_by_string_concatenation_in_service_packages` (not the `persistence`, `watchlist`, `config` or `kafka` packages; no Cypher) and `services/core-hub/src/integrationTest/java/dev/auspex/corehub/SignalRestIT.java::test_injection_payload_is_rejected_or_bound_and_node_count_is_unchanged` | `untested` (partial) |
| INV-13 | `CLAUDE.md:67`; requirements §7 | `services/ingestion-scraper/tests/unit/test_ingestion_pipeline.py::test_pipeline_archives_before_publishing` | `tested` |
| INV-14 | `CLAUDE.md:68`; requirements §10.1 | `services/ingestion-scraper/tests/unit/test_ingestion_pipeline.py::test_event_id_is_stable_across_schema_version_bump` | `tested` |
| INV-15 | `CLAUDE.md:69`; scaffolding exception `CLAUDE.md:138`: `## 2026-10-22 — Living docs — PENDING — system ratification batch` | process rule, no machine check | `untested` |

## Retired requirements

Invariants are never retired; an invariant changes only by an amendment line under it.

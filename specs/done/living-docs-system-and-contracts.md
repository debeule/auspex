# Living docs: system, invariants and contracts

> Archived. Not authoritative: current behaviour is in docs/ (see docs/README.md).

**Status:** done
**Blocked by:** `docs-check-tooling` (checks A–F, K and M, run in the definition of done); the integration branch `feature/living-docs-integration` existing (`## 2026-10-15 — Living docs — PENDING — rollout branch model`); owner answers, appended as `CHOICE` entries, to `## 2026-10-15 — Living docs — PENDING — raw-pointer contract`, `## 2026-10-15 — Living docs — PENDING — restore exception to invariant 2` and `## 2026-10-15 — Living docs — PENDING — invariant 6 wording` (these three set the text written here). Not blocking, default written until answered: `## 2026-10-15 — Living docs — PENDING — can a DECISIONS entry narrow an invariant` (default: no), `## 2026-10-15 — Living docs — PENDING — closed sets on the wire` (default: an unknown value is invalid), `## 2026-10-15 — Living docs — PENDING — defects found while scoping` (default: fix specs after the rollout).
**Branch:** `feature/living-docs-system-and-contracts` (from and PR into `feature/living-docs-integration`, never `develop`)
**Docs impact:** creates `docs/README.md` (the whole file; no other spec edits it), `docs/system/overview.md` (SYS), `docs/system/invariants.md` (INV-1 … INV-15), `docs/system/contracts.md` (CON). Also changes: `DECISIONS.md` (two appended entries); the INV/SYS/CON rows of `specs/living-docs-cutover-matrix.md` (fragment-row `ID` cells, and the `IDs` cells of decisions-table rows classified binding whose fragment rows carry `M-INV-`, `M-SYS-` or `M-CON-`); `docs-check.toml` (removes `"system"` from `[rollout] planned_domains`, that entry only); this spec's own `TODO.md` row; this file moves to `specs/done/`. Does **not** write the `docs/requirements.md` § → ID index; `legacy-docs-retirement` writes it, using the § 3 table in Notes.

---

## Context

Written against `develop` @ `e51f742`. Paths below are at that commit.

**What owns these subjects today, and why that is a problem.**

* **Invariants** exist twice, numbered differently.
  * Root `CLAUDE.md:54-69` numbers them 1–15. 26 active and hold specs cite "Invariant N" in that numbering (`grep -l 'Invariant [0-9]' specs/*.md specs/hold/*.md`).
  * `docs/requirements.md:63-87` (§3) numbers 12 rules differently: §3.3 is CLAUDE 6, §3.4 is 7, §3.5 is 8, §3.6 is 9, §3.7 is 10, §3.11 is 12, §3.12 is part of 11. §3.8 and §3.9 are core-hub rules, not invariants.
  * Two wordings disagree. Invariant 6 says "API keys are Airflow Connections" (`CLAUDE.md:60`), but the source keys are scraper environment variables (`services/ingestion-scraper/tests/unit/test_scraper_connector_env.py::test_scraper_container_receives_every_connector_env_var`). Invariant 7's fixture is `signal_event_v1.json`; requirements §13 (`requirements.md:402`) names `research_signal_event.json`.
  * The invariants are also restated in `services/CLAUDE.md:37-42`, `services/core-hub/CLAUDE.md:29-36` and `services/ingestion-scraper/CLAUDE.md:17-23`. Two of those restatements are stricter than the invariant: "No DB access, ever" (`services/CLAUDE.md:39`) and "No Postgres, no Neo4j" (`services/ingestion-scraper/CLAUDE.md:19`), while `services/ingestion-scraper/scripts/sample_corroborations.py:46-60,86-100` reads both stores (SELECT and MATCH only).
* **Exceptions to invariants** live only in `DECISIONS.md` or nowhere.
  * Restore writes Postgres and Neo4j directly (`services/backup/src/auspex_backup/restore.py:33-70`; compose profile `restore`). The reconciliation is the "Boundary" paragraph of `## 2026-10-09 — Stack backup — CHOICE — nightly backup to a folder on the Mac` and item 4 of `## 2026-10-10 — Stack backup — CHOICE — client tools from the server image, memory and restore semantics`. Invariant 2 has no exception clause.
  * core-hub calls ClinicalTrials.gov directly for the watchlist preview (`services/core-hub/src/main/java/dev/auspex/corehub/watchlist/WatchlistService.java:46`; `## 2026-09-20 — Watchlist backend — CHOICE — core-hub calls ClinicalTrials.gov directly`). No invariant names it.
  * The scaffolding exemption to test-first (`CLAUDE.md:137`: creating `pyproject.toml`, `pom.xml`, `docker-compose.yml`, directory trees and `.env.example` needs no prior test) sits in the documentation section, away from invariant 15.
* **Cross-process contracts** are spread over requirements §2 (`requirements.md:44-59`), §10 (`:308-350`), `services/CLAUDE.md:5-24`, `docker/CLAUDE.md:13-25`, `docker/README.md:107` and code.
  * Machine authorities: `docker/topics.yaml` (names, partitions, retention; read by `kafka-init`), the Pydantic models (`services/ingestion-scraper/src/auspex_ingest/models.py:12-87`), the generated fixture `services/core-hub/src/test/resources/contract/signal_event_v1.json` (written by `services/ingestion-scraper/tests/unit/test_contract_fixture.py::test_generate_contract_fixture`, drift-checked by `.github/workflows/python.yml:84-89`), the Java records (`services/core-hub/src/main/java/dev/auspex/corehub/signal/ResearchSignalEvent.java`, `…/corroboration/CorroboratedSignalEvent.java`), `EventType` (`services/ingestion-scraper/src/auspex_ingest/extractor.py:9-22`), `_CANONICAL_PREFIXES` (`models.py:6`) and `EVENT_SCHEMA_VERSION` (`models.py:9`).
  * **Raw-pointer field mismatch** (item C1 of `## 2026-10-15 — Living docs — PENDING — defects found while scoping`). `KafkaProducerClient.publish_raw` (`services/ingestion-scraper/src/auspex_ingest/messaging/kafka_producer.py:18-29`) sends the `RawDocument` fields, which carry `retrieved_at`, plus `raw_object_key`. `RawAuditService` (`services/core-hub/src/main/java/dev/auspex/corehub/audit/RawAuditService.java:47`) reads `ingested_at`, which is absent, so every real raw pointer would fail and dead-letter. `RawAuditIT::test_raw_listener_writes_audit_row_only` passes only because it publishes the hand-written `TestFixtures.validRawJson()` (`services/core-hub/src/integrationTest/java/dev/auspex/corehub/TestFixtures.java`). Separately, `pipeline.py:159` publishes the pointer only alongside a published signal, while requirements §2 and §3.7 expect an audit row per archived document.
  * **Corroborated-event gaps** (item C8 of the same entry). `CorroboratedSignalEvent` has no `schema_version`, no generated fixture and no shared model. `services/strategy/src/auspex_strategy/runtime/events.py:9-31` mirrors it by hand. A send can be acknowledged and the scan's commit then fail, so a corroboration can be published twice.
  * **DLT partition text is wrong in two places.** `services/CLAUDE.md:24` and `docker/README.md:107` describe Spring's same-partition default; the resolver returns partition `-1` (`services/core-hub/src/main/java/dev/auspex/corehub/config/KafkaConfig.java:187-188`), as `## 2026-08-16 — Step 1.3 — VERIFIED — DeadLetterPublishingRecoverer with Spring Kafka 4.1` records.
  * **Closed sets are not typed on the wire** (item C7 of the same entry). `source_type`, `directionality` and `event_type` are `str` in Python and `String` in Java. `KafkaErrorHandlingIT::test_unknown_enum_value_goes_to_dlt` actually sends an unknown major `schema_version`. `directionality` values exist only in `services/ingestion-scraper/prompts/extraction/v1.txt:29`.
  * **Symmetry is half-tested.** The Java test deserializes the generated fixture, but with unknown properties ignored, a field the Python model has and the Java record lacks passes silently.
* **System facts** (naming table, no legacy system) are in root `CLAUDE.md:18-33,46-47` only. `docs/` has no index.

**What a cold session needs.** This spec and the repo. Every source is a repo path cited here, and the rollout rules this spec depends on (template, ID scheme, provenance, conflict policy) are restated under Constraints. The rollout design is in `specs/living-docs-cutover-design.md`.

## What this builds

Four files on the integration branch. When this merges, the domain specs (`living-docs-ingestion`, `living-docs-core-hub`, `living-docs-research`, `living-docs-strategy-and-dashboard`, `living-docs-operations`, `living-docs-engineering-workflow`) cite real `INV-` and `CON-` IDs instead of question-mark placeholders.

### 1. `docs/README.md` (non-normative index; listed as non-normative in `docs-check.toml`)

This spec writes the whole file in its final form. No other spec edits it. Links to the owner docs of domains still listed in `[rollout] planned_domains` are reported by the checker as notices, not findings, until each domain merges; at the final gate the list is empty and every link must resolve.

* **Layers.** `docs/` is approved current behaviour; `specs/*.md` and `specs/hold/*.md` are proposed changes and govern only their own work until merged; `specs/done/`, `docs/HISTORY.md` and history-class `DECISIONS.md` entries are archive, never a source of a current rule.
* **Tree.** The complete `docs/` tree with one line per file:
  * `docs/README.md` (this index);
  * `docs/system/overview.md` (SYS), `docs/system/invariants.md` (INV), `docs/system/contracts.md` (CON);
  * `docs/ingestion/connectors.md`, `docs/ingestion/pipeline.md` (ING), `docs/ingestion/extraction.md` (EXT);
  * `docs/core-hub/consumption.md`, `docs/core-hub/storage.md`, `docs/core-hub/http-api.md` (HUB), `docs/core-hub/corroboration.md` (COR);
  * `docs/research/market-data.md`, `docs/research/universe.md`, `docs/research/panels.md`, `docs/research/simulation.md`, `docs/research/backtesting.md` (RES), `docs/research/evaluation-protocol.md` (EVA);
  * `docs/strategy/contract.md`, `docs/strategy/runtime.md`, `docs/strategy/risk.md`, `docs/strategy/decision-trace.md` (STR);
  * `docs/dashboard.md` (DSH);
  * `docs/operations/topology.md`, `docs/operations/orchestration.md`, `docs/operations/observability.md`, `docs/operations/backup.md` (OPS);
  * `docs/engineering/change-workflow.md`, `docs/engineering/conventions.md`, `docs/engineering/verification.md` (ENG);
  * the non-normative files below.

  Each line is a relative link.
* **ID namespace table.** The 13 fixed namespaces (`INV SYS CON ING EXT HUB COR RES EVA STR DSH OPS ENG`), each with its domain, its owner files (linked) and its ID form (`INV-N`, else `NS-NNN`). Adding a namespace changes `docs-check.toml` and this file in one PR. A requirement keeps its ID when it moves file.
* **Authority map.** Every machine-readable authority, the values it governs, its lock, and the namespace whose doc explains it. The rows: hypothesis files and `registry.jsonl`; universe rules files; model registry and gate records; strategy registry and themes; FINRA calendar; `sources.yaml`; `docker/topics.yaml`; the generated signal fixture; Flyway migrations; compose and `.env.example`; Grafana alerting, Prometheus, ILM and statsd mapping files; `VERSIONS.md` and the lock files; CI workflows and `check_commit_identity.sh`. Docs explain these files and never copy their values.
* **Precedence pointer.** One sentence linking the conflict policy in `docs/engineering/change-workflow.md`. Invariant exceptions live only under their invariant (`docs/system/invariants.md`).
* **Verification status legend:** `tested`, `enforced`, `untested`, `divergent` (must cite a `DECISIONS.md` heading), `pending-decision` (must cite a `PENDING` heading), with the meaning of each and which are allowed at cutover.
* **Evidence label legend** for reviews, audits and `DECISIONS.md` `VERIFIED` entries: `APPROVED-INTENT`, `OBSERVED-IMPL`, `TEST-ASSERTION`, `EXECUTED`, `HISTORICAL`, `PROPOSED`, `UNVERIFIED`, plus `VERIFIED-DOCS` (read in vendor documentation on a stated date) and `VERIFIED-SOURCE` (read in vendor source at a stated tag). Neither of the last two is execution.
* **Non-normative and legacy files and their roles** (this spec owns this section too): `docs/requirements.md` (legacy § → ID index, non-normative), `docs/strategy-research.md` (rationale), `docs/local-model-runbook.md` and `docs/backup-restore.md` (runbooks), `docs/PREREQUISITES.md` (user-action queue), `docs/HISTORY.md` (archive). The `docs/requirements.md` description is the post-rollout one; nothing reaches `develop` before `legacy-docs-retirement` makes it true.
* No requirement text and no requirement IDs defined here.

### 2. `docs/system/overview.md` (SYS)

In this spec, `system ratification batch` in a Source cell is shorthand: the doc's verification `Source` cell carries the full citation `` `## <date> — Living docs — PENDING — system ratification batch` `` with the date the entry is appended, as check K requires for `pending-decision` rows.

Required H2s (Scope, Requirements, Verification, Retired requirements), plus optional `Component map`, `Glossary`, `Rationale`.

* **Component map** (descriptive, non-normative): ingestion-scraper, core-hub, price-service (`services/backtesting`), strategy-runtime (`services/strategy`), backup and restore (`services/backup`), dashboard, Airflow, and the stores (MinIO, Kafka, Postgres, Neo4j), with the data flow sources → scraper → MinIO + Kafka → core-hub → Postgres + Neo4j → corroborated topic → strategy runtime, and the dashboard's server layer in front of core-hub. Each arrow links to its owner (CON, HUB, OPS, STR, DSH), never restating it.
* **Naming table**: one row per identifier kind (compose project, Kafka topics, Java root package, Python import packages, MinIO buckets, Postgres databases, roles), with its **authority** (`.env.example` `COMPOSE_PROJECT_NAME`, `docker/topics.yaml`, `services/core-hub/src/main/java/dev/auspex/corehub/`, each `pyproject.toml` and `src/` package directory, `.env.example` `MINIO_BUCKET` and compose `minio-init`/`BACKUP_BUCKETS`, `.env.example` `POSTGRES_DB`/`POSTGRES_USER` and `docker/postgres-init/`) and what each holds. Topic and bucket names are not restated; the authority is linked. The three buckets' roles come from `CLAUDE.md:27` and `## 2026-10-10 — Strategy runtime — CHOICE — state placement, timing and the pass-through stub` item 1.
* **Requirements** (planned order; numbers are assigned in this order with `python3 -m tools.docs_check --next SYS`, created by `docs-check-tooling`):
  1. The project is named Auspex; components keep descriptive names (`ingestion-scraper`, `core-hub`), never themed. *Source:* `system ratification batch` (`CLAUDE.md:31`).
  2. The identifiers in the naming table are fixed. Renaming one changes its authority file and this table in the same PR. *Source:* `system ratification batch` (`CLAUDE.md:18-29`).
  3. There is no legacy system: no prior schema, data or release behaviour to preserve. Flyway migrations are the scripts that create the schema on an empty database. *Source:* `system ratification batch` (`CLAUDE.md:46-47`).
  4. Auspex is a single-user installation: one researcher, no per-user data and no per-user authorization. The schema consequence (no `user_id`) is HUB's; the login is DSH's. *Source:* `## 2026-09-20 — Watchlist backend — CHOICE — No user_id column; single-user installation, extensible`; `## 2026-10-08 — Control-surface scoping — CHOICE — dashboard runs in the stack behind its own server layer`.
* **Not in this file** (link only): what logs may carry (requirements §3.3, second sentence: no credentials, no full `raw_content`) is the log contract in `docs/operations/observability.md`; the no-plan-step-names rule is in `docs/engineering/conventions.md`.
* **Rationale**: requirements §14 "Settled — do not relitigate", item by item, each linked to the owner that now states it (sync-only → INV-8; Airflow + Kafka → OPS; separate Airflow DB → OPS; first-class `SignalNode` → HUB; `confidence_score` 0.0–1.0 → CON; UTC → INV-9; Testcontainers at the store boundary → ENG; free-tier-first → this file's rationale only; TDD → INV-15).
* **Glossary**: corroboration, entity key, participant set, raw pointer, signal, DLT, as-of, known-at delay, natural key. Definitions only; each links to the owner requirement.

### 3. `docs/system/invariants.md` (INV)

* **Numbering**: `INV-1 … INV-15` in root `CLAUDE.md:55-69` order. The text of each is the `CLAUDE.md` text verbatim, except where an approved amendment changes it. This spec writes no further invariant. A sixteenth (processing time never decides an as-of read; `## 2026-10-15 — Living docs — PENDING — processing time in as-of decisions`) is written only if the owner's `CHOICE` adopts it, and then by the cutover's decision application in `docs/system/invariants.md`; until then the STR and RES requirements carry the rule.
* **Form of each item**:
  ```markdown
  - <a id="INV-6"></a>**INV-6** — <current text>
    - Scope: <what it covers and does not>; owners that implement it: <IDs>.
    - Exception (approved by `## <date> — … — CHOICE — …`): <the whole exception text; nowhere else>.
    - Amended YYYY-MM-DD by `## <date> — … — CHOICE — …`: previous text "<exact previous text>".
  ```
  Scope lines may clarify; they never narrow. Only an exception line narrows, and only with a cited `CHOICE` (default of `## 2026-10-15 — Living docs — PENDING — can a DECISIONS entry narrow an invariant`). An exception whose only source is a `CLAUDE.md` line is written as `Exception (pending: system ratification batch)` citing the batch `PENDING` heading, and flipped to the `CHOICE` when the owner approves the batch.
* **Content per invariant** (Scope and exception lines this spec writes):

| INV | Text | Scope / exception / amendment lines |
|---|---|---|
| 1 | `CLAUDE.md:55` verbatim | Scope: covers the service's code and its scripts. Writing Airflow Variables or local state files is a write outside MinIO and Kafka (requirements §3.1; cursor state belongs to the orchestrator). **Read-only scope note:** reading Postgres or Neo4j, as `scripts/sample_corroborations.py` does, is within INV-1, which restricts writes. This replaces the stricter wording of `services/CLAUDE.md:39` and `services/ingestion-scraper/CLAUDE.md:19` and is listed in the ratification batch. |
| 2 | `CLAUDE.md:56` verbatim | Scope: the application database (`auspex`) and Neo4j; the `airflow` database belongs to Airflow. The backup service only reads. **Exception** (default option of `## 2026-10-15 — Living docs — PENDING — restore exception to invariant 2`): the `restore` one-shot (compose profile `restore`, `auspex_backup.restore`) writes both Postgres databases, Neo4j and MinIO, only into stores that hold no data (no table outside the system schemas, no Neo4j node, no object in any backed-up bucket), checked before anything is written, with the `app` profile stopped; it refuses otherwise. It cites the two Stack backup `CHOICE` headings above plus the `CHOICE` that answers that `PENDING` entry. Procedure links to `docs/backup-restore.md`; OPS links here. |
| 3 | `CLAUDE.md:57` verbatim | Scope: the ingestion DAG. Other DAGs follow the same pattern (call a service HTTP API, no logic); that policy is OPS's. |
| 4 | `CLAUDE.md:58` verbatim | Scope note: market and reference snapshots (short interest, SEC ownership, catalyst panel, filing text) are not sources under INV-4 (`## 2026-10-07 — Second-wave specs — CHOICE — short interest is a market-data snapshot, not a connector`; `## 2026-10-07 — Edge research scoping — CHOICE — ownership and insider data are snapshots, not connectors`). **Exception:** core-hub's watchlist preview calls the ClinicalTrials.gov API directly for one interactive lookup; nothing it returns is archived, published or stored as a signal (`## 2026-09-20 — Watchlist backend — CHOICE — core-hub calls ClinicalTrials.gov directly`). This is the only place the exception is written; HUB's http-api doc links here. Placement under INV-4 is listed in the ratification batch. |
| 5 | `CLAUDE.md:59` verbatim | Scope: links COR. |
| 6 | Default option of `## 2026-10-15 — Living docs — PENDING — invariant 6 wording`: "No credentials, URLs, or ports in source. Credentials live in `.env` only and are read by the service that uses them." | Amended line quoting `CLAUDE.md:60` exactly: "No credentials, URLs, or ports in source. `.env` only; API keys are Airflow Connections." Scope: links OPS (compose `${VAR}` rule). |
| 7 | `CLAUDE.md:61` verbatim | Scope: today the signal event; the raw pointer and corroborated event are CON requirements with status `divergent`. |
| 8 | `CLAUDE.md:62` verbatim | Scope: concurrency, if needed, comes from Airflow task parallelism (requirements §3.5). |
| 9 | `CLAUDE.md:63` verbatim | Scope: wire timestamps (CON), MinIO keys (ING), Java `timezoneCheck` (ENG). |
| 10 | `CLAUDE.md:64` verbatim (its "(requirements §3.7)" keeps resolving through the legacy index) | Scope: the declared keys for Kafka-fed store paths are the CON natural-key requirements; other domains declare the keys of their own paths in their owner doc. |
| 11 | `CLAUDE.md:65` verbatim | Scope: DLT naming and headers (CON); which failures dead-letter, retries and pause (HUB consumption); DLT depth and signal age reporting (HUB, OPS). |
| 12 | `CLAUDE.md:66` verbatim | Scope: SQL and Cypher in core-hub, the backup service and any script. Labels and relationship types, which Cypher cannot bind, are checked against an identifier pattern before use (link OPS backup). |
| 13 | `CLAUDE.md:67` verbatim | Scope: links ING pipeline order. |
| 14 | `CLAUDE.md:68` verbatim | Scope: formula in CON. |
| 15 | `CLAUDE.md:69` verbatim | Scope: "the rule above" is the stop-and-flag rule kept in the root agent instructions (plain text, no path, so check B does not fail before `agent-instruction-hierarchy` lands). **Exception (pending: system ratification batch):** creating `pyproject.toml`, `pom.xml`, `docker-compose.yml`, directory trees and `.env.example` is scaffolding, not behaviour, and needs no prior test; everything else does (`CLAUDE.md:137`). This is the only place the exemption is written; ENG links here. |

* **Verification** (one row per INV; recommended statuses, which the implementer confirms by reading each named test). The `Source` cell names every source the item carries: the `CLAUDE.md` line, the requirements §, and the full text of each binding decision heading behind a scope, exception or amendment line. Check M `--decisions` reads this cell.

| INV | Source | Verified by | Status |
|---|---|---|---|
| 1 | `CLAUDE.md:55`; requirements §3.1; read-only scope note: `system ratification batch` | `services/ingestion-scraper/tests/unit/test_connector_contract.py::test_fetch_since_performs_no_io_beyond_http` covers connectors only | `untested` (partial, named) |
| 2 | `CLAUDE.md:56`; requirements §3.2; `## 2026-10-09 — Stack backup — CHOICE — nightly backup to a folder on the Mac`; `## 2026-10-10 — Stack backup — CHOICE — client tools from the server image, memory and restore semantics`; `## 2026-10-15 — Living docs — PENDING — restore exception to invariant 2` (the owner's `CHOICE` replaces it at the flip) | `services/core-hub/src/test/java/dev/auspex/corehub/arch/ArchRulesTest.java::test_rest_package_has_no_direct_database_imports` is partial; exception: `services/backup/tests/unit/test_restore.py::test_restore_refuses_a_target_store_that_is_not_empty` | `untested` (partial) |
| 3 | `CLAUDE.md:57`; requirements §5 | `services/ingestion-scraper/tests/unit/test_ingestion_dag.py::test_dag_task_posts_the_cursor_to_the_scraper_ingest_endpoint` | `tested` |
| 4 | `CLAUDE.md:58`; requirements §6.1; `## 2026-10-07 — Second-wave specs — CHOICE — short interest is a market-data snapshot, not a connector`; `## 2026-10-07 — Edge research scoping — CHOICE — ownership and insider data are snapshots, not connectors`; `## 2026-09-20 — Watchlist backend — CHOICE — core-hub calls ClinicalTrials.gov directly` | `services/ingestion-scraper/tests/unit/test_connector_registry.py::test_no_source_type_equality_branch_in_shared_modules` | `tested` |
| 5 | `CLAUDE.md:59`; requirements §4.2 | none directly; COR's abstract contract test covers the one implementation | `untested` |
| 6 | `CLAUDE.md:60`; requirements §3.3 (first sentence); `## 2026-10-15 — Living docs — PENDING — invariant 6 wording` (the owner's `CHOICE` replaces it at the flip) | `services/ingestion-scraper/tests/unit/test_repo_scaffolding.py::test_no_credential_has_a_source_default`; defaults remain at `services/core-hub/src/main/resources/application.yml:6-8,21-27`, `WatchlistService.java:46`, `sample_corroborations.py:90` | `divergent`, citing `## <date> — Living docs — FLAG — invariant conflicts found while writing the system docs` |
| 7 | `CLAUDE.md:61`; requirements §3.4 | `services/ingestion-scraper/tests/unit/test_contract_fixture.py::test_contract_fixture_carries_the_current_schema_version`; CI drift step `python.yml:84-89`; the Java side does not detect a field missing from the record | `untested` (partial; CON rows carry the detail) |
| 8 | `CLAUDE.md:62`; requirements §1, §3.5 | `services/ingestion-scraper/tests/unit/test_connector_contract.py::test_fetch_since_is_not_a_coroutine_and_returns_an_iterator` (connectors only) | `untested` (partial) |
| 9 | `CLAUDE.md:63`; requirements §3.6 | `services/ingestion-scraper/tests/unit/test_connector_contract.py::test_minio_key_converts_offset_timestamp_to_utc_wall_time` and `timezoneCheck` (partial) | `untested` (partial) |
| 10 | `CLAUDE.md:64`; requirements §3.7 | per CON natural-key rows | `tested` if every CON natural-key row is `tested`, else `untested` |
| 11 | `CLAUDE.md:65`; requirements §3.10, §3.12; `## 2026-10-10 — Strategy runtime — CHOICE — state placement, timing and the pass-through stub` (item 5, the conflict) | `services/core-hub/src/integrationTest/java/dev/auspex/corehub/KafkaErrorHandlingIT.java::test_poison_message_does_not_block_partition`; the strategy runtime skips unreadable records without a DLT (item 5 of that `CHOICE`) | `divergent`, citing `## <date> — Living docs — FLAG — invariant conflicts found while writing the system docs` |
| 12 | `CLAUDE.md:66`; requirements §3.11 | `ArchRulesTest.java::test_no_query_built_by_string_concatenation_in_service_packages` (not `persistence`, `watchlist`, `config`, `kafka`; no Cypher) and `SignalRestIT.java::test_injection_payload_is_rejected_or_bound_and_node_count_is_unchanged` | `untested` (partial) |
| 13 | `CLAUDE.md:67`; requirements §7 | `services/ingestion-scraper/tests/unit/test_ingestion_pipeline.py::test_pipeline_archives_before_publishing` | `tested` |
| 14 | `CLAUDE.md:68`; requirements §10.1 | `test_ingestion_pipeline.py::test_event_id_is_stable_across_schema_version_bump` | `tested` |
| 15 | `CLAUDE.md:69`; scaffolding exception `CLAUDE.md:137` (`system ratification batch`) | process rule, no machine check | `untested` |

  **Citations in verification cells** are always in backticks (check K); `<date>` is replaced by the append date when the entry is written. **Rule for partial coverage:** `tested` only when the named test asserts the requirement as written. Otherwise `untested`, with the partial tests named in the row. This keeps check K honest.

### 4. `docs/system/contracts.md` (CON)

Scope: everything that crosses a process boundary on Kafka, including dead-letter topic naming, partitioning and headers. Values live in `docker/topics.yaml` and the models. Which failures a consumer dead-letters, and its retries, are HUB's (`docs/core-hub/consumption.md`); write behaviour after consumption is HUB's too. Planned requirement order (numbers assigned in this order):

| # | Requirement (summary of the text to write) | Source (priority order under Constraints) | Recommended status |
|---|---|---|---|
| 1 | Topics are provisioned only from `docker/topics.yaml` by the `kafka-init` one-shot, never as a side effect of a producer or consumer. | requirements §1 Infrastructure | `untested` |
| 2 | Topic roles: `auspex.raw.ingested` carries raw-document pointers (scraper → core-hub audit); `auspex.signals.extracted` carries `ResearchSignalEvent` (scraper → core-hub); `auspex.signals.corroborated` carries `CorroboratedSignalEvent` (core-hub → strategy runtime); each has a `<topic>.dlt`. Partitions and retention are in `topics.yaml`. | requirements §2; `## 2026-09-20 — Strategy layer session 2 — CHOICE — Event-driven Kafka consumer for the strategy runtime` | `untested` |
| 3 | Keys are identity: raw pointer → `external_id`; signal → `event_id`; corroborated → `entity_key`. Never a gene target. | requirements §2 | `untested` (raw and signal keys are tested by `test_ingestion_pipeline.py::test_raw_topic_keyed_by_external_id` and `::test_signals_topic_keyed_by_event_id`; the corroborated key is not) |
| 4 | Every source topic has a `.dlt` topic with the same partition count, as defence in depth (the publish does not depend on it). | requirements §2; `topics.yaml:4-5` | `untested` (`test_infra_containers.py::test_dlt_partition_count_matches_source_topic` is excluded from CI) |
| 5 | A raw pointer is the `RawDocument` fields in snake_case without `raw_content`, plus `raw_object_key`, keyed by `external_id`, with a `schema_version` header; its time field is `retrieved_at`, and producer and consumer read the same names. | requirements §2; `## 2026-10-15 — Living docs — PENDING — raw-pointer contract` | **`divergent`**: `RawAuditService.java:47` reads `ingested_at`; cites `## 2026-10-15 — Living docs — PENDING — raw-pointer contract` |
| 6 | A raw pointer is published for every archived document, whether or not it yields a signal. (If the owner chooses option b of the raw-pointer contract: only alongside a published signal, status `tested`.) | requirements §2, §3.7; `## 2026-10-15 — Living docs — PENDING — raw-pointer contract` | **`divergent`**: `pipeline.py:159`; cites `## 2026-10-15 — Living docs — PENDING — raw-pointer contract` |
| 7 | The raw pointer has a fixture generated from the Pydantic model, which the core-hub tests deserialize. | INV-7; `## 2026-10-15 — Living docs — PENDING — raw-pointer contract` | **`divergent`**: no raw fixture; `RawAuditIT` uses `TestFixtures.validRawJson()`; cite `## 2026-10-15 — Living docs — PENDING — defects found while scoping` (item C1) |
| 8 | `ResearchSignalEvent`'s fields are those of the Pydantic model (`models.py:45`), in snake_case, and the Java record matches them field for field. `external_id` and `raw_object_key` are on every event (chain of custody). List fields are lists; only `canonical_id` and `primary_company` may be null. | INV-7; requirements §10.2; `## 2026-10-10 — Single-source cleanup — CHOICE — one version of each pre-rollout artifact` | `tested`: `ResearchSignalEventTest.java::test_signal_event_json_contract_matches_generated_python_fixture`, `::test_event_without_company_level_fields_is_rejected` |
| 9 | The fixture `signal_event_v1.json` is generated by `test_contract_fixture.py`; CI fails when the committed file differs. | INV-7; requirements §13 (filename corrected; Rationale says so) | `enforced`: `python.yml:84-89` |
| 10 | A field present on one side and missing on the other fails a test on that side. | INV-7 | **`divergent`**: Java ignores a field it lacks; cites `## <date> — Living docs — FLAG — invariant conflicts found while writing the system docs` |
| 11 | Every timestamp on the wire is ISO-8601 UTC with `Z`; a naive timestamp is invalid on the wire. | INV-9 | `tested`: `test_ingestion_pipeline.py::test_timestamps_serialize_as_utc_z` (producer half; the consumer's rejection is HUB's) |
| 12 | `confidence_score` is required and is a number in [0.0, 1.0] inclusive; the producer never clamps or rescales it. Java holds it as a non-null bounded `BigDecimal`. Rejection of a missing or out-of-range value is HUB's (`docs/core-hub/consumption.md`). | requirements §10.3 | `untested` (validated by a direct `Validator` only; listener validation is item C6 of the defects entry, HUB's) |
| 13 | `event_type` values are the `EventType` literal (`extractor.py:9-22`); the producer records an unknown model label as `other`. | requirements §10.2; `## 2026-10-07 — Company-level extraction — CHOICE — event taxonomy and identifier fields (schema 1.1)` item 3 | `tested`: `test_company_level_extraction.py::test_unknown_event_type_from_model_is_recorded_as_other` |
| 14 | `source_type` values are the entries of `sources.yaml`. | requirements §10.2; INV-4 | `untested` |
| 15 | `directionality` is one of `positive`, `negative`, `neutral`. | `system ratification batch` (values only in `prompts/extraction/v1.txt:29`) | `pending-decision` |
| 16 | Each `trial_ids` entry is `NCT` + 8 digits. | requirements §10.2 | `tested`: `test_company_level_extraction.py::test_malformed_trial_ids_are_dropped_and_valid_ones_upper_cased` |
| 17 | Closed-set fields (`source_type`, `directionality`, `event_type`) carry only values from their set; a value outside it is invalid on the wire. Which invalid records dead-letter is HUB's (`docs/core-hub/consumption.md`). | requirements §10.2; `## 2026-10-15 — Living docs — PENDING — closed sets on the wire` | `untested`: both sides carry them as plain strings and no test asserts the set on the wire. The consumer's reaction to an invalid value, and the one `divergent` row for item C7, are HUB's (`docs/core-hub/consumption.md`) |
| 18 | `event_id = uuid5(NAMESPACE_URL, canonical_id)` when `canonical_id` is set, else `uuid5(NAMESPACE_URL, "<source_type>:<external_id>")`. | requirements §10.1; INV-14 | `tested`: `test_ingestion_pipeline.py::test_same_canonical_id_from_two_source_types_yields_one_event_id`, `::test_event_id_falls_back_to_source_and_external_id_when_no_canonical_id` (name both in the row) |
| 19 | `extraction_id = uuid5(NAMESPACE_URL, "<event_id>:<schema_version>:<prompt_version>:<prefilter_version>:<extraction_model>")`. | requirements §10.1 | `tested`: `services/ingestion-scraper/tests/unit/test_reextract.py::test_extraction_id_changes_on_prompt_version_change` |
| 20 | `canonical_id` carries a type prefix from `_CANONICAL_PREFIXES`; a connector that can supply one supplies it for every document. | requirements §10.1 | `tested`: `test_connector_contract.py::test_canonical_id_is_typed_or_absent_rejects_bare` |
| 21–27 | One requirement per declared natural key, Kafka-fed paths: `raw_fetch_audit` (MinIO object key, do nothing), `signal_current` (`event_id`, update), `signal_extraction_history` (`(event_id, extraction_id)`, do nothing), `source_observation` (`(event_id, source_type, external_id)`, do nothing), `corroboration` (`(entity_key, participants_hash)`, do nothing with supersession), `(:Signal)` (`event_id`, MERGE), entity nodes (natural key per the HUB graph model, MERGE). | requirements §3.7; INV-10 | `tested` per row: `SignalPersistenceIT.java::test_duplicate_delivery_creates_one_audit_row`, `::test_redelivery_with_new_extraction_upserts_current_and_appends_history`, `::test_second_source_observation_appends_and_does_not_change_signal_source_type`, `::test_duplicate_delivery_creates_one_signal_node`, `CorroborationServiceContractTest.java::test_fourth_signal_supersedes_rather_than_duplicating`; entity nodes: HUB's test |
| 28 | `schema_version` is `major.minor`, compared as integers; the current value is `EVENT_SCHEMA_VERSION`. A record with an unknown major is incompatible; how a consumer reacts is HUB's (`docs/core-hub/consumption.md`). | requirements §10.4 | `tested`: `ResearchSignalEventTest.java::test_schema_version_compares_as_major_minor_integers_not_strings` |
| 29 | A known major with another minor is compatible: the consumer accepts it, logs it and ignores unknown properties. | requirements §10.4 | `tested`: `ResearchSignalEventTest.java::test_minor_version_bump_with_extra_field_is_accepted` ("logged" untested; say so) |
| 30 | `schema_version` travels as a UTF-8 header and as a field; consumers read the field. | requirements §10.4; `system ratification batch` (field-read half) | `tested`: `test_ingestion_pipeline.py::test_schema_version_header_present_on_both_topics` |
| 31 | A schema bump changes the Pydantic model, the Java record and the regenerated fixture in one PR. | requirements §10.4 | `untested` |
| 32 | `CorroboratedSignalEvent` is snake_case JSON with ISO-8601 timestamps and no type header, fields as the Java record, published only for corroborations that are not superseded. | requirements §2, §4.1 | `tested`: `services/core-hub/src/test/java/dev/auspex/corehub/config/CorroboratedWireFormatTest.java::test_corroborated_event_is_snake_case_json_with_iso_timestamps_and_no_type_header` |
| 33 | A corroborated event is delivered at least once; consumers treat `(entity_key, participants_hash)` as its identity. | `system ratification batch` (code: send before commit); `## 2026-09-20 — Strategy layer session 2 — FLAG — Corroboration surrogate key deferred; composite natural key in trace` | `pending-decision` |
| 34 | The corroborated event carries `schema_version` and has a generated fixture that the Python consumer's tests read. | INV-7; requirements §10.4 | **`divergent`**; cite `## 2026-10-15 — Living docs — PENDING — defects found while scoping` (item C8) |
| 35 | A dead letter goes to `<source topic>.dlt` (lowercase). | requirements §2 | `tested`: `KafkaErrorHandlingIT.java::test_dlt_publish_succeeds_with_custom_lowercase_resolver` |
| 36 | The dead-letter publish uses partition `-1` (the producer chooses). | requirements §2 | `untested` (embedded Kafka has one partition, so no test can tell `-1` from the same partition) |
| 37 | A dead letter keeps the original key and carries `kafka_dlt-exception-message` and `kafka_dlt-original-topic`; its value is the original bytes when deserialization failed, else snake_case JSON. | requirements §2, §3.10; `system ratification batch` (value form and header names: `## 2026-08-16 — Step 1.3 — VERIFIED — DeadLetterPublishingRecoverer with Spring Kafka 4.1`) | `tested`: `KafkaErrorHandlingIT.java::test_dlt_headers_present` (value form untested; say so) |

* **Known traps** in this file: the `DeadLetterPublishingRecoverer` default (`.DLT`, same partition) and why the resolver returns `-1` (the two DLT requirements above; the "re-verify" caveat is dropped, citing the 2026-08-16 `VERIFIED` entry); a primitive `double` turns a missing `confidence_score` into `0.0` (the `confidence_score` requirement); `FAIL_ON_UNKNOWN_PROPERTIES` must be `false` or the first additive change dead-letters everything (the minor-version compatibility requirement).
* **Rationale**: requirements §2 partitioning note (keys are identity, not gene targets); §10.1 near-miss formulas; §10.2 chain of custody; the fixture-name drift (`research_signal_event.json` vs `signal_event_v1.json`); `services/CLAUDE.md:24` and `docker/README.md:107` were wrong about the partition; `auspex.signals.corroborated.dlt` is provisioned but nothing publishes to it (the strategy runtime skips and counts).
* **Not in this file** (link only): which records dead-letter (missing or out-of-range `confidence_score`, an invalid closed-set value, an unknown major version, a naive timestamp), retry counts, `ErrorHandlingDeserializer`, pause and replay (HUB consumption); `signal_current.source_type` set from the first observation, Postgres/Neo4j types of `confidence_score` (HUB storage); re-extraction (EXT); log content (OPS observability).

### 5. `DECISIONS.md` entries appended by this spec

1. `## <date> — Living docs — PENDING — system ratification batch`: the list of every requirement, scope line and exception written with Source `system ratification batch` (status `pending-decision`, or the pending exception lines under INV-1, INV-4 and INV-15), each with its code or file citation.
2. `## <date> — Living docs — FLAG — invariant conflicts found while writing the system docs`: INV-6 defaults in source (`application.yml:6-8,21-27`, `WatchlistService.java:46`, `sample_corroborations.py:90`); INV-11 vs the strategy runtime's skip-and-count with no DLT; the Java consumer ignoring a field the Python model has (CON symmetry). For each: fix spec, or an exception under the invariant with the owner's word.

The owner approves the batch by appending `## <date> — Living docs — CHOICE — system ratification batch`; once it exists, the cutover's decision-application step flips the batch's rows from `pending-decision` to their real status (and the pending exception lines to cite the `CHOICE`). This spec does not do the flip.

## Out of scope

* Any code, test or CI change. Items C1, C7 and C8 of `## 2026-10-15 — Living docs — PENDING — defects found while scoping`, the Java unknown-field gap and the INV-6 defaults are recorded, not fixed.
* An invariant 16 (see Numbering above).
* The `docs/requirements.md` § → ID index and its banner (`legacy-docs-retirement`).
* `AGENTS.md`/`CLAUDE.md` edits (`agent-instruction-hierarchy`). This spec only adds the plain-text reference in INV-15's scope line.
* Editing READMEs or nested `CLAUDE.md` files to remove the restated invariants and topic tables (`legacy-docs-retirement` and `agent-instruction-hierarchy`).
* HUB, ING, EXT, COR, RES, EVA, STR, DSH, OPS, ENG content. This spec links to their owner docs; the links are notices until each domain merges.
* Active and hold specs: none is assigned to this spec. Specs citing "Invariant N" keep resolving through check D's alias; specs citing "§3.N" are repointed by their domain spec using the table in Notes.

## Constraints

* **No application code changes.** Docs are not evidence that code complies; every status cites code or a test by `path::name`.
* **Conversion provenance (initial rollout).** Every requirement carries a `Source`, in priority order: today's `docs/requirements.md` § when still true; a `DECISIONS.md` `CHOICE` heading; an archived spec; an invariant; an owner ratification. When the only source is code, a README, a `CLAUDE.md` section other than the invariants, a trap or a config comment, write Source `system ratification batch`, status `pending-decision`, citing the `PENDING` batch heading. A source that contradicts the code is written as the approved version with status `divergent` and a DECISIONS heading; never silently follow the code.
* **Conflict policy.** Locked machine authorities win, then other machine authorities for values, then `docs/`. A disagreement between `docs/` and code is recorded (`divergent` + `FLAG`) and decided by the owner. An unabsorbed DECISIONS entry never outranks `docs/`; a DECISIONS entry cannot narrow an invariant except through an exception line under it. Agent files and READMEs never win on requirements.
* **IDs.** INV uses `CLAUDE.md` numbering and is the only namespace amended in place (amendment line, exceptions under the item; a new invariant takes the next number). SYS and CON are `NS-NNN` (three digits), numbered in file order with `python3 -m tools.docs_check --next <NS>` (created by `docs-check-tooling`). Spec prose never writes a planned CON or SYS number; numbers exist only once allocated. Definition: a list item starting `<a id="NS-NNN"></a>**NS-NNN**`; each defined once across `docs/`. Retirement (SYS, CON): move to `## Retired requirements` with date, retiring heading, replacement or `none`, original text. Decision references are `DECISIONS.md` headings; a decision-register number never appears in `docs/` or in this spec.
* **One owner per subject.** DLT naming, partitioning and headers are CON's; failure classification is HUB's; log content is OPS's; the no-plan-step-names rule is ENG's; the restore exception is written only under INV-2, the ClinicalTrials.gov exception only under INV-4, the scaffolding exception only under INV-15.
* **No copied values.** No partition counts, retention periods, bucket or topic name lists, version strings or schema version value in these files; link the authority. Topic names may appear as identifiers in CON requirement text (they name what the requirement is about).
* **Template.** Each living file opens with `Domain: <NS> · Code: <paths> · Last reviewed against: develop @ e51f742` (a develop SHA, never a feature-branch SHA) and has the H2s Scope, Requirements, Verification, Retired requirements; optional Machine-readable authorities, Known traps, Rationale. Verification table columns: `ID | Source | Verified by | Status`.
* **Frozen paths.** None of this spec's files is frozen, and it moves nothing but itself. It must not move or edit `SETUP.md`, `VERSIONS.md`, `docs/backup-restore.md`, `docs/strategy-research.md`, the hypothesis-cited specs or `specs/point-in-time-universe.md`.
* **Invariants that apply to this work:** 15 (the checks below are written and run before the files are declared done); 9 (dates in entries are UTC dates).

## Dependencies

* **Needs:** `docs-check-tooling` merged into the integration branch; the decision entries listed under Blocked by; the matrix `specs/living-docs-cutover-matrix.md` on the integration branch (this spec fills only the `ID` cells of its own rows and the `IDs` cells of binding decisions rows that carry its prefixes).
* **Hands to later specs:**
  * `INV-1 … INV-15` and every CON ID, so the domain specs replace their CON placeholders. Post the final CON number list in the PR body.
  * The § 3 → INV table (Notes) to `legacy-docs-retirement`.
  * The trap destinations (matrix rows) to the specs that own them; this spec writes only the three CON traps.
  * The root-`CLAUDE.md` section destinations to `agent-instruction-hierarchy`.

## Affected files

| Path | Action |
|---|---|
| `docs/README.md` | create (whole file; sole owner) |
| `docs/system/overview.md` | create |
| `docs/system/invariants.md` | create |
| `docs/system/contracts.md` | create |
| `DECISIONS.md` | modify (append two entries; never edit existing ones) |
| `specs/living-docs-cutover-matrix.md` | modify (`ID` cells of INV/SYS/CON fragment rows; `IDs` cells of decisions-table rows classified binding whose fragment rows carry `M-INV-`, `M-SYS-` or `M-CON-`) |
| `docs-check.toml` | modify (`[rollout] planned_domains`: remove `"system"` only, as the last step) |
| `TODO.md` | modify (this spec's own row only: status `done`, link to `specs/done/`) |
| `specs/living-docs-system-and-contracts.md` → `specs/done/living-docs-system-and-contracts.md` | move (Status `done`) |
| `CLAUDE.md`, `services/CLAUDE.md`, `services/core-hub/CLAUDE.md`, `services/ingestion-scraper/CLAUDE.md`, `docker/CLAUDE.md` | untouched, cited |
| `docs/requirements.md` §0–§3, §10, §14 | untouched, cited |
| `docker/topics.yaml`, `services/ingestion-scraper/src/auspex_ingest/models.py`, `…/identity.py`, `…/extractor.py`, `…/messaging/kafka_producer.py`, `…/pipeline.py`, `services/core-hub/src/test/resources/contract/signal_event_v1.json`, `services/core-hub/src/main/java/dev/auspex/corehub/signal/ResearchSignalEvent.java`, `…/corroboration/CorroboratedSignalEvent.java`, `…/audit/RawAuditService.java`, `…/config/KafkaConfig.java`, `services/strategy/src/auspex_strategy/runtime/events.py`, `services/backup/src/auspex_backup/restore.py` | untouched, cited |

## Required tests

All checks run from the repo root. `python3 -m tools.docs_check` and its flags are created by `docs-check-tooling`; output is one line per finding, `CHECK path:line message`. Every run is scoped with `--paths` to this spec's own files: `docs/README.md,docs/system/**,specs/living-docs-system-and-contracts.md` (after the move, the `specs/done/` path).

**Checker assertions** (fail = any finding line, or a non-zero exit for check M):

* `matrix_rows_for_invariants_all_have_assigned_ids` — `python3 -m tools.docs_check --matrix specs/living-docs-cutover-matrix.md --domain INV`. Fails if a move/ratify/divergent/retire row has no ID that check C finds, or (as check M verifies) the ID's verification `Source` cell lacks the row's document-level source reference (file path, requirements §, or DECISIONS heading; line numbers are not compared). M-INV-036 and M-INV-042 are `link` rows and are not checked.
* `matrix_rows_for_system_all_have_assigned_ids` — same, `--domain SYS`.
* `matrix_rows_for_contracts_all_have_assigned_ids` — same, `--domain CON`.
* `binding_decisions_for_system_carry_ids` — `python3 -m tools.docs_check --matrix specs/living-docs-cutover-matrix.md --decisions --domain INV` (then `SYS`, `CON`; the domain filter selects binding rows by the `NS` cell of their fragment rows) reports no finding (empty `IDs`, unknown ID, or heading text missing from the ID's `Source` cell). The processing-time rows M-INV-036 and M-INV-042 are `link` rows to STR in the matrix and need no INV ID.
* `system_docs_links_and_paths_resolve` — checks A and B report no finding for these files. Links to owner docs of domains still in `planned_domains` appear as notices on stderr, not findings.
* `system_ids_defined_once` — check C reports nothing for INV/SYS/CON.
* `system_references_and_decision_headings_resolve` — check D reports nothing for these files: every `NS-NNN`, "Invariant N" and cited `DECISIONS.md` heading resolves; no register number; no CON placeholder.
* `system_docs_have_required_sections` — check E reports nothing: required H2s present; `Last reviewed against` is an ancestor of HEAD; this spec keeps every required section.
* `system_verification_rows_complete` — check K reports nothing: one row per active ID; every `tested` row's `path::name` exists as `def name` / `void name(` in that file; `Source` non-empty.
* `system_domain_no_longer_planned` — after `"system"` is removed from `planned_domains`, check F reports no finding for domain `system`.

**Spec-specific checks** (each a command in the definition of done):

* `invariants_follow_claude_numbering_and_text` — for N in 1–15 except amended ones, the text after `**INV-N** — ` on the definition line equals `git show e51f742:CLAUDE.md` line `54+N` with the `N. ` prefix removed. Fails on any reorder or rewording without an amendment line.
* `no_sixteenth_invariant` — `grep -cE 'id="INV-1[6-9]"' docs/system/invariants.md` is 0 (the pattern is written as a range so check D does not read it as a reference to an undefined ID).
* `inv6_amendment_quotes_previous_text_exactly` — if the invariant-6 wording default is chosen, the INV-6 item has an `Amended` line whose quoted text equals `CLAUDE.md:60` minus the `6. ` prefix, and cites the `CHOICE` heading that answers that `PENDING` entry.
* `restore_exception_stated_only_under_inv2` — the restore exception appears inside the INV-2 item, citing both Stack backup `CHOICE` headings and the restore `CHOICE`. Fails if it appears under another item or in `overview.md`/`contracts.md`.
* `ctgov_exception_stated_only_under_inv4` — same for the ClinicalTrials.gov exception and its 2026-09-20 heading; `grep -c 'ClinicalTrials.gov' docs/system/overview.md docs/system/contracts.md` is 0 for both files.
* `scaffolding_exception_stated_only_under_inv15` — the INV-15 item has an `Exception` line naming `pyproject.toml` and `.env.example`; no other file in `docs/system/` names the exemption.
* `inv1_has_read_only_scope_note` — the INV-1 item has a Scope line naming `sample_corroborations.py` as a read.
* `inv_verification_has_source_column` — the header of the INV verification table is `| ID | Source | Verified by | Status |`, and each of the six binding decision headings named in its Source cells (the two Stack backup, two snapshot, Watchlist backend and Strategy runtime `CHOICE` headings) appears there verbatim.
* `raw_pointer_rows_are_divergent_and_cite_the_raw_pointer_decision` — the verification rows for the raw-pointer requirements (shape, every archived document) have status `divergent` and cite the raw-pointer contract heading; the fixture row cites the defects-found-while-scoping heading.
* `corroborated_event_gaps_are_divergent` — the schema-version/fixture requirement for the corroborated event is `divergent` citing the defects-found-while-scoping heading; the at-least-once requirement is `pending-decision` citing the batch heading.
* `closed_set_row_is_not_a_second_divergent` — the closed-set requirement's row is not `divergent`, cites the closed-sets heading in its Source and links `docs/core-hub/consumption.md` (the single `divergent` row for item C7 is HUB's).
* `no_failure_classification_or_log_rule_in_system_docs` — `grep -nEi 'dead-letter(s|ed)? (a|the|any)|is dead-lettered|never logged|logs? (never|must not)' docs/system/overview.md docs/system/contracts.md` prints nothing (classification is HUB's, log content OPS's).
* `readme_lists_every_domain_doc` — each of the 28 `docs/` paths in the tree under What this builds §1 appears as a link target in `docs/README.md`, and `grep -c 'written by spec' docs/README.md` is 0.
* `no_topics_yaml_value_copied` — `grep -nE '\b(604800000|7776000000|2592000000|[0-9]+ partitions|RF ?1|replication)\b' docs/system/*.md docs/README.md` prints nothing.
* `naming_table_links_authorities_without_restating_topic_or_bucket_names` — `grep -nE 'auspex-(raw|prices|strategy)|auspex\.(raw|signals)\.' docs/system/overview.md` prints nothing.
* `no_plan_step_or_register_numbers_in_system_docs` — `grep -nE '\b(Step|Phase) [0-9]|\bD-[0-9]{2}\b|\[(A|B|P2|P3|Q|C|E|F)[0-9-]+\]' docs/README.md docs/system/*.md` prints nothing (provenance tags from requirements.md are not carried over).
* `every_pending_row_is_in_the_ratification_batch` — every ID whose row says `pending-decision` and `system ratification batch`, and every pending exception line, appears in the body of the `system ratification batch` entry in `DECISIONS.md`, and vice versa.
* `existing_suites_unaffected` — `cd services/ingestion-scraper && uv run pytest tests/unit -q` reports the same passed count as on the integration branch before this spec (no code changed; the doc-reading test `test_docs_never_offer_down_v_as_a_fix` still passes).

## Definition of done

Run in this order; the `planned_domains` edit is the last change before the final check run.

```bash
P='docs/README.md,docs/system/**,specs/living-docs-system-and-contracts.md'
python3 -m tools.docs_check --matrix specs/living-docs-cutover-matrix.md --domain INV && \
python3 -m tools.docs_check --matrix specs/living-docs-cutover-matrix.md --domain SYS && \
python3 -m tools.docs_check --matrix specs/living-docs-cutover-matrix.md --domain CON && echo MATRIX-OK
python3 -m tools.docs_check --only A,B,C,D,E,K --paths "$P" && echo SYSTEM-CLEAN
for n in $(seq 1 15); do [ "$n" = 6 ] && continue
  exp=$(git show e51f742:CLAUDE.md | sed -n "$((54+n))p" | sed -E "s/^$n\. //")
  grep -qF "**INV-$n** — $exp" docs/system/invariants.md || echo "INV-$n differs"; done; echo INV-TEXT-CHECKED
test "$(grep -cE 'id="INV-1[6-9]"' docs/system/invariants.md)" -eq 0 && echo NO-INV16
grep -qF '| ID | Source | Verified by | Status |' docs/system/invariants.md && echo INV-SOURCE-COLUMN
grep -nE '\b(604800000|7776000000|2592000000|[0-9]+ partitions)\b|auspex-(raw|prices|strategy)|\bD-[0-9]{2}\b|written by spec' docs/README.md docs/system/*.md ; test $? -eq 1 && echo NO-COPIED-VALUES
(cd services/ingestion-scraper && uv run pytest tests/unit -q | tail -1)
# last change: remove "system" from [rollout] planned_domains in docs-check.toml, then:
python3 -m tools.docs_check --only F | grep -E '\bsystem\b' ; test $? -eq 1 && echo SYSTEM-NOT-PLANNED
python3 -m tools.docs_check --only A,B,D --paths "$P" && echo SYSTEM-LINKS-FINAL
```

Expected: `MATRIX-OK`, `SYSTEM-CLEAN`, `INV-TEXT-CHECKED` with no "differs" line above it, `NO-INV16`, `INV-SOURCE-COLUMN`, `NO-COPIED-VALUES`, the scraper unit line showing the same `N passed` as the integration branch before this spec with 0 failed, `SYSTEM-NOT-PLANNED`, and `SYSTEM-LINKS-FINAL` (links into other planned domains still print as notices on stderr). Then, in the same PR: Status `done`, move this file to `specs/done/`, update this spec's `TODO.md` row.

## Compatibility

* **Readers.** Nothing existing moves or changes. `docs/requirements.md` and every `CLAUDE.md` still say what they said; the new files are additive until the cutover. The integration branch is not `develop`, so no reader sees two authorities live.
* **Links.** No inbound link changes. `docs/README.md` links every planned domain doc; those links are notices until each domain spec merges and must all resolve at the final gate.
* **Agents.** `CLAUDE.md` still auto-loads. Agents working on the integration branch can open `docs/system/invariants.md`; "Invariant N" citations mean the same number.
* **Tests and CI.** No code, test or workflow changes. `docs.yml` is report-only until cutover.
* **Later specs.** CON numbers are stable once merged. A later spec that needs a CON change uses Docs impact and the retirement rule.

## Rollback

On the integration branch, before any domain spec cites a CON or INV number: revert the range `<integration-branch tip before this spec's merge>..<tip after it>` in one commit, in a PR into the integration branch, keeping `DECISIONS.md` as it is (revert every other path), then append `## <date> — Living docs — FLAG — system docs withdrawn` recording the revert and stating that the two entries this spec appended no longer describe live docs. After a dependent spec has merged, revert the dependents first, or fix forward. Nothing reaches `develop`, so no data, runtime or `develop` rollback exists.

## Notes

### Requirements §3 → INV mapping (for `legacy-docs-retirement`'s index; one row each)

| requirements § | Subject | Absorbed by |
|---|---|---|
| §3.1 | Scraper writes only MinIO and Kafka; no cursor-state exemption | INV-1 (scope line carries the Airflow Variables point) |
| §3.2 | core-hub sole writer | INV-2 |
| §3.3 | No credentials, keys or hosts in source; keys as Airflow Connections; logs without credentials or full `raw_content` | INV-6 (amended per the invariant-6 wording decision); logs half: OPS observability log contract |
| §3.4 | Schema symmetry, explicit SNAKE_CASE, generated fixture | INV-7; CON (signal event shape, fixture rule) |
| §3.5 | Synchronous throughout | INV-8 |
| §3.6 | UTC always, including derived strings | INV-9; CON (wire timestamps) |
| §3.7 | Idempotent writes per declared natural key, with table | INV-10; CON (one requirement per key) |
| §3.8 | Write order Neo4j → Postgres → ack, ack mode, qualified `@Transactional` | no INV; HUB (consumption, storage) |
| §3.9 | Consumer semantics | no INV; HUB (consumption) |
| §3.10 | Dead-letter classification, retries, `ErrorHandlingDeserializer`, headers, never block | INV-11; CON (DLT naming, partition, headers, closed-set typing); HUB (classification, retries, deserializer) |
| §3.11 | Parameterized queries, controller allowlist, ArchUnit + injection tests | INV-12; HUB (ticker allowlist) |
| §3.12 | Nothing dies silently; DLT depth and signal age reported | INV-11; HUB (health reporter); OPS (alerts) |

Invariants with no §3 item: INV-3 (§5, §6.1), INV-4 (§6.1, §13 ArchUnit), INV-5 (§4.2), INV-13 (§7, §7.1), INV-14 (§10.1), INV-15 (§13, §14).

### Owner-decision branches

| Decision heading (all `## 2026-10-15 — Living docs — PENDING — …`) | Default (written) | If the owner chooses otherwise |
|---|---|---|
| raw-pointer contract | CON raw shape and "every archived document" approved, both `divergent` | Option b: the "every archived document" requirement says "alongside each published signal" and is `tested`; the field-name requirement stays `divergent` |
| restore exception to invariant 2 | Exception under INV-2 | Option b: no exception; INV-2 `divergent` citing that `CHOICE` until a fix spec routes restore through core-hub |
| invariant 6 wording | INV-6 amended | Option b: INV-6 keeps the `CLAUDE.md` text, status `divergent` (keys are env vars) |
| can a DECISIONS entry narrow an invariant | No; exceptions only under the invariant | If yes: the strategy runtime's skip (2026-10-10 `CHOICE` item 5) is cited as INV-11's exception instead of the FLAG |
| closed sets on the wire | Unknown value invalid on the wire (CON, `untested`); HUB's row `divergent` | If tolerated: the requirement says unknown values are carried as received, status per code; HUB's reaction changes with it |
| processing time in as-of decisions | Nothing written here; STR and RES carry the rule | If adopted: the cutover's decision application writes the sixteenth invariant (`retrieved_at` and `first_detected_at` are processing times too; the owner says whether it names them) |

### Open problems and traps

* **Decision titles** follow the canonical suffixes of the `## 2026-10-15 — Living docs — PENDING — …` entries in `DECISIONS.md`.
* **Closed sets on the wire** is split: CON states the value sets (this spec), HUB owns what a consumer does with an invalid value and carries the one `divergent` row for item C7 (`living-docs-core-hub`).
* **No `extracted_at` on the event.** `## 2026-09-20 — Strategy layer session 2 — FLAG — extracted_at missing from ResearchSignalEvent (§10.2)` is still open; CON does not add the field.
* **The `fda:` prefix** is in `_CANONICAL_PREFIXES` but `fda_approval` has no `sources.yaml` entry (`## 2026-10-15 — Living docs — PENDING — fda_approval source`, written by `living-docs-ingestion`). The canonical-prefix requirement names the authority, not the list, so it is unaffected.
* **Ack mode and listener validation** (items C5 and C6 of the defects entry) are HUB's to record; the `confidence_score` requirement states only the wire half.
* **As built.**
  * **Raw pointer rows are `tested`, not `divergent`.** C1 was fixed on develop (b7582c3, `specs/done/raw-pointer-contract-fix.md`) before this spec ran. CON-005, CON-006 and CON-007 therefore cite the raw-pointer CHOICE and the pointer tests, and the required test `raw_pointer_rows_are_divergent_and_cite_the_raw_pointer_decision` no longer applies.
  * **Reviewed at develop b7582c3, not e51f742.** Line citations follow b7582c3. The invariant text is the same in both.
  * **Answered decisions are cited by their CHOICE heading.**
  * **`Step 1.3` stays in contracts.md.** It appears in the CON-035, CON-036 and CON-037 Source cells and in one Known traps line, as the verbatim `## 2026-08-16 — Step 1.3 — VERIFIED — …` headings, because check M requires the exact heading text.

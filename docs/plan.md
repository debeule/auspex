# Auspex — Execution Plan

`requirements.md` defines *what* the system must satisfy; this file defines *the order and acceptance criteria*.

**Built test-first.** Every step lists **Required Test Cases**, written and failing before implementation.

> **How to read this.** No code exists; this is a greenfield build and this plan is its sole input. Bracketed tags like `[A1]` or `[P2-3]` are provenance markers from adversarial review of this specification — they do not reference anything ever implemented. Where a note calls a choice "intuitive and wrong," that is a warning against a plausible mistake, not a description of existing behaviour. v3 closes a second audit run against v2 itself. Second-pass changes are tagged `[P2-n]`; first-pass tags are retained. The structural changes in v3: cursor ownership moved wholly to the DAG task `[P2-5]`; an `EntityNormalizer` seam added in Phase 1 so Phase 2 substitutes rather than inserts `[P2-11]`; a pre-filter stage before extraction `[P2-8]`; corroboration supersession `[P2-4]`; and a **new Step 4.0 historical backfill**, without which Phase 4 has no sample to measure `[P2-1]`.

---

```xml
<instructions_for_claude>
  1. Execute phases strictly in order (0 → 6). Do not begin a phase until the prior phase's "Definition of Done" is met.
  2. Within a phase, execute steps in numeric order. Pause after each and confirm the Definition of Done.
  3. TDD is mandatory: write the step's "Required Test Cases" first, confirm they fail for the right reason, then implement.
  4. BEFORE writing a step's tests, re-read the requirements.md sections it cites and confirm the test list is consistent with them. If a listed test can only pass by violating a requirement, STOP and flag it — do not write the test. (In v1, Step 2.1's test list encoded an architecture error that TDD would have faithfully built. A green suite is necessary, not sufficient.)
  5. Before writing any Phase 0 code, outline the directory tree and confirm it matches "Directory Structure".
  6. Keep all code modular, typed, and clean with production-ready error handling.
  7. Never violate an "Architecture Invariant" — if a task appears to require it, stop and flag it.
  8. Treat each step's "Out of Scope" as a hard boundary.
  9. "Required Test Cases" is a minimum, not a ceiling. Add tests; never delete or weaken a listed case to make a build pass.
 10. Read PROGRESS.md at the start of every session; the first unchecked box is the work. Update it as each item completes, not at the end.
 11. Scaffolding is exempt from test-first: build files, directory trees, docker-compose.yml, and .env.example are not behaviour. Everything else needs a failing test first.
 12. "Fails for the right reason" is mechanical: ImportError / AttributeError / AssertionError in Python, an assertion or missing-symbol failure in Java. A collection error, syntax error, or misconfigured path is NOT a valid red. Paste the failure output into PROGRESS.md before implementing.
 13. A test run that executed zero tests is a failure, not a pass. Report the test count for every step.
 14. Branch per phase, commit per step, commit only when the step's tests pass. Never commit .env or build output.
 15. When you stop and flag, append to DECISIONS.md with the required format and halt the phase. Do not work around an invariant.
 16. Every version is pinned in VERSIONS.md. Never install a floating version, a `latest` tag, or a `>=` range.
</instructions_for_claude>
```

---

## Architecture Invariants

1. **Event-driven decoupling:** `ingestion-scraper` writes only to MinIO and Kafka. **No exceptions** — cursor state belongs to the orchestrator `[P2-5]`.
2. **Single writer:** `core-hub` is the sole writer to the application database and Neo4j.
3. **Orchestration does not do work:** a DAG task resolves config, reads/writes the cursor, and calls `IngestionPipeline.run(source_type, cursor)`. No ingestion logic in DAG code; no pipeline logic inside `fetch_since()`.
4. **Sources are pluggable:** every source is a `SourceConnector` in `sources.yaml`. No source-specific branching in `dag_factory`, `IngestionPipeline`, `GraphUpdateService`, or the REST layer.
5. **Correlation is swappable:** all corroboration sits behind `CorroborationService`.
6. **No hardcoded config:** env-driven via `.env`; source API keys are Airflow Connections.
7. **Schema symmetry:** Python model and Java record identical, snake_case on the wire, contract fixture generated from the Python model.
8. **Synchronous execution model.**
9. **UTC on the wire and in derived strings**, including MinIO keys.
10. **Idempotent writes on each path's declared natural key** (requirements §3.7).
11. **Nothing dies silently:** DLT with diagnostic headers, never blocking a partition; DLT depth reported.
12. **Parameterized queries only**, enforced by ArchUnit plus behavioural injection tests.
13. **The archive is unconditional:** every successful fetch writes a MinIO snapshot before any other side effect.
14. **Identity is document identity:** `event_id` never varies with schema version, prompt, model, or which source observed the document (requirements §10.1) `[P2-3]`.
15. **Test-first**, subject to instruction 4.

## Directory Structure

```
/docker
  docker-compose.yml
  topics.yaml
/services
  /ingestion-scraper
    /prompts/extraction        (versioned prompt files)
    /config/prefilter          (versioned pre-filter vocabularies)   [P2-8]
    /tests {unit,integration,fixtures,golden}
  /core-hub
    build.gradle.kts  settings.gradle.kts  gradle/libs.versions.toml
    /src/main/resources/db/migration    (Flyway's required directory name; these are
                                         schema-creation scripts for an empty database,
                                         not upgrades from anything)
    /src/test/java                      (unit — ./gradlew test)
    /src/integrationTest/java           (container-backed — ./gradlew integrationTest)
    /src/test/resources/contract        (generated — do not hand-edit)
/services/backtesting
/orchestration/airflow/{dags,config}
CLAUDE.md          (root — auto-loaded by Claude Code every session)
PROGRESS.md  VERSIONS.md  DECISIONS.md
/docs  plan.md  requirements.md  PREREQUISITES.md
/services/CLAUDE.md                     (cross-service contract; auto-loaded under services/)
/services/ingestion-scraper/CLAUDE.md   (Python conventions; auto-loaded when working here)
/services/core-hub/CLAUDE.md            (Java conventions; auto-loaded when working here)
/docker/CLAUDE.md                       (infra commands and traps; auto-loaded when working here)
.env.example  .gitignore  README.md  verify_pipeline.sh
```

---

## Phase 0 — Environment & Infrastructure

### Step 0.0 — Preflight & Version Pinning `[P3-3]`
**Objective:** fail fast on environment problems, and turn every floating version into an exact one, before any code exists. Testcontainers is load-bearing from Step 1.1 — discovering a Docker problem there means discovering it mid-step, and the likely silent failure is integration tests being skipped rather than run.
**Tasks:**
- Verify the Docker daemon is reachable and Compose v2 is present.
- Verify the toolchain: `uv`, JDK 25, the **Gradle wrapper** (`./gradlew --version` → Gradle 9.7.0 on JVM 25).
- Confirm `failOnNoDiscoveredTests` is available on the `Test` task; if not, record the test-count fallback in `DECISIONS.md`.
- Resolve every *resolve at 0.0* entry in `VERSIONS.md` to an exact version and **write it back into that file**.
- Pull all five images and confirm each starts.
- Confirm the ⏳ items in `PREREQUISITES.md` have been requested; record the dates in `DECISIONS.md`.
**Checks (a script, not a test suite — nothing exists to test yet):**
- `docker info` succeeds; `docker compose version` reports v2+.
- Each pinned image pulls by exact tag.
- `python --version`, `java -version`, `uv --version` match `VERSIONS.md`.
- No entry in `VERSIONS.md` still reads *resolve at 0.0*.
**Definition of Done:** the preflight script exits 0 and `VERSIONS.md` contains no unresolved entries.
**Out of Scope:** any application code, any container configuration.

### Step 0.1 — Root Scaffolding
**Tasks:** directory tree; `.env.example` covering `COMPOSE_PROJECT_NAME=auspex`, both Postgres databases, Neo4j, Kafka, MinIO (bucket `auspex-raw`), `OPENAI_API_KEY`, `EXTRACTION_MODEL`, `WATCHED_TICKERS`, `EPO_OPS_KEY`, `EPO_OPS_SECRET`, `NCBI_API_KEY` (optional), `OPENFDA_API_KEY`, `SEC_USER_AGENT`, `TZ=UTC` — **no defaults for any credential**; `.gitignore`. All identifiers follow the naming table in `CLAUDE.md`.
**Required Test Cases:**
- `test_env_example_covers_all_referenced_vars` (documented ignore-list permitted for dynamic lookups).
- `test_no_legacy_topic_prefix_remains` — no `biotech.` identifier anywhere in the repo; the project prefix is `auspex.`.
- `test_env_file_is_gitignored`.
- `test_no_credential_has_a_source_default`.
**Definition of Done:** Step 0.1 tests pass.

### Step 0.2 — Docker Compose & Topic Provisioning
**Tasks:** `kafka` (KRaft, auto-topic-creation **disabled**), `postgres` 16 (named volume, `TZ=UTC`, init script creating the application DB and `airflow` with separate roles, no cross-grants), `neo4j` 5, `minio` (+ bucket). **All ports bound to `127.0.0.1`.** `topics.yaml` plus a provisioning script creating every topic with explicit partitions (6), RF (1), and retention — invoked by compose, by `IngestionPipeline` startup, and by the Java test fixture. DLTs get the same partition count as their source topics.
**Required Test Cases:**
- `test_all_containers_reachable`; `test_postgres_has_separate_airflow_database`; `test_postgres_timezone_is_utc`; `test_minio_bucket_exists`.
- `test_topics_created_from_topics_yaml_with_declared_partitions_and_retention`.
- `test_dlt_partition_count_matches_source_topic` — prevents a DLT publish that itself fails.
- `test_producing_to_an_undeclared_topic_fails` — set a low `message.timeout.ms` in the test so it fails fast; `confluent-kafka` produce is async, so assert on the delivery report, not an immediate raise `[P2-13]`.
**Definition of Done:** all four containers healthy; Step 0.2 tests pass.
**Out of Scope:** Airflow (Step 2.1); its database is provisioned here only because the compose init script runs solely against an empty data directory.

---

## Phase 1 — Core Pipeline MVP (Mock Data)

### Step 1.1 — Connector Contract & Raw Storage
**Tasks:** `pyproject.toml` (no async clients); `RawDocument` per requirements §6.3 including typed `canonical_id`, `published_date`, `content_sha256`; `SourceConnector` ABC — **fetch and map only**; `minio_client.py` writing `raw/{source_type}/{external_id}/{retrieved_at:%Y%m%dT%H%M%SZ}-{sha256[:8]}.json`.
**Required Test Cases:**
- `test_rawdocument_rejects_naive_datetime`; `test_rawdocument_normalizes_offset_to_utc`; `test_rawdocument_requires_schema_version`.
- `test_canonical_id_is_typed_or_absent` — `doi:`/`nct:`/`epo-app:`/`edgar:` prefix, never a bare identifier `[P2-3]`.
- `test_minio_key_includes_retrieved_at_and_content_hash`.
- `test_minio_key_converts_offset_timestamp_to_utc_wall_time`.
- **Edge:** `test_refetch_with_changed_content_creates_second_object`.
- **Edge:** `test_same_second_refetch_of_identical_content_is_a_noop_not_an_error`.
- **Edge:** `test_same_second_refetch_of_different_content_creates_a_distinct_key`.
- `test_connector_is_abstract`; **Edge:** `test_fetch_since_is_not_a_coroutine_and_returns_an_iterator`.
- `test_fetch_since_performs_no_io_beyond_http` — fake MinIO/Kafka clients record zero calls.
**Definition of Done:** suite passes against a Testcontainers MinIO.

### Step 1.2 — Mock Connector, Pre-filter, Extraction, Pipeline, Publish
**Tasks:**
- `MockConnector` returning four documents: two sharing a gene target from different source types (the corroboration case), one containing no research signal (the `None` case), and one that the pre-filter should reject `[P2-8]`.
- `ResearchSignalEvent` per requirements §10.2, including `extraction_id`, `external_id`, `raw_object_key`, `prefilter_version`, and **list-valued** `gene_targets`/`mechanisms`.
- Identity per requirements §10.1: `event_id` from `canonical_id` alone when present, else `(source_type, external_id)`.
- `prefilter.py` — deterministic vocabulary match, versioned file in `config/prefilter/` `[P2-8]`.
- `llm_extractor.py` returning `ResearchSignalEvent | None`; client injected; prompt in `prompts/extraction/v1.md`; content passed as delimited data; `raw_content` truncated; `gene_targets` validated against a controlled vocabulary.
- `EntityNormalizer` interface with an **identity implementation**; every entity value passes through it `[P2-11]`.
- `kafka_producer.py`: pointer event keyed by `external_id`, signal event keyed by `event_id`, `schema_version` header on both, **`flush()` and delivery-report check before returning**.
- **`IngestionPipeline.run(source_type, cursor) -> RunResult`**: pre-filter → dedup → archive → extract → publish, per-document error isolation, full counts plus `max_published_date_processed`. **Stateless with respect to cursors** `[P2-5]`.
- `run_mock_ingestion.py` as a thin CLI taking the cursor as an argument. An injected `now()` provider.
**Required Test Cases:**
- `test_confidence_score_bounds`.
- `test_event_id_is_stable_across_schema_version_bump` — the intuitive design puts `schema_version` in the id; that is wrong, and this is the guard.
- `test_same_canonical_id_from_two_source_types_yields_one_event_id` — **fails against the near-miss formula `uuid5(f"{source_type}:{canonical_id}")`, which cannot collapse mirrors because `source_type` differs** `[P2-3]`.
- `test_event_id_falls_back_to_source_and_external_id_when_no_canonical_id`.
- `test_connector_supplying_canonical_id_intermittently_fails_loudly` — identity must not depend on field availability `[P2-3]`.
- `test_raw_topic_payload_excludes_raw_content`; `test_raw_topic_keyed_by_external_id`; `test_signals_topic_keyed_by_event_id`.
- `test_schema_version_header_present_on_both_topics`; `test_timestamps_serialize_as_utc_z`.
- `test_signal_event_carries_external_id_and_raw_object_key` — the chain-of-custody guard.
- `test_llm_client_is_never_called_live` — enforced by `pytest-socket`.
- **Edge:** `test_prefiltered_document_is_archived_but_never_reaches_the_llm` `[P2-8]`.
- **Edge:** `test_prefilter_counts_appear_in_run_result` — silent filtering is the failure mode.
- **Edge:** `test_document_with_no_signal_is_archived_but_publishes_no_event`.
- **Edge:** `test_extractor_returns_none_rather_than_inventing_a_gene_target`.
- **Edge:** `test_publish_threshold_defaults_to_zero_and_is_counted_when_raised` `[P2-7]`.
- **Edge:** `test_injected_instruction_in_raw_content_does_not_change_extracted_entities`.
- **Edge:** `test_gene_target_outside_controlled_vocabulary_is_flagged_not_written`.
- **Edge:** `test_llm_returns_invalid_payload` — nothing published.
- **Edge:** `test_one_bad_document_does_not_abort_the_batch`.
- **Edge:** `test_kafka_delivery_failure_fails_the_run`.
- `test_pipeline_archives_before_publishing`; `test_pipeline_reads_no_cursor_state` `[P2-5]`.
- `test_entity_values_pass_through_the_normalizer` — the seam exists before Phase 2 needs it `[P2-11]`.
**Definition of Done:** suite passes, including a Testcontainers-Kafka integration test asserting message counts per topic.

### Step 1.3 — Core Hub Scaffolding
**Tasks:**
- Spring Boot 3.3+ with Flyway and ArchUnit. `application.yml`: env-driven hosts; Jackson `JavaTimeModule`, `WRITE_DATES_AS_TIMESTAMPS=false`, **`FAIL_ON_UNKNOWN_PROPERTIES=false`**, `SNAKE_CASE`; `ack-mode: RECORD`, `auto-offset-reset: earliest`; `ddl-auto: validate`; JVM `TZ=UTC`.
- Java `ResearchSignalEvent` record; **`BigDecimal` + `@NotNull @DecimalMin("0.0") @DecimalMax("1.0")`**; `@Valid` on the listener payload.
- **Flyway `V1__signal_schema.sql`**: `raw_fetch_audit`, `signal_current`, `signal_extraction_history`, **`source_observation`** `[P2-3]`, `corroboration` (with `participants_hash` and `superseded_by`) `[P2-4]`, per requirements §3.7. `confidence_score NUMERIC(4,3)`.
- Two listeners with **`ErrorHandlingDeserializer`** on both.
- Neo4j per requirements §9: `Company` MERGEd on normalized `name`; **`confidence_score` persisted as a `double` through an explicit converter** `[P2-6]`; constraints, indexes, and a `(:GraphSchema {version})` node created idempotently at startup.
- `GraphUpdateService`: MERGE only, Neo4j → Postgres → ack, **qualified transaction managers**, separate repository base packages.
- `DefaultErrorHandler` + `DeadLetterPublishingRecoverer` with a **custom resolver** producing lowercase `.dlt` and partition `-1`; `FixedBackOff` giving 1 attempt + 2 retries.
- Injected `java.time.Clock`.
**Required Test Cases** *(unit unless marked)*:
- *Unit:* `test_signal_event_json_contract_matches_generated_python_fixture`.
- *Unit:* `test_minor_version_bump_with_extra_field_is_accepted`.
- *Unit:* `test_unknown_major_schema_version_is_classified_as_deterministic_failure`.
- *Unit:* `test_missing_confidence_score_is_rejected_not_defaulted_to_zero` — fails against a primitive `double`.
- *Unit:* `test_snake_case_payload_maps_to_every_record_component`.
- *Unit:* `test_schema_version_compares_as_major_minor_integers_not_strings`.
- *Container:* `test_timestamp_round_trip_preserves_instant`; **Edge:** `test_naive_timestamp_is_rejected_to_dlq`.
- *Forked JVM:* **Edge:** `test_non_utc_default_timezone_does_not_alter_stored_values` (`-Duser.timezone=America/New_York`).
- *Container:* `test_duplicate_delivery_creates_one_audit_row`; `test_duplicate_delivery_creates_one_signal_node`.
- *Container:* **Edge:** `test_redelivery_with_new_extraction_upserts_current_and_appends_history`.
- *Container:* `test_second_source_observation_appends_and_does_not_change_signal_source_type` — first observation wins, so corroboration counts cannot shift retroactively `[P2-3]`.
- *Container:* **Edge:** `test_listener_container_restart_midbatch_is_idempotent` (Spring `MessageListenerContainer`, not the Docker container).
- *Container:* `test_neo4j_failure_prevents_offset_commit_and_redelivery_converges`.
- *Container:* `test_every_signal_row_has_a_matching_graph_node` — the reconciliation nothing else asserts.
- *Container:* `test_confidence_score_is_numerically_comparable_in_cypher` — `WHERE s.confidence_score > 0.5` must filter, not string-compare `[P2-6]`.
- *Container:* `test_two_companies_without_tickers_are_two_nodes`.
- *Container:* `test_signal_is_a_node_not_relationship_properties`; `test_one_signal_referencing_three_entities_is_stored_once`; `test_signal_with_multiple_gene_targets_creates_one_node_and_n_edges`.
- *Container:* `test_malformed_json_goes_to_dlt_immediately`; **Edge:** `test_poison_message_does_not_block_partition` — both fail without `ErrorHandlingDeserializer`.
- *Container:* `test_unknown_enum_value_goes_to_dlt`; `test_transient_failure_gives_exactly_three_deliveries_then_dlt`; `test_dlt_headers_present`; `test_dlt_publish_succeeds_with_custom_lowercase_resolver`.
- *Container:* `test_raw_listener_writes_audit_row_only`.
- *Container:* `test_schema_applies_to_an_empty_database`; `test_ddl_auto_is_validate`.
- *ArchUnit (scoped to application packages)* `[P2-10]`: `test_no_unqualified_transactional`; `test_no_query_built_by_string_concatenation`.
**Definition of Done:** suite passes; the container-backed portion completes in under three minutes locally.

### Step 1.4 — Corroboration Service
**Tasks:**
- `@Scheduled` job matching **pairwise** (requirements §4): same entity via `EntityNormalizer`, distinct `source_type`, `|Δ published_date| ≤ 90 days`, over `(:Signal)-[:TARGETS|USES_MECHANISM]->(e)`.
- A `corroboration_watermark` on `ingested_at` drives the scan `[P2-4]`.
- Records keyed `(entity_key, participants_hash)` with `superseded_by`, `corroborated_at = max(participant.published_date)`, `first_detected_at = clock.instant()`.
- Publish non-superseded records to `auspex.signals.corroborated`.
- Degree cap (default 500) on hub entities. All Cypher parameterized.
- The whole test list below is an **abstract contract test class** any implementation must pass.
**Required Test Cases:**
- `test_two_distinct_sources_same_target_produces_one_corroboration`.
- **Edge:** `test_two_historical_signals_90_days_apart_corroborate_regardless_of_run_time` — dated three years ago, fixed clock. **Fails against a wall-clock (`now − 90d`) window — the obvious reading of "rolling 90 days", which would leave Phase 4 with nothing to measure.**
- **Edge:** `test_two_signals_same_source_type_produce_none`; `test_signals_91_days_apart_produce_none`.
- **Edge:** `test_signal_exactly_at_window_boundary` — inclusive or exclusive, asserted and documented.
- **Edge:** `test_two_signals_sharing_only_a_company_do_not_corroborate`.
- **Edge:** `test_high_degree_entity_is_skipped_by_the_degree_cap`.
- `test_corroborated_at_is_latest_participant_publication_not_run_time`.
- `test_repeated_scheduler_runs_do_not_duplicate`; `test_watermark_advances_and_is_not_reprocessed` `[P2-4]`.
- **Edge:** `test_fourth_signal_supersedes_rather_than_duplicating` — an entity at three sources gaining a fourth produces one new row with the old row marked superseded, **not two live rows for the same evidence** `[P2-4]`.
- **Edge:** `test_superseded_rows_are_retained_for_backtesting_but_excluded_from_notifications`.
- **Edge:** `test_corroboration_via_mechanism_when_no_gene_target`.
- **Edge:** `test_three_distinct_sources_produce_one_live_record_not_one_per_pair`.
- `test_corroboration_survives_reextraction_of_a_participant` — a new `extraction_id` under the same `event_id` creates no second corroboration.
**Definition of Done:** suite passes via the abstract contract class.

### Step 1.5 — REST API
**Tasks:** `GET /api/v1/signals/{ticker}` with allowlist validation at the boundary; parameterized Cypher returning direct signals and corroborated signals reachable via shared entities within 1–2 hops; DTO with linking entity, distinct source types, `corroborated_at`, overall confidence, UTC `Z` timestamps; `@ControllerAdvice`; CORS.
**Required Test Cases:**
- `test_returns_direct_and_corroborated_signals` against a seeded graph containing two corroborating signals, one non-corroborating signal on the same ticker, one signal on a different ticker, and **one signal reachable only via a shared gene target with no ticker mention** — the actual product claim.
- `test_superseded_corroborations_are_excluded_from_responses` `[P2-4]`.
- **Edge:** `test_unknown_ticker_returns_empty_lists_not_500`.
- **Edge:** `test_dotted_ticker_is_accepted_and_routed` (`BRK.A`).
- **Injection:** `test_injection_payload_is_rejected_or_bound_and_node_count_is_unchanged` — `A" OR 1=1 //` and `'); MATCH (n) DETACH DELETE n //` as ticker and as every additional parameter; `400` where the allowlist applies, empty results where binding applies, node count identical before and after.
- `test_ticker_allowlist_rejects_lowercase_unicode_and_overlong`.
- `test_confidence_score_serialized_in_0_1_range`; `test_timestamps_serialized_as_utc_z`; `test_error_handler_returns_structured_body_not_stacktrace`.
**Definition of Done:** suite passes.
**Out of Scope:** auth, pagination, rate limiting.

### Step 1.6 — End-to-End Verification
**Tasks:** `verify_pipeline.sh` (smoke only); a full-pipeline Testcontainers test covering the same path; README commands.
**Required Test Cases:**
- `test_end_to_end_mock_ingestion_to_rest_response`.
- `test_pipeline_is_rerunnable` — audit rows, nodes, corroborations unchanged on a second run.
- `test_archived_but_unpublished_document_is_republished_on_the_next_run` — simulate a Kafka failure after the MinIO write. **The silent-permanent-loss case that arises if dedup keys on fetch rather than on published content.**
- `test_verify_script_exits_zero_on_clean_stack` — the container-down variant is a **manual** check; stopping a container breaks concurrent Testcontainers tests.
**Definition of Done:** both suites pass on a clean checkout with no manual steps beyond `.env`. `verify_pipeline.sh` exiting 0 is a supporting signal, not the criterion.

### Step 1.7 — Phase 2 Readiness Review (decisions, not code)
**Tasks:** one page in `README.md` recording the cursor rule; the ticker-resolution source and the fate of unresolvable companies; the `sources.yaml` schema **including** `schedule` (Airflow 3 name — **not** `schedule_interval`), `rate_limit_rps`, `initial_lookback`, `max_documents_per_run`, `prefilter_vocabulary`, and `source_config`; the Step 2.0 extraction-quality gate; and the Step 4.0 backfill budget in documents and dollars `[P2-1]`.
**Required Test Cases:** `test_sources_yaml_schema_validates_all_declared_fields`; `test_unknown_field_in_sources_yaml_is_rejected_at_parse_time`.
**Definition of Done:** the page exists and the schema tests pass.

---

## Phase 2 — Real Source Ingestion

### Step 2.0 — Extraction Quality Harness
**Objective:** make extraction quality measurable before five connectors depend on it. Every test in this plan stubs the LLM, by design — so without this step nothing anywhere detects that extraction is simply wrong.
**Tasks:** promote the prompt to a reviewed versioned artifact; assemble 20–30 hand-labelled **real** documents across all source types in `tests/golden/`; a scoring script reporting per-field precision/recall, the `is_signal` confusion matrix, `confidence_score` calibration, and **pre-filter false negatives** `[P2-8]`. Run manually, never in CI. Record a baseline and the threshold from Step 1.7.
**Required Test Cases:**
- `test_golden_set_covers_every_source_type_and_both_is_signal_classes`.
- `test_golden_set_includes_documents_the_prefilter_should_and_should_not_reject` `[P2-8]`.
- `test_scoring_script_reproduces_hand_computed_scores_on_a_toy_set`.
- `test_prompt_and_prefilter_versions_are_recorded_on_every_extracted_event`.
**Definition of Done:** a scored baseline exists and is recorded in the README, including the pre-filter's false-negative rate.

### Step 2.1 — Airflow, DAG Factory, Pipeline Wiring
**Tasks:** add `airflow` to compose against its own logical database; `sources.yaml` per the Step 1.7 schema; `dag_factory.py` generating one DAG per entry whose single task **reads the cursor Variable, calls `IngestionPipeline.run(source_type, cursor)`, and writes back `max_published_date_processed` on success** `[P2-5]`; `catchup=False` (explicit, even though Airflow 3 now defaults to it), `max_active_runs=1`, staggered schedules; the shared `RateLimitedClient`; API keys as Airflow Connections.
**Required Test Cases:**
- `test_dag_factory_generates_one_dag_per_registry_entry`; `test_generated_dags_have_no_import_errors`.
- `test_dag_task_delegates_to_ingestion_pipeline` — **not `test_dag_task_only_invokes_fetch_since`: that phrasing can only pass if `fetch_since` performs the MinIO write and Kafka publish, pushing the whole pipeline into every connector.**
- `test_dag_module_imports_no_connector_or_client_classes`.
- `test_generated_dags_set_catchup_false_and_max_active_runs_one`.
- `test_cursor_is_read_and_written_only_by_the_dag_task` `[P2-5]`.
- `test_cursor_advances_only_after_a_successful_run`; `test_failed_run_leaves_cursor_unchanged`; `test_cursor_advances_to_max_published_date_not_now`; `test_cursor_is_utc_aware`.
- **Edge:** `test_malformed_sources_yaml_fails_loudly` at parse time; **Edge:** `test_duplicate_source_type_is_rejected`.
- `test_airflow_metadata_is_a_separate_database`.
- `test_rate_limited_client_enforces_configured_rps` (fake clock); `test_two_connectors_on_the_same_host_share_one_bucket`.
- `test_dag_factory_contains_no_source_specific_branching`.
**Definition of Done:** suite passes with only `MockConnector` registered, and the generated DAG produces the same MinIO/Kafka output as `run_mock_ingestion.py`.

### Step 2.2 — Academic Papers Connector
**Tasks:** `AcademicPaperConnector` over bioRxiv (`https://api.biorxiv.org/details/{server}/{start}/{end}/{cursor}`, no key, 100/page, integer cursor) and PubMed E-utilities (optional key: 3→10 req/s). **`raw_content` is title + abstract — the details endpoint returns no full text.** `canonical_id = "doi:<doi>"`. `published_date` = the fetched version's posting date.
**Required Test Cases (fixture-driven):**
- `test_biorxiv_payload_maps_to_rawdocument`; `test_pubmed_payload_maps_to_rawdocument`.
- `test_published_date_is_the_public_posting_date_not_retrieved_at`.
- `test_doi_is_set_as_typed_canonical_id`.
- `test_same_paper_from_biorxiv_and_pubmed_produces_one_event_id_and_two_source_observations` `[P2-3]`.
- **Edge:** `test_missing_author_corresponding_and_missing_category_do_not_crash_mapping` — named fields, not "missing optional fields" in the abstract.
- **Edge:** `test_non_utc_source_date_is_converted`.
- **Edge:** `test_http_429_is_retried_after_the_limiter_backs_off`; `test_http_500_surfaces_as_task_failure`.
- **Edge:** `test_empty_result_set_yields_no_documents_and_no_error`.
- **Edge:** `test_new_biorxiv_version_of_the_same_doi_is_an_amendment_not_a_duplicate`.
- `test_connector_runs_through_the_unchanged_ingestion_pipeline` — constructed only via the registry. **Not `test_no_change_required_to_core_pipeline`: asserting the absence of a diff is unfalsifiable in a test.**
**Definition of Done:** suite passes, plus one manual live check and a Step 2.0 golden-set score at threshold for this source type.

### Step 2.3 — Patent Filings Connector
**Tasks:**
- `EpoOpsPatentConnector` over `https://ops.epo.org/3.2/rest-services/`; OAuth2 client credentials (`EPO_OPS_KEY` / `EPO_OPS_SECRET`) POSTed to `/auth/accesstoken`; token cached and refreshed before its 20-minute expiry; both PatentsView URLs and Lens.org are not viable — see DECISIONS.md and CLAUDE.md known traps.
- Search via `POST /rest-services/published-data/search` with CQL queries filtering by applicant name (`pa`) and CPC class (`cl`: C12N, A61K, A61P, C07K); paginate using the `X-OPS-Range` header (max 2,000 results per window — split on date for backfill). Covers EP, PCT (WO), and US patents via DOCDB; US data arrives via USPTO→EPO feed with a 1–2 week lag, acceptable for weekly polling.
- **`published_date` = pre-grant publication date (kind A1/A2 `date_published`), else grant date.** `filing_date` retained, never used for alignment. A US application is not public at filing — it publishes ~18 months later.
- `canonical_id = "epo-app:<country>-<app_number>"` derived from `application-reference` — stable across the pre-grant publication (A1) and its later grant (B1/B2) for the same application. `external_id` = full DOCDB publication reference `<country>-<pub_number>-<kind>` (e.g. `US-20240123456-A1`). Confirm the exact XML element path against a real API response and record in DECISIONS.md.
**Required Test Cases:** the Step 2.2 shape, plus:
- `test_published_date_is_the_public_disclosure_date_not_filing_date` — fixture with an 18-month gap. **The corrected look-ahead guard; must fail if the fields are swapped back.**
- `test_filing_date_and_granted_date_are_retained_and_excluded_from_alignment`.
- `test_pregrant_publication_and_its_later_grant_resolve_to_one_event_id` — A1 and B1 records share the same `application-reference`, yielding one `canonical_id` and one `event_id` `[P2-3]`.
- **Edge:** `test_pending_filing_with_no_grant_date_is_handled`.
- **Edge:** `test_missing_api_credentials_fail_with_clear_message_not_deep_401`.
- **Edge:** `test_oauth_token_is_refreshed_before_expiry`.
- **Edge:** `test_429_respects_the_retry_after_header`.
- **Edge:** `test_pct_application_with_us_and_ep_designations_produces_one_document`.
**Definition of Done:** suite passes; confirm EPO OPS standard-tier rate limit (2.5 req/s) from documentation and record in DECISIONS.md; one manual live query returning at least one record for each of the 8 watched companies.

### Step 2.4 — Clinical Trials Connector
**Tasks:** `ClinicalTrialConnector` over `https://clinicaltrials.gov/api/v2/studies` (no key, `nextPageToken`, `pageSize` ≤ 1000, `fields` projection). `canonical_id = "nct:<NCT id>"`. **`published_date` = `studyFirstPostDateStruct.date`, or `lastUpdatePostDateStruct.date` on an amended fetch** — submission is private, posting is public.
**Required Test Cases:** the Step 2.2 shape, plus:
- `test_published_date_is_a_post_date_not_the_submission_date`; `test_both_date_fields_retained_separately`.
- **Edge:** `test_amended_trial_creates_a_new_snapshot_and_a_new_extraction_under_the_same_event_id`.
- **Edge:** `test_unchanged_refetch_is_archived_but_not_re_extracted`.
**Definition of Done:** suite passes.

### Step 2.5 — Regulatory Connector (rescoped)
**Tasks:** `FdaApprovalConnector` over openFDA `drugsfda`, `label`, `drugshortages`. Free key needed in practice — **1,000 requests/day without one.** **Do not attempt Fast Track / RMAT / orphan designations via openFDA:** verified, there is no designations endpoint; orphan designations live in a separate FDA database published as an HTML search with spreadsheet export, and Fast Track/RMAT are not machine-readable at all. Optional stretch: a slow-schedule bulk import of the orphan export, and/or a press-release feed as its **own `source_type`**.
**Required Test Cases:** the Step 2.2 shape, plus:
- `test_approval_action_maps_to_expected_directionality`.
- **Edge:** `test_record_without_company_match_still_ingests`.
- **Edge:** `test_daily_quota_exhaustion_surfaces_as_a_clear_error_not_an_empty_result_set`.
**Definition of Done:** suite passes and the designation-coverage decision is recorded.

### Step 2.6 — Material Disclosures Connector
**Tasks:** `SecEdgarConnector` over `https://efts.sec.gov/LATEST/search-index` and `https://data.sec.gov/submissions/CIK##########.json`. No key; **mandatory descriptive `User-Agent` with contact email as a named constant** (403 without). **5 req/s ceiling shared across every `*.sec.gov` host** — the SEC's 10 req/s limit is aggregate per IP, exceeding it blocks the IP for ~10 minutes, and retrying extends the block. `canonical_id = "edgar:<accession>"`; `published_date = acceptanceDateTime`. Treat the EFTS response shape as unstable: it is undocumented, with no published parameter list or schema commitment.
**Required Test Cases:** the Step 2.2 shape, plus:
- `test_user_agent_header_sent_on_every_request_including_retries`; `test_user_agent_is_a_named_constant`.
- `test_sec_hosts_share_one_rate_limit_bucket`.
- **Edge:** `test_8k_with_multiple_items_yields_expected_document_count`.
- **Edge:** `test_403_is_treated_as_a_block_and_backs_off_before_retrying`.
**Definition of Done:** suite passes.

### Step 2.7 — Deduplication and Amendment Precedence
**Tasks:** implement requirements §7.1 — archive always; dedup gates extraction and publish only; `content_sha256` within a document; **`dedup/canonical/{sha256(canonical_id)}.json` marker objects written after successful publish** for cross-source collapse `[P2-2]`. No embedding similarity. A skip is logged and counted, never an error.
**Required Test Cases:**
- `test_same_disclosure_from_two_sources_skips_the_second_extraction_via_the_canonical_marker` — **without the marker object there is no way to look up by canonical id (MinIO keys are organized by `external_id`), so every mirrored paper gets extracted twice at full LLM cost** `[P2-2]`.
- `test_unchanged_refetch_is_archived_but_not_re_extracted`.
- `test_changed_content_is_treated_as_an_amendment_and_republished`.
- **Edge:** `test_dedup_never_suppresses_the_minio_write`.
- **Edge:** `test_marker_written_only_after_successful_publish` — and `test_failed_marker_write_causes_at_most_one_redundant_extraction`, the documented, acceptable failure mode.
- **Edge:** `test_document_with_no_canonical_id_is_not_deduped_across_sources`.
- **Edge:** `test_duplicate_skip_does_not_fail_the_task`.
- `test_dedup_requires_no_state_outside_minio`.
**Definition of Done:** suite passes.

### Step 2.8 — Entity and Ticker Resolution
**Objective:** substitute the real `EntityNormalizer` for the Phase 1 identity implementation `[P2-11]`, and produce the tickers the REST endpoint is keyed on. Placed ahead of Phase 3 because without normalization corroboration silently misses matches, and because **no earlier step produces a ticker** — leave it later and the flagship endpoint returns empty for every real query while all tests stay green.
**Tasks:** gene/mechanism synonym normalization (HGNC symbols and aliases); company→ticker resolution seeded from `https://www.sec.gov/files/company_tickers.json`, with normalized-name matching and an explicit unresolved bucket. An unresolvable company is stored, corroborates by gene target, and simply does not appear under a ticker query.
**Required Test Cases:**
- **The entire Step 1.4 contract test class passes unmodified against the real normalizer** `[P2-11]`.
- `test_two_accepted_gene_names_resolve_to_one_entity_node`.
- **Edge:** `test_distinct_genes_with_similar_names_do_not_merge` — the false-positive guard, and the more dangerous failure.
- **Edge:** `test_case_and_hyphenation_variants_normalize`; `test_unknown_alias_falls_back_to_raw_name_without_error`.
- `test_company_name_resolves_to_ticker_from_the_sec_mapping`.
- **Edge:** `test_unresolvable_company_is_stored_and_still_corroborates_by_gene_target`.
- `test_normalization_runs_before_graph_write`.
- **Edge:** `test_changing_the_normalizer_rekeys_deliberately_and_does_not_silently_merge` — by this step the graph holds nodes written in Phase 1 and Steps 2.2–2.7, and a normalizer change alters their entity keys. Re-keying is a deliberate, scripted, tested operation with a recorded before/after node count — never a side effect of swapping the normalizer `[P2-11]`.
**Definition of Done:** suite passes and a live run produces at least one ticker-resolved corroboration from real data.

**Phase 2 exit criterion:** the full suite passes with all connectors on independent schedules, deduplicated, through the pipeline. **Frozen** — `SourceConnector`, `RawDocument`, `ResearchSignalEvent`, `IngestionPipeline`, `GraphUpdateService`, the REST layer. **Expected to change** — `sources.yaml` schema and `dag_factory` config plumbing, provided each change is generic and no `if source_type == ...` branch ever appears. A blanket "zero changes to `dag_factory`" would be unachievable the moment CPC filters, an NCBI key, and a mandatory User-Agent need somewhere to live.

---

## Phase 3 — Correlation Quality

### Step 3.1 — Confidence Scoring
**Tasks:** weight corroboration strength by source-type diversity and recency, not raw count; surface on the existing `CorroboratedSignal` and REST response; no parallel scoring field.
**Required Test Cases:**
- `test_three_source_types_score_higher_than_two`; `test_recent_corroboration_scores_higher_than_stale` (fixed clock).
- **Edge:** `test_score_never_leaves_0_1_range` — property-based over randomized inputs.
- **Edge:** `test_five_signals_one_source_type_score_below_two_signals_two_source_types`.
- `test_scoring_is_a_pure_function_of_its_inputs` — unit, no container.
**Definition of Done:** suite passes.

### Step 3.2 — Corroboration Quality Review
**Tasks:** sample 30 corroborations from real Phase 2 data; hand-classify as genuine, coincidental, or extraction error; record **corroboration precision** (a distinct figure from Step 2.0's extraction score) `[P2-14]`; feed errors back into the golden set.
**Required Test Cases:** `test_sampling_script_is_deterministic_given_a_seed`.
**Definition of Done:** the review exists and its precision figure is recorded. **If corroboration precision is below the threshold agreed in Step 1.7, fix extraction or normalization before Phase 4** — otherwise the backtest measures noise and the result is uninterpretable.

---

## Phase 4 — Signal Validation & Backtesting

### Step 4.0 — Historical Backfill (prerequisite) `[P2-1]`
**Objective:** produce a sample large enough for Phase 4 to mean anything. Forward-only collection at realistic signal density yields single-digit corroborations in a quarter; Step 4.4's metrics on that sample would be noise.
**Tasks:**
- A backfill runner reusing `IngestionPipeline.run(source_type, cursor)` with an explicit historical cursor. **It never writes the live cursor Variable.**
- Bounded scope: 24 months, sources that support date-ranged bulk queries (ClinicalTrials.gov, EPO OPS patents, EDGAR full-text, bioRxiv), run **one source at a time** under the same shared rate limiter.
- A pre-flight estimate — documents, LLM calls after pre-filtering, and cost — checked against the Step 1.7 budget before execution.
- Resumable: a checkpoint per (source, date window), so an interruption resumes rather than restarting.
**Required Test Cases:**
- `test_backfill_does_not_advance_the_live_cursor`.
- `test_backfill_is_resumable_from_its_checkpoint`.
- `test_backfill_respects_the_shared_rate_limiter` — a fake clock asserts the aggregate rate, not per-call delays.
- `test_backfill_dry_run_reports_document_and_call_estimates_without_calling_the_llm`.
- `test_backfill_aborts_when_the_estimate_exceeds_the_configured_budget`.
- **Edge:** `test_backfilled_document_reuses_an_existing_event_id_when_already_ingested_live`.
**Definition of Done:** suite passes; a dry run is recorded; the real backfill has completed for at least two source types and the resulting corroboration count is recorded in the README. **If that count is too small for the Phase 4 statistics to be meaningful, say so and stop here rather than producing a number that looks like a finding.**

### Step 4.1 — Price Data Ingestion
**Tasks:** a `/services/backtesting` module; `yfinance` for daily OHLCV via a **cached, rate-limited session**; **every fetched series written to Parquet in MinIO on first fetch and never re-fetched** — `YFRateLimitError` is a recurring IP-level block even at low rates, and Yahoo's terms contemplate personal use. Document **Stooq** as the named fallback.
**Required Test Cases:**
- `test_ohlcv_maps_to_storage_schema` against a fixture.
- `test_price_series_is_read_from_the_minio_snapshot_when_present` — the second run makes no network call.
- **Edge:** `test_missing_ticker_returns_empty_not_exception`; `test_delisted_ticker_partial_history_handled`; `test_price_dates_stored_utc`.
**Definition of Done:** suite passes and prices for a test ticker are stored.

### Step 4.2 — Point-in-Time Alignment
**Tasks:** join on `published_date` for signals and **`corroborated_at` for corroborations** — never `retrieved_at`, `ingested_at`, or `first_detected_at`. Reject any join attempting a non-public timestamp.
**Required Test Cases:**
- `test_signal_excluded_from_price_window_predating_disclosure`.
- `test_corroboration_aligns_to_corroborated_at_not_first_detected_at`.
- `test_superseded_corroboration_is_evaluated_with_its_own_participant_set_not_the_latest` `[P2-4]`.
- **Edge:** `test_patent_aligns_to_publication_date_not_filed_date` — 18-month gap in the fixture.
- **Edge:** `test_trial_aligns_to_post_date_not_submission_date`.
- **Edge:** `test_retrieved_at_far_later_than_published_date_uses_published_date`.
- **Edge:** `test_backfilled_document_does_not_leak_into_an_earlier_window`.
- **Edge:** `test_join_attempt_using_ingested_at_raises`.
- **Edge:** `test_signal_published_after_market_close_aligns_to_next_session`; `test_signal_on_market_holiday_aligns_to_next_trading_day`.
**Definition of Done:** suite passes.

### Step 4.3 — Backtesting Module
**Tasks:** test whether corroborated signals precede price moves and by how long; re-runnable from archived data only (MinIO snapshots plus price Parquet).
**Required Test Cases:**
- `test_backtest_runs_with_sockets_disabled` — `pytest-socket` (`--disable-socket --allow-unix-socket`); documented limit: it patches in-process sockets and will not catch a subprocess.
- `test_identical_inputs_produce_identical_output`.
- **Edge:** `test_no_corroborated_signals_produces_an_empty_report_not_a_crash`.
- **Edge:** `test_reextraction_from_archive_resolves_the_documented_snapshot` — implementable now that `raw_object_key` is on the event.
- **Edge:** `test_multiple_extractions_of_one_document_count_once` — the double-counting that follows from putting `schema_version` in `event_id`.
**Definition of Done:** suite passes and a run produces a report — even if the finding is "no significant effect" — using only archived data.

### Step 4.4 — Performance Metrics
**Tasks:** hit rate, average lead time, basic risk-adjusted stats.
**Required Test Cases:**
- `test_metrics_against_known_synthetic_series` — hand-computed expected values.
- **Edge:** `test_zero_signal_run_metrics_are_defined`; `test_single_observation_risk_stats_handled`.
- `test_sample_size_is_reported_alongside_every_metric` — a hit rate over six observations must be visibly a hit rate over six observations `[P2-1]`.
- `test_run_parameters_stored_with_results` — window size, source types, `prompt_version`, `prefilter_version`, `extraction_model`.
**Definition of Done:** suite passes.

---

## Phase 5 — Frontend & Usability

### Step 5.1 — Dashboard
**Tasks:** Next.js app visualizing the entity graph and recent corroborated signals.
**Required Test Cases:** `test_graph_renders_from_api_fixture`; `test_empty_state_renders`; `test_api_error_renders_error_state_not_blank_page`.
**Definition of Done:** suite passes and the dashboard renders live data from the existing API. If a genuine gap appears, extend `SignalController` — don't create a parallel API.

### Step 5.2 — Watchlist, Alerts, Health Reporting
**Tasks:** ticker/gene-target watchlist; Discord/Slack/email notification on new corroborated signals; **wire the §12 health reporter to the same transport** (DLT depth, per-source age-of-latest-signal).
**Required Test Cases:**
- `test_matching_signal_triggers_notification` (stubbed transport).
- **Edge:** `test_non_matching_signal_does_not_notify`.
- **Edge:** `test_same_corroboration_notifies_once` — including after a re-extraction changes `extraction_id` but not `event_id`.
- **Edge:** `test_supersession_notifies_once_about_the_new_evidence_not_again_about_the_old` `[P2-4]`.
- **Edge:** `test_notification_transport_failure_is_retried_then_logged`.
- `test_dlt_depth_above_threshold_notifies`.
**Definition of Done:** suite passes and a test watchlist entry triggers a real notification within one polling cycle.

### Step 5.3 — Auth (conditional)
Spring Security with JWT/OAuth2, **only if** the system moves beyond single-user local use. Do not implement speculatively.

---

## Phase 6 — Hardening & Scaling

### Step 6.1 — Kafka Partition Verification
**Tasks:** verify key distribution across the six partitions declared in Step 0.2. Six was chosen at creation precisely so this step is a check, not a change — altering partition count rehashes every key. If distribution is genuinely pathological, record the measurement in `DECISIONS.md` and stop; do not repartition without deciding it is worth losing per-key ordering.
**Required Test Cases:** `test_key_distribution_across_partitions`; **Edge:** `test_repartitioning_preserves_per_key_ordering` *(only if undertaken)*.

### Step 6.2 — Neo4j Indexing at Scale
**Tasks:** optimize traversal indexes as the graph grows. *(Constraint/index **existence** is tested in Step 1.3, where failure is caught immediately.)*
**Required Test Cases:** `test_ticker_query_uses_index_not_full_scan` (query plan, not wall clock); **Edge:** `test_p95_latency_within_threshold_at_scaled_node_count`.

### Step 6.3 — CI/CD Pipeline
**Tasks:** GitHub Actions running linting, both suites, the ArchUnit rules, the generated-fixture drift check, and container builds.
**Required Test Cases:**
- `test_pipeline_runs_testcontainers_suite` — the Java job actually starts containers, not silently skipping when Docker is unavailable.
- `test_no_test_is_skipped_silently`.
- `test_contract_fixture_is_current` — the tree is clean after `pytest`.
**Definition of Done:** checks pass on a real pull request; the deliberately-broken-PR verification has been done once by hand and recorded.

### Step 6.4 — Kafka Streams Correlation (conditional)
**Precondition:** the scheduled query is *measurably* inadequate — record the latency or cost measurement. Absent that, do not build this.
**Tasks:** a topology keyed by normalized entity emitting `CorroboratedSignal` on 2+ distinct source types; swap the `CorroborationService` binding by profile.
**Required Test Cases:**
- **The entire Step 1.4 contract test class runs unmodified against the new implementation and passes.** Any test needing an edit indicates a leaked implementation detail — fix the interface.
- `test_topology_with_topologytestdriver`; **Edge:** `test_out_of_order_event_within_window_still_corroborates`; `test_late_arrival_past_grace_period_is_handled_per_documented_policy`; `test_state_store_survives_restart`; `test_duplicate_event_id_does_not_double_count`.
- `test_step_1_5_rest_suite_passes_unmodified_under_the_streams_profile` — **not a byte-identical source-file diff: that fails on a reformat and passes against a completely broken implementation.**
**Open risks to resolve first:** (1) Streams windows advance on *stream time*, so replaying history behaves differently depending on whether live and historical records interleave — the pairwise semantics in requirements §4 are straightforward in Cypher and are not in a windowed store. (2) The supersession semantics in §4.1 have no natural expression in a windowed aggregation. Verify both before committing.

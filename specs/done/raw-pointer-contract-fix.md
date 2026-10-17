# Raw pointer contract fix

**Status:** done
**Branch:** `feature/raw-pointer-contract-fix`

---

## Context

The scraper publishes a *raw pointer* to `auspex.raw.ingested`, and core-hub turns each pointer into one `raw_fetch_audit` row. Today the two sides disagree on the payload, and the producer sends pointers for too few documents. The owner settled the contract in `## 2026-10-17 — Living docs — CHOICE — raw-pointer contract` (option A): **a pointer for every archived document, carrying `retrieved_at`.** Defect C1 in `## 2026-10-15 — Living docs — PENDING — defects found while scoping` requires this fix before the first stack run (`## 2026-10-17 — Living docs — CHOICE — defects found while scoping`).

**What is wrong today:**
- **Field.** `RawAuditService.record` (`services/core-hub/src/main/java/dev/auspex/corehub/audit/RawAuditService.java:47`) reads `ingested_at`. The producer sends `retrieved_at`, so `node.get("ingested_at")` is null and `.asText()` throws a `NullPointerException`.
  - That exception is retryable under `rawErrorHandler` (`services/core-hub/src/main/java/dev/auspex/corehub/config/KafkaConfig.java:139`). Every pointer would be retried through the back-off and then dead-lettered.
  - `RawAuditIT` and `SignalPersistenceIT` stay green because they publish a hand-written payload, `TestFixtures.validRawJson()` (`services/core-hub/src/integrationTest/java/dev/auspex/corehub/TestFixtures.java:69`), which carries `ingested_at`.
- **Scope.** `IngestionPipeline.run` (`services/ingestion-scraper/src/auspex_ingest/pipeline.py`) calls `publish_raw` only after extraction returns a signal above the threshold. That is right next to `publish_signal`, so documents that are prefiltered out, not a signal, or below the threshold get no pointer.
  - Requirements §2 describes the pointer as published before extraction runs ("impossible for the pointer event (published before extraction has run)").
  - `raw_fetch_audit` is documented as "Every document fetched, regardless of signal outcome" (`services/core-hub/README.md:30`).
  - The scraper README's pipeline stages say `auspex.raw.ingested (all)`.

**What already matches:**
- **Producer payload.** `KafkaProducerClient.publish_raw` (`services/ingestion-scraper/src/auspex_ingest/messaging/kafka_producer.py:18`) sends `RawDocument.model_dump_json()` plus `raw_object_key`, keyed on `external_id`, with a `schema_version` header.
  - `RawDocument` (`services/ingestion-scraper/src/auspex_ingest/models.py:12`) excludes `raw_content` from the dump.
  - It carries `schema_version`, `external_id`, `canonical_id`, `source_type`, `source_url`, `published_date`, `content_sha256` and `retrieved_at`, which covers every field §2 lists.
- **Audit table.** `raw_fetch_audit` (Flyway `V1__signal_schema.sql`) already names its column `retrieved_at`, with primary key `raw_object_key`. It needs no migration.
- **Archive key.** `MinioArchive.put` (`services/ingestion-scraper/src/auspex_ingest/storage/minio_client.py:31`) returns `(key, is_new)`. Because the key embeds `retrieved_at`, each fetch normally writes a new object, and `is_new` is false only when the same object already exists.

## What this builds

1. **Every archived document gets a pointer.** Right after `self._archive.put(doc)` returns `is_new = True`, before the unchanged-re-fetch check, the prefilter, the canonical check and extraction, the pipeline calls `self._producer.publish_raw(doc, key, doc.schema_version)`.
   - Remove the later `publish_raw` call that sits next to `publish_signal`.
   - A document whose archive object already existed (`is_new = False`) gets no new pointer: its pointer was sent when the object was first written.
   - A `publish_raw` that raises fails the document like any other step. It counts in `failed`, the cursor does not pass it, and nothing after it runs for that document.
   - Delivery is confirmed by the existing end-of-run `flush()`, as for signals.
2. **core-hub reads `retrieved_at`.** `RawAuditService.record` takes `retrieved_at` as the audit row's `retrieved_at`.
   - A pointer missing any of `raw_object_key`, `source_type`, `external_id` or `retrieved_at`, or whose `retrieved_at` has no offset, raises a new `InvalidRawPointerException`. It no longer produces a `NullPointerException` or a `DateTimeParseException`.
   - `rawErrorHandler` registers that exception as not retryable, so a malformed pointer goes straight to `auspex.raw.ingested.dlt` with the standard DLT headers instead of spending the back-off.
   - The `content_sha256` fallback (hashing the payload when the field is absent) is removed. The field is required like the other four, because the producer always sends it and a hash of the pointer JSON is not the content hash.
3. **A generated pointer contract fixture.** A pytest writes `services/core-hub/src/test/resources/contract/raw_pointer_v1.json` from the real `KafkaProducerClient.publish_raw` output, captured through a fake confluent producer. This mirrors the signal fixture (Invariant 7: the fixture is generated, not hand-written).
   - A Java unit test feeds that file to `RawAuditService`.
   - `TestFixtures.validRawJson()` returns the generated file's contents, so `RawAuditIT` and `SignalPersistenceIT` publish exactly what the scraper publishes.
4. **Docs.**
   - `services/ingestion-scraper/README.md` pipeline stages: the raw pointer moves to its own stage right after the archive (all archived documents), and stage 8 publishes signals only.
   - `services/core-hub/README.md`: one line under the raw audit saying that a malformed pointer dead-letters without retries.

## Out of scope

- **Bucket name.** §2 says "bucket/key". The pointer carries only the key, and the bucket stays the configured `auspex-raw`. Adding a `raw_bucket` field would be a wire change with no consumer.
- **Observations.** Recording an observation when a canonical id first published by another source is fetched again (requirements §7.1.5) is a separate divergence.
- **Schema change.** No change to `raw_fetch_audit` or any Flyway script, and no change to the `schema_version` value.
- **Living docs.** The living-docs specs (`specs/living-docs-*.md`) are not edited here. Their writers read the code when they run, see Notes.

## Constraints

- **Invariant 13.** The archive write stays the first side effect. The pointer is published only after `put` returns, and never for a document whose `put` raised.
- **Invariant 11.** Nothing dies silently. A malformed pointer reaches the DLT with headers, and it never blocks the partition through retries.
- **Invariant 10.** The audit stays idempotent on `raw_object_key` (`ON CONFLICT DO NOTHING`).
- **Invariant 7.** The pointer fixture is generated by pytest; snake_case on the wire.
- **Invariants 1 and 2.** The scraper writes only MinIO and Kafka, and core-hub is the only Postgres writer. Nothing here changes either.
- **Invariant 9.** `retrieved_at` is UTC on the wire.
- **Async `produce()`.** `confluent-kafka` `produce()` is asynchronous (root `CLAUDE.md` known traps). More pointers per run go through the same end-of-run `flush()`, and a failed flush still clears `completed`.
- **Ordering of the pointer.** It is published before the processed-marker check, so a re-fetch whose content was already processed still gets its pointer. The audit row records the fetch; the marker only spares the extraction.

## Required tests

Write these first and confirm each fails for the right reason: an `AssertionError`, `FileNotFoundError` or `ImportError` on the Python side, and an assertion failure or a missing-class compile error on the Java side.

**Python** (`services/ingestion-scraper/tests/unit/test_raw_pointer_contract.py`):
- `test_raw_pointer_published_for_every_archived_document`: four new documents go through the pipeline. One is prefiltered out, one is not a signal, one is below the threshold and one is a signal. Exactly four pointers are published, one per `external_id`, and one signal.
- `test_raw_pointer_published_before_extraction`: the call order is archive, then `publish_raw`, then extract for a document that reaches extraction.
- `test_raw_pointer_not_republished_for_existing_archive_object`: an archive whose `put` returns `is_new = False` produces no pointer.
- `test_raw_pointer_publish_failure_fails_the_document`: `publish_raw` raises for one document. `result.failed` is 1, the extractor was not called for it, and `next_cursor` is not past its `published_date`.
- `test_raw_pointer_payload_carries_contract_fields_and_no_content`: the bytes `KafkaProducerClient.publish_raw` hands to a fake confluent producer parse to JSON.
  - It has `raw_object_key`, `external_id`, `canonical_id`, `source_type`, `source_url`, `retrieved_at`, `content_sha256` and `schema_version`, and no `raw_content`.
  - `retrieved_at` parses as a UTC-aware datetime, and the message key is `external_id`.
- `test_raw_pointer_contract_fixture_is_generated`: writes `raw_pointer_v1.json` from that payload and asserts the committed file equals what was just generated. It fails if anyone hand-edits the file without regenerating it.

**Java unit** (`services/core-hub/src/test/java/dev/auspex/corehub/audit/RawAuditServiceTest.java`, mocked `JdbcTemplate`):
- `test_generated_raw_pointer_records_audit_row_with_retrieved_at`: reads `contract/raw_pointer_v1.json` and calls `record`. It verifies one insert with the fixture's `raw_object_key`, `source_type`, `external_id` and `content_sha256`, and an `OffsetDateTime` equal to its `retrieved_at`.
- `test_raw_pointer_missing_retrieved_at_is_invalid`: the fixture with `retrieved_at` removed throws `InvalidRawPointerException`, not a `NullPointerException`, and nothing is inserted.
- `test_raw_pointer_without_offset_is_invalid`: `retrieved_at` of `2024-06-15T12:00:00` (no offset) throws `InvalidRawPointerException`.

**Java unit** (`services/core-hub/src/test/java/dev/auspex/corehub/config/KafkaRetryTest.java`):
- `invalidRawPointerGoesToTheDltWithoutRetry`: the real `rawErrorHandler` recovers a listener failure caused by `InvalidRawPointerException` on the first delivery. It lets the not-retryable registration be mutation-checked without containers.

**Changed Python test** (`services/ingestion-scraper/tests/unit/test_unchanged_refetch.py`): the unchanged re-fetch test now expects one raw pointer and no signal (renamed `..._skips_extraction_and_signal_publish`), per "Ordering of the pointer" above.

**Java integration** (`services/core-hub/src/integrationTest/java/dev/auspex/corehub/RawAuditIT.java`):
- `test_raw_listener_writes_audit_row_only`: keeps its assertions, but `validRawJson()` now returns the generated fixture. It also asserts that the row's `retrieved_at` equals the fixture's.
- `test_invalid_raw_pointer_dead_letters_without_retry`: a pointer without `retrieved_at` appears on `auspex.raw.ingested.dlt` with the `kafka_dlt-exception-cause-fqcn` header naming `InvalidRawPointerException` (the container wraps the listener's exception in `ListenerExecutionFailedException`, which `kafka_dlt-exception-fqcn` names). It is delivered once, with no retry attempts: the IT spies on `RawAuditService` and verifies one `record` call, since retries all happen before the DLT publish. No audit row is written.

## Definition of done

```bash
cd services/ingestion-scraper && uv run pytest tests/unit/test_raw_pointer_contract.py -q --strict-markers \
  && uv run pytest tests/unit -q --strict-markers && uv run ruff check . && uv run mypy src
cd ../core-hub && ./gradlew test --rerun-tasks --tests '*RawAuditServiceTest' && ./gradlew test --rerun-tasks
```

**Expected:**
- 6 passed in the new Python file, and the full unit suite is green.
- 3 Java unit tests in `RawAuditServiceTest`, 1 more in `KafkaRetryTest`, and the Java unit suite is green.
- `./gradlew integrationTest` with `RawAuditIT` (2 tests) and `SignalPersistenceIT` green is proven in CI. Cloud sessions have no Docker, so the PR says so.

**Mutation-check, and list each in the PR:**
- Read `ingested_at` again in `RawAuditService` → the generated-fixture unit test and `RawAuditIT` go red.
- Move `publish_raw` back after extraction → the every-document and ordering tests go red.
- Drop the `is_new` guard → the existing-object test goes red.
- Drop the not-retryable registration → `invalidRawPointerGoesToTheDltWithoutRetry` and the dead-letter IT go red.
- Hand-edit `raw_pointer_v1.json` → the fixture test goes red.

## Notes

- **Volume.** Pointers now go out per fetched-and-archived document instead of per signal. `auspex.raw.ingested` keeps 7-day retention, and `raw_fetch_audit` grows by one row per archive object. That is what its README line already says.
- **Interaction with the living docs.** If this merges before the living-docs rollout, the writers of `docs/system/contracts.md` and `docs/core-hub/consumption.md` find the code matching the approved contract and record CON-001/002 and the audit requirement as `tested` instead of `divergent`. Their specs tell them to verify against the code, so no edit is needed here.
- **`SignalPersistenceIT`** publishes the raw pointer twice to show the audit is idempotent. It keeps doing so with the generated fixture.

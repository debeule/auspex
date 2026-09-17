# Re-extraction CLI

**Status:** ready
**Blocked by:** —
**Branch:** `feature/reextraction-cli`

---

## Context

When a prompt, pre-filter vocabulary, or extraction model changes, historical documents in MinIO need to be re-extracted under the new versions. Without this, the corpus ends up split: some signals extracted with the old prompt, some with the new, with no marker recording the boundary. `requirements.md §10.4` makes re-extraction an explicit, operator-invoked operation.

What already exists:

- `LLMExtractor` in `src/auspex_ingest/extractor.py` — takes a `RawDocument`, returns `ResearchSignalEvent | None`. Parameterised on `prompt_version`, `model`, `schema_version`, and `prefilter_version`.
- `MinioArchive` in `src/auspex_ingest/storage/minio_client.py` — stores documents under `raw/{source_type}/{external_id}/{timestamp}-{sha256[:8]}.json`. The archived JSON includes `raw_content` (added back by `put()` since the field is excluded from Pydantic serialization).
- `KafkaProducerClient` in `src/auspex_ingest/kafka_producer.py` — `publish_signal()` writes to `auspex.signals.extracted`.
- `identity.py` — `compute_event_id()` and `compute_extraction_id()` are deterministic; same inputs → same id.
- `Prefilter` in `src/auspex_ingest/prefilter.py` — can be bypassed if the document already passed the pre-filter during original ingestion.
- `scripts/run_pipeline.py` — the pattern to follow for a standalone CLI script that wires together `auspex_ingest` components.

Core-hub's `SignalListener` already handles idempotent upserts: re-publishing under the same `event_id` updates `signal_current` and appends to `signal_extraction_history`. Corroboration re-runs automatically because re-extracted signals carry a fresh `ingested_at`, which advances past the `corroboration_watermark` on the next scheduled corroboration run.

## What this builds

A CLI at `scripts/reextract.py` and a testable `ReextractionRunner` class in `src/auspex_ingest/reextract.py` that:

1. Lists MinIO objects under `raw/` (optionally filtered by `--source-type`).
2. For each object, reads the archived JSON and reconstructs the `RawDocument` including `raw_content`.
3. Optionally filters by `--since` / `--until` on `published_date`.
4. Runs `LLMExtractor.extract()` with the operator-specified `--prompt-version`, `--model`, and `--schema-version`.
5. Publishes each resulting `ResearchSignalEvent` to `auspex.signals.extracted`.
6. In `--dry-run` mode: counts MinIO objects that match the filters and reports the estimated cost without calling the LLM or publishing anything.
7. Reports final counts: `scanned`, `skipped_by_filter`, `not_signal`, `published`, `failed`.

`MinioArchive` gains a `list_raw_keys(source_type_prefix: str | None) -> Iterator[str]` method to list archived document keys. This is the only change to existing code.

## Out of scope

- Does not modify the live Airflow cursor Variable.
- Does not re-archive to MinIO — the document is already there.
- Does not trigger corroboration directly — the scheduled corroboration job picks up re-extracted signals naturally via `ingested_at` advancement.
- Does not handle schema migrations or data model changes — re-extraction only re-runs the LLM against the existing `raw_content`.
- No backfill of new source types — re-extraction is over documents already in MinIO.

## Constraints

- **Invariant 1**: `ReextractionRunner` writes only to Kafka. No Postgres, no Neo4j, no Airflow Variables, no cursor files.
- **`event_id` is stable across re-extraction.** `compute_event_id(doc.canonical_id, doc.source_type, doc.external_id)` is deterministic. A re-extraction of the same document must produce the same `event_id` regardless of prompt version or model. This is how core-hub knows to upsert rather than insert.
- **`extraction_id` changes when any version changes.** `compute_extraction_id(event_id, schema_version, prompt_version, prefilter_version, model)` is deterministic; changing any input produces a distinct id. Core-hub appends the new id to `signal_extraction_history`.
- **`--dry-run` must not call the LLM and must not publish.** It may read from MinIO to count matching documents.
- The pre-filter runs during re-extraction by default with the version specified via `--prefilter-version`. It can be skipped with `--skip-prefilter` only when the operator explicitly accepts that some originally-filtered documents may now pass — this must be documented in the CLI help text.
- Re-extraction is never invoked from `IngestionPipeline.run()`. The two paths are independent; crossing them would re-extract on every routine fetch.
- `confluent-kafka` `produce()` is async — `flush()` and check delivery reports (same obligation as in `KafkaProducerClient`).

## Required tests

**Unit (`tests/unit/test_reextract.py`):**

- `test_raw_document_reconstructed_from_archived_json` — `ReextractionRunner` reads MinIO JSON and passes a valid `RawDocument` (with `raw_content`) to the extractor; no connector is involved.
- `test_event_id_stable_across_prompt_version_change` — re-extracting the same archived document with a different `prompt_version` produces the same `event_id`.
- `test_extraction_id_changes_on_prompt_version_change` — re-extracting with a different `prompt_version` produces a different `extraction_id`.
- `test_publishes_to_signals_extracted_topic` — when LLM returns a signal, `publish_signal()` is called with the event; `flush()` is called after.
- `test_dry_run_does_not_call_llm_or_publish` — with `dry_run=True`, the extractor and producer are never called.
- `test_dry_run_returns_estimated_document_count` — `dry_run=True` returns the number of MinIO objects matching the filters without extracting.
- `test_source_type_filter_restricts_listed_keys` — `source_type="biorxiv"` causes `list_raw_keys("biorxiv")` to be called; objects from other source types are not processed.
- `test_since_filter_excludes_documents_before_date` — a document with `published_date` before `--since` is skipped; `skipped_by_filter` counter increments.
- `test_until_filter_excludes_documents_after_date` — symmetric.
- `test_non_signal_document_increments_not_signal_counter` — when LLM returns `None`, `not_signal` increments and nothing is published.
- `test_per_document_failure_does_not_abort_run` — a document that raises during extraction increments `failed` and the run continues to the next document.
- `test_runner_never_writes_to_airflow_or_cursor` — no calls to Airflow Variables, no MinIO writes outside of what `list_raw_keys` reads, no local state files written.

**Integration (`tests/integration/test_reextract_integration.py`):**

- `test_reextraction_round_trip_publishes_valid_signal` — archives a real document to a MinIO testcontainer, runs re-extraction against it with a stubbed LLM, confirms the published `ResearchSignalEvent` is valid and carries the expected `event_id`.

## Definition of done

```bash
cd services/ingestion-scraper && uv run pytest tests/unit/test_reextract.py tests/integration/test_reextract_integration.py -v -m "unit or integration"
```

Expected: all tests pass.

```bash
uv run python scripts/reextract.py --help
```

Expected: usage is printed showing `--source-type`, `--since`, `--until`, `--prompt-version`, `--model`, `--schema-version`, `--prefilter-version`, `--skip-prefilter`, `--dry-run`.

## Notes

- The archived JSON includes `raw_content` because `minio_client.py:put()` manually includes it (`{**json.loads(doc.model_dump_json()), "raw_content": doc.raw_content}`). The `RawDocument` Pydantic model excludes it via `Field(exclude=True)` to avoid logging it — so reconstruction must use `model_validate(json_data)` after manually pulling `raw_content` back out. Verify this in the first red test.
- MinIO listing is paginated via `list_objects(recursive=True)`. For large archives this will be slow — the CLI should print progress. A future optimisation (out of scope here) would be a MinIO object-key index in Postgres.
- The gene vocabulary (`gene_vocab` in `LLMExtractor`) may have changed between the original extraction and re-extraction. The CLI should accept an optional `--gene-vocab-file` pointing to a newline-delimited HGNC symbol list. If omitted, the vocabulary filter is not applied (same as passing `gene_vocab=None`).
- `--dry-run` is the right first command to run before a large batch to estimate LLM cost: `scanned` × average tokens per document × model price.

# Structured Source Extraction

**Status:** hold
**Hold reason (2026-10-07 edge research):** its only consumers (the Form 4 and offering connectors) are on hold. Comes off hold with either of them. `DECISIONS.md` 2026-10-07 "ownership and insider data are snapshots, not connectors".
**Blocked by:**
1. Company-level event extraction (in progress, first wave) — `ResearchSignalEvent` must carry the event type and company identifiers that a structured mapper fills in.

**Branch:** `feature/structured-source-extraction`

---

## Context

Every document today goes through one path (requirements §6.2): **pre-filter → dedup → MinIO archive → extract → publish**, where extract is an LLM call through the registry-driven extractor (`LLMExtractorFactory`), and the pre-filter requires a term from the source's `prefilter_vocabulary` (gene symbols, modalities).

The 2026-10-07 edge feasibility audit (row 9) asks for cheap company-level sources: Form 4 insider buys, equity offerings, short interest, and catalyst dates. Form 4 and offering filings are structured: the facts a trade needs (transaction code, shares, price, form type, filer) are fields in the document, not prose. Sending them through the LLM would cost one local-model call each (10 to 15 s on the backfill machine), add extraction error to data that has none, and fail the gene-vocabulary pre-filter anyway.

The connector and pipeline shape is fixed by invariants: a new source is a `SourceConnector` plus a `sources.yaml` entry, with no `if source_type == ...` in shared code (Invariant 4), and `fetch_since()` only fetches and maps (Invariant 3).

## What this builds

1. **`sources.yaml` field `extraction`**: `llm` (default, today's behaviour) or `structured`. A source with `extraction: structured` names a mapper: `structured_mapper: insider_transactions`.
2. **`StructuredMapper` ABC** in `auspex_ingest/extraction/structured.py`: `map(raw: RawDocument) -> ExtractionOutcome`, returning the same outcome types the LLM path returns (signal or `not_signal`), so dedup, publish, `RunResult` counting and DLT handling are unchanged. Mappers are looked up in a registry by name; the pipeline chooses LLM or mapper from the source's config, never from its `source_type`.
3. **Extraction identity for structured events**: `extraction_model = "structured:<mapper name>"`, `prompt_version = "<mapper version>"`, `prefilter_version = "none"`. `extraction_id` changes when the mapper version changes; `event_id` never does (Invariant 14).
4. **Pre-filter per source**: `prefilter: vocabulary` (default) or `prefilter: issuer_scope`, which admits documents whose issuer CIK is in `config/universe/backfill_scope.yaml` (or a configured CIK list until the point-in-time universe lands). `prefiltered_out` is still counted.
5. **Lineage rule amended**: the historical-backfill single-lineage check ("exactly one `extraction_model`") applies to LLM-extracted rows. Structured rows are checked separately: one mapper version per source in the backfill window.

## Out of scope

- Any concrete connector (Form 4, offerings, and the others have their own specs).
- Changing the LLM path, prompt, or registry.
- New Kafka topics: structured events are `ResearchSignalEvent`s on `auspex.signals.extracted` like every other signal, with the raw pointer on `auspex.raw.ingested` as today.

## Constraints

- Invariants 1, 3, 4, 13: archive first and unconditionally; the mapper runs where the LLM call runs today; selection by config.
- Invariant 7: no schema change here; mappers fill fields the company-level extraction spec defines. If a field is missing, stop and flag rather than adding it in this spec.
- Invariant 8: synchronous.
- Invariant 10: dedup and `canonical_id` markers behave identically for both paths.

## Required tests

In `services/ingestion-scraper/tests/unit/test_structured_extraction.py`:
- `test_structured_source_does_not_call_the_llm`
- `test_structured_mapper_is_selected_by_config_not_source_type` — two sources with different `source_type`s and the same mapper name both use it
- `test_unknown_structured_mapper_name_fails_at_startup`
- `test_structured_event_records_mapper_name_and_version_as_extraction_identity`
- `test_structured_document_is_archived_before_mapping` — mapper raises; archive object exists; failure counted
- `test_issuer_scope_prefilter_admits_only_in_scope_ciks`
- `test_mapper_version_change_keeps_event_id_and_changes_extraction_id`
- `test_llm_sources_are_unaffected_by_the_extraction_field_default`
- `test_structured_not_signal_is_counted_in_run_result_like_llm_not_signal`
- `test_vocabulary_prefilter_remains_the_default`

## Definition of done

```bash
cd services/ingestion-scraper && uv run pytest tests/unit/test_structured_extraction.py -q --strict-markers && uv run pytest tests/unit -q && uv run ruff check . && uv run mypy src
```

Expected: 10 new tests pass; full unit suite green with a non-zero count.

Then: `services/ingestion-scraper/README.md` pipeline stages and `sources.yaml` schema table list `extraction`, `structured_mapper` and `prefilter`; `docs/requirements.md` §6.2 and §6.6 state the structured path and the issuer-scope pre-filter; the lineage amendment recorded in `DECISIONS.md` and reflected in `specs/historical-backfill.md`.

## Notes

- This is a requirements change to §6.2 (one extraction path) and §6.6 (vocabulary pre-filter before every LLM call). The structured path makes no LLM call, so §6.6's cost rationale does not apply, but the text must say so before the tests are written.

# Lineage Trace View

**Status:** blocked
**Blocked by:** `specs/signal-browse-views.md` (signal, corroboration and company views the trace links into) and `specs/done/graph-and-connector-wiring-fixes.md`.
**Branch:** `feature/lineage-trace-view`

---

## Context

Decided 2026-10-08: the dashboard must show how a conclusion was reached: this document produced this signal, which was linked to these others because they share this entity, giving this corroboration and score. The chain must be strategy-agnostic. Decisions and P&L join it later through `specs/research-results-view.md`.

What is stored today, joinable on `raw_object_key` and `event_id`:
- MinIO `auspex-raw`: the archived raw document, key `raw/{source_type}/{external_id}/{retrieved_at}Z-{sha8}.json`. The scraper's `MinioArchive.get_raw` reads it.
- Postgres `raw_fetch_audit` (key, source, external id, content hash, `retrieved_at`, `recorded_at`).
- `signal_current` and the append-only `signal_extraction_history`, with `extraction_id`, `schema_version`, `prompt_version`, `prefilter_version`, `extraction_model` (registry id with digest) and `recorded_at`.
- `source_observation`: every source and raw key that saw the same `event_id`.
- `corroboration`: participants, `distinct_source_count`, `corroborated_at`, `first_detected_at`, `superseded_by`.

What is missing:
- No endpoint fetches by `event_id`, `raw_object_key` or corroboration key, and none serves the raw document or extraction history.
- **Why** a corroboration formed is not stored: which entity the participants share, which signal triggered the scan, the window applied, the gaps between publication dates. Entities skipped by the degree cap (§4.2) are dropped silently.
- `CorroborationScorer.score` reads the wall clock, so the same corroboration scores differently on different days and a past score can't be reproduced.

## What this builds

1. **Corroboration evidence**, written by core-hub in the same transaction as each new corroboration row (next free Flyway version): `corroboration_evidence(entity_key, participants_hash, shared_entity_name, shared_entity_label, trigger_event_id, window_days, scan_started_at, pair_gaps jsonb)`, where `pair_gaps` lists each participant pair's publication-date gap in days. Plus `corroboration_degree_skip(entity_key, degree, cap, scan_started_at)` for every entity the cap skips. Both append-only.
2. **Reproducible score:** `CorroborationScorer.score(distinctSources, corroboratedAt, asOf)`. Responses give the score at `corroborated_at` and at the request time, each with its parts.
3. **core-hub lineage endpoints:**
   - `GET /api/v1/lineage/signals/{event_id}`: current signal, every extraction in history (versions, model, `recorded_at`), source observations with their raw keys and audit rows, and the non-superseded corroborations it belongs to.
   - `GET /api/v1/lineage/corroborations/{entity_key}/{participants_hash}`: participants (with their lineage summaries), evidence, the supersession chain both ways, and the two scores.
   - `GET /api/v1/lineage/raw?key=`: the audit row for a raw key and the `event_id`s it produced.
4. **Raw document read:** scraper `GET /raw?key=` returns the archived document. Read-only; the key must match the archive key pattern.
5. **Dashboard `/trace`:** `/trace/signal/[event_id]` and `/trace/corroboration/[entity_key]/[participants_hash]` render the chain top to bottom: raw document (expandable text, source link, retrieved time) → extraction (model, prompt, schema, prefilter versions, every re-extraction) → signal → corroboration (shared entity, trigger, window, date gaps, score then and now, superseded by). A "Decisions" section at the end shows "No strategy decisions recorded" until the results view fills it. Every signal and corroboration row in the browse views links here.

## Out of scope

- Strategy decisions, fills and P&L in the chain (`specs/research-results-view.md`).
- Persisting score history beyond the reproducible `asOf` computation.
- Changing what corroborates (window, cap, kinds).

## Constraints

- Invariant 2: core-hub writes the evidence tables; the scraper's `/raw` only reads MinIO.
- Invariant 5: evidence is written inside the existing `CorroborationService` implementation; `CorroborationServiceContractTest` passes unmodified.
- Invariant 10 and §3.7: evidence is keyed by the corroboration's natural key `(entity_key, participants_hash)`, `DO NOTHING` on conflict.
- Invariant 12: lineage endpoints bind every parameter; `event_id` must parse as a UUID; `entity_key` and `participants_hash` are validated against their formats; the raw key against the archive pattern (no path traversal).
- §4.1: the trace may show superseded corroborations, labelled as superseded, because it explains history. The browse views still exclude them.
- Invariant 9: all times UTC.

## Required tests

core-hub, `src/integrationTest/java/.../corroboration/CorroborationEvidenceIT.java`:
- `newCorroborationWritesEvidenceWithSharedEntityTriggerWindowAndGaps`
- `evidenceIsWrittenInTheSameTransactionAsTheCorroboration` (a failure injected after the corroboration insert leaves neither row)
- `rescanDoesNotDuplicateEvidence`
- `degreeCapSkipIsRecorded`

core-hub, `src/test/java/.../corroboration/CorroborationScorerTest.java`:
- `scoreAtAGivenAsOfIsIndependentOfTheClock`
- `scoreAtCorroboratedAtMatchesScoreWithClockFixedThere`

core-hub, `src/integrationTest/java/.../lineage/LineageIT.java`:
- `signalLineageListsEveryExtractionAndObservation`
- `signalLineageListsOnlyNonSupersededCorroborations`
- `corroborationLineageShowsSupersessionChainBothWays`
- `corroborationLineageReturnsScoreThenAndNowWithParts`
- `rawKeyLineageReturnsAuditRowAndProducedEventIds`
- `malformedEventIdOrKeyReturns400`

ingestion-scraper, `tests/unit/test_raw_read_api.py`:
- `test_raw_endpoint_returns_archived_document`
- `test_raw_endpoint_rejects_keys_outside_the_archive_pattern`
- `test_raw_endpoint_returns_404_for_missing_key`

Dashboard (Vitest), `Trace.test.tsx`:
- `test_signal_trace_renders_raw_extraction_signal_and_corroboration_in_order`
- `test_corroboration_trace_shows_evidence_and_both_scores`
- `test_superseded_corroboration_is_labelled_and_links_to_its_successor`
- `test_decisions_section_shows_empty_state`
- `test_browse_rows_link_to_their_trace`

## Definition of done

```bash
cd services/core-hub && ./gradlew test integrationTest --rerun-tasks
cd services/ingestion-scraper && uv run pytest tests/unit/test_raw_read_api.py -q --strict-markers
cd services/dashboard && npm run lint && npx tsc --noEmit && npm run test:ci && npm run build
```

Expected: all green, including the 12 Java, 3 scraper and 5 dashboard tests above; `CorroborationServiceContractTest` unmodified and passing.

Then on the stack: open a corroboration's trace and follow it from the corroboration to each participant's raw document.

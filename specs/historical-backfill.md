# Historical Backfill

**Status:** blocked
**Blocked by:**
1. Budget approval — run the dry run first, get sign-off before execution. See `docs/PREREQUISITES.md`.
2. Local model selection — `model-evaluation` spec must pass a local candidate at ≥0.85 precision and its gate record must be written before the backfill can run. Chosen model recorded in DECISIONS.md `2026-09-19 CHOICE`.
3. `extraction-backend` spec must be done first: the cutoff guard reads the model registry, the gate record check runs at startup, and the lineage report requires pinned `extraction_model` values in `signal_extraction_history`.
4. `model-evaluation` spec must be done first: dry-run wall-clock estimate for local backends reads the latency record from `evaluate_model.py`.
5. `golden-set-expansion` spec must be done first: gate records for the chosen model on the expanded (multi-gene-target) golden set must exist before running at scale.

**Recommended before starting (not a hard blocker but significantly affects signal yield):** `edgar-content-fix` spec — without it, EDGAR 8-K documents in the backfill window will produce metadata-only `raw_content` and no extractable signals (8 of 13 Phase 2 FNs were this failure mode).

**Branch:** `feature/historical-backfill`

---

## Context

Forward-only collection at realistic biotech signal density yields single-digit corroborations per quarter — not enough for Phase 4 to produce meaningful statistics. This spec produces the sample. It reuses `IngestionPipeline.run(source_type, cursor)` with an explicit historical cursor; no new pipeline logic.

**Patent connector status**: HISTORY.md shows the patent connector blocked at Phase 2 exit (EPO OPS credentials pending). TODO.md confirms it was completed as a separate spec afterward: 10 tests, live DOCDB confirmed, credentials configured. EPO OPS is in scope.

**Sources in scope** (all support date-ranged bulk queries):
- ClinicalTrials.gov
- EPO OPS patents
- EDGAR full-text
- bioRxiv
- PubMed

FDA is not included: low event density for the 8 watched companies over 24 months, and the daily quota constraint makes bulk queries slow.

**Lineage constraint**: the whole backtest corpus must come from one model. Documents already extracted live (under `gpt-4o-mini` or any subsequent model) are skipped by content-hash dedup (§7.1) on re-fetch. If the backfill model differs from those live extractions, the corpus is silently mixed. The overlap must be re-extracted under the backfill model via the reextraction-cli (§10.4) before the backtest runs. The dry run reports how many in-window documents are already extracted and under which model identifiers.

**Local test-period extractions**: if live extraction has run under a local model during the test period, those events carry the local model's pinned identifier. They may be part of the backfill corpus only if the local model is also the chosen backfill model (same registry entry, same prompt and prefilter versions). Otherwise they must be excluded from the backtest corpus via re-extraction under the backfill model.

## What this builds

`scripts/run_backfill.py`:
- Accepts `--source-type`, `--start-date`, `--end-date`, `--margin-months` (default 3).
- **Cutoff guard** (in the runner, not the pipeline or connectors): refuses any window where `start_date < model.cutoff_date + margin_months`. Error message names model id, cutoff date, margin, and requested start date. `IngestionPipeline` receives any cursor without model-cutoff logic.
- Runs one source at a time through the existing shared rate limiter.
- Checkpoints per (source, date window) in MinIO so an interruption resumes from the last completed window.
- Writes a run manifest to MinIO at start (`backfill/manifests/{run_id}.json`) recording: sources, window, model_id, prompt_version, prefilter_version, counts, checkpoint state, effective margin_months. Updates the manifest on completion.
- `--dry-run`: no LLM calls. Reports:
  - Per source: document count, LLM calls after pre-filter, estimated cost (API backends from token budget × per-token price), estimated wall-clock time (local backends from the latency record written by `evaluate_model.py`; fails loudly if no latency record exists for the active model).
  - Overlap report: count and model identifiers of in-window documents already present in `signal_extraction_history`.
- Reads `BACKFILL_BUDGET_CEILING` from `.env`; aborts before any LLM calls if the estimate exceeds it. Absent `BACKFILL_BUDGET_CEILING` without `--dry-run` → startup failure.
- Never writes to the live Airflow cursor Variable.

## Out of scope

New connectors. Changes to `IngestionPipeline`. Modification of the live scheduler or cursor. Re-extraction of the live overlap (reextraction-cli spec). FDA in the backfill.

## Constraints

- Invariant 1: runner writes only to MinIO and Kafka (via the pipeline).
- Invariant 3: runner calls `IngestionPipeline.run()` — no ingestion logic in the runner.
- Invariant 13: MinIO archive is unconditional and first (unchanged inside the pipeline).
- Invariant 10: idempotent — a document already ingested live reuses its `event_id`.
- Cutoff guard lives in the runner. `IngestionPipeline` must accept any cursor.
- Lineage decision is Option A (DECISIONS.md 2026-09-19 CHOICE): the backfill model is the local model selected by spec 2a. The dry-run overlap report must show zero in-window documents under a different model identifier before the live run proceeds, OR those documents must be re-extracted under the backfill model via the reextraction-cli first. A mixed-lineage corpus is not acceptable — do not proceed to Phase 4 until `SELECT DISTINCT extraction_model FROM signal_extraction_history WHERE published_date >= backfill_start` returns exactly one identifier.
- `BACKFILL_BUDGET_CEILING` absent without `--dry-run` → fail loudly.
- EPO OPS: CQL date-range syntax `pd within "YYYYMMDD,YYYYMMDD"` confirmed (DECISIONS.md 2026-09-17); 2,000-result per-window limit requires date-window splitting for high-density CPC classes.
- PubMed: NCBI rate limit is 3 req/s without key, 10 with (key configured per PREREQUISITES.md); use `datetype=pdat&mindate=YYYY/MM/DD&maxdate=YYYY/MM/DD`.

## Required tests

Carried from plan.md Step 4.0:
- `test_backfill_does_not_advance_the_live_cursor`
- `test_backfill_is_resumable_from_its_checkpoint`
- `test_backfill_respects_the_shared_rate_limiter`
- `test_backfill_dry_run_reports_document_and_call_estimates_without_calling_the_llm`
- `test_backfill_aborts_when_estimate_exceeds_configured_budget`
- `test_backfilled_document_reuses_existing_event_id_when_already_ingested_live`

New:
- `test_cutoff_guard_refuses_window_starting_before_model_cutoff_plus_margin` — error message names model id, cutoff, margin, and requested start date
- `test_cutoff_guard_margin_defaults_to_three_months`
- `test_cutoff_guard_lives_in_runner_not_pipeline` — `IngestionPipeline` accepts any cursor; the guard asserted only on the runner
- `test_dry_run_reports_already_extracted_documents_by_model_id` — overlap count and model identifier(s) in dry-run output
- `test_run_manifest_written_to_minio_at_run_start` — manifest object present before any `IngestionPipeline.run()` call
- `test_dry_run_uses_latency_record_for_local_backend_wall_clock_estimate` — synthetic latency record fixture; dry-run output contains time estimate; no LLM called
- `test_dry_run_fails_loudly_when_no_latency_record_exists_for_local_backend` — local backend active, no latency file → raises with a message naming the model

## Definition of done

```bash
cd services/ingestion-scraper && uv run pytest tests/unit/test_backfill.py -q
```

Expected: 13+ passed.

Then:
- Dry run for all five source types recorded in `DECISIONS.md`.
- Real backfill completed for at least two source types.
- Corroboration count after backfill recorded in `README.md`. If too small for Phase 4 statistics to be meaningful, record that finding and stop.

## Notes

Budget estimate: ~26,000 LLM calls at `gpt-4o-mini-2024-07-18` pricing ≈ $65. Actual depends on pre-filter pass rate. For a local model at mean latency from `evaluate_model.py`, e.g. ~5 s/document at Ollama on 36 GB: 26,000 × 5 s ≈ 36 hours. Run under `caffeinate -i` and rely on checkpoints for restarts.

The single-lineage requirement means: before backtesting, verify `SELECT DISTINCT extraction_model FROM signal_extraction_history WHERE published_date >= backfill_start` returns exactly one model identifier. If it returns more than one, re-extract the minority under the backfill model before computing Phase 4 metrics.

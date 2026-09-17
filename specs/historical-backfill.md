# Historical Backfill

**Status:** blocked
**Blocked by:** budget approval — run the dry run first, get sign-off before execution. See `docs/PREREQUISITES.md`.
**Branch:** `feature/historical-backfill`

---

## Context

Forward-only collection produces single-digit corroborations per quarter — not enough for the backtesting specs that follow this one to produce meaningful results. This spec produces the sample. It reuses `IngestionPipeline.run(source_type, cursor)` with an explicit historical cursor — no new pipeline logic.

Current live connectors: ClinicalTrials, PubMed, bioRxiv, EDGAR, FDA. EPO OPS is blocked pending credentials and can be added later without re-running the backfill.

## What this builds

A backfill runner (`scripts/run_backfill.py`) that:
- Takes a source type, start date, and end date as arguments
- Runs one source at a time through the existing rate limiter
- Checkpoints progress per (source, date window) so interruptions resume rather than restart
- Prints a dry-run estimate (document count, estimated LLM calls, estimated cost) without making any LLM calls when `--dry-run` is passed
- Aborts before any LLM calls if the estimate exceeds the configured budget ceiling

The runner **never writes to the live Airflow cursor Variable**. It uses an explicit cursor passed as an argument.

## Out of scope

New connectors, changes to `IngestionPipeline`, any modification to the live scheduler or cursor state.

## Constraints

- Invariant 1: writes only to MinIO and Kafka.
- Invariant 3: runner calls `IngestionPipeline.run()` — no ingestion logic in the runner itself.
- Invariant 13: MinIO archive is unconditional and first.
- Invariant 10: idempotent — a document already ingested live must reuse its existing `event_id`, not create a duplicate.
- The shared `RateLimitedClient` enforces rate limits across all sources — the backfill uses the same instance.
- Budget ceiling must be configured in `.env` before running.

## Required tests

- `test_backfill_does_not_advance_the_live_cursor` — the Airflow Variable is unchanged after a run
- `test_backfill_is_resumable_from_its_checkpoint` — interrupted run picks up from the last completed window
- `test_backfill_respects_the_shared_rate_limiter` — fake clock asserts aggregate rate, not per-call delays
- `test_backfill_dry_run_reports_estimates_without_calling_llm` — `--dry-run` produces document and cost estimates; zero LLM calls
- `test_backfill_aborts_when_estimate_exceeds_configured_budget` — exits before any LLM calls
- `test_backfilled_document_reuses_existing_event_id_when_already_ingested_live` — idempotency guard

## Definition of done

```bash
cd services/ingestion-scraper && uv run pytest tests/unit/test_backfill.py -q
```

Expected: 6+ passed.

Then: dry run recorded in `DECISIONS.md`. Backfill completed for at least two source types. Resulting corroboration count recorded in `README.md`. **If the count is too small for backtesting statistics to be meaningful, record that finding and stop — do not produce a number that looks like a result.**

## Notes

Budget estimate from planning: ~26,000 LLM calls at `gpt-4o-mini` pricing ≈ $65. Actual depends on pre-filter pass rate — run the dry run first. Set `BACKFILL_BUDGET_CEILING` in `.env` before executing.

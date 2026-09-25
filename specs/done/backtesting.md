# Backtesting Module

**Status:** done
**Blocked by:** —
**Branch:** `feature/backtesting`

---

## Context

`services/backtesting/` has price ingestion and alignment after those specs are done. This spec builds the backtest runner that tests whether corroborated signals precede price moves. It runs entirely from archived data — MinIO snapshots and price Parquet. It should produce a report even if the finding is "no significant effect."

The entity-only variant is required by DECISIONS.md (2026-09-19 Phase 4 FLAG v2) as a contamination control: if the model's directionality and confidence_score encode hindsight, the entity-only variant will perform similarly to or better than the full variant.

## What this builds

A backtest runner that:
- Loads corroborations from the aligned dataset (alignment spec output)
- Measures whether corroborated signals precede measurable price moves and by how long
- Produces a reproducible report: identical inputs → identical output
- Runs with sockets disabled — all data comes from MinIO snapshots and Parquet; no live network calls
- Supports `--variant entity-only` and `--variant full` (default: runs both, reports side-by-side)

**Entity-only variant**: a corroboration is the structural fact that two signals share the same `gene_target` from distinct `source_type` values within ±90 days. `directionality` and `confidence_score` are not used in grouping or weighting.

**Full variant**: corroboration uses `directionality` and `confidence_score` in addition to the structural criteria. Disagrees with entity-only only when those fields differ across a corroborating pair.

## Out of scope

Performance metrics (separate spec), price data fetching (price ingestion spec), alignment (alignment spec). This spec assumes those exist.

## Constraints

- All reads from MinIO/Parquet only. No live API calls. `pytest-socket` with `--disable-socket` must pass.
- Reproducible: given the same archived snapshots, the runner produces the same report every time.
- `event_id` is document identity — multiple extractions of the same document count once, not once per extraction.
- `raw_object_key` on the event enables re-extraction from archive if needed.

## Required tests

- `test_backtest_runs_with_sockets_disabled` — `pytest-socket` with `--disable-socket --allow-unix-socket`; documented limit: patches in-process sockets only, not subprocesses
- `test_identical_inputs_produce_identical_output`
- `test_no_corroborated_signals_produces_empty_report_not_crash`
- `test_reextraction_from_archive_resolves_the_correct_snapshot` — uses `raw_object_key` from the event
- `test_multiple_extractions_of_one_document_count_once` — guards the double-counting failure from putting `schema_version` in `event_id`
- `test_entity_only_variant_ignores_directionality_and_confidence` — two signals with matching gene_target and distinct source_types produce a corroboration regardless of their directionality values; result is identical with directionality flipped
- `test_full_variant_uses_directionality_weighting` — same pair as above; full-variant corroboration score differs when directionality values change
- `test_both_variants_reported_side_by_side` — single runner call with no explicit variant; output contains sections for both entity-only and full results

## Definition of done

```bash
cd services/backtesting && uv run pytest tests/unit/test_backtest.py -q
```

Expected: 8 passed.

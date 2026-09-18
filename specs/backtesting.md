# Backtesting Module

**Status:** done
**Blocked by:** —
**Branch:** `feature/backtesting`

---

## Context

`services/backtesting/` has price ingestion and alignment after those specs are done. This spec builds the backtest runner that tests whether corroborated signals precede price moves. It runs entirely from archived data — MinIO snapshots and price Parquet. It should produce a report even if the finding is "no significant effect."

## What this builds

A backtest runner that:
- Loads corroborations from the aligned dataset (alignment spec output)
- Measures whether corroborated signals precede measurable price moves and by how long
- Produces a reproducible report: identical inputs → identical output
- Runs with sockets disabled — all data comes from MinIO snapshots and Parquet; no live network calls

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

## Definition of done

```bash
cd services/backtesting && uv run pytest tests/unit/test_backtest.py -q
```

Expected: 5+ passed. Plus: a run produces a report using only archived data — even if the finding is "no significant effect."

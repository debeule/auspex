# Performance Metrics

**Status:** ready
**Blocked by:** —
**Branch:** `feature/performance-metrics`

---

## Context

`services/backtesting/` has the backtest runner after that spec is done. This spec adds the statistics layer on top of the backtest output.

The entity-only variant is required by DECISIONS.md (2026-09-19 Phase 4 FLAG v2). Metrics must be computed and reported separately for each variant so the contamination control can be inspected alongside the full-model results.

## What this builds

A metrics module that computes hit rate, average lead time, and basic risk-adjusted stats from backtest results. Every metric is reported with its sample size — a hit rate over six observations must be visibly a hit rate over six observations. Run parameters are stored with results.

Each metrics output carries a `variant` field (`entity-only` or `full`). When the runner produces both variants, metrics are computed for each and reported side-by-side.

## Out of scope

Visualisation (dashboard spec), live alerting (watchlist spec). This spec only computes and persists metrics.

## Constraints

- Every metric output includes sample size — never report a percentage without the N.
- Run parameters stored alongside results: window size, source types, `prompt_version`, `prefilter_version`, `extraction_model`, `variant`.
- Zero-signal and single-observation edge cases must produce defined (not error) outputs.

## Required tests

Carried from Phase 2:
- `test_metrics_against_known_synthetic_series` — hand-computed expected values; asserts exact figures
- `test_zero_signal_run_metrics_are_defined` — empty dataset produces a valid metrics object, not an exception
- `test_single_observation_risk_stats_handled` — no division-by-zero or NaN
- `test_sample_size_reported_alongside_every_metric`
- `test_run_parameters_stored_with_results`

New:
- `test_metrics_output_includes_variant_field` — every metrics object has a `variant` field; value is `entity-only` or `full`
- `test_entity_only_and_full_variants_reported_side_by_side` — when runner output contains both variants, metrics module produces two result objects
- `test_entity_only_metrics_independent_of_directionality` — synthetic series with mixed directionality values; entity-only metrics are unchanged; full-variant metrics differ

## Definition of done

```bash
cd services/backtesting && uv run pytest tests/unit/test_metrics.py -q
```

Expected: 8+ passed.

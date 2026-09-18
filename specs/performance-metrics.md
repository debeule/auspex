# Performance Metrics

**Status:** done
**Blocked by:** —
**Branch:** `feature/performance-metrics`

---

## Context

`services/backtesting/` has the backtest runner after that spec is done. This spec adds the statistics layer on top of the backtest output.

## What this builds

A metrics module that computes hit rate, average lead time, and basic risk-adjusted stats from backtest results. Every metric is reported with its sample size — a hit rate over six observations must be visibly a hit rate over six observations. Run parameters are stored with results.

## Out of scope

Visualisation (dashboard spec), live alerting (watchlist spec). This spec only computes and persists metrics.

## Constraints

- Every metric output includes sample size — never report a percentage without the N.
- Run parameters stored alongside results: window size, source types, `prompt_version`, `prefilter_version`, `extraction_model`.
- Zero-signal and single-observation edge cases must produce defined (not error) outputs.

## Required tests

- `test_metrics_against_known_synthetic_series` — hand-computed expected values; asserts exact figures
- `test_zero_signal_run_metrics_are_defined` — empty dataset produces a valid metrics object, not an exception
- `test_single_observation_risk_stats_handled` — no division-by-zero or NaN
- `test_sample_size_reported_alongside_every_metric`
- `test_run_parameters_stored_with_results`

## Definition of done

```bash
cd services/backtesting && uv run pytest tests/unit/test_metrics.py -q
```

Expected: 5+ passed.

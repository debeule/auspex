# Evaluation Protocol

**Status:** blocked
**Blocked by:**
1. `specs/market-simulation.md` — `CostModel` and `CurrencyConverter` required for net-expectancy computation
2. `specs/performance-metrics.md` (entity-only variant) — metrics output format must exist before the evaluation report can extend it
3. `specs/historical-backfill.md` — the protocol can be implemented and unit-tested without backfill data, but a meaningful end-to-end run requires the backfill corpus

**Branch:** `feature/evaluation-protocol`

---

## Context

The backtesting module (specs/backtesting.md) produces signal counts and lag distributions. The performance-metrics module (specs/performance-metrics.md) produces per-variant metrics. This spec adds the statistical evaluation layer: abnormal returns relative to XBI, known-at timing with configurable delay, walk-forward splitting with embargo, deflated Sharpe computation, bootstrap confidence intervals, and holdout protection.

The evaluation-protocol spec implements the Bailey & López de Prado (2014) deflated Sharpe ratio and the Harvey, Liu & Zhu (2016) `t > 3` promotion threshold — the two primary safeguards against overfitting on a small sample.

All hypotheses are evaluated via this protocol. The protocol itself does not decide which hypothesis to test — that is the hypothesis-registry spec's concern.

## What this builds

`auspex_backtesting/evaluation.py`:

**`AbnormalReturnCalculator`**
- `compute(signal_returns: pd.Series, benchmark_returns: pd.Series) → AbnormalReturnSeries` — element-wise arithmetic excess return (signal return minus benchmark return over the same window). Returns an object exposing: `mean`, `std`, `t_stat`, `p_value`, `hit_rate` (fraction > 0), `n`.
- Benchmark returns: XBI daily close, fetched via the same yfinance price-ingestion path (ticker `XBI`), stored in MinIO Parquet.

**`BootstrapCI`**
- `compute(series: pd.Series, n_bootstrap: int = 10_000, ci: float = 0.95, seed: int = 42) → tuple[float, float]` — bootstrap CI on the mean using paired samples with replacement. Seeded for reproducibility.

**`WalkForwardSplitter`**
- `split(events: pd.DataFrame, in_sample_months: int, oos_months: int, embargo_days: int) → list[WalkForwardSegment]`
- Each `WalkForwardSegment` has `.in_sample` and `.oos` DataFrames of events.
- Events in the embargo window (last `embargo_days` of in-sample through first `embargo_days` of OOS) are excluded from both splits.
- If the event set is too small to produce even one split, raises `InsufficientEventsError` naming the required vs available counts.
- Holdout: the last `HOLDOUT_MONTHS` (default 3, read from `.env`) of the event date range are excluded from all splits. Accessed only after promotion (see below).

**`HoldoutGuard`**
- `is_sealed(result: EvaluationResult) → bool` — True until `is_promotable(result)` returns True. `run_holdout(events)` raises `HoldoutSealedError` if called while sealed.
- Promotion check: `deflated_sharpe > PROMOTION_DEFLATED_SHARPE_THRESHOLD` AND `t_stat > PROMOTION_T_THRESHOLD`; thresholds read from `.env` (defaults: 0.95 and 3.0 per Harvey et al. 2016 and Bailey & López de Prado 2014).

**`DeflatedSharpe`**
- `compute(sharpe_ratio: float, n_obs: int, n_trials: int, skewness: float = 0.0, kurtosis: float = 3.0) → float` — Bailey & López de Prado (2014) Eq. 2. Requires `n_trials` (number of backtests run on this hypothesis corpus, read from `config/hypotheses/trials/h<n>.jsonl`). A higher trial count deflates the Sharpe further.

**`KnownAtDelay`**
- Applied to every event before evaluation: `entry_date = next_trading_day(corroborated_at + timedelta(KNOWN_AT_DELAY_DAYS))`; `KNOWN_AT_DELAY_DAYS` read from `.env` (default 1). Sensitivity analysis at 0, 1, 3, 5 values must be included in the evaluation report.

**`EvaluationProtocol`**
- `run(hypothesis_id: str, events: pd.DataFrame, variant: str) → EvaluationResult`
- Calls `verify_hypothesis(hypothesis_id)` first — raises on unregistered or modified hypothesis.
- Returns `EvaluationResult` with fields: `hypothesis_id`, `variant` (entity-only or full), `n_events`, `known_at_delay_days`, `mean_abnormal_return`, `t_stat`, `p_value`, `deflated_sharpe`, `bootstrap_ci_95`, `hit_rate`, `net_expectancy_eur` (mean P&L per event in EUR, net of costs from `CostModel`), `walk_forward_segments`, `holdout_sealed`, `run_id`.

## Out of scope

Live evaluation, trade signal generation, IBKR order submission. Intraday timing. Factor model regression (Fama-French etc.) — XBI excess return is the only benchmark at this sample size. CGT computation (post-trade accounting, not part of evaluation).

## Constraints

- Sockets disabled in all unit tests. All data from MinIO Parquet. No live yfinance calls in tests.
- `KNOWN_AT_DELAY_DAYS`, `HOLDOUT_MONTHS`, `PROMOTION_DEFLATED_SHARPE_THRESHOLD`, `PROMOTION_T_THRESHOLD`, `N_BOOTSTRAP` all read from `.env`. Absent without defaults noted above → startup failure with a descriptive message naming the missing variable.
- The trial count fed to `DeflatedSharpe.compute()` must come from `config/hypotheses/trials/h<n>.jsonl` line count — not a hardcoded value. Every additional backtest run increases the penalty.
- `evaluation.py` must not contain ingestion logic. It reads MinIO Parquet via the existing price-ingestion path; it does not call any connector.
- Invariant 1 (scraper writes only to MinIO/Kafka) and Invariant 2 (core-hub sole writer to DB) are not implicated — this module lives in `services/backtesting/` and is read-only with respect to the pipeline.

## Required tests

In `tests/unit/test_evaluation_protocol.py`:

- `test_abnormal_return_calculator_subtracts_benchmark_correctly` — signal return 5%, benchmark return 2%, → abnormal return 3%; mean and t_stat computed from a three-event fixture match hand-computed values
- `test_bootstrap_ci_width_narrows_with_larger_sample` — CI width at n=200 is narrower than at n=20 for the same distribution
- `test_walk_forward_splitter_produces_correct_segment_count` — 24-month event range, in_sample=18, oos=6 → 1 segment (slides by OOS window; 1 complete non-overlapping segment)
- `test_walk_forward_splitter_respects_embargo` — embargo_days=30; no event within 30 days of the split boundary appears in either in_sample or oos
- `test_deflated_sharpe_is_lower_than_sharpe_for_multiple_trials` — `compute(sr=1.5, n_obs=100, n_trials=5)` < 1.5; `compute(sr=1.5, n_obs=100, n_trials=1)` is closer to 1.5
- `test_holdout_raises_error_before_promotion` — `HoldoutGuard.run_holdout()` raises `HoldoutSealedError` when `is_promotable(result) = False`
- `test_evaluation_result_includes_variant_field` — `EvaluationResult.variant` is `'entity-only'` when run with entity-only variant; `'full'` otherwise
- `test_net_expectancy_is_computed_net_of_costs` — `net_expectancy_eur` equals mean_abnormal_return_in_eur minus `CostModel.round_trip_cost_usd` converted to EUR; fixture with known values matches hand-computed result

## Definition of done

```bash
cd services/backtesting && uv run pytest tests/unit/test_evaluation_protocol.py -q
```

Expected: 8 passed.

Then: at least one `EvaluationProtocol.run()` call on H1 using real backfill data recorded in DECISIONS.md with: n_events, mean_abnormal_return, t_stat, deflated_sharpe, variant (entity-only), known_at_delay_days, holdout_sealed status.

## Notes

**Walk-forward with 24-month data:** One in-sample/OOS segment (18 months in, 6 months out) is the maximum non-overlapping split. With holdout of 3 months, the usable window is 21 months, yielding one 18-month in-sample + 3-month OOS segment (not the 6 intended). At this data volume walk-forward is primarily a validation check, not a robust OOS regime. Document this limitation in the evaluation report.

**Known-at timing vs ingestion latency:** `corroborated_at = max(published_date)` is a public date — in the real world, we would not know about the second signal the moment it was published. `KNOWN_AT_DELAY_DAYS=1` models a conservative 1-business-day lag between publication and our observation. If the ingestion pipeline runs daily, this is approximately correct. Run the sensitivity analysis at 0, 1, 3, 5 days and report all four results.

**Deflated Sharpe formula reference:** Bailey, D.H. and López de Prado, M. (2014). "The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting, and Non-Normality." Journal of Portfolio Management, 40(5), pp. 94–107. Use the formula from Eq. 2 of that paper.

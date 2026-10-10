# Evaluation Protocol

**Status:** ready
**Blocked by:** none for the code and its required tests. Both code prerequisites are done: `specs/done/market-simulation.md` (`CostModel`, `CurrencyConverter`) and `specs/done/performance-metrics.md` (entity-only variant). Only the end-to-end run under "Definition of done" waits on `specs/historical-backfill.md`; it is recorded later and is not a merge condition.

**Branch:** `feature/evaluation-protocol`

---

## Context

The backtesting module (specs/backtesting.md) produces signal counts and lag distributions. The performance-metrics module (specs/performance-metrics.md) produces per-variant metrics. This spec adds the statistical evaluation layer: abnormal returns relative to XBI, known-at timing with configurable delay, walk-forward splitting with embargo, deflated Sharpe computation, bootstrap confidence intervals, and holdout protection.

The evaluation-protocol spec implements the Bailey & López de Prado (2014) deflated Sharpe ratio and the Harvey, Liu & Zhu (2016) `t > 3` promotion threshold — the two primary safeguards against overfitting on a small sample.

**The protocol is pre-registered.** `config/hypotheses/protocol.yaml` was registered in `config/hypotheses/registry.jsonl` on 2026-10-07, before any backtest touched the backfill corpus (see `DECISIONS.md`, 2026-10-07 pre-registration entries). It fixes the abnormal-return model, the inference method, how trials are counted, the family trial budget, the promotion thresholds and the kill criteria. This module reads those values from that file after verifying its hash with `verify_hypothesis("protocol")`; none of them is read from `.env`, so a threshold cannot be changed without a new, dated registry entry. Every hypothesis YAML declares a `role` (`promotable`, `diagnostic` or `descriptive`) and a `status` (`pre-registered` or `suspended`); promotable hypotheses also declare their trial grid and one `primary_cell`.

All hypotheses are evaluated via this protocol. The protocol itself does not decide which hypothesis to test — that is the hypothesis-registry spec's concern.

## What this builds

`auspex_backtesting/evaluation.py`:

**`AbnormalReturnCalculator`**
- Market model against XBI, per `protocol.yaml` `abnormal_return`: for each event, OLS of the ticker's daily return on XBI's daily return over trading days `[-250, -30]` relative to the entry date gives `alpha` and `beta`; the event's abnormal return over a window is `sum(R_ticker − (alpha + beta × R_XBI))` over that window's trading days.
- Fewer than `min_estimation_obs` (120) estimation days → market-adjusted fallback (`alpha = 0`, `beta = 1`); the event is flagged `estimation_fallback = True` and the report states how many events used it.
- `compute(events: pd.DataFrame, prices: PriceStore, window: tuple[int, int]) → AbnormalReturnSeries` exposing `values` (one per event), `mean`, `std`, `hit_rate` (fraction > 0 in the registered direction), `n`, `n_fallback`, and per-event `ticker` and `event_month` for clustering.
- Benchmark returns: XBI daily close, fetched via the same yfinance price-ingestion path (ticker `XBI`), stored in MinIO Parquet.

**`ClusteredInference`**
- `t_stat(series: AbnormalReturnSeries) → InferenceResult` — t-statistic of the mean with two-way cluster-robust standard errors by `ticker` and `event_month` (Cameron, Gelbach & Miller 2011).
- When either dimension has fewer than `min_clusters_per_dimension` (30) clusters, the p-value comes from a wild cluster bootstrap (Webb weights, `bootstrap_draws` 9,999, seed 42) clustered on the smaller dimension, and `InferenceResult.method` says so. With the current 8-ticker watchlist this is always the bootstrap path.
- `independent_events(series) → int` — events on the same ticker whose holding windows overlap count as one. Reported beside `n`.
- `InferenceResult` carries `t_stat`, `p_value`, `method`, `n_clusters_ticker`, `n_clusters_month`, `n_independent`.

**`TrialLedger`**
- Each line appended to `config/hypotheses/trials/<id>.jsonl` records the cells evaluated in that run: a list of `(holding_period_days, known_at_delay_days, variant)`.
- `family_trial_count(trials_dir, hypotheses) → int` — the number of cells evaluated across every run of every hypothesis whose `role` is listed in `protocol.yaml` `trials.counts_roles` (`promotable`). Diagnostic and descriptive runs are logged but not counted. This is the `n_trials` passed to `DeflatedSharpe`.
- `remaining_budget()` = the hypothesis family's `families.<family>.budget_cells` (64 for `event_backfill`) − that family's trial count. A run whose cells would exceed it raises `TrialBudgetExhaustedError` before any return is computed.

**`KillCriteria`**
- `evaluate(hypothesis_id, results) → list[KillVerdict]` — applies each `protocol.yaml` `kill_criteria` entry whose `applies_to` covers the hypothesis, on the in-sample segment only. A `KillVerdict` carries `criterion_id`, `fired: bool`, the inputs it compared, and the registered `action`.
- `lagging_signal` (H3): fires when mean CAR[-20,-1] and mean CAR[+1,+20] share a sign and `|pre| >= |post|`, at known-at delay 1.
- `no_in_sample_effect` (promotable): fires unless at least one registered horizon, at the primary delay and variant, has mean net abnormal return above 0 in the registered direction with clustered t at or above 1.5.
- `cost_check` (promotable): fires when the median modelled round-trip cost exceeds half the expected gross abnormal return.
- `mapping_quality` and `forward_check` are evaluated outside this module (golden-set evaluation and forward paper trading); `KillCriteria` exposes their thresholds so those callers read the same registered values.
- Verdicts are written into the evaluation report. A fired criterion is acted on by a manual `DECISIONS.md` entry; the module does not edit hypothesis files.

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
- Promotion check, on the hypothesis's `primary_cell` only: `deflated_sharpe > deflated_sharpe_min` AND clustered `t_stat > clustered_t_min` AND no kill criterion fired. Thresholds read from `protocol.yaml` `promotion` (0.95 and 3.0 per Bailey & López de Prado 2014 and Harvey et al. 2016). A non-primary cell that clears both thresholds is reported but cannot promote.
- Diagnostic and descriptive hypotheses are never promotable.

**`DeflatedSharpe`**
- Shared: the portfolio backtest (`specs/cross-sectional-portfolio-backtest.md`) imports `DeflatedSharpe` and `TrialLedger` for its own verdict on monthly returns. Keep both free of event-specific inputs.
- `compute(sharpe_ratio: float, n_obs: int, n_trials: int, skewness: float = 0.0, kurtosis: float = 3.0) → float` — Bailey & López de Prado (2014) Eq. 2. `n_trials` is `TrialLedger.family_trial_count()`: every cell of every promotable hypothesis evaluated on this corpus, not the number of runs of one hypothesis. A higher trial count deflates the Sharpe further.

**`KnownAtDelay`**
- Applied to every event before evaluation: `entry_date = next_trading_day(corroborated_at + timedelta(known_at_delay_days))`. The delays evaluated are the hypothesis's declared `known_at_delay_days` (promotable hypotheses declare 0, 1, 3, 5 per `protocol.yaml`); each delay is a separate cell and counts as a trial. The primary delay is 1.

**`EvaluationProtocol`**
- `run(hypothesis_id: str, events: pd.DataFrame, variant: str) → EvaluationResult`
- The class exists (`auspex_backtesting.protocol`, from the slow-signal pre-registration): its constructor verifies `protocol`, and `admit(hypothesis_id)` verifies the hypothesis and refuses an unbudgeted family, a family over budget, a role the family does not hold, and shorts or options. `run()` calls `admit()` first.
- Raises `HypothesisSuspendedError` when the hypothesis `status` is `suspended`.
- Raises `UnregisteredCellError` when asked for a horizon, delay or variant outside the hypothesis's declared grid.
- Raises `TrialBudgetExhaustedError` (see `TrialLedger`) before computing anything when the run would exceed the family budget.
- Returns `EvaluationResult` with fields: `hypothesis_id`, `variant` (entity-only or full), `n_events`, `n_independent_events`, `known_at_delay_days`, `mean_abnormal_return`, `t_stat` (clustered), `p_value`, `inference_method`, `n_estimation_fallback`, `deflated_sharpe`, `n_trials`, `is_primary_cell`, `bootstrap_ci_95`, `hit_rate`, `net_expectancy_eur` (mean P&L per event in EUR, net of costs from `CostModel`), `kill_verdicts`, `walk_forward_segments`, `holdout_sealed`, `run_id`.

## Out of scope

Live evaluation, trade signal generation, IBKR order submission. Intraday timing. Multi-factor regression (Fama-French etc.) — the single-index market model against XBI is the only benchmark at this sample size. CGT computation (post-trade accounting, not part of evaluation). Changing any value in `protocol.yaml` — that is a new registration and a `DECISIONS.md` entry, not code.

## Constraints

- Sockets disabled in all unit tests. All data from MinIO Parquet. No live yfinance calls in tests.
- Known-at delays, holdout months, promotion thresholds, kill-criteria thresholds, clustering settings and the trial budget are read from the registered `config/hypotheses/protocol.yaml`, never from `.env` or source. A modified or unregistered protocol file is a startup failure. `N_BOOTSTRAP` (for `BootstrapCI` only) stays in `.env`.
- The trial count fed to `DeflatedSharpe.compute()` must come from `TrialLedger.family_trial_count()` — the sum of cells across `config/hypotheses/trials/*.jsonl` for promotable hypotheses — not a hardcoded value and not one hypothesis's line count. Every additional cell evaluated increases the penalty.
- Kill criteria and the in-sample/OOS split use only the in-sample segment; the holdout stays sealed.
- `evaluation.py` must not contain ingestion logic. It reads MinIO Parquet via the existing price-ingestion path; it does not call any connector.
- Invariant 1 (scraper writes only to MinIO/Kafka) and Invariant 2 (core-hub sole writer to DB) are not implicated — this module lives in `services/backtesting/` and is read-only with respect to the pipeline.

## Required tests

In `tests/unit/test_evaluation_protocol.py`:

- `test_market_model_abnormal_return_removes_beta_exposure` — ticker returns generated as `1.8 × R_XBI` with no idiosyncratic term; event-window abnormal return is 0 to within 1e-9, while the raw excess over XBI is not
- `test_market_model_estimation_excludes_event_and_gap_days` — a price shock placed on day −10 changes the event-window abnormal return but leaves the estimated `alpha` and `beta` unchanged
- `test_market_model_falls_back_to_market_adjusted_with_short_history` — 60 days of history before the event; abnormal return equals raw excess over XBI and the event is counted in `n_fallback`
- `test_clustered_t_stat_is_smaller_than_naive_for_overlapping_same_ticker_events` — fixture of overlapping events on two tickers with a shared shock; clustered `|t|` < naive iid `|t|`
- `test_clustered_inference_uses_wild_bootstrap_below_minimum_clusters` — 8 tickers → `InferenceResult.method == "wild_cluster_bootstrap"`; 40 tickers and 40 months → `"two_way_clustered"`
- `test_independent_event_count_merges_overlapping_same_ticker_windows` — three SRPT events 5 days apart with 20-day windows plus one BEAM event → `n_independent == 2`
- `test_family_trial_count_sums_cells_across_promotable_hypotheses` — `trials/h1.jsonl` with two runs of 8 cells and `trials/h4.jsonl` with one run of 4 cells, plus a diagnostic `trials/h3.jsonl` run → `family_trial_count == 20`
- `test_run_refuses_when_family_trial_budget_would_be_exceeded` — ledger at 60 cells, budget 64, a run requesting 8 cells raises `TrialBudgetExhaustedError` and appends nothing
- `test_run_refuses_cell_outside_registered_grid` — horizon 15 requested for a hypothesis declaring `[5, 10, 20, 30]` raises `UnregisteredCellError`
- `test_run_refuses_suspended_hypothesis` — hypothesis with `status: suspended` raises `HypothesisSuspendedError`
- `test_run_refuses_modified_protocol_file` — `protocol.yaml` edited after registration raises `HypothesisModifiedError`
- `test_promotion_is_judged_on_primary_cell_only` — a non-primary cell with t 3.5 and deflated Sharpe 0.97, primary cell with t 1.2 → `is_promotable` False
- `test_lagging_signal_kill_fires_when_pre_window_dominates` — mean CAR[-20,-1] 6%, CAR[+1,+20] 2% → fired; CAR[-20,-1] 1%, CAR[+1,+20] 4% → not fired; CAR[-20,-1] −3%, CAR[+1,+20] 2% → not fired
- `test_no_in_sample_effect_kill_fires_without_a_positive_significant_horizon` — all horizons net mean ≤ 0 → fired; one horizon with net mean 2% and clustered t 1.6 → not fired; one horizon with net mean 2% and clustered t 1.4 → fired
- `test_kill_criteria_thresholds_come_from_registered_protocol` — a protocol fixture with `min_clustered_t: 2.5` changes the second case above to fired
- `test_bootstrap_ci_width_narrows_with_larger_sample` — CI width at n=200 is narrower than at n=20 for the same distribution
- `test_walk_forward_splitter_produces_correct_segment_count` — 24-month event range, in_sample=18, oos=6 → 1 segment (slides by OOS window; 1 complete non-overlapping segment)
- `test_walk_forward_splitter_respects_embargo` — embargo_days=30; no event within 30 days of the split boundary appears in either in_sample or oos
- `test_deflated_sharpe_is_lower_than_sharpe_for_multiple_trials` — `compute(sr=1.5, n_obs=100, n_trials=32)` < 1.5; `compute(sr=1.5, n_obs=100, n_trials=1)` is closer to 1.5
- `test_holdout_raises_error_before_promotion` — `HoldoutGuard.run_holdout()` raises `HoldoutSealedError` when `is_promotable(result) = False`
- `test_evaluation_result_includes_variant_field` — `EvaluationResult.variant` is `'entity-only'` when run with entity-only variant; `'full'` otherwise
- `test_report_lists_cost_components_per_trade` — each trade in the report carries `RoundTripCost.components()` (commission, spread, tob, fx_fee, borrow_fee); the cost model is built with a `SpreadEstimator` so spreads are per ticker
- `test_net_expectancy_is_computed_net_of_costs` — `net_expectancy_eur` equals mean_abnormal_return_in_eur minus `CostModel.round_trip_cost_usd` converted to EUR; fixture with known values matches hand-computed result

## Definition of done

```bash
cd services/backtesting && uv run pytest tests/unit/test_evaluation_protocol.py -q
```

Expected: 22 passed.

Then, once the historical backfill exists (a later session; not a merge condition): the first `EvaluationProtocol.run()` on real backfill data is H3 (its `run_order` is 1), recorded in DECISIONS.md with the pre and post CARs, n_events, n_independent_events, inference method and the `lagging_signal` verdict. Promotable hypotheses run only after H3 and only once re-registered with `status: pre-registered`; each such run is recorded with n_events, mean_abnormal_return, clustered t_stat, deflated_sharpe, n_trials, variant, known_at_delay_days, kill verdicts and holdout_sealed status.

## Notes

**Walk-forward with 24-month data:** One in-sample/OOS segment (18 months in, 6 months out) is the maximum non-overlapping split. With holdout of 3 months, the usable window is 21 months, yielding one 18-month in-sample + 3-month OOS segment (not the 6 intended). At this data volume walk-forward is primarily a validation check, not a robust OOS regime. Document this limitation in the evaluation report.

**Known-at timing vs ingestion latency:** `corroborated_at = max(published_date)` is a public date — in the real world, we would not know about the second signal the moment it was published. A known-at delay of 1 models a conservative 1-business-day lag between publication and our observation. If the ingestion pipeline runs daily, this is approximately correct. The 0, 3 and 5 day delays are sensitivity cells; they count as trials and cannot promote.

**Why clustered errors and a market model:** events on the same ticker overlap in time and all watched names co-move with XBI, so an iid t-test on 100 events may describe 20 to 30 independent bets. Small-cap biotech betas to XBI are rarely 1, so raw excess return leaves sector beta in the "abnormal" return. With 8 tickers there are too few clusters for cluster-robust errors to be reliable on their own; the wild cluster bootstrap (Cameron, Gelbach & Miller 2008; Webb 2023) is the small-cluster correction.

**Trial budget:** 64 cells across the family is two hypotheses at H1's grid (4 horizons × 4 delays × 2 variants = 32). Spending it on one re-registered hypothesis leaves room for one more; exhausting it means the backfill corpus is spent and new hypotheses wait for forward data.

**Deflated Sharpe formula reference:** Bailey, D.H. and López de Prado, M. (2014). "The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting, and Non-Normality." Journal of Portfolio Management, 40(5), pp. 94–107. Use the formula from Eq. 2 of that paper.

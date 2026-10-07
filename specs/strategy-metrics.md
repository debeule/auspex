# Strategy Metrics

**Status:** blocked
**Blocked by:**
1. `specs/strategy-framework.md` — `VirtualBook`, strategy registry, and version tracking must exist
2. `specs/hypothesis-registry.md` — trial count (for deflated Sharpe) is read from `config/hypotheses/trials/`
3. `specs/evaluation-protocol.md` — `DeflatedSharpe.compute()` and `BootstrapCI` are imported from there

**Branch:** `feature/strategy-metrics`

---

## Context

The strategy runtime (previous spec) maintains per-strategy virtual books in MinIO Parquet. This spec builds the metrics layer that reads those books, computes statistics, and exposes them through an API. Metrics are never computed in a frontend; the API is the computation boundary.

`DeflatedSharpe.compute()` and `BootstrapCI.compute()` already exist in the evaluation-protocol spec. This spec imports them rather than reimplementing.

## What this builds

### `services/strategy/src/auspex_strategy/metrics/`

**`ActivityFunnel`**
Per strategy version and mode, from the runtime's event counters:
- `inputs_seen` — corroboration events processed
- `intents` — `TradeIntent`s produced by `decide()`
- `passed_risk` — intents approved by `RiskManager`
- `filled` — intents that received a `VirtualBook` fill (entry)
- `closed` — positions closed with realised P&L

**`TradeMetrics`**
Computed from `VirtualBook.closed_trades()`:
- `hit_rate` — fraction of closed trades with `net_pnl_eur > 0`
- `avg_win_eur`, `avg_loss_eur` — mean P&L of winning and losing trades
- `expectancy_eur` — `hit_rate × avg_win_eur − (1 − hit_rate) × |avg_loss_eur|`
- `avg_holding_days`, `trades_per_year`
- All reported with `n` (trade count) and a `bootstrap_ci_95` from `BootstrapCI`.
- If `n < MIN_TRADES_FOR_METRICS` (from `.env`, default 20): `InsufficientTradeDataError` raised. The API still returns the metric object but with `insufficient_data: true` and null values for all statistics. Never silently return a number over an insufficient sample.

**`ReturnMetrics`**
- `mean_abnormal_return` (vs XBI, using `AbnormalReturnCalculator` from evaluation-protocol)
- `cumulative_abnormal_return_series` — one data point per closed trade in time order
- `sharpe` — annualised Sharpe of trade-level abnormal returns
- `deflated_sharpe` — `DeflatedSharpe.compute(sharpe, n_obs=n_closed, n_trials=trial_count_from_registry)`
  - `trial_count` = `TrialLedger.family_trial_count()` from the evaluation-protocol spec: cells evaluated across every promotable hypothesis on the corpus, per the registered `config/hypotheses/protocol.yaml`
  - This is the honest guard: every cell evaluated on any promotable hypothesis increments the trial count and deflates the reported Sharpe
- `max_drawdown_pct` — maximum peak-to-trough drawdown of the cumulative P&L curve
- `bootstrap_ci_95` on `mean_abnormal_return` from `BootstrapCI`
- All with `n` alongside

**`BacktestPaperComparison`**
- `is_inside_backtest_ci(paper_metrics, backtest_metrics) → bool` — True if paper `mean_abnormal_return` falls within `backtest_metrics.bootstrap_ci_95`
- `deviation_from_backtest_ci` — signed distance from nearest CI boundary (negative = outside)
- If `is_inside_backtest_ci = False`: flag `paper_tracking_deviation = True` in the `StrategyMetricsSummary`

**`CorrelationMatrix`**
- `compute(strategy_versions: list[str]) → pd.DataFrame` — pairwise Pearson correlation of trade-level abnormal returns across all active strategy versions
- Aligned on trade close dates; missing dates treated as 0 abnormal return
- Only includes strategy versions with at least `MIN_TRADES_FOR_METRICS` closed trades

**`LatencyMetrics`**
- Reads `strategy/latency/distribution.jsonl` from MinIO
- Reports `p50`, `p95`, `p99` of `latency_corroboration_to_intent_ms`
- Includes a count of how many signals had latency > `KNOWN_AT_DELAY_DAYS × 24 × 3600 × 1000` ms (i.e., where the actual observed delay exceeded the modelled delay)

**`StrategyMetricsSummary`** — top-level object returned by the API:
```
{
  strategy_name, version, mode, hypothesis_id,
  activity_funnel, trade_metrics, return_metrics,
  backtest_paper_comparison (null if mode=backtest),
  insufficient_data, n_strategies_ever_tested (total across all versions),
  computed_at
}
```

`n_strategies_ever_tested` is the total count of distinct (strategy_name, version) pairs that have ever been registered, including retired ones. This is the "honesty guard" number surfaced in the UI to contextualise the deflated Sharpe.

### API endpoint

`GET /api/v1/metrics/strategies` — returns list of `StrategyMetricsSummary` for all non-retired strategies across all modes.
`GET /api/v1/metrics/strategies/<name>/<version>` — single strategy version.
`GET /api/v1/metrics/correlation` — returns `CorrelationMatrix`.

The metrics API is served by the strategy service (Flask or the existing scraper HTTP API pattern), not core-hub. It reads MinIO only.

## Out of scope

Storing metrics in Postgres (read from MinIO only). UI rendering. Generating signals or running strategies. Deleting historical metrics.

## Constraints

- All reads from MinIO. No live strategy execution during metrics computation.
- Versions are never mixed: metrics for version "1.0" use only the virtual book for "1.0". `StrategyMetricsSummary.version` is always pinned.
- `pytest-socket --disable-socket` across unit tests.
- `n` must appear next to every metric in the API response and in internal data structures. Any metric without a corresponding `n` is a test failure.
- Invariant 6: `MINIO_ENDPOINT`, credentials from `.env` only.

## Required tests

In `tests/unit/test_strategy_metrics.py`:

- `test_metrics_reproduce_hand_computed_on_toy_trade_set` — 5-trade fixture with known entry/exit prices and costs; `hit_rate`, `expectancy_eur`, `mean_abnormal_return` match hand-computed expected values to 4 decimal places
- `test_versions_are_never_mixed` — two `VirtualBook` fixtures for same strategy name but versions "1.0" and "1.1"; `TradeMetrics` for "1.0" uses only "1.0" trades; verified by trade count
- `test_insufficient_data_raises_not_silently_zero` — 3 closed trades with `MIN_TRADES_FOR_METRICS=20`; calling `TradeMetrics.compute()` raises `InsufficientTradeDataError`; `StrategyMetricsSummary` has `insufficient_data: true` and null statistics
- `test_deflated_sharpe_reads_trial_count_from_registry` — synthetic `trials/h1.jsonl` with one run of 4 cells and `trials/h4.jsonl` with one run of 1 cell (both promotable); `deflated_sharpe` computed from `DeflatedSharpe.compute(n_trials=5)` matches expected value; matches neither the raw Sharpe nor a value computed with `n_trials=1`
- `test_backtest_paper_comparison_flags_deviation_outside_ci` — paper `mean_abnormal_return = 0.01`; backtest `bootstrap_ci_95 = (0.03, 0.07)`; `is_inside_backtest_ci = False`; `deviation_from_backtest_ci` is negative
- `test_correlation_matrix_covers_all_active_versions` — three strategy version fixtures with 25+ trades each; matrix is 3×3 symmetric; diagonal entries are 1.0
- `test_metrics_api_returns_computed_not_raw` — API endpoint called with MinIO fixture; response body contains `hit_rate` and `mean_abnormal_return`; does not contain raw trade rows
- `test_sample_size_next_to_every_metric` — `StrategyMetricsSummary` serialised to dict; verify every statistical metric field has a corresponding `n_<field>` or top-level `n` present

## Definition of done

```bash
cd services/strategy && uv run pytest tests/unit/test_strategy_metrics.py -q
```

Expected: 8 passed.

Then: `GET /api/v1/metrics/strategies` returns a valid response for a strategy with at least `MIN_TRADES_FOR_METRICS` synthetic closed trades in a MinIO fixture.

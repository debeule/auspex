# services/strategy

Strategy plugins (`auspex_strategy`) and the runtime that runs them.

## Commands

| Purpose | Command |
|---|---|
| Install | `uv sync` |
| Unit tests | `uv run pytest tests/unit -q` |
| Lint + types | `uv run ruff check . && uv run mypy src` |
| Image | `docker build -f services/strategy/Dockerfile -t auspex-strategy services` (from the repo root; the image installs `services/backtesting` from source) |

## Runtime (`auspex_strategy.runtime`)

| Component | What it does |
|---|---|
| `BacktestReplayRunner` | Replays corroborations in time order through `research`-or-above strategies; `paper`-or-above ones trade into `backtest` books. Returns a `BacktestResult` (intents per strategy, books, timing). |
| `StreamingRuntime` | Consumes `auspex.signals.corroborated` (group `auspex-strategy-runtime`) and runs `paper`-or-above strategies; checkpoints the offset to MinIO after each event. |
| `IsolatedDecider` | Wraps every `decide()`: a crash, a call past `STRATEGY_TIMEOUT_SECONDS` or an invalid intent is counted per strategy and never reaches another strategy. |
| `InputHealthMonitor` | Polls core-hub's `/api/v1/health/inputs` every `HEALTH_CHECK_INTERVAL_SECONDS`; pauses strategies that declare an unhealthy input. No answer counts as unhealthy. |
| `OverlapDetector` | Marks intents from different strategies on the same event, ticker and direction (`rationale.overlap_with`). |
| `LatencyTracer` | Records corroboration-to-intent latency; warns at startup when the median exceeds a strategy's known-at delay. |
| `PaperBroker` / `VirtualBook` | Fills approved intents at the next session's open (`FillModel`), exits on the holding rule or stop (`FillModel.stop_exit_price`), charges `CostModel` costs, converts P&L with `CurrencyConverter`. |
| `PassThroughRiskManager` | Approves every intent at `PASS_THROUGH_POSITION_EUR`; no risk checks. |
| `FunnelCounter` | Counts, per strategy version and mode, the events `decide()` ran on, the intents it produced and the intents risk approved. |

The known-at delay of each strategy comes from its registered hypothesis file (`primary_cell.known_at_delay_days`).

## State in MinIO (bucket `auspex-strategy`)

| Key | Content |
|---|---|
| `strategy/books/<strategy>/<mode>/trades.parquet` | Append-only book rows: `order`, `open`, `rejected`, `close`; each carries the `strategy_version` whose intent placed the order |
| `strategy/funnel/<strategy>/<mode>.json` | Funnel counts per version: `inputs_seen`, `intents`, `passed_risk` |
| `strategy/health/pauses.jsonl` | Pause start and end per strategy |
| `strategy/latency/distribution.jsonl` | Corroboration-to-intent latency per intent, with strategy and version |
| `strategy/checkpoints/auspex-strategy-runtime/<topic>.json` | Next offset per partition |

## Strategy metrics (`auspex_strategy.metrics`)

Computed on request from the books, funnel counters and latency log in MinIO and the price snapshots; nothing is stored and no strategy runs. Every figure is for one strategy version in one mode: a trade belongs to the version that opened it.

| Component | What it reports |
|---|---|
| `ActivityFunnel` | `inputs_seen` → `intents` → `passed_risk` → `filled` → `closed` |
| `TradeMetrics` | `hit_rate`, `avg_win_eur`, `avg_loss_eur`, `expectancy_eur` (with `bootstrap_ci_95`), `avg_holding_days`, `trades_per_year` |
| `ReturnMetrics` | Per-trade abnormal return vs XBI (market model, `[+1, +h]` sessions, in the trade's direction, net of costs): mean with `bootstrap_ci_95`, cumulative series, annualised `sharpe`, `deflated_sharpe` (a probability, per-trade Sharpe, `n_trials` from the hypothesis family's trial ledger), `max_drawdown_pct` |
| `BacktestPaperComparison` | Whether a forward book's mean abnormal return is inside the same version's backtest CI; outside sets `paper_tracking_deviation` |
| `CorrelationMatrix` | Pearson correlation of abnormal returns across versions, aligned on close dates |
| `LatencyMetrics` | p50/p95/p99 corroboration-to-intent latency and how many exceed the known-at delay |

Every group carries its sample size `n`. Below `MIN_TRADES_FOR_METRICS` closed trades a group reports `insufficient_data: true` and null statistics, never a number. `n_strategies_ever_tested` counts every (strategy, version) pair registered, recorded under `config/strategies/versions/` or booked.

## HTTP (port 8003)

`GET /health` returns `ok` with each strategy's failure count and pause state. `GET /metrics` exposes `auspex_strategy_decide_failures_total{strategy}`, `auspex_strategy_paused{strategy}` and `auspex_strategy_rejected_events_total`.

| Route | Returns |
|---|---|
| `GET /api/v1/metrics/strategies` | A `StrategyMetricsSummary` for every booked version and mode of each strategy that is not retired |
| `GET /api/v1/metrics/strategies/<name>/<version>` | That version's summaries, one per mode it has a book in; 404 if none |
| `GET /api/v1/metrics/correlation?mode=<mode>` | `strategy_versions` and the `matrix` for one mode (default `paper`) |

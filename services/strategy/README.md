# services/strategy

Strategy plugins (`auspex_strategy`) and the runtime that runs them.

## Commands

| Purpose | Command |
|---|---|
| Install | `uv sync` |
| Unit tests | `uv run pytest tests/unit -q` |
| Lint + types | `uv run ruff check . && uv run mypy src` |
| Kill switch | `uv run python -m auspex_strategy kill [--strategy <name>] [--reason <why>] [--reset]` (needs `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`; no Docker) |
| Image | `docker build -f services/strategy/Dockerfile -t auspex-strategy services` (from the repo root; the image installs `services/backtesting` from source) |

## Runtime (`auspex_strategy.runtime`)

| Component | What it does |
|---|---|
| `BacktestReplayRunner` | Replays corroborations in time order through `research`-or-above strategies; each event's `paper`-or-above intents go to risk together, and approved ones trade into `backtest` books (no fills when `broker=None`). With a `DecisionTracer`, every risk decision is traced. Returns a `BacktestResult` (intents per strategy, books, timing). |
| `StreamingRuntime` | Consumes `auspex.signals.corroborated` (group `auspex-strategy-runtime`) and runs `paper`-or-above strategies; checkpoints the offset to MinIO after each event. |
| `IsolatedDecider` | Wraps every `decide()`: a crash, a call past `STRATEGY_TIMEOUT_SECONDS` or an invalid intent is counted per strategy and never reaches another strategy. Names valid intents deterministically (strategy, version, corroboration, `as_of`, position), so a replay reproduces `intent_id`s. |
| `InputHealthMonitor` | Polls core-hub's `/api/v1/health/inputs` every `HEALTH_CHECK_INTERVAL_SECONDS`; pauses strategies that declare an unhealthy input. No answer counts as unhealthy. |
| `OverlapDetector` | Marks intents from different strategies on the same event, ticker and direction (`rationale.overlap_with`). |
| `LatencyTracer` | Records corroboration-to-intent latency; warns at startup when the median exceeds a strategy's known-at delay. |
| `PaperBroker` / `VirtualBook` | Fills approved intents at the next session's open (`FillModel`), exits on the holding rule or stop (`FillModel.stop_exit_price`), charges `CostModel` costs, converts P&L with `CurrencyConverter`. |
| `RiskManager` (protocol) | `review(intents)` returns one `RiskDecision` per intent: status (`APPROVED`, `REJECTED`, `PAUSED`), every check run (`RiskCheckRecord`), sizing and netting. |
| `PassThroughRiskManager` | Approves every intent at `PASS_THROUGH_POSITION_EUR`; no risk checks, so its decisions cannot be traced. The streaming runtime still uses it until books are valued (`PortfolioRiskReview` below then takes its place). A killed strategy's intents are dropped before risk. |
| `FunnelCounter` | Counts, per strategy version and mode, the events `decide()` ran on, the intents it produced and the intents risk approved. |

## Decision traces (`auspex_strategy.trace`)

| Component | What it does |
|---|---|
| `TraceRecord` | Frozen record of one intent's chain: participant documents (`DocumentRecord`: raw object key, extraction), corroboration key, strategy and code hash, rationale, risk checks and outcome, netting, sizing, and execution and P&L fields (empty until fills are traced). |
| `TraceValidator` | One rule set for backtest, paper and live: raises `TraceIncompleteError` naming each missing field. |
| `TraceStore` | Appends validated traces as JSONL; never rewrites a line. `read(strategy, mode, since=)`. |
| `DecisionTracer` | Builds a trace from a corroboration, a `RiskDecision` and the slot; looks up participant documents by `event_id`. |
| `TraceReplayer` | Replays archived events through one strategy and a risk stub; every field but `trace_id`, `approved_at` and `fill_time` matches the original. |

Only backtests are traced so far: paper and live need participant documents, ticker and source types from core-hub and a risk layer that runs checks (DECISIONS.md 2026-10-11).

The known-at delay of each strategy comes from its registered hypothesis file (`primary_cell.known_at_delay_days`).

## Risk (`auspex_strategy.risk`)

Every limit is an `.env` variable (`.env.example`, "Risk limits"); `RiskLimits.from_env` fails naming the variable when one is missing or looser than `config/hypotheses/protocol.yaml` `sizing` (the protocol file must match its registered hash). Shorts are rejected while the protocol's `instruments.shorts_enabled` is false.

| Component | What it does |
|---|---|
| `KellySizer` | Quarter Kelly (`KELLY_FRACTION`) on a win probability shrunk toward 0.5, from the strategy's closed trades; `FALLBACK_POSITION_PCT` below `MIN_TRADES_FOR_KELLY`; capped at `MAX_POSITION_PCT` per name. |
| Position limits | Per-strategy position count, one position per theme across strategies (`config/themes.yaml`; an unmapped ticker is rejected), the per-name cap across strategies, gross and net exposure. |
| `BinaryEventGuard` | No entry within `CATALYST_GUARD_DAYS` of a known catalyst, exit at the last close before one, unless the strategy declares that type in `trades_catalyst_types` (never for shorts). Catalysts from the catalyst date panel (`PanelCatalysts`: PDUFA, AdCom); readouts have no source yet. |
| `ShortGuard` | Borrow fee, short interest and days-to-cover ceilings on entry; hard stop and EUR loss cap as exit intents. |
| `DrawdownAndFlowLimits` | Daily loss limit (blocks the rest of the day), turnover ceiling, and a drawdown past `MAX_DRAWDOWN_PCT` turns the global kill switch on. |
| `KillSwitch` | Global or per-strategy flag in MinIO; set and reset from the command line. Open positions keep their own exits. |
| `risk.RiskManager` | `evaluate(intent, book, market)` runs drawdown, kill switch, sizing, position limits, catalyst guard, short guard, loss and turnover; the first failure rejects. `ApprovalDecision.checks` lists every check that ran. |
| `PortfolioRiskReview` | The runtime's `review()` over `RiskManager.evaluate`: one `RiskDecision` per intent (kill switch, drawdown and daily loss are `PAUSED`), each approval counted toward the next intent's limits. Needs a reader for the book and market state. |

## State in MinIO (bucket `auspex-strategy`)

| Key | Content |
|---|---|
| `strategy/books/<strategy>/<mode>/trades.parquet` | Append-only book rows: `order`, `open`, `rejected`, `close`; each carries the `strategy_version` whose intent placed the order |
| `strategy/funnel/<strategy>/<mode>.json` | Funnel counts per version: `inputs_seen`, `intents`, `passed_risk` |
| `strategy/health/pauses.jsonl` | Pause start and end per strategy |
| `strategy/latency/distribution.jsonl` | Corroboration-to-intent latency per intent, with strategy and version |
| `strategy/checkpoints/auspex-strategy-runtime/<topic>.json` | Next offset per partition |
| `strategy/traces/<strategy>/<mode>/traces.jsonl` | Decision traces (`backtest`, `paper`, `live`) |
| `strategy/killswitch/global.json`, `strategy/killswitch/<strategy>.json` | Kill switch flags |
| `strategy/killswitch/events.jsonl` | Every trigger and reset: reason, time, who |
| `strategy/risk/catalyst_holds.jsonl` | Entries and holds through a catalyst type the strategy declares |

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

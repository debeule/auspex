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

The known-at delay of each strategy comes from its registered hypothesis file (`primary_cell.known_at_delay_days`).

## State in MinIO (bucket `auspex-strategy`)

| Key | Content |
|---|---|
| `strategy/books/<strategy>/<mode>/trades.parquet` | Append-only book rows: `order`, `open`, `rejected`, `close` |
| `strategy/health/pauses.jsonl` | Pause start and end per strategy |
| `strategy/latency/distribution.jsonl` | Corroboration-to-intent latency per intent |
| `strategy/checkpoints/auspex-strategy-runtime/<topic>.json` | Next offset per partition |

## HTTP (port 8003)

`GET /health` returns `ok` with each strategy's failure count and pause state. `GET /metrics` exposes `auspex_strategy_decide_failures_total{strategy}`, `auspex_strategy_paused{strategy}` and `auspex_strategy_rejected_events_total`.

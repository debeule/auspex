# Strategy Runtime

**Status:** blocked
**Blocked by:**
1. `specs/strategy-framework.md` — `Strategy` ABC, `AsOfContext`, `TradeIntent`, `StrategyRegistry` must exist
2. `specs/market-simulation.md` — `FillModel`, `CostModel`, `CurrencyConverter` needed for virtual book P&L

**Branch:** `feature/strategy-runtime`

---

## Context

The strategy framework (previous spec) defines the plugin contract and the as-of context. This spec builds the machinery that runs strategies continuously and manages their virtual books. The runtime is the component that bridges the event stream (Kafka) to strategy execution and tracks performance per strategy in isolation.

Invariant 2 (core-hub sole writer to application DB) constrains where state is persisted. Virtual books, latency traces, and checkpoints are stored in MinIO — not Postgres — so the runtime writes no application-DB rows. Decision traces use the schema from the decision-trace spec and are stored in MinIO JSONL. See DECISIONS.md 2026-09-20 for the storage placement flag.

## What this builds

### `services/strategy/src/auspex_strategy/runtime/`

**`BacktestReplayRunner`**
- Accepts a sorted sequence of `CorroborationRecord` events (from a MinIO snapshot or the backtesting module's aligned output).
- Advances `as_of` event by event: for each event, constructs a `BacktestAsOfContext(as_of = corroborated_at + KNOWN_AT_DELAY_DAYS)`, calls each registered `research`-or-above strategy's `decide()`, collects intents.
- Hands intents to `RiskManager` (portfolio-and-risk spec) → `VirtualBook`. When portfolio-and-risk spec is not yet implemented, a pass-through stub is used.
- Strategies at `research` status run in replay mode only; no virtual book is updated.
- Produces a `BacktestResult` containing per-strategy intent lists and timing metadata.

**`StreamingRuntime`**
- Kafka consumer, consumer group `auspex-strategy-runtime`, topic `auspex.signals.corroborated`.
- For each consumed `CorroboratedSignal` event: constructs `LiveAsOfContext(as_of = corroborated_at + KNOWN_AT_DELAY_DAYS)`, runs all `paper`-or-above strategies.
- Strategies at `research` status do NOT run in streaming mode.
- **Isolation**: each strategy's `decide()` call is wrapped in an independent try/except. A crash, timeout (`STRATEGY_TIMEOUT_SECONDS` from `.env`), or invalid output (e.g. intent on a non-watched ticker) is caught, counted in `failure_counts[strategy_name]`, logged at ERROR level, and does not affect other strategies.
- Checkpoints consumer offset to MinIO after each processed event so restart resumes from the last committed position.

**`VirtualBook`**
- One instance per strategy per mode (paper/live-confirm/live-auto). Backed to MinIO as append-only Parquet (`strategy/books/<strategy_name>/<mode>/trades.parquet`).
- On receiving a filled intent (from `FillModel`): appends an open position row.
- On exit trigger (holding_rule fires or stop-loss reached; a stop fills via `FillModel.stop_exit_price`, worst price of the day on a binary event day): appends a closed position row with entry price, exit price, shares, costs (from `CostModel`), P&L in USD and EUR.
- `VirtualBook.snapshot()` → current open positions and closed trade history (read from Parquet).
- The real portfolio (live capital) is tracked as a separate `VirtualBook` with `mode=live` in addition to the per-strategy books; all fills are attributed back to the originating strategy book for comparison.

**`InputHealthMonitor`**
- Polls `GET /api/v1/health/inputs` on core-hub at `HEALTH_CHECK_INTERVAL_SECONDS` (from `.env`, default 60).
- Maps each `InputSource` enum to a health check result.
- For a strategy whose `declared_inputs` includes an unhealthy source: sets `paused = True` on that strategy's runner, emits no new intents until health recovers, records pause start and end in MinIO JSONL (`strategy/health/pauses.jsonl`).
- Local model host (`EXTRACTION_MODEL` with `backend: local`): connection-refused on the health check marks `InputSource.EXTRACTION_MODEL` as unhealthy. When the extraction pipeline stalls, no new corroborations form — the strategy sees no new events rather than stale events.

**`OverlapDetector`**
- Detects when two strategies' intents for the same event target the same ticker and direction.
- Flags the overlap in both intents' `rationale.overlap_with` field before passing to risk.
- An overlap is not a rejection; it is a signal that two strategies are making the same bet. Capital allocator (portfolio-and-risk) decides whether to net or stack them.

**`LatencyTracer`**
- Extracts `published_at` (= `corroborated_at` = max published_date of participants), `ingested_at` (from the CorroboratedSignal's `first_detected_at`), and `intent_time` (now at the point `decide()` returns).
- Appends to MinIO JSONL (`strategy/latency/distribution.jsonl`): `{corroborated_at, ingested_at, intent_time, latency_corroboration_to_intent_ms}`.
- This distribution feeds back into the evaluation-protocol's `KNOWN_AT_DELAY_DAYS` sensitivity analysis. If median latency exceeds `KNOWN_AT_DELAY_DAYS × 24h`, flag at startup.

### Trigger model and placement

The runtime is proposed to live in `services/strategy/` as a long-running Docker container with a Kafka consumer loop. It is NOT an Airflow DAG: Airflow owns ingestion cursors, but the strategy runtime reacts to Kafka events not a polling schedule. See DECISIONS.md 2026-09-20 for the trigger model flag.

### Same-event overlap detection note

In paper/live mode, if multiple strategies subscribe to `CORROBORATION_NEW` and the same corroboration event fires on the same tick, `OverlapDetector` flags all affected intents. They are all passed through the risk pipeline, and the capital allocator (portfolio-and-risk) nets opposing intents before order submission.

## Out of scope

Risk checking and position sizing (portfolio-and-risk spec). Decision trace format and storage (decision-trace spec). Broker connectivity and live order routing (session 3). Airflow DAG changes. Core-hub changes. New Kafka topics (the runtime is a consumer of `auspex.signals.corroborated`; any new producer topic is session 3 scope).

## Constraints

- Isolation is non-negotiable: a single crashing strategy must never crash the runtime or affect other strategies' books.
- Virtual books are append-only Parquet. Never delete or overwrite a trade row. Correction = a new offsetting row with `is_correction=True`.
- `STRATEGY_TIMEOUT_SECONDS` from `.env` (default 5): if `decide()` exceeds this, the call is interrupted (thread timeout or process pool), the failure is counted, and execution continues.
- `pytest-socket --disable-socket` across the unit suite. No live Kafka, no live core-hub, no live MinIO. All injected as fakes.
- Invariant 6: `HEALTH_CHECK_BASE_URL` from `.env`, not hardcoded.

## Required tests

In `tests/unit/test_strategy_runtime.py`:

- `test_research_strategy_does_not_run_in_streaming_mode` — `StreamingRuntime` initialised with a strategy at `status: research`; `StreamingRuntime.process(event)` skips it; no intents produced, no virtual book entry
- `test_paper_strategy_virtual_book_records_fill` — strategy at `status: paper`; `BacktestReplayRunner` processes one corroboration; intent produced; `FillModel` stub returns entry price; `VirtualBook.snapshot()` shows one open position
- `test_one_strategy_crash_does_not_affect_others` — two strategies registered; first raises `RuntimeError` in `decide()`; second produces a valid intent; runtime failure_counts[first] = 1; second's virtual book updated normally
- `test_stale_input_source_pauses_strategy` — `InputHealthMonitor` reports `EXTRACTION_MODEL` as unhealthy; strategy declaring `EXTRACTION_MODEL` in `declared_inputs` produces no intents; pause recorded in MinIO fixture; strategy without that declared input continues normally
- `test_intents_from_same_event_by_two_strategies_are_flagged_as_overlap` — two strategies both produce a LONG SRPT intent triggered by the same corroboration record; both intents have `rationale.overlap_with` populated with each other's `intent_id`
- `test_latency_trace_records_corroboration_to_intent_gap` — mock event with known `corroborated_at` and `first_detected_at`; `intent_time` captured; `LatencyTracer` entry contains all three timestamps and the computed gap
- `test_virtual_book_pnl_matches_market_simulation` — synthetic position opened at price A, closed at price B, N shares; `VirtualBook.closed_trades()` net P&L equals `FillModel` + `CostModel` calculation for same inputs
- `test_backtest_replay_is_deterministic` — replay same event sequence twice with identical strategy and context; intents are equal (fields, not `intent_id`s)

## Definition of done

```bash
cd services/strategy && uv run pytest tests/unit/test_strategy_runtime.py -q
```

Expected: 8 passed.

Then: a `BacktestReplayRunner` run against 10 synthetic corroboration events with `StructuralConvergenceStrategy` (stub returning one LONG intent per event) produces a `BacktestResult` and a non-empty `VirtualBook` snapshot without error.

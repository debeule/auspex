# Forward Paper Trading

**Status:** blocked
**Blocked by:**
1. `specs/strategy-runtime.md` — `StreamingRuntime`, `VirtualBook` (paper mode) and `BacktestReplayRunner` must exist.
2. Backtest look-ahead fix (in progress, first wave) — the paper ledger and the backtest must build events the same way (one event per corroboration record as of `corroborated_at`, NYSE calendar, after-close timing), or the forward results cannot be compared with the backtest.
3. ~~Pre-registration and kill criteria~~ — done 2026-10-07 (`config/hypotheses/`, `DECISIONS.md`): the hypotheses, trial ledger, clustered standard errors and the "forward check" kill criterion must be recorded before any forward trade is logged; a hypothesis edited after paper trading starts is a new trial.
4. ~~Realistic trading costs~~ — done (`specs/done/realistic-cost-model.md`): per-ticker spread (`SpreadEstimator`), FX conversion fee, average-daily-volume cap and gap risk. The capital tiers below are only meaningful with size-dependent costs.
5. Recommended, not a hard blocker: `specs/company-program-corroboration.md`. Paper trading can start on gene-target corroboration, but the audit expects company-program events to be the ones worth testing; starting earlier only buys calendar time.

**Branch:** `feature/forward-paper-trading`

---

## Context

The 2026-10-07 edge feasibility audit (row 7) calls forward paper trading "the only out-of-sample data nobody has seen, and it costs nothing but time". Every month it is not running is a month of unseen data lost. Its forward-check kill criterion: after 12 months of paper trading and at least 60 independent events, require a positive mean net abnormal return and clustered `t > 2` before any real capital; otherwise Auspex stays a research and risk tool.

What exists or is specified:
- `services/strategy` (`auspex_strategy`): `Strategy` ABC, `AsOfContext`, `TradeIntent`, `StrategyRegistry`, strategy `status` (`research` → `paper` → `live-confirm` → `live-auto`), `SubscriptionType.CALENDAR_TICK`.
- `specs/strategy-runtime.md`: `StreamingRuntime` consumes `auspex.signals.corroborated` and runs `paper`-or-above strategies; `VirtualBook` is append-only Parquet in MinIO per strategy and mode; runtime state lives in MinIO, not Postgres (Invariant 2). It does not define a daily close-out, a gap check, or a report.
- `specs/decision-trace.md`: full `TraceRecord`. This spec needs only the subset listed below and must not block on the full trace.
- `services/backtesting`: `PriceSnapshotStore` (MinIO Parquet), `MarketCalendar`, `CostModel`, `FillModel`, `CurrencyConverter`; `config/hypotheses/` with `verify_hypothesis()`.
- Daily price refresh: price snapshots are "fetch once" for history; the forward ledger needs each new session's close for its tickers, XBI and `EURUSD=X`.

## What this builds

Paper trading is the gate for real capital: its results decide whether any capital is justified and how much (the user's framing, 2026-10-07). So the ledger runs the same intents at several notional account sizes in parallel, and the report shows where fixed costs and capacity start to erode returns.

In `services/strategy/src/auspex_strategy/paper/`:

1. **`PaperLedger`** — append-only, one Parquet file per NYSE session in MinIO: `strategy/paper/ledger/{yyyy-mm-dd}.parquet`. Row kinds:
   - `intent` — every `TradeIntent` a `paper` strategy produced that session, approved or not: `strategy_name`, `strategy_version`, `hypothesis_id`, hypothesis registry hash, `as_of`, corroboration key `(entity_key, participants_hash)`, `raw_object_key`s of the participants, ticker, direction, intended entry session.
   - `fill` / `exit` — from `VirtualBook` (paper mode), with `FillModel` price, `CostModel` costs, and EUR P&L via `CurrencyConverter`.
   - `mark` — end-of-session mark-to-market of every open position.
   - `heartbeat` — exactly one per `paper` strategy per session, written even when nothing happened. A missing heartbeat is a gap.
   Every `fill`, `exit` and `mark` row carries a `capital_tier_eur`. Tiers come from `PAPER_CAPITAL_TIERS_EUR` in `.env` (default `10000,50000,250000`). Each tier is its own paper `VirtualBook` per strategy: the same intents, sized with `PositionSizer` for that tier's capital, filled and costed with the realistic cost model, so commission minimums, Belgian TOB, FX fees, spread and the ADV cap all scale as they would for real. An intent the ADV cap clips or rejects at a tier is recorded as such for that tier, never silently resized. `intent` and `heartbeat` rows are tier-independent.
   A file for a session is written once; a correction is a new row with `is_correction = true` in a later session's file.
2. **`DailyCloseOut`** — subscribed to `CALENDAR_TICK` after the NYSE close: refreshes the session's closes for open-position tickers, XBI and `EURUSD=X` through the existing price path, writes marks and heartbeats, and closes positions whose holding rule expired. Runs inside the strategy runtime container (the runtime is not an Airflow DAG; `DECISIONS.md` 2026-09-20).
3. **`LedgerGapDetector`** — lists NYSE sessions since the ledger start with a missing heartbeat for any `paper` strategy. Exposed as Prometheus gauges `auspex_paper_ledger_gap_sessions` and `auspex_paper_ledger_last_session_age_days` (alert in Grafana when the age exceeds 2 sessions).
4. **Hypothesis freeze check** — at startup and before each session's writes, every `paper` strategy's hypothesis must pass `verify_hypothesis()`; a modified hypothesis stops that strategy's ledger (logged, gap visible) rather than silently continuing under a changed definition.
5. **`scripts/paper_report.py`** — per hypothesis: ledger start date, sessions covered, gaps, events, independent events (clustered by ticker and month, the same clustering the pre-registration work defines), mean net abnormal return vs XBI (market model from the evaluation protocol), clustered t, and the forward-check verdict: `insufficient` (under 12 months or under 60 independent events), `pass`, or `fail`.
   **Per capital tier**, side by side: gross and net return, cost drag (fixed costs such as minimum commissions, and proportional costs such as TOB, FX and spread, shown separately), share of intents clipped or rejected by the ADV cap, and net abnormal return with clustered t. The report names the smallest tier where fixed costs stop dominating and the largest tier before capacity clipping cuts net return by more than a quarter (both read from the tier results, not extrapolated). The verdict is given per tier: a hypothesis can pass at €10k and fail at €250k.

## Out of scope

- Real orders or broker connectivity (live trading, session 3).
- Risk checks and sizing beyond the pass-through stub `strategy-runtime` already allows (`specs/portfolio-and-risk.md`).
- The full `TraceRecord` and `TraceValidator` (`specs/decision-trace.md`); the ledger's `intent` rows carry the chain of custody needed now.
- Changing hypotheses, kill criteria or the evaluation statistics (pre-registration work and `specs/evaluation-protocol.md`).
- Intraday marks.

## Constraints

- Invariant 2: no application-DB writes; ledger, marks and heartbeats live in MinIO.
- Invariant 9: sessions and timestamps in UTC; session dates from `MarketCalendar`.
- Invariant 14: intents reference documents by `event_id`/`raw_object_key`, never by a re-derived identity.
- Append-only: no ledger row is ever edited or deleted.
- Point-in-time: an intent's `as_of` is the runtime's known-at time; entry is the next session's open after `as_of`, using the same rule as the backtest (look-ahead fix). The ledger must never record a fill price from a session before the intent existed.
- `pytest-socket` blocks network in unit tests; Kafka, MinIO and prices are fakes.
- Invariant 6: schedule offsets, MinIO and price settings from `.env`.

## Required tests

In `services/strategy/tests/unit/test_paper_ledger.py`:
- `test_heartbeat_written_for_each_paper_strategy_on_a_session_without_events`
- `test_missing_heartbeat_is_reported_as_a_gap`
- `test_gap_gauges_report_gap_count_and_last_session_age`
- `test_close_out_refreshes_session_closes_for_open_tickers_xbi_and_eurusd`
- `test_rejected_intent_is_still_recorded_in_the_ledger`
- `test_entry_fill_is_next_session_open_after_intent_as_of` — intent after Friday's close → Monday open; Good Friday skipped
- `test_ledger_file_for_a_session_is_never_overwritten` — second write for the same session raises; a correction lands as a new row in a later file
- `test_open_position_is_marked_to_market_at_session_close`
- `test_position_closes_when_holding_rule_expires`
- `test_modified_hypothesis_stops_its_strategy_ledger` — registry hash mismatch → no rows for that strategy, gap reported, other strategies continue
- `test_research_status_strategy_writes_no_ledger_rows`
- `test_paper_report_verdict_is_insufficient_before_twelve_months_or_sixty_independent_events`
- `test_paper_report_verdict_requires_positive_mean_and_clustered_t_above_two`
- `test_each_capital_tier_gets_its_own_book_from_the_same_intents`
- `test_fixed_costs_take_a_larger_share_of_returns_at_the_smallest_tier` — same trade, €10k vs €250k; minimum commission share of cost is higher at €10k
- `test_adv_cap_clip_is_recorded_per_tier_not_silently_resized`
- `test_capital_tiers_are_read_from_env_with_documented_default`
- `test_paper_report_gives_a_verdict_per_capital_tier`

## Definition of done

```bash
cd services/strategy && uv run pytest tests/unit/test_paper_ledger.py -q --strict-markers
```

Expected: 18 passed.

Then: the runtime container runs on the stack with at least one `paper` strategy; after 5 consecutive NYSE sessions the ledger has 5 heartbeat files with no gaps and `scripts/paper_report.py` prints a report; the start date recorded in `DECISIONS.md`. The audit's "30 days without gaps" criterion is checked in a later session and recorded there; it is not a merge condition.

## Notes

- Capital tiers: €10k, €50k and €250k are defaults chosen because the user's capital is undecided; change them in `.env` before the ledger starts. Adding a tier later is fine (it starts its own forward record that day); removing one discards nothing.
- Why a heartbeat row: without one, "no events today" and "the job did not run" look identical, and a silent gap in forward data is unrecoverable.
- Which strategies go to `paper`: every hypothesis the pre-registration work keeps (H3 first per the audit triage). Logging intents for every registered hypothesis, including ones that would not be traded, is cheap and keeps the forward trial count honest.

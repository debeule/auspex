# Portfolio and Risk

**Status:** done
**Blocked by:**
1. Met: `specs/done/strategy-runtime.md` — `TradeIntent` flow and `VirtualBook` must exist
2. Met: `specs/done/market-simulation.md` — `CostModel`, `CurrencyConverter`, `PositionSizer` required

**Branch:** `feature/portfolio-and-risk`

---

## Context

The strategy runtime generates `TradeIntent`s from strategy decision functions. Before any intent becomes a real or virtual fill, it passes through the risk layer. This spec builds that layer: position sizing, exposure limits, short-specific guards, loss limits, and kill switches.

**Which strategies this covers.** Sizing, exposure limits and the binary-event guard here are written for event strategies. Portfolio hypotheses (`evaluation: portfolio`, such as H9) are sized by `EqualRiskSizer` and guarded by `CatalystGuard` in `specs/done/cross-sectional-portfolio-backtest.md`, and forward paper trading reuses those. `KillSwitch` and the loss limits apply to every strategy. `BinaryEventGuard` reads a `CatalystSource`: in production the point-in-time catalyst date panel (`specs/catalyst-date-panel.md`, PDUFA and AdCom dates). A hand-maintained catalyst file is ruled out by root `CLAUDE.md` ("Where work can run"); readout dates have no automated source yet (`DECISIONS.md` 2026-10-11).

Every limit is a configurable parameter with a test that verifies it is read from `.env`, not hardcoded. No defaults in source code — startup fails with a descriptive message if a required limit is absent from `.env`. See `.env.example`. Units: `*_PCT` limits on capital are fractions (0.03 is 3%); `MAX_BORROW_FEE_ANNUAL_PCT`, `MAX_SHORT_INTEREST_PCT` and `SHORT_HARD_STOP_PCT` are percentages (3.0 is 3%), the units of their sources.

**Pre-registered sizing ceilings.** `config/hypotheses/protocol.yaml` (registered 2026-10-07, before the backfill) fixes a `sizing` section: Kelly multiplier at most 0.25 (quarter Kelly), at most 5% of capital per name, at most one open position per correlated theme, and no holding through a known binary event unless the strategy trades that event type. Few, correlated, fat-tailed bets make full Kelly ruinous. The `.env` limits below may be set tighter than these ceilings, never looser: at startup the risk layer verifies the protocol file's hash with the hypothesis registry and fails, naming the variable, when an `.env` value exceeds its ceiling. `MIN_TRADES_FOR_KELLY` may not go below `sizing.min_trades_for_kelly`. While `instruments.shorts_enabled` is false, every short intent is rejected (`SHORTS_DISABLED`).

## What this builds

### `services/strategy/src/auspex_strategy/risk/`

**`KellySizer`**
- `size(intent, estimates, capital_eur, fx_rate, price_usd) → int` — fractional Kelly with shrinkage, floored to integer shares.
- Kelly fraction: `f = (p × (b + 1) − 1) / b` where `p` is win probability and `b` is mean win / mean loss, both estimated from the strategy's closed trade history (`VirtualBook.closed_trades()`).
- Shrinkage: blend toward the uninformed prior (`p_prior = 0.5, b_prior = 1.0`) using `KELLY_SHRINKAGE_FACTOR` from `.env` (recommended 0.5). `p_shrunk = p_prior + KELLY_SHRINKAGE_FACTOR × (p_estimated − p_prior)`. Shrinkage corrects the estimate; it is not the Kelly multiplier.
- Fractional Kelly: the sized fraction is `KELLY_FRACTION × f(p_shrunk, b)`, with `KELLY_FRACTION` from `.env` (recommended 0.25) and at most `sizing.max_kelly_fraction` (0.25).
- Cap: the sized amount is capped at `MAX_POSITION_PCT × total_capital_eur` (`MAX_POSITION_PCT` from `.env`, recommended 0.03, at most `sizing.max_position_pct` = 0.05).
- Final integer shares via `PositionSizer.size_shares()` from market-simulation spec. Raises `PositionTooSmallError` if result is 0.
- When trade history is below `MIN_TRADES_FOR_KELLY` (from `.env`, recommended 20, at least `sizing.min_trades_for_kelly` = 20), falls back to `FALLBACK_POSITION_PCT × total_capital_eur` so early-stage strategies can still size without a Kelly estimate.

**`PositionLimits`**
- Evaluated per intent against current book state.
- `MAX_POSITION_PCT` — a single position cannot exceed this fraction of total capital.
- `MAX_GROSS_EXPOSURE` — sum of absolute position sizes / total capital cannot exceed this.
- `MAX_NET_EXPOSURE` — (longs − shorts) / total capital cannot exceed this in either direction.
- `MAX_POSITIONS_PER_STRATEGY` — maximum number of concurrent open positions per strategy.
- `MAX_POSITIONS_PER_THEME` — maximum concurrent open positions across all strategies in tickers sharing a theme (at most `sizing.max_positions_per_theme` = 1). Themes come from `config/themes.yaml`, a ticker → theme map; the current 8 watched tickers are one theme. A ticker absent from the map is rejected with `check_name = "THEME_UNMAPPED"` rather than treated as uncorrelated.
- All from `.env`.

**`BinaryEventGuard`**
- `CATALYST_GUARD_DAYS` from `.env` (recommended 3): if a ticker has a known scheduled catalyst within this many calendar days, no new position is opened in that ticker.
- Catalysts come from a `CatalystSource`; `PanelCatalysts` reads the catalyst date panel by CIK. A ticker the source cannot answer for is rejected (`CATALYST_UNKNOWN`). Readouts are not guarded until they have an automated source.
- **Shorts**: the guard is mandatory for shorts and cannot be overridden per strategy.
- **Longs**: a strategy may enter or hold through a catalyst only when its parameters declare that catalyst's type in `trades_catalyst_types` (for example a strategy whose event is the readout itself). There is no blanket override. Every such entry or hold is appended to `strategy/risk/catalyst_holds.jsonl`, which the decision trace reads.
- Existing positions: when a catalyst is known within `CATALYST_GUARD_DAYS` of an open position in that ticker, and the owning strategy does not trade that catalyst type, the guard emits an exit intent at the last close before the catalyst date. This applies whether the catalyst was known at entry or appeared later.
- Catalyst entries carry a `type` field (`readout`, `pdufa`, `adcom`, `other`).

**`ShortGuard`**
- `MAX_BORROW_FEE_ANNUAL_PCT` from `.env` — short intents rejected if `CostModel.borrow_fee_annual_pct(ticker)` exceeds this (one flat `BORROW_FEE_ANNUAL_PCT` for every ticker; no per-ticker borrow data).
- `MAX_SHORT_INTEREST_PCT` from `.env` — short intents rejected if short interest as a percentage of shares outstanding exceeds this. Source: `ShortInterestStore` (FINRA), the period published by the day before. No data for the ticker → these checks are skipped with a WARNING.
- Shorts are rejected outright (`SHORTS_DISABLED`) while `protocol.yaml` `instruments.shorts_enabled` is false.
- `MAX_DAYS_TO_COVER` from `.env` — short intents rejected if days-to-cover exceeds this.
- `SHORT_HARD_STOP_PCT` from `.env` — per-trade hard stop-loss for short positions; auto-closes if price moves against by this percentage.
- `MAX_LOSS_PER_SHORT_EUR` from `.env` — absolute EUR loss cap per short position before forced closure.

**`DrawdownAndFlowLimits`**
- `DAILY_LOSS_LIMIT_EUR` from `.env` — if today's realised + unrealised P&L across all strategies drops below this (negative value), all new intents blocked for the rest of the trading day. Resets at next market open.
- `MAX_DRAWDOWN_PCT` from `.env` — if drawdown from peak total book value exceeds this, global kill switch is activated.
- `DAILY_TURNOVER_CEILING_PCT` from `.env` — total buys + sells today / total capital cannot exceed this.

**`KillSwitch`**
- `KillSwitch.trigger(reason, strategy_name=None)` — global if `strategy_name` is None; per-strategy otherwise.
- Effect: no new intents pass risk for the affected scope; open positions are NOT force-closed (position wind-down is the strategy's configured `exit_conditions`).
- State stored as a flag file in MinIO (`strategy/killswitch/global.json` or `strategy/killswitch/<strategy_name>.json`). `StreamingRuntime` checks it for each strategy before risk and drops a killed strategy's intents.
- CLI: `python -m auspex_strategy kill` (global) or `python -m auspex_strategy kill --strategy <name>`. Every trigger is recorded with `{reason, triggered_at, triggered_by}` in MinIO JSONL.
- Reset: `python -m auspex_strategy kill --reset [--strategy <name>]`. Also recorded.

**`RiskManager`**
- `RiskManager.evaluate(intent, book_state, market_state) → ApprovalDecision`
- Runs checks in order: drawdown (so a breach turns the global kill switch on even when a later check would reject the intent) `→ KillSwitch → sizing (KellySizer) → PositionLimits → BinaryEventGuard → ShortGuard (if SHORT) → daily loss and turnover`. First failure short-circuits and returns a rejected `ApprovalDecision` with the check name and inputs.
- `ApprovalDecision.checks` lists every check that ran, in order, as `(check_name, inputs_snapshot, passed)`, for the decision trace.
- `catalyst_exits(book, as_of)` and `short_exits(book, market)` return exit intents; nothing executes them until the risk layer is plugged into the runtime (out of scope below).
- An `ApprovalDecision` carries: `approved: bool`, `check_name` (first failure), `check_inputs` (the values that triggered the rejection), `sizing_result` (if approved), `adjusted_shares` (if capped by PositionLimits).

## Out of scope

Order execution and broker connectivity (session 3). Live price feed (risks use current price from `FillModel`'s most recent Parquet data for the trade day). CGT calculation (post-trade accounting). Readout dates (catalyst-calendar spec). Supplying the book and market state `PortfolioRiskReview` (the runtime's `review()` over `RiskManager.evaluate`) reads in the streaming runtime, and executing exit intents (with forward paper trading, which values the books; `DECISIONS.md` 2026-10-11).

## Constraints

- Every limit is read from `.env`. No default in source code. Startup fails loudly with the variable name if absent.
- `pytest-socket --disable-socket` across unit tests. No live calls.
- The `KillSwitch` CLI must work without Docker (direct `python -m` invocation) so it is reachable during an emergency even if the compose stack is degraded.
- Invariant 6: no credentials in source.

## Required tests

In `tests/unit/test_portfolio_and_risk.py`:

- `test_kelly_sizer_shrinks_estimate_toward_prior` — `p=0.9, b=2.0, KELLY_SHRINKAGE_FACTOR=0.5, KELLY_FRACTION=0.25` → `p_shrunk = 0.7`; sized fraction equals 0.25 × Kelly(0.7, 2.0) = 0.1375
- `test_kelly_fraction_above_protocol_ceiling_fails_startup` — `KELLY_FRACTION=0.5` → startup error naming `KELLY_FRACTION` and the ceiling 0.25
- `test_max_position_pct_above_protocol_ceiling_fails_startup` — `MAX_POSITION_PCT=0.10` → startup error naming `MAX_POSITION_PCT` and the ceiling 0.05
- `test_second_position_in_same_theme_is_rejected` — open SRPT long from strategy A; BEAM long from strategy B, same theme in `config/themes.yaml` → rejected with `check_name = "THEME_LIMIT"`
- `test_ticker_without_theme_is_rejected` — intent for a ticker absent from `config/themes.yaml` → rejected with `check_name = "THEME_UNMAPPED"`
- `test_open_position_is_exited_before_known_catalyst` — open SRPT long, `readout` catalyst added 2 days ahead, strategy does not declare `readout` → exit intent dated the last close before the catalyst
- `test_strategy_trading_the_catalyst_type_may_hold_through_it` — same setup, strategy declares `trades_catalyst_types: [readout]` → no exit intent; the hold is recorded in `strategy/risk/catalyst_holds.jsonl`
- `test_kelly_sizer_caps_at_max_position_pct` — full Kelly exceeds `MAX_POSITION_PCT × capital`; result equals `floor(MAX_POSITION_PCT × capital / fx / price)`
- `test_kelly_falls_back_below_minimum_trade_count` — fewer than `MIN_TRADES_FOR_KELLY` closed trades; sizing uses `FALLBACK_POSITION_PCT` instead of history-derived Kelly
- `test_gross_exposure_limit_rejects_intent_at_ceiling` — book at `MAX_GROSS_EXPOSURE`; new long intent → `ApprovalDecision.approved = False, check_name = "GROSS_EXPOSURE"`
- `test_net_exposure_limit_rejects_directional_excess` — net long at `MAX_NET_EXPOSURE`; another long intent → rejected
- `test_binary_event_guard_blocks_entry_within_catalyst_window` — catalyst known to the catalyst source for ticker SRPT within `CATALYST_GUARD_DAYS`; SRPT long intent → rejected with `check_name = "CATALYST_GUARD"`
- `test_short_guard_blocks_entry_above_borrow_fee_cap` — `CostModel` returns borrow fee above `MAX_BORROW_FEE_ANNUAL_PCT`; short intent → rejected
- `test_daily_loss_limit_blocks_all_intents_when_breached` — day P&L below `DAILY_LOSS_LIMIT_EUR`; any intent → rejected with `check_name = "DAILY_LOSS_LIMIT"`
- `test_drawdown_limit_triggers_global_kill_switch` — drawdown exceeds `MAX_DRAWDOWN_PCT`; `KillSwitch.is_active()` returns True; all subsequent intents rejected
- `test_global_kill_switch_blocks_all_strategies` — `KillSwitch.trigger("test")` called; `RiskManager.evaluate()` rejects all intents regardless of strategy
- `test_per_strategy_kill_switch_blocks_only_named_strategy` — kill strategy A; intents from strategy B still pass if other checks pass
- `test_kill_switch_reachable_from_cli_without_docker` — subprocess call `python -m auspex_strategy kill --reason test`; MinIO fixture contains the kill flag; `KillSwitch.is_active()` returns True

## Definition of done

```bash
cd services/strategy && uv run pytest tests/unit/test_portfolio_and_risk.py -q
```

Expected: 18 passed.

Then:
- `config/themes.yaml` maps every watched ticker to a theme.
- `.env.example` documents all 15+ limit variables with recommended starting values.
- `python -m auspex_strategy kill --help` prints usage.

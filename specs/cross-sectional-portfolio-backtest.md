# Cross-Sectional Portfolio Backtest

**Status:** ready
**Blocked by:**
1. Met in code: `specs/point-in-time-universe.md` (PR #21, #22) — monthly `UniverseSnapshot`s with `exited_on`, `exit_reason` and `price_coverage`. Runs on the stack need its first build.
2. Met: `specs/done/slow-signal-preregistration.md` — `protocol.yaml` (`portfolio_inference`, `portfolio_kill_criteria`, families, equal-risk default). A portfolio run passes `EvaluationProtocol.admit()` before it reads returns; `quarterly_trade_date()` and `select_component_variant()` apply H9's registered rules.
3. Soft: `specs/catalyst-date-panel.md` for the catalyst guard modes. The engine and the `none` guard work without it; guard tests use fixture dates.
4. Before any H9 or H10 run, not before the code: the first universe build on the stack. `config/universe/rules.yaml` already starts in 2014.

**Branch:** `feature/cross-sectional-portfolio-backtest`

---

## Context

The backtester in `services/backtesting` (`auspex_backtesting.backtest.runner`) replays **events**: one entry per corroboration, a fixed holding window, a per-event abnormal return. The 2026-10-07 edge research moved the alpha path to monthly **scores** over a universe (holdings composite, risk-factor change), which need a different engine: at each rebalance, rank every member, form a portfolio, hold it, pay the turnover, repeat.

Research report 2 adds the trade structure: a basket of 15 or more names at roughly equal risk instead of a few Kelly-sized positions (a −70% gap on a 12.5% position costs about 9% of capital; on a 5% position, 3.5%), no hold through a known catalyst, sector beta to XBI measured, and no shorts or options.

What exists:
- `market_sim/`: `MarketCalendar`, `FillModel`, `CostModel` (Fixed IBKR pricing, one `tob_rate`; PR #13 adds `SpreadEstimator`, FX fee, ADV cap), `CurrencyConverter`, `PositionSizer`.
- `prices/snapshot_store.py`: OHLCV Parquet in MinIO, read-only for backtests.
- Universe snapshots (point-in-time universe spec): `auspex-prices/universe/{rules_version}/{yyyy-mm}.parquet`.
- Catalyst calendar (`specs/catalyst-calendar.md`): `GET /api/v1/catalysts?ticker=&from=&to=&as_of=`.

## What this builds

In `services/backtesting/src/auspex_backtesting/portfolio/`:

1. **`ScoreSnapshot`** — the input contract every score produces: one Parquet per rebalance date, `auspex-prices/scores/{hypothesis_id}/{version}/{yyyy-mm-dd}.parquet`, columns `cik, ticker, score, known_at_max` (the latest known-at time of any input, which must be before the rebalance date's open), plus component columns. Written once, never overwritten. `ScoreSnapshot.validate()` rejects a row whose `known_at_max` is at or after the rebalance open.
2. **`PortfolioRule`** — from the hypothesis:
   - selection: `top_n` with hold bands (`enter_rank`, `exit_rank`; for example buy at rank ≤ 15, sell only below rank 30), `top_quintile`, or `exclude_bottom_quintile` (hold the universe minus the worst fifth). A hard cut is a band with `enter_rank == exit_rank`.
   - cadence: `monthly`, `quarterly_after_13f` (first NYSE session at least `offset_days` calendar days after each 13F deadline, 45 days after quarter end), or `semi_annual_after_13f`. Scores can be newer than the last trade date; trades happen only on cadence dates.
   - an optional exclusion filter from a second `ScoreSnapshot` (for example the most-changed quintile of the filing-text score): excluded names are not bought and held names in it are sold at the next trade date.
   Ties are broken by CIK so runs are deterministic.
3. **`EqualRiskSizer`** — weights proportional to 1 / trailing 60-session volatility (data before the rebalance date only), capped at the protocol's per-name ceiling, renormalised; fails if fewer than the protocol's `min_names` remain.
4. **`CatalystGuard`** — reads point-in-time catalyst dates (`specs/catalyst-date-panel.md`) as of each trade date. Modes, as the hypothesis declares:
   - `none`.
   - `skip_entry`: do not buy a name with a binary due before the next trade date. Held names stay.
   - `exit_and_reenter`: sell held names before a binary due before the next trade date, and buy back on the first session after it if still ranked inside the band. This costs an extra round trip, which is booked.
   - `exit_low_score_only`: like `exit_and_reenter`, but only for held names ranked outside the entry band.
   It reports names skipped or exited, and how many members had no catalyst data at all (a guard only works where dates exist).
5. **`PortfolioBacktest.run(hypothesis, universe_version, tier_eur) → PortfolioResult`** — monthly loop: target weights → orders at the first session's open after the rebalance date (the same next-open rule as the event backtest) → fills and costs from `FillModel` and `CostModel` per trade, sized at the capital tier → daily marks → month-end. A member that exits mid-month is closed at its last close; if its `exit_reason` is `delisted` or `deregistered` and the price series ends before `exited_on`, the missing part is booked at −30% (the universe spec's bound) and the month is flagged. Positions below the commission-derived minimum ticket are skipped and counted.
6. **`CostModel` commission schedules** — `IBKR_PRICING=fixed|tiered` (Tiered: $0.0035 a share, $0.35 minimum, plus pass-through fees), so the €10k tier is costed as a small account would actually be charged. TOB stays one rate for shares; ETF TOB classes are out of scope until an ETF is traded. Cost defaults follow the 2026-10-08 Belgian cost research: `FX_FEE_RATE` defaults to 0 for a USD-held account (conversions happen on deposit, not per trade), and `MIN_HALF_SPREAD_BPS` defaults to 10 for small-cap biotech instead of the large-cap 2. Both are `.env` values, changed in `.env.example` with a `DECISIONS.md` entry.
7. **`PortfolioResult`** — monthly gross and net return, turnover, yearly cost drag (round-trip cost × round trips per year), average holding period per name (the Belgian speculation-tax risk metric), return inside catalyst windows (±5 sessions around a known binary) versus other days, cost by component, number of names, excess over XBI and over the universe equal-weight, rolling 12-month beta to XBI, worst single-name month contribution, the share of net P&L from the top 5% of name-months, delisting-bound months, and skipped tickets. Evaluated through `protocol.yaml` `portfolio_inference` (Newey-West t, deflated Sharpe with the family trial count) and `portfolio_kill_criteria`, in-sample and holdout reported separately; the holdout is read only when the run is marked final, and a second final read is refused.
8. **`scripts/run_portfolio_backtest.py`** — runs a registered hypothesis at every tier in `PAPER_CAPITAL_TIERS_EUR` and writes the report; logs one trial per primary cell and variant to the family ledger.

## Out of scope

- Computing any score (the score specs write `ScoreSnapshot`s).
- An XBI hedge as a traded position. Beta is measured and reported; a hedge would be a short ETF leg, which the protocol disables. Revisit only if the beta report shows the basket's excess is mostly sector beta.
- Options, shorts, intraday fills.
- Live or paper execution (`specs/forward-paper-trading.md`).

## Constraints

- Point-in-time: universe, scores, volatility, catalysts and prices are read as of the rebalance date; nothing dated on or after the rebalance open enters a decision.
- Invariant 9: UTC; rebalance dates from `MarketCalendar` (first NYSE session of the month).
- Requirements §8: prices are read from snapshots only; a missing snapshot raises, never fetches.
- Deterministic: same snapshots and parameters give an identical result.
- `pytest-socket` in unit tests; synthetic price and score fixtures only.

## Required tests

In `services/backtesting/tests/unit/test_portfolio_backtest.py`:
- `test_planted_monthly_edge_is_recovered_net_of_costs` — synthetic universe where the top quintile earns +1% a month gross; net result within tolerance of 1% minus modelled costs
- `test_no_edge_universe_returns_minus_costs` — random scores; mean excess is negative by about the cost drag
- `test_score_known_at_or_after_rebalance_open_is_rejected`
- `test_orders_fill_at_first_session_open_after_rebalance_date`
- `test_exclude_bottom_quintile_turns_over_less_than_top_quintile` — same scores, lower turnover and cost
- `test_equal_risk_weights_are_inverse_trailing_volatility_capped_at_ceiling`
- `test_equal_risk_sizer_refuses_fewer_than_minimum_names`
- `test_trailing_volatility_uses_only_sessions_before_rebalance`
- `test_member_delisted_mid_month_is_closed_at_last_close`
- `test_delisting_with_missing_tail_is_booked_at_minus_thirty_percent_and_flagged`
- `test_members_without_catalyst_data_are_counted_not_assumed_clear`
- `test_tiered_pricing_charges_less_than_fixed_on_a_small_ticket`
- `test_ticket_below_commission_minimum_is_skipped_and_counted`
- `test_result_reports_excess_over_xbi_and_universe_equal_weight`
- `test_newey_west_t_uses_protocol_lag`
- `test_holdout_cannot_be_read_twice`
- `test_backtest_is_deterministic_for_identical_inputs`
- `test_each_capital_tier_is_costed_separately`
- `test_hold_band_keeps_a_name_until_it_falls_below_exit_rank`
- `test_hard_cut_turns_over_more_than_hold_band_on_the_same_scores`
- `test_quarterly_trade_date_is_first_session_offset_days_after_13f_deadline`
- `test_scores_newer_than_last_trade_date_do_not_trade_before_next_cadence_date`
- `test_skip_entry_guard_skips_buy_but_keeps_held_name_through_binary`
- `test_exit_and_reenter_guard_books_an_extra_round_trip`
- `test_exit_low_score_only_guard_exits_only_names_outside_entry_band`
- `test_exclusion_filter_sells_held_name_at_next_trade_date`
- `test_result_reports_average_holding_period_and_yearly_cost_drag`
- `test_catalyst_window_returns_are_split_from_other_days`
- `test_fx_fee_defaults_to_zero_and_min_half_spread_to_ten_bps`

## Definition of done

```bash
cd services/backtesting && uv run pytest tests/unit/test_portfolio_backtest.py -q --strict-markers && uv run pytest tests/unit -q
```

Expected: 29 passed; full unit suite green with a non-zero count.

Then: `services/backtesting/README.md` documents the portfolio engine and `ScoreSnapshot` contract; `.env.example` gains `IBKR_PRICING` and the new `FX_FEE_RATE` and `MIN_HALF_SPREAD_BPS` defaults.

## Notes

- The planted-edge test is the one that matters: if the engine cannot recover a known 1% a month, no real result from it means anything (report 3's done-when).
- Report 2's `GapRiskReport` is folded into `PortfolioResult` (worst name-month, top-5% share) instead of a separate class.

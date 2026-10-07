# Realistic Cost Model

**Status:** done

**Branch:** `feature/realistic-cost-model`

---

## Context

`services/backtesting/src/auspex_backtesting/market_sim/` (market-simulation spec) prices a round trip with a flat 50 bp half-spread, IBKR commission, Belgian TOB and borrow fee, and fills only at the open and close. The edge feasibility audit (2026-10-07, recommendation 10) found this understates micro-cap costs and overstates large-cap ones, and has no FX fee, no size limit against liquidity and no model of a stop gapping through on binary news days, where the largest returns sit.

## What this builds

- **`SpreadEstimator`** (`market_sim/liquidity.py`): per-ticker half-spread from daily close, high and low (Abdi and Ranaldo 2017) over the 21 sessions before the entry date.
- **`CostModel`**: optional `spread_estimator` and `entry_date`; with an estimator the spread is per ticker, floored at `MIN_HALF_SPREAD_BPS`. Without one it keeps the flat `SPREAD_BPS`. Adds an IBKR FX conversion fee (`FX_FEE_RATE`, 0.03% per leg).
- **`RoundTripCost.components()`**: per-component breakdown for per-trade reporting.
- **`VolumeCap`** (`market_sim/liquidity.py`): largest order as `MAX_ADV_FRACTION` (default 1%) of 20-session average daily volume; `PositionSizer.size_shares(..., max_shares=)` applies it.
- **`FillModel.stop_exit_price`**: a stop fills at the open on a gap through, at the stop on an intraday cross, and at the day's worst price on a binary event day.

## Out of scope

Market-impact curves beyond the volume cap. Per-ticker borrow rates. Wiring into the evaluation report (evaluation-protocol spec, `test_report_lists_cost_components_per_trade` added there) and the virtual book (strategy-runtime spec).

## Constraints

- MinIO snapshots only; unit tests run under `--disable-socket`.
- Point in time: spread and volume read only bars strictly before the entry date.
- Cost parameters come from `.env` (`FX_FEE_RATE`, `MIN_HALF_SPREAD_BPS`, `MAX_ADV_FRACTION` added).
- Existing market-simulation tests unchanged.

## Required tests

`services/backtesting/tests/unit/test_realistic_costs.py`:
- `test_spread_estimator_recovers_bid_ask_bounce_spread`
- `test_spread_estimator_ignores_bars_on_or_after_as_of_date`
- `test_spread_estimator_raises_without_two_prior_sessions`
- `test_cost_model_charges_per_ticker_spread_from_estimator`
- `test_cost_model_floors_estimated_spread_at_minimum`
- `test_cost_model_requires_entry_date_when_estimating_spread`
- `test_cost_model_round_trip_includes_fx_conversion_fee`
- `test_volume_cap_limits_shares_to_fraction_of_average_daily_volume`
- `test_volume_cap_rejects_position_when_cap_is_below_one_share`
- `test_stop_fills_at_open_when_price_gaps_through_it`
- `test_stop_fills_at_stop_price_on_an_ordinary_intraday_cross`
- `test_stop_fills_at_worst_price_of_the_day_on_a_binary_event_day`
- `test_stop_is_not_triggered_when_range_stays_clear`
- `test_spread_estimator_reads_negative_estimate_as_zero_and_cost_model_floors_it`
- `test_spread_estimator_skips_bars_with_missing_or_nonpositive_prices`
- `test_spread_estimator_raises_when_window_has_no_usable_bars`
- `test_cost_model_without_estimator_charges_flat_spread_and_ignores_entry_date`
- `test_cost_parameters_read_new_settings_from_env`
- `test_volume_cap_reads_fraction_from_env`
- `test_volume_cap_ignores_bars_on_or_after_as_of_date`
- `test_volume_cap_raises_without_volume_history`
- `test_volume_cap_rejects_position_when_stock_did_not_trade`
- `test_position_sizer_keeps_affordable_shares_when_below_volume_cap`
- `test_short_stop_fills_at_stop_on_intraday_cross_and_at_high_on_binary_day`
- `test_binary_day_stop_not_triggered_when_range_stays_clear`
- `test_stop_touching_exactly_at_low_fills_at_stop`
- `test_stop_raises_when_bar_is_absent`

Red before implementation: `ImportError: cannot import name 'SpreadEstimator' from 'auspex_backtesting.market_sim'`.

The edge-case tests were added in a second pass and three failed against the first implementation, each a real bug: a zero low raised `ValueError: expected a positive input, got 0.0` from `math.log`, an all-NaN close window returned NaN instead of raising `PriceDataAbsentError`, and an all-NaN volume window raised `ValueError: cannot convert float NaN to integer`. Bars with a missing or non-positive close, high or low are now skipped, and missing volume is dropped before averaging.

## Definition of done

```bash
cd services/backtesting && uv run pytest tests/unit/test_realistic_costs.py tests/unit/test_market_simulation.py -q
```

Expected: 38 passed (27 new, 11 market-simulation unchanged).

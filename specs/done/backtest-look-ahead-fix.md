# Backtest Look-Ahead Fix

**Status:** done
**Blocked by:** —
**Branch:** `feature/backtest-look-ahead-fix`

---

## Context

The edge feasibility audit (2026-10-07, recommendations 1 and 2) found two ways the backtest in `services/backtesting/` earned returns no live system could have earned:

1. `BacktestRunner._compute_variants` qualified a gene target on its whole signal history, and `metrics/calculator.py::_qualifying_results` then counted every member signal's return from that signal's own date, including signals published before the second source existed.
2. Timestamp hygiene: `alignment/aligner.py` used `USFederalHolidayCalendar` (wrong on Good Friday and Columbus Day), treated a date-only `published_date` (midnight UTC) as known the same day, entered at the open of a session that had already started, and `_window_returns` counted price rows while every hypothesis states holding periods in calendar days (`docs/strategy-research.md`).

`market_sim.MarketCalendar` (NYSE via pandas-market-calendars) and `FillModel` (entry at the open, exit at the close of `next_trading_day(entry + N calendar days)`) already exist.

## What this builds

- `aligner.entry_session(ts)`: the first NYSE session whose open comes after `ts` became public. A date-only `published_date` is known after that day's close. Used by `align()` and by the runner.
- `BacktestEvent` carries `published_date: datetime` instead of a caller-supplied `entry_date`; the runner derives entry from it.
- Window returns run from the entry session's open to the close of the first session on or after `entry + N` calendar days, matching `FillModel`. A missing entry or exit row gives `None` instead of the last available close.
- Variants are corroboration events: per `(gene_target, ticker)`, replay signals in publication order; a signal forms an event when the signals within the preceding 90 days (itself included) span two source types. `corroborated_at` is the latest participant's `published_date`, entry is `entry_session(corroborated_at)`, and the event carries its own window returns. A set sharing a participant with the previous event is an extension, not a new event.
- `MetricsCalculator.compute_both_variants` counts one return per event with weight above 0. Member signals no longer count.

## Out of scope

- Capturing EDGAR `acceptanceDateTime` in `connectors/sec_edgar.py` (the EDGAR press-release work owns that connector). Until then 8-Ks are date-only and enter the session after the filing date, which is conservative.
- `KNOWN_AT_DELAY_DAYS`, abnormal returns, trial ledgers (evaluation protocol).
- Delisted price data (point-in-time universe work).

## Constraints

- requirements §4: pairwise window is between signals, `|Δ published_date| ≤ 90 days`, distinct `source_type`s.
- requirements §4.1: `corroborated_at = max(participant.published_date)` is the only join field; supersession must not double-count backtest observations.
- requirements §6.7: `published_date` is the public date; non-public fields stay forbidden in `align()`.
- Invariant 9: UTC everywhere; session logic converts to ET only to compare with the NYSE open.

## Required tests

`tests/unit/test_alignment.py`:
- `test_good_friday_signal_enters_the_following_monday`
- `test_columbus_day_is_a_trading_session`
- `test_signal_during_market_hours_enters_at_the_next_sessions_open`
- `test_date_only_published_date_is_known_after_that_days_close`
- `test_date_only_published_date_on_a_friday_enters_monday`

`tests/unit/test_backtest.py`:
- `test_after_close_8k_enters_at_the_next_sessions_open`
- `test_holding_window_counts_calendar_days_not_price_rows`
- `test_holding_window_ending_on_a_closed_day_exits_at_the_next_session`
- `test_window_return_is_none_when_prices_end_before_the_exit_session`
- `test_corroboration_event_enters_after_its_latest_participant`
- `test_signals_more_than_90_days_apart_do_not_corroborate`
- `test_signal_joining_an_existing_corroboration_does_not_add_an_event`
- `test_disjoint_later_corroboration_on_the_same_target_is_a_new_event`
- `test_corroboration_events_are_per_ticker`
- `test_corroboration_event_return_runs_from_its_own_entry_not_the_earliest_member`

`tests/unit/test_metrics.py`:
- `test_member_signal_predating_its_corroboration_is_not_counted` (audit done-when: A on day 0, B on day 60 gives one event entering after day 60; A's return is excluded)
- `test_variant_metrics_are_empty_when_no_signal_carries_a_gene_target`
- `test_entity_only_metrics_independent_of_directionality` changed from `n == 2` (both members) to `n == 1` (one event)

Red before implementation: `ImportError: cannot import name 'entry_session'` in `test_alignment.py`; `TypeError: BacktestEvent.__init__() got an unexpected keyword argument 'published_date'` across `test_backtest.py` and `test_metrics.py`.

## Definition of done

```bash
cd services/backtesting && uv run pytest tests/unit -q
```

Expected: 66 passed.

# Price finality and split availability

**Status:** ready
**Branch:** `feature/price-finality-and-split-availability`

---

## Context

`services/backtesting/src/auspex_backtesting/prices/price_refresher.py` (`PriceRefresher.refresh`) keeps one append-only Parquet snapshot per ticker in `auspex-prices`. It downloads from Yahoo, falling back to Stooq, through `today + 1 day`, stores every row of a first download, and later appends only rows dated after the last stored bar. `_check_continuity` compares the last stored bar with the provider's bar for the same date, but only when the provider returned that date. `stack_bootstrap.py` runs a refresh at stack start, at any time of day.

`prices/splits.py` (`SplitStore.ensure`) fetches a ticker's split history once from Yahoo and stores it. When the request fails it stores nothing and returns an empty series. `universe/job.py` (`PreparedPrices.splits`) returns an empty series for a ticker with nothing stored, and `universe/market_cap.py` (`market_cap_usd`) then restates the share count by a factor of 1. `UniverseBuildJob.run` writes each missing month once and skips months already stored.

Found by the consolidated audit of 2026-10-10 (findings C2 and C3; the audit file is in the project's `audit/` folder) and checked against `develop` at `d615504`:

1. **A bar fetched during a session is kept for ever.** A refresh during NYSE hours can receive today's unfinished daily bar. It is stored, and the next refresh appends only later dates, so the final close never replaces it. (Reproduced with the exact functions: a stored close of 100 stayed after the provider supplied a final 101.)
2. **A missing overlap skips the continuity check.** When the provider's response does not include the last stored date, later bars are appended with no evidence they are on the same split basis. (Reproduced: a next-session close of 10 was appended after 100.)
3. **A failed split lookup reads as "no splits".** A ticker whose split request failed gets a market cap restated by 1. Across a 1:10 reverse split that is a tenfold cap error, which can move the ticker in or out of the universe. The month is then stored, and a later successful lookup never rebuilds it.

No price snapshot, split history or universe month has been built yet (the first build runs in `specs/first-run-on-stack-machine.md`), so nothing stored needs to be migrated or quarantined.

## What this builds

- **Only completed bars are stored.** `MarketCalendar` gains `session_close(d) -> datetime` (UTC, early closes included, from the pandas-market-calendars schedule). `PriceRefresher` takes a `now: Callable[[], datetime]` instead of `today`, and stores a bar only when it is complete: for a NYSE-listed ticker or ETF, its session closed at least `_SETTLE_DELAY` (2 hours) before `now`; for `EURUSD=X`, its UTC day ended at least `_SETTLE_DELAY` before `now`. Incomplete bars are dropped from the response before storing, on first download and on every refresh. A dropped bar is fetched again by the next refresh.
- **No overlap, no append.** A refresh appends only when the provider's response includes the last stored bar and that bar passes `_check_continuity`. A response without it raises `SnapshotDiscontinuityError` naming the ticker and the missing date, and stores nothing; the stored bars stay usable up to where they end, as they do today for a failed continuity check.
- **Split history has three states and a coverage date.** `SplitStore.ensure(ticker, through: date)` returns a `SplitHistory(status, ratios, covered_through)` with `status` one of `available` (one or more splits), `confirmed_empty` (the provider answered with none) or `unavailable` (the request failed; nothing new stored, retried on the next call). `covered_through` is the UTC date of the successful fetch, stored in the split file's metadata: the history vouches for splits up to that date and says nothing about later ones.
- **A read beyond coverage refreshes or fails.** When the stored history's `covered_through` is before `through`, `ensure` fetches again and stores the new history and date; if that fetch fails it returns `unavailable`, never the older history, so a stored "no splits" cannot hide a split that came after it. `SplitStore.load` returns the stored history with its `covered_through`, or `None`.
- **Market caps stay on the price snapshot's basis.** Each price snapshot records `adjusted_through` in its metadata: the UTC date of the first download, the day the provider's split adjustment was taken. (A later split re-adjusts the provider's history, so the overlap check refuses to extend the snapshot; its bars stay on the old basis.) `market_cap_usd` restates a share count only by splits dated after the count's `end` and on or before the snapshot's `adjusted_through`, and needs a split history with `covered_through` on or after `adjusted_through`; otherwise the history counts as `unavailable` for that month.
- **An unknown split history blocks the month, not the ticker's cap alone.** `PreparedPrices.splits` returns the `SplitHistory`, and `UniverseBuilder` treats an `unavailable` history for any ticker whose market cap the month needs as a build failure for that month: the month is not written, `BuildSummary` counts it under `split_unavailable` with the tickers named, and the next run builds it. A month is therefore only ever written from known split histories, and a failed-then-recovered lookup gives the same month as a clean run.

## Out of scope

- Versioned or content-addressed price snapshots (append-only stays the storage model).
- Corporate actions other than splits (dividends, spin-offs, ticker changes).
- Normalizing ownership ratios to a common share basis (`specs/ownership-share-basis.md`).
- Any change to universe rules, thresholds or the H9/H10 registrations.

## Constraints

- Invariant 9: UTC everywhere; `session_close` returns an aware UTC datetime, and the settle check compares aware datetimes.
- Invariant 6: `_SETTLE_DELAY` is a code constant (a provider property, not a deployment setting); no new `.env` entry.
- Unknown stays unknown: no code path turns an `unavailable` split history into a factor of 1 or a numeric cap.
- The universe build still fails one month at a time; months that do not need the failed ticker are still built.

## Required tests

Unit (`services/backtesting/tests/unit/`):

`test_price_refresh.py`
- `test_bar_of_an_open_session_is_not_stored` — now 15:00 New York on a session day; provider returns that day's bar; it is not in the stored snapshot
- `test_unfinished_bar_is_stored_after_the_session_settles` — the same day refreshed at 18:30 New York with a final close of 101 stores 101
- `test_early_close_session_settles_from_its_early_close` — the day after Thanksgiving, refreshed at 15:30 New York (close 13:00 + 2 h), stores that day's bar
- `test_session_close_is_utc_across_the_dst_change` — `session_close` for a March session before and after the US DST change returns 21:00 and 20:00 UTC
- `test_fx_bar_is_stored_only_after_its_utc_day_ends`
- `test_refresh_without_the_last_stored_bar_appends_nothing` — provider response starts the session after the last stored bar; `SnapshotDiscontinuityError`, snapshot unchanged
- `test_refresh_with_a_matching_overlap_appends_new_bars` — control

`test_universe_build.py`
- `test_split_lookup_failure_is_unavailable_and_not_stored` — `ensure` with the provider raising returns `unavailable`; no split file written
- `test_provider_answer_with_no_splits_is_confirmed_empty`
- `test_split_after_the_first_fetch_is_seen_by_a_later_read` — history fetched on day 1 with no splits; a 1:10 reverse split on day 5; `ensure(through=day 6)` refetches and returns `available` with the split and `covered_through` day 6
- `test_refetch_failure_beyond_coverage_is_unavailable_not_the_stored_history` — stored `confirmed_empty` through day 1, refetch raises, `ensure(through=day 6)` is `unavailable`
- `test_market_cap_ignores_splits_after_the_price_basis_date` — snapshot `adjusted_through` day 3, split on day 5: the cap uses no factor for it
- `test_split_history_older_than_the_price_basis_is_unavailable_for_market_cap`
- `test_month_needing_an_unavailable_split_history_is_not_written` — a member's history unavailable; the month is absent from the store and `BuildSummary.split_unavailable` names the ticker
- `test_month_built_after_split_recovery_equals_a_clean_build` — first run with the lookup failing, second run with it succeeding: the stored month equals one built by a single clean run, including a 1:10 reverse split member's cap
- `test_reverse_split_restates_the_share_count_to_the_price_basis` — control: shares 10M before a 1:10 reverse split, close on today's basis, cap uses 1M shares

## Definition of done

```bash
cd services/backtesting && uv run pytest tests/unit -q
cd services/backtesting && uv run ruff check . && uv run mypy src
```

Expected: the 16 tests above pass with the rest of the unit suite; no failures.

## Notes

- **Why block the month rather than store a cap of `None`:** a month written with an unknown cap is never rebuilt (`UniverseBuildJob` skips stored months), so the gap would be permanent. Blocking keeps the rebuild automatic. The cost is that one ticker whose lookup keeps failing holds back every month that needs it; `BuildSummary` names it, and the first-run spec records it in `DECISIONS.md` if it persists.
- **`_SETTLE_DELAY`:** two hours covers Yahoo's usual post-close revisions. A later provider revision of a settled bar is still caught by the overlap check, which then refuses to extend the series, as today.

# Short Interest Snapshots

**Status:** blocked
**Blocked by:** the first fetch on the stack machine (Definition of done, second block). All code and the 9 required tests are in `auspex_backtesting.short_interest`; what remains is a FINRA API credential (`docs/PREREQUISITES.md`) and running `scripts/fetch_short_interest.py` against FINRA, which cloud sessions cannot reach (`specs/first-run-on-stack-machine.md` step 3c, `DECISIONS.md` 2026-10-10 PENDING).

**Progress (2026-10-10):** FINRA's documentation read (`DECISIONS.md` 2026-10-10 VERIFIED): the API needs a credential, exchange-listed coverage starts June 2021 (so H9 runs its two-component variant by its pre-registered rule), and publication is the 7th business day after settlement. Publication dates come from that rule, with FINRA's published schedule rows winning (`config/short_interest/finra_calendar.csv`, `DECISIONS.md` 2026-10-10 CHOICE). Red before implementation: `ModuleNotFoundError: No module named 'auspex_backtesting.short_interest'` at collection. Eleven supporting tests (calendar, client, share counts, gaps) are in `tests/unit/test_short_interest_sources.py`. The derived share of shares outstanding and the change since the previous period are restated to one split basis with the ownership panels' split factors, or missing with a reason (`DECISIONS.md` 2026-10-11 CHOICE).

**Branch:** `feature/short-interest-snapshots`

---

## Context

Short interest is free, company-level and orthogonal to document signals (2026-10-07 edge feasibility audit, row 9, marked inferred). It is one of the three components of the holdings composite (H9, `specs/holdings-composite-score.md`), whose pre-registered component choice depends on how far back the history goes, so the first available settlement date must be reported. It is also an input the `portfolio-and-risk` spec lists as a deferred "short interest data auto-feed" for its short guard.

Unlike the other row-9 sources, short interest is a time series per ticker, published twice a month, not a document. It belongs with price data, not in the document pipeline: `services/backtesting` already snapshots OHLCV to MinIO bucket `auspex-prices` once and reads snapshots thereafter (requirements §8). This spec follows that pattern instead of adding a `SourceConnector`, which deviates from the audit's "new connectors and `sources.yaml` entries" for this one source; the reason is recorded in `DECISIONS.md` 2026-10-07.

Timing trap (same class as patent `filed_date`): FINRA short interest is reported as of a **settlement date** and published about a week later. The known-at date is the **publication date**. Joining on settlement date is look-ahead.

Source: FINRA publishes consolidated short interest for exchange-listed and OTC equities through its public data API (dataset `consolidatedShortInterest`, group `otcMarket`) and as downloadable files, with a published schedule of settlement and publication dates. Neither the endpoint, its authentication requirements, nor the history depth was reachable from the scoping session (proxy-blocked); verify at the start of the session and record the outcome in `DECISIONS.md`. If the API needs credentials, they go in `.env` (Invariant 6) and `docs/PREREQUISITES.md`.

## What this builds

In `services/backtesting/src/auspex_backtesting/short_interest/`:
- `ShortInterestFetcher` — fetches each settlement period's records for the configured tickers, with `settlement_date`, `publication_date` (from FINRA's published calendar, stored with the data), `short_interest_shares`, `average_daily_volume`, `days_to_cover`.
- `ShortInterestStore` — Parquet in MinIO `auspex-prices/short_interest/{ticker}.parquet`, written once per period and appended for new periods; never rewritten.
- `ShortInterestStore.as_of(ticker, date)` — the latest record whose `publication_date` is on or before `date`.
- Derived features: short interest as % of shares outstanding (shares from the universe spec when present, else null), and change since the previous period.
- `scripts/fetch_short_interest.py` CLI for the backfill. The scheduled refresh (endpoint and DAG) is `specs/slow-signal-data-refresh.md`; keep the fetch callable as one job so that spec can wrap it.

## Out of scope

- Daily short-sale volume (Reg SHO) files: different measure, separate decision.
- Borrow fees and availability (IBKR, see `docs/PREREQUISITES.md`).
- Hypotheses using short interest (registered separately).
- Wiring into `ShortGuard` (portfolio-and-risk), which reads `as_of()` when that spec is implemented.

## Constraints

- Invariant 9: UTC; dates are NYSE session dates.
- Point-in-time: `as_of()` must never return a record before its publication date.
- Requirements §8: fetch once, read snapshots thereafter.
- `pytest-socket` in unit tests; fixtures only.

## Required tests

In `services/backtesting/tests/unit/test_short_interest.py`:
- `test_as_of_returns_nothing_before_publication_date` — settlement 15th, publication 24th; `as_of(23rd)` returns the prior period
- `test_as_of_returns_the_latest_published_period`
- `test_days_to_cover_is_short_interest_over_average_daily_volume`
- `test_store_appends_new_periods_without_rewriting_existing_ones`
- `test_missing_ticker_in_a_period_is_recorded_as_absent_not_zero`
- `test_short_interest_pct_of_shares_is_null_when_shares_outstanding_unknown`
- `test_fetcher_stores_publication_date_from_the_finra_calendar_not_settlement_date`
- `test_period_already_stored_is_not_refetched`
- `test_coverage_report_states_first_available_settlement_date`

## Definition of done

```bash
cd services/backtesting && uv run pytest tests/unit/test_short_interest.py -q --strict-markers
```

Expected: 9 passed.

Then: one live fetch for the universe tickers (watchlist if the universe has not landed) from the earliest available period; history depth, the first available settlement date, and any gaps recorded in `DECISIONS.md`. `services/backtesting` README updated; `CLAUDE.md` naming table describes `auspex-prices` as market and reference data snapshots if the point-in-time universe has not already changed it.

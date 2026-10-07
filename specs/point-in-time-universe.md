# Point-in-Time Stock Universe

**Status:** blocked
**Blocked by:**
1. Backtest look-ahead fix (in progress, first wave) — backtest events must be built from corroboration records as of `corroborated_at` and windows must use the NYSE calendar before a wider universe is fed through the runner.
2. User decision on the scope choices listed under **Scope choices** below. Defaults are written in; the user confirms or changes them, and the outcome is recorded in `DECISIONS.md` as a CHOICE before implementation starts. The audit asks for this to be settled **before the historical backfill runs**, because the universe decides which companies' filings and trials get backfilled.

**Branch:** `feature/point-in-time-universe`

---

## Context

Backtests today run on 8 tickers chosen by hand in 2026 (`SRPT, SPRB, BEAM, CRSP, CAPR, ABVX, RCKT, QURE`; `DECISIONS.md` 2026-08-15, `WATCHED_TICKERS` in `.env.example`, now persisted as the user's watchlist by the watchlist-backend spec). The 2026-10-07 edge feasibility audit rated this fatal: hindsight selection, one correlated theme (gene therapy and editing), and an effective sample far below the event count. Without a wider, rules-based universe no test reaches `t > 3` (audit row 8, "inferred").

What exists in `services/backtesting` (`auspex_backtesting`):
- `prices/price_fetcher.py` — yfinance with a Stooq fallback; `prices/snapshot_store.py` writes OHLCV Parquet to MinIO bucket `auspex-prices` ("fetch once, then never again", requirements §8).
- `market_sim/universe.py` — `TradableUniverse.validate(tickers, start, end)` fails a backtest up front when a ticker's snapshot does not span the requested range. A name that delists mid-window fails this check today.
- `market_sim/calendar.py` — `MarketCalendar` (NYSE sessions).
- `backtest/runner.py` — `_window_returns` silently uses the last available close when price data runs out (audit survivorship row, `runner.py:164`), so a delisted or acquired name gets a truncated return with no error.
- `scripts/fetch_prices.py` — CLI over `PriceFetcher`.
- `docs/PREREQUISITES.md` — "Delisted ticker price data source" is open.

SEC data available without a key (descriptive `User-Agent` required, 10 req/s aggregate across `*.sec.gov`, known trap):
- `https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip` — every filer's submissions JSON: `sic`, `exchanges`, current `tickers`, `formerNames`, and the filing list (form type, filing date, acceptance time). Covers inactive filers.
- `https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip` — XBRL facts, including `dei:EntityCommonStockSharesOutstanding` with the date each value was reported.
- Bulk archives avoid tens of thousands of per-company requests against the SEC rate limit. Both URLs must be re-verified at the start of the session; record the check in `DECISIONS.md`.

## What this builds

1. **Universe rules file** `config/universe/rules.yaml` (versioned like a hypothesis: any edit after the first backtest bumps `version` and is a new trial): SIC codes, exchanges, market-cap floor, liquidity floor, rebalance frequency (monthly), and the window.
2. **`auspex_backtesting/universe/`**
   - `ListingHistory` — derives, per CIK, listing entry and exit dates from filings: entry at the first exchange registration (`8-A12B`) or IPO prospectus (`424B4`), exit at the delisting notice (`25-NSE`/`25`) or deregistration (`15-12B`, `15-12G`). Ticker history from the filing headers where present, else the current ticker stamped `ticker_source = 'current'`.
   - `MarketCapEstimator` — shares outstanding as last reported **on or before** the evaluation date (XBRL fact filed date, never period end) × that day's close.
   - `UniverseBuilder.build(month) → UniverseSnapshot` — members at the first NYSE session of the month that satisfy every rule using only data known on that date. Each member row: `cik, ticker, name, sic, exchange, market_cap_usd, median_dollar_volume_20d, entered_on, exited_on (nullable), exit_reason (delisted | acquired | deregistered | null)`.
   - Snapshots written to MinIO `auspex-prices/universe/{rules_version}/{yyyy-mm}.parquet` and never overwritten (a rules change writes under a new version).
3. **Delisted-name price coverage.** `scripts/build_universe.py` fetches price history for every member (including delisted ones) through the chosen source, writes snapshots through the existing `PriceSnapshotStore`, and prints a coverage report: members, members with full price history, members with partial history and why.
4. **Backtest integration.**
   - `TradableUniverse` accepts membership spans: a ticker is validated over `[entered_on, exited_on]`, not the full backtest range.
   - `_window_returns` stops silently truncating: a window that runs past a member's last price ends at the last close with `exit_reason` set from the universe row, and the result is counted separately in the report. A window that runs out of data for any other reason raises `PriceDataAbsentError`.
   - The backtest takes its tickers from the universe snapshot for the event's month, not from `WATCHED_TICKERS` or the watchlist. Events on companies outside the universe that month are dropped and counted.
5. **Backfill scope file.** `scripts/build_universe.py --export-backfill-scope` writes the union of members over the backfill window (CIKs, tickers, names) to `config/universe/backfill_scope.yaml`, which the historical-backfill spec reads to scope company-level sources.

## Scope choices

The findings leave these open. Defaults in **bold**; confirm or change before implementation.

| Choice | Default | Alternatives | Why it matters |
|---|---|---|---|
| SIC codes | **2834, 2836, 8731** | 2834 and 2836 only (the audit's list) | Many clinical-stage biotechs file under 8731 (commercial biological research); leaving it out drops a large share of small biotechs. |
| Exchanges | **NYSE, Nasdaq, NYSE American** | add OTC | OTC names are untradeable at a useful size and have the worst price data. |
| Market-cap floor (at rebalance) | **$50M** | $100M, $300M | Lower floors add under-covered names (where an edge might exist) and costs. |
| Liquidity floor | **20-day median dollar volume ≥ $500k** | $250k, $1M | Ties into the cost model's ADV cap (1 to 2% of ADV per trade). |
| Market-cap ceiling | **none** (a ceiling is tested as a pre-registered subgroup) | $2B, $5B | The audit suggests a niche big funds skip; making it a subgroup keeps both readings. |
| Delisted price source | **free first**: yfinance + Stooq, measure coverage; if under 90% of delisted members have full history, buy one month of a paid vendor with delisted US equities, snapshot once, cancel | paid from the start; accept the gap | A missing delisted name biases results upward. "Fetch once" means a single paid month is enough. |
| Backfill breadth | **company-scoped for EDGAR and ClinicalTrials.gov** (filings by universe CIK; trials by universe lead sponsor), topic-scoped (current vocabulary) for bioRxiv, PubMed and patents | topic-scoped for all sources (smaller, as today) | A universe of several hundred names multiplies 8-K and trial volume; on the 24 GB laptop this adds roughly one to two days of extraction (inferred, to be replaced by the backfill dry run). |

## Out of scope

- Changing ingestion connectors or `sources.yaml` to filter by universe (the historical-backfill spec reads `backfill_scope.yaml`; live ingestion scoping is a separate change).
- Removing the user's watchlist. The watchlist stays as the user's curated view in the dashboard; it no longer defines the backtest universe.
- Point-in-time SIC reclassification (SEC publishes current SIC only; a reclassified company is classified by today's code, recorded as a known limitation).
- Factor exposures and sector neutralization.

## Constraints

- Invariant 6: SEC `User-Agent` and any vendor key come from `.env`; no URLs in source beyond the documented public SEC endpoints in config.
- Invariant 9: all dates UTC; rebalance date is the first NYSE session of the month per `MarketCalendar`.
- Invariant 15: test-first.
- Point-in-time rule: every field used to admit a member on date D must have been public on or before D (XBRL `filed` date, filing acceptance time). Period-end dates are never used as known-at dates (the same trap as patent `filed_date`).
- SEC rate limit: bulk archives only for the build; any per-company request goes through the shared rate limiter at ≤ 5 req/s.
- Requirements §8: every price series is snapshotted once and read from MinIO thereafter.
- `pytest-socket` blocks network in unit tests; SEC and price data come from fixtures.

## Required tests

In `services/backtesting/tests/unit/test_universe.py`:
- `test_member_admitted_only_with_data_public_on_rebalance_date` — shares-outstanding fact filed the day after rebalance is not used; the prior fact is
- `test_company_below_market_cap_floor_is_excluded`
- `test_company_below_liquidity_floor_is_excluded`
- `test_company_with_excluded_sic_code_is_excluded`
- `test_delisted_company_is_a_member_until_its_delisting_notice` — `25-NSE` accepted mid-month: member in that month's snapshot, `exited_on` set, absent from the next
- `test_ipo_company_enters_on_first_rebalance_after_listing`
- `test_snapshot_is_written_under_rules_version_and_never_overwritten`
- `test_universe_build_is_deterministic_for_the_same_inputs`
- `test_tradable_universe_validates_delisted_ticker_over_its_membership_span_only`
- `test_window_running_past_delisting_ends_at_last_close_with_exit_reason`
- `test_window_running_out_of_data_without_a_delisting_raises`
- `test_backtest_drops_and_counts_events_on_companies_outside_the_universe`
- `test_backfill_scope_export_is_the_union_of_members_over_the_window`

## Definition of done

```bash
cd services/backtesting && uv run pytest tests/unit/test_universe.py -q --strict-markers
```

Expected: 13 passed.

Then:
- `scripts/build_universe.py` run for the backfill window on the stack machine; member count per month, delisted count, and price coverage report recorded in `DECISIONS.md`.
- `config/universe/backfill_scope.yaml` committed.
- `CLAUDE.md` naming table: `auspex-prices` described as "market and reference data snapshots (OHLCV, universe)".
- `services/backtesting` README and `docs/PREREQUISITES.md` updated (delisted price source resolved or its gap stated).

## Notes

- Effort: the largest second-wave package (audit: L). If the session runs long, split `ListingHistory` + `UniverseBuilder` (items 1–2) from the backtest integration (item 4).
- Effective sample: a wider universe adds events, but biotech names still co-move. Clustered standard errors (pre-registration work, first wave) remain necessary; this spec does not replace them.
- Ticker history is the weakest link: SEC's current `tickers` field is empty for most delisted filers. Filing headers and the price vendor's delisted symbol list are the two fallbacks; unresolved members are listed in the coverage report, never silently dropped.

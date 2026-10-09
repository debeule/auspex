# backtesting

Price snapshots, the point-in-time stock universe, market simulation and the backtest runner (`auspex_backtesting`).

## Point-in-time universe

`auspex_backtesting.universe` builds, for every month in the window of `config/universe/rules.yaml`, the list of US biotechs that were listed and tradeable on that month's first NYSE session, using only data public before that session opened. Delisted and acquired companies stay in the months they were listed.

| Rule (version 1) | Value |
|---|---|
| SIC codes | 2834, 2836, 8731 (SEC's current code) |
| Exchanges | NYSE, Nasdaq, NYSE American |
| Market cap | ≥ $50M: last share count filed before the rebalance × the last close before it, restated through later splits |
| Liquidity | median close × volume over the 20 sessions before the rebalance ≥ $500k |
| Window | from 2014-01, monthly, to the current month |

One universe serves every study: the slow-signal study reads it from 2014, the event backfill from `BACKFILL_SCOPE_START`. The build refuses a `PRICE_HISTORY_START` later than 45 days before the window (HTTP 409).

Inputs are SEC's nightly bulk archives (filer submissions and XBRL company facts, two downloads instead of per-company requests) and the price snapshots in `auspex-prices`, fetched from Yahoo, then Stooq. Listing spans come from exchange registrations, delisting notices and deregistrations. A delisted company's ticker comes from its inline XBRL report name (2019 on) or, before that, from the XBRL instance named in its last report's filing index (one request per such company, paced under SEC's limit, `SEC_ARCHIVES_URL`); `DECISIONS.md` (2026-10-08, point-in-time universe) records how each edge case is decided.

Stored in the `auspex-prices` bucket under `universe/{rules_version}/`:

| Object | Written |
|---|---|
| `{yyyy-mm}.parquet` | once per month; never overwritten |
| `rules.yaml` | on the version's first build; a different file under the same version is refused |
| `coverage.json` | every build: members, how many have complete prices, and every member without, with the reason |
| `listings.parquet` | every build: every listing span as now known, exits included; backtests read exits and coverage from it |
| `backfill_scope.yaml` | every build: the union of members from `BACKFILL_SCOPE_START` (default 2024-01) to the latest month, for the historical backfill |

Each member row: `cik, ticker, ticker_source (current | filing | unresolved), name, sic, exchange, market_cap_usd, median_dollar_volume_20d, entered_on, exited_on, exit_reason (delisted | acquired | deregistered), price_coverage (complete | partial | none), coverage_note`.

The stack builds it by itself: the `auspex_universe_build` DAG calls `POST /universe/build` on the price service in the first week of every month and on the first start. Measured price coverage of delisted members is recorded in `DECISIONS.md` after the first build.

### In backtests

`load_membership(UniverseStore(minio), rules_version)` gives a `UniverseMembership`; pass it to `BacktestRunner.run` or `run_backtest(..., universe=...)`. Then:

- only events on companies that were members in their entry month are traded; the rest are counted in `BacktestReport.outside_universe`;
- a window past a delisted member's last price ends at that close, with `WindowReturn.exit_reason` set;
- a window the prices do not cover is `excluded` and counted by exit reason; a fully priced, still-listed member running out of data raises `PriceDataAbsentError`;
- each `MetricsReport` carries a `survivorship` summary: excluded count and share by exit reason, a bounded mean that puts excluded events back at −30% (delisted, deregistered) or 0% (acquired) over their unpriced part, and `survivorship_gap = material` above 10% excluded.

## Catalyst date panel

`auspex_backtesting.catalysts` holds the scheduled binary events a backtest may know about on a given day: PDUFA dates and FDA advisory committee meetings, each as it was disclosed at the time. No LLM is involved; both sources are worded regularly enough for fixed rules.

| Source | What is read | Known at |
|---|---|---|
| 8-K press releases | Each universe company's 8-Ks with Item 7.01 or 8.01, found in EDGAR's quarterly `master.idx` (`SEC_FULL_INDEX_URL`); the filing index (`SEC_ARCHIVES_URL`) gives the items, acceptance time and Exhibit 99.1. Sentences naming `PDUFA`, `target action date` or `goal date` with a date | the 8-K's acceptance time |
| Federal Register | FDA notices titled "... Advisory Committee; Notice of Meeting" (`FEDERAL_REGISTER_API_URL`, no key): meeting date, committee, and the agenda's application, product and sponsor. Cancellations and postponements are counted, not applied | 06:00 Eastern on the publication date |

Each date keeps the precision it was written at: `day`, `month`, `quarter` or `half` ("second half of 2027" is July to December, never a day). Each row keeps the sentence or agenda it came from. A sponsor is matched to a universe company by name; a notice matching none or several is stored with no CIK and counted, never assigned.

Stored in the `auspex-prices` bucket:

| Object | Written |
|---|---|
| `catalysts/{edgar,federal_register}/{yyyy}q{q}.parquet` | rows by quarter of disclosure; rows are only added, a revision is a new row |
| `catalyst-documents/...` | every index page, exhibit and notice read, so no document is fetched twice; the indexes of a quarter still in progress are not kept |

`CatalystPanel(minio).as_of(cik, at)` gives the upcoming catalysts known at `at`: per catalyst (rows of a company sharing an application number or product name), the latest row disclosed by then. `binaries_between(cik, start, end, as_of)` gives those whose period overlaps a window, for the catalyst guard. Both take a timezone-aware time.

Requests to SEC are paced at 5 per second with `SEC_USER_AGENT`, Federal Register at 1 per second. A 403 or 429 ends the run without retrying, since retrying extends an SEC block; running again continues from the stored documents. Coverage is partial by nature: not every company names its PDUFA date in an 8-K, and the build's coverage report counts members with no catalyst data.

## Price service metrics

`GET /metrics` on the price service (port 8001, scraped by Prometheus as job `price-service`):

| Metric | Meaning |
|---|---|
| `auspex_price_refresh_runs_total{outcome}` | `/prices/refresh` calls; `failed` when any ticker failed |
| `auspex_price_tickers_refreshed_total` / `auspex_price_tickers_failed_total` | tickers per outcome |
| `auspex_price_refresh_last_success_timestamp_seconds` | last refresh in which every ticker refreshed; absent until the first one |
| `auspex_price_refresh_sessions_since_success` | NYSE sessions strictly between that success (or the service's start) and today, UTC; Grafana's **Price Refresh Stale** fires at 2 |

## Scripts

| Script | Purpose |
|---|---|
| `scripts/fetch_prices.py` | Snapshot prices for tickers outside the watchlist, once |
| `scripts/build_universe.py` | Run a universe build outside the schedule, or `--export-backfill-scope PATH` to copy the backfill scope out of MinIO |
| `scripts/build_catalyst_panel.py` | Build or extend the catalyst panel (`--since`, default 2014-01-01; `--until`, default today) and print its coverage: catalysts per year, members with any catalyst, unmatched advisory committee notices, PDUFA hits by precision. Needs the universe built first |
| `scripts/register_hypothesis.py` | Register a hypothesis file in the pre-registration ledger |

## Commands

| Purpose | Command |
|---|---|
| Install | `uv sync` |
| Unit tests | `uv run pytest tests/unit -q` |
| Lint | `uv run ruff check .` |

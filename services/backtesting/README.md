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

Inputs are SEC's nightly bulk archives (filer submissions and XBRL company facts, two downloads instead of per-company requests) and the price snapshots in `auspex-prices`, fetched from Yahoo, then Stooq. Listing spans come from exchange registrations, delisting notices and deregistrations; `DECISIONS.md` (2026-10-08, point-in-time universe) records how each edge case is decided.

Stored in the `auspex-prices` bucket under `universe/{rules_version}/`:

| Object | Written |
|---|---|
| `{yyyy-mm}.parquet` | once per month; never overwritten |
| `rules.yaml` | on the version's first build; a different file under the same version is refused |
| `coverage.json` | every build: members, how many have complete prices, and every member without, with the reason |
| `listings.parquet` | every build: every listing span as now known, exits included; backtests read exits and coverage from it |
| `backfill_scope.yaml` | every build: the union of members over the window, for the historical backfill |

Each member row: `cik, ticker, ticker_source (current | filing | unresolved), name, sic, exchange, market_cap_usd, median_dollar_volume_20d, entered_on, exited_on, exit_reason (delisted | acquired | deregistered), price_coverage (complete | partial | none), coverage_note`.

The stack builds it by itself: the `auspex_universe_build` DAG calls `POST /universe/build` on the price service in the first week of every month and on the first start. Measured price coverage of delisted members is recorded in `DECISIONS.md` after the first build.

### In backtests

`load_membership(UniverseStore(minio), rules_version)` gives a `UniverseMembership`; pass it to `BacktestRunner.run` or `run_backtest(..., universe=...)`. Then:

- only events on companies that were members in their entry month are traded; the rest are counted in `BacktestReport.outside_universe`;
- a window past a delisted member's last price ends at that close, with `WindowReturn.exit_reason` set;
- a window the prices do not cover is `excluded` and counted by exit reason; a fully priced, still-listed member running out of data raises `PriceDataAbsentError`;
- each `MetricsReport` carries a `survivorship` summary: excluded count and share by exit reason, a bounded mean that puts excluded events back at −30% (delisted, deregistered) or 0% (acquired) over their unpriced part, and `survivorship_gap = material` above 10% excluded.

## Scripts

| Script | Purpose |
|---|---|
| `scripts/fetch_prices.py` | Snapshot prices for tickers outside the watchlist, once |
| `scripts/build_universe.py` | Run a universe build outside the schedule, or `--export-backfill-scope PATH` to copy the backfill scope out of MinIO |
| `scripts/register_hypothesis.py` | Register a hypothesis file in the pre-registration ledger |

## Commands

| Purpose | Command |
|---|---|
| Install | `uv sync` |
| Unit tests | `uv run pytest tests/unit -q` |
| Lint | `uv run ruff check .` |

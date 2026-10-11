# backtesting

Price snapshots, the point-in-time stock universe, SEC ownership panels, market simulation and the backtest runner (`auspex_backtesting`).

## Point-in-time universe

`auspex_backtesting.universe` builds, for every month in the window of `config/universe/rules.yaml`, the list of US biotechs that were listed and tradeable on that month's first NYSE session, using only data public before that session opened. Delisted and acquired companies stay in the months they were listed.

| Rule (version 1) | Value |
|---|---|
| SIC codes | 2834, 2836, 8731 (SEC's current code) |
| Exchanges | NYSE, Nasdaq, NYSE American |
| Market cap | ≥ $50M: last share count filed before the rebalance × the last close before it, restated through the splits after the count up to the price snapshot's `adjusted_through` date |
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

A month is only built from known split histories. Each ticker's history in `splits/{ticker}.parquet` is `available`, `confirmed_empty` (Yahoo answered with none) or `unavailable` (the request failed), and vouches for splits up to its `covered_through` date; a read beyond it fetches again. When a member's market cap needs a history that is unavailable or does not reach the price snapshot's `adjusted_through`, the month is not written: the build summary lists it under `split_unavailable` with the tickers, and the next build tries it again.

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

## Price snapshots

`PriceRefresher` keeps one append-only OHLCV snapshot per ticker in `auspex-prices` (`{ticker}.parquet`), from Yahoo, then Stooq. Only completed bars are stored: a session's bar two hours after its NYSE close (early closes included), an `EURUSD=X` bar two hours after its UTC day ends. An unfinished bar is dropped and fetched again by the next refresh. A refresh appends only when the response repeats the last stored bar within 2%; a re-adjusted or missing overlap bar raises `SnapshotDiscontinuityError` and stores nothing, and the stored bars stay usable up to where they end. The snapshot's Parquet metadata records `adjusted_through`, the UTC date of its first download: its closes are on that day's share basis.

## Price service metrics

`GET /metrics` on the price service (port 8001, scraped by Prometheus as job `price-service`):

| Metric | Meaning |
|---|---|
| `auspex_price_refresh_runs_total{outcome}` | `/prices/refresh` calls; `failed` when any ticker failed |
| `auspex_price_tickers_refreshed_total` / `auspex_price_tickers_failed_total` | tickers per outcome |
| `auspex_price_refresh_last_success_timestamp_seconds` | last refresh in which every ticker refreshed; absent until the first one |
| `auspex_price_refresh_sessions_since_success` | NYSE sessions strictly between that success (or the service's start) and today, UTC; Grafana's **Price Refresh Stale** fires at 2 |
| `auspex_universe_latest_month` | latest stored universe month as YYYYMM, read from MinIO at each scrape; 0 before the first build, absent while MinIO cannot be read; **Universe Month Missing** fires from day 8 |

## Evaluation protocol

`config/hypotheses/protocol.yaml` and the `h*.yaml` hypotheses are locked by hash in `registry.jsonl`; a changed file is refused until re-registered with `scripts/register_hypothesis.py`, and earlier registry lines are never edited.

- `verify_hypothesis()` checks the hash and the hypothesis's shape: `evaluation: event` or `portfolio`, a `role`, no event-only field (`known_at_delay_days`, `holding_period_days`, `entry_timing_days`) on a portfolio hypothesis and no portfolio-only field (`rebalance_frequency`, `hold_bands`, `in_sample_years`, ...) on an event one, `holdout_years` after `in_sample_years`, `trial_cells` equal to the `trial_grid` product.
- A hypothesis with `uses` (H10) registers one score several ways; each use is checked and promoted on its own.
- `EvaluationProtocol(config_dir=..., registry_path=...).admit(hypothesis_id)` is the gate before any evaluation reads returns: it refuses a family with no registered budget, a family over budget once every registered hypothesis is counted, a role the family does not hold (the registry and catalyst families hold diagnostics only), and shorts or options above the protocol's instrument ceilings.
- `check_promotable()` refuses filters, diagnostics and descriptive hypotheses.
- `forward_check_branch()` gives the event or portfolio forward check; `evaluate_portfolio_forward_check()` and `is_data_gap()` apply the portfolio branch per capital tier.
- `PortfolioForwardRecord` takes paper and replay returns as `(YYYY-MM, value)` ledger rows. `evaluate_portfolio_forward_check()` returns `invalid` before any comparison when a return or in-sample value is NaN or infinite, the standard error is negative, or the months are malformed, duplicated, missing inside the range or not the same in both ledgers; `reasons` names each problem and its months. `invalid` is a data problem, not a kill.
- `quarterly_trade_date()` and `select_component_variant()` apply H9's registered trade-date rule and component fallback.

### Event evaluation

`EvaluationProtocol(..., prices=PriceSnapshotStore(minio), costs=TradeCosts(CostModel(spread_estimator=SpreadEstimator(store)), CurrencyConverter(store), position_eur=...)).run(hypothesis_id, events, variant)` evaluates an event hypothesis (`auspex_backtesting.evaluation`). `events` has one row per event of that variant, with `ticker` and `corroborated_at`.

- **Refusals, before anything is recorded:** a modified protocol or hypothesis, a suspended hypothesis, a horizon, delay or variant outside the declared grid, a missing `N_BOOTSTRAP`.
- **Trial ledger:** the run's cells (each requested horizon at each known-at delay) are reserved in `config/hypotheses/trials/<id>.jsonl` before any price is read, under an exclusive lock on `trials/.lock` together with the family budget check. A run over the family budget raises `TrialBudgetExhaustedError`; a run that fails later still counts. A torn final line is truncated and logged; any other unreadable line raises `TrialLedgerCorruptError` until the file is fixed by hand. `run_backtest()` reserves its raw-return windows the same way.
- **Holdout:** the last `promotion.holdout_months` of the event date range are not read. `HoldoutGuard.run_holdout()` releases them only for a promotable result on the primary cell.
- **Per cell:** entry is the session on or after `corroborated_at` plus the delay; horizon `h` is the market-model CAR over sessions `[+1, +h]` against XBI (estimation window `[-250, -30]`, market-adjusted below 120 days), clustered t (wild cluster bootstrap below 30 clusters), independent events, bootstrap CI, each trade's cost components and net EUR P&L, and the deflated Sharpe ratio of net returns against the family trial count.
- **Result:** the primary cell when evaluated (else the first), every cell in `cells`, kill verdicts (`lagging_signal`, `no_in_sample_effect`, `cost_check`), walk-forward segments (18 months in, 6 out, 30-day embargo) and `holdout_sealed`. `to_report()` gives it as plain data.

### Portfolio backtest

`auspex_backtesting.portfolio` backtests score hypotheses (`evaluation: portfolio`) as a traded, long-only basket.

**Score snapshots** are the contract every score writes: one Parquet per score and rebalance date, `scores/{hypothesis_id}/{version}/{yyyy-mm-dd}.parquet` in `auspex-prices`, with `cik`, `ticker`, `score` (higher ranks higher), `known_at_max` (UTC, the latest time any input of the row became known) and any component columns. `ScoreStore.write()` refuses an existing snapshot, and `ScoreSnapshot.validate()` refuses a row known at or after the rebalance session's open; the engine validates every snapshot it reads.

**`PortfolioBacktest.run(rule, universe_version, tier_eur, start, end)`**:
- A `PortfolioRule` (`PortfolioRule.from_hypothesis(hypothesis, cell, score)` for a trial-grid cell) selects `top_n` with hold bands (buy at rank `enter_rank` or better, keep while at `exit_rank` or better; equal ranks are a hard cut), `top_quintile` or `exclude_bottom_quintile`, ties broken by CIK. Cadence is `monthly` (first NYSE session of each month), `quarterly_after_13f` or `semi_annual_after_13f` (`quarterly_trade_date()`; Q2 and Q4 only for semi-annual). An optional exclusion score's bottom quintile is neither bought nor kept.
- On each decision date the month's universe snapshot is ranked on the latest score snapshot dated on or before it; orders fill at the open of the next session through `FillModel`, sells first, buys within the cash left.
- `EqualRiskSizer` weights by 1 / trailing 60-session volatility from sessions before the decision date, capped at the protocol's `max_position_pct`; what the caps leave is cash earning nothing, never spread above the cap. Fewer than `min_names` raises `InsufficientNamesError`.
- `CatalystGuard` modes: `none`, `skip_entry` (no new buy with a binary due before the next fill), `exit_and_reenter` (sell at the close before the binary, buy back at the open after it while still before the next fill), `exit_low_score_only` (the same, only for held names outside the entry band). Each decision reports names checked, clear, with a binary, without any catalyst data (counted, never clear), skipped and exited, and universe members without catalyst data.
- Each order is costed by `CostModel.leg_cost_usd()` at the tier's size. A new position below `CostModel.min_ticket_usd()` (minimum commission over IBKR's 1% commission cap) is skipped and counted.
- A held name whose prices stop is closed at its last close; a `delisted` or `deregistered` exit whose prices stop before the session before `exited_on` is booked at -30% and its month flagged.

**`PortfolioResult`** has per month gross and net return, cost, turnover, names held, cash share, XBI and universe equal-weight returns and the excess over each (also against the equal-weight scaled to the invested share), plus cost by component, yearly cost drag (average round-trip cost times round trips a year), average holding period overall and per name, returns inside ±5 sessions of a known day-precision binary versus other days, rolling 12-month beta to XBI, the worst name-month, the share of net P&L from the top 5% of name-months, delisting-bound months, skipped tickets, unpriced member-months and the top-minus-bottom score quintile returns.

**`PortfolioEvaluation.run(hypothesis_id, cell, rule, universe_version, tiers_eur, final=...)`** admits the hypothesis, reserves the cell in the family ledger, runs every tier over the in-sample years and applies `PortfolioVerdict` at the smallest tier:
- In-sample kill criteria from `protocol.yaml` `portfolio_kill_criteria`: `no_in_sample_spread` (Newey-West t of the quintile spread at the registered lag, and the top quintile's net excess over the universe equal-weight from a `top_quintile` run of the same rule), `turnover_cost` and `survivorship` (unpriced member-month share; the result is `not_usable`).
- Deflated Sharpe of the monthly net excess over the declared benchmark with the family trial count, and its Newey-West t. Only the primary cell of a promotable hypothesis can pass; filters and diagnostics are `not_promotable`.
- On a final run whose in-sample verdict passed, the holdout years are read once (`HoldoutRecord`, one file per hypothesis use created exclusively) and `holdout_check` gives `promoted` or `killed`. A final run is refused before anything is reserved or read when the holdout was read already, or when any universe or score snapshot it would read has no input manifest (`InputsNotPinnedError`); until input manifests exist (`specs/research-input-archive.md`) the default `NoInputManifests` refuses every final run.

## SEC ownership panels

`auspex_backtesting.ownership` keeps two point-in-time panels from SEC's bulk data for the holdings composite (H9): who holds each universe company (Form 13F) and what its insiders bought and sold (Forms 4 and 5). They are time series joined to a monthly score, so they are stored like prices, not sent through the document pipeline.

Every read is as of an instant and sees only filings accepted before it: `filing_accepted_at`, never the period a 13F reports on or the day a trade was made. The data sets give only a filing date, so `filing_accepted_at` is 22:00 US Eastern on that date, the latest EDGAR accepts; daily Form 4 rows carry their real acceptance time.

| Reader | Returns |
|---|---|
| `HoldingsPanel.load(store).specialist_ownership(issuer_cik, as_of)` | shares held by healthcare specialist 13F filers in each one's latest report accepted before `as_of` (a later restatement never changes an earlier read), over shares outstanding filed before `as_of` |
| `InsiderPanel.load(store, market_caps).net_insider_buying(issuer_cik, as_of, days=90)` | open-market purchases (`P`) minus sales (`S`) accepted in the window, in USD over market cap; 10b5-1 plan trades and purchases within two days of the issuer's `424B4`/`424B5` (`offering_participation`) left out |
| `InsiderPanel.transactions(issuer_cik, as_of, days=90)` | the window's transactions with the `offering_participation` flag |
| `SpecialistClassifier.from_hypothesis(filings).classify(as_of)` | per filer: healthcare share over the four quarters before `as_of`, latest reported value, `is_specialist` |

A 13F filer is a **healthcare specialist** as of a date when at least `SPECIALIST_HEALTHCARE_SHARE` of its reported long equity value over the four calendar quarters before it is in SIC 2834, 2836, 8731 or 3841 issuers and its latest report totals at least `SPECIALIST_MIN_AUM_USD`. Both thresholds are read from the registered H9 hypothesis (`config/hypotheses/h9.yaml`, `components.specialist_13f_ownership.thresholds`), their only source; an unregistered or edited `h9.yaml` is refused. Derived from the filings, not from a list, so no fund is picked for having done well later.

Stored in the `auspex-prices` bucket under `ownership/`, each file written once unless noted:

| Object | Content |
|---|---|
| `13f/{label}.parquet` | universe holdings of one 13F data set: `accession_number, filer_cik, issuer_cik, cusip, shares, value_usd, period_of_report, filing_accepted_at, is_amendment, amendment_type`; the data set's coverage report in its metadata |
| `13f/filings/{label}.parquet` | every holdings report in it, with total and healthcare long equity value |
| `13f/specialists/{label}.parquet` | specialist classification as of just after the data set's last filing (rewritten only if missing) |
| `insider/{yyyy}q{q}.parquet` | universe transactions of one insider data set: `accession_number, issuer_cik, owner_cik, role, transaction_code, acquired_disposed, shares, price, transaction_date, filing_date, filing_accepted_at, is_10b5_1` |
| `insider/daily/{yyyy-mm-dd}.parquet` | the same, from that day's form index and Form 4 XML, for days after the latest insider data set; readers prefer the data set once stored and log any disagreement |
| `offerings/{yyyy}q{q}.parquet`, `offerings/daily/{yyyy-mm-dd}.parquet` | `424B4`/`424B5` filings of universe issuers from the quarterly and daily form indexes |
| `shares_outstanding.parquet` | cover-page share counts of universe companies; replaced on every run |

13F data sets are labelled as SEC names them: calendar quarters (`2023q4`) through 2023, three-month windows (`01mar2024-31may2024`) since. Holdings are mapped from CUSIP to CIK by issuer name against every SEC operating company's current and former names; each data set reports unmapped CUSIPs and their value instead of dropping them. How amendments, joint filings and 10b5-1 trades are counted is recorded in `DECISIONS.md` (2026-10-09, SEC ownership datasets).

`scripts/fetch_ownership.py` backfills everything from `OWNERSHIP_HISTORY_START`, once (needs a built universe; it keeps only universe companies), and prints coverage. SEC requests go through one client paced at 5 per second with `SEC_USER_AGENT`; a refusal stops the run without retrying.

## Short interest

`auspex_backtesting.short_interest` keeps FINRA's consolidated short interest per universe ticker for the holdings composite's days-to-cover component (H9). FINRA counts short positions as of two settlement dates a month and publishes them on the 7th business day after; a period is known from its **publication date**, never its settlement date.

| Reader | Returns |
|---|---|
| `ShortInterestStore(minio).as_of(ticker, date)` | the latest period published on or before `date` (known by the end of that day; FINRA gives no time of day, so a decision before the close asks for the session before), or None |
| `ShortInterestStore(minio).features(ticker, date, shares)` | that record with short interest as a percentage of shares outstanding (None without a known share count) and the change in shares short since the previous period |

A record has `settlement_date, publication_date, reported, short_interest_shares, average_daily_volume, days_to_cover`. `days_to_cover` is the exact ratio of the two counts (FINRA's own figure is rounded and floored at 1.00), None when volume is zero. A ticker missing from a period FINRA published is stored with `reported` false and no counts: absent, not zero.

Stored in the `auspex-prices` bucket as `short_interest/{ticker}.parquet`. A file only gains new periods; a stored period is never rewritten, and a rerun fetches only periods some ticker lacks. Settlement and publication dates come from FINRA's rule (the 15th and the month's last settlement day, each moved back to an NYSE session; published seven sessions later), except in months whose dates FINRA published in `config/short_interest/finra_calendar.csv`, which win. Share counts by ticker (`UniverseShareCounts`) go through the ticker's universe company to the ownership panels' `shares_outstanding.parquet`.

FINRA's data covers exchange-listed stocks only from June 2021 (earlier files are OTC only), so `SHORT_INTEREST_HISTORY_START` is 2021-06-01 and H9's in-sample period from 2014 runs its two-component variant by its pre-registered rule. Requests need a FINRA API credential (`FINRA_API_CLIENT_ID`, `FINRA_API_CLIENT_SECRET`).

## Scripts

| Script | Purpose |
|---|---|
| `scripts/fetch_prices.py` | Snapshot prices for tickers outside the watchlist, once |
| `scripts/build_universe.py` | Run a universe build outside the schedule, or `--export-backfill-scope PATH` to copy the backfill scope out of MinIO |
| `scripts/build_catalyst_panel.py` | Build or extend the catalyst panel (`--since`, default 2014-01-01; `--until`, default today) and print its coverage: catalysts per year, members with any catalyst, unmatched advisory committee notices, PDUFA hits by precision. Needs the universe built first |
| `scripts/register_hypothesis.py` | Register a hypothesis file in the pre-registration ledger |
| `scripts/fetch_ownership.py` | Backfill and extend the SEC ownership panels and print their coverage |
| `scripts/fetch_short_interest.py` | Backfill and extend FINRA short interest for the universe's tickers and print coverage: first available settlement date, periods FINRA returned nothing for, gaps, tickers never reported. Needs the universe built first |
| `scripts/run_portfolio_backtest.py` | Run a registered portfolio hypothesis's cell (default its primary cell) at every tier in `PAPER_CAPITAL_TIERS_EUR`, reserve the cell in the trial ledger and write the report and verdict as JSON (`--final` reads the holdout once) |

## Commands

| Purpose | Command |
|---|---|
| Install | `uv sync` |
| Unit tests | `uv run pytest tests/unit -q` |
| Lint | `uv run ruff check .` |

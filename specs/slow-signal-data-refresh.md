# Slow-Signal Data Refresh

**Status:** blocked
**Blocked by:**
1. `specs/sec-ownership-datasets.md`: the ownership panels and `fetch_ownership.py`'s job, which this spec puts behind an endpoint.
2. `specs/catalyst-date-panel.md`: `CatalystPanelBuild`, which this spec puts behind an endpoint.
3. `specs/short-interest-snapshots.md`: `ShortInterestFetcher` and `ShortInterestStore`.
4. `specs/filing-text-change-score.md`: the filing panel and `RiskFactorChangeScore`.
5. `specs/holdings-composite-score.md`: `HoldingsCompositeScore`.
6. `specs/infrastructure-observability.md`: the alert provisioning and `test_stack_alert_expressions.py` that the stale-input alert joins.

Every item above is a code dependency, not a stack run. Tests use fakes of each job.

**Branch:** `feature/slow-signal-data-refresh`

---

## Context

The slow-signal path (H9 holdings composite with H10 as its exclusion filter, `config/hypotheses/`) is built from panels that only backfill scripts fill today: `scripts/fetch_ownership.py`, `scripts/build_catalyst_panel.py`, `scripts/fetch_short_interest.py`, `scripts/build_filing_panel.py`, `scripts/compute_holdings_scores.py`. That is enough for a backtest. It is not enough for forward paper trading (`specs/forward-paper-trading.md`). On each quarterly trade date, `PortfolioRebalance` reads the latest `ScoreSnapshot`, and a snapshot, universe snapshot or closing price that was not available before that session's open is a **data gap**. A 12-month forward check with a gap fails.

Root `CLAUDE.md` ("Where work can run") says data that must stay current belongs in an Airflow DAG calling a service HTTP API, never in a script run by hand. Two specs flagged the missing schedule in `DECISIONS.md` on 2026-10-09: the catalyst date panel FLAG "not kept current by the stack" and the SEC ownership datasets FLAG "panels are refreshed by a script, not a DAG".

The pattern to follow already exists in `services/backtesting`:
- `src/auspex_backtesting/api.py`: the price service (Flask, gunicorn) with `POST /prices/refresh` and `POST /universe/build`. Each route builds its job from `.env` (`refresher_from_env()`, `universe_job_from_env()`) and maps a source outage (`OSError`) to 502, so the DAG retries.
- `dags/price_refresh.py` and `dags/universe_build.py`: each DAG makes one `requests.post` to `PRICE_API_URL`, raises on 4xx/5xx, has `retries` set, `catchup=False`, `max_active_runs=1` and `is_paused_upon_creation=False`.
- `prices/price_refresher.py:43` `price_universe()`: the daily price refresh covers `WATCHED_TICKERS` plus XBI and `EURUSD=X` only. Universe members get prices only from the monthly universe build. H9's tradable floor (20-day median dollar volume), `EqualRiskSizer` (trailing 60-session volatility) and daily marks all need current closes for every member.

## What this builds

1. **Price service endpoints** in `api.py`, each running an existing job and returning its summary. Each is idempotent: a second call with nothing new published writes nothing and returns 200 with zero counts.
   - `POST /ownership/refresh`: stores any 13F or insider data set SEC has published since the last stored one, then fills daily Form 4s up to yesterday.
   - `POST /short-interest/refresh`: fetches every FINRA settlement period published since the last stored one.
   - `POST /filings/refresh`: indexes, cuts and scores 10-K/10-Q filings accepted since the last run, for members of every universe a registered hypothesis reads.
   - `POST /catalysts/build`: runs `CatalystPanelBuild` for quarters not yet complete in the panel.
   - `POST /scores/build`: for each `evaluation: portfolio` hypothesis at status `paper` or above (and its filters), writes the `ScoreSnapshot` for the latest rebalance date that has none. It refuses (409) when an input panel is stale under item 4 and names the stale input. It never writes a snapshot from stale inputs.
2. **Universe members in the daily price refresh.** `price_universe()` adds the current month's members of the universes named in `PRICE_REFRESH_UNIVERSES` (`.env`, default the biotech universe id). Members whose listing ended (`exited_on` set) and tickers no longer in any refreshed universe drop out. A failure on a member is reported per ticker as today. Open paper positions are refreshed by `DailyCloseOut` itself, not here.
3. **DAGs** in `services/backtesting/dags/`, one per endpoint, using the existing pattern. Schedules come from `.env` with documented defaults:
   - ownership: daily, 07:00 UTC.
   - short interest: daily, 07:30 UTC. Most days nothing new is published, and the call is a no-op.
   - filings: daily, 08:00 UTC.
   - catalysts: daily, 08:30 UTC.
   - scores: daily, 10:00 UTC, after the others. Most days there is no new rebalance date, and the call is a no-op.

   The scores DAG must finish before the NYSE open on a rebalance date.
4. **Freshness.** Each endpoint sets `auspex_panel_last_success_timestamp_seconds{panel=...}` on success. `auspex_panel_stale{panel=...}` is 1 when the panel's newest stored period is older than its expected publication lag allows. The lags are 13F data set 100 days, insider data set 100 days, daily Form 4 4 days, short interest 20 days, filings 3 days, catalysts 3 days and universe 40 days, each in `.env`. A Grafana alert, "Slow-signal input stale", fires on any stale panel. This is the same staleness `/scores/build` refuses on.

## Out of scope

- New data sources, new hypotheses, or changes to how any panel or score is computed.
- The H10 broad (`us_small_mid`) universe in the daily price refresh. Add its id to `PRICE_REFRESH_UNIVERSES` only when an H10 broad use reaches `paper`.
- Paper ledger, rebalance and close-out logic (`specs/forward-paper-trading.md`).
- The LLM pipeline and its DAGs.

## Constraints

- Invariant 1 and 2: the price service writes only MinIO (`auspex-prices`). Nothing here touches the scraper, Postgres or Neo4j.
- Invariant 3: DAGs contain only the HTTP call. No panel logic in DAG code.
- Invariant 6: URLs, schedules, lags and universe ids come from `.env`. Update `.env.example` and `SETUP.md` only if a value has no safe default.
- Invariant 9: schedules and timestamps in UTC.
- SEC traps (root `CLAUDE.md`): shared ≤ 5 req/s limiter across the ownership, filings and catalyst jobs, because they share SEC's 10 req/s per-IP bucket. A 403/429 ends the run with 502, with no in-process retry, and the DAG's retry comes after the block window (`retry_delay` ≥ 15 minutes).
- Point-in-time: a refresh appends; it never rewrites a stored period (each panel's own rule). `/scores/build` writes each snapshot once.
- `pytest-socket` in unit tests; jobs are fakes.

## Required tests

In `services/backtesting/tests/unit/test_data_refresh_api.py`:
- `test_each_refresh_endpoint_runs_its_job_and_returns_the_summary`
- `test_refresh_with_nothing_new_published_writes_nothing_and_returns_200`
- `test_source_outage_returns_502_so_the_dag_retries`
- `test_sec_jobs_share_one_rate_limiter`
- `test_score_build_writes_snapshot_only_for_paper_or_higher_portfolio_hypotheses_and_their_filters`
- `test_score_build_refuses_when_an_input_panel_is_stale_and_names_it`
- `test_score_build_does_not_overwrite_an_existing_snapshot`
- `test_freshness_gauges_set_on_success_and_stale_flag_follows_publication_lag`

In `services/backtesting/tests/unit/test_price_refresh.py` (added):
- `test_price_universe_includes_current_members_of_configured_universes`
- `test_member_with_exited_listing_is_not_refreshed`

In `services/backtesting/tests/unit/test_data_refresh_dags.py`:
- `test_each_dag_only_posts_to_its_endpoint_and_raises_on_error_status`
- `test_dag_schedules_come_from_env_with_documented_defaults`
- `test_score_dag_default_schedule_runs_after_input_dags_and_before_the_nyse_open`
- `test_sec_dags_retry_after_the_block_window`

In `docker/grafana/test_stack_alert_expressions.py` (added): firing and quiet cases for "Slow-signal input stale".

## Definition of done

```bash
cd services/backtesting && uv run pytest tests/unit/test_data_refresh_api.py tests/unit/test_data_refresh_dags.py tests/unit/test_price_refresh.py -q --strict-markers && uv run pytest tests/unit -q
```

Expected: the 14 new tests pass with the rest of the backtesting unit suite. The alert-expression cases pass with that suite's own command.

Then, on the stack machine (picked up by `specs/first-run-on-stack-machine.md` step 8): every new DAG runs once green, `auspex_panel_stale` is 0 for every panel, and stopping one refresh past its lag raises the alert. Record the outcome in `DECISIONS.md`.

## Notes

- Why one spec: the five endpoints share one pattern, one limiter and one freshness rule, and none is useful for paper trading without the others.
- Daily schedules for monthly or quarterly data make a missed day recoverable the next morning, without anyone noticing. The endpoints are idempotent, so the daily cost is one index read per source.

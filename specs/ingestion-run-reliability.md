# Ingestion run reliability

**Status:** blocked
**Blocked by:** `specs/graph-and-connector-wiring-fixes.md` merged into `develop` (it rewrites the scraper API's pipeline wiring and `sources.py`, which this spec changes too)
**Branch:** `feature/ingestion-run-reliability`

---

## Context

Each live source is polled once a day by an Airflow DAG in `services/ingestion-scraper/dags/auspex_dags.py`, generated from `services/ingestion-scraper/config/sources.yaml`. The task reads Variable `cursor:{source_type}`, POSTs it to the scraper's `/ingest/<source_type>` (`src/auspex_ingest/api.py`), and writes back `max_published_date_processed` from the response. `IngestionPipeline.run` (`src/auspex_ingest/pipeline.py`) archives every document to MinIO, skips documents with a processed marker for the current model and prompt, prefilters, extracts with the local model, publishes to Kafka, and writes processed markers after a confirmed flush. All HTTP from connectors goes through one `RateLimitedClient` (`src/auspex_ingest/connectors/rate_limited_client.py`).

Requirements: `docs/requirements.md` §5 (DAG owns the cursor; `catchup=False`, `max_active_runs=1`, staggered schedules), §6.5 (shared per-host rate limits; SEC 10 req/s aggregate, configure 5; bioRxiv and ClinicalTrials.gov 1 req/s), §7.1 (dedup gates extraction, never the archive).

What goes wrong today, found by the soak-test readiness audit (2026-10-09):
1. **Failed documents are skipped for good.** `max_published_date_processed` is raised for every fetched document before extraction, so a document whose extraction fails (model server down, timeout, Mac asleep) lies behind the new cursor and is never fetched again. The API returns 200 and the DAG run is green.
2. **Every source starts at 00:00 UTC** (`schedule: "@daily"` on all six entries), so six runs share one scraper process and one model server that serves one request at a time. Queued extraction calls time out, which feeds problem 1.
3. **`max_documents_per_run` is declared in `sources.yaml` but never read.** A first run with a 30-day lookback, or a catch-up after downtime, can outlast the DAG's 3,600 s HTTP timeout; the task fails without a cursor while the scraper keeps working, and the next run of the same source can overlap it.
4. **No retries** on ingestion tasks, and the `mock` fixture source gets a scheduled DAG like any live one.
5. **Rate limits:** `RateLimitedClient` raises `RateLimitExceeded` when a bucket is empty instead of waiting (nothing catches it, so the run fails), and its buckets have no lock although concurrent runs share them. `sources.yaml` sets bioRxiv to 3 req/s and ClinicalTrials.gov to 5 req/s against §6.5's 1. The universe build's SEC filing-index lookups run at 8 req/s (`services/backtesting/src/auspex_backtesting/universe/sec_index.py`, `_REQUEST_INTERVAL_S = 0.125`) in a different container from EDGAR ingestion (4 req/s), so the two together can pass SEC's 10 req/s. `SecEdgarConnector._get_json` sleeps 60 s after a 403 and retries, which extends an SEC block.

## What this builds

- A run never moves the cursor past a document it failed to process. The safe cursor is the earliest failed document's `published_date` when any failed, else the latest processed date. The DAG task saves it and then fails, so the run shows red, retries, and alerts.
- Live sources start at staggered times, and ingestion tasks share an Airflow pool with one slot, so only one ingestion run talks to the model server at a time.
- A run sends at most `max_documents_per_run` documents to extraction. Documents skipped as already processed don't count. When the cap is reached the run stops and returns the cursor it was given, so the next run continues where this one stopped, using the processed markers.
- The scraper refuses a second concurrent run of the same source with HTTP 409.
- Ingestion tasks retry twice, 15 minutes apart, with an `execution_timeout` the HTTP timeout matches.
- Sources without a schedule (`mock`) get a DAG that never runs on a schedule.
- `RateLimitedClient` waits for a token and is thread-safe. `sources.yaml` rates follow §6.5. The universe build's SEC lookups run at no more than 5 req/s, so they and EDGAR ingestion (4 req/s) stay under 10 together. EDGAR stops a run on a 403 instead of retrying into the block.

## Out of scope

- Changing what is extracted, the prompt, the model, or the processed-marker key.
- Moving ingestion to an asynchronous start-and-poll API.
- The SEC ownership and catalyst panels' own SEC clients (already paced at 5 req/s and not scheduled).
- Alert rules for failed documents and silent sources (`specs/pipeline-alerting-gaps.md`).

## Constraints

- Invariant 3: the DAG only calls the scraper HTTP API; the pool, schedule and retry settings live in the DAG and `sources.yaml`, the cursor rule lives in the pipeline.
- Invariant 4: no `if source_type == ...`; per-source behaviour comes from `sources.yaml`.
- Invariant 8: synchronous Python; the per-source lock and rate-limit waiting use `threading`.
- Invariant 9: cursors stay UTC-aware ISO strings.
- §5: the pipeline stays stateless with respect to cursors; it only reports the safe cursor. "On failure, leave the Variable untouched" still holds for a request that errors (5xx, timeout). A run that completed with failed documents writes the safe cursor, which is never later than any failed document (`DECISIONS.md` 2026-10-09 entry).
- The Airflow pool must exist before the scheduler queues a task; it is created at container start by the compose command, not by hand.

## Required tests

Python unit (`services/ingestion-scraper/tests/unit/`):
- `test_cursor_stops_at_the_earliest_failed_document` — a run with successes on later dates and one failure on an earlier date returns the failed document's date
- `test_cursor_is_the_latest_processed_date_when_nothing_failed`
- `test_failed_document_is_extracted_again_on_the_next_run` — rerun from the returned cursor re-extracts only the failed document (processed markers skip the rest)
- `test_extraction_cap_stops_the_run_and_returns_the_input_cursor`
- `test_already_processed_documents_do_not_count_toward_the_extraction_cap`
- `test_second_concurrent_run_of_a_source_is_refused_with_409`
- `test_runs_of_different_sources_are_not_blocked_by_the_source_lock`
- `test_ingestion_task_saves_the_safe_cursor_then_fails_when_documents_failed` — the task callable in the DAG file, with HTTP and Variable access stubbed
- `test_ingestion_task_leaves_the_cursor_untouched_when_the_request_fails`
- `test_live_sources_start_at_distinct_times` — every scheduled entry in `sources.yaml` has a different start time, none within 30 minutes of another
- `test_ingestion_tasks_use_the_single_slot_ingestion_pool`
- `test_ingestion_tasks_retry_twice_fifteen_minutes_apart`
- `test_ingestion_http_timeout_matches_the_task_execution_timeout`
- `test_source_without_schedule_is_never_scheduled`
- `test_source_rates_follow_the_requirements_limits` — bioRxiv and ClinicalTrials.gov at most 1 req/s, PubMed at most 3, EPO at most 2, SEC at most 5
- `test_rate_limited_client_waits_for_a_token_instead_of_raising`
- `test_rate_limited_client_never_exceeds_the_rate_across_threads`
- `test_edgar_stops_on_a_refused_request_without_retrying`

Python unit (`services/backtesting/tests/unit/`):
- `test_filing_index_lookups_run_at_most_five_per_second`

Config (`services/ingestion-scraper/tests/unit/`, parsing `docker/docker-compose.yml`):
- `test_airflow_creates_the_ingestion_pool_before_the_scheduler_starts`

## Definition of done

```bash
cd services/ingestion-scraper && uv run pytest tests/unit -q --strict-markers && uv run ruff check . && uv run mypy src && cd ../..
cd services/backtesting && uv run pytest tests/unit -q --strict-markers && cd ../..
```

Expected: both suites pass with the 20 new tests among them, lint and types clean, CI green on the PR. On the stack (picked up by `specs/first-run-on-stack-machine.md` step 8): the Airflow UI lists pool `ingestion` with 1 slot, and stopping the model server during a run leaves that run red with its cursor at or before the first failed document.

## Notes

- Why a pool and staggering both: staggering is what §5 asks for and spreads the normal day; the pool keeps runs from piling up after the Mac wakes from sleep, when every missed DAG fires at once.
- The DAG task lives only in `dags/auspex_dags.py`, tested by `tests/unit/test_ingestion_dag.py` against stand-in Airflow modules; the older in-process DAG factory module was removed.
- The cap per source is set so a capped run fits inside the task timeout at the measured extraction latency (`specs/soak-test-run.md` measures it on day 1).

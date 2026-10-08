# Pipeline Control View

**Status:** blocked
**Blocked by:** `specs/dashboard-foundation.md` (BFF, login, API client) and `specs/graph-and-connector-wiring-fixes.md` (every source reachable through the scraper API).
**Branch:** `feature/pipeline-control-view`

---

## Context

Decided 2026-10-08: the dashboard is where the user monitors and steers the automated parts. Grafana covers technical health; this view covers what the pipeline did and lets the user act on it, without opening the Airflow UI.

What exists:
- Airflow 3.3.1 runs `standalone` (`docker-compose.yml`, `127.0.0.1:8082`). One DAG per `sources.yaml` entry (`services/ingestion-scraper/dags/auspex_dags.py`, tag `auspex`) and `price_refresh` (`services/backtesting/dags/`). The ingestion task posts to `/ingest/<source_type>`, then writes the returned cursor to Variable `cursor:{source_type}`. It doesn't return the `RunResult`, so run counts are visible only in logs.
- Airflow's REST API `/api/v2` is up (the healthcheck uses it), but no user is set up for machine access; standalone generates its own admin password.
- The scraper's `POST /reextract` runs synchronously inside the request.
- Dead-lettered records sit on the `*.dlt` topics with diagnostic headers. core-hub counts them (`CountingDeadLetterRecoverer`), and Grafana shows totals, but nothing lists individual records.
- Requirements §5: the DAG task owns the cursor, `catchup=False`, `max_active_runs=1`, and a backfill never writes the live cursor. §12: cursor position is visible.

## What this builds

1. **Airflow API access for the BFF:** a dedicated Airflow API user with credentials from `.env` (`AIRFLOW_API_USERNAME`, `AIRFLOW_API_PASSWORD`). The BFF exchanges them for a token, caches it, and refreshes it on a 401. Only the BFF holds these credentials.
2. **Run results recorded:** the ingestion task returns the `RunResult` (fetched, archived, prefiltered out, extracted, published, failed, cursor before and after) as its XCom value; the price task returns tickers refreshed and failed.
3. **Re-extraction as a DAG:** `auspex_reextract`, triggered with a conf (`source_type`, date range, `prefilter_version`, `dry_run`), calls the scraper's `/reextract` and returns its counts. It has no schedule, `max_active_runs=1`, and never touches a cursor Variable.
4. **Dashboard view `/pipeline`:**
   - One row per Auspex DAG (tag `auspex`, plus `price_refresh` and `auspex_reextract`): paused or active, last run state and time (UTC), next run, the current cursor, and the last run's counts.
   - Per DAG: run history with counts and links to the run's task log in Airflow; a trigger button (with conf for re-extraction); pause and resume.
   - Actions are limited to DAGs tagged `auspex`; the BFF refuses any other `dag_id`.
5. **Dead letters** (`/pipeline/dead-letters`): core-hub `GET /api/v1/dead-letters?topic=&limit=` returns, per `*.dlt` topic, its depth and its newest records' headers: exception class and message, original topic, partition, offset, timestamp, and `event_id` or raw object key when the payload has one. Read with a dedicated consumer that never commits offsets. Payload bodies are not returned.

## Out of scope

- Editing schedules (they stay in `sources.yaml`, read at DAG parse).
- Replaying dead letters back onto their topics. A later spec, once the view shows how often it is needed.
- Backfill orchestration (`specs/historical-backfill.md`).
- Infrastructure health (`specs/infrastructure-observability.md`).

## Constraints

- Invariant 3: DAGs only call scraper HTTP endpoints; the re-extraction DAG holds no extraction logic.
- §5: run, trigger and re-extraction never write `cursor:{source_type}` except through the existing ingestion task on success. A triggered ingestion run uses the same task, so it advances the cursor exactly as a scheduled one does.
- Invariant 6: Airflow credentials only in `.env` and the BFF's server env.
- Invariant 11: the dead-letter reader is read-only. It uses its own consumer group with auto-commit off and never commits, so it cannot move the DLT position seen by any other consumer.
- Requirements §3.3: no `raw_content` in any response.

## Required tests

ingestion-scraper, `tests/unit/test_dag_tasks.py` (Airflow modules stubbed in `sys.modules`; no Airflow install):
- `test_ingestion_task_returns_run_result_as_xcom`
- `test_ingestion_task_writes_cursor_only_on_success`
- `test_failed_ingestion_leaves_cursor_unchanged_and_raises`
- `test_reextract_dag_posts_conf_to_scraper_and_returns_counts`
- `test_reextract_dag_never_writes_a_cursor_variable`
- `test_every_auspex_dag_has_catchup_false_and_one_active_run`

backtesting, `tests/unit/test_price_refresh_dag.py`:
- `test_price_task_returns_refreshed_and_failed_tickers`

core-hub, `src/integrationTest/java/.../deadletter/DeadLetterReadIT.java`:
- `deadLetterEndpointReportsDepthPerDltTopic`
- `deadLetterRecordShowsHeadersAndOriginalCoordinates`
- `readingDeadLettersCommitsNoOffset`
- `deadLetterResponseContainsNoPayloadBody`

Dashboard (Vitest):
- `airflow-bff.test.ts`
  - `test_bff_obtains_and_caches_airflow_token`
  - `test_bff_refreshes_token_once_on_401`
  - `test_bff_lists_only_auspex_dags`
  - `test_bff_refuses_trigger_and_pause_for_non_auspex_dag`
- `Pipeline.test.tsx`
  - `test_dag_row_shows_state_cursor_and_last_counts`
  - `test_trigger_posts_and_shows_the_new_run`
  - `test_pause_toggle_updates_the_row`
  - `test_reextract_trigger_sends_conf`
- `DeadLetters.test.tsx`
  - `test_dead_letters_list_shows_headers_and_original_coordinates`

## Definition of done

```bash
cd services/ingestion-scraper && uv run pytest tests/unit/test_dag_tasks.py -q --strict-markers
cd services/backtesting && uv run pytest tests/unit/test_price_refresh_dag.py -q --strict-markers
cd services/core-hub && ./gradlew integrationTest --tests '*DeadLetterReadIT' --rerun-tasks
cd services/dashboard && npm run lint && npx tsc --noEmit && npm run test:ci && npm run build
```

Expected: 6, 1 and 4 passed; dashboard suite green with the 9 tests above included.

Then on the stack: trigger the PubMed DAG from `/pipeline`, see the run finish with its counts and the advanced cursor, and pause and resume it.

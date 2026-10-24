# Orchestration

Domain: OPS · Code: `services/ingestion-scraper/dags/`, `services/backtesting/dags/`, `services/backup/dags/`, `docker/docker-compose.yml` (service `airflow`) · Last reviewed against: develop @ `b7582c3`

## Scope

Airflow: which DAGs exist and what each calls, the rules every DAG follows, how ingestion runs are scheduled, pooled and retried, the DAG side of the ingestion cursor, and the Airflow secrets.

Not here:
- what `next_cursor` is and when the scraper returns which value, the extraction cap and the scraper HTTP API: [pipeline.md](../ingestion/pipeline.md);
- what each called endpoint does: the owner doc named in the catalogue below;
- the rule that DAGs hold no ingestion logic: INV-3 in [invariants.md](../system/invariants.md); the rule of one connector and one `sources.yaml` entry per source: INV-4;
- the schedule values themselves: each DAG file's `schedule=` and each `sources.yaml` entry's `schedule`. They are never copied into `docs/`;
- the Airflow container's memory and worker settings: [topology.md](topology.md); the alert on a failed DAG run and the statsd mapping: [observability.md](observability.md).

## Requirements

- <a id="OPS-024"></a>**OPS-024** — The stack's DAGs are exactly those in this table; each one's schedule is set in the file named.

  | DAG | File | Calls | Owner of what it calls |
  |---|---|---|---|
  | `auspex_<source_type>`, one per `sources.yaml` entry | `services/ingestion-scraper/dags/auspex_dags.py` (schedule from the entry's `schedule` in `services/ingestion-scraper/config/sources.yaml`) | scraper `POST /ingest/<source_type>` | [pipeline.md](../ingestion/pipeline.md) |
  | `auspex_price_refresh` | `services/backtesting/dags/price_refresh.py` | price-service `POST /prices/refresh` | [market-data.md](../research/market-data.md) |
  | `auspex_universe_build` | `services/backtesting/dags/universe_build.py` | price-service `POST /universe/build` | [universe.md](../research/universe.md) |
  | `auspex_backup` | `services/backup/dags/backup.py` | backup `POST /backup` | [backup.md](backup.md) |
  | `auspex_daily_health` | `services/ingestion-scraper/dags/daily_health.py` with `services/ingestion-scraper/dags/health_summary.py` | Prometheus' query API, then the alert contact (email or webhook) | [observability.md](observability.md) |

- <a id="OPS-025"></a>**OPS-025** — Every DAG holds no logic beyond its one call: it posts to one service endpoint (or, for the health summary, queries Prometheus and sends the message), applying INV-3 to every DAG. Every DAG sets `catchup=False` and `max_active_runs=1`, and its schedule is in UTC (INV-9).
- <a id="OPS-026"></a>**OPS-026** — `auspex_price_refresh`, `auspex_universe_build`, `auspex_backup` and `auspex_daily_health` are active at creation (`is_paused_upon_creation=False`). Ingestion DAGs are paused at creation (Airflow's `DAGS_ARE_PAUSED_AT_CREATION`, set in compose) and are switched on only once a gated extraction model exists (`SETUP.md`).
- <a id="OPS-027"></a>**OPS-027** — There is one ingestion DAG per `sources.yaml` entry, built in one loop with no source-specific branching (INV-4). An entry without a `schedule` gets a DAG that is never scheduled.
- <a id="OPS-028"></a>**OPS-028** — The scheduled sources start at distinct, spaced times, so runs do not pile up behind the single pool slot.
- <a id="OPS-029"></a>**OPS-029** — Every ingestion task runs in the one-slot `ingestion` pool, so one run at a time talks to the model server. The `airflow` service creates the pool before the scheduler starts.
- <a id="OPS-030"></a>**OPS-030** — Ingestion tasks retry, spaced apart (counts and spacing in `services/ingestion-scraper/dags/auspex_dags.py`), and the HTTP request to the scraper uses the task's execution timeout as its own timeout.
- <a id="OPS-031"></a>**OPS-031** — The non-ingestion DAGs retry (`default_args` in each file), and those that call a service fail the task on any HTTP error status.
- <a id="OPS-032"></a>**OPS-032** — Each source's cursor is the Airflow Variable `cursor:{source_type}`. Only the ingestion DAG's task reads and writes it, around its call to the scraper; the scraper never stores a cursor (INV-1).
- <a id="OPS-033"></a>**OPS-033** — The cursor position of every source can be read in the Airflow UI.
- <a id="OPS-034"></a>**OPS-034** — When the Variable does not exist, the task starts from `initial_lookback` days (from the source's `sources.yaml` entry) before the current time, in UTC.
- <a id="OPS-035"></a>**OPS-035** — The task posts the cursor to `/ingest/<source_type>`. When the run completes, the task writes the returned `next_cursor` to the Variable (never the current time) and leaves the Variable as it is when none is returned; then, if any document failed, it fails the task, so the run retries and shows red with the safe cursor already saved.
- <a id="OPS-036"></a>**OPS-036** — When the request to the scraper fails, the task leaves the Variable untouched.
- <a id="OPS-037"></a>**OPS-037** — `AIRFLOW_FERNET_KEY`, `AIRFLOW_JWT_SECRET` and `AIRFLOW_SECRET_KEY` come from `.env` as required references, so `up` stops when one is missing. The stored Variables and Connections can be read only with the same Fernet key, after a recreate and after a recovery from backup alike.
- <a id="OPS-038"></a>**OPS-038** — Compose sets no Airflow 2 `webserver.*` option; every Airflow setting uses its Airflow 3 name.
- <a id="OPS-039"></a>**OPS-039** — Airflow's admin password file is on the `airflow_state` volume, which `airflow-state-init` makes writable for Airflow's user before Airflow starts, so the password survives a recreate.

## Machine-readable authorities

| File | Governs | Notes |
|---|---|---|
| `services/ingestion-scraper/dags/auspex_dags.py` | Ingestion DAGs, pool name, retries, task timeout | OPS-027 to OPS-030, OPS-032 to OPS-036 |
| `services/backtesting/dags/price_refresh.py`, `services/backtesting/dags/universe_build.py`, `services/backup/dags/backup.py`, `services/ingestion-scraper/dags/daily_health.py` | The other DAGs, their schedules and retries | OPS-024 to OPS-026, OPS-031 |
| `services/ingestion-scraper/config/sources.yaml` | Each source's `schedule` and `initial_lookback` | Values stay there |
| `docker/docker-compose.yml` (service `airflow`) | DAG mounts, pool creation, paused-at-creation default, secrets | OPS-026, OPS-029, OPS-037 to OPS-039 |

## Verification

| ID | Source | Verified by | Status |
|---|---|---|---|
| OPS-024 | requirements §5; ``## 2026-10-07 — Startup data — CHOICE — data fills itself on `up`; prices refresh daily``; `specs/done/stack-backup.md`; `specs/done/pipeline-alerting-gaps.md`; `specs/point-in-time-universe.md` [`orchestration/README.md`; `docker/README.md`] | `services/ingestion-scraper/tests/unit/test_ingestion_dag.py::test_ingestion_dag_defines_one_dag_per_sources_entry`; `services/backup/tests/unit/test_backup_dag.py::test_backup_dag_posts_to_the_backup_service_and_fails_on_http_error`; `services/ingestion-scraper/tests/unit/test_daily_health_summary.py::test_daily_summary_dag_runs_once_a_day_at_seven_utc`; no test covers the price and universe DAGs | untested |
| OPS-025 | requirements §5; INV-3 [`orchestration/README.md`] | `services/ingestion-scraper/tests/unit/test_ingestion_dag.py::test_ingestion_dags_disable_catchup_and_run_one_at_a_time` covers ingestion only | untested |
| OPS-026 | ``## 2026-10-07 — Startup data — CHOICE — data fills itself on `up`; prices refresh daily`` (spelled in the matrix as 2026-10-07 — Startup data — CHOICE — data fills itself on up; prices refresh daily) [`orchestration/README.md`; `SETUP.md`] | no test reads `is_paused_upon_creation` or the compose default | untested |
| OPS-027 | requirements §5; INV-4; `specs/done/ingestion-run-reliability.md` [`services/ingestion-scraper/tests/unit/test_ingestion_dag.py`] | `services/ingestion-scraper/tests/unit/test_ingestion_dag.py::test_ingestion_dag_defines_one_dag_per_sources_entry`; `services/ingestion-scraper/tests/unit/test_ingestion_dag.py::test_dag_file_contains_no_source_specific_branching`; `services/ingestion-scraper/tests/unit/test_ingestion_dag.py::test_source_without_schedule_is_never_scheduled` | tested |
| OPS-028 | `## 2026-10-10 — Ingestion run reliability — CHOICE — schedule times, extraction cap and task timeout`; `specs/done/ingestion-run-reliability.md` [`services/ingestion-scraper/tests/unit/test_ingestion_dag.py`] | `services/ingestion-scraper/tests/unit/test_ingestion_dag.py::test_live_sources_start_at_distinct_times` | tested |
| OPS-029 | `specs/done/ingestion-run-reliability.md` [`services/ingestion-scraper/tests/unit/test_ingestion_dag.py`] | `services/ingestion-scraper/tests/unit/test_ingestion_dag.py::test_ingestion_tasks_use_the_single_slot_ingestion_pool`; `services/ingestion-scraper/tests/unit/test_ingestion_dag.py::test_airflow_creates_the_ingestion_pool_before_the_scheduler_starts` | tested |
| OPS-030 | `## 2026-10-10 — Ingestion run reliability — CHOICE — schedule times, extraction cap and task timeout`; `specs/done/ingestion-run-reliability.md` [`services/ingestion-scraper/tests/unit/test_ingestion_dag.py`] | `services/ingestion-scraper/tests/unit/test_ingestion_dag.py::test_ingestion_tasks_retry_twice_fifteen_minutes_apart`; `services/ingestion-scraper/tests/unit/test_ingestion_dag.py::test_ingestion_http_timeout_matches_the_task_execution_timeout` | tested |
| OPS-031 | `## 2026-10-22 — Living docs — PENDING — operations ratification batch`, approved by `## 2026-10-24 — Living docs — CHOICE — operations ratification batch` [`services/backtesting/dags/*.py`; `services/backup/dags/backup.py`; `services/ingestion-scraper/dags/daily_health.py`] | `services/backup/tests/unit/test_backup_dag.py::test_backup_dag_posts_to_the_backup_service_and_fails_on_http_error` covers the backup DAG only | untested |
| OPS-032 | requirements §0.2; requirements §5; INV-1 | `services/ingestion-scraper/tests/unit/test_ingestion_dag.py::test_dag_task_posts_the_cursor_to_the_scraper_ingest_endpoint`; `services/ingestion-scraper/tests/unit/test_ingestion_dag.py::test_cursor_advances_to_the_reported_next_cursor_after_a_successful_run` | tested |
| OPS-033 | requirements §12 | holds because the cursor is a Variable (OPS-032); not checked | untested |
| OPS-034 | requirements §5; `## 2026-10-17 — Living docs — CHOICE — initial_lookback value` | `services/ingestion-scraper/tests/unit/test_ingestion_dag.py::test_first_run_starts_initial_lookback_days_back_in_utc` | tested |
| OPS-035 | requirements §5; `## 2026-10-09 — Soak-test readiness — CHOICE — cursor after a run with failed documents` | `services/ingestion-scraper/tests/unit/test_ingestion_dag.py::test_cursor_advances_to_the_reported_next_cursor_after_a_successful_run`; `services/ingestion-scraper/tests/unit/test_ingestion_dag.py::test_run_that_processed_nothing_leaves_cursor_unchanged`; `services/ingestion-scraper/tests/unit/test_ingestion_dag.py::test_ingestion_task_saves_the_safe_cursor_then_fails_when_documents_failed` | tested |
| OPS-036 | requirements §5 | `services/ingestion-scraper/tests/unit/test_ingestion_dag.py::test_ingestion_task_leaves_the_cursor_untouched_when_the_request_fails` | tested |
| OPS-037 | `## 2026-10-10 — Stack state persistence — CHOICE — required secrets and a writable state volume`; `specs/done/stack-state-persistence.md` [`docker/docker-compose.yml`; `docker/README.md`; `docker/CLAUDE.md`] | `services/ingestion-scraper/tests/unit/test_stack_persistence_config.py::test_airflow_fernet_key_jwt_secret_and_api_secret_key_are_required_env_references` | tested |
| OPS-038 | `specs/done/stack-state-persistence.md`; `## 2026-10-10 — Stack state persistence — VERIFIED — Airflow 3.3.1 option names` [`services/ingestion-scraper/tests/unit/test_stack_persistence_config.py`] | `services/ingestion-scraper/tests/unit/test_stack_persistence_config.py::test_airflow_uses_no_airflow_2_webserver_options` | tested |
| OPS-039 | `## 2026-10-10 — Stack state persistence — CHOICE — required secrets and a writable state volume`; `specs/done/stack-state-persistence.md` [`services/ingestion-scraper/tests/unit/test_stack_persistence_config.py`] | `services/ingestion-scraper/tests/unit/test_stack_persistence_config.py::test_airflow_password_file_is_on_the_airflow_state_volume`; `services/ingestion-scraper/tests/unit/test_stack_persistence_config.py::test_airflow_state_volume_is_made_writable_for_the_airflow_user_before_airflow_starts` | tested |

## Known traps

- Airflow 3 renamed `schedule_interval` to `schedule`. Task code cannot reach the metadata database directly; Variables and Connections go through the Task SDK (`airflow.sdk.Variable`). (from `CLAUDE.md`, Known traps; requirements §5)
- When no Fernet key is set, Airflow generates one into `airflow.cfg` inside the container. A recreated container then has a new key, and every encrypted Variable (the ingestion cursors) and Connection becomes unreadable; hence OPS-037. The `AIRFLOW__WEBSERVER__*` names are Airflow 2 and are ignored by Airflow 3 (OPS-038). (from `CLAUDE.md`, Known traps)

## Rationale

- Airflow owns when a source is polled; there is no message queue for scheduling. Airflow as scheduler with Kafka as the event backbone was a settled choice (requirements §14). (requirements §5)
- Overlapping fetch windows were judged acceptable: they break at roughly five times today's volume, not a hundred. (requirements §5)
- Saving the safe cursor before failing the task means an unattended run never loses documents to a model-server outage or a sleeping Mac, while the processed markers stop the retry from re-extracting what already succeeded.

## Retired requirements

None.

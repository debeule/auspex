# Stack backup

**Status:** blocked
**Blocked by:** `specs/done/stack-state-persistence.md` merging into `develop` (it fixes the compose project name and the Airflow secrets, which a restored Airflow database depends on)
**Branch:** `feature/stack-backup`

---

## Context

Every store in the stack keeps its data on a named volume in Docker Desktop's VM disk (`docker/docker-compose.yml`, top-level `volumes:`). That survives deleting containers and images, but not "Clean / Purge data", "Reset to factory defaults", reinstalling Docker Desktop, `docker system prune --volumes` or `down -v`. Some of that data can't be rebuilt:

- **MinIO `auspex-prices`**: OHLCV snapshots are append-only by design (`services/backtesting/src/auspex_backtesting/prices/price_refresher.py`). Providers re-adjust history, so a refetch does not give back the same bars. `universe/{version}/` holds the pinned `rules.yaml` and the monthly members (`universe/store.py`).
- **MinIO `auspex-raw`**: the raw archive (Invariant 13). Re-fetching is slow and rate-limited, and some sources revise documents.
- **Postgres `auspex`**: signals, extraction history, corroboration, watermark and watchlist (Flyway V1–V4). Rebuilding it means re-running the LLM over the whole archive.
- **Postgres `airflow`**: ingestion cursors (Variables `cursor:{source_type}`), DAG paused state and run history.
- **Neo4j**: the signal graph core-hub writes with `MERGE` (`persistence/Neo4jWriteService.java`). It mirrors `signal_current`, but no code rebuilds it from Postgres.

The owner decided on 2026-10-09 to back these up every night to a folder on the Mac (`DECISIONS.md`, "Stack backup — CHOICE"). The pattern for scheduled work is fixed (root `CLAUDE.md`, "Where work can run"): an Airflow DAG calls a service HTTP API, and the DAG holds no logic. `services/backtesting` (Flask + gunicorn `price-service`, DAGs in `services/backtesting/dags/`) is the model to copy.

## What this builds

- A `backup` service (`services/backup/`, package `auspex_backup`, Flask + gunicorn) on the compose network only, with no published port. `POST /backup` runs one backup and returns its manifest. `GET /health` is the healthcheck.
- One backup writes to `/backup`, which is bind-mounted from `${BACKUP_HOST_DIR}` (an absolute path on the Mac, for example `/Users/<you>/auspex-backup`, inside Docker Desktop's shared folders):
  - `postgres/<YYYY-MM-DD>/auspex.dump` and `airflow.dump`: `pg_dump --format=custom`, one dated folder per run.
  - `neo4j/<YYYY-MM-DD>/graph.jsonl`: every node (element id, labels, properties) and relationship (type, endpoint ids, properties), read in one read transaction over bolt. No downtime is needed. Community edition can only `neo4j-admin database dump` offline.
  - `minio/<bucket>/<object key>`: an additive mirror of `auspex-raw` and `auspex-prices`. An object is copied when it is new or its ETag or size changed. An object deleted from MinIO stays in the mirror.
  - `last_success.json`: UTC start and end, per-store counts and bytes. Written last, by atomic rename, and only when every store succeeded.
  - Dated Postgres and Neo4j folders older than `BACKUP_KEEP_DAYS` (default 14) are pruned after a successful run. The newest folder is never pruned.
- An Airflow DAG `auspex_backup` (`services/backup/dags/backup.py`, mounted into Airflow like the price DAGs) runs daily at 03:00 UTC with `catchup=False`, unpaused at creation, with retries. It only posts to `POST /backup` and fails on any HTTP error.
- A `restore` one-shot in compose profile `restore` (`docker compose --profile restore ... run --rm restore --date YYYY-MM-DD`). It restores Postgres (`pg_restore` into both databases), Neo4j (replays `graph.jsonl`: each node with its labels and properties, then each relationship between the restored nodes) and MinIO (uploads the mirror). It refuses any target store that isn't empty. `docs/backup-restore.md` is the runbook for a session on the Mac: when to restore, the order (stop the `app` profile, then `up` the infra on fresh volumes, `restore`, then start the `app` profile), and what to check afterwards.
- `SETUP.md` gains `BACKUP_HOST_DIR`, a note that Time Machine should include that folder, and a note that `.env` is the only copy of the stack's secrets and must be kept somewhere safe as well.

## Out of scope

- Off-site or cloud copies. Time Machine covers the folder; anything further is the owner's choice.
- Backing up Elasticsearch, Prometheus and Grafana. Logs and metrics are rebuildable or disposable, and Grafana is provisioned from the repo.
- Kafka. Messages are transient: everything consumed is in Postgres and Neo4j, and the raw archive is in MinIO.
- Alerting on a failed or stale backup. Alerting belongs to the multi-week test run readiness work. This spec exposes `last_success.json` and the failed DAG run.
- Encrypting the backup folder (FileVault covers the Mac's disk).

## Constraints

- **Invariants 1 and 2:** the backup service only reads from MinIO, Postgres and Neo4j. Writing back is the job of `restore`, a recovery tool run with core-hub stopped, never during normal operation. The DECISIONS.md CHOICE entry records this boundary.
- **Invariant 6:** credentials come from `.env` through compose env. The Postgres password reaches `pg_dump` and `pg_restore` through the `PGPASSWORD` environment, never `argv`.
- **Invariant 8:** synchronous Python only.
- **Invariant 9:** dated folder names and manifest timestamps are UTC.
- **Invariant 12:** no string-built Cypher or SQL. The Neo4j export and replay use parameterized queries. Labels and relationship types, which Cypher can't parameterize, are checked against `^[A-Za-z_][A-Za-z0-9_]*$` before use.
- **`pg_dump` must match the server's major version (18).** The image installs `postgresql-client-18` from the PostgreSQL apt repository; Debian's own client is older and refuses a newer server. Pin it in `VERSIONS.md`.
- **Python 3.14.2 and uv** like the other Python services. Add `services/backup` to `.github/workflows/python.yml` (lint, types, unit, integration) and its uv cache key.
- Compose conventions from #29: a `mem_limit` from `.env.example` within the memory-budget test, and the `co.elastic.logs/enabled` label. New variables go into `.env.example`'s existing grouping with minimal edits.
- A backup that fails part-way leaves the previous `last_success.json` in place and returns HTTP 500 naming the failed store.
- Doc maintenance table in root `CLAUDE.md`: new Docker service → `docker/README.md`; new dev command (`restore`) → `README.md` and `docker/README.md`.

## Required tests

Unit (`services/backup/tests/unit/`, no containers, fake clients):
- `test_minio_mirror_copies_only_new_or_changed_objects`
- `test_minio_mirror_keeps_objects_deleted_from_minio`
- `test_postgres_dump_runs_custom_format_pg_dump_for_both_databases_with_password_only_in_env`
- `test_dated_folders_older_than_keep_days_are_pruned_and_the_newest_never_is`
- `test_manifest_is_written_last_and_only_when_every_store_succeeded`
- `test_failed_store_returns_500_naming_it_and_keeps_the_previous_manifest`
- `test_neo4j_export_writes_every_node_and_relationship_with_labels_and_properties`
- `test_neo4j_replay_rejects_a_label_that_is_not_a_plain_identifier`
- `test_backup_reads_but_never_writes_to_minio_postgres_or_neo4j`
- `test_restore_refuses_a_target_store_that_is_not_empty`
- `test_backup_dag_posts_to_the_backup_service_and_fails_on_http_error`

Static compose checks (`services/ingestion-scraper/tests/unit/test_stack_backup_config.py`):
- `test_backup_destination_is_a_bind_mount_from_backup_host_dir`
- `test_backup_dag_directory_is_mounted_into_airflow`
- `test_restore_service_runs_only_under_the_restore_profile`

Integration (`services/backup/tests/integration/`, testcontainers, CI only):
- `test_postgres_backup_and_restore_round_trip_gives_identical_rows`
- `test_neo4j_backup_and_restore_round_trip_gives_identical_graph`
- `test_minio_backup_and_restore_round_trip_gives_identical_objects`

## Definition of done

```bash
cd services/backup && uv run ruff check . && uv run mypy src && uv run pytest tests/unit -q --strict-markers
cd services/ingestion-scraper && uv run pytest tests/unit/test_stack_backup_config.py -q --strict-markers
cd services/ingestion-scraper && uv run pytest tests/unit -q --strict-markers   # memory budget still green
```

Expected: 11 passed; 3 passed; the unit suite green. In CI: the 3 integration tests pass.

**On the stack machine** (step 8 of `specs/first-run-on-stack-machine.md` picks this up):
Set `BACKUP_HOST_DIR`, `up` with the `app` profile, then trigger `auspex_backup` once from Airflow. Check that `last_success.json` exists, its counts match `select count(*) from signal_current`, the Neo4j node count and the MinIO object counts, both `.dump` files are non-empty, and `pg_restore --list` reads each one. A full restore drill against live data is left out: the fixed `container_name`s stop a second copy of the stack from running beside the live one, and the round trip is proven by the integration tests. Record the outcome as a VERIFIED or FLAG entry in `DECISIONS.md`.

## Notes

- The MinIO mirror is additive, so a corrupted or deleted object can be recovered from the mirror. It grows with the raw archive. Price snapshots are rewritten in place every refresh, and since they only gain bars, the mirror's latest copy contains every earlier one.
- Element ids in `graph.jsonl` are only for linking relationships to nodes within one file. Replay creates nodes with their labels and properties and maps old ids to new ones. The graph's own uniqueness constraints (`Neo4jSchemaInitializer`) are created by core-hub on its next start.
- Restoring the `airflow` database also restores encrypted Variables. They decrypt only with the same `AIRFLOW_FERNET_KEY`, which is why this spec waits for stack state persistence and why `.env` must be kept safe.

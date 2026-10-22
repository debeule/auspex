# Backup

Domain: OPS · Code: `services/backup/`, `docker/docker-compose.yml` (services `backup`, `restore`) · Last reviewed against: develop @ `b7582c3`

## Scope

What the nightly backup copies, how a run behaves, what is kept and for how long, and what is not backed up.

Not here:
- recovery: the `restore` one-shot is the one approved writer besides core-hub, and its conditions are written only as the exception under [INV-2](../system/invariants.md#INV-2). The procedure is the runbook [backup-restore.md](../backup-restore.md);
- the DAG rules the backup DAG shares with every other DAG: [orchestration.md](orchestration.md);
- the backup image and its memory limit: [topology.md](topology.md).

## Requirements

- <a id="OPS-060"></a>**OPS-060** — Every night the DAG `auspex_backup` posts once to the backup service's `POST /backup` and fails on any HTTP error. The backup writes into `/backup`, a bind mount of the host folder `BACKUP_HOST_DIR`.
- <a id="OPS-061"></a>**OPS-061** — Both Postgres databases (`BACKUP_DATABASES`: the application database and Airflow's) are dumped with `pg_dump` in custom format into a dated folder. The password reaches `pg_dump` only through the environment, never the command line, and a failed dump leaves no partial file.
- <a id="OPS-062"></a>**OPS-062** — The whole Neo4j graph is exported over bolt in one read transaction into a dated folder: every node with its labels and properties, then every relationship with its type, endpoints and properties.
- <a id="OPS-063"></a>**OPS-063** — The MinIO mirror covers every bucket `minio-init` creates.
- <a id="OPS-064"></a>**OPS-064** — The MinIO mirror is additive and undated: an object is copied when it is new, changed, or missing from the mirror; an object deleted from MinIO stays in the mirror; the mirror is never pruned.
- <a id="OPS-065"></a>**OPS-065** — The mirror refuses an object key that would resolve outside its bucket's folder.
- <a id="OPS-066"></a>**OPS-066** — After a successful run, dated Postgres and Neo4j folders strictly older than `BACKUP_KEEP_DAYS` are pruned; the newest dated folder is never pruned.
- <a id="OPS-067"></a>**OPS-067** — A run backs up every store even after one has failed. `last_success.json` is written last, by atomic rename, and only when every store succeeded; otherwise the endpoint answers 500 naming the failed stores and the previous `last_success.json` stays.
- <a id="OPS-068"></a>**OPS-068** — `POST /backup` answers 409 while a run is in progress.
- <a id="OPS-069"></a>**OPS-069** — The backup only reads Postgres, Neo4j and MinIO (INV-1, INV-2).
- <a id="OPS-070"></a>**OPS-070** — Values in Cypher are parameterised; node labels and relationship types, which Cypher cannot bind, are checked against a plain-identifier pattern before use (INV-12).
- <a id="OPS-071"></a>**OPS-071** — Elasticsearch, Prometheus, Grafana and Kafka are not backed up: logs and metrics are disposable or rebuilt, Grafana is provisioned from the repository, and everything Kafka carried is in Postgres, Neo4j or the raw archive.

Recovery from a backup writes the stores only under the exception to INV-2; this file does not restate it. Steps: [backup-restore.md](../backup-restore.md).

## Machine-readable authorities

| File | Governs | Notes |
|---|---|---|
| `docker/docker-compose.yml` (service `backup`) | `BACKUP_DATABASES`, `BACKUP_BUCKETS`, the `/backup` mount | OPS-061, OPS-063 |
| `.env.example` | `BACKUP_KEEP_DAYS`, `BACKUP_HOST_DIR` | Values never copied here |
| `services/backup/dags/backup.py` | Schedule and retries | OPS-060 |

## Verification

| ID | Source | Verified by | Status |
|---|---|---|---|
| OPS-060 | `## 2026-10-09 — Stack backup — CHOICE — nightly backup to a folder on the Mac`; `specs/done/stack-backup.md` [`docs/backup-restore.md`] | `services/backup/tests/unit/test_backup_dag.py::test_backup_dag_posts_to_the_backup_service_and_fails_on_http_error`; `services/ingestion-scraper/tests/unit/test_stack_backup_config.py::test_backup_destination_is_a_bind_mount_from_backup_host_dir` | tested |
| OPS-061 | `specs/done/stack-backup.md` [`docs/backup-restore.md`] | `services/backup/tests/unit/test_postgres_dump.py::test_postgres_dump_runs_custom_format_pg_dump_for_both_databases_with_password_only_in_env`; `services/backup/tests/unit/test_postgres_dump.py::test_a_failed_dump_leaves_no_partial_dump_file` | tested |
| OPS-062 | `specs/done/stack-backup.md` [`docs/backup-restore.md`] | `services/backup/tests/unit/test_graph.py::test_neo4j_export_writes_every_node_and_relationship_with_labels_and_properties` | tested |
| OPS-063 | `## 2026-10-10 — Strategy runtime — CHOICE — state placement, timing and the pass-through stub` (item 1) [`docs/backup-restore.md`] | `BACKUP_BUCKETS` (`docker/docker-compose.yml:247`) and `stack_buckets()` (`services/backtesting/src/auspex_backtesting/stack_bootstrap.py:35`) are two lists that no test ties together; a new bucket would go unmirrored silently | untested |
| OPS-064 | `specs/done/stack-backup.md` [`docs/backup-restore.md`] | `services/backup/tests/unit/test_minio_mirror.py::test_minio_mirror_copies_only_new_or_changed_objects`; `services/backup/tests/unit/test_minio_mirror.py::test_minio_mirror_recopies_an_object_whose_mirror_file_is_missing`; `services/backup/tests/unit/test_minio_mirror.py::test_minio_mirror_keeps_objects_deleted_from_minio` | tested |
| OPS-065 | `specs/done/stack-backup.md` [`services/backup/tests/unit/test_minio_mirror.py`] | `services/backup/tests/unit/test_minio_mirror.py::test_minio_mirror_refuses_a_key_that_escapes_the_bucket_folder` | tested |
| OPS-066 | `## 2026-10-10 — Stack backup — CHOICE — client tools from the server image, memory and restore semantics` (item 3); `specs/done/stack-backup.md` [`docs/backup-restore.md`] | `services/backup/tests/unit/test_prune.py::test_dated_folders_older_than_keep_days_are_pruned_and_the_newest_never_is`; `services/backup/tests/unit/test_backup_run.py::test_successful_backup_prunes_old_dated_folders` | tested |
| OPS-067 | `## 2026-10-10 — Stack backup — CHOICE — client tools from the server image, memory and restore semantics` (item 3); `specs/done/stack-backup.md` [`docs/backup-restore.md`; `services/backup/README.md`] | `services/backup/tests/unit/test_backup_run.py::test_manifest_is_written_last_and_only_when_every_store_succeeded`; `services/backup/tests/unit/test_backup_run.py::test_failed_store_returns_500_naming_it_and_keeps_the_previous_manifest` | tested |
| OPS-068 | `## 2026-10-22 — Living docs — PENDING — operations ratification batch` [`services/backup/src/auspex_backup/api.py`; `services/backup/README.md`] | no test | pending-decision |
| OPS-069 | `## 2026-10-09 — Stack backup — CHOICE — nightly backup to a folder on the Mac`; `specs/done/stack-backup.md` [`services/backup/README.md`] | `services/backup/tests/unit/test_backup_run.py::test_backup_reads_but_never_writes_to_minio_postgres_or_neo4j` | tested |
| OPS-070 | INV-12; `specs/done/stack-backup.md` [`services/backup/README.md`] | `services/backup/tests/unit/test_graph.py::test_neo4j_replay_rejects_a_label_that_is_not_a_plain_identifier` | tested |
| OPS-071 | `specs/done/stack-backup.md` | an exclusion; nothing to test | untested |

## Known traps

- The MinIO mirror has no date (OPS-064), while the Postgres and Neo4j copies are dated. A recovery for an earlier date therefore pairs those dated databases with the latest mirror, which may hold newer objects (processed markers, strategy checkpoints) than the databases expect. Whether that can suppress work after a recovery has not been analysed. (from `docs/backup-restore.md`)

## Rationale

- A bind-mounted folder on the Mac, nightly, because named volumes do not survive Docker Desktop's "Purge data" or a factory reset, and Time Machine covers the folder (`## 2026-10-09 — Stack backup — CHOICE — nightly backup to a folder on the Mac`).

## Retired requirements

None.

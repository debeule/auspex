# Backup service

Copies Postgres, Neo4j and MinIO into `BACKUP_HOST_DIR` on the host every night, and restores one dated copy into empty stores. Restoring step by step: [docs/backup-restore.md](../../docs/backup-restore.md).

Commands: [AGENTS.md](AGENTS.md).

| Piece | What it is |
|---|---|
| `POST /backup` (`auspex_backup.api`) | One backup run: database dumps (`BACKUP_DATABASES`), the Neo4j export, the MinIO mirror (`BACKUP_BUCKETS`), `last_success.json` and pruning |
| `GET /health` | Compose healthcheck and blackbox probe |
| `dags/backup.py` | The Airflow DAG `auspex_backup`, which posts to `BACKUP_API_URL/backup` |
| `python -m auspex_backup.restore --date YYYY-MM-DD` | The compose service `restore` (profile `restore`) |

The image is built on `postgres:18.6`, so `pg_dump` and `pg_restore` come from the server's own image.

## Where the rules are

- What a run reads and writes, its schedule, outcomes, pruning and the restore: [docs/operations/backup.md](../../docs/operations/backup.md).
- The restore boundary: the exception under INV-2 in [docs/system/invariants.md](../../docs/system/invariants.md).

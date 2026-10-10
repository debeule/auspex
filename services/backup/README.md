# Backup service

Copies Postgres, Neo4j and MinIO into `BACKUP_HOST_DIR` on the host every night, and restores
one dated copy into empty stores. Restoring step by step: `docs/backup-restore.md`.

| Piece | What it does |
|---|---|
| `POST /backup` (`auspex_backup.api`) | One run: `pg_dump --format=custom` of `BACKUP_DATABASES`, Neo4j export to `graph.jsonl` in one read transaction, additive mirror of `BACKUP_BUCKETS`; then `last_success.json` and pruning. 200 with the manifest, 500 naming the failed stores, 409 while a run is in progress |
| `GET /health` | Compose healthcheck and blackbox probe |
| `dags/backup.py` | Airflow DAG `auspex_backup`, daily 03:00 UTC, posts to `BACKUP_API_URL/backup` and fails on any HTTP error |
| `python -m auspex_backup.restore --date YYYY-MM-DD` | Compose service `restore` (profile `restore`): checks every target is empty, then `pg_restore`, graph replay and upload |

## Key constraints

- The backup only reads from the stores (Invariants 1 and 2). Writing them back is `restore`'s job, run by hand with core-hub stopped.
- The Postgres password reaches `pg_dump` and `pg_restore` only through `PGPASSWORD`, never their command line.
- Labels and relationship types are written into Cypher only after matching `^[A-Za-z_][A-Za-z0-9_]*$`; every value is a parameter.
- The image is built on `postgres:18.6`, so `pg_dump` matches the server's major version.

## Commands

```bash
uv sync
uv run ruff check . && uv run mypy src
uv run pytest tests/unit -q            # fakes, no containers
uv run pytest tests/integration -q     # Postgres, Neo4j and LocalStack containers; CI runs these
```

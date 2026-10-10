# Backup and restore

The stack backs itself up every night at 03:00 UTC (Airflow DAG `auspex_backup`, which calls the
`backup` service). Everything goes into `BACKUP_HOST_DIR`, a folder on the Mac that Time Machine
also copies.

## What is in the folder

| Path | What | Kept |
|---|---|---|
| `postgres/<YYYY-MM-DD>/auspex.dump`, `airflow.dump` | `pg_dump --format=custom` of the application and Airflow databases | `BACKUP_KEEP_DAYS` (14), newest always |
| `neo4j/<YYYY-MM-DD>/graph.jsonl` | Every node (labels, properties) and relationship (type, endpoints, properties) | `BACKUP_KEEP_DAYS` (14), newest always |
| `minio/auspex-raw/…`, `minio/auspex-prices/…` | Mirror of both buckets; objects deleted from MinIO stay here | Never pruned |
| `minio/.index/<bucket>.json` | ETag and size per mirrored object, so a run copies only what changed | — |
| `last_success.json` | UTC start and end and per-store counts of the last run in which every store succeeded | Replaced by the next full success |

Dates are UTC. A failed run leaves the previous `last_success.json` in place and shows red in Airflow.

## When to restore

Only when the stores themselves are gone or wrong, for example after Docker Desktop's "Reset to
factory defaults", "Clean / Purge data", a reinstall, `docker system prune --volumes` or `down -v`.
A recreated container or image needs no restore: the named volumes survive it
(`docker/README.md`, "What survives a recreate").

Pick the date from `last_success.json` (its `date`), or an earlier dated folder if the newest
backup already holds the problem. The MinIO mirror has no dates: it is the latest copy of every
object ever backed up.

## Order

Restore needs empty stores and refuses any store that already holds data, so nothing may write
to them first: not core-hub (Flyway, the graph), not Airflow (its own migrations), not the
scraper.

```bash
# 1. Stop everything (keeps volumes). Then, only if the stores are wrong rather than gone,
#    remove their volumes; that deletes their data.
docker compose --profile app -f docker/docker-compose.yml --env-file .env down

# 2. Start only the stores restore writes to.
docker compose -f docker/docker-compose.yml --env-file .env up -d --wait postgres neo4j minio

# 3. Restore one date.
docker compose --profile restore -f docker/docker-compose.yml --env-file .env run --rm restore --date YYYY-MM-DD

# 4. Start the rest.
docker compose --profile app -f docker/docker-compose.yml --env-file .env up -d --wait
```

`.env` must hold the same `AIRFLOW_FERNET_KEY` the backup was taken under, or Airflow's stored
Variables (the ingestion cursors) restore but do not decrypt.

Restore checks every target first and writes nothing if one holds data; it prints which.
It then runs `pg_restore` into both databases, replays `graph.jsonl` into Neo4j, and uploads the
mirror into both buckets.

## Checks afterwards

- `MATCH (n) RETURN count(n)` in Neo4j Browser equals `stores.neo4j.nodes` in the
  `last_success.json` of the date you restored (a later run replaces that file, so note it first).
- Each bucket in the MinIO console holds at least `stores.minio.<bucket>_objects` objects; more if
  the mirror kept objects deleted since.
- Airflow shows the ingestion DAGs with their previous paused state, and
  `docker exec auspex-airflow airflow variables get cursor:<source>` prints a date.
- core-hub starts without a Flyway error, and the dashboard lists the signals.

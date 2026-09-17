# CLAUDE.md — docker/

Auto-loaded when working in this directory.

## Commands

```bash
docker compose -f docker/docker-compose.yml --env-file .env up -d --wait   # bring up
docker compose -f docker/docker-compose.yml --env-file .env down            # keep volumes
docker compose -f docker/docker-compose.yml --env-file .env down -v         # wipe volumes
```

## Topic provisioning

`provision.sh` runs on first `up` and creates Kafka topics from `topics.yaml`.
If topic counts are wrong: `down -v` then `up` again.

**DLT topic partition count must match the source topic.** Spring's `DeadLetterPublishingRecoverer`
uses partition `-1` (producer chooses from available partitions) — if counts differ, DLT publishing
fails silently. We use lowercase `.dlt` suffix, not `.DLT`. Verify partition parity whenever adding
a topic pair.

## Environment

All credentials from root `.env`. No defaults in docker-compose.yml. Ports are bound to
`127.0.0.1` — local only, intentional.

## Service health

`--wait` in the up command blocks until all healthchecks pass.
`auspex-airflow` healthcheck is slow (~60s) — normal, not a failure.

## Postgres databases

Two databases share one container: `auspex` (application, role `auspex_app`) and `airflow`
(Airflow metadata, role `airflow`). Created by `postgres-init/01_airflow.sh` on first volume init.
If you wipe volumes, both are recreated from scratch — Flyway re-runs migrations on next `core-hub` start.

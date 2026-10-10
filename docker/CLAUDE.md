# CLAUDE.md — docker/

Auto-loaded when working in this directory.

## Commands

```bash
docker compose -f docker/docker-compose.yml --env-file .env up -d --wait   # bring up
docker compose -f docker/docker-compose.yml --env-file .env down            # keep volumes
docker compose -f docker/docker-compose.yml --env-file .env down -v         # destroys all data (every volume); never a fix
```

## Topic provisioning

The `kafka-init` one-shot (`kafka-init/create-topics.sh`) creates topics from `topics.yaml` on every `up`;
`minio-init` creates the buckets and `price-bootstrap` fills missing price snapshots. All three are
no-ops when the data exists. A wrong partition count is fixed on that topic alone (`docker/README.md`, Kafka topics), never with `down -v`, which destroys all data.

Startup data belongs in a one-shot compose service; data that must stay current belongs in an
Airflow DAG. Never a script to run by hand (root `CLAUDE.md`, "Where work can run").

**DLT topic partition count must match the source topic.** Spring's `DeadLetterPublishingRecoverer`
defaults to the source record's partition number, which fails when the DLT has fewer partitions; our
resolver returns `-1` (producer chooses), and we keep counts equal anyway. We use lowercase `.dlt`,
not `.DLT`. Verify partition parity whenever adding a topic pair.

## Environment

All values from root `.env`; every variable `.env.example` defines is a bare `${VAR}` in
docker-compose.yml (or `${VAR:?message}` where an unset value must stop `up`), with the value written once, in
`.env.example` (`test_compose_gives_no_default_to_env_example_variables`). Ports are bound to
`127.0.0.1` — local only, intentional; exporters publish none.

## Monitoring

Every service needs a `mem_limit` from `.env`, the `co.elastic.logs/enabled` label, and, if it has a
healthcheck, a Prometheus scrape job or blackbox probe. The long-running limits must fit 7.5 GB.
Grafana expands `$VAR` in `grafana/provisioning/alerting/*.yaml`: write a literal `$` (as in
`{{ $$labels.instance }}`) as `$$`, or it silently becomes empty. Alert PromQL is tested with
promtool in `tests/unit/test_stack_alert_expressions.py`; add a case for every new rule.

## State across recreates

Every stateful path is on a named volume; `test_stack_persistence_config.py` lists them. A new
stateful service gets a named volume declared under top-level `volumes:` and mounted read-only into
`volume-usage`. Airflow's Fernet key, JWT secret and API secret key come from `.env` as required
`${VAR:?...}` references: if Airflow generated them, a recreate would replace them and the stored
cursors would no longer decrypt.
Never suggest `down -v` as a fix: it destroys all data, and every mention must say so.
Password changes in place are in `docker/README.md`.

## Service health

`--wait` in the up command blocks until all healthchecks pass.
`auspex-airflow` healthcheck is slow (~60s) — normal, not a failure.

## Postgres databases

Two databases share one container: `auspex` (application, role `auspex_app`) and `airflow`
(Airflow metadata, role `airflow`). Created by `postgres-init/01_airflow.sh` on first volume init; `airflow-db-role` re-applies the
Airflow role's password from `.env` on every `up`.
If you wipe volumes, both are recreated from scratch — Flyway re-runs migrations on next `core-hub` start.

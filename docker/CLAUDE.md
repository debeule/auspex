# CLAUDE.md — docker/

Auto-loaded when working in this directory.

## Commands

```bash
docker compose -f docker/docker-compose.yml --env-file .env up -d --wait   # bring up
docker compose -f docker/docker-compose.yml --env-file .env down            # keep volumes
docker compose -f docker/docker-compose.yml --env-file .env down -v         # wipe volumes
```

## Topic provisioning

The `kafka-init` one-shot (`kafka-init/create-topics.sh`) creates topics from `topics.yaml` on every `up`;
`minio-init` creates the buckets and `price-bootstrap` fills missing price snapshots. All three are
no-ops when the data exists. If topic counts are wrong: `down -v` then `up` again.

Startup data belongs in a one-shot compose service; data that must stay current belongs in an
Airflow DAG. Never a script to run by hand (root `CLAUDE.md`, "Where work can run").

**DLT topic partition count must match the source topic.** Spring's `DeadLetterPublishingRecoverer`
defaults to the source record's partition number, which fails when the DLT has fewer partitions; our
resolver returns `-1` (producer chooses), and we keep counts equal anyway. We use lowercase `.dlt`,
not `.DLT`. Verify partition parity whenever adding a topic pair.

## Environment

All values from root `.env`; new variables use a bare `${VAR}` in docker-compose.yml, with the
value written once, in `.env.example`. Ports are bound to
`127.0.0.1` — local only, intentional; exporters publish none.

## Monitoring

Every service needs a `mem_limit` from `.env`, the `co.elastic.logs/enabled` label, and, if it has a
healthcheck, a Prometheus scrape job or blackbox probe. The long-running limits must fit 7.5 GB.
Grafana expands `$VAR` in `grafana/provisioning/alerting/*.yaml`: write a literal `$` (as in
`{{ $$labels.instance }}`) as `$$`, or it silently becomes empty. Alert PromQL is tested with
promtool in `tests/unit/test_stack_alert_expressions.py`; add a case for every new rule.

## Service health

`--wait` in the up command blocks until all healthchecks pass.
`auspex-airflow` healthcheck is slow (~60s) — normal, not a failure.

## Postgres databases

Two databases share one container: `auspex` (application, role `auspex_app`) and `airflow`
(Airflow metadata, role `airflow`). Created by `postgres-init/01_airflow.sh` on first volume init.
If you wipe volumes, both are recreated from scratch — Flyway re-runs migrations on next `core-hub` start.

# docker

## Owners

- `docs/operations/topology.md`, `docs/operations/orchestration.md`, `docs/operations/observability.md`, `docs/operations/backup.md`.
- Topics in `docker/topics.yaml`: `docs/system/contracts.md`.

## Commands

None here: stack commands (up, down, smoke test, restore) are in the root `README.md`. Changing a password in place: `docker/README.md`.

## Layout

- `docker-compose.yml`; `topics.yaml` with `kafka-init/`; `postgres-init/`, `airflow-db-role/`, `postgres-monitor/`.
- Monitoring: `prometheus/`, `grafana/`, `elasticsearch/`, `filebeat/`, `blackbox-exporter/`, `statsd-exporter/`, `volume-usage/`.

## Requirements that bite here

- OPS-009: one-shots are no-ops when the data exists.
- OPS-006: bare `${VAR}` for `.env.example` variables.
- OPS-014: `mem_limit` from `.env`.
- OPS-042: shared rotating logging setting.
- OPS-043: log-shipping label on every service.
- OPS-044: scrape job or probe for a healthcheck.
- OPS-005: ports bound to `127.0.0.1`.
- OPS-017: stateful paths on named volumes.
- OPS-019: `down -v` destroys all data and is never a fix.
- OPS-037: Airflow secrets from `.env`.
- OPS-056: a promtool case per alert rule.
- CON-001: topics only from `topics.yaml`.
- CON-004: DLT partition parity.

## Trap pointers

- OPS-057: Grafana expands `$VAR` in alerting files; write `$$`: `docs/operations/observability.md`, Known traps.
- OPS-037: Airflow generates a Fernet key when none is set: `docs/operations/orchestration.md`, Known traps.
- OPS-011: Airflow's healthcheck takes about a minute: `docs/operations/topology.md`, Known traps.

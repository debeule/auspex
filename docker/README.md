# docker/

The Docker Compose stack that runs Auspex on one machine: `docker-compose.yml`, the startup one-shots and the monitoring configuration. Commands to bring it up and down are the [stack commands in the root README](../README.md#stack-commands); manual steps are in [SETUP.md](../SETUP.md).

---

## Services

Profile `default` starts with a plain `up`; `app` needs `--profile app`; `restore` runs only under `--profile restore`. Image tags are in [VERSIONS.md](../VERSIONS.md), ports and schedules in `docker-compose.yml` and the DAG files.

| Service | Purpose | Profile |
|---|---|---|
| `kafka` | Message broker (KRaft) | default |
| `kafka-init` | One-shot: creates the topics in `topics.yaml` | default |
| `postgres` | Application database and Airflow metadata database | default |
| `neo4j` | Signal graph | default |
| `minio` | Object store: raw document archive, prices and research panels, strategy runtime state | default |
| `minio-init` | One-shot: creates the stack's buckets | default |
| `price-bootstrap` | One-shot: fills missing price snapshots on `up` | default |
| `price-service` | HTTP API the price refresh and universe build DAGs call | default |
| `backup` | HTTP API the nightly backup DAG calls | default |
| `restore` | Restores one dated backup into empty stores | restore |
| `elasticsearch` | Log storage | default |
| `elasticsearch-setup` | One-shot: applies the log retention policy | default |
| `filebeat` | Ships container logs to Elasticsearch | default |
| `prometheus` | Metrics scraping and storage | default |
| `grafana` | Dashboards and alerting | default |
| `node-exporter`, `cadvisor`, `volume-usage` | Docker VM, per-container and per-volume metrics | default |
| `postgres-monitor-role` | One-shot: the exporter's read-only Postgres role | default |
| `postgres-exporter`, `kafka-exporter`, `elasticsearch-exporter`, `blackbox-exporter`, `statsd-exporter` | Store, broker, health-probe and Airflow metrics | default |
| `airflow-db-role` | One-shot: the Airflow metadata role and its password | default |
| `airflow-state-init` | One-shot: makes the Airflow state volume writable | default |
| `airflow` | DAG scheduler | default |
| `ingestion-scraper` | Scraper HTTP API | app |
| `core-hub` | Signal processor and REST API | app |
| `strategy-runtime` | Runs strategies on corroborations into virtual books | app |
| `dashboard` | Control and research UI | app |

## Where the rules are

- Containers, profiles, ports, one-shots, memory and disk bounds, volumes and what survives a recreate: [docs/operations/topology.md](../docs/operations/topology.md).
- DAGs, schedules, cursors and the Airflow secrets: [docs/operations/orchestration.md](../docs/operations/orchestration.md).
- Logs, metrics, dashboards, alerts and the daily health summary: [docs/operations/observability.md](../docs/operations/observability.md).
- Nightly backup and restore: [docs/operations/backup.md](../docs/operations/backup.md).
- Topics, keys, partitions and dead letters: [docs/system/contracts.md](../docs/system/contracts.md); the values are in `topics.yaml`.
- Variables to fill in `.env`: [SETUP.md](../SETUP.md) step 1. The local model server on the host: [docs/local-model-runbook.md](../docs/local-model-runbook.md).

---

## Procedures

**Fixing one topic's partition count.** `--if-not-exists` leaves an existing topic as it is. To fix one topic's partition count, change only that topic: grow it with `docker exec auspex-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --alter --topic <name> --partitions <n>`, or shrink it by `--delete`-ing that topic and running `up` (kafka-init recreates it; only that topic's messages are lost).

**Changing a password in place** (change it in the store first, then in `.env`):

| Store | How |
|---|---|
| Postgres `POSTGRES_USER` | `docker exec auspex-postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "ALTER ROLE \"$POSTGRES_USER\" PASSWORD '<new>'"` (the container's local socket is trusted), then `.env`, then `up` |
| Postgres `AIRFLOW_DB_PASSWORD`, `POSTGRES_MONITOR_PASSWORD` | Edit `.env` and `up`; a one-shot applies it |
| Neo4j | `docker exec -it auspex-neo4j cypher-shell -u neo4j -d system "ALTER CURRENT USER SET PASSWORD FROM '<old>' TO '<new>'"`, then `.env` and `up` |
| Grafana admin | `docker exec auspex-grafana grafana cli admin reset-admin-password '<new>'`, then `.env` |
| MinIO root | Edit `.env` and `up`; MinIO reads it on every start |

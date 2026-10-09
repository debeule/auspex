# Infrastructure Observability

**Status:** done
**Branch:** `feature/infrastructure-observability`

---

## Context

Decided 2026-10-08: Grafana is the single place for technical health (services up, errors, hardware, disk); the dashboard is for using the application. Today Grafana (`docker/grafana/provisioning/`) has three application dashboards (Pipeline, Operations, Errors) and five alert rules, and Prometheus (`docker/prometheus/prometheus.yml`) scrapes only core-hub and the scraper. The 2026-10-08 audit found:

- No metrics from Kafka, Postgres, Neo4j, MinIO, Elasticsearch, Airflow, price-service or Ollama. A dead datastore shows only as downstream symptoms.
- No host, VM, container or volume metrics. No container has a memory limit; Prometheus has no size cap.
- **No contact point or notification policy**, so alerts change state inside Grafana and reach no one.
- Airflow DAG failures are visible only in the Airflow UI.
- macOS: Docker Desktop runs a Linux VM (8 GB cap). An exporter inside the stack sees the VM and the VM disk that holds the volumes, not the Mac. Ollama runs natively on the Mac and uses most of its RAM.

## What this builds

1. **Exporters in `docker-compose.yml`** (infra profile, ports bound to `127.0.0.1` or not published):
   - `node-exporter`: VM CPU, memory, filesystem of the Docker data disk.
   - `cadvisor`: per-container CPU, memory, restarts.
   - `postgres-exporter`, `kafka-exporter` (broker, topic, consumer-group lag including `*.dlt`), `elasticsearch-exporter`.
   - MinIO's native `/minio/v2/metrics/cluster` scraped directly (`MINIO_PROMETHEUS_AUTH_TYPE=public`, internal network only).
   - `blackbox-exporter` probing every service's health endpoint, Neo4j's HTTP port, and Ollama at `host.docker.internal:11434/api/version`.
   - `statsd-exporter` receiving Airflow's statsd metrics (`AIRFLOW__METRICS__STATSD_ON=true`), mapped to DAG run success/failure and task failure counters per `dag_id`.
2. **Host metrics on the Mac:** Prometheus scrapes a native `node_exporter` at `host.docker.internal:9100` (job `mac-host`). Installing it (`brew install node_exporter`, `brew services start node_exporter`) is one new step in `SETUP.md`; the job is allowed to be down without failing anything else, and its absence raises one info-level alert.
3. **price-service `/metrics`** with `prometheus_client`, matching the scraper's pattern: refresh runs, tickers refreshed, tickers failed, last successful refresh timestamp.
4. **Prometheus:** retention bounded by both `--storage.tsdb.retention.time` and `--storage.tsdb.retention.size` from `.env`.
5. **Grafana:**
   - An "Auspex Infrastructure" dashboard: service up/down grid (blackbox + `up`), Mac and VM CPU/memory/disk, per-container memory and restarts, per-volume and Docker disk use, Postgres connections and database size, Kafka lag per group, Elasticsearch disk, Airflow DAG run outcomes.
   - `alerting/contactpoints.yaml` and `alerting/policies.yaml`. The contact point type and address come from `.env` (`ALERT_CONTACT_TYPE`, plus the type's settings such as `ALERT_EMAIL_ADDRESSES` with SMTP settings, or a webhook URL). Default `email`.
   - New alert rules: any scrape or probe target down for 5 minutes; Docker disk below 15% free; Mac disk below 10% free; VM memory above 90% for 10 minutes; container restarted more than 3 times in an hour; Airflow DAG run failed; price refresh not successful for 2 NYSE sessions; Ollama down while an extraction DAG is running.
6. **Compose memory limits** (`mem_limit`) for every service, sized from `.env` so the totals fit the documented Docker Desktop budget in `docker/README.md`.

## Out of scope

- Application or strategy metrics in the dashboard (other specs).
- Log shipping changes beyond labelling every service for Filebeat (`co.elastic.logs/enabled`).
- Kibana.
- Paging or on-call integrations beyond the one configured contact point.

## Constraints

- Invariant 6: every port, address, credential and threshold from `.env`; `.env.example` documents each new variable.
- VERSIONS.md: every new image pinned to an exact tag, resolved at implementation and written back to VERSIONS.md. No `latest`.
- Exporter credentials (Postgres, Elasticsearch) use read-only roles created by the existing init scripts.
- Neo4j Community has no Prometheus endpoint; a blackbox probe is enough.
- The Mac host job must not make the stack depend on a host install: Prometheus and Grafana start and the infrastructure dashboard renders with the job down.

## Required tests

`services/ingestion-scraper/tests/unit/test_stack_observability_config.py` (parses the compose and provisioning files; no containers):
- `test_every_compose_service_with_a_healthcheck_is_scraped_or_probed`
- `test_every_new_image_is_pinned_to_an_exact_tag`
- `test_every_compose_service_has_a_memory_limit_from_env`
- `test_prometheus_retention_is_bounded_by_time_and_size`
- `test_mac_host_job_targets_host_docker_internal_node_exporter`
- `test_ollama_is_probed_by_blackbox`
- `test_contact_point_and_default_policy_are_provisioned`
- `test_contact_point_settings_come_from_env_placeholders`
- `test_alert_rules_exist_for_target_down_disk_memory_restarts_dag_failure_and_price_refresh`
- `test_infrastructure_dashboard_is_provisioned_with_service_grid_and_disk_panels`
- `test_airflow_statsd_is_enabled_and_mapped_to_dag_outcome_metrics`
- `test_every_service_is_labelled_for_log_shipping`

`services/backtesting/tests/unit/test_price_metrics.py`:
- `test_metrics_endpoint_exposes_refresh_counters_and_last_success_timestamp`
- `test_failed_ticker_increments_failure_counter_without_raising_from_metrics`

`docker/grafana/test_provisioning.sh` (live smoke, extended):
- Infrastructure dashboard found; contact point listed; every Prometheus target in state `up` except `mac-host`, which may be `down`.

## Definition of done

```bash
cd services/ingestion-scraper && uv run pytest tests/unit/test_stack_observability_config.py -q --strict-markers
cd services/backtesting && uv run pytest tests/unit/test_price_metrics.py -q --strict-markers
docker compose --profile app -f docker/docker-compose.yml --env-file .env up -d --wait
sh docker/grafana/test_provisioning.sh
```

Expected: 12 passed, 2 passed, all services healthy, smoke script prints all PASS. (The build added tests beyond these; the files report 20 and 6.)

The last three commands and the alert check run on the stack machine, in step 8 of `specs/first-run-on-stack-machine.md`: install `node_exporter` on the Mac (`SETUP.md` step 2), bring the stack up, run the smoke script, then stop the Postgres container and confirm the target-down alert reaches the configured contact point within 10 minutes. Record the result as a VERIFIED or FLAG entry in `DECISIONS.md`, closing the 2026-10-09 PENDING.

## Built

- Required tests: all 14, plus `test_alert_expressions_reference_only_env_vars_grafana_receives`, `test_exporter_credentials_are_a_monitoring_role_not_the_app_owner`, `test_minio_metrics_are_public_on_the_internal_network_only`, `test_new_exporters_publish_no_host_ports`, two `volume-usage` tests, `tests/unit/test_stack_alert_expressions.py` (every new alert's PromQL run through `promtool test rules`, firing and quiet cases; CI installs promtool) and four more price metrics tests (NYSE session counting, holidays, service start, one registry per app).
- Deviations, each in `DECISIONS.md` 2026-10-09: the monitoring role comes from a one-shot (`postgres-monitor-role`), not `postgres-init/`, so existing volumes get it; volume sizes come from a `du` sidecar (`volume-usage`) through node-exporter's textfile collector; node-exporter reads the VM through PID 1 instead of bind-mounting `/`. Every new value lives only in `.env.example` (compose uses bare `${VAR}`).

## Notes

- Why both a VM and a Mac exporter: on Docker Desktop the VM disk fills independently of the Mac disk, and Ollama's memory never shows inside the VM. Each covers a failure the other cannot see.
- cAdvisor on Docker Desktop reports per-container CPU and memory reliably; some filesystem metrics are missing because of the VM's cgroup layout. Volume sizes come from node-exporter's filesystem metrics on the Docker data disk, not cAdvisor.

# Container limits and log rotation

**Status:** done
**Branch:** `feature/container-limits-and-log-rotation`

---

## Context

The whole stack runs in Docker Desktop on the owner's Mac, in a Linux VM capped at 8 GB, next to a natively running model server. `docker/docker-compose.yml` defines every service. Infrastructure observability gives each container a `mem_limit` from `.env` (`*_MEM_LIMIT`), sized so the long-running ones add up to the VM minus 512 MB, sets `KAFKA_HEAP_OPTS` and `CORE_HUB_JAVA_TOOL_OPTIONS`, and adds Prometheus retention by time and size. Logs: every container writes JSON to stdout; Filebeat (`docker/filebeat/filebeat.yml`) ships them into daily `auspex-logs-*` indices whose ILM policy (`docker/elasticsearch/ilm_policy.json`) deletes them after 180 days. Stack config tests live in `services/ingestion-scraper/tests/unit/test_stack_observability_config.py`.

Found by the soak-test readiness audit (2026-10-09):
1. **Airflow** runs `airflow standalone` (API server, scheduler, DAG processor, triggerer, plus one process per running task under LocalExecutor) in 1,152 MB. Airflow 3's API server starts 4 worker processes by default, so the container is likely at its limit before any task runs.
2. **Neo4j** gets 576 MB and no heap or page-cache setting, so its own heuristics decide both.
3. **The dashboard** container has no `mem_limit`, and the existing limits already fill the budget.
4. **No service sets a log driver or rotation.** Docker Desktop's default `json-file` driver keeps every line forever on the VM disk, and Elasticsearch keeps a second copy for 180 days. Healthcheck and probe requests produce a steady stream of access-log lines.
5. **Prometheus**' size cap (4 GB) can be reached within two weeks with cAdvisor's series, so the start of a multi-week run is dropped.

## What this builds

- Every service in `docker-compose.yml`, one-shots included, uses one shared logging setting: the `json-file` driver with `max-size` 20 MB and `max-file` 3, from an `x-logging` anchor (`json-file`, not `local`: see Notes).
- Log indices are deleted after 30 days, and Filebeat drops access-log lines for the healthcheck and probe paths (`/health`, `/actuator/health`, `/api/v2/monitor/health`, `/-/healthy`, `/api/health`, `/minio/health/live`).
- Airflow starts one API worker and runs at most 4 tasks at once (`AIRFLOW__API__WORKERS=1`, `AIRFLOW__CORE__PARALLELISM=4`). Its limit is raised to 1,536 MB.
- Neo4j's heap and page cache are set explicitly from `.env` (`NEO4J_HEAP_SIZE`, `NEO4J_PAGECACHE_SIZE`), with heap plus page cache at most 75% of its limit.
- The dashboard has `DASHBOARD_MEM_LIMIT`, and the long-running limits are rebalanced so their sum, dashboard included, stays within 7,680 MB (8 GB VM minus 512 MB).
- Prometheus' size retention is 6 GB, so 21 days fit at the audit's growth estimate.
- `docker/README.md` has a disk budget table (per store, expected growth, the setting that bounds it) and a memory budget table that sums to the limit.

## Out of scope

- Measuring real peaks on the Mac. `specs/soak-test-run.md` measures them on day 1 and adjusts `.env`, which needs no code change.
- Fernet key, admin password, Kafka offset retention and cluster ID (owned by the data persistence work).
- Alert rules (`specs/pipeline-alerting-gaps.md`).
- The model server's memory, which is outside Docker.

## Constraints

- Invariant 6: every new value is an `.env` variable, added to `.env.example` in its existing grouping, with no default in compose.
- `docker/CLAUDE.md`: ports stay on `127.0.0.1`; one-shots stay no-ops when their data exists.
- A container at its limit is OOM-killed and restarted; the budget is a ceiling, not a reservation, so the sum test guards the worst case.
- Flyway and Neo4j data are untouched; only settings change, so no volume needs recreating.

## Required tests

Config tests (`services/ingestion-scraper/tests/unit/test_stack_observability_config.py` or a sibling file), parsing `docker/docker-compose.yml`, `.env.example` and the Elastic files:
- `test_every_service_uses_the_shared_rotating_log_driver`
- `test_log_rotation_caps_each_container_at_sixty_megabytes`
- `test_every_service_has_a_memory_limit`
- `test_long_running_memory_limits_fit_the_vm_budget` — the sum over services with a restart policy other than `"no"`, dashboard included, is at most 7,680 MB at `.env.example` values
- `test_neo4j_heap_and_page_cache_fit_within_its_limit`
- `test_airflow_runs_one_api_worker_and_at_most_four_tasks`
- `test_log_indices_are_deleted_after_thirty_days`
- `test_filebeat_drops_healthcheck_access_lines`
- `test_prometheus_keeps_up_to_six_gigabytes`
- `test_every_limit_variable_is_documented_in_env_example`

## Definition of done

```bash
cd services/ingestion-scraper && uv run pytest tests/unit -q --strict-markers && uv run ruff check . && cd ../..
docker compose -f docker/docker-compose.yml --env-file .env.example config --quiet && echo compose-ok
```

Expected: the suite passes with the 10 new tests among them; `compose-ok`; CI green on the PR. On the stack (picked up by `specs/first-run-on-stack-machine.md` step 8): every container shows `json-file` with `max-size` 20m and `max-file` 3 in `docker inspect` and `docker stats` shows no container above 90% of its limit an hour after `up`.

## Notes

- Filebeat's container input reads Docker's `json-file` output; the `local` driver writes a binary format it cannot parse, so `json-file` with rotation is used (`DECISIONS.md`, 2026-10-10).
- Starting values that sum to exactly 7,680 MB from infrastructure observability's set (adjust after the day-1 measurement): Airflow 1,152 → 1,536; dashboard 256 and price-service 1,024 (already set when the dashboard joined the stack; the monthly universe build is price-service's peak, watch it); Neo4j 576 → 512 (256 MB heap, 128 MB page cache); Elasticsearch 896 → 768 (heap stays 512m); Kafka 640 → 576 (heap stays 384m); Prometheus 384 → 320; core-hub 768 → 704. Everything else is unchanged.

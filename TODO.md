# TODO — Spec Index

Each line links to a self-contained spec in `specs/`. Open the spec and read it in full before starting — it has everything needed.

**Session start:** find the first `ready` spec. If none are ready, pick a `draft` spec to scope (see `specs/README.md`).

---

| Spec | Status | Notes |
|---|---|---|
| [Patent connector (EPO OPS)](specs/done/patent-connector.md) | `done` | 10 tests, live DOCDB confirmed |
| [Historical backfill](specs/historical-backfill.md) | `blocked` | Needs budget approval after dry run |
| [Price data ingestion](specs/done/price-ingestion.md) | `done` | 5 tests passed |
| [Point-in-time alignment](specs/done/point-in-time-alignment.md) | `done` | 10 tests passed |
| [Backtesting module](specs/done/backtesting.md) | `done` | 5 tests passed |
| [Performance metrics](specs/done/performance-metrics.md) | `done` | 5 tests passed |
| [Centralised logging](specs/done/centralised-logging.md) | `done` | 11 tests passed (6 Python unit, 4 Java unit, 1 integration) |
| [Metrics](specs/done/metrics.md) | `done` | 7 tests — Prometheus scrape: Java Micrometer + Python prometheus-client |
| [Grafana dashboards](specs/done/grafana-dashboards.md) | `done` | Grafana 13 provisioned: 2 datasources, 3 dashboards, 3 alert rules; 5 smoke tests pass |
| [Scraper HTTP API](specs/done/scraper-api.md) | `done` | 10 tests passed (9 unit, 1 integration) |
| [Containerisation](specs/done/containerisation.md) | `done` | Dockerfiles for scraper + core-hub; Kafka dual-listener; app profile; all services healthy |
| [Re-extraction CLI](specs/done/reextraction-cli.md) | `done` | 13 tests (12 unit, 1 integration) |
| [Kafka partition verification](specs/done/kafka-partition-verification.md) | `done` | 1 integration test; distribution acceptable, no repartitioning needed |
| [Python module layout](specs/done/python-module-layout.md) | `done` | 4 smoke tests; messaging/, connectors/rate_limited_client, RunResult→pipeline |
| [Java package reorganization](specs/java-package-reorganization.md) | `ready` | Structural only — no behavior change |
| [Java service decomposition](specs/java-service-decomposition.md) | `ready` | After Java package reorganization — splits corroboration monolith, renames services, introduces ports |
| [Dashboard](specs/dashboard.md) | `draft` | Needs scoping — after backtesting chain |
| [Watchlist & alerts](specs/watchlist-alerts.md) | `draft` | Needs scoping — transport and storage model |
| [Neo4j indexing at scale](specs/neo4j-indexing.md) | `draft` | Needs backfill data before meaningful |
| [CI/CD pipeline](specs/ci-cd.md) | `draft` | Needs runner decision + broken-PR check |
| [Kafka Streams correlation](specs/kafka-streams-correlation.md) | `draft` | Conditional — only if scheduled query proves inadequate |

---

## Session log
| Date | Spec worked | Left off at | Blocked? |
|---|---|---|---|
| 2026-09-18 | Price data ingestion | Done — 5 tests green | No |
| 2026-09-18 | Point-in-time alignment | Done — 10 tests green | No |
| 2026-09-18 | Backtesting module | Done — 5 tests green | No |
| 2026-09-18 | Performance metrics | Done — 5 tests green | No |
| 2026-09-18 | Centralised logging | Done — 11 tests green (6 Python unit, 4 Java unit, 1 integration) | No |
| 2026-09-18 | Scraper HTTP API | Done — 10 tests green (9 unit, 1 integration) | No |
| 2026-09-18 | Metrics | Done — 7 tests green (5 Python unit, 2 Java unit); Prometheus service added | No |
| 2026-09-18 | Grafana dashboards | Done — 5 smoke tests pass; Grafana 13 + provisioning, elasticsearch-setup init container | No |
| 2026-09-18 | Containerisation | Done — ingestion-scraper + core-hub containerised; all services healthy; Kafka dual-listener | No |
| 2026-09-18 | Re-extraction CLI | Done — 13 tests green (12 unit, 1 integration); scripts/reextract.py; MinioArchive.list_raw_keys/get_raw | No |
| 2026-09-19 | Kafka partition verification | Done — 1 integration test; UUID key distribution uniform across 6 partitions | No |
| 2026-09-19 | Python module layout | Done — 4 smoke tests; messaging/ sub-package, rate_limited_client into connectors/, RunResult into pipeline | No |

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
| [Backtesting module](specs/backtesting.md) | `ready` | After point-in-time alignment |
| [Performance metrics](specs/performance-metrics.md) | `ready` | After backtesting |
| [Centralised logging](specs/centralised-logging.md) | `ready` | After performance metrics — Elasticsearch + Filebeat, prerequisite for metrics, Grafana, and containerisation |
| [Metrics](specs/metrics.md) | `ready` | After logging — Kafka lag, JVM heap, LLM throughput via Prometheus |
| [Grafana dashboards](specs/grafana-dashboards.md) | `ready` | After logging + metrics — unified UI for logs and metrics |
| [Scraper HTTP API](specs/scraper-api.md) | `ready` | After logging — prerequisite for containerisation |
| [Containerisation](specs/containerisation.md) | `ready` | After scraper API + logging — enables prod-sim local run |
| [Re-extraction CLI](specs/reextraction-cli.md) | `ready` | After containerisation — run before any prompt or model version bump |
| [Kafka partition verification](specs/kafka-partition-verification.md) | `ready` | After containerisation — measurement only, no code unless skewed |
| [Python module layout](specs/python-module-layout.md) | `ready` | Structural only — no behavior change |
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

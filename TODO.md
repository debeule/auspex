# TODO — Spec Index

Each line links to a self-contained spec in `specs/`. Open the spec and read it in full before starting — it has everything needed.

**Session start:** find the first `ready` spec. If none are ready, pick a `draft` spec to scope (see `specs/README.md`).

---

| Spec | Status | Notes |
|---|---|---|
| [Patent connector (EPO OPS)](specs/patent-connector.md) | `done` | 10 tests, live DOCDB confirmed |
| [Historical backfill](specs/historical-backfill.md) | `blocked` | Needs budget approval after dry run |
| [Price data ingestion](specs/price-ingestion.md) | `ready` | Execute first — prerequisite for the three below |
| [Point-in-time alignment](specs/point-in-time-alignment.md) | `ready` | After price ingestion |
| [Backtesting module](specs/backtesting.md) | `ready` | After alignment |
| [Performance metrics](specs/performance-metrics.md) | `ready` | After backtesting |
| [Dashboard](specs/dashboard.md) | `draft` | Needs scoping — see spec notes |
| [Watchlist & alerts](specs/watchlist-alerts.md) | `draft` | Needs scoping — transport and storage model |
| [Re-extraction CLI](specs/reextraction-cli.md) | `ready` | Run before any prompt or model version bump |
| [Centralised logging](specs/centralised-logging.md) | `ready` | Elastic Stack — prerequisite for scraper API, dashboards, and containerisation |
| [Kibana dashboards](specs/kibana-dashboards.md) | `ready` | After logging — operational dashboards, saved searches, alert rules |
| [Scraper HTTP API](specs/scraper-api.md) | `ready` | After logging — prerequisite for containerisation |
| [Containerisation](specs/containerisation.md) | `ready` | After scraper API + logging — enables prod-sim local run |
| [Kafka partition verification](specs/kafka-partition-verification.md) | `ready` | Measurement only — no code unless skewed |
| [Neo4j indexing at scale](specs/neo4j-indexing.md) | `draft` | Needs backfill data before meaningful |
| [CI/CD pipeline](specs/ci-cd.md) | `draft` | Needs runner decision + broken-PR check |
| [Kafka Streams correlation](specs/kafka-streams-correlation.md) | `draft` | Conditional — only if scheduled query proves inadequate |

---

## Session log
| Date | Spec worked | Left off at | Blocked? |
|---|---|---|---|
| | | | |

# TODO — Spec Index

Each line links to a self-contained spec in `specs/`. Open the spec and read it in full before starting — it has everything needed.

**Session start:** find the first `ready` spec. If none are ready, pick a `draft` spec to scope (see `specs/README.md`).

---

| Spec | Status | Notes |
|---|---|---|
| [CI/CD pipeline](specs/ci-cd.md) | `ready` | Brought off hold — protects the long-running backfill against regressions |
| [Extraction backend](specs/extraction-backend.md) | `ready` | Model registry; digest pinning; gate records; abstract contract test; deprecation warning |
| [EDGAR content fix](specs/edgar-content-fix.md) | `ready` | Extend SecEdgarConnector to fetch 8-K filing text; 8/13 Phase 2 FNs were metadata-only |
| [Model evaluation](specs/model-evaluation.md) | `ready` | 3 manual scripts: candidate comparison (latency record), leakage canary, cross-model agreement |
| [Backtesting module](specs/backtesting.md) | `ready` | Reopened: entity-only variant (no directionality/confidence) required by Phase 4 FLAG v2 |
| [Performance metrics](specs/performance-metrics.md) | `ready` | Reopened: per-variant metrics output required by Phase 4 FLAG v2 |
| [Watchlist backend](specs/watchlist-backend.md) | `ready` | Postgres schema; CRUD endpoints; preview (SEC + graph + ClinicalTrials auto-detect); company summary |
| [Watchlist UI](specs/watchlist-ui.md) | `ready` | /watchlist management page; /watchlist/[ticker] detail page; gene target chips; do after watchlist-backend |
| [Golden set expansion](specs/golden-set-expansion.md) | `blocked` | Blocked by model-evaluation — local model must be chosen before gate records can be written |
| [Historical backfill](specs/historical-backfill.md) | `blocked` | Budget approval + extraction-backend + model-evaluation + golden-set-expansion first |
| [Patent connector (EPO OPS)](specs/done/patent-connector.md) | `done` | 10 tests, live DOCDB confirmed |
| [Price data ingestion](specs/done/price-ingestion.md) | `done` | 5 tests passed |
| [Point-in-time alignment](specs/done/point-in-time-alignment.md) | `done` | 10 tests passed |
| [Centralised logging](specs/done/centralised-logging.md) | `done` | 11 tests passed (6 Python unit, 4 Java unit, 1 integration) |
| [Metrics](specs/done/metrics.md) | `done` | 7 tests — Prometheus scrape: Java Micrometer + Python prometheus-client |
| [Grafana dashboards](specs/done/grafana-dashboards.md) | `done` | Grafana 13 provisioned: 2 datasources, 3 dashboards, 3 alert rules; 5 smoke tests pass |
| [Scraper HTTP API](specs/done/scraper-api.md) | `done` | 10 tests passed (9 unit, 1 integration) |
| [Containerisation](specs/done/containerisation.md) | `done` | Dockerfiles for scraper + core-hub; Kafka dual-listener; app profile; all services healthy |
| [Re-extraction CLI](specs/done/reextraction-cli.md) | `done` | 13 tests (12 unit, 1 integration) |
| [Kafka partition verification](specs/done/kafka-partition-verification.md) | `done` | 1 integration test; distribution acceptable, no repartitioning needed |
| [Python module layout](specs/done/python-module-layout.md) | `done` | 4 smoke tests; messaging/, connectors/rate_limited_client, RunResult→pipeline |
| [Java package reorganization](specs/done/java-package-reorganization.md) | `done` | 22 unit + 55 integration tests; signal, persistence, corroboration, audit, query packages |
| [Java service decomposition](specs/done/java-service-decomposition.md) | `done` | 8 unit tests; CorroborationScanner extracted, SignalIngestionService + ports, 85 total tests green |
| [Dashboard](specs/done/dashboard.md) | `done` | 5 component tests; Next.js 15 App Router, Vitest + RTL, NEXT_PUBLIC_API_URL |
| [Watchlist & alerts](specs/hold/watchlist-alerts.md) | `hold` | Come off hold when Phase 4 shows a real repeatable signal worth acting on |
| [Neo4j indexing at scale](specs/neo4j-indexing.md) | `blocked` | Blocked by historical backfill; thresholds are placeholders — treat as blocked-and-draft until after backfill |
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
| 2026-09-19 | Java package reorganization | Done — 22 unit + 55 integration tests; signal, persistence, corroboration, audit, query packages; MetricsIT compilation fixed | No |
| 2026-09-19 | Java service decomposition | Done — 8 new unit tests; 30 unit + 55 integration = 85 total green | No |
| 2026-09-19 | Dashboard | Done — 5 component tests green; Next.js 15 App Router, Vitest + RTL | No |
| 2026-09-19 | Extraction backend, historical backfill | Scoping session — 2 specs written; lineage decision required before backfill can start | Yes (lineage) |
| 2026-09-19 | Extraction backend, model evaluation, historical backfill | Rescoped — 3 specs; digest pinning, gate records, 3 evaluation scripts, latency-based dry run; lineage decision required | Yes (lineage) |
| 2026-09-19 | Full spec audit + refactor | ci-cd off hold; EDGAR content fix spec; golden set expansion spec; backtesting + performance-metrics reopened for entity-only variant | No |
| 2026-09-20 | Watchlist scoping | watchlist-backend + watchlist-ui specs written; watchlist-alerts hold spec updated (schema superseded) | No |

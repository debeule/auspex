# TODO — Spec Index

Each line links to a self-contained spec in `specs/`. Open the spec and read it in full before starting — it has everything needed.

**Session start:** find the first `ready` spec. If none are ready, pick a `draft` spec to scope (see `specs/README.md`).

---

| Spec | Status | Notes |
|---|---|---|
| [CI/CD pipeline](specs/done/ci-cd.md) | `done` | java + python workflows; 4 checks green on PR #1; session provided broken-PR evidence |
| [Extraction backend](specs/done/extraction-backend.md) | `done` | 23 tests (15 unit + 8 contract); registry.yaml; gate record; LLMExtractorFactory; deprecation warning |
| [EDGAR content fix](specs/done/edgar-content-fix.md) | `done` | 18 tests; full 8-K text via data.sec.gov/submissions; live fetch verified (4,282 chars) |
| [EDGAR EFTS fixture alignment](specs/done/edgar-efts-fixture-alignment.md) | `done` | Fixtures + _map aligned to real EFTS schema (adsh, ciks, display_names, form, period_ending) |
| [Model evaluation](specs/done/model-evaluation.md) | `done` | 6 tests; evaluate_model.py, check_leakage.py, compare_models.py; auspex_ingest.model_evaluation |
| [Backtesting module](specs/done/backtesting.md) | `done` | 8 tests; entity-only and full corroboration variants; CorroborationGroup, VariantReport |
| [Performance metrics](specs/done/performance-metrics.md) | `done` | 8 tests; variant field on MetricsReport; compute_both_variants; entity-only vs full filtering |
| [Watchlist backend](specs/done/watchlist-backend.md) | `done` | 11 tests (8 unit + 3 integration); Flyway V3; CRUD + preview + summary; SecTickerCache; WireMock CT stub |
| [Watchlist UI](specs/done/watchlist-ui.md) | `done` | 8 tests; WatchlistPage, CompanyDetail; NavBar; /watchlist + /watchlist/[ticker] routes |
| [Hypothesis registry](specs/done/hypothesis-registry.md) | `done` | 6 tests; hypothesis.py; register_hypothesis.py; config/hypotheses/h1–h8.yaml; registry.jsonl |
| [Market simulation](specs/market-simulation.md) | `blocked` | Blocked by backtesting entity-only variant; MarketCalendar (NYSE), FillModel, CostModel (TOB), CurrencyConverter, PositionSizer |
| [Evaluation protocol](specs/evaluation-protocol.md) | `blocked` | Blocked by market-simulation + performance-metrics entity-only; abnormal returns vs XBI, walk-forward, deflated Sharpe, holdout |
| [Strategy framework](specs/done/strategy-framework.md) | `done` | 9 tests; Strategy ABC, AsOfContext, TradeIntent, StrategyRegistry, versioning; 6 seed stubs (H1, H4–H8) |
| [Strategy runtime](specs/strategy-runtime.md) | `blocked` | Blocked by strategy-framework + market-simulation; BacktestReplayRunner, StreamingRuntime, VirtualBook, InputHealthMonitor |
| [Portfolio and risk](specs/portfolio-and-risk.md) | `blocked` | Blocked by strategy-runtime + market-simulation; KellySizer, exposure limits, binary-event guard, short guards, kill switches |
| [Strategy metrics](specs/strategy-metrics.md) | `blocked` | Blocked by strategy-framework + hypothesis-registry + evaluation-protocol; activity funnel, deflated Sharpe, correlation matrix, API |
| [Decision trace](specs/decision-trace.md) | `blocked` | Blocked by strategy-framework + strategy-runtime; immutable TraceRecord from raw doc to P&L, TraceStore, TraceValidator |
| [Golden set expansion](specs/golden-set-expansion.md) | `blocked` | Blocked by model-evaluation — local model must be chosen before gate records can be written |
| [Historical backfill](specs/historical-backfill.md) | `blocked` | Runner + dry run built (19 unit tests + 1 IT); live run blocked on local model choice, golden set, human sign-off |
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
| 2026-09-20 | Strategy layer session 1 | docs/strategy-research.md (H1–H8); hypothesis-registry (ready), market-simulation (blocked), evaluation-protocol (blocked) specs written; DECISIONS.md + PREREQUISITES.md updated | No |
| 2026-09-20 | Strategy layer session 2 | strategy-framework (ready), strategy-runtime, portfolio-and-risk, strategy-metrics, decision-trace (all blocked) specs written; 8 DECISIONS.md entries; TODO.md updated | No |
| 2026-09-20 | CI/CD pipeline | Done — java + python workflows green on PR #1; 4 CI fixes (gradle jar, quay.io minio, tuple unpack, git diff path) | No |
| 2026-09-20 | Extraction backend | Done — 23 tests green (15 unit + 8 contract); LLMExtractorFactory, ConfigurationError, GateNotPassedError, ContextLengthError; registry.yaml; gate record | No |
| 2026-09-25 | EDGAR content fix | Done — 18 tests green; document text via data.sec.gov/submissions; live fetch verified; EFTS fixture mismatch patched; edgar-efts-fixture-alignment spec added | No |
| 2026-09-25 | EDGAR EFTS fixture alignment | Done — 18 tests green; fixtures + _map use real field names; dual-format fallbacks removed | No |
| 2026-09-25 | Model evaluation | Done — 6 tests green; evaluate_model.py, check_leakage.py, compare_models.py; auspex_ingest.model_evaluation | No |
| 2026-09-25 | Backtesting module | Done — 8 tests green; entity-only and full corroboration variants; CorroborationGroup, VariantReport | No |
| 2026-09-25 | Performance metrics | Done — 8 tests green; variant field on MetricsReport; compute_both_variants; entity-only vs full filtering | No |
| 2026-09-25 | Watchlist backend | Done — 11 tests green (8 unit + 3 integration); Flyway V3; CRUD + preview + summary; GlobalExceptionHandler ResponseStatusException fix | No |
| 2026-09-26 | Watchlist UI | Done — 8 tests green (13 total); WatchlistPage, CompanyDetail, NavBar; /watchlist + /watchlist/[ticker] routes | No |
| 2026-09-26 | Hypothesis registry | Done — 6 tests green; hypothesis.py; register_hypothesis.py; h1–h8.yaml; registry.jsonl | No |
| 2026-09-26 | Strategy framework | Done — 9 tests green; services/strategy/; Strategy ABC, AsOfContext, StrategyRegistry, VersionConflictError; 6 seed stubs | No |
| 2026-10-07 | Historical backfill | run_backfill.py, dry run, ceilings, checkpoints, core-hub lineage endpoint; 19 unit tests green; live run not started | Yes (model choice, sign-off) |

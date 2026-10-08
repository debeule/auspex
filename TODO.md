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
| [EDGAR press-release content](specs/done/edgar-press-release-content.md) | `done` | 60 tests; items 2.02/7.01/8.01 only; Exhibit 99.1 leads raw_content; published_date = acceptance time (UTC); company CIK from ciks[0] |
| [Model evaluation](specs/done/model-evaluation.md) | `done` | 6 tests; evaluate_model.py, check_leakage.py, compare_models.py; auspex_ingest.model_evaluation |
| [Backtesting module](specs/done/backtesting.md) | `done` | 8 tests; entity-only and full corroboration variants; CorroborationGroup, VariantReport |
| [Performance metrics](specs/done/performance-metrics.md) | `done` | 8 tests; variant field on MetricsReport; compute_both_variants; entity-only vs full filtering |
| [Watchlist backend](specs/done/watchlist-backend.md) | `done` | 11 tests (8 unit + 3 integration); Flyway V3; CRUD + preview + summary; SecTickerCache; WireMock CT stub |
| [Watchlist UI](specs/done/watchlist-ui.md) | `done` | 8 tests; WatchlistPage, CompanyDetail; NavBar; /watchlist + /watchlist/[ticker] routes |
| [Hypothesis registry](specs/done/hypothesis-registry.md) | `done` | 6 tests; hypothesis.py; register_hypothesis.py; config/hypotheses/h1–h8.yaml; registry.jsonl |
| [Local model integration](specs/done/local-model-integration.md) | `done` | 10 tests; registry-driven extractor in api/scripts; Ollama digest lookup; register_local_model.py; runbook |
| [Realistic cost model](specs/done/realistic-cost-model.md) | `done` | 27 tests; per-ticker spread (Abdi-Ranaldo), FX fee, ADV volume cap, gap-through-stop fills |
| [Market simulation](specs/done/market-simulation.md) | `done` | 11 tests; market_sim: MarketCalendar (NYSE), FillModel, CostModel (TOB), CurrencyConverter, PositionSizer, TradableUniverse; EURUSD=X + XBI fetch pending on stack machine |
| [Evaluation protocol](specs/evaluation-protocol.md) | `blocked` | Spec blockers (market-simulation, performance-metrics) are done; end-to-end run waits on backfill; protocol pre-registered 2026-10-07 (config/hypotheses/protocol.yaml); market-model abnormal returns vs XBI, clustered t, family trial ledger, kill criteria, walk-forward, deflated Sharpe, holdout; 22 tests |
| [Strategy framework](specs/done/strategy-framework.md) | `done` | 9 tests; Strategy ABC, AsOfContext, TradeIntent, StrategyRegistry, versioning; 6 seed stubs (H1, H4–H8) |
| [Backtest look-ahead fix](specs/done/backtest-look-ahead-fix.md) | `done` | 26 new tests (89 backtesting unit); events enter after corroborated_at; NYSE calendar; date-only = after close; calendar-day windows |
| [Strategy runtime](specs/strategy-runtime.md) | `blocked` | Blocked by strategy-framework + market-simulation; BacktestReplayRunner, StreamingRuntime, VirtualBook, InputHealthMonitor |
| [Portfolio and risk](specs/portfolio-and-risk.md) | `blocked` | Blocked by strategy-runtime; quarter-Kelly sizer, 5% per-name and one-per-theme ceilings, exposure limits, exit before binary events, short guards, kill switches; 18 tests |
| [Strategy metrics](specs/strategy-metrics.md) | `blocked` | Blocked by strategy-framework + hypothesis-registry + evaluation-protocol; activity funnel, deflated Sharpe, correlation matrix, API |
| [Decision trace](specs/decision-trace.md) | `blocked` | Blocked by strategy-framework + strategy-runtime; immutable TraceRecord from raw doc to P&L, TraceStore, TraceValidator |
| [Golden set expansion](specs/golden-set-expansion.md) | `blocked` | Blocked by model-evaluation — local model must be chosen before gate records can be written |
| [Historical backfill](specs/historical-backfill.md) | `blocked` | Budget approval + extraction-backend + model-evaluation + golden-set-expansion first |
| [Company-level extraction](specs/done/company-level-extraction.md) | `done` | Schema 1.1: event_type, primary_company, program_identifiers, trial_ids; prompt v1.1; Flyway V4; gate needs a v1.1 run |
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
| [Company-program corroboration](specs/company-program-corroboration.md) | `blocked` | Blocked by company-level event extraction + requirements §4/§9 amendment approval; Program nodes, COMPANY_PROGRAM kind, configurable window, point-in-time score |
| [Point-in-time universe](specs/point-in-time-universe.md) | `blocked` | Code done: monthly list built by the `auspex_universe_build` DAG, backtests trade only members, unpriced windows excluded and counted, delisting bound, survivorship flag; all 23 required tests. Blocked only by the first build on the stack: record coverage in DECISIONS.md, commit backfill_scope.yaml |
| [Forward paper trading](specs/forward-paper-trading.md) | `blocked` | Blocked by strategy-runtime + look-ahead fix; daily paper ledger at €10k/€50k/€250k, heartbeats, gap detection, forward-check report per tier. **Gates live trading:** no real capital until its forward check passes, and its per-tier results set how much |
| [Structured source extraction](specs/structured-source-extraction.md) | `blocked` | Blocked by company-level event extraction; deterministic mapper path + issuer-scope pre-filter for structured filings |
| [Insider buying connector](specs/insider-buying-connector.md) | `blocked` | Blocked by company-level event extraction + structured source extraction; SEC Form 4 open-market purchases |
| [Equity offering connector](specs/equity-offering-connector.md) | `blocked` | Blocked by company-level event extraction + structured source extraction; S-3, 424B5, 424B4 |
| [Short interest snapshots](specs/short-interest-snapshots.md) | `blocked` | Blocked by company-level event extraction; FINRA short interest as MinIO Parquet, known at publication date |
| [Catalyst calendar](specs/catalyst-calendar.md) | `blocked` | Blocked by company-level event extraction; PDUFA dates from filings, as-of calendar endpoint |
| [FDA advisory committee connector](specs/fda-advisory-committee-connector.md) | `blocked` | Blocked by company-level event extraction + catalyst calendar; Federal Register meeting notices |
| [Graph and connector wiring fixes](specs/graph-and-connector-wiring-fixes.md) | `ready` | Mechanism links written as VIA (never corroborate); Company.ticker never set; scraper API builds only 2 of 6 connectors (Invariant 4); 16 tests |
| [Infrastructure observability](specs/infrastructure-observability.md) | `ready` | Exporters for every service, Mac host + Docker VM metrics, Airflow statsd, Infrastructure dashboard, alert contact point, memory limits; 14 tests + live smoke |
| [Dashboard foundation](specs/dashboard-foundation.md) | `ready` | Dashboard in the stack: BFF route handlers, single-user login, core-hub write token, container, CI, lint, `next` upgrade, error states; 27 tests |
| [Managed ingestion config](specs/managed-ingestion-config.md) | `blocked` | Blocked by graph-and-connector wiring fixes + dashboard foundation; watchlist as single source for tickers and terms, append-only versions, vocabulary hash in prefilter_version, golden-set check; 25 tests |
| [Ingestion config UI](specs/ingestion-config-ui.md) | `blocked` | Blocked by managed ingestion config + dashboard foundation; companies, sources, history pages; research config read-only; 15 tests |
| [Signal browse views](specs/signal-browse-views.md) | `blocked` | Blocked by wiring fixes + dashboard foundation; paged signal, corroboration, company and entity APIs and views; 21 tests |
| [Pipeline control view](specs/pipeline-control-view.md) | `blocked` | Blocked by dashboard foundation + wiring fixes; Airflow runs, trigger, pause, cursors, run counts, re-extract DAG, dead letters; 20 tests |
| [Lineage trace view](specs/lineage-trace-view.md) | `blocked` | Blocked by signal browse views + wiring fixes; corroboration evidence, reproducible score, lineage endpoints, /trace; 20 tests |
| [Research results view](specs/research-results-view.md) | `draft` | Blocked by the strategy direction decision (PR #19) and the result-producing specs; strategy-agnostic read API, decision references, results views |

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
| 2026-10-07 | Market simulation | Done — 11 tests green (49 backtesting unit total); pandas-market-calendars 5.4.0; fetch_prices.py; EURUSD=X/XBI fetch pending | No |
| 2026-10-07 | Local model integration | Done — 10 tests green (235 unit); production now reaches Ollama; awaiting gate runs on the backfill machine | No |
| 2026-10-07 | Realistic cost model | Done — 27 tests green; market-simulation tests unchanged | No |
| 2026-10-07 | Pre-registration and kill criteria | Done — 13 tests green (test_preregistered_protocol.py; 76 backtesting unit); protocol.yaml + hypothesis v2 registered before backfill; evaluation-protocol, portfolio-and-risk, strategy-metrics specs updated; 5 DECISIONS entries | No |
| 2026-10-07 | EDGAR press-release content | Done — 60 tests green, mutation-checked; filing index replaces submissions lookup | No |
| 2026-10-07 | Second-wave specs from the edge feasibility audit | Scoping session — 9 specs written (all blocked); historical-backfill, strategy-runtime, portfolio-and-risk reconciled; universe scope decided by the user (defaults, free delisted prices) | No |
| 2026-10-07 | Backtest look-ahead fix | Done — 26 new tests, mutation-checked; member signals no longer counted; NYSE calendar; calendar-day windows | No |
| 2026-10-07 | Company-level extraction | Done — 30 new Python tests, 1 new Java unit, 2 new IT; 282 Python unit + 42 Java unit green; gate re-run at v1.1 pending | No |
| 2026-10-08 | Point-in-time universe, part 1 | Monthly list done — 15 of 23 required tests plus 34 edge-case tests, mutation-checked; 178 backtesting unit green; part 2 (backtest integration) next | No |
| 2026-10-08 | Point-in-time universe, part 2 | Backtest integration done — 23 of 23 required tests, 200 backtesting unit green, mutation-checked; spec waits on the first stack build | Yes (stack run) |
| 2026-10-08 | Control-surface scoping | Scoping session: 9 specs from the frontend audit (3 ready, 5 blocked, 1 draft); decisions approved by the user | No |

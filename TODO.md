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
| [Strategy runtime](specs/strategy-runtime.md) | `ready` | Prerequisites done (strategy-framework, market-simulation); BacktestReplayRunner, StreamingRuntime, VirtualBook, InputHealthMonitor, runtime container + CI for services/strategy; 9 tests. Forward paper trading runs inside it |
| [Portfolio and risk](specs/portfolio-and-risk.md) | `blocked` | Blocked by strategy-runtime; event strategies (the H9 basket is sized and guarded in the portfolio backtest; kill switches apply to all); quarter-Kelly sizer, 5% per-name and one-per-theme ceilings, exposure limits, exit before binary events, short guards, kill switches; 18 tests |
| [Strategy metrics](specs/strategy-metrics.md) | `blocked` | Blocked by evaluation-protocol (strategy-framework and hypothesis-registry done); activity funnel, deflated Sharpe, correlation matrix, API |
| [Decision trace](specs/decision-trace.md) | `blocked` | Blocked by strategy-runtime (strategy-framework done); immutable TraceRecord from raw doc to P&L, TraceStore, TraceValidator |
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
| [Ingestion run reliability](specs/ingestion-run-reliability.md) | `blocked` | Blocked by graph-and-connector-wiring-fixes merge; safe cursor on failed documents, staggered schedules + single-slot pool, extraction cap, per-source lock, retries, §6.5 rate limits, SEC pacing under 10 req/s; 20 tests |
| [Dead-letter recovery](specs/dead-letter-recovery.md) | `blocked` | Blocked by dashboard-foundation merge (write token); listeners pause while a store is down, longer transient back-off, DLT replay endpoint, corroboration watermark after acknowledged sends; 12 tests |
| [Container limits and log rotation](specs/container-limits-and-log-rotation.md) | `blocked` | Blocked by infrastructure-observability + dashboard-foundation merges; rotating log driver on every service, 30-day log indices, Airflow 1 API worker, Neo4j heap/page cache, memory budget incl. dashboard; 10 tests |
| [Pipeline alerting gaps](specs/pipeline-alerting-gaps.md) | `blocked` | Blocked by infrastructure-observability merge; Source Silence at 30 h, §12 core-hub health reporter, 8 new rules, daily health summary DAG; 19 tests |
| [Soak test run](specs/soak-test-run.md) | `blocked` | Mac only; blocked by first-run model gate + the four specs above; 21 days, Mac prep, day-1 measurement, daily checks, induced faults, 13 pass criteria |
| [Watchlist & alerts](specs/hold/watchlist-alerts.md) | `hold` | Come off hold when the backtest shows a real repeatable signal worth acting on |
| [Neo4j indexing at scale](specs/neo4j-indexing.md) | `blocked` | Blocked by historical backfill; thresholds are placeholders — treat as blocked-and-draft until after backfill |
| [Kafka Streams correlation](specs/kafka-streams-correlation.md) | `draft` | Conditional — only if scheduled query proves inadequate |
| [Company-program corroboration](specs/company-program-corroboration.md) | `blocked` | Off the alpha path since 2026-10-07 (research tool, veto mapping). Blocked by requirements §4/§9 amendment approval (company-level extraction done); Program nodes, COMPANY_PROGRAM kind, configurable window, point-in-time score |
| [Point-in-time universe](specs/point-in-time-universe.md) | `blocked` | Code done: one universe from 2014-01 (backfill scope from 2024-01), monthly list built by the `auspex_universe_build` DAG, backtests trade only members, unpriced windows excluded and counted, delisting bound, survivorship flag; all 23 required tests. Blocked only by the first build on the stack: record coverage in DECISIONS.md, commit backfill_scope.yaml |
| [Forward paper trading](specs/forward-paper-trading.md) | `blocked` | Blocked by strategy-runtime + look-ahead fix; daily paper ledger at €10k/€50k/€250k, heartbeats, gap detection, forward-check report per tier. **Gates live trading:** no real capital until its forward check passes, and its per-tier results set how much |
| [Structured source extraction](specs/hold/structured-source-extraction.md) | `hold` | On hold 2026-10-07: only consumers (Form 4, offering connectors) are on hold |
| [Insider buying connector](specs/hold/insider-buying-connector.md) | `hold` | On hold 2026-10-07: insider data enters as a panel (sec-ownership-datasets); T+1 insider copying dropped by the research |
| [Equity offering connector](specs/hold/equity-offering-connector.md) | `hold` | On hold 2026-10-07: no biotech offering evidence; trading it needs shorts |
| [Slow-signal data refresh](specs/slow-signal-data-refresh.md) | `blocked` | Blocked by sec-ownership-datasets, catalyst-date-panel, short-interest-snapshots, filing-text-change-score, holdings-composite-score, infrastructure-observability; price-service endpoints + DAGs keeping ownership, short interest, filings, catalysts and monthly score snapshots current; universe members in the daily price refresh; staleness gauges and alert; 14 tests. **Needed before the paper ledger starts** (a missing snapshot is a data gap) |
| [Live trading](specs/live-trading.md) | `draft` | Scoped only after a forward check passes; gathers §0.1 amendment, IBKR order tickets (live-confirm first), reconciliation, live kill switches, tax record; user actions in docs/PREREQUISITES.md |
| [Short interest snapshots](specs/short-interest-snapshots.md) | `ready` | Prerequisites done (company-level extraction; universe in code); FINRA short interest as MinIO Parquet, known at publication date; H9 component; 9 tests |
| [Catalyst calendar](specs/catalyst-calendar.md) | `blocked` | Blocked by the backfill timing decision (company-level extraction and press-release content done); PDUFA dates from filings, as-of calendar endpoint |
| [FDA advisory committee connector](specs/fda-advisory-committee-connector.md) | `blocked` | Blocked by catalyst calendar (company-level extraction done); Federal Register meeting notices |
| [Slow-signal pre-registration](specs/done/slow-signal-preregistration.md) | `done` | 37 tests (13 existing + 4 hash checks for h9–h12 + 20 new); one protocol version (families, portfolio inference and kill criteria, forward-check branches, equal-risk, instrument ceilings); H8 veto, H9, H10 (two uses), H11/H12 diagnostics; `EvaluationProtocol.admit()`; volatility correction |
| [Cross-sectional portfolio backtest](specs/cross-sectional-portfolio-backtest.md) | `ready` | Code unblocked; H9/H10 runs need the first universe build on the stack (window from 2014 is in rules.yaml); quarterly banded rotation (15/30), cadence and catalyst-guard variants, equal-risk basket, tiered commissions, planted-edge test |
| [SEC ownership datasets](specs/sec-ownership-datasets.md) | `ready` | After pre-registration (build order 2026-10-08); 13F holdings and insider transactions as point-in-time panels, rule-based specialist funds |
| [Holdings composite score](specs/holdings-composite-score.md) | `blocked` | Blocked by sec-ownership-datasets + short-interest snapshots + pre-registration; H9 score: specialist 13F, insider P buys, days to cover; $500M/$2M tradable floor |
| [Filing text change score](specs/filing-text-change-score.md) | `blocked` | Blocked by pre-registration; adds the `us_small_mid` universe file; H10 Item 1A year-on-year change ("lazy prices"), no LLM |
| [Catalyst date panel](specs/catalyst-date-panel.md) | `blocked` | Code done: point-in-time PDUFA dates from 8-K exhibits (phrase rules, precision kept) and AdCom meetings from Federal Register notices, append-only panel with `as_of` and `binaries_between`, every document fetched once; all 10 required tests. Blocked only by the first build on the stack: coverage and a 30-hit hand check in DECISIONS.md (first-run step 3a) |
| [ClinicalTrials.gov version diffs](specs/clinicaltrials-version-diffs.md) | `blocked` | Pre-registration met (H11 registered); after the SEC base in build order; registry edit history (record history or AACT), quiet flag, H11 diagnostic |
| [Graph and connector wiring fixes](specs/graph-and-connector-wiring-fixes.md) | `ready` | Mechanism links written as VIA (never corroborate); Company.ticker never set; scraper API builds only 2 of 6 connectors (Invariant 4); 16 tests |
| [Graph and connector wiring fixes](specs/done/graph-and-connector-wiring-fixes.md) | `done` | 16 tests (11 Java, 5 Python); USES_MECHANISM + VIA rewrite on startup; Company.ticker from unique SEC match + watchlist back-fill; connector registry builds all 6 sources; publish threshold per entry, default 0.0 |
| [ClinicalTrials.gov version diffs](specs/clinicaltrials-version-diffs.md) | `blocked` | Blocked by slow-signal pre-registration; registry edit history (record history or AACT), quiet flag, H11 diagnostic |
| [Graph and connector wiring fixes](specs/done/graph-and-connector-wiring-fixes.md) | `done` | 14 tests (9 Java, 5 Python); mechanism links as USES_MECHANISM; Company.ticker from unique SEC match + watchlist back-fill; connector registry builds all 6 sources; publish threshold per entry, default 0.0 |
| [Dashboard foundation](specs/done/dashboard-foundation.md) | `done` | Next 16 BFF + single-user login, core-hub write token, no CORS, container + CI; 50 dashboard, 2 stack-config, 6 core-hub IT + 4 unit tests; live stack check pending on the stack machine |
| [Infrastructure observability](specs/done/infrastructure-observability.md) | `done` | 26 tests (20 stack config incl. promtool alert cases, 6 price metrics); 7 exporters + volume-usage, Mac/VM metrics, Airflow statsd, Infrastructure dashboard, contact point + policy, 9 new alerts, memory limits; live smoke and alert delivery run in first-run step 8 |
| [Dashboard foundation](specs/dashboard-foundation.md) | `ready` | Dashboard in the stack: BFF route handlers, single-user login, core-hub write token, container, CI, lint, `next` upgrade, error states; 27 tests |
| [Single-source cleanup](specs/done/single-source-cleanup.md) | `done` | One version of each pre-rollout artifact: one extraction prompt (v1), no stale gate record or prefilter yaml, event schema 1.0, one extractor, no DAG factory or plan.md, strategy params only in hypotheses, no compose copies of .env.example; 35 tests |
| [Managed ingestion config](specs/managed-ingestion-config.md) | `blocked` | Blocked by graph-and-connector wiring fixes + dashboard foundation; watchlist as single source for tickers and terms, append-only versions, vocabulary hash in prefilter_version, golden-set check; 25 tests |
| [Ingestion config UI](specs/ingestion-config-ui.md) | `blocked` | Blocked by managed ingestion config + dashboard foundation; companies, sources, history pages; research config read-only; 15 tests |
| [Signal browse views](specs/signal-browse-views.md) | `blocked` | Blocked by wiring fixes + dashboard foundation; paged signal, corroboration, company and entity APIs and views; 21 tests |
| [Pipeline control view](specs/pipeline-control-view.md) | `blocked` | Blocked by dashboard foundation + wiring fixes; Airflow runs, trigger, pause, cursors, run counts, re-extract DAG, dead letters; 20 tests |
| [Lineage trace view](specs/lineage-trace-view.md) | `blocked` | Blocked by signal browse views + wiring fixes; corroboration evidence, reproducible score, lineage endpoints, /trace; 20 tests |
| [Research results view](specs/research-results-view.md) | `draft` | Strategy direction decided 2026-10-08 (both); blocked by the result-producing specs; strategy-agnostic read API, decision references, results views |
| [Stack state persistence](specs/done/stack-state-persistence.md) | `done` | 12 tests; Airflow Fernet key, JWT and API secret from .env (required), admin password file on `airflow_state`, Kafka offsets 90 days + pinned cluster ID, project name in compose, filebeat registry volume, `airflow-db-role` one-shot, no `down -v` as a fix; recreate check pending on the stack machine (first-run step 8) |
| [Stack backup](specs/stack-backup.md) | `blocked` | Blocked by stack state persistence; nightly `auspex_backup` DAG → backup service: pg_dump of both databases, Neo4j JSONL export, additive MinIO mirror into a Mac folder, pruning, manifest; `restore` one-shot + runbook; 17 tests |
| [First run on the stack machine](specs/first-run-on-stack-machine.md) | `blocked` | Runs only on the user's Mac, started there by name; cloud sessions skip it. Stack up with prices from 2013, first universe build + coverage + backfill scope (closes point-in-time universe), Ollama gate at prompt v1 (Llama 3.1 8B Q8 vs Phi-3 14B, rule fixed in advance), one-source extraction test, backfill dry run if PR #8 has merged |

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
| 2026-10-09 | Point-in-time universe, window from 2014 | One universe from 2014-01 instead of a second version; backfill scope from BACKFILL_SCOPE_START; pre-2019 delisted tickers from XBRL instance names; 18 new tests, 218 backtesting unit green, mutation-checked | Yes (stack run) |
| 2026-10-08 | Control-surface scoping | Scoping session: 9 specs from the frontend audit (3 ready, 5 blocked, 1 draft); decisions approved by the user | No |
| 2026-10-09 | Pre-launch spec audit | Data-refresh and live-trading specs added; short interest and strategy runtime ready; stale blockers fixed; edits to #26/#28 files follow their merge | No |
| 2026-10-09 | Catalyst date panel | Code done — 10 required tests plus 38 edge-case tests, 24 mutations caught; 266 backtesting unit green; waits on the stack build | Yes (stack run) |
| 2026-10-09 | Infrastructure observability | Done — 26 new tests green, mutation-checked; stack smoke and alert delivery pending on the Mac (first-run step 8) | No |
| 2026-10-10 | Single-source cleanup | Done: 362 scraper, 272 backtesting, 13 strategy unit green, mutation-checked; Java unit and container tests proven in CI (Maven Central 429 locally) | No |
| 2026-10-10 | Stack state persistence | Done — 12 tests green, 14 mutations caught; 367 ingestion-scraper unit green; recreate check pending on the Mac | No |
| 2026-10-09 | Slow-signal pre-registration | Done — 37 tests green; protocol, H1–H12 at one version each; no trials on the new families | No |
| 2026-10-09 | Graph and connector wiring fixes | Done; container tests proven in CI | No |

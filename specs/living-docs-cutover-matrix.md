# Living docs migration matrix

Companion to `specs/living-docs-cutover.md`. It is **not a spec**: `docs-check.toml` excludes it from checks E and J, and it moves to `specs/done/` with the cutover spec.

Written against: develop @ e51f742. It was assembled from five domain fragments (engineering, system and contracts, ingestion and core-hub, research and strategy, operations), and every row cites its source as `path:line` or a requirements §.

## How to use it

* **One row per normative statement or block.**
  * `Disposition` says what happens to the statement: move, ratify, divergent, retire, link, keep or delete.
  * `Target` names the owner doc. `Spec` names the rollout spec that does the work.
* **`ID` is empty in this version.** Each domain spec fills `ID` for the rows whose Target is in its namespaces when it allocates numbers, and edits no other rows.
* **Decisions-table `IDs`** are filled the same way: a binding row is filled by every domain spec owning the `NS` cell of one of its `Fragment rows` (not the `M-<prefix>` of the row id), each appending its own IDs space-separated. On a rebase conflict in one cell, keep both sets.
* **"design §N"** refers to `specs/living-docs-cutover-design.md`.
* **Labels such as `E F11` or `F F12`** in Note cells are identifiers from the scoping investigations, kept only for traceability. Each row restates its rule in full, so no row depends on them. The defect labels C1, C5–C8, E F3, E F4, E F6, D F3, H1–H3 and A1–A3 are defined in `DECISIONS.md` under `2026-10-15 — Living docs — PENDING — defects found while scoping`.
* **Check M** (`python3 -m tools.docs_check --matrix specs/living-docs-cutover-matrix.md --domain NS`) fails while any move, ratify, divergent or retire row of `NS` has no defined ID, or its ID's verification `Source` lacks the row's document-level reference (path, `requirements §N` or DECISIONS heading; see `specs/docs-check-tooling.md`).
* **The decisions table** below classifies all 117 `CHOICE` heading texts in `DECISIONS.md` (counted outside code fences; all 117 texts are unique).
  * Binding rows get the IDs that cite them as `Source`.
  * Check M `--decisions` verifies both the classification and the IDs.

## At-risk classes

Scoping listed these classes of normative statements whose only home is an archived spec, a README, the `CLAUDE.md` trap list, a `DECISIONS.md` entry, a config comment or a `TODO.md` note. Rows cite them as "at-risk class #N"; the cutover's absorption audit checks each maps to an ID.

1. Date-only `published_date` is known after that day's close; entry at first NYSE session open after publication; calendar-day windows — `specs/done/backtest-look-ahead-fix.md:20-22`; DECISIONS `## 2026-10-07 — Backtest look-ahead fix — CHOICE — entry and holding-window timing`. HISTORICAL+TEST-ASSERTION names only.
2. One backtest event per corroboration, not per superseding record — DECISIONS `## 2026-10-07 — Backtest look-ahead fix — CHOICE — one backtest event per corroboration`.
3. Entity-only variant reported alongside full variant in all research output — DECISIONS `## 2026-09-19 — Phase 4 — FLAG (v2 …)`; `specs/done/backtesting.md`, `performance-metrics.md`.
4. Strategies never see `ingested_at`/`extracted_at`; only `corroborated_at + known-at delay` — DECISIONS `## 2026-09-20 — Strategy layer session 2 — CHOICE — Strategies never see ingested_at …`.
5. Processed-marker semantics (`dedup/processed/...`, written only after final outcome and Kafka flush; identity = model|prompt|prefilter) — DECISIONS `## 2026-10-07 — Live ingestion — CHOICE`; scraper README stage 3. Not in req §7.1.
6. Graph edge replacement on rewrite — core-hub README; `specs/done/graph-relationship-replacement.md`. Not in req §9.
7. Listener pause on store outage, DLT replay at-most-once (`corehub-dlt-replay` group) — core-hub README; `specs/done/dead-letter-recovery.md`; DECISIONS `## 2026-10-09 — Soak-test readiness — CHOICE — transient Kafka failures pause instead of retrying longer`.
8. SEC request budget split (EDGAR 4 req/s + universe build 5 req/s < 10) — DECISIONS `## 2026-10-09 — Soak-test readiness — CHOICE — SEC request budget across containers`; scraper README. Req §6.5 says "Configure 5 req/s".
9. Corroboration scorer formula — core-hub README only.
10. Dashboard/BFF security boundary: core-hub non-GET requires bearer write token; no CORS; browser only talks to dashboard — README architecture, core-hub README, DECISIONS `## 2026-10-08 — Control-surface scoping — CHOICE — dashboard runs in the stack behind its own server layer`. Not an invariant in CLAUDE.md or requirements §3.
11. Research config is read-only (changes only by dated re-registration) — DECISIONS 2026-10-08.
12. Single-user installation, no `user_id` — DECISIONS `## 2026-09-20 — Watchlist backend — CHOICE`.
13. core-hub calls ClinicalTrials.gov directly (watchlist preview) — DECISIONS `## 2026-09-20 — Watchlist backend — CHOICE — core-hub calls ClinicalTrials.gov directly`. Boundary exception not in requirements.
14. Deterministic intent ids; one DocumentRecord per participant; RiskDecision carries every check — `specs/done/decision-trace.md`; DECISIONS 2026-10-11.
15. Risk check order and units; kill switch before batched review; unmapped theme ticker rejected — `specs/done/portfolio-and-risk.md`, DECISIONS 2026-10-11, `config/themes.yaml` comment, strategy README.
16. Universe rules version lock (edit after build ⇒ new version) — `config/universe/rules.yaml` header comment only.
17. Publication-date rules for slow data (FINRA rule, 13F acceptance time from filing date) — DECISIONS 2026-10-09/10 entries; backtesting README.
18. Process/ops rules living only in CLAUDE.md: no hand-run setup scripts, stack-machine-only work in a spec, commit identity (CI check `.github/scripts/check_commit_identity.sh`), never `down -v` as a fix, Flyway frozen comments, operational traps (Fernet, bcrypt `$`, Grafana `$$`, Ollama `num_ctx`/digest, Docker Hub mirror, LocalStack licence).
19. Extraction gate threshold ≥0.85 `is_signal` precision and model decision rule fixed in advance — SETUP §3, DECISIONS `## 2026-10-08 — First run on the stack machine — CHOICE — local model decision rule`; not in req §11.3.
20. Requirements of "code done, blocked" active specs (point-in-time universe, ownership, short interest, catalyst panel, filing text, H9 score) — only in active specs + backtesting README.

## Decisions table

| Heading | Classification | IDs | Fragment rows |
|---|---|---|---|
| `## 2026-08-15 — Step 0.0 — CHOICE` | history |  | M-ENG-126 |
| `## 2026-08-15 — Step 0.0 — CHOICE — MinIO pinned to RELEASE.2025-09-07T16-13-09Z` | history |  | M-OPS-250 |
| `## 2026-08-15 — Step 0.0 — CHOICE — LLM provider changed from Anthropic to OpenAI` | history |  | M-EXT-043 |
| `## 2026-08-15 — Step 2.3 — CHOICE — Patent connector: PatentsView → Lens.org → EPO OPS (final)` | binding | ING-018 | M-ING-120 |
| `## 2026-08-15 — Step 0.0 — CHOICE — Ticker-restricted ingestion via pre-filter vocabulary (no architecture change)` | history |  | M-ING-122 |
| `## 2026-08-15 — Step 2.3 — CHOICE — Patent connector changed from Lens.org to EPO OPS` | binding | ING-018 | M-ING-121 |
| `## 2026-08-15 — Step 0.0 — CHOICE — Watched tickers and initial pre-filter vocabulary` | history |  | M-ING-123 |
| `## 2026-09-19 — Watchlist & alerts — CHOICE — Discord webhook transport` | history |  | M-COR-027 |
| `## 2026-09-19 — Watchlist & alerts — CHOICE — Entity-key-based watchlist, not ticker-based` | history |  | M-COR-028 |
| `## 2026-09-19 — Historical backfill — CHOICE — Option A: local model for backfill, API model forward-only` | binding | EXT-013 | M-EXT-044 |
| `## 2026-09-19 — CI/CD pipeline — CHOICE — GitHub-hosted runners` | binding | ENG-013 | M-ENG-127 |
| `## 2026-09-20 — Watchlist backend — CHOICE — No user_id column; single-user installation, extensible` | binding | SYS-004 HUB-039 | M-SYS-183,M-HUB-073 |
| `## 2026-09-20 — Watchlist backend — CHOICE — core-hub calls ClinicalTrials.gov directly` | binding | INV-4 HUB-047 | M-INV-035,M-HUB-074 |
| `## 2026-09-20 — Option A hosting — CHOICE — A1 (MacBook) confirmed for Phase 4; A2/A3 deferred` | history |  | M-EXT-045,M-OPS-251 |
| `## 2026-09-20 — Strategy layer — CHOICE — XBI as primary benchmark` | history |  | M-EVA-060 |
| `## 2026-09-20 — Strategy layer — CHOICE — Known-at delay default: 1 business day after corroborated_at` | history |  | M-EVA-061 |
| `## 2026-09-20 — Strategy layer — CHOICE — Holdout: last 3 months sealed` | history |  | M-EVA-062 |
| `## 2026-09-20 — Strategy layer session 2 — CHOICE — New `services/strategy/` service (not extending backtesting)` | binding |  | M-STR-070 |
| `## 2026-09-20 — Strategy layer session 2 — CHOICE — MinIO for virtual books and traces; strategy service serves metrics API` | binding |  | M-STR-071 |
| `## 2026-09-20 — Strategy layer session 2 — CHOICE — Event-driven Kafka consumer for the strategy runtime` | binding | CON-002 | M-CON-082,M-STR-072 |
| `## 2026-09-20 — Strategy layer session 2 — CHOICE — Strategies never see ingested_at or extracted_at; InputHealthMonitor handles model downtime` | binding |  | M-STR-073 |
| `## 2026-09-20 — Strategy layer session 2 — CHOICE — Equal risk budget per promoted strategy; correlation-aware cap` | binding |  | M-STR-074 |
| `## 2026-09-20 — Strategy layer session 2 — CHOICE — Minimum 20 trades before metrics and Kelly sizing` | binding |  | M-STR-075 |
| `## 2026-09-19 — Dashboard — CHOICE — Node 22 LTS (Phase 5 resolution)` | history |  | M-ENG-128 |
| `## 2026-09-25 — Watchlist backend — CHOICE — live preview smoke test deferred` | history |  | M-HUB-075 |
| `## 2026-10-07 — Live ingestion — CHOICE — unchanged re-fetch skip with retry-safe markers` | binding | ING-032 | M-ING-124 |
| `## 2026-10-07 — Market simulation — CHOICE — PositionSizer `fx_rate` is EUR per USD` | binding |  | M-RES-170 |
| `## 2026-10-07 — Market simulation — CHOICE — FillModel does not shift entry dates` | binding |  | M-RES-171 |
| `## 2026-10-07 — Market simulation — CHOICE — 11 tests, not 10; `scripts/fetch_prices.py`` | history |  | M-ENG-129 |
| `## 2026-10-07 — Local model integration — CHOICE — gate threshold and version labels aligned` | binding | EXT-007 EXT-013 | M-EXT-046 |
| `## 2026-10-07 — Startup data — CHOICE — data fills itself on `up`; prices refresh daily` | binding | OPS-009 OPS-026 | M-SYS-186,M-RES-174,M-OPS-252 |
| `## 2026-10-07 — Realistic cost model — CHOICE — per-ticker spread, FX fee, volume cap, gap-through stops` | binding |  | M-RES-175 |
| `## 2026-10-07 — Pre-registration — CHOICE — evaluation protocol and kill criteria locked before the backfill` | binding |  | M-EVA-063 |
| `## 2026-10-07 — Pre-registration — CHOICE — trials counted as cells across the hypothesis family, budget 64` | binding |  | M-EVA-064 |
| `## 2026-10-07 — Pre-registration — CHOICE — market-model abnormal returns against XBI with two-way clustered errors` | binding |  | M-EVA-065 |
| `## 2026-10-07 — Pre-registration — CHOICE — hypothesis triage; versions 2 registered` | binding |  | M-EVA-066 |
| `## 2026-10-07 — Pre-registration — CHOICE — sizing ceilings: quarter Kelly, 5% per name, one position per theme, no hold through binary events` | binding |  | M-EVA-067 |
| `## 2026-10-07 — EDGAR press-release content — CHOICE — filing index replaces the submissions lookup` | binding | ING-014 ING-017 | M-ING-125 |
| `## 2026-10-07 — Second-wave specs — CHOICE — structured filings bypass the LLM` | history |  | M-ING-126 |
| `## 2026-10-07 — Second-wave specs — CHOICE — short interest is a market-data snapshot, not a connector` | binding | INV-4 | M-INV-039,M-RES-176 |
| `## 2026-10-07 — Second-wave specs — CHOICE — point-in-time universe scope` | binding |  | M-RES-177 |
| `## 2026-10-07 — Second-wave specs — CHOICE — paper trading gates capital, run at several sizes` | binding |  | M-EVA-069 |
| `## 2026-10-07 — Backtest look-ahead fix — CHOICE — one backtest event per corroboration, not per superseding record` | binding |  | M-RES-179 |
| `## 2026-10-07 — Backtest look-ahead fix — CHOICE — entry and holding-window timing` | binding |  | M-RES-180 |
| `## 2026-10-07 — Company-level extraction — CHOICE — event taxonomy and identifier fields (schema 1.1)` | binding | CON-013 CON-016 EXT-008 ING-019 HUB-033 | M-CON-083,M-EXT-047 |
| `## 2026-10-07 — Edge research scoping — CHOICE — edge research synthesis: the alpha path becomes slow monthly scores` | history |  | M-EVA-070 |
| `## 2026-10-07 — Edge research scoping — CHOICE — ownership and insider data are snapshots, not connectors` | binding | INV-4 | M-INV-040,M-RES-181 |
| `## 2026-10-07 — Edge research scoping — CHOICE — deferred items` | history |  | M-EVA-073 |
| `## 2026-10-08 — Edge research scoping — CHOICE — quarterly banded rotation; catalysts as a guard, not a trigger` | binding |  | M-RES-183 |
| `## 2026-10-08 — Edge research scoping — CHOICE — two non-LLM panels before the LLM backfill` | binding |  | M-EVA-074 |
| `## 2026-10-08 — Point-in-time universe — CHOICE — how the monthly list is derived from free SEC data` | binding |  | M-RES-184 |
| `## 2026-10-08 — Point-in-time universe — CHOICE — windows the prices do not cover` | binding |  | M-RES-185 |
| `## 2026-10-08 — Control-surface scoping — CHOICE — Grafana for technical health, dashboard for using the application` | binding | OPS-051 | M-DSH-034,M-OPS-253 |
| `## 2026-10-08 — Control-surface scoping — CHOICE — the watchlist is the single source for tracked tickers and terms` | history |  | M-ING-127,M-DSH-035 |
| `## 2026-10-08 — Control-surface scoping — CHOICE — research config is read-only in the dashboard` | binding |  | M-DSH-036 |
| `## 2026-10-08 — Control-surface scoping — CHOICE — dashboard runs in the stack behind its own server layer` | binding | HUB-041 HUB-043 | M-SYS-184,M-HUB-076,M-DSH-037 |
| `## 2026-10-08 — First run on the stack machine — CHOICE — price history from 2013, set before the first `up`` | history |  | M-RES-186 |
| `## 2026-10-08 — First run on the stack machine — CHOICE — local model decision rule, fixed before the gate runs` | binding | EXT-014 | M-EXT-048 |
| `## 2026-10-09 — Guideline setup — CHOICE — merge flow, merge bar and shared-log conflicts written into the repo` | binding | ENG-010 ENG-011 ENG-030 ENG-031 ENG-032 | M-ENG-130,M-SYS-185 |
| `## 2026-10-09 — Point-in-time universe — CHOICE — one universe from 2014, backfill scope from its own start` | binding |  | M-RES-187 |
| `## 2026-10-08 — Edge research scoping — CHOICE — direction: both` | history |  | M-EVA-075 |
| `## 2026-10-08 — Edge research scoping — CHOICE — portfolio paper-trading pass rule` | binding |  | M-EVA-076 |
| `## 2026-10-08 — Edge research scoping — CHOICE — build order` | history |  | M-EVA-077 |
| `## 2026-10-09 — CI — CHOICE — container images off anonymous Docker Hub` | binding | OPS-008 | M-ENG-131,M-OPS-254 |
| `## 2026-10-09 — CI — CHOICE — remaining test images through mirror.gcr.io` | history |  | M-ENG-132 |
| `## 2026-10-09 — Stack backup — CHOICE — nightly backup to a folder on the Mac` | binding | INV-2 OPS-060 OPS-069 | M-INV-037,M-OPS-257 |
| `## 2026-10-09 — Soak-test readiness — CHOICE — cursor after a run with failed documents` | binding | ING-026 OPS-035 | M-ING-128,M-OPS-258 |
| `## 2026-10-09 — Soak-test readiness — CHOICE — transient Kafka failures pause instead of retrying longer` | binding | HUB-012 HUB-013 HUB-016 | M-HUB-077 |
| `## 2026-10-09 — Soak-test readiness — CHOICE — SEC request budget across containers` | binding | ING-006 ING-007 OPS-023 | M-ING-129,M-OPS-259 |
| `## 2026-10-09 — Dashboard foundation — CHOICE — Next 16, Vitest 5 and Tailwind 4 to clear the advisories` | history |  | M-DSH-032 |
| `## 2026-10-09 — Dashboard foundation — CHOICE — login endpoint, write-token failure mode, path layout` | binding | HUB-041 | M-HUB-078,M-DSH-033 |
| `## 2026-10-09 — Pre-launch spec audit — CHOICE — gaps closed in the spec index` | history |  | M-ENG-133 |
| `## 2026-10-09 — Catalyst date panel — CHOICE — how documents become rows` | binding |  | M-RES-189 |
| `## 2026-10-09 — Infrastructure observability — CHOICE — monitoring role from a one-shot, not an init script` | binding | OPS-013 | M-OPS-260 |
| `## 2026-10-09 — Infrastructure observability — CHOICE — compose defaults for sizes and thresholds` | history |  | M-OPS-261 |
| `## 2026-10-09 — Infrastructure observability — CHOICE — memory limits sized to 7.5 GB, first estimates` | binding | OPS-014 | M-OPS-262 |
| `## 2026-10-09 — Infrastructure observability — CHOICE — VM and volume metrics without host bind mounts` | binding | OPS-045 | M-OPS-263 |
| `## 2026-10-09 — Infrastructure observability — CHOICE — alert definitions the spec left open` | binding | OPS-055 | M-OPS-264 |
| `## 2026-10-09 — Infrastructure observability — CHOICE — monitoring values only in .env.example` | binding | OPS-006 | M-OPS-265 |
| `## 2026-10-10 — Infrastructure observability — CHOICE — dashboard memory limit and health probe` | binding | OPS-014 OPS-044 | M-OPS-266 |
| `## 2026-10-10 — Single-source cleanup — CHOICE — one version of each pre-rollout artifact` | binding | CON-008 | M-ENG-134,M-CON-084,M-STR-084 |
| `## 2026-10-09 — Dashboard — CHOICE — Node 24 LTS, actions on Node 24` | history |  | M-ENG-135 |
| `## 2026-10-09 — CI — CHOICE — one prefix for every test image` | binding | ENG-014 | M-ENG-136,M-OPS-256 |
| `## 2026-10-10 — Stack state persistence — CHOICE — required secrets and a writable state volume` | binding | OPS-037 OPS-013 OPS-039 | M-OPS-267 |
| `## 2026-10-09 — Slow-signal pre-registration — CHOICE — one protocol and one version per hypothesis, H9–H12 registered` | binding |  | M-EVA-079 |
| `## 2026-10-09 — Slow-signal pre-registration — CHOICE — details the spec left open` | binding |  | M-EVA-080 |
| `## 2026-10-09 — Graph and connector wiring fixes — CHOICE — publish threshold default is 0.0, not the API's 0.5` | binding | EXT-002 | M-EXT-049 |
| `## 2026-10-09 — Graph and connector wiring fixes — CHOICE — ticker resolution details` | binding | HUB-034 HUB-047 | M-HUB-079 |
| `## 2026-10-09 — Graph and connector wiring fixes — CHOICE — calibrated publish thresholds before launch` | binding | EXT-021 | M-EXT-050 |
| `## 2026-10-09 — Graph and connector wiring fixes — CHOICE — no VIA migration` | history |  | M-HUB-080 |
| `## 2026-10-09 — SEC ownership datasets — CHOICE — acceptance time from a filing date` | binding |  | M-RES-190 |
| `## 2026-10-09 — SEC ownership datasets — CHOICE — how filings, amendments and trades are counted` | binding |  | M-RES-191 |
| `## 2026-10-09 — SEC ownership datasets — CHOICE — specialist thresholds have one source, the registered H9` | binding |  | M-RES-193 |
| `## 2026-10-10 — Container limits and log rotation — CHOICE — json-file log driver with rotation, not local` | binding | OPS-042 | M-OPS-268 |
| `## 2026-10-10 — Pipeline alerting gaps — CHOICE — Source Silence reads the last run over 7 days, and no data alerts` | binding | OPS-058 | M-OPS-269 |
| `## 2026-10-10 — Pipeline alerting gaps — CHOICE — which sources the daily summary lists` | binding | OPS-059 | M-OPS-270 |
| `## 2026-10-10 — Pipeline alerting gaps — CHOICE — Elasticsearch read-only indices from the exporter` | binding | OPS-049 | M-OPS-271 |
| `## 2026-10-10 — Pre-launch spec audit — CHOICE — portfolio verdict and the remaining blockers` | binding |  | M-EVA-081 |
| `## 2026-10-10 — Stack backup — CHOICE — client tools from the server image, memory and restore semantics` | binding | INV-2 OPS-020 OPS-066 OPS-067 | M-INV-038,M-OPS-272 |
| `## 2026-10-10 — Ingestion run reliability — CHOICE — schedule times, extraction cap and task timeout` | binding | ING-027 OPS-028 OPS-030 | M-ING-131,M-OPS-273 |
| `## 2026-10-10 — Ingestion run reliability — CHOICE — rate limiter spaces requests evenly, with no burst` | binding | ING-005 | M-ING-132 |
| `## 2026-10-10 — Ingestion run reliability — CHOICE — a 403 on a filing index also stops the EDGAR run` | binding | ING-007 | M-ING-133 |
| `## 2026-10-10 — Ingestion run reliability — CHOICE — requirements §5 text follows the 2026-10-09 cursor decision` | history |  | M-ING-134 |
| `## 2026-10-10 — Consolidated code, strategy and BV audit — CHOICE — what becomes specs, what does not` | binding |  | M-ENG-137,M-EVA-082 |
| `## 2026-10-10 — Price finality and split availability — CHOICE — edges the spec leaves open` | binding |  | M-RES-194 |
| `## 2026-10-10 — Corroboration late arrivals — CHOICE — contract test signals are written pending, clear runs after the commit` | binding | COR-001 COR-010 | M-COR-029 |
| `## 2026-10-10 — Evaluation protocol — CHOICE — how the event evaluation reads the spec` | binding |  | M-EVA-083 |
| `## 2026-10-10 — Evaluation protocol — CHOICE — the raw-return backtest reserves trial cells too` | binding |  | M-EVA-084 |
| `## 2026-10-10 — Short interest snapshots — CHOICE — publication dates from FINRA's rule, published rows win` | binding |  | M-RES-195 |
| `## 2026-10-10 — Strategy runtime — CHOICE — state placement, timing and the pass-through stub` | binding | INV-11 | M-INV-041,M-STR-079,M-OPS-275 |
| `## 2026-10-11 — Cross-sectional portfolio backtest — CHOICE — how the engine reads the spec` | binding |  | M-RES-196 |
| `## 2026-10-11 — Strategy metrics — CHOICE — where the spec left the metrics open` | binding |  | M-STR-080 |
| `## 2026-10-11 — Short interest snapshots — CHOICE — short interest share and change on one split basis` | binding |  | M-RES-197 |
| `## 2026-10-15 — Filing text change score — CHOICE — how the panel reads EDGAR and where the second universe lives` | binding |  | M-RES-198 |
| `## 2026-10-11 — Decision trace — CHOICE — one document record per participant, deterministic intent ids, risk reviews per event` | binding |  | M-STR-081 |
| `## 2026-10-11 — Portfolio and risk — CHOICE — catalyst and short-interest sources, units and check order` | binding |  | M-STR-082 |
| `## 2026-10-15 — Holdings composite score — CHOICE — where the spec left the H9 score open` | binding |  | M-RES-199 |

## Engineering (ENG)


Baseline `develop` @ `e51f742`. Specs: `docs-check-tooling` (tooling, workflows), `living-docs-engineering-workflow` (ENG docs, `specs/README.md`, `_template.md`, PR template). "item N" in Target is the numbered requirement list in `specs/living-docs-engineering-workflow.md` (ENG numbers are assigned in that order with `--next ENG`). Hard rules owned by root `AGENTS.md` get no ID (design §7.2). `living-docs-system-and-contracts` owns the naming, invariants, no-legacy and known-traps sections of root `CLAUDE.md`; they are not covered here.

Abbreviations: VER = `docs/engineering/verification.md`, CW = `docs/engineering/change-workflow.md`, CNV = `docs/engineering/conventions.md`, AG = root `AGENTS.md`, SAG = service `AGENTS.md`, The `Spec` column names spec files without the `.md`.

### Root `CLAUDE.md` (process sections)

| Row | Source (path:line or §) | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-ENG-001 | CLAUDE.md:3-9 | `@TODO.md`, `@VERSIONS.md` auto-loaded every session | process | retire | AG (no auto-load) | — | agent-instruction-hierarchy | `agent instruction files` PENDING heading (default) |  |
| M-ENG-002 | CLAUDE.md:10-14 | On-demand reading list: specs, requirements, PREREQUISITES, DECISIONS, SETUP | process | link | AG "Where things are" | — | agent-instruction-hierarchy | routing, no rule |  |
| M-ENG-003 | CLAUDE.md:14 | New manual step goes to SETUP.md only if not automatable | process | link | AG; OPS topology owns "no hand-run setup" | — | agent-instruction-hierarchy | at-risk class #18 |  |
| M-ENG-004 | CLAUDE.md:16 | Assigned spec is the work; else first `ready`; update spec as items complete | process | keep | AG session start | — | agent-instruction-hierarchy | hard rule (agent session) |  |
| M-ENG-005 | CLAUDE.md:35-36 | "What this is": see README | status-note | link | AG / README | — | agent-instruction-hierarchy | |  |
| M-ENG-006 | CLAUDE.md:39-40 | Read TODO, open spec, read in full | process | keep | AG session start | — | agent-instruction-hierarchy | hard rule |  |
| M-ENG-007 | CLAUDE.md:41 | No ready spec: scope a draft; scoping = tests and DoD only | process | move | CW item 17 (scoping clause) | ENG | living-docs-engineering-workflow | engineering ratification batch | ENG-017 |
| M-ENG-008 | CLAUDE.md:42 | Confirm required tests consistent with requirements before writing | process | keep | AG (rule that matters most) | — | agent-instruction-hierarchy | hard rule; §13 ¶1 restates it (M-ENG-061) |  |
| M-ENG-009 | CLAUDE.md:43 | Work only the current spec | process | keep | AG session start | — | agent-instruction-hierarchy | hard rule |  |
| M-ENG-010 | CLAUDE.md:44 | Done: mark done, move to specs/done, repoint TODO row, PR | process | move | CW item 16 | ENG | living-docs-engineering-workflow | engineering ratification batch; enforced by check J | ENG-016 |
| M-ENG-011 | CLAUDE.md:50 | Green suite necessary not sufficient; stop, DECISIONS, ask if test violates requirement | process | keep | AG verbatim | — | agent-instruction-hierarchy | design §7.2: AG owns |  |
| M-ENG-012 | CLAUDE.md:52 | `test_dag_task_only_invokes_fetch_since` anecdote | rationale | keep | AG (one line) or VER Rationale | — | agent-instruction-hierarchy | non-normative |  |
| M-ENG-013 | CLAUDE.md:73-97 | Service command table (Python, Java, backtesting, backup, dashboard, fixture) | command | link | each SAG `## Commands` | — | agent-instruction-hierarchy | Codex cannot follow links, so commands live in the loaded file |  |
| M-ENG-014 | CLAUDE.md:75-78,93,96 | Stack commands: compose up/down, `down -v`, restore, smoke | command | link | root README.md (owner) | — | legacy-docs-retirement | `down -v` text guarded by `test_docs_never_offer_down_v_as_a_fix` |  |
| M-ENG-015 | CLAUDE.md:99 | Zero-tests run is a failure; check reported count | process | keep | AG hard rule | — | agent-instruction-hierarchy | §7.2: no ENG ID |  |
| M-ENG-016 | CLAUDE.md:99 | `failOnNoDiscoveredTests = true` on every Test task; `--strict-markers` | requirement | ratify | VER item 3 | ENG | living-docs-engineering-workflow | code: `build.gradle.kts:95,101-102`, pyproject addopts; engineering ratification batch | ENG-003 |
| M-ENG-017 | CLAUDE.md:101 | Gradle UP-TO-DATE is not a pass; prove with `--rerun-tasks` | process | keep | AG hard rule | — | agent-instruction-hierarchy | CI part (`--rerun-tasks` in java.yml) in VER item 3 |  |
| M-ENG-018 | CLAUDE.md:105-109 | Red for the right reason (Python errors vs Java compile/assertion) | process | ratify | VER item 1 | ENG | living-docs-engineering-workflow | engineering ratification batch | ENG-001 |
| M-ENG-019 | CLAUDE.md:109 | Paste failure output into PR description | process | ratify | VER item 1; PR template | ENG | living-docs-engineering-workflow | engineering ratification batch | ENG-001 |
| M-ENG-020 | CLAUDE.md:110-114 | Inner loop steps; full container suite at spec completion only | process | ratify | VER item 2 | ENG | living-docs-engineering-workflow | engineering ratification batch | ENG-002 |
| M-ENG-021 | CLAUDE.md:111 | Step 7 "Update docs (see below)" | process | link | CW item 20 | — | living-docs-engineering-workflow | replaced by the owner-doc rule |  |
| M-ENG-022 | CLAUDE.md:118 | Doc updates are part of the commit | process | move | CW items 19–20 | ENG | living-docs-engineering-workflow | `docs impact field and Docs unchanged line` PENDING heading | ENG-019 ENG-020 |
| M-ENG-023 | CLAUDE.md:120-133 | Change-type → README/CLAUDE.md update table | process | retire | replaced by `docs/engineering/conventions.md` item 40 | — | living-docs-engineering-workflow | generator of finding #11 (duplication); retired, not moved |  |
| M-ENG-024 | CLAUDE.md:135 | Update both CLAUDE.md and README; "intentional duplication is fine" | stale | delete | — | — | living-docs-engineering-workflow | contradicts one-owner rule (CNV item 40) |  |
| M-ENG-025 | CLAUDE.md:137 | Scaffolding exemption from test-first | invariant | link | INV-15 exception in `docs/system/invariants.md` | INV | living-docs-system-and-contracts | Same source as M-SYS-039, which carries the ID |  |
| M-ENG-026 | CLAUDE.md:140 | A comment tells what the code cannot; readable cold | requirement | ratify | CNV item 43 | ENG | living-docs-engineering-workflow | engineering ratification batch | ENG-043 |
| M-ENG-027 | CLAUDE.md:141 | Javadoc / docstrings / TSDoc per stack; conventions in services/CLAUDE.md | process | link | `services/AGENTS.md` | — | agent-instruction-hierarchy | §7.2 per-stack form stays nested |  |
| M-ENG-028 | CLAUDE.md:142 | Never in a comment: restatement, narration, plan steps, history… | requirement | ratify | CNV item 44 | ENG | living-docs-engineering-workflow | engineering ratification batch | ENG-044 |
| M-ENG-029 | CLAUDE.md:143 | Doc comments on contracts, not everything | requirement | ratify | CNV item 45 | ENG | living-docs-engineering-workflow | engineering ratification batch | ENG-045 |
| M-ENG-030 | CLAUDE.md:144 | Stale is worse than missing; fix comments in same commit | requirement | ratify | CNV item 46 | ENG | living-docs-engineering-workflow | engineering ratification batch | ENG-046 |
| M-ENG-031 | CLAUDE.md:145 | Flyway migrations frozen; don't edit comments | requirement | link | HUB (`docs/core-hub/storage.md`) | HUB | living-docs-core-hub | not ENG; CNV links |  |
| M-ENG-032 | CLAUDE.md:149-152 | Test file layout per service (unit/integration, *Test/*IT) | command | link | SAG `## Layout` | — | agent-instruction-hierarchy | |  |
| M-ENG-033 | CLAUDE.md:149 | `@pytest.mark.unit (default)` | stale | delete | — | — | living-docs-engineering-workflow | unregistered, unused (`grep mark\.unit` → 0); would fail `--strict-markers` |  |
| M-ENG-034 | CLAUDE.md:154 | CorroborationServiceContractTest abstract; new impl passes it unmodified | requirement | link | COR (`docs/core-hub/corroboration.md`) | COR | living-docs-core-hub | not ENG |  |
| M-ENG-035 | CLAUDE.md:158-163 | Git Flow branches: main, develop, feature, release, hotfix | process | ratify | CW item 29 | ENG | living-docs-engineering-workflow | engineering ratification batch | ENG-029 |
| M-ENG-036 | CLAUDE.md:161 | One feature branch per spec, name from spec | process | ratify | CW item 29 | ENG | living-docs-engineering-workflow | engineering ratification batch | ENG-029 |
| M-ENG-037 | CLAUDE.md:165-169 | Rebase not merge commits; ff-only; no `--no-ff` unless agreed | process | move | CW item 30 | ENG | living-docs-engineering-workflow | Guideline setup CHOICE (binding) | ENG-030 |
| M-ENG-038 | CLAUDE.md:172 | Push feature branch, PR into develop; never push develop/main | process | keep | AG hard rule | — | agent-instruction-hierarchy | §7.2 |  |
| M-ENG-039 | CLAUDE.md:173 | CI green and ready-to-merge before asking | process | move | VER item 10 | ENG | living-docs-engineering-workflow | Guideline setup CHOICE | ENG-010 |
| M-ENG-040 | CLAUDE.md:174 | Merge only when the owner says so | process | keep | AG hard rule | — | agent-instruction-hierarchy | §7.2 |  |
| M-ENG-041 | CLAUDE.md:175-179 | Local rebase + ff-only recipe; not GitHub merge button | process | move | CW item 30 (+ `docs_check --base` step) | ENG | living-docs-engineering-workflow | Guideline setup CHOICE; docs_check step in engineering ratification batch | ENG-030 |
| M-ENG-042 | CLAUDE.md:180 | main only through release branch on owner's request | process | move | CW item 31 | ENG | living-docs-engineering-workflow | Guideline setup CHOICE | ENG-031 |
| M-ENG-043 | CLAUDE.md:182-183 | Every added/altered behaviour has a test | requirement | move | VER item 10 | ENG | living-docs-engineering-workflow | Guideline setup CHOICE | ENG-010 |
| M-ENG-044 | CLAUDE.md:184 | Mutation check locally; mutant never own branch; CI-only commit+revert | requirement | move | VER item 11 | ENG | living-docs-engineering-workflow | Guideline setup CHOICE | ENG-011 |
| M-ENG-045 | CLAUDE.md:185 | Spec PR: every requirement maps to a named test | requirement | move | VER item 10 | ENG | living-docs-engineering-workflow | Guideline setup CHOICE; reworded to Docs impact IDs | ENG-010 |
| M-ENG-046 | CLAUDE.md:186 | PR description lists mutation checks and CI-only runs | process | move | VER item 11; PR template | ENG | living-docs-engineering-workflow | Guideline setup CHOICE | ENG-011 |
| M-ENG-047 | CLAUDE.md:188 | Union merge driver; after rebase check order, no duplicates | process | move | CW item 32 | ENG | living-docs-engineering-workflow | Guideline setup CHOICE; J enforces TODO dups | ENG-032 |
| M-ENG-048 | CLAUDE.md:191 | Commit only when the spec's tests pass | process | ratify | CW item 35 | ENG | living-docs-engineering-workflow | engineering ratification batch | ENG-035 |
| M-ENG-049 | CLAUDE.md:192 | Never commit .env, target/, .venv/, __pycache__/, volumes | value | ratify | CW item 35; list owned by `.gitignore` | ENG | living-docs-engineering-workflow | list not copied | ENG-035 |
| M-ENG-050 | CLAUDE.md:193 | Claude never author/committer/co-author; no trailers; CI check | process | keep | AG hard rule | — | agent-instruction-hierarchy | enforced by `commit-identity.yml`; at-risk class #18 |  |
| M-ENG-051 | CLAUDE.md:194 | No Claude footers on GitHub; keep comments rare | process | keep | AG hard rule | — | agent-instruction-hierarchy | PR template carries no footer (`living-docs-engineering-workflow` test) |  |
| M-ENG-052 | CLAUDE.md:195 | Commit subject: one lowercase line, `subject: detail1, detail2` | process | keep | AG hard rule | — | agent-instruction-hierarchy | |  |
| M-ENG-053 | CLAUDE.md:198 | Cloud sessions: no Docker/sec.gov/Yahoo; container tests proven in CI | process | keep | AG hard rule | — | agent-instruction-hierarchy | VER item 13 links for "what CI proves" |  |
| M-ENG-054 | CLAUDE.md:198 | Cloud sessions cannot delete branches; don't push disposable ones | process | keep | AG hard rule | — | agent-instruction-hierarchy | |  |
| M-ENG-055 | CLAUDE.md:199 | Mac-only work goes into a spec the owner runs there | process | keep | AG hard rule | — | agent-instruction-hierarchy | at-risk class #18 |  |
| M-ENG-056 | CLAUDE.md:200 | No hand-run setup/data scripts; one-shots and DAGs | requirement | link | OPS `docs/operations/topology.md` (owner); AG pointer | OPS | living-docs-operations | at-risk class #18; R1 §3a |  |
| M-ENG-057 | CLAUDE.md:229-243 | File map | process | keep | AG "Where things are" | — | agent-instruction-hierarchy | |  |
| M-ENG-058 | CLAUDE.md:237 | DECISIONS heading format `## date — topic — TYPE — title` | process | link | DECISIONS.md header (keep); CW item 33 | ENG | living-docs-engineering-workflow | format stays in the file's own header |  |
| M-ENG-059 | CLAUDE.md:233 | `specs/` holds draft, ready, blocked | stale | delete | — | — | agent-instruction-hierarchy | omits `hold`; CW item 16 owns statuses |  |
| M-ENG-060 | CLAUDE.md:246 | Don't report complete unless tests ran; blocked → DECISIONS and stop | process | keep | AG hard rule | — | agent-instruction-hierarchy | |  |

### `docs/requirements.md` §13–§14

| Row | Source (path:line or §) | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-ENG-061 | §13 ¶1 (:396) | Tests precede implementation; DoD includes check against requirements | requirement | link | INV-15 (test-first); AG rule that matters most | INV | living-docs-system-and-contracts, agent-instruction-hierarchy | no ENG restatement |  |
| M-ENG-062 | §13 ¶2 (:398) | pytest unit/integration with `integration` marker | requirement | ratify | VER item 3 | ENG | living-docs-engineering-workflow | source §13; layout to SAG | ENG-003 |
| M-ENG-063 | §13 ¶2 (:398) | `--disable-socket` across scraper unit suite | requirement | divergent | VER item 4 | ENG | living-docs-engineering-workflow | FLAG `ingestion-scraper unit suite does not disable sockets` (appended by `living-docs-engineering-workflow`); code `pyproject.toml` | ENG-004 |
| M-ENG-064 | §13 ¶2 (:398) | Source APIs stubbed via respx; OpenAI client injected and stubbed | requirement | move | VER item 5 | ENG | living-docs-engineering-workflow | source §13 | ENG-005 |
| M-ENG-065 | §13 ¶2 (:398) | Testcontainers for MinIO and Kafka, not manual compose | requirement | move | VER item 6 | ENG | living-docs-engineering-workflow | source §13, §14 | ENG-006 |
| M-ENG-066 | §13 ¶2 (:398) | Injected `now()` provider throughout | requirement | move | VER item 5 | ENG | living-docs-engineering-workflow | source §13 | ENG-005 |
| M-ENG-067 | §13 ¶3 (:400) | core-hub container tests for round trips, Cypher, DLQ, upsert | requirement | move | VER item 6 | ENG | living-docs-engineering-workflow | source §13 | ENG-006 |
| M-ENG-068 | §13 ¶3 (:400) | Plain unit tests (no Spring) for DTO, validation, scoring `[C2]` | requirement | move | VER item 8 | ENG | living-docs-engineering-workflow | source §13 | ENG-008 |
| M-ENG-069 | §13 ¶3 (:400) | Static singleton containers, reuse, one context, no DirtiesContext, truncation | requirement | move | VER item 6 | ENG | living-docs-engineering-workflow | source §13 | ENG-006 |
| M-ENG-070 | §13 ¶3 (:400) | Phase 1 Java suite under three minutes locally | stale | delete | — | — | living-docs-engineering-workflow | plan-step target; machine-specific; CNV item 44 bans targets in docs of this kind |  |
| M-ENG-071 | §13 ¶3 (:400) | `Clock` injected; awaitility, never `Thread.sleep` | requirement | move | VER item 5 | ENG | living-docs-engineering-workflow | source §13 | ENG-005 |
| M-ENG-072 | §13 ¶3 (:400) | Timezone test as separate `timezoneCheck` task, forked JVM | requirement | move | VER item 7 | ENG | living-docs-engineering-workflow | source §13; supports INV-9 | ENG-007 |
| M-ENG-073 | §13 ¶3 (:400) | Container tests in own `integrationTest` source set | requirement | move | VER item 7 | ENG | living-docs-engineering-workflow | source §13 | ENG-007 |
| M-ENG-074 | §13 ¶3 (:400) | ArchUnit: no concatenated queries, no unqualified @Transactional, no source branching | requirement | link | INV-12 / INV-4 (`living-docs-system-and-contracts`); HUB | INV | living-docs-system-and-contracts | not ENG |  |
| M-ENG-075 | §13 ¶4 (:402) | Contract fixture generated by pytest; CI fails if dirty | contract | link | CON (`docs/system/contracts.md`) | CON | living-docs-system-and-contracts | file name stale (`research_signal_event.json` → `signal_event_v1.json`) |  |
| M-ENG-076 | §13 ¶5 (:404) | Named guards each have a test failing on plausible-wrong impl | requirement | link | each owner domain (ING, EXT, HUB, COR, CON) | — | — | general rule = VER item 10 |  |
| M-ENG-077 | §13 ¶6 (:406) | `verify_pipeline.sh` is smoke, never correctness authority | requirement | move | VER item 9 | ENG | living-docs-engineering-workflow | source §13 | ENG-009 |
| M-ENG-078 | §14 (:412) | Settled: Testcontainers over mocks at store boundary; TDD | rationale | link | VER item 6 Rationale; INV-15 | — | living-docs-engineering-workflow | §14 becomes Rationale (design §6) |  |

### `specs/README.md`

| Row | Source (path:line or §) | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-ENG-079 | "What a spec must be" — self-contained | Cold session with spec + root CLAUDE.md can start; prerequisites in Blocked by | requirement | ratify | CW item 17; README keeps explanation citing ID | ENG | living-docs-engineering-workflow | "CLAUDE.md" → "AGENTS.md" | ENG-017 |
| M-ENG-080 | same — one deliverable | One independently executable unit; >1 session probably two specs | requirement | ratify | CW item 17 | ENG | living-docs-engineering-workflow | engineering ratification batch | ENG-017 |
| M-ENG-081 | same — named after what it does | Filename and title describe the deliverable | requirement | ratify | CW item 17 | ENG | living-docs-engineering-workflow | plan-step ban itself: SYS naming (`living-docs-system-and-contracts`) | ENG-017 |
| M-ENG-082 | "Required fields" table | Fields required before `ready` | value | keep | README table (meanings); list in `docs-check.toml` `[specs]` | ENG | living-docs-engineering-workflow, docs-check-tooling | CW item 17 cites; check E enforces | ENG-017 |
| M-ENG-083 | "Required fields" — (new) | Docs impact field | requirement | move | CW item 18; README field row | ENG | living-docs-engineering-workflow | `docs impact field and Docs unchanged line` PENDING heading | ENG-018 |
| M-ENG-084 | "Notes is optional" | Notes optional, encouraged | process | keep | README | — | living-docs-engineering-workflow | |  |
| M-ENG-085 | "Test naming rules" | Test name is a falsifiable claim named after behaviour | requirement | ratify | CNV item 47; README table kept as examples | ENG | living-docs-engineering-workflow | engineering ratification batch | ENG-047 |
| M-ENG-086 | "Test naming rules" | No plan steps, phases, spec filenames in names | requirement | link | `docs/engineering/conventions.md` item 49 | ENG | living-docs-engineering-workflow | Same rule as M-SYS-019 |  |
| M-ENG-087 | "Statuses" table | draft, ready, blocked, done meanings | requirement | ratify | CW item 16 | ENG | living-docs-engineering-workflow | engineering ratification batch | ENG-016 |
| M-ENG-088 | "Statuses" — (missing) | `hold` status used by 4 specs, undefined | stale | ratify | CW item 16; README row added | ENG | living-docs-engineering-workflow | finding F-H9 | ENG-016 |
| M-ENG-089 | "Statuses" — done | Move done specs to specs/done; never delete | requirement | ratify | CW item 16; archive frozen CW item 36 | ENG | living-docs-engineering-workflow | `archive policy for specs/done` PENDING heading for frozen part | ENG-016 ENG-036 |
| M-ENG-090 | "Statuses" ¶ | Draft → ready in scoping; scoping ≠ implementation | requirement | ratify | CW item 17 | ENG | living-docs-engineering-workflow | dup of M-ENG-007 | ENG-017 |
| M-ENG-091 | (new) | Decision citation rule: heading, register number only in parentheses | requirement | move | CW item 26; README section "Citing decisions" | ENG | living-docs-engineering-workflow | engineering ratification batch; check D | ENG-026 |
| M-ENG-092 | (new) | Handoff section when a session stops early | requirement | move | CW item 28; README section "Handoff" | ENG | living-docs-engineering-workflow | engineering ratification batch | ENG-028 |
| M-ENG-093 | "Template" | Copy `_template.md` | process | keep | README | — | living-docs-engineering-workflow | |  |

### `specs/_template.md`

| Row | Source (path:line or §) | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-ENG-094 | `specs/_template.md:3-5` | Status/Blocked by/Branch header fields | process | keep | template (+ Docs impact line) | — | living-docs-engineering-workflow | |  |
| M-ENG-095 | `_template.md` Constraints | "Which architecture invariants from root CLAUDE.md apply" | stale | keep | template, reworded to INV/owner IDs | — | living-docs-engineering-workflow | |  |
| M-ENG-096 | `_template.md` Required tests | Write first; confirm each fails for the right reason | process | link | VER item 1 | — | living-docs-engineering-workflow | |  |
| M-ENG-097 | (new) | Optional `## Handoff` with seven lines | process | keep | template | — | living-docs-engineering-workflow | CW item 28 owns the rule |  |

### `.github/` (workflows and scripts as authorities)

| Row | Source (path:line or §) | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-ENG-098 | `.github/workflows/commit-identity.yml:3-7` | Identity check on PRs into main, develop | value | keep | workflow (authority); AG hard rule names it | — | docs-check-tooling | `docs-check-tooling` adds `feature/living-docs-integration` |  |
| M-ENG-099 | `.github/scripts/check_commit_identity.sh:9-19` | Rejects Claude author/committer, Co-Authored-By/Claude-Session trailers | value | keep | script (authority); tested by `test_commit_identity_check.py` | — | docs-check-tooling | AG hard rule; at-risk class #18 |  |
| M-ENG-100 | `.github/workflows/java.yml:61` | `./gradlew check timezoneCheck --rerun-tasks` | value | keep | workflow; VER item 3 cites | ENG | living-docs-engineering-workflow | | ENG-003 |
| M-ENG-101 | `.github/workflows/python.yml:62` | ingestion-scraper `uv sync --all-extras` without `--locked` | status-note | keep | workflow | — | — | F-H8; no requirement today; owner may add via batch |  |
| M-ENG-102 | `.github/workflows/python.yml:85-90` | Regenerate fixture; `git diff --exit-code` contract dir | value | keep | workflow; CON cites | CON | living-docs-system-and-contracts | |  |
| M-ENG-103 | `.github/workflows/python.yml:92-121` | backtesting job: no ruff/mypy | status-note | keep | workflow | — | — | contradicts TODO notes "ruff and mypy clean" (status only) |  |
| M-ENG-104 | `python.yml`, `java.yml` env | `TESTCONTAINERS_HUB_IMAGE_NAME_PREFIX=mirror.gcr.io/`; Ryuk off | value | keep | workflow; VER item 14 | ENG | living-docs-engineering-workflow | trap text: `living-docs-system-and-contracts` known traps row | ENG-014 |
| M-ENG-105 | all workflows `runs-on` | `ubuntu-latest` GitHub-hosted | value | keep | workflow; VER item 13 | ENG | living-docs-engineering-workflow | | ENG-013 |
| M-ENG-106 | `.github/workflows/dashboard.yml:1-20` | path filter `services/dashboard/**` | value | keep | workflow | — | — | DSH owns what it checks |  |
| M-ENG-107 | (new) `docs.yml` | Docs checker, report-only until cutover | value | keep | workflow; VER item 15 | ENG | docs-check-tooling | | ENG-015 |
| M-ENG-108 | (new) `pull_request_template.md` | PR record sections; no footer | process | keep | template; CW item 37 | ENG | living-docs-engineering-workflow | | ENG-037 |
| M-ENG-109 | `.gitattributes` | `merge=union` for DECISIONS.md, TODO.md | value | keep | file; CW item 32 cites | ENG | living-docs-engineering-workflow | | ENG-032 |

### the at-risk classes at-risk class #18 (ENG share)

| Row | Source (path:line or §) | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-ENG-110 | at-risk class #18 | No hand-run setup scripts | requirement | link | OPS topology | OPS | living-docs-operations | see M-ENG-056 |  |
| M-ENG-111 | at-risk class #18 | Stack-machine-only work in a spec | process | keep | AG | — | agent-instruction-hierarchy | see M-ENG-055 |  |
| M-ENG-112 | at-risk class #18 | Commit identity (CI check) | process | keep | AG + `commit-identity.yml`; CW links | — | agent-instruction-hierarchy | see M-ENG-050 |  |
| M-ENG-113 | at-risk class #18 | Never `down -v` as a fix | requirement | link | OPS topology; README command | OPS | living-docs-operations, legacy-docs-retirement | test-guarded |  |
| M-ENG-114 | at-risk class #18 | Flyway comments frozen | requirement | link | HUB storage | HUB | living-docs-core-hub | see M-ENG-031 |  |
| M-ENG-115 | at-risk class #18 | Operational traps (Fernet, bcrypt, Grafana `$$`, Ollama, mirror, LocalStack) | trap | link | owner docs' Known traps | — | — | covered by trap rows M-OPS-210..219 and the system known-traps rows |  |

### Other process sources (not in the assigned list, found while reading)

| Row | Source (path:line or §) | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-ENG-116 | `DECISIONS.md:3` | Append-only; never edit or delete an entry | process | move | CW item 33 | ENG | living-docs-engineering-workflow | engineering ratification batch | ENG-033 |
| M-ENG-117 | `DECISIONS.md:9-15,17` | Entry format and `BLOCKED` = stop and ask | process | keep | DECISIONS.md header; CW item 33 links | ENG | living-docs-engineering-workflow | | ENG-033 |
| M-ENG-118 | `VERSIONS.md:3` | No floating tags, latest, `>=`; resolve at install, write back | requirement | ratify | CNV item 48 | ENG | living-docs-engineering-workflow | values stay in VERSIONS.md | ENG-048 |
| M-ENG-119 | `VERSIONS.md` "Version-sensitive claims" | Re-verify claims when dependent code is touched; record in DECISIONS | requirement | ratify | CNV item 48 | ENG | living-docs-engineering-workflow | table stays in VERSIONS.md | ENG-048 |
| M-ENG-120 | `TODO.md:3-7` | Session start: first ready spec; spec index role | process | ratify | CW item 34; AG | ENG | living-docs-engineering-workflow | session-log part: FLAG `TODO session log kept after the merge-flow choice dropped it` | ENG-034 |
| M-ENG-121 | design §8.5 | Conversion provenance, ratification batch | requirement | ratify | CW item 27 | ENG | living-docs-engineering-workflow | new rule; engineering ratification batch | ENG-027 |
| M-ENG-122 | design §9.1–9.2 | Conflict precedence; docs are not proof | requirement | ratify | CW items 23–25; VER item 12 | ENG | living-docs-engineering-workflow | engineering ratification batch | ENG-012 ENG-023 ENG-024 ENG-025 |
| M-ENG-123 | design §5.2 | ID scheme, retirement, no reuse, collisions | requirement | ratify | CW items 21–22 | ENG | living-docs-engineering-workflow | engineering ratification batch | ENG-021 ENG-022 |
| M-ENG-124 | design §3, §7.2 | Content by kind; one owner per fact | requirement | ratify | CNV items 40–42 | ENG | living-docs-engineering-workflow | engineering ratification batch | ENG-040 ENG-041 ENG-042 |
| M-ENG-125 | design §10.2 | Semantic review recorded in PR; Last reviewed bump rule | requirement | ratify | CW items 37–39 | ENG | living-docs-engineering-workflow | engineering ratification batch | ENG-037 ENG-038 ENG-039 |

### `DECISIONS.md` CHOICE headings about process, CI or git

Classification for the cutover's decisions table (`Heading | Classification | IDs`). IDs are filled when `living-docs-engineering-workflow` allocates them.

| Row | Source (path:line or §) | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-ENG-126 | DECISIONS.md:21 `## 2026-08-15 — Step 0.0 — CHOICE` | Log initialized; versions pinned | history | keep | — | — | — | **history** |  |
| M-ENG-127 | DECISIONS.md:320 `## 2026-09-19 — CI/CD pipeline — CHOICE — GitHub-hosted runners` | CI uses GitHub-hosted ubuntu-latest | rationale | move | VER item 13 Source | ENG | living-docs-engineering-workflow | **binding** | ENG-013 |
| M-ENG-128 | DECISIONS.md:438 `## 2026-09-19 — Dashboard — CHOICE — Node 22 LTS (Phase 5 resolution)` | Node 22 pinned | history | keep | — | — | — | **history**; superseded by :969 |  |
| M-ENG-129 | DECISIONS.md:529 `## 2026-10-07 — Market simulation — CHOICE — 11 tests, not 10; \`scripts/fetch_prices.py\`` | Test added beyond spec list | history | keep | — | — | — | **history** (process precedent only) |  |
| M-ENG-130 | DECISIONS.md:819 `## 2026-10-09 — Guideline setup — CHOICE — merge flow, merge bar and shared-log conflicts written into the repo` | Merge flow, merge bar, union driver, identity check, cloud limits | rationale | move | VER items 10–11, CW items 30–32 Source | ENG | living-docs-engineering-workflow | **binding**; its "session log dropped" clause is not practised → FLAG | ENG-010 ENG-011 ENG-030 ENG-031 ENG-032 |
| M-ENG-131 | DECISIONS.md:852 `## 2026-10-09 — CI — CHOICE — container images off anonymous Docker Hub` | Images off anonymous Docker Hub; registry mirror | rationale | keep | history (rationale in VER item 14 cites the superseding CHOICE) | — | living-docs-engineering-workflow | **history** (mechanism superseded by :974; the goal is carried by :974) |  |
| M-ENG-132 | DECISIONS.md:857 `## 2026-10-09 — CI — CHOICE — remaining test images through mirror.gcr.io` | LocalStack via mirror; Java prefix env | rationale | keep | history (rationale in VER item 14 cites the superseding CHOICE) | — | living-docs-engineering-workflow | **history** (superseded by :974) |  |
| M-ENG-133 | DECISIONS.md:896 `## 2026-10-09 — Pre-launch spec audit — CHOICE — gaps closed in the spec index` | Specs added, statuses set | history | keep | — | — | — | **history** (index state) |  |
| M-ENG-134 | DECISIONS.md:964 `## 2026-10-10 — Single-source cleanup — CHOICE — one version of each pre-rollout artifact` | One version of each artifact; bare `${VAR}` in compose | rationale | link | OPS (compose rule), EXT (prompt v1), CON (schema 1.0) | — | domain specs | **binding** for the domain rules it fixes; not ENG |  |
| M-ENG-135 | DECISIONS.md:969 `## 2026-10-09 — Dashboard — CHOICE — Node 24 LTS, actions on Node 24` | Node 24; every action on its Node 24 major | value | keep | VERSIONS.md, workflows (values) | — | — | **history** (values live in the authorities) |  |
| M-ENG-136 | DECISIONS.md:974 `## 2026-10-09 — CI — CHOICE — one prefix for every test image` | One Testcontainers prefix in both container jobs | rationale | move | VER item 14 Source | ENG | living-docs-engineering-workflow | **binding** | ENG-014 |
| M-ENG-137 | DECISIONS.md:1100 `## 2026-10-10 — Consolidated code, strategy and BV audit — CHOICE — what becomes specs, what does not` | Audit triage into specs | history | keep | — | — | — | **history** for ENG (domain items owned by research/core-hub fragments) |  |

### File-level roles

| Source file | Final role | Spec |
|---|---|---|
| `CLAUDE.md` (root) | `@AGENTS.md` pointer; process text split to AG (hard rules) and `docs/engineering/*` | `agent-instruction-hierarchy` (`living-docs-engineering-workflow` writes ENG) |
| `docs/requirements.md` §13–§14 | § index rows → ENG/CON/INV IDs | `legacy-docs-retirement` (`living-docs-engineering-workflow` writes ENG) |
| `specs/README.md` | spec-format guide citing ENG IDs; field meanings; hold, Docs impact, citing decisions, handoff | `living-docs-engineering-workflow` |
| `specs/_template.md` | template with Docs impact and optional Handoff | `living-docs-engineering-workflow` |
| `.github/workflows/*.yml`, `.github/scripts/check_commit_identity.sh` | machine authority for CI gates; explained by VER | `docs-check-tooling` (docs.yml, identity branch), `living-docs-engineering-workflow` (docs) |
| `.github/pull_request_template.md` | new; PR record | `living-docs-engineering-workflow` |
| `.gitattributes` | machine authority (union driver) | — |
| `DECISIONS.md` header | keeps its own format; CW links | `living-docs-engineering-workflow` |
| `tools/docs_check/`, `docs-check.toml` | new; checker and its config (ownership map, namespaces, frozen paths) | `docs-check-tooling` |
| `docs/engineering/{verification,change-workflow,conventions}.md` | new; ENG owner docs | `living-docs-engineering-workflow` |

Row counts by class (137 rows): process 50 · requirement 47 · value 12 · rationale 8 · stale 6 · history 5 · command 3 · status-note 3 · invariant 1 · contract 1 · trap 1. DECISIONS classification: binding 3 for ENG (:320, :819, :974) + 1 binding for other domains (:964); history 8.


## System, invariants and contracts (INV, SYS, CON) and all agent files


Written against `develop` @ `e51f742`. Sources read at `/home/claude/auspex-baseline`.

**Spec column legend:** `system` = `living-docs-system-and-contracts` · `agents` = `agent-instruction-hierarchy` · `ingestion` = `living-docs-ingestion` · `core-hub` = `living-docs-core-hub` · `research` = `living-docs-research` · `strategy` = `living-docs-strategy-and-dashboard` · `operations` = `living-docs-operations` · `engineering` = `living-docs-engineering-workflow` · `legacy` = `legacy-docs-retirement` · `cutover` = `living-docs-cutover`.

**Target column:** a `docs/` path plus, for INV, the fixed ID; for SYS and CON, the planned position in `living-docs-system-and-contracts` ("CON #5"). Numbers are assigned when the file is written; the spec fills them in here. `AGENTS.md` targets carry no ID (agent workflow, no requirement). `→`living-docs-research/living-docs-strategy-and-dashboard`` marks research-only items (still listed here).

**Decision column:** `DECISIONS.md` headings, shortened. `PENDING X` = `## 2026-10-15 — Living docs — PENDING — X`; the docs cite the matching `CHOICE` once answered. `batch` = `## <date> — Living docs — PENDING — system ratification batch`. `FLAG-INV` = `## <date> — Living docs — FLAG — invariant conflicts found while writing the system docs`.

Row prefixes: `M-INV` invariant rows, `M-CON` contract rows, `M-SYS` everything else in this fragment (system facts, agent-workflow content and traps routed to other domains).

---

### 1. `CLAUDE.md` (root)

| Row | Source (path:line or §) | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-SYS-001 | `CLAUDE.md:3` | "Auto-loaded every session" | status-note | delete | — | — | agent-instruction-hierarchy | Loader fact; replaced by `@AGENTS.md` |  |
| M-SYS-002 | `CLAUDE.md:5-9` | `@TODO.md`, `@VERSIONS.md` imported; do not re-read them | process | retire | `AGENTS.md` (Where things are, plain paths) | — | agent-instruction-hierarchy | PENDING `agent instruction files` |  |
| M-SYS-003 | `CLAUDE.md:10` | Current spec in `specs/`, done in `specs/done/`; read spec in full | process | move | `AGENTS.md` Session start | — | agent-instruction-hierarchy | |  |
| M-SYS-004 | `CLAUDE.md:11` | Read requirements sections the spec cites | process | retire | `AGENTS.md` Session start (read Docs impact owners) | — | agent-instruction-hierarchy | requirements.md becomes an index (PENDING Fate of `docs/requirements.md`) |  |
| M-SYS-005 | `CLAUDE.md:12` | Read PREREQUISITES when blocked on credential or decision | process | move | `AGENTS.md` Where things are | — | agent-instruction-hierarchy | |  |
| M-SYS-006 | `CLAUDE.md:13` | Read DECISIONS before flagging; append when you flag | process | move | `AGENTS.md` Where things are | — | agent-instruction-hierarchy | |  |
| M-SYS-007 | `CLAUDE.md:14` | SETUP holds only manual steps; new step only if unautomatable | process | move | `AGENTS.md` Hard rules (where work can run) | — | agent-instruction-hierarchy | Also OPS topology (startup data) |  |
| M-SYS-008 | `CLAUDE.md:16` | Assigned spec is the work, else first ready; update as you go | process | move | `AGENTS.md` Session start | — | agent-instruction-hierarchy | Conflicts with `TODO.md:5`; agents edits that line |  |
| M-SYS-009 | `CLAUDE.md:19` | Name rationale: no single source is evidence, convergence is | rationale | move | `docs/system/overview.md` Rationale | SYS | living-docs-system-and-contracts | | docs/system/overview.md#rationale |
| M-SYS-010 | `CLAUDE.md:18,21-29` | Naming identifiers are fixed; do not vary | requirement | ratify | `docs/system/overview.md` (SYS #2) | SYS | living-docs-system-and-contracts | batch | SYS-002 |
| M-SYS-011 | `CLAUDE.md:23` | Compose project `auspex` | value | link | overview naming table → `.env.example` `COMPOSE_PROJECT_NAME` | SYS | living-docs-system-and-contracts | Value not restated |  |
| M-SYS-012 | `CLAUDE.md:24` | Kafka topic names | value | link | overview naming table → `docker/topics.yaml` | SYS | living-docs-system-and-contracts | N5: not restated |  |
| M-SYS-013 | `CLAUDE.md:25` | Java root package | value | link | overview naming table → `services/core-hub/src/main/java/dev/auspex/corehub/` | SYS | living-docs-system-and-contracts | |  |
| M-SYS-014 | `CLAUDE.md:26` | Python import packages | value | link | overview naming table → each `pyproject.toml`, `src/` package dir | SYS | living-docs-system-and-contracts | |  |
| M-SYS-015 | `CLAUDE.md:27` | Three MinIO buckets and what each holds | value | link | overview naming table → `.env.example` `MINIO_BUCKET`, compose `minio-init`, `BACKUP_BUCKETS` | SYS | living-docs-system-and-contracts | Roles kept, names linked; finding #8 (SETUP/VERSIONS list 2) is legacy's |  |
| M-SYS-016 | `CLAUDE.md:28` | Postgres databases `auspex`, `airflow` | value | link | overview naming table → `.env.example` `POSTGRES_DB`, `docker/postgres-init/` | SYS | living-docs-system-and-contracts | |  |
| M-SYS-017 | `CLAUDE.md:29` | Roles `auspex_app`, `airflow` | value | link | overview naming table → `.env.example` `POSTGRES_USER`, `docker/airflow-db-role/` | SYS | living-docs-system-and-contracts | |  |
| M-SYS-018 | `CLAUDE.md:31` | Service directories descriptive, never themed | requirement | ratify | `docs/system/overview.md` (SYS #1) | SYS | living-docs-system-and-contracts | batch | SYS-001 |
| M-SYS-019 | `CLAUDE.md:33` | No plan-step references in names, tests, branches, commits | requirement | move | `docs/engineering/conventions.md` item 49; one-line hard rule in `AGENTS.md` | ENG | living-docs-engineering-workflow | engineering ratification batch (source is CLAUDE.md only) | ENG-049 |
| M-SYS-020 | `CLAUDE.md:35-36` | "What this is": see README | status-note | link | `AGENTS.md` Where things are | — | agent-instruction-hierarchy | |  |
| M-SYS-021 | `CLAUDE.md:39-43` | Session start steps 1–5 | process | move | `AGENTS.md` Session start | — | agent-instruction-hierarchy | |  |
| M-SYS-022 | `CLAUDE.md:44` | Done flow: mark done, move, TODO row, commit, PR | process | move | `docs/engineering/change-workflow.md` (lifecycle); `AGENTS.md` names it | ENG | living-docs-engineering-workflow | | ENG-016 |
| M-SYS-023 | `CLAUDE.md:47` | No legacy system; Flyway scripts create schema on empty DB | requirement | ratify | `docs/system/overview.md` (SYS #3) | SYS | living-docs-system-and-contracts | batch | SYS-003 |
| M-SYS-024 | `CLAUDE.md:50` | Rule that matters most: test can only pass by violating → stop, flag, ask | process | move | `AGENTS.md` Session start (3) | — | agent-instruction-hierarchy | INV-15 refers to it in plain text |  |
| M-SYS-025 | `CLAUDE.md:52` | `test_dag_task_only_invokes_fetch_since` cautionary story | rationale | move | `docs/engineering/verification.md` Rationale | ENG | living-docs-engineering-workflow | | docs/engineering/verification.md#rationale |
| M-SYS-026 | `CLAUDE.md:54` | Never violate an invariant; stop and flag | process | move | `AGENTS.md` Session start (4) | — | agent-instruction-hierarchy | |  |
| M-INV-001 | `CLAUDE.md:55` | Scraper writes only to MinIO and Kafka | invariant | move | `docs/system/invariants.md#INV-1` | INV | living-docs-system-and-contracts | Scope line: Airflow Variables/local state are writes; read-only note (`sample_corroborations.py`) in batch | INV-1 |
| M-INV-002 | `CLAUDE.md:56` | core-hub sole writer to application DB and Neo4j | invariant | move | `#INV-2` | INV | living-docs-system-and-contracts | Restore exception: PENDING `restore exception to invariant 2` | INV-2 |
| M-INV-003 | `CLAUDE.md:57` | DAG calls `/ingest/<source_type>`; no logic in DAGs or `fetch_since` | invariant | move | `#INV-3` | INV | living-docs-system-and-contracts | | INV-3 |
| M-INV-004 | `CLAUDE.md:58` | New source = connector + `sources.yaml` entry; no source branching | invariant | move | `#INV-4` | INV | living-docs-system-and-contracts | CT.gov exception placed here (batch); snapshot scope note | INV-4 |
| M-INV-005 | `CLAUDE.md:59` | All corroboration behind `CorroborationService` | invariant | move | `#INV-5` | INV | living-docs-system-and-contracts | | INV-5 |
| M-INV-006 | `CLAUDE.md:60` | No credentials/URLs/ports in source; API keys are Airflow Connections | invariant | divergent | `#INV-6` (amended) | INV | living-docs-system-and-contracts | PENDING `invariant 6 wording`; defaults in source → FLAG-INV | INV-6 |
| M-INV-007 | `CLAUDE.md:61` | Model and record identical; snake_case; fixture generated | invariant | move | `#INV-7` | INV | living-docs-system-and-contracts | Raw and corroborated events divergent in CON | INV-7 |
| M-INV-008 | `CLAUDE.md:62` | Synchronous Python; no `async`, no `aiokafka` | invariant | move | `#INV-8` | INV | living-docs-system-and-contracts | | INV-8 |
| M-INV-009 | `CLAUDE.md:63` | UTC everywhere, including MinIO keys | invariant | move | `#INV-9` | INV | living-docs-system-and-contracts | | INV-9 |
| M-INV-010 | `CLAUDE.md:64` | Idempotent writes on each path's declared natural key | invariant | move | `#INV-10` | INV | living-docs-system-and-contracts | Keys: CON #21–27 | INV-10 |
| M-INV-011 | `CLAUDE.md:65` | Nothing dies silently: DLT with headers, never block a partition | invariant | divergent | `#INV-11` | INV | living-docs-system-and-contracts | Strategy runtime skip-and-count, no DLT → FLAG-INV | INV-11 |
| M-INV-012 | `CLAUDE.md:66` | Parameterized queries; ArchUnit + injection tests | invariant | move | `#INV-12` | INV | living-docs-system-and-contracts | ArchUnit covers some packages only (status untested, partial) | INV-12 |
| M-INV-013 | `CLAUDE.md:67` | MinIO archive unconditional, before any other side effect | invariant | move | `#INV-13` | INV | living-docs-system-and-contracts | | INV-13 |
| M-INV-014 | `CLAUDE.md:68` | `event_id` is document identity; never varies | invariant | move | `#INV-14` | INV | living-docs-system-and-contracts | | INV-14 |
| M-INV-015 | `CLAUDE.md:69` | Test-first, subject to the rule above | invariant | move | `#INV-15` | INV | living-docs-system-and-contracts | "Rule above" → `AGENTS.md` (plain text) | INV-15 |
| M-SYS-027 | `CLAUDE.md:75-78` | Stack up (infra, app), down, down -v commands | command | keep | `README.md` (stack-command owner) | — | legacy-docs-retirement | down -v line must keep "destroys all data" |  |
| M-SYS-028 | `CLAUDE.md:79-83,97` | Scraper install, unit, one file, full, lint, regenerate fixture | command | move | `services/ingestion-scraper/AGENTS.md` | — | agent-instruction-hierarchy | |  |
| M-SYS-029 | `CLAUDE.md:84-89` | Gradle test, integrationTest, check, one class, timezoneCheck, rerun | command | move | `services/core-hub/AGENTS.md` | — | agent-instruction-hierarchy | |  |
| M-SYS-030 | `CLAUDE.md:90-91` | Backtesting unit and integration | command | move | `services/backtesting/AGENTS.md` | — | agent-instruction-hierarchy | |  |
| M-SYS-031 | `CLAUDE.md:92` | Backup lint, types, unit | command | move | `services/backup/AGENTS.md` | — | agent-instruction-hierarchy | |  |
| M-SYS-032 | `CLAUDE.md:93,96` | Restore command; smoke test | command | keep | `README.md` | — | legacy-docs-retirement | |  |
| M-SYS-033 | `CLAUDE.md:94-95` | Dashboard lint/types/tests; build + bundle check | command | move | `services/dashboard/AGENTS.md` | — | agent-instruction-hierarchy | Strategy and kill-switch rows missing here (G9): add from `README.md:60-61` to strategy `AGENTS.md` |  |
| M-SYS-034 | `CLAUDE.md:99` | Zero tests executed is a failure | process | move | `AGENTS.md` Hard rules | — | agent-instruction-hierarchy | |  |
| M-SYS-035 | `CLAUDE.md:99` | `failOnNoDiscoveredTests = true`; pytest `--strict-markers` | requirement | move | `docs/engineering/verification.md` | ENG | living-docs-engineering-workflow | `build.gradle.kts:95,102` | ENG-003 |
| M-SYS-036 | `CLAUDE.md:101` | Gradle `UP-TO-DATE` is not a pass; use `--rerun-tasks` | process | move | `AGENTS.md` Hard rules | — | agent-instruction-hierarchy | Duplicate at `services/core-hub/CLAUDE.md:45` deleted |  |
| M-SYS-037 | `CLAUDE.md:103-114` | TDD loop steps; right-reason red; container suite at completion | process | move | `docs/engineering/verification.md` | ENG | living-docs-engineering-workflow | | ENG-001 ENG-002 |
| M-SYS-038 | `CLAUDE.md:116-135` | Doc-maintenance table; "intentional duplication is fine" | stale | retire | replaced by `docs/engineering/conventions.md` item 40 ("Doc ownership") | — | living-docs-engineering-workflow | Retired, not moved; same source as M-ENG-023 |  |
| M-SYS-039 | `CLAUDE.md:137` | Scaffolding exemption from test-first | invariant | move | INV-15 exception in `docs/system/invariants.md` | INV | living-docs-system-and-contracts | An exception narrows INV-15, so it lives under it; "pom.xml" is stale (Gradle). Same source as M-ENG-025 | INV-15 |
| M-SYS-040 | `CLAUDE.md:140-144` | Comment rules: intent only, no narration, contracts, stale worse | process | move | `docs/engineering/conventions.md` | ENG | living-docs-engineering-workflow | | ENG-043 ENG-044 ENG-045 ENG-046 |
| M-SYS-041 | `CLAUDE.md:145` | Flyway migrations frozen; don't edit applied comments | requirement | move | `docs/core-hub/storage.md` | HUB | living-docs-core-hub | | HUB-020 |
| M-SYS-042 | `CLAUDE.md:148-152` | Test file locations and markers per service | process | move | Layout rows of scraper and core-hub `AGENTS.md`; `docs/engineering/verification.md` | ENG | agent-instruction-hierarchy, living-docs-engineering-workflow | | ENG-003 |
| M-SYS-043 | `CLAUDE.md:154` | `CorroborationServiceContractTest` abstract; extend unmodified | requirement | move | `docs/core-hub/corroboration.md` | COR | living-docs-core-hub | Nested file keeps the ID only | COR-001 |
| M-SYS-044 | `CLAUDE.md:158-163` | Git Flow branches | process | move | `docs/engineering/change-workflow.md` | ENG | living-docs-engineering-workflow | | ENG-029 |
| M-SYS-045 | `CLAUDE.md:165-169` | Rebase, resolve in rebase, ff-only, no `--no-ff` | process | move | `docs/engineering/change-workflow.md` | ENG | living-docs-engineering-workflow | | ENG-030 |
| M-SYS-046 | `CLAUDE.md:172` | Never push to `develop` or `main` directly | process | move | `AGENTS.md` Hard rules | — | agent-instruction-hierarchy | `## 2026-10-09 — Guideline setup — CHOICE — merge flow, …` |  |
| M-SYS-047 | `CLAUDE.md:174-179` | Merge only on owner's word; local rebase + ff recipe | process | move | Hard rule in `AGENTS.md`; recipe in `docs/engineering/change-workflow.md` | ENG | agent-instruction-hierarchy, living-docs-engineering-workflow | same CHOICE | ENG-030 |
| M-SYS-048 | `CLAUDE.md:180` | `main` only via release branch on request | process | move | `docs/engineering/change-workflow.md` | ENG | living-docs-engineering-workflow | | ENG-031 |
| M-SYS-049 | `CLAUDE.md:182-186` | Ready to merge: tests per behaviour, mutation check, PR lists them | process | move | `docs/engineering/verification.md` | ENG | living-docs-engineering-workflow | | ENG-010 ENG-011 |
| M-SYS-050 | `CLAUDE.md:188` | DECISIONS/TODO union merge driver; check order after rebase | process | move | `docs/engineering/change-workflow.md` | ENG | living-docs-engineering-workflow | | ENG-032 |
| M-SYS-051 | `CLAUDE.md:191` | Commit only when the spec's tests pass | process | move | `docs/engineering/change-workflow.md` | ENG | living-docs-engineering-workflow | | ENG-035 |
| M-SYS-052 | `CLAUDE.md:192` | Never commit `.env`, `target/`, `.venv/`, `__pycache__/`, volumes | process | move | `AGENTS.md` Hard rules | — | agent-instruction-hierarchy | |  |
| M-SYS-053 | `CLAUDE.md:193` | Commits carry the requester's identity; no Claude author or trailers | process | move | `AGENTS.md` Hard rules | — | agent-instruction-hierarchy | Enforced by `check_commit_identity.sh` |  |
| M-SYS-054 | `CLAUDE.md:194` | No Claude footers or session links on GitHub | process | move | `AGENTS.md` Hard rules | — | agent-instruction-hierarchy | |  |
| M-SYS-055 | `CLAUDE.md:195` | Commit subject only, lowercase, `subject: detail1, detail2` | process | move | `AGENTS.md` Hard rules | — | agent-instruction-hierarchy | |  |
| M-SYS-056 | `CLAUDE.md:198` | Cloud sessions: no Docker/sec.gov/Yahoo; container tests in CI | process | move | `AGENTS.md` Hard rules (owner) | — | agent-instruction-hierarchy | ENG verification links |  |
| M-SYS-057 | `CLAUDE.md:199` | Mac-only work goes into a spec the owner runs there | process | move | `AGENTS.md` Hard rules | — | agent-instruction-hierarchy | Stale path `specs/first-run-on-stack-machine.md` still valid |  |
| M-SYS-058 | `CLAUDE.md:200` | No hand-run setup/data scripts; one-shot or DAG calling API | requirement | move | `docs/operations/topology.md`; one-line hard rule in `AGENTS.md` | OPS | living-docs-operations, agent-instruction-hierarchy | `## 2026-10-07 — Startup data — CHOICE — data fills itself on up; prices refresh daily` | OPS-009 |
| M-SYS-059 | `CLAUDE.md:203` | `ErrorHandlingDeserializer` mandatory | trap | move | `docs/core-hub/consumption.md` Known traps | HUB | living-docs-core-hub | | docs/core-hub/consumption.md#known-traps |
| M-SYS-060 | `CLAUDE.md:204` | DLPR default `.DLT` and same partition; resolver returns -1 | trap | move | `docs/system/contracts.md` Known traps (CON #36–37) | CON | living-docs-system-and-contracts | Drop "re-verify": `## 2026-08-16 — Step 1.3 — VERIFIED — DeadLetterPublishingRecoverer with Spring Kafka 4.1` | docs/system/contracts.md#known-traps |
| M-SYS-061 | `CLAUDE.md:205` | `produce()` async: flush, check delivery reports | trap | move | `docs/ingestion/pipeline.md` Known traps | ING | living-docs-ingestion | | docs/ingestion/pipeline.md#known-traps |
| M-SYS-062 | `CLAUDE.md:206` | `MERGE {ticker: null}` matches all; MERGE Company on name | trap | move | `docs/core-hub/storage.md` Known traps | HUB | living-docs-core-hub | | docs/core-hub/storage.md#known-traps |
| M-SYS-063 | `CLAUDE.md:207` | Neo4j no decimal; NUMERIC(4,3); double via converter | trap | move | `docs/core-hub/storage.md` Known traps | HUB | living-docs-core-hub | C12: "converter" is an inline `.doubleValue()` | docs/core-hub/storage.md#known-traps |
| M-SYS-064 | `CLAUDE.md:208` | Primitive double cannot be null; BigDecimal + `@NotNull` | trap | move | `docs/system/contracts.md` Known traps (CON #12) | CON | living-docs-system-and-contracts | | docs/system/contracts.md#known-traps |
| M-SYS-065 | `CLAUDE.md:209` | `FAIL_ON_UNKNOWN_PROPERTIES=false` on consumer | trap | move | `docs/system/contracts.md` Known traps (CON #30) | CON | living-docs-system-and-contracts | Illustrative core-hub AGENTS lists it as HUB; this fragment owns it under CON | docs/system/contracts.md#known-traps |
| M-SYS-066 | `CLAUDE.md:210` | Patents: filed date is not disclosure; use pre-grant publication | trap | move | `docs/ingestion/connectors.md` Known traps | ING | living-docs-ingestion | | docs/ingestion/connectors.md#known-traps |
| M-SYS-067 | `CLAUDE.md:211` | Trials: first-submitted date private; post date public | trap | move | `docs/ingestion/connectors.md` Known traps | ING | living-docs-ingestion | | docs/ingestion/connectors.md#known-traps |
| M-SYS-068 | `CLAUDE.md:212` | SEC 10 req/s per IP, User-Agent, filing index, ciks[0], XBRL names | trap | move | `docs/ingestion/connectors.md` Known traps; aggregate budget `docs/operations/topology.md` | ING | living-docs-ingestion, living-docs-operations | Stale path `specs/edgar-efts-fixture-alignment.md` → `specs/done/…` (finding #7) | docs/ingestion/connectors.md#known-traps |
| M-SYS-069 | `CLAUDE.md:213` | openFDA has no designations endpoint | trap | move | `docs/ingestion/connectors.md` Known traps | ING | living-docs-ingestion | `fda_approval source`: approved, `divergent` (M-ING-047, no `sources.yaml` entry yet); the trap stays current | docs/ingestion/connectors.md#known-traps |
| M-SYS-070 | `CLAUDE.md:214` | PatentsView superseded, Lens.org commercial; use EPO OPS | trap | move | `docs/ingestion/connectors.md` Known traps | ING | living-docs-ingestion | | docs/ingestion/connectors.md#known-traps |
| M-SYS-071 | `CLAUDE.md:215` | Docker Hub rate limits; test images via `mirror.gcr.io` prefix | trap | move | `docs/engineering/verification.md` Known traps | ENG | living-docs-engineering-workflow | `## 2026-10-09 — CI — CHOICE — …` (3 entries) | docs/engineering/verification.md#known-traps |
| M-SYS-072 | `CLAUDE.md:216` | Airflow 3 `schedule`; Task SDK proxies Variables/Connections | trap | move | `docs/operations/orchestration.md` Known traps | OPS | living-docs-operations | | docs/operations/orchestration.md#known-traps |
| M-SYS-073 | `CLAUDE.md:217` | Scraper is one gunicorn process (threads), metrics per process | trap | move | `docs/operations/topology.md` (requirement + trap) | OPS | living-docs-operations | | OPS-021 docs/operations/topology.md#known-traps |
| M-SYS-074 | `CLAUDE.md:218` | `make_metrics()` cached per registry; DuplicateTimeseries | trap | link | `docs/operations/observability.md` Known traps (M-OPS-212) | — | living-docs-ingestion | |  |
| M-SYS-075 | `CLAUDE.md:219` | Grafana expands `$VAR` in alerting files; write `$$` | trap | move | `docs/operations/observability.md` Known traps | OPS | living-docs-operations | `## 2026-10-09 — Infrastructure observability — VERIFIED — Grafana expands …` | docs/operations/observability.md#known-traps |
| M-SYS-076 | `CLAUDE.md:220` | LocalStack `2026.x` needs licence; pin 4.9.2 | trap | move | `docs/engineering/verification.md` Known traps | ENG | living-docs-engineering-workflow | Pin value in `VERSIONS.md` | docs/engineering/verification.md#known-traps |
| M-SYS-077 | `CLAUDE.md:221` | bcrypt hash `$`: single-quote in `.env`, `\$` in `.env.local` | trap | move | `docs/dashboard.md` Known traps | DSH | living-docs-strategy-and-dashboard | |  |
| M-SYS-078 | `CLAUDE.md:222` | Next 16 middleware renamed `proxy`; `next lint` gone | trap | move | `docs/dashboard.md` Known traps | DSH | living-docs-strategy-and-dashboard | |  |
| M-SYS-079 | `CLAUDE.md:223` | Airflow generates Fernet key if unset; keys from `.env` | trap | move | `docs/operations/orchestration.md` Known traps | OPS | living-docs-operations | | docs/operations/orchestration.md#known-traps |
| M-SYS-080 | `CLAUDE.md:224` | Docker Desktop has no Metal; Ollama on host | trap | link | `docs/operations/topology.md` Known traps (M-OPS-218) | — | living-docs-ingestion | Procedure stays in `docs/local-model-runbook.md` |  |
| M-SYS-081 | `CLAUDE.md:225` | Ollama `/v1` ignores `num_ctx`; set `OLLAMA_CONTEXT_LENGTH` | trap | move | `docs/ingestion/extraction.md` Known traps | EXT | living-docs-ingestion | | docs/ingestion/extraction.md#known-traps |
| M-SYS-082 | `CLAUDE.md:226` | Ollama tag re-pointing; registry pins digest, checked at startup | trap | move | `docs/ingestion/extraction.md` Known traps | EXT | living-docs-ingestion | | docs/ingestion/extraction.md#known-traps |
| M-SYS-083 | `CLAUDE.md:229-243` | File map | process | move | `AGENTS.md` Where things are | — | agent-instruction-hierarchy | |  |
| M-SYS-084 | `CLAUDE.md:246` | Tone: report only on passing run; say blocked plainly | process | move | `AGENTS.md` Tone | — | agent-instruction-hierarchy | |  |

### 2. `services/CLAUDE.md`

| Row | Source | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-SYS-085 | `services/CLAUDE.md:3` | Auto-loaded in service directories | status-note | delete | — | — | agent-instruction-hierarchy | |  |
| M-CON-001 | `services/CLAUDE.md:7-8,12` | Pydantic model generates `signal_event_v1.json` | contract | move | `docs/system/contracts.md` (CON #9) | CON | living-docs-system-and-contracts | | CON-009 |
| M-SYS-086 | `services/CLAUDE.md:10` | Regenerate fixture command | command | move | `services/ingestion-scraper/AGENTS.md` | — | agent-instruction-hierarchy | |  |
| M-CON-002 | `services/CLAUDE.md:13` | Python model changes: regenerate and commit | contract | move | `docs/system/contracts.md` (CON #32) | CON | living-docs-system-and-contracts | | CON-031 |
| M-CON-003 | `services/CLAUDE.md:15-22` | Topic table: partitions, producer, consumer | contract | move | CON #2 (roles); values → `docker/topics.yaml` | CON | living-docs-system-and-contracts | Partition numbers not copied; corroborated consumer = strategy-runtime | CON-002 |
| M-CON-004 | `services/CLAUDE.md:24` | Provisioning in `topics.yaml` | contract | move | CON #1 | CON | living-docs-system-and-contracts | | CON-001 |
| M-CON-005 | `services/CLAUDE.md:24` | DLPR publishes same partition; mismatch fails silently | stale | delete | — (CON #37 states -1) | CON | living-docs-system-and-contracts, agent-instruction-hierarchy | Wrong vs `KafkaConfig.java:187-188` (C2/G4) |  |
| M-SYS-087 | `services/CLAUDE.md:28` | Comment rule lives in root CLAUDE | status-note | link | `services/AGENTS.md` → `docs/engineering/conventions.md` | — | agent-instruction-hierarchy | |  |
| M-SYS-088 | `services/CLAUDE.md:30-35` | Per-stack comment form table | process | move | `docs/engineering/conventions.md` item 52 | ENG | living-docs-engineering-workflow | `services/AGENTS.md` keeps a one-line pointer (`agent-instruction-hierarchy`) | ENG-052 |
| M-INV-016 | `services/CLAUDE.md:39` | Scraper writes only MinIO and Kafka; "No DB access, ever" | invariant | link | `#INV-1` | INV | agent-instruction-hierarchy | Stricter than INV-1; read-only note in batch |  |
| M-INV-017 | `services/CLAUDE.md:40` | core-hub sole writer | invariant | link | `#INV-2` | INV | agent-instruction-hierarchy | |  |
| M-SYS-089 | `services/CLAUDE.md:42` | Crossing boundary is an architecture violation | process | delete | covered by `AGENTS.md` stop-and-flag | — | agent-instruction-hierarchy | Duplicate |  |

### 3. `services/core-hub/CLAUDE.md`

| Row | Source | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-SYS-090 | `services/core-hub/CLAUDE.md:3` | Auto-loaded with root | status-note | delete | — | — | agent-instruction-hierarchy | |  |
| M-SYS-091 | `services/core-hub/CLAUDE.md:7-12` | Six Gradle commands | command | move | `services/core-hub/AGENTS.md` | — | agent-instruction-hierarchy | Duplicate of root `:84-89` |  |
| M-SYS-092 | `services/core-hub/CLAUDE.md:16` | Package, topics, DB, role names | value | link | `docs/system/overview.md` naming table | SYS | agent-instruction-hierarchy | |  |
| M-SYS-093 | `services/core-hub/CLAUDE.md:19` | Kotlin DSL, committed wrapper, Gradle version | requirement | move | `docs/engineering/conventions.md`; version → `VERSIONS.md` | ENG | living-docs-engineering-workflow | requirements §1 :32 | ENG-053 |
| M-SYS-094 | `services/core-hub/CLAUDE.md:20` | Versions only in `libs.versions.toml`, matching `VERSIONS.md` | requirement | move | `docs/engineering/conventions.md` | ENG | living-docs-engineering-workflow | | ENG-053 |
| M-SYS-095 | `services/core-hub/CLAUDE.md:21` | No `io.spring.dependency-management` plugin | requirement | move | `docs/engineering/conventions.md` | ENG | living-docs-engineering-workflow | ENG batch (CLAUDE-only source) | ENG-053 |
| M-SYS-096 | `services/core-hub/CLAUDE.md:22-25` | Java toolchain pinned to 25 | requirement | move | `docs/engineering/conventions.md`; value → `VERSIONS.md` | ENG | living-docs-engineering-workflow | | ENG-053 |
| M-SYS-097 | `services/core-hub/CLAUDE.md:26` | `integrationTest` JVM Test Suite, own source set, in `check` | requirement | move | `docs/engineering/verification.md`; layout row in core-hub `AGENTS.md` | ENG | living-docs-engineering-workflow, agent-instruction-hierarchy | requirements §13 | ENG-007 |
| M-SYS-098 | `services/core-hub/CLAUDE.md:27` | `timezoneCheck` own task, non-UTC JVM | requirement | move | `docs/engineering/verification.md` | ENG | living-docs-engineering-workflow | requirements §13 | ENG-007 |
| M-INV-018 | `services/core-hub/CLAUDE.md:30` | Sole writer to DB and Neo4j | invariant | link | `#INV-2` | INV | agent-instruction-hierarchy | |  |
| M-SYS-099 | `services/core-hub/CLAUDE.md:31` | Write order Neo4j → Postgres → ack; ack-mode RECORD | requirement | move | `docs/core-hub/consumption.md` / `storage.md` | HUB | living-docs-core-hub | C5: RECORD likely not applied (HUB records divergent/untested) | HUB-014 HUB-024 |
| M-SYS-100 | `services/core-hub/CLAUDE.md:32` | Every `@Transactional` qualified; separate repository packages | requirement | move | `docs/core-hub/storage.md` | HUB | living-docs-core-hub | requirements §3.8 | HUB-026 |
| M-SYS-101 | `services/core-hub/CLAUDE.md:33` | Flyway owns schema; `ddl-auto: validate` | requirement | move | `docs/core-hub/storage.md` | HUB | living-docs-core-hub | requirements §1 :38 | HUB-019 |
| M-SYS-102 | `services/core-hub/CLAUDE.md:34` | MERGE, never CREATE, for signal and entity nodes | requirement | move | `docs/core-hub/storage.md` | HUB | living-docs-core-hub | | HUB-023 |
| M-INV-019 | `services/core-hub/CLAUDE.md:35` | No string-built queries; ArchUnit | invariant | link | `#INV-12` | INV | agent-instruction-hierarchy | |  |
| M-SYS-103 | `services/core-hub/CLAUDE.md:36` | Java records, no Lombok, constructor injection | requirement | move | `docs/engineering/conventions.md` | ENG | living-docs-engineering-workflow | requirements §1 :32 | ENG-054 |
| M-SYS-104 | `services/core-hub/CLAUDE.md:39` | Unit vs container source sets | process | move | core-hub `AGENTS.md` Layout | — | agent-instruction-hierarchy | |  |
| M-SYS-105 | `services/core-hub/CLAUDE.md:40` | Static singleton containers, one context, truncate, < 3 min | requirement | move | `docs/engineering/verification.md` | ENG | living-docs-engineering-workflow | requirements §13 | ENG-006 |
| M-SYS-106 | `services/core-hub/CLAUDE.md:41` | Contract test abstract; extend unmodified | requirement | move | `docs/core-hub/corroboration.md` | COR | living-docs-core-hub | dup of M-SYS-043 | COR-001 |
| M-SYS-107 | `services/core-hub/CLAUDE.md:42` | Awaitility, never `Thread.sleep` | requirement | move | `docs/engineering/verification.md` | ENG | living-docs-engineering-workflow | requirements §13 | ENG-005 |
| M-SYS-108 | `services/core-hub/CLAUDE.md:45` | `UP-TO-DATE` runs nothing; `--rerun-tasks` | process | delete | dup of M-SYS-036 (`AGENTS.md`) | — | agent-instruction-hierarchy | |  |
| M-SYS-109 | `services/core-hub/CLAUDE.md:46` | Gradle 9 configuration cache: fix script, don't disable | trap | move | `docs/engineering/conventions.md` Known traps | ENG | living-docs-engineering-workflow | ENG batch | docs/engineering/conventions.md#known-traps |
| M-SYS-110 | `services/core-hub/CLAUDE.md:47` | `ErrorHandlingDeserializer` mandatory | trap | delete | dup of M-SYS-059 | HUB | living-docs-core-hub | |  |
| M-CON-006 | `services/core-hub/CLAUDE.md:48` | DLT resolver lowercase `.dlt`, partition -1; re-verify | trap | move | CON Known traps (CON #36–37) | CON | living-docs-system-and-contracts | "Re-verify" stale (verified 2026-08-16) | docs/system/contracts.md#known-traps |
| M-CON-007 | `services/core-hub/CLAUDE.md:49` | `confidence_score` BigDecimal / NUMERIC(4,3) / double | trap | move | CON Known traps (wire, CON #12); storage half `docs/core-hub/storage.md` | CON | living-docs-system-and-contracts, living-docs-core-hub | | docs/system/contracts.md#known-traps |
| M-CON-008 | `services/core-hub/CLAUDE.md:50` | `FAIL_ON_UNKNOWN_PROPERTIES=false` | trap | delete | dup of M-SYS-065 | CON | living-docs-system-and-contracts | |  |
| M-SYS-111 | `services/core-hub/CLAUDE.md:51` | MERGE null ticker trap | trap | delete | dup of M-SYS-062 | HUB | living-docs-core-hub | |  |
| M-SYS-112 | `services/core-hub/CLAUDE.md:52` | Boot 4.1 / Spring Kafka 4.1 differ from 3.x tutorials | trap | move | `docs/engineering/conventions.md` Known traps | ENG | living-docs-engineering-workflow | requirements §1 :32 | docs/engineering/conventions.md#known-traps |

### 4. `services/ingestion-scraper/CLAUDE.md`

| Row | Source | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-SYS-113 | `services/ingestion-scraper/CLAUDE.md:3` | Auto-loaded with root | status-note | delete | — | — | agent-instruction-hierarchy | |  |
| M-SYS-114 | `services/ingestion-scraper/CLAUDE.md:7-11` | Five uv commands | command | move | `services/ingestion-scraper/AGENTS.md` | — | agent-instruction-hierarchy | |  |
| M-SYS-115 | `services/ingestion-scraper/CLAUDE.md:15` | Package, bucket, topics names | value | link | `docs/system/overview.md` naming table | SYS | agent-instruction-hierarchy | |  |
| M-INV-020 | `services/ingestion-scraper/CLAUDE.md:18` | Sync only; no async, await, aiokafka | invariant | link | `#INV-8` | INV | agent-instruction-hierarchy | |  |
| M-SYS-116 | `services/ingestion-scraper/CLAUDE.md:18` | `fetch_since` returns an `Iterator` | requirement | move | `docs/ingestion/connectors.md` | ING | living-docs-ingestion | requirements §6.1 | ING-001 |
| M-INV-021 | `services/ingestion-scraper/CLAUDE.md:19` | Writes MinIO, Kafka only; no Postgres, Neo4j, Variables, state files | invariant | link | `#INV-1` (scope line) | INV | living-docs-system-and-contracts, agent-instruction-hierarchy | "No Postgres, no Neo4j" read-ban relaxed by INV-1 read-only note → batch |  |
| M-INV-022 | `services/ingestion-scraper/CLAUDE.md:20` | `fetch_since()` fetches and maps only | invariant | link | `#INV-3`; detail `docs/ingestion/connectors.md` | INV | agent-instruction-hierarchy | |  |
| M-SYS-117 | `services/ingestion-scraper/CLAUDE.md:21` | Every HTTP call via `RateLimitedClient` | requirement | move | `docs/ingestion/connectors.md` | ING | living-docs-ingestion | requirements §1 :28, §6.5 | ING-005 |
| M-INV-023 | `services/ingestion-scraper/CLAUDE.md:22` | Datetimes aware; UTC before serialization and MinIO key | invariant | link | `#INV-9`; key format `docs/ingestion/pipeline.md` | INV | agent-instruction-hierarchy | |  |
| M-SYS-118 | `services/ingestion-scraper/CLAUDE.md:23` | Inject clients and `now()`; no construction inside | requirement | move | `docs/engineering/conventions.md` (seams) | ENG | living-docs-engineering-workflow | requirements §13 (injected clients, `now()`) | ENG-005 |
| M-SYS-119 | `services/ingestion-scraper/CLAUDE.md:26` | `pytest-socket` disables sockets in unit suite | requirement | move | `docs/engineering/verification.md` | ENG | living-docs-engineering-workflow | requirements §13 | ENG-004 |
| M-SYS-120 | `services/ingestion-scraper/CLAUDE.md:27` | APIs stubbed with `respx` against saved fixtures | requirement | move | `docs/engineering/verification.md` | ENG | living-docs-engineering-workflow | requirements §13 | ENG-005 |
| M-SYS-121 | `services/ingestion-scraper/CLAUDE.md:28` | Integration tests use testcontainers, not compose | requirement | move | `docs/engineering/verification.md` | ENG | living-docs-engineering-workflow | requirements §13 | ENG-006 |
| M-CON-009 | `services/ingestion-scraper/CLAUDE.md:29` | `test_contract_fixture.py` generates the fixture | contract | link | CON #9 | CON | agent-instruction-hierarchy | |  |
| M-SYS-122 | `services/ingestion-scraper/CLAUDE.md:32` | `produce()` async trap | trap | delete | dup of M-SYS-061 | ING | living-docs-ingestion | |  |
| M-SYS-123 | `services/ingestion-scraper/CLAUDE.md:33` | `strftime` on non-UTC aware datetime writes local time with Z | trap | move | `docs/ingestion/pipeline.md` Known traps (MinIO keys) | ING | living-docs-ingestion | Protects INV-9 | docs/ingestion/pipeline.md#known-traps |
| M-SYS-124 | `services/ingestion-scraper/CLAUDE.md:34` | `instructor` invents values; hence `is_signal` and `None` | trap | move | `docs/ingestion/extraction.md` Known traps | EXT | living-docs-ingestion | requirements §11.1 | docs/ingestion/extraction.md#known-traps |
| M-SYS-125 | `services/ingestion-scraper/CLAUDE.md:35` | One gunicorn process; don't raise workers | trap | delete | dup of M-SYS-073 | OPS | living-docs-operations | |  |
| M-SYS-126 | `services/ingestion-scraper/CLAUDE.md:36` | `configure_logging()` in `create_app()`; ECS field names | requirement | link | `docs/operations/observability.md` (log contract, M-OPS-026) | — | living-docs-operations | OPS batch (CLAUDE-only source) |  |

### 5. `docker/CLAUDE.md`

| Row | Source | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-SYS-127 | `docker/CLAUDE.md:3` | Auto-loaded in docker/ | status-note | delete | — | — | agent-instruction-hierarchy | |  |
| M-SYS-128 | `docker/CLAUDE.md:7-11` | Compose up, down, down -v (destroys all data; never a fix) | command | keep | `README.md` (stack commands); `docker/AGENTS.md` names it | — | legacy-docs-retirement, agent-instruction-hierarchy | Test reads this file; after reduction it has no `down -v` line |  |
| M-CON-010 | `docker/CLAUDE.md:15` | `kafka-init` creates topics from `topics.yaml` on every up | contract | move | CON #1; one-shot detail `docs/operations/topology.md` | CON | living-docs-system-and-contracts, living-docs-operations | | CON-001 |
| M-SYS-129 | `docker/CLAUDE.md:16-17` | `minio-init`, `price-bootstrap` one-shots; no-ops when data exists | requirement | move | `docs/operations/topology.md` | OPS | living-docs-operations | | OPS-009 |
| M-SYS-130 | `docker/CLAUDE.md:17` | Wrong partition count fixed per topic, never `down -v` | requirement | move | `docs/operations/topology.md` | OPS | living-docs-operations | | OPS-019 |
| M-SYS-131 | `docker/CLAUDE.md:19-20` | Startup data one-shot; current data DAG; no hand-run scripts | requirement | link | M-SYS-058 owner | OPS | living-docs-operations | dup |  |
| M-CON-011 | `docker/CLAUDE.md:22-25` | DLT partition parity; resolver -1; lowercase `.dlt`; verify on new pair | contract | move | CON #4, #36, #37 | CON | living-docs-system-and-contracts | Correct text (unlike `services/CLAUDE.md:24`) | CON-004 CON-035 CON-036 |
| M-SYS-132 | `docker/CLAUDE.md:29-31` | Every `.env.example` var a bare `${VAR}` or `${VAR:?}` in compose | requirement | move | `docs/operations/topology.md` | OPS | living-docs-operations | `test_compose_gives_no_default_to_env_example_variables` | OPS-006 |
| M-SYS-133 | `docker/CLAUDE.md:31-32` | Ports bound to 127.0.0.1; exporters publish none | requirement | move | `docs/operations/topology.md` | OPS | living-docs-operations | requirements §1 :40 | OPS-005 |
| M-SYS-134 | `docker/CLAUDE.md:36-39` | `mem_limit` from `.env`, log label, scrape/probe, 7.5 GB, logging anchor | requirement | move | `docs/operations/topology.md` / `observability.md` | OPS | living-docs-operations | Value (7.5 GB) owned by compose/.env tests | OPS-014 OPS-042 OPS-043 OPS-044 |
| M-SYS-135 | `docker/CLAUDE.md:40-41` | Grafana `$$` in alerting files | trap | delete | dup of M-SYS-075 | OPS | living-docs-operations | |  |
| M-SYS-136 | `docker/CLAUDE.md:41-42` | Alert PromQL tested with promtool; add case per rule | requirement | move | `docs/operations/observability.md` | OPS | living-docs-operations | Path is under `services/ingestion-scraper/tests/unit/` | OPS-056 |
| M-SYS-137 | `docker/CLAUDE.md:46-48` | Every stateful path on named volume, listed in test, in volume-usage | requirement | move | `docs/operations/topology.md` | OPS | living-docs-operations | | OPS-017 |
| M-SYS-138 | `docker/CLAUDE.md:48-50` | Fernet, JWT, API secret from `.env` as required refs | requirement | move | `docs/operations/orchestration.md` | OPS | living-docs-operations | `## 2026-10-10 — Stack state persistence — CHOICE — …` | OPS-037 |
| M-SYS-139 | `docker/CLAUDE.md:51` | Never suggest `down -v` as a fix; every mention says so | requirement | move | `docs/operations/topology.md` | OPS | living-docs-operations | Guarded by `test_docs_never_offer_down_v_as_a_fix` | OPS-019 |
| M-SYS-140 | `docker/CLAUDE.md:52` | Password changes in place are in `docker/README.md` | status-note | link | `docker/AGENTS.md` | — | agent-instruction-hierarchy | |  |
| M-SYS-141 | `docker/CLAUDE.md:56-57` | `--wait` blocks on healthchecks; Airflow healthcheck ~60 s | status-note | move | `docs/operations/topology.md` | OPS | living-docs-operations | | OPS-011 |
| M-SYS-142 | `docker/CLAUDE.md:61-64` | Two databases, roles; init script; role re-applied; Flyway reruns | requirement | move | `docs/operations/topology.md`; names → overview naming table | OPS | living-docs-operations | | OPS-012 OPS-013 |

### 6. `docs/requirements.md` §0, §1, §2, §3, §10, §14

| Row | Source | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-SYS-143 | §0.1 | Historical research instrument, not live monitor | requirement | keep | stays with live-trading spec (`specs/live-trading.md`) →`living-docs-research/living-docs-strategy-and-dashboard` | EVA | living-docs-research | Out of rollout (`historical-instrument amendment out of scope`); index row only; C4 conflict open |  |
| M-SYS-144 | §0.2 | Cursor in Airflow Variables, read/written by DAG task | requirement | move | `docs/ingestion/pipeline.md` (rule), `docs/operations/orchestration.md` (storage) | ING | living-docs-ingestion, living-docs-operations | | ING-026 |
| M-SYS-145 | §0.3 | 24-month backfill prerequisite; 90-day `initial_lookback` | requirement | divergent | backfill →`living-docs-research/living-docs-strategy-and-dashboard` (`specs/historical-backfill.md`); lookback `docs/ingestion/connectors.md` names `sources.yaml` | ING | living-docs-ingestion, living-docs-research | `sources.yaml` value is 30 (`initial_lookback value`) | ING-004 |
| M-SYS-146 | §0.3 note | Forward-only collection cannot support backtest; backfill needed | rationale | move | →`living-docs-research/living-docs-strategy-and-dashboard` `docs/research/backtesting.md` Rationale | RES | living-docs-research | |  |
| M-SYS-147 | §0.4 | ≤500 extractions/day; separate backfill budget; pre-filter | requirement | move | `docs/ingestion/extraction.md` | EXT | living-docs-ingestion | | EXT-007 |
| M-CON-012 | §0.5 | `gene_targets` is a list | contract | move | CON #8 | CON | living-docs-system-and-contracts | | CON-008 |
| M-SYS-148 | §0.6 | Kafka Streams not a requirement | requirement | move | `docs/core-hub/corroboration.md` | COR | living-docs-core-hub | `specs/kafka-streams-correlation.md` draft | COR-002 |
| M-SYS-149 | §0.7 | Tickerless signals stored, corroborated, absent from ticker responses | requirement | move | `docs/core-hub/storage.md` / `http-api.md` | HUB | living-docs-core-hub | | HUB-036 |
| M-SYS-150 | §1 :26 | Python 3.14, uv, lock committed, exact pins | requirement | move | `docs/engineering/conventions.md`; values `VERSIONS.md` | ENG | living-docs-engineering-workflow | | ENG-048 |
| M-INV-024 | §1 :27 | Fully synchronous; `fetch_since` returns Iterator | invariant | link | `#INV-8`; Iterator → `docs/ingestion/connectors.md` | INV | living-docs-system-and-contracts | |  |
| M-SYS-151 | §1 :28 | `httpx` only via `RateLimitedClient`; library list | requirement | move | `docs/ingestion/connectors.md`; list → `pyproject.toml` | ING | living-docs-ingestion | | ING-005 |
| M-SYS-152 | §1 :29 | Test libraries; testcontainers required | requirement | move | `docs/engineering/verification.md` | ENG | living-docs-engineering-workflow | | ENG-006 |
| M-SYS-153 | §1 :32 | Java 25, Boot 4.x, Gradle Kotlin DSL, no Lombok | requirement | move | `docs/engineering/conventions.md`; values `VERSIONS.md` | ENG | living-docs-engineering-workflow | | ENG-053 ENG-054 |
| M-SYS-154 | §1 :32 | Spring Kafka 4.1 DLPR re-confirm at Step 1.3 | history | delete | — | — | living-docs-system-and-contracts | Confirmed `## 2026-08-16 — Step 1.3 — VERIFIED — …` |  |
| M-SYS-155 | §1 :33-34 | core-hub dependencies and test stack incl. ArchUnit | value | link | `gradle/libs.versions.toml` | ENG | living-docs-engineering-workflow | |  |
| M-CON-013 | §1 :37 | Topics from declarative `topics.yaml`, never producer side effect | contract | move | CON #1 | CON | living-docs-system-and-contracts | | CON-001 |
| M-SYS-156 | §1 :38 | Postgres holds raw audit, signals, history, observations, corroborations, price series | stale | delete | `docs/core-hub/storage.md` lists actual tables | HUB | living-docs-core-hub | "price series" wrong: prices are MinIO Parquet (A C5) |  |
| M-SYS-157 | §1 :38 | Airflow metadata separate DB, own role, no cross-grants | requirement | move | `docs/operations/topology.md` | OPS | living-docs-operations | §14 settled too | OPS-012 |
| M-SYS-158 | §1 :38 | Flyway owns schema; `ddl-auto=validate` | requirement | move | `docs/core-hub/storage.md` | HUB | living-docs-core-hub | | HUB-019 |
| M-SYS-159 | §1 :39 | Neo4j constraints via versioned idempotent startup component; `GraphSchema` node | requirement | move | `docs/core-hub/storage.md` | HUB | living-docs-core-hub | | HUB-032 |
| M-SYS-160 | §1 :40 | MinIO credentials from `.env`, no defaults; ports on 127.0.0.1 | requirement | move | INV-6 (credentials); `docs/operations/topology.md` (ports) | OPS | living-docs-operations | | OPS-005 OPS-006 |
| M-CON-014 | §2 :48 | Raw pointer: fields, `retrieved_at`, no `raw_content`, key `external_id` | contract | divergent | CON #5 | CON | living-docs-system-and-contracts | PENDING `raw-pointer contract`; C1 `RawAuditService.java:47` | CON-005 |
| M-CON-015 | §2 :48, §3.7 | Raw pointer for every archived document | contract | divergent | CON #6 | CON | living-docs-system-and-contracts | PENDING `raw-pointer contract`; `pipeline.py:159` | CON-006 |
| M-CON-016 | §2 :49 | Signals topic carries `ResearchSignalEvent`, key `event_id` | contract | move | CON #2, #3 | CON | living-docs-system-and-contracts | | CON-002 CON-003 |
| M-CON-017 | §2 :50 | Corroborated topic, key `entity_key`, consumers "notifications" | contract | move | CON #2, #3 | CON | living-docs-system-and-contracts | Consumer corrected to strategy runtime (`## 2026-09-20 — Strategy layer session 2 — CHOICE — Event-driven Kafka consumer …`) | CON-002 CON-003 |
| M-CON-018 | §2 :51 | Two DLTs, inherited key, manual triage | contract | move | CON #2, #38 | CON | living-docs-system-and-contracts | `topics.yaml` also has `auspex.signals.corroborated.dlt` (no producer) | CON-002 CON-037 |
| M-CON-019 | §2 :53 | Keys are document identity, never gene target | contract | move | CON #3 (+ Rationale) | CON | living-docs-system-and-contracts | | CON-003 |
| M-CON-020 | §2 :55 | 6 partitions, RF 1 | value | link | `docker/topics.yaml` | CON | living-docs-system-and-contracts | Not copied |  |
| M-CON-021 | §2 :55 | DLT same partition count because Spring uses same partition | contract | move | CON #4 (parity as defence) | CON | living-docs-system-and-contracts | Rationale corrected (C2) | CON-004 |
| M-CON-022 | §2 :57 | Lowercase `.dlt` via custom resolver; partition -1 | contract | move | CON #36, #37 | CON | living-docs-system-and-contracts | | CON-035 CON-036 |
| M-CON-023 | §2 :59 | Retention per topic | value | link | `docker/topics.yaml` | CON | living-docs-system-and-contracts | Not copied |  |
| M-INV-025 | §3.1 | Scraper writes only MinIO and Kafka; no cursor exemption | invariant | move | `#INV-1` (+ scope line) | INV | living-docs-system-and-contracts | | INV-1 |
| M-INV-026 | §3.2 | Single database writer | invariant | move | `#INV-2` | INV | living-docs-system-and-contracts | | INV-2 |
| M-INV-027 | §3.3 | No credentials, keys, hosts in source; keys as Airflow Connections | invariant | divergent | `#INV-6` | INV | living-docs-system-and-contracts | PENDING `invariant 6 wording` | INV-6 |
| M-SYS-161 | §3.3 | Logs never carry credentials or full `raw_content` | requirement | move | `docs/operations/observability.md` (log contract) | OPS | living-docs-operations | Core-hub test only: `LoggingTest.java::test_log_output_does_not_contain_raw_content_field` | OPS-041 |
| M-INV-028 | §3.4 | Schema symmetry; snake_case; Python generates fixture | invariant | move | `#INV-7` | INV | living-docs-system-and-contracts | | INV-7 |
| M-CON-024 | §3.4 | Explicit `PropertyNamingStrategies.SNAKE_CASE` | contract | move | CON #8 | CON | living-docs-system-and-contracts | | CON-008 |
| M-INV-029 | §3.5 | Synchronous; concurrency from Airflow task parallelism | invariant | move | `#INV-8` (+ scope line) | INV | living-docs-system-and-contracts | | INV-8 |
| M-INV-030 | §3.6 | Timestamps UTC incl. MinIO keys from UTC value | invariant | move | `#INV-9` | INV | living-docs-system-and-contracts | | INV-9 |
| M-INV-031 | §3.7 | Idempotent writes per declared natural key | invariant | move | `#INV-10` | INV | living-docs-system-and-contracts | | INV-10 |
| M-CON-025 | §3.7 table | `raw_fetch_audit` keyed by MinIO object key, do nothing | contract | move | CON #21 | CON | living-docs-system-and-contracts | | CON-021 |
| M-CON-026 | §3.7 table | `signal_current` keyed by `event_id`, latest extraction wins | contract | move | CON #22 | CON | living-docs-system-and-contracts | First-observation `source_type`: HUB | CON-022 |
| M-CON-027 | §3.7 table | `signal_extraction_history` `(event_id, extraction_id)`, append-only | contract | move | CON #23 | CON | living-docs-system-and-contracts | | CON-023 |
| M-CON-028 | §3.7 table | `source_observation` `(event_id, source_type, external_id)`, append-only | contract | move | CON #24 | CON | living-docs-system-and-contracts | | CON-024 |
| M-CON-029 | §3.7 table | `corroboration` `(entity_key, participants_hash)`, supersession | contract | move | CON #25 | CON | living-docs-system-and-contracts | | CON-025 |
| M-CON-030 | §3.7 table | `(:Signal)` MERGE on `event_id` | contract | move | CON #26 | CON | living-docs-system-and-contracts | | CON-026 |
| M-CON-031 | §3.7 table | Entity nodes MERGE on natural key per §9 | contract | move | CON #27 (links HUB graph model) | CON | living-docs-system-and-contracts | | CON-027 |
| M-SYS-162 | §3.8 | Write order Neo4j → Postgres → ack; RECORD; qualified `@Transactional`; ArchUnit | requirement | move | `docs/core-hub/consumption.md` / `storage.md` | HUB | living-docs-core-hub | No INV | HUB-014 HUB-024 HUB-026 |
| M-SYS-163 | §3.9 | earliest; one group per listener; small `max.poll.records` | requirement | move | `docs/core-hub/consumption.md` | HUB | living-docs-core-hub | No INV | HUB-001 |
| M-CON-032 | §3.10 | Deterministic failures (deserialize, validation, enum, score, major) → DLT immediately | contract | link | `docs/core-hub/consumption.md` | — | living-docs-system-and-contracts | Unknown enum: PENDING `closed sets on the wire`, divergent (C7) |  |
| M-SYS-164 | §3.10 | Transient: 3 deliveries with back-off, then DLT | requirement | move | `docs/core-hub/consumption.md` | HUB | living-docs-core-hub | | HUB-012 |
| M-SYS-165 | §3.10 | `ErrorHandlingDeserializer` wraps both listeners | requirement | move | `docs/core-hub/consumption.md` | HUB | living-docs-core-hub | | HUB-002 |
| M-CON-033 | §3.10 | Diagnostic headers on every dead letter | contract | move | CON #38 | CON | living-docs-system-and-contracts | | CON-037 |
| M-INV-032 | §3.10 | Never block a partition | invariant | move | `#INV-11` | INV | living-docs-system-and-contracts | | INV-11 |
| M-INV-033 | §3.11 | Parameterized queries; ArchUnit + injection tests | invariant | move | `#INV-12` | INV | living-docs-system-and-contracts | | INV-12 |
| M-SYS-166 | §3.11 | Controller ticker allowlist regex | requirement | move | `docs/core-hub/http-api.md` | HUB | living-docs-core-hub | Value is code (`SignalController`) | HUB-044 |
| M-INV-034 | §3.12 | Nothing dies silently | invariant | move | `#INV-11` | INV | living-docs-system-and-contracts | | INV-11 |
| M-SYS-167 | §3.12 | DLT depth and per-source signal age reported | requirement | move | `docs/core-hub/consumption.md` (health reporter); alerts `docs/operations/observability.md` | HUB | living-docs-core-hub, living-docs-operations | | HUB-052 |
| M-CON-034 | §10.1 | `event_id` formula, canonical else `source_type:external_id` | contract | move | CON #18 | CON | living-docs-system-and-contracts | | CON-018 |
| M-CON-035 | §10.1 | `extraction_id` formula | contract | move | CON #19 | CON | living-docs-system-and-contracts | | CON-019 |
| M-CON-036 | §10.1 | `canonical_id` typed prefix; connector supplies it consistently | contract | move | CON #20 | CON | living-docs-system-and-contracts | Prefixes owned by `models.py:6` | CON-020 |
| M-SYS-168 | §10.1 | `signal_current.source_type` from first observation, never updated | requirement | move | `docs/core-hub/storage.md` | HUB | living-docs-core-hub | | HUB-028 |
| M-CON-037 | §10.1 | Near-miss identity formulas and why | rationale | move | CON Rationale | CON | living-docs-system-and-contracts | | docs/system/contracts.md#rationale |
| M-CON-038 | §10.2 | Field list of `ResearchSignalEvent` | contract | move | CON #8 (field list owned by model + fixture) | CON | living-docs-system-and-contracts | Not copied | CON-008 |
| M-CON-039 | §10.2 | `event_type` closed set | contract | move | CON #13 (values owned by `EventType`) | CON | living-docs-system-and-contracts | | CON-013 |
| M-CON-040 | §10.2 | `source_type` enum | contract | move | CON #14 | CON | living-docs-system-and-contracts | | CON-014 |
| M-CON-041 | §10.2 | `directionality` enum | contract | ratify | CON #15 | CON | living-docs-system-and-contracts | Values only in `prompts/extraction/v1.txt:29`; batch | CON-015 |
| M-CON-042 | §10.2 | `trial_ids` `NCT` + 8 digits; `primary_company` nullable | contract | move | CON #16, #8 | CON | living-docs-system-and-contracts | | CON-016 CON-008 |
| M-CON-043 | §10.2 | Schema version is 1.0 | value | link | `models.py:9` `EVENT_SCHEMA_VERSION` | CON | living-docs-system-and-contracts | Not copied |  |
| M-CON-044 | §10.2 | `external_id`, `raw_object_key` keep chain of custody; lists rationale | contract | move | CON #8 (+ Rationale) | CON | living-docs-system-and-contracts | | CON-008 |
| M-CON-045 | §10.3 | `confidence_score` 0.0–1.0 inclusive; missing/out of range → DLT, never clamped | contract | link | `docs/core-hub/consumption.md` | — | living-docs-system-and-contracts | C6 unverified listener validation |  |
| M-CON-046 | §10.3 | Java `BigDecimal` with `@NotNull @DecimalMin @DecimalMax` | contract | move | CON #12 | CON | living-docs-system-and-contracts | | CON-012 |
| M-SYS-169 | §10.3 | `@Valid` explicit on listener payload | requirement | move | `docs/core-hub/consumption.md` | HUB | living-docs-core-hub | C6 | HUB-011 |
| M-SYS-170 | §10.3 | Postgres NUMERIC(4,3); Neo4j double | requirement | move | `docs/core-hub/storage.md` | HUB | living-docs-core-hub | | HUB-029 |
| M-CON-047 | §10.4 | `major.minor` parsed as integers | contract | move | CON #28 | CON | living-docs-system-and-contracts | | CON-028 |
| M-CON-048 | §10.4 | Unknown major → DLQ | contract | link | `docs/core-hub/consumption.md` | — | living-docs-system-and-contracts | |  |
| M-CON-049 | §10.4 | Minor mismatch accepted and logged; `FAIL_ON_UNKNOWN_PROPERTIES=false` | contract | move | CON #30 | CON | living-docs-system-and-contracts | | CON-029 |
| M-CON-050 | §10.4 | Version as UTF-8 header and field | contract | move | CON #31 | CON | living-docs-system-and-contracts | "consumers read the field" half → batch | CON-030 |
| M-CON-051 | §10.4 | Bump updates model, record and fixture in one change | contract | move | CON #32 | CON | living-docs-system-and-contracts | | CON-031 |
| M-SYS-171 | §10.4 | Re-extraction is an explicit CLI operation | requirement | move | `docs/ingestion/extraction.md` | EXT | living-docs-ingestion | | EXT-019 |
| M-SYS-172 | §14 | Sync-only settled | rationale | link | INV-8 rationale in `docs/system/overview.md` | INV | living-docs-system-and-contracts | |  |
| M-SYS-173 | §14 | Airflow scheduler, Kafka backbone | rationale | move | `docs/operations/orchestration.md` Rationale | OPS | living-docs-operations | | docs/operations/orchestration.md#rationale |
| M-SYS-174 | §14 | Airflow metadata separate logical DB | rationale | link | M-SYS-157 owner | OPS | living-docs-operations | |  |
| M-SYS-175 | §14 | First-class `SignalNode` | rationale | move | `docs/core-hub/storage.md` Rationale | HUB | living-docs-core-hub | | docs/core-hub/storage.md#rationale |
| M-SYS-176 | §14 | `confidence_score` 0.0–1.0 float | rationale | link | CON #12 Rationale | CON | living-docs-system-and-contracts | |  |
| M-SYS-177 | §14 | UTC everywhere | rationale | link | INV-9 | INV | living-docs-system-and-contracts | |  |
| M-SYS-178 | §14 | Testcontainers over mocks at store boundary | rationale | move | `docs/engineering/verification.md` Rationale | ENG | living-docs-engineering-workflow | | docs/engineering/verification.md#rationale |
| M-SYS-179 | §14 | Free-tier-first tooling | rationale | move | `docs/system/overview.md` Rationale | SYS | living-docs-system-and-contracts | | docs/system/overview.md#rationale |
| M-SYS-180 | §14 | TDD | rationale | link | INV-15 | INV | living-docs-system-and-contracts | |  |
| M-SYS-181 | §14 heading | "Do not relitigate" | process | move | conflict policy `docs/engineering/change-workflow.md` | ENG | living-docs-engineering-workflow | | ENG-023 |

### 7. `docker/topics.yaml` (machine authority)

| Row | Source | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-CON-052 | `docker/topics.yaml:1-3` | Single source for names, partitions, retention; read by kafka-init | value | keep | authority; described by CON #1, authority table in `docs/README.md` | CON | living-docs-system-and-contracts | |  |
| M-CON-053 | `docker/topics.yaml:4-5` | Source topics 6 partitions RF 1; DLTs mirror, not relying on -1 | contract | move | CON #4 (meaning); numbers stay in file | CON | living-docs-system-and-contracts | | CON-004 |
| M-CON-054 | `docker/topics.yaml:7-36` | Six topic entries with partitions and retention | value | keep | authority | CON | living-docs-system-and-contracts | `auspex.signals.corroborated.dlt` has no producer (C9): CON Rationale |  |

### 8. Models, fixture and wire code (machine authorities)

| Row | Source | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-CON-055 | `services/ingestion-scraper/src/auspex_ingest/models.py:6` | Canonical id prefixes | value | keep | authority for CON #20 | CON | living-docs-system-and-contracts | Includes `fda:` (`fda_approval source` context) |  |
| M-CON-056 | `services/ingestion-scraper/src/auspex_ingest/models.py:8-9` | `EVENT_SCHEMA_VERSION` constant | value | keep | authority for CON #28 | CON | living-docs-system-and-contracts | |  |
| M-CON-057 | `services/ingestion-scraper/src/auspex_ingest/models.py:12-21` | `RawDocument` fields; `raw_content` excluded from dump | value | keep | authority for CON #5 | CON | living-docs-system-and-contracts | |  |
| M-CON-058 | `services/ingestion-scraper/src/auspex_ingest/models.py:23-33,73-87` | Aware datetimes, UTC-normalised, serialised with `Z` | contract | move | CON #11 | CON | living-docs-system-and-contracts | | CON-011 |
| M-CON-059 | `services/ingestion-scraper/src/auspex_ingest/models.py:45-71` | `ResearchSignalEvent` fields; defaults for company-level fields | value | keep | authority for CON #8 | CON | living-docs-system-and-contracts | Asymmetric nullability noted (Python defaults vs Java `@NotNull`) |  |
| M-CON-060 | `services/ingestion-scraper/src/auspex_ingest/models.py:64` | `confidence_score` `ge=0.0, le=1.0` | contract | move | CON #12 | CON | living-docs-system-and-contracts | | CON-012 |
| M-CON-061 | `services/ingestion-scraper/src/auspex_ingest/identity.py:4-20` | `compute_event_id`, `compute_extraction_id` | contract | move | CON #18, #19 | CON | living-docs-system-and-contracts | | CON-018 CON-019 |
| M-CON-062 | `services/ingestion-scraper/src/auspex_ingest/extractor.py:9-23` | `EventType` literal | value | keep | authority for CON #13 | CON | living-docs-system-and-contracts | |  |
| M-CON-063 | `services/ingestion-scraper/src/auspex_ingest/extractor.py:41-45` | Unknown model label recorded as `other` | contract | move | CON #13 | CON | living-docs-system-and-contracts | `## 2026-10-07 — Company-level extraction — CHOICE — …` item 3 | CON-013 |
| M-CON-064 | `services/ingestion-scraper/prompts/extraction/v1.txt:29` | `directionality` values positive/negative/neutral | contract | ratify | CON #15 | CON | living-docs-system-and-contracts | batch | CON-015 |
| M-CON-065 | `services/core-hub/src/test/resources/contract/signal_event_v1.json` | Generated signal fixture | value | keep | authority; CON #9 | CON | living-docs-system-and-contracts | |  |
| M-CON-066 | `services/ingestion-scraper/tests/unit/test_contract_fixture.py:63,85` | Generator; key set equals model fields | contract | move | CON #9 verification | CON | living-docs-system-and-contracts | | CON-009 |
| M-CON-067 | `.github/workflows/python.yml:84-89` | Regenerate fixture, fail on diff | contract | keep | CON #9 `enforced` | CON | living-docs-system-and-contracts | |  |
| M-CON-068 | `services/core-hub/src/main/java/dev/auspex/corehub/signal/ResearchSignalEvent.java:19-45` | Java record, `BigDecimal` bounded score | value | keep | authority (Java side) for CON #8, #12 | CON | living-docs-system-and-contracts | |  |
| M-CON-069 | `ResearchSignalEventTest.java` (all) | Java side ignores a field missing from the record | contract | divergent | CON #10 (status `untested`) | CON | living-docs-system-and-contracts | C13 | CON-010 |
| M-CON-070 | `services/ingestion-scraper/src/auspex_ingest/messaging/kafka_producer.py:18-29` | Raw pointer payload, key, header | contract | divergent | CON #5 | CON | living-docs-system-and-contracts | PENDING `raw-pointer contract` | CON-005 |
| M-CON-071 | `services/ingestion-scraper/src/auspex_ingest/messaging/kafka_producer.py:31-38` | Signal payload, key, header | contract | move | CON #3, #31 | CON | living-docs-system-and-contracts | | CON-003 CON-030 |
| M-CON-072 | `services/ingestion-scraper/src/auspex_ingest/messaging/kafka_producer.py:40-48` | Flush, fail on undelivered | requirement | link | `docs/ingestion/pipeline.md` | ING | living-docs-ingestion | |  |
| M-CON-073 | `services/core-hub/src/main/java/dev/auspex/corehub/audit/RawAuditService.java:47` | Reads `ingested_at` | contract | divergent | CON #5 verification row | CON | living-docs-system-and-contracts | C1 | CON-005 |
| M-CON-074 | `services/ingestion-scraper/src/auspex_ingest/pipeline.py:159` | Raw pointer only alongside a published signal | contract | divergent | CON #6 verification row | CON | living-docs-system-and-contracts | PENDING `raw-pointer contract` | CON-006 |
| M-CON-075 | `TestFixtures.java` `validRawJson` | Hand-written raw payload, no raw fixture | contract | divergent | CON #7 | CON | living-docs-system-and-contracts | PENDING `defects found while scoping` | CON-007 |
| M-CON-076 | `services/core-hub/src/main/java/dev/auspex/corehub/corroboration/CorroboratedSignalEvent.java:7-18` | Six fields; snake_case, ISO, no type header | contract | move | CON #33 | CON | living-docs-system-and-contracts | requirements §4.1 | CON-032 |
| M-CON-077 | `strategy/.../runtime/events.py:9-31` | Hand mirror of corroborated event | contract | divergent | CON #35 | CON | living-docs-system-and-contracts | C8; PENDING `defects found while scoping` | CON-034 |
| M-CON-078 | `ScheduledCorroborationService` send-then-commit | At-least-once corroborated delivery | contract | ratify | CON #34 | CON | living-docs-system-and-contracts | batch | CON-033 |
| M-CON-079 | `services/core-hub/src/main/java/dev/auspex/corehub/config/KafkaConfig.java:187-188` | DLT topic `+".dlt"`, partition -1 | contract | move | CON #36, #37 | CON | living-docs-system-and-contracts | | CON-035 CON-036 |
| M-CON-080 | `KafkaConfig.java` DLT template map | DLT value bytes or snake_case JSON | contract | ratify | CON #38 | CON | living-docs-system-and-contracts | `## 2026-08-16 — Step 1.3 — VERIFIED — …`; batch | CON-037 |
| M-CON-081 | `services/core-hub/src/integrationTest/java/dev/auspex/corehub/KafkaErrorHandlingIT.java:49` | `test_unknown_enum_value_goes_to_dlt` tests unknown major | contract | divergent | CON #17 verification | CON | living-docs-system-and-contracts | C7; PENDING Closed sets on the wire | CON-017 |

### 9. `DECISIONS.md` entries in this domain (CHOICE classified; VERIFIED/FLAG used as sources)

| Row | Source (heading) | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-SYS-182 | `## 2026-08-15 — Step 0.0 — CHOICE` | Log initialised | history | keep | archive | — | living-docs-cutover | history |  |
| M-SYS-183 | `## 2026-09-20 — Watchlist backend — CHOICE — No user_id column; …` | Single-user installation | requirement | move | SYS #4; schema half `docs/core-hub/storage.md` | SYS | living-docs-system-and-contracts, living-docs-core-hub | **binding** | SYS-004 |
| M-INV-035 | `## 2026-09-20 — Watchlist backend — CHOICE — core-hub calls ClinicalTrials.gov directly` | Direct CT.gov call for watchlist preview | invariant | move | Exception under `#INV-4` | INV | living-docs-system-and-contracts | **binding**; placement under INV-4 in batch | INV-4 |
| M-CON-082 | `## 2026-09-20 — Strategy layer session 2 — CHOICE — Event-driven Kafka consumer …` | Strategy runtime consumes corroborated topic; no new topics | contract | move | CON #2; group and checkpoints → STR | CON | living-docs-system-and-contracts, living-docs-strategy-and-dashboard | **binding** | CON-002 |
| M-INV-036 | `## 2026-09-20 — Strategy layer session 2 — CHOICE — Strategies never see ingested_at …` | No processing time in as-of decisions | invariant | link | STR contract requirement (M-STR-059/M-STR-092); a sixteenth invariant only if the owner adopts it | — | living-docs-system-and-contracts | **binding** (via M-STR-073); at-risk class #4; The cutover's decision application writes a sixteenth invariant if the CHOICE on `processing time in as-of decisions` adopts it |  |
| M-CON-083 | `## 2026-10-07 — Company-level extraction — CHOICE — … (schema 1.1)` | Items 1, 3: direction in `directionality`; unknown → `other`; trial_ids validated | contract | move | CON #13, #16 | CON | living-docs-system-and-contracts | **binding** for items 1–3; "schema 1.1", "prompt v1.1" **history** (superseded by Single-source cleanup); item 4 HUB; item 5 ING | CON-013 CON-016 |
| M-CON-084 | `## 2026-10-10 — Single-source cleanup — CHOICE — one version of each pre-rollout artifact` | Schema 1.0; company fields required in Java, only `primary_company` nullable | contract | move | CON #8 | CON | living-docs-system-and-contracts | **binding** (event half); other items to their domains | CON-008 |
| M-INV-037 | `## 2026-10-09 — Stack backup — CHOICE — nightly backup to a folder on the Mac` | Backup only reads; restore one-shot refuses non-empty, core-hub stopped | invariant | move | Exception under `#INV-2` | INV | living-docs-system-and-contracts | **binding** (Boundary paragraph); rest OPS | INV-2 |
| M-INV-038 | `## 2026-10-10 — Stack backup — CHOICE — client tools …, memory and restore semantics` | Item 4: definition of "empty" for restore | invariant | move | Exception under `#INV-2` | INV | living-docs-system-and-contracts | **binding** (item 4); items 1–3, 5–6 OPS/history | INV-2 |
| M-INV-039 | `## 2026-10-07 — Second-wave specs — CHOICE — short interest is a market-data snapshot, not a connector` | Snapshots are not sources | invariant | move | Scope note under `#INV-4`; rules →`living-docs-research/living-docs-strategy-and-dashboard` RES | INV | living-docs-system-and-contracts, living-docs-research | **binding** | INV-4 |
| M-INV-040 | `## 2026-10-07 — Edge research scoping — CHOICE — ownership and insider data are snapshots, not connectors` | Snapshots are not sources | invariant | move | Scope note under `#INV-4`; rules →`living-docs-research/living-docs-strategy-and-dashboard` RES | INV | living-docs-system-and-contracts, living-docs-research | **binding** | INV-4 |
| M-INV-041 | `## 2026-10-10 — Strategy runtime — CHOICE — state placement, timing and the pass-through stub` | Item 5: unreadable payload skipped and counted; no runtime DLT | invariant | divergent | `#INV-11` verification (FLAG-INV) | INV | living-docs-system-and-contracts, living-docs-strategy-and-dashboard | **binding** for STR; conflicts with INV-11 → FLAG-INV; item 1 (third bucket) → SYS naming table | INV-11 |
| M-SYS-184 | `## 2026-10-08 — Control-surface scoping — CHOICE — dashboard runs in the stack behind its own server layer` | Browser talks only to dashboard; write token; no CORS | requirement | link | SYS component map; owner `docs/core-hub/http-api.md` (at-risk class #10) | HUB | living-docs-core-hub, living-docs-strategy-and-dashboard | **binding**, owned elsewhere |  |
| M-SYS-185 | `## 2026-10-09 — Guideline setup — CHOICE — merge flow, merge bar and shared-log conflicts …` | PR flow, owner merges, union driver | process | move | `AGENTS.md` hard rules; ENG change-workflow | ENG | agent-instruction-hierarchy, living-docs-engineering-workflow | **binding** | ENG-010 ENG-011 ENG-030 ENG-031 ENG-032 |
| M-SYS-186 | `## 2026-10-07 — Startup data — CHOICE — data fills itself on up; prices refresh daily` | No hand-run data scripts | requirement | move | `docs/operations/topology.md`; `AGENTS.md` hard rule | OPS | living-docs-operations, agent-instruction-hierarchy | **binding** | OPS-009 |
| M-SYS-187 | `## 2026-10-10 — Consolidated code, strategy and BV audit — CHOICE — what becomes specs, what does not` | Triage of audit findings into specs | history | keep | archive | — | living-docs-cutover | history |  |
| M-CON-085 | `## 2026-08-16 — Step 1.3 — VERIFIED — DeadLetterPublishingRecoverer with Spring Kafka 4.1` | Multi-template DLT recoverer; `.dlt` and -1 confirmed | contract | ratify | CON #36–38 Source / Known traps | CON | living-docs-system-and-contracts | VERIFIED, not CHOICE: rows go in batch | CON-035 CON-036 CON-037 |
| M-CON-086 | `## 2026-08-16 — Step 1.3 — VERIFIED — Spring Kafka 4.1 DLT header names` | `kafka_dlt-exception-message`, `kafka_dlt-original-topic` | contract | ratify | CON #38 | CON | living-docs-system-and-contracts | batch | CON-037 |
| M-CON-087 | `## 2026-09-20 — Strategy layer session 2 — FLAG — Corroboration surrogate key deferred; …` | Corroboration identity is `(entity_key, participants_hash)` | contract | move | CON #34 (supporting source) | CON | living-docs-system-and-contracts | | CON-033 |
| M-CON-088 | `## 2026-09-20 — Strategy layer session 2 — FLAG — extracted_at missing from ResearchSignalEvent (§10.2)` | No `extracted_at` on the event | status-note | keep | CON Notes; open flag | CON | living-docs-system-and-contracts | Not added by the rollout |  |

### 10. the at-risk classes at-risk classes in this domain

| Row | Source | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-INV-042 | at-risk class #4 | Strategies/backtests never use `ingested_at`/`extracted_at` for as-of | invariant | link | STR contract requirement (M-STR-059/M-STR-092); a sixteenth invariant only if the owner adopts it | — | living-docs-system-and-contracts | = M-INV-036; The cutover's decision application writes a sixteenth invariant if the CHOICE on `processing time in as-of decisions` adopts it |  |
| M-SYS-188 | at-risk class #10 | core-hub non-GET needs write token; no CORS | requirement | link | `docs/core-hub/http-api.md`; SYS component map links | HUB | living-docs-core-hub | Owner elsewhere |  |
| M-SYS-189 | at-risk class #12 | Single-user installation, no `user_id` | requirement | move | SYS #4 + HUB storage | SYS | living-docs-system-and-contracts, living-docs-core-hub | = M-SYS-183 | SYS-004 |
| M-INV-043 | at-risk class #13 | core-hub calls ClinicalTrials.gov directly | invariant | move | Exception under `#INV-4` | INV | living-docs-system-and-contracts | = M-INV-035 | INV-4 |
| M-SYS-190 | at-risk class #18 | Process/ops rules only in CLAUDE.md (scripts, identity, down -v, Flyway, traps) | process | move | rows M-SYS-007, -046…-058, -059…-082, -139, -041 | — | agent-instruction-hierarchy, living-docs-operations, living-docs-engineering-workflow | Every item routed above |  |

### File-level dispositions

| Source file | Final role | Spec |
|---|---|---|
| `CLAUDE.md` | `@AGENTS.md` only; content routed per §1 | agents |
| `services/CLAUDE.md` | `@AGENTS.md` only | agents |
| `services/core-hub/CLAUDE.md` | `@AGENTS.md` only | agents |
| `services/ingestion-scraper/CLAUDE.md` | `@AGENTS.md` only | agents |
| `docker/CLAUDE.md` | `@AGENTS.md` only (path kept: read by `test_docs_never_offer_down_v_as_a_fix`) | agents |
| `AGENTS.md` (new, root and 8 nested) | Canonical agent instructions; no requirement text | agents |
| `docs/requirements.md` §0, §1, §2, §3, §10, §14 | Absorbed into INV/SYS/CON and other domains; legacy § → ID index rows (§3 table in `living-docs-system-and-contracts` Notes) | system (content), legacy (index) |
| `docker/topics.yaml` | Machine authority, unchanged | — |
| `services/ingestion-scraper/src/auspex_ingest/models.py`, `identity.py`, `extractor.py` | Machine authority, unchanged | — |
| `services/core-hub/src/test/resources/contract/signal_event_v1.json` | Generated machine authority, unchanged | — |
| `ResearchSignalEvent.java`, `CorroboratedSignalEvent.java` | Machine authority (Java side), unchanged | — |
| `docs/README.md` (new) | Non-normative index, namespaces, authority map, legends | system |
| `docs/system/overview.md`, `invariants.md`, `contracts.md` (new) | Owners of SYS, INV, CON | system |
| `DECISIONS.md` CHOICE entries in §9 | Binding ones absorbed by the cited IDs; others history | system (absorb), cutover (classification check) |


## Ingestion and core-hub (ING, EXT, HUB, COR)


Written against develop @ `e51f742`. Specs: **ingestion** = `specs/living-docs-ingestion.md`, **core-hub** = `specs/living-docs-core-hub.md`. Other specs are named by file.
Row IDs use the four `living-docs-ingestion/living-docs-core-hub` prefixes; the `NS` column is the namespace of the target, which may belong to another spec (then the row is `link`, or `move` into that spec's file, and the owning spec assigns the ID).
Decision headings are abbreviated by title: *Raw-pointer* = `## 2026-10-15 — Living docs — PENDING — raw-pointer contract`; *Lookback* (`initial_lookback value`); *fda_approval* (`fda_approval source`); *Closed sets* (`closed sets on the wire`); *RunResult* (`RunResult counters`); *Defects* = `… — defects found while scoping`; *run_pipeline* (`run_pipeline.py support`). Ratification batches: *ING batch* = `… — PENDING — ingestion ratification batch`, *HUB batch* = `… — PENDING — core-hub ratification batch`.
Target IDs are not assigned here (design §5.2); `connectors.md#4` means "the 4th requirement listed for that file in the spec".

### docs/requirements.md §4, §4.1, §4.2 (corroboration)

| Row | Source (path:line or §) | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-COR-001 | §4 :93-99 | Corroborate: same normalized entity, distinct source_type, published ≤ 90 days apart | requirement | move | core-hub/corroboration.md#2 | COR | living-docs-core-hub | tested: `CorroborationServiceContractTest::test_two_distinct_sources_same_target_produces_one_corroboration`, `::test_signals_91_days_apart_produce_none`, `::test_signal_exactly_at_window_boundary` | COR-003 |
| M-COR-002 | §4 :101 | Window is between the two signals, never against now | requirement | move | corroboration.md#2 | COR | living-docs-core-hub | `::test_two_historical_signals_90_days_apart_corroborate_regardless_of_run_time` | COR-003 |
| M-COR-003 | §4.1 :105-107 | Why `(entity_key, participant_event_ids)` key fails under growth | rationale | link | corroboration.md Rationale | COR | living-docs-core-hub | no ID |  |
| M-COR-004 | §4.1 :109-112 | Record: entity_key, participants_hash, participant ids, distinct_source_count | requirement | move | corroboration.md#4 | COR | living-docs-core-hub | | COR-005 |
| M-COR-005 | §4.1 :113 | corroborated_at = max participant published_date; only backtest join field | requirement | move | corroboration.md#4 | COR | living-docs-core-hub | `::test_corroborated_at_is_latest_participant_publication_not_run_time`; `living-docs-research` cites it | COR-005 |
| M-COR-006 | §4.1 :114 | first_detected_at is scheduler run time, diagnostic only | requirement | move | corroboration.md#4 | COR | living-docs-core-hub | untested | COR-006 |
| M-COR-007 | §4.1 :115 | Larger group supersedes; superseded rows kept, excluded from notifications and REST | requirement | move | corroboration.md#5 | COR | living-docs-core-hub | `::test_fourth_signal_supersedes_rather_than_duplicating`, `::test_superseded_rows_are_retained_for_backtesting_but_excluded_from_notifications` | COR-007 |
| M-COR-008 | §4.2 :118 | Every graph write marks signal pending with fresh token, same transaction | requirement | move | corroboration.md#6 | COR | living-docs-core-hub | `CorroborationServiceIT::writeCommittingLongAfterItStartedIsCorroborated` | COR-008 |
| M-COR-009 | §4.2 :118 | Scan reads pending batch; matches ±90 days of its own published_date | requirement | move | corroboration.md#7 | COR | living-docs-core-hub | batch size is `corroboration.scan-batch-size` (`application.yml:70`, value) | COR-009 |
| M-COR-010 | §4.2 :118 | Wall-clock filter allowed only as documented optimisation, never semantics | requirement | move | corroboration.md#9 | COR | living-docs-core-hub | | COR-011 |
| M-COR-011 | §4.2 :118 | Entities above configurable degree cap (default 500) are skipped | requirement | move | corroboration.md#7 | COR | living-docs-core-hub | `::test_high_degree_entity_is_skipped_by_the_degree_cap` | COR-009 |
| M-COR-012 | §4.2 :118 | Clear pending only after sends acked, inserts committed, token unchanged | requirement | move | corroboration.md#8 | COR | living-docs-core-hub | `CorroborationScannerTest::pendingFlagIsClearedOnlyAfterEverySendIsAcknowledged`, `::clearUsesTheWriteTokenTheScanRead` | COR-010 |
| M-COR-013 | §4.2 :118 | No clock decides; late commit, lagging partition, DLT replay all scanned | requirement | move | corroboration.md#9 | COR | living-docs-core-hub | `CorroborationServiceIT::signalWrittenAfterNewerSignalsWereScannedIsCorroborated` | COR-011 |
| M-COR-014 | §4.2 :120 | `CorroborationService` interface stays | invariant | link | INV-5 | INV | living-docs-system-and-contracts | corroboration.md#1 applies it |  |
| M-COR-015 | §4.2 :120 | Streams implementation is conditional later work | status-note | keep | specs/kafka-streams-correlation.md | COR | living-docs-core-hub | not current behaviour |  |

### docs/requirements.md §5 (orchestration and cursor)

| Row | Source | Rule or content | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-ING-001 | §5 :126 | Airflow 3: `schedule` rename, Task SDK proxies Variables, `catchup` default | trap | link | operations/orchestration.md | OPS | living-docs-operations | |  |
| M-ING-002 | §5 :128 | Airflow owns when; Kafka owns after extraction; no RabbitMQ | rationale | link | system/overview.md | SYS | living-docs-system-and-contracts | |  |
| M-ING-003 | §5 :130 | Pipeline stateless: takes cursor, returns next_cursor; earliest failed else latest | requirement | move | ingestion/pipeline.md#5 | ING | living-docs-ingestion | CHOICE "cursor after a run with failed documents"; `test_ingestion_run_reliability.py::test_cursor_stops_at_the_earliest_failed_document` | ING-026 |
| M-ING-004 | §5 :130 | Capped run returns the input cursor | requirement | move | pipeline.md#5 | ING | living-docs-ingestion | `::test_extraction_cap_stops_the_run_and_returns_the_input_cursor` | ING-026 |
| M-ING-005 | §5 :132-137 | DAG task reads Variable, writes next_cursor, fails after; untouched on error | requirement | link | operations/orchestration.md | OPS | living-docs-operations | design §2 seam: DAG side is OPS |  |
| M-ING-006 | §5 :134 | First-run default is now − initial_lookback from sources.yaml | requirement | move | connectors.md#4 | ING | living-docs-ingestion | pending-decision *Lookback*; `test_api.py::test_ingest_absent_cursor_defaults_to_initial_lookback` | ING-004 |
| M-ING-007 | §5 :139 | `run_mock_ingestion.py` and backfill runner take cursor as argument | stale | delete | — | — | living-docs-ingestion | neither script exists at e51f742 |  |
| M-ING-008 | §5 :139 | A backfill never writes the live cursor | requirement | keep | specs/historical-backfill.md | ING | living-docs-ingestion | unbuilt; stays in the change spec |  |
| M-ING-009 | §5 :141 | catchup=False, max_active_runs=1, staggered schedules | requirement | link | operations/orchestration.md | OPS | living-docs-operations | |  |

### docs/requirements.md §6.1–§6.9 (connectors and pipeline)

| Row | Source | Rule or content | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-ING-010 | §6.1 :147-156 | fetch_since fetches and maps only: no MinIO, model or publish | requirement | move | connectors.md#1 | ING | living-docs-ingestion | `test_connector_contract.py::test_fetch_since_performs_no_io_beyond_http`; applies INV-3 | ING-001 |
| M-ING-011 | §6.1 :151 | fetch_since is synchronous, returns Iterator, cursor UTC-aware | requirement | move | connectors.md#1 | ING | living-docs-ingestion | `::test_fetch_since_is_not_a_coroutine_and_returns_an_iterator`; INV-8 | ING-001 |
| M-ING-012 | §6.1 :158 | [A1] why connectors must not write | rationale | link | connectors.md Rationale | ING | living-docs-ingestion | |  |
| M-ING-013 | §6.2 :167 | Order pre-filter → dedup → archive → extract → publish | stale | move | pipeline.md#1 | ING | living-docs-ingestion | corrected to archive first (finding #2); Rationale records it; `test_ingestion_pipeline.py::test_pipeline_archives_before_publishing` | ING-022 |
| M-ING-014 | §6.2 :167 | Pipeline is the single caller of connector, archive, extractor, producer | requirement | move | pipeline.md#2 | ING | living-docs-ingestion | untested | ING-023 |
| M-ING-015 | §6.2 :169 | Failing document recorded; run continues | requirement | move | pipeline.md#3 | ING | living-docs-ingestion | `::test_one_bad_document_does_not_abort_the_batch` | ING-024 |
| M-ING-016 | §6.2 :169 | RunResult counts incl. deduped, extracted | requirement | ratify | pipeline.md#4 | ING | living-docs-ingestion | pending-decision *RunResult*; code has no deduped/extracted (`pipeline.py:16-29`) | ING-025 |
| M-ING-017 | §6.2 :169 | RunResult `deduped`, `extracted` counters | requirement | retire | pipeline.md Retired | ING | living-docs-ingestion | *RunResult*; original text kept | ING-041 |
| M-ING-018 | §6.2 :169 | Task fails after saving next_cursor when any document failed | requirement | link | operations/orchestration.md | OPS | living-docs-operations | pipeline.md#5 owns next_cursor |  |
| M-ING-019 | §6.2 :171 | Flush and check delivery reports; undelivered message fails run | requirement | move | pipeline.md#8 | ING | living-docs-ingestion | untested for the real client; `test_kafka_delivery_failure_fails_the_run` is weak | ING-029 |
| M-ING-020 | §6.3 :175 | RawDocument fields as connector output | contract | move | connectors.md#1 | ING | living-docs-ingestion | wire form is CON; `test_connector_contract.py::test_rawdocument_rejects_naive_datetime` | ING-001 |
| M-ING-021 | §6.3 :175 | Source-specific dates retained separately | requirement | divergent | connectors.md#10 | ING | living-docs-ingestion | *Defects*: kept only in raw_content | ING-016 |
| M-ING-022 | §6.4 :179 | EntityNormalizer seam, identity implementation, every write through it | requirement | move | pipeline.md#17 | ING | living-docs-ingestion | `::test_entity_values_pass_through_the_normalizer`; core-hub entity_key normalization → corroboration.md#3 | ING-038 |
| M-ING-023 | §6.4 :179 | Seam history (introduced early, not inserted later) | history | delete | — | — | living-docs-ingestion | plan history |  |
| M-ING-024 | §6.5 :183 | One RateLimitedClient; per-host bucket from sources.yaml | requirement | move | connectors.md#5 | ING | living-docs-ingestion | `test_rate_limited_client.py::test_two_connectors_on_the_same_host_share_one_bucket` | ING-005 |
| M-ING-025 | §6.5 :183 | Airflow schedules staggered | requirement | link | operations/orchestration.md | OPS | living-docs-operations | |  |
| M-ING-026 | §6.5 :185-192 | Verified per-host limits table (6 hosts) | contract | move | connectors.md#6 | ING | living-docs-ingestion | external facts kept in doc; configured rates stay in sources.yaml; `test_sources_schema.py::test_source_rates_follow_the_requirements_limits` | ING-006 |
| M-ING-027 | §6.5 :192 | SEC: "Configure 5 req/s" | value | link | sources.yaml; operations/topology.md | OPS | living-docs-operations | configured value 4 lives in sources.yaml; aggregate budget is OPS |  |
| M-ING-028 | §6.5 :187 | EPO token expires 20 min, refresh; 429 carries Retry-After | trap | move | connectors.md Known traps | ING | living-docs-ingestion | | docs/ingestion/connectors.md#known-traps |
| M-ING-029 | §6.5 :192 | SEC User-Agent mandatory; IP block ~10 min, retry extends it | trap | move | connectors.md Known traps; #7 | ING | living-docs-ingestion | | docs/ingestion/connectors.md#known-traps ING-007 |
| M-ING-030 | §6.5 :188 | openFDA daily cap of 1,000 binds without a key | trap | divergent | connectors.md (`fda_approval`) | ING | living-docs-ingestion | *fda_approval*; approved source, no `sources.yaml` entry yet; the cap binds once the entry exists | ING-020 |
| M-ING-031 | §6.6 :196 | Deterministic vocabulary pre-filter before every model call (title or content) | requirement | ratify | pipeline.md#16 | ING | living-docs-ingestion | *ING batch*: code matches raw_content only (`prefilter.py:17-20`) | ING-037 |
| M-ING-032 | §6.6 :196 | Pre-filter measured on golden set for false negatives | requirement | move | extraction.md#15 | EXT | living-docs-ingestion | `test_scoring.py::test_golden_set_includes_documents_the_prefilter_should_and_should_not_reject` | EXT-015 |
| M-ING-033 | §6.6 :196 | Vocabulary versioned alongside prompt (`prefilter_version`) | requirement | move | extraction.md#7 | EXT | living-docs-ingestion | | EXT-007 |
| M-ING-034 | §6.6 :196 | prefiltered_out counted in RunResult | requirement | move | pipeline.md#4 | ING | living-docs-ingestion | `::test_prefilter_counts_appear_in_run_result`; dedup skips also counted there (*RunResult*) | ING-025 |
| M-ING-035 | §6.6 :196 | Cost rationale for the pre-filter | rationale | link | pipeline.md Rationale | ING | living-docs-ingestion | |  |
| M-ING-036 | §6.7 :200 | published_date is when information became public; non-public dates never align | requirement | move | connectors.md#9 | ING | living-docs-ingestion | | ING-009 |
| M-ING-037 | §6.7 :204 | bioRxiv: date of fetched version | requirement | move | connectors.md#9 | ING | living-docs-ingestion | `test_academic_papers.py::test_published_date_is_the_public_posting_date_not_retrieved_at` | ING-010 |
| M-ING-038 | §6.7 :205 | PubMed: earliest public availability | requirement | divergent | connectors.md#9 | ING | living-docs-ingestion | *Defects*: partial dates default to day 1 | ING-011 |
| M-ING-039 | §6.7 :206 | Patents: pre-grant publication, else grant; filed_date excluded | requirement | move | connectors.md#9 | ING | living-docs-ingestion | `test_epo_ops.py::test_published_date_is_the_public_disclosure_date_not_filing_date` | ING-012 |
| M-ING-040 | §6.7 :207 | Clinical trials: first post, or last update post when amended | requirement | move | connectors.md#9 | ING | living-docs-ingestion | `test_clinical_trials.py::test_published_date_is_a_post_date_not_the_submission_date` | ING-013 |
| M-ING-041 | §6.7 :208 | Regulatory: action date | requirement | divergent | connectors.md (`fda_approval`) | ING | living-docs-ingestion | *fda_approval*; approved source, no `sources.yaml` entry yet | ING-015 |
| M-ING-042 | §6.7 :209 | EDGAR: acceptanceDateTime | requirement | move | connectors.md#9 | ING | living-docs-ingestion | `test_sec_edgar.py::test_published_date_is_the_acceptance_time_converted_from_eastern_to_utc` | ING-014 |
| M-ING-043 | §6.8 :213-221 | Verified source APIs table (endpoint, auth, status) | contract | move | connectors.md#6 | ING | living-docs-ingestion | dated facts; patents row's "see CLAUDE.md traps" becomes a trap entry | ING-006 |
| M-ING-044 | §6.8 :220 | EFTS undocumented; keep the mapping thin | trap | move | connectors.md Known traps | ING | living-docs-ingestion | | docs/ingestion/connectors.md#known-traps |
| M-ING-045 | §6.8 :221 | company_tickers.json is ticker resolution source | contract | link | core-hub/storage.md#10 | HUB | living-docs-core-hub | used by `SecTickerCache` |  |
| M-ING-046 | §6.9 :225 | openFDA has no designations endpoint | trap | move | connectors.md Known traps | ING | living-docs-ingestion | | docs/ingestion/connectors.md#known-traps |
| M-ING-047 | §6.9 :227 | `fda_approval` source via Drugs@FDA, labels, shortages | requirement | divergent | connectors.md#14 | ING | living-docs-ingestion | *fda_approval*; approved source, no `sources.yaml` entry yet; connector code exists and is tested, only unconfigured — see spec Notes | ING-020 |
| M-ING-048 | §6.9 :228 | Optional `fda_designation` as own source_type | requirement | retire | connectors.md#14 Retired | ING | living-docs-ingestion | never built | ING-021 |

### docs/requirements.md §7, §7.1 (archive, dedup, precedence)

| Row | Source | Rule or content | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-ING-049 | §7 :234 | Archive unconditional, before any other side effect | invariant | link | INV-13 | INV | living-docs-system-and-contracts | pipeline.md#1 applies it |  |
| M-ING-050 | §7 :236-240 | Object key raw/{source}/{external_id}/{UTC ts}-{sha8}.json | contract | move | pipeline.md#9 | ING | living-docs-ingestion | `test_connector_contract.py::test_minio_key_converts_offset_timestamp_to_utc_wall_time` | ING-030 |
| M-ING-051 | §7 :242 | Same-second retry must not be a collision error | requirement | move | pipeline.md#9 | ING | living-docs-ingestion | `tests/integration/test_minio_storage.py::test_same_second_refetch_of_identical_content_is_a_noop_not_an_error` | ING-030 |
| M-ING-052 | §7.1.1 :246 | Archive always, first | invariant | link | INV-13 | INV | living-docs-system-and-contracts | |  |
| M-ING-053 | §7.1.2 :247 | Dedup gates extraction and publish only, never archive | requirement | move | pipeline.md#10 | ING | living-docs-ingestion | `test_deduplication.py::test_dedup_never_suppresses_the_minio_write` | ING-031 |
| M-ING-054 | §7.1.3 :248 | Same content hash: skip extraction and publish | requirement | move | pipeline.md#11 | ING | living-docs-ingestion | implemented as processed markers (CHOICE "unchanged re-fetch…") | ING-032 |
| M-ING-055 | §7.1.4 :249 | Amendment publishes under same event_id, new extraction_id | requirement | move | pipeline.md#12 | ING | living-docs-ingestion | `::test_changed_content_is_treated_as_an_amendment_and_republished` | ING-033 |
| M-ING-056 | §7.1.5 :250-254 | Canonical marker path and payload | contract | move | pipeline.md#13 | ING | living-docs-ingestion | | ING-034 |
| M-ING-057 | §7.1.5 :256 | Marker written after successful publish | requirement | divergent | pipeline.md#13 | ING | living-docs-ingestion | *Defects*: written before flush (`pipeline.py:168` vs `:189`) | ING-034 |
| M-ING-058 | §7.1.5 :256 | Cross-source hit skips extraction, records source_observation | requirement | divergent | pipeline.md#14 | ING | living-docs-ingestion | *Defects*; scope of the raw pointer follows *Raw-pointer* (CON) | ING-035 |
| M-ING-059 | §7.1.5 :258 | Marker write failure → one re-extraction, absorbed downstream | requirement | move | pipeline.md#13 | ING | living-docs-ingestion | `::test_failed_marker_write_causes_at_most_one_redundant_extraction` | ING-034 |
| M-ING-060 | §7.1.6 :260 | No canonical_id: cross-source duplicates accepted | requirement | move | pipeline.md#15 | ING | living-docs-ingestion | `::test_document_with_no_canonical_id_is_not_deduped_across_sources` | ING-036 |
| M-ING-061 | §7.1 :262 | Embedding-similarity dedup is cut | rationale | link | pipeline.md Rationale | ING | living-docs-ingestion | |  |
| M-ING-062 | §7.1 :264 | Postgres warehouse; DuckDB is a possible next step | status-note | delete | — | — | living-docs-ingestion | future idea, not behaviour |  |

### docs/requirements.md §9 (graph model)

| Row | Source | Rule or content | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-HUB-001 | §9 :278-289 | Signal node properties and three relationship types | contract | move | core-hub/storage.md#9 | HUB | living-docs-core-hub | company-level fields not in graph (CHOICE "event taxonomy…", item 4) | HUB-030 HUB-033 |
| M-HUB-002 | §9 :286-288 | Only TARGETS, USES_MECHANISM, MENTIONS are written | requirement | move | storage.md#9 | HUB | living-docs-core-hub | enforced: `ArchRulesTest::noRelationshipTypeOtherThanThoseInTheGraphModelIsWritten` | HUB-031 |
| M-HUB-003 | §9 :291 | Company MERGEs on name, never ticker; ticker set-if-known | requirement | move | storage.md#10 | HUB | living-docs-core-hub | CHOICE "ticker resolution details" item 4: extracted name as written; `SignalPersistenceIT::test_two_companies_without_tickers_are_two_nodes` | HUB-034 |
| M-HUB-004 | §9 :293 | confidence_score is a double in the graph, explicit conversion | requirement | move | storage.md#8 | HUB | living-docs-core-hub | `SignalPersistenceIT::test_confidence_score_is_numerically_comparable_in_cypher`; "converter" is an inline `.doubleValue()` | HUB-029 |
| M-HUB-005 | §9 :293 | Verify SDN default conversion for pinned version | stale | delete | — | — | living-docs-core-hub | no SDN repositories are used |  |
| M-HUB-006 | §9 :295 | Unique constraints, indexes, one GraphSchema node | requirement | move | storage.md#9 | HUB | living-docs-core-hub | `Neo4jSchemaInitializer`; untested by name beyond `SchemaIT` | HUB-032 |
| M-COR-016 | §9 :297-301 | Corroboration pattern is typed (never MENTIONS) | requirement | move | corroboration.md#2 | COR | living-docs-core-hub | `CorroborationServiceContractTest::test_two_signals_sharing_only_a_company_do_not_corroborate` | COR-003 |

### docs/requirements.md §11 (extraction), plus §10.4 re-extraction and §3/§10.3 consumer rules owned by HUB

| Row | Source | Rule or content | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-EXT-001 | §11.1 :356-358 | extract returns event or None; model decides via is_signal | requirement | move | extraction.md#1 | EXT | living-docs-ingestion | `test_ingestion_pipeline.py::test_extractor_returns_none_rather_than_inventing_a_gene_target` | EXT-001 |
| M-EXT-002 | §11.1 :358 | None → archived, counted, no event | requirement | move | extraction.md#1 | EXT | living-docs-ingestion | `::test_document_with_no_signal_is_archived_but_publishes_no_event` | EXT-001 |
| M-EXT-003 | §11.1 :358 | Why forced events create junk nodes | rationale | link | extraction.md Rationale | EXT | living-docs-ingestion | |  |
| M-EXT-004 | §11.1 :360 | min_confidence_to_publish per source, default 0.0 | requirement | move | extraction.md#2 | EXT | living-docs-ingestion | CHOICE "publish threshold default is 0.0…"; `::test_publish_threshold_defaults_to_zero_and_is_counted_when_raised` | EXT-002 |
| M-EXT-005 | §11.1 :360 | Raise only on calibration evidence | requirement | keep | specs/golden-set-expansion.md | EXT | living-docs-ingestion | unbuilt calibration |  |
| M-EXT-006 | §11.2 :366 | Delimited block, system instruction: content is data | requirement | divergent | extraction.md#3 | EXT | living-docs-ingestion | *Defects*: prompt lacks the statement | EXT-003 |
| M-EXT-007 | §11.2 :367 | raw_content truncated to a documented maximum | requirement | move | extraction.md#4 | EXT | living-docs-ingestion | names `_MAX_CONTENT_CHARS` (`extraction_backend.py:29`); untested | EXT-004 |
| M-EXT-008 | §11.2 :368 | gene_targets checked against HGNC; unknown to review bucket | requirement | divergent | extraction.md#5 | EXT | living-docs-ingestion | *Defects*; cited test is vacuous | EXT-005 |
| M-EXT-009 | §11.2 :369 | Extracted ticker validated against allowlist before graph write | requirement | move | extraction.md#6 | EXT | living-docs-ingestion | untested; controller half → core-hub/http-api.md#3 | EXT-006 |
| M-EXT-010 | §11.2 :371 | Payoff is manufactured corroboration | rationale | link | extraction.md Rationale | EXT | living-docs-ingestion | |  |
| M-EXT-011 | §11.3 :377 | Prompt is versioned file; prompt_version on every event | requirement | move | extraction.md#7 | EXT | living-docs-ingestion | `test_scoring.py::test_prompt_and_prefilter_versions_are_recorded_on_every_extracted_event` | EXT-007 |
| M-EXT-012 | §11.3 :377 | Golden set (20–30 docs) spans every source_type, scores fields, calibration, FNs | requirement | divergent | extraction.md#15 | EXT | living-docs-ingestion | *Defects*: no epo_ops document; count dropped (51 today) | EXT-015 |
| M-EXT-013 | §11.3 :377 | Runs manually, never in CI, gates each connector | requirement | move | extraction.md#13, #15 | EXT | living-docs-ingestion | | EXT-013 EXT-015 |
| M-EXT-014 | §10.4 :348 | Re-extraction is explicit CLI over archive, never routine side effect | requirement | move | extraction.md#19 | EXT | living-docs-ingestion | `test_reextract.py::test_runner_never_writes_to_airflow_or_cursor` | EXT-019 |
| M-EXT-015 | §10.4 :348 | Re-extraction writes new extraction_id, re-runs corroboration | requirement | divergent | extraction.md#19 | EXT | living-docs-ingestion | *Defects*: flags ignored, offset replaced; corroboration re-run via pending flag (`CorroborationServiceIT::reExtractedSignalIsScannedAgain`) | EXT-019 |
| M-HUB-007 | §3.8 :79 | Neo4j → Postgres → acknowledge | requirement | move | storage.md#4 | HUB | living-docs-core-hub | `SignalIngestionServiceTest::test_ingest_calls_graph_port_before_record_port`; shared row with `living-docs-system-and-contracts` fragment | HUB-024 |
| M-HUB-008 | §3.8 :79 | ack-mode RECORD; offset never committed before both stores return | requirement | move | consumption.md#8 | HUB | living-docs-core-hub | untested (C5), *Defects*; `FaultInjectionIT::test_neo4j_failure_prevents_offset_commit…` does not prove it | HUB-014 |
| M-HUB-009 | §3.8 :79 | Repositories in separate base packages with explicit @Enable… | stale | retire | storage.md Retired | HUB | living-docs-core-hub | *HUB batch*: no repositories exist (C12) | HUB-040 |
| M-HUB-010 | §3.8 :79 | Every @Transactional qualified (ArchUnit) | requirement | move | storage.md#5 | HUB | living-docs-core-hub | enforced: `ArchRulesTest::test_no_unqualified_transactional` | HUB-026 |
| M-HUB-011 | §3.9 :80 | earliest; one group per listener; small max.poll.records | requirement | move | consumption.md#1 | HUB | living-docs-core-hub | untested | HUB-001 |
| M-HUB-012 | §3.10 :81 | Deterministic failures → DLT at once (incl. unknown enum) | requirement | divergent | consumption.md#4 | HUB | living-docs-core-hub | unknown enum: *Closed sets* (C7); `KafkaErrorHandlingIT::test_malformed_json_goes_to_dlt_immediately` | HUB-004 HUB-005 HUB-006 HUB-007 HUB-008 HUB-009 |
| M-HUB-013 | §3.10 :81 | Transient: 3 deliveries with back-off, then DLT | requirement | move | consumption.md#6 | HUB | living-docs-core-hub | `KafkaRetryTest::transientFailureIsRetriedTwiceWithGrowingBackoff` | HUB-012 |
| M-HUB-014 | §3.10 :81 | ErrorHandlingDeserializer on both listeners | requirement | move | consumption.md#2 | HUB | living-docs-core-hub | `KafkaRetryTest::deserializationFailureGoesToTheDltWithoutRetry` | HUB-002 |
| M-HUB-015 | §3.10 :81 | Never block a partition | invariant | link | INV-11 | INV | living-docs-system-and-contracts | consumption.md#6; `KafkaErrorHandlingIT::test_poison_message_does_not_block_partition` |  |
| M-HUB-016 | §10.3 :342 | @Valid on listener payload needed explicitly | requirement | move | consumption.md#5 | HUB | living-docs-core-hub | untested (C6), *Defects* | HUB-011 |
| M-HUB-017 | §10.3 :344 | Missing/out-of-range score → DLT, never clamped | requirement | move | consumption.md#4 | HUB | living-docs-core-hub | untested through Kafka (C6) | HUB-007 HUB-008 |
| M-HUB-018 | §10.3 :342 | NUMERIC(4,3) in Postgres | requirement | move | storage.md#8 | HUB | living-docs-core-hub | Flyway V1 | HUB-029 |
| M-HUB-019 | §10.1 :328 | signal_current.source_type from first observation; observations append | requirement | move | storage.md#7 | HUB | living-docs-core-hub | `SignalPersistenceIT::test_second_source_observation_appends_and_does_not_change_signal_source_type` | HUB-028 |
| M-HUB-020 | §10.4 :346 | FAIL_ON_UNKNOWN_PROPERTIES=false on the consumer | requirement | move | consumption.md#3 | HUB | living-docs-core-hub | `ResearchSignalEventTest::test_minor_version_bump_with_extra_field_is_accepted` | HUB-003 |
| M-HUB-021 | §12 :388 | @Scheduled health reporter: DLT depth, per-source signal age | requirement | move | http-api.md#8 | HUB | living-docs-core-hub | `HealthReporterTest::healthReporterExportsDltDepthPerTopic`; "from Phase 5 notification transport" → keep in specs/hold/watchlist-alerts.md | HUB-052 |

### services/ingestion-scraper/README.md

| Row | Source | Rule or content | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-ING-063 | services/ingestion-scraper/README.md:3 | "Pulls documents from 5 public sources" | stale | delete | — | — | legacy-docs-retirement | 6 registered, 5 configured live |  |
| M-ING-064 | services/ingestion-scraper/README.md:3 | Archive unconditional, before any other side effect | invariant | link | INV-13 | INV | legacy-docs-retirement | |  |
| M-ING-065 | services/ingestion-scraper/README.md:3 | Stateless, no DB; cursor in Airflow Variables | invariant | link | INV-1; pipeline.md#5 | INV | legacy-docs-retirement | |  |
| M-ING-066 | services/ingestion-scraper/README.md:9-16 | Pipeline stage list | requirement | link | pipeline.md#1 | ING | legacy-docs-retirement | README order drifts (canonical before pre-filter in code) |  |
| M-ING-067 | services/ingestion-scraper/README.md:11 | Processed markers after confirmed delivery; identity model+prompt+prefilter | requirement | link | pipeline.md#11 | ING | legacy-docs-retirement | at-risk class #5 |  |
| M-ING-068 | services/ingestion-scraper/README.md:13 | Canonical check "skips when content hash seen before" | stale | delete | — | — | legacy-docs-retirement | it skips on another source's canonical marker |  |
| M-ING-069 | services/ingestion-scraper/README.md:14 | Company-level fields extracted; NCT ids validated | requirement | link | extraction.md#8 | EXT | legacy-docs-retirement | |  |
| M-ING-070 | services/ingestion-scraper/README.md:15 | `HgncEntityNormalizer` resolves aliases and tickers | stale | delete | — | — | legacy-docs-retirement | production wires `IdentityNormalizer` (`pipeline_factory.py:52`) |  |
| M-ING-071 | services/ingestion-scraper/README.md:16 | raw.ingested published for all documents | stale | link | CON raw pointer | CON | living-docs-system-and-contracts | *Raw-pointer*; code publishes for published signals only |  |
| M-ING-072 | services/ingestion-scraper/README.md:18 | At most max_documents_per_run to extraction; processed don't count | requirement | link | pipeline.md#6 | ING | legacy-docs-retirement | |  |
| M-ING-073 | services/ingestion-scraper/README.md:18 | Capped or unconfirmed-delivery run returns given cursor | requirement | link | pipeline.md#5 | ING | legacy-docs-retirement | |  |
| M-ING-074 | services/ingestion-scraper/README.md:18 | Second concurrent run of a source → 409 | requirement | ratify | pipeline.md#7 | ING | living-docs-ingestion | *ING batch* (archived spec ingestion-run-reliability also lists it); `test_ingestion_run_reliability.py::test_second_concurrent_run_of_a_source_is_refused_with_409` | ING-028 |
| M-ING-075 | services/ingestion-scraper/README.md:22 | DAG per entry; hour apart; pool 1 slot; retries; 3 h; save then fail | requirement | link | operations/orchestration.md | OPS | living-docs-operations | |  |
| M-ING-076 | services/ingestion-scraper/README.md:28-35 | Connectors table (class, source_type, status) | status-note | keep | README | — | legacy-docs-retirement | fix stale statuses: fda_approval "Active" (unconfigured), epo_ops "Blocked" (scheduled) |  |
| M-ING-077 | services/ingestion-scraper/README.md:32 | ClinicalTrials.gov raw_content includes lead sponsor | requirement | link | connectors.md#13 | ING | legacy-docs-retirement | |  |
| M-ING-078 | services/ingestion-scraper/README.md:33 | EDGAR 8-K items, Exhibit 99.1 + cover, acceptance time | requirement | link | connectors.md#11 | ING | legacy-docs-retirement | |  |
| M-ING-079 | services/ingestion-scraper/README.md:41-43 | Adding a connector: module, register, sources.yaml entry | process | keep | README | — | legacy-docs-retirement | how-to stays; requirement is connectors.md#2 |  |
| M-ING-080 | services/ingestion-scraper/README.md:45 | Unregistered source_type raises UnknownSourceTypeError listing types | requirement | ratify | connectors.md#2 | ING | living-docs-ingestion | *ING batch*; `test_connector_registry.py::test_unknown_source_type_raises_a_named_error_listing_registered_types` | ING-002 |
| M-ING-081 | services/ingestion-scraper/README.md:53-60 | sources.yaml field table | contract | link | connectors.md (sources.yaml semantics) | ING | legacy-docs-retirement | |  |
| M-ING-082 | services/ingestion-scraper/README.md:54 | Live sources ≥ 30 min apart (test-enforced) | requirement | link | operations/orchestration.md | OPS | living-docs-operations | |  |
| M-ING-083 | services/ingestion-scraper/README.md:55 | Rate spacing even, no burst; requests wait | requirement | link | connectors.md#5 | ING | legacy-docs-retirement | |  |
| M-ING-084 | services/ingestion-scraper/README.md:55 | Per-source rate numbers (1, 3, 2, ≤5) | value | delete | sources.yaml | — | legacy-docs-retirement | copies of machine values |  |
| M-ING-085 | services/ingestion-scraper/README.md:56 | initial_lookback: days fetched on first run | requirement | link | connectors.md#4 | ING | legacy-docs-retirement | *Lookback* |  |
| M-ING-086 | services/ingestion-scraper/README.md:57 | max_documents_per_run sized to 3 h timeout | rationale | link | pipeline.md Rationale | ING | legacy-docs-retirement | |  |
| M-ING-087 | services/ingestion-scraper/README.md:60 | min_confidence_to_publish optional, default 0.0 | requirement | link | extraction.md#2 | EXT | legacy-docs-retirement | |  |
| M-ING-088 | services/ingestion-scraper/README.md:62 | Unknown fields rejected at parse time | requirement | ratify | connectors.md#3 | ING | living-docs-ingestion | *ING batch*; `test_sources_schema.py::test_unknown_field_in_sources_yaml_is_rejected_at_parse_time` | ING-003 |
| M-ING-089 | services/ingestion-scraper/README.md:68-75 | Development commands | command | link | services/ingestion-scraper/AGENTS.md | — | agent-instruction-hierarchy | |  |
| M-ING-090 | services/ingestion-scraper/README.md:74,94 | `run_pipeline.py` CLI without Airflow | command | keep | README scripts table | — | legacy-docs-retirement | *run_pipeline*: developer tool, no requirement |  |
| M-ING-091 | services/ingestion-scraper/README.md:83 | "138+ tests" | status-note | delete | — | — | legacy-docs-retirement | stale count |  |
| M-ING-092 | services/ingestion-scraper/README.md:84 | Integration tests: LocalStack S3, Kafka, no stack | process | link | engineering/verification.md | ENG | living-docs-engineering-workflow | |  |
| M-ING-093 | services/ingestion-scraper/README.md:85 | Golden set of 50 documents | status-note | delete | — | — | legacy-docs-retirement | 51 files; no count in docs |  |
| M-ING-094 | services/ingestion-scraper/README.md:95 | score_extraction writes gate record | requirement | link | extraction.md#13 | EXT | legacy-docs-retirement | |  |
| M-ING-095 | services/ingestion-scraper/README.md:96 | evaluate_model writes latency record per model | requirement | link | extraction.md#13 | EXT | legacy-docs-retirement | archived spec model-evaluation |  |
| M-ING-096 | services/ingestion-scraper/README.md:97 | Leakage canary flags months ≥ 70% correct after cutoff | requirement | ratify | extraction.md#16 | EXT | living-docs-ingestion | *ING batch*; `test_model_evaluation.py::test_leakage_canary_scoring_reproduces_hand_computed_result_on_toy_set` | EXT-016 |
| M-ING-097 | services/ingestion-scraper/README.md:98 | Cross-model agreement: Jaccard, directionality, confidence correlation | requirement | ratify | extraction.md#17 | EXT | living-docs-ingestion | *ING batch*; `::test_cross_model_agreement_reproduces_hand_computed_metrics_on_toy_set` | EXT-017 |
| M-ING-098 | services/ingestion-scraper/README.md:99 | register_local_model copies candidate with live digest | requirement | link | extraction.md#9-10 | EXT | legacy-docs-retirement | `test_local_model_integration.py::test_register_local_model_appends_loadable_entry_with_live_digest` |  |
| M-ING-099 | services/ingestion-scraper/README.md:100 | sample_corroborations reads live DB | requirement | ratify | extraction.md#18; INV-1 scope note | EXT | living-docs-ingestion | *ING batch*; read-only scope stated by `living-docs-system-and-contracts` | EXT-018 |
| M-ING-100 | services/ingestion-scraper/README.md:101 | Corroboration review scored against 0.85 gate | requirement | ratify | extraction.md#18 | EXT | living-docs-ingestion | *ING batch*; only README and `HISTORY.md:96`; no test asserts exit 2 | EXT-018 |
| M-ING-101 | services/ingestion-scraper/README.md:107 | SEC 10 req/s aggregate; 403 stops EDGAR run | requirement | link | connectors.md#7 | ING | legacy-docs-retirement | CHOICE "a 403 on a filing index also stops…" |  |
| M-ING-102 | services/ingestion-scraper/README.md:107 | EDGAR 4 req/s + universe build 5 req/s stay under 10 | requirement | link | operations/topology.md; connectors.md#6 | OPS | living-docs-operations | at-risk class #8: aggregate is OPS, per-connector ING |  |
| M-ING-103 | services/ingestion-scraper/README.md:107 | User-Agent mandatory; index.htm doc table; Accepted is US Eastern | trap | link | connectors.md Known traps; #11 | ING | legacy-docs-retirement | |  |
| M-ING-104 | services/ingestion-scraper/README.md:107 | Company CIK from ciks[0]; submissions too short | trap | link | connectors.md#11 | ING | legacy-docs-retirement | |  |
| M-ING-105 | services/ingestion-scraper/README.md:107 | Inline-XBRL `/ix?doc=` links; hits deduplicated by accession | requirement | ratify | connectors.md#11 | ING | living-docs-ingestion | *ING batch* | ING-017 |
| M-ING-106 | services/ingestion-scraper/README.md:107 | EFTS `_source` uses adsh, ciks, display_names | trap | link | connectors.md Known traps | ING | legacy-docs-retirement | |  |
| M-ING-107 | services/ingestion-scraper/README.md:108 | EPO OPS OAuth2, 2.5 req/s free tier | trap | link | connectors.md#6 | ING | legacy-docs-retirement | |  |
| M-ING-108 | services/ingestion-scraper/README.md:109 | openFDA 1,000/day; no designations | trap | link | connectors.md Known traps | ING | legacy-docs-retirement | daily-cap half is M-ING-030 (`divergent`: approved *fda_approval* source; the cap binds once its `sources.yaml` entry exists) |  |
| M-ING-109 | services/ingestion-scraper/README.md:110 | CT.gov v2 needs `filter.advanced` range syntax | trap | ratify | connectors.md Known traps | ING | living-docs-ingestion | *ING batch* | docs/ingestion/connectors.md#known-traps |
| M-ING-110 | services/ingestion-scraper/README.md:111 | Patents: filed_date is not disclosure date | trap | link | connectors.md#9 | ING | legacy-docs-retirement | |  |

### services/core-hub/README.md

| Row | Source | Rule or content | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-HUB-022 | services/core-hub/README.md:3 | Sole database writer | invariant | link | INV-2 | INV | legacy-docs-retirement | restore exception under INV-2 (`restore exception to invariant 2`) |  |
| M-HUB-023 | services/core-hub/README.md:3 | What core-hub consumes, writes, serves | status-note | keep | README | — | legacy-docs-retirement | orientation |  |
| M-HUB-024 | services/core-hub/README.md:10-13 | Neo4j → Postgres → acknowledge, ack-mode RECORD | requirement | link | storage.md#4; consumption.md#8 | HUB | legacy-docs-retirement | C5 |  |
| M-HUB-025 | services/core-hub/README.md:17 | Store outage pauses both listeners; resume when both answer | requirement | link | consumption.md#7 | HUB | legacy-docs-retirement | at-risk class #7; `StoreAvailabilityGuardTest::listenersResumeOnlyWhenBothStoresAreUp` |  |
| M-HUB-026 | services/core-hub/README.md:17 | Probe interval 5 s (`store-check-interval-ms`) | value | link | application.yml | HUB | legacy-docs-retirement | value owned by config |  |
| M-HUB-027 | services/core-hub/README.md:18 | 1 + 2 retries, 5 s then 30 s; deterministic to DLT at once | requirement | link | consumption.md#4, #6 | HUB | legacy-docs-retirement | |  |
| M-HUB-028 | services/core-hub/README.md:19 | Health report every 5 min: DLT depth definition, signal age from Postgres | requirement | link | http-api.md#8 | HUB | legacy-docs-retirement | metric names → operations/observability.md |  |
| M-HUB-029 | services/core-hub/README.md:19 | Failed corroboration run increments failure counter | requirement | link | corroboration.md#12 | COR | legacy-docs-retirement | `ScheduledCorroborationServiceTest::corroborationScanFailureIncrementsTheCounter` |  |
| M-HUB-030 | services/core-hub/README.md:20 | Dead letters keep key, headers and wire form | contract | link | CON (DLT) | CON | living-docs-system-and-contracts | |  |
| M-HUB-031 | services/core-hub/README.md:30 | raw_fetch_audit: every document fetched | requirement | link | storage.md#12; CON raw pointer | HUB | legacy-docs-retirement | divergent: *Raw-pointer* |  |
| M-HUB-032 | services/core-hub/README.md:31-34 | Table purposes | contract | link | storage.md | HUB | legacy-docs-retirement | |  |
| M-HUB-033 | services/core-hub/README.md:33 | source_observation one row per (event_id, source_type) | stale | delete | — | — | legacy-docs-retirement | key also has external_id |  |
| M-HUB-034 | services/core-hub/README.md:34 | corroboration holds "active" records | stale | delete | — | — | legacy-docs-retirement | superseded rows are retained |  |
| M-HUB-035 | services/core-hub/README.md:38-43 | Node keys; pending flag and token on Signal | contract | link | storage.md#9; corroboration.md#6 | HUB | legacy-docs-retirement | |  |
| M-HUB-036 | services/core-hub/README.md:45 | Relationship types enforced; write replaces the signal's edges | requirement | link | storage.md#9, #11 | HUB | legacy-docs-retirement | at-risk class #6; `GraphRelationshipReplacementIT::rewriteWithADifferentGeneReplacesTheTargetsEdge` |  |
| M-HUB-037 | services/core-hub/README.md:47 | Ticker only on single SEC match; never cleared; watchlist back-fill | requirement | link | storage.md#10 | HUB | legacy-docs-retirement | CHOICE "ticker resolution details"; `CompanyTickerIT::companyMatchingTwoSecTitlesGetsNoTicker` |  |
| M-HUB-038 | services/core-hub/README.md:47 | CompanyNameNormalizer suffix list | requirement | ratify | storage.md#10 | HUB | living-docs-core-hub | *HUB batch* (code-only detail) | HUB-035 |
| M-HUB-039 | services/core-hub/README.md:49 | Flyway owns schema; ddl-auto validate, never update | requirement | link | storage.md#1 | HUB | legacy-docs-retirement | `SchemaIT::test_ddl_auto_is_validate` |  |
| M-COR-017 | services/core-hub/README.md:55 | Corroboration definition, supersession by containment | requirement | link | corroboration.md#2, #5 | COR | legacy-docs-retirement | |  |
| M-COR-018 | services/core-hub/README.md:57-59 | Score = 0.7 diversity + 0.3 recency, clamped; factor definitions | requirement | ratify | corroboration.md#11 | COR | living-docs-core-hub | *HUB batch*; at-risk class #9; README is the only prose source; `CorroborationScorerTest::test_score_never_leaves_0_1_range` | COR-013 |
| M-COR-019 | services/core-hub/README.md:61 | Pending flag and token scan; clear after commit if token unchanged | requirement | link | corroboration.md#6-9 | COR | legacy-docs-retirement | |  |
| M-COR-020 | services/core-hub/README.md:63 | CorroborationService abstract; contract test re-runs unmodified | requirement | link | corroboration.md#1 | COR | legacy-docs-retirement | "steps 2.8 and 6.4" is a plan-step reference: delete |  |
| M-HUB-040 | services/core-hub/README.md:69 | Non-GET under /api needs bearer write token; 401 otherwise | requirement | link | http-api.md#1 | HUB | legacy-docs-retirement | at-risk class #10; `WriteTokenIT::writeWithoutTokenIsRejectedWith401` |  |
| M-HUB-041 | services/core-hub/README.md:69 | No CORS; browsers reach core-hub via dashboard | requirement | link | http-api.md#2 | HUB | legacy-docs-retirement | `WriteTokenIT::noCorsHeadersAreReturnedForCrossOriginRequests` |  |
| M-HUB-042 | services/core-hub/README.md:71 | Watchlist summary contents | contract | link | http-api.md#4 | HUB | legacy-docs-retirement | |  |
| M-HUB-043 | services/core-hub/README.md:73 | DLT replay semantics; "replayed at most once" | requirement | ratify | consumption.md#10 | HUB | living-docs-core-hub | *HUB batch*: wording corrected to at-least-once, absorbed by idempotent writes | HUB-017 |
| M-HUB-044 | services/core-hub/README.md:75,79 | Signals by ticker: direct + corroborated | contract | link | http-api.md#3 | HUB | legacy-docs-retirement | |  |
| M-HUB-045 | services/core-hub/README.md:77 | Ticker must be in "configured allowlist" | stale | delete | — | — | legacy-docs-retirement | it is a regex, not a list |  |
| M-HUB-046 | services/core-hub/README.md:78 | Returns 404 if no signals | stale | ratify | http-api.md#3 | HUB | living-docs-core-hub | *HUB batch*: approved text is 200 with empty lists (`SignalRestIT::test_unknown_ticker_returns_empty_lists_not_500`) | HUB-045 |
| M-HUB-047 | services/core-hub/README.md:80 | Injection test covers Cypher injection and MATCH DELETE | requirement | link | storage.md#6 | HUB | legacy-docs-retirement | `SignalRestIT::test_injection_payload_is_rejected_or_bound_and_node_count_is_unchanged` |  |
| M-HUB-048 | services/core-hub/README.md:86-93 | Development commands | command | link | services/core-hub/AGENTS.md | — | agent-instruction-hierarchy | |  |
| M-HUB-049 | services/core-hub/README.md:99-103 | Build layout: Kotlin DSL, catalog matches VERSIONS.md, no dependency-management plugin | process | link | engineering/conventions.md | ENG | living-docs-engineering-workflow | |  |
| M-HUB-050 | services/core-hub/README.md:111-114 | Test layout; static singleton containers; 3-minute target | process | link | engineering/verification.md | ENG | living-docs-engineering-workflow | |  |
| M-HUB-051 | services/core-hub/README.md:116 | Contract test is abstract, never inlined | requirement | link | corroboration.md#1 | COR | legacy-docs-retirement | |  |
| M-HUB-052 | services/core-hub/README.md:122 | @Transactional always qualified | requirement | link | storage.md#5 | HUB | legacy-docs-retirement | |  |
| M-HUB-053 | services/core-hub/README.md:123 | MERGE, never CREATE, for signal and entity nodes | requirement | ratify | storage.md#3 | HUB | living-docs-core-hub | *HUB batch* beyond §3.7's table | HUB-023 |
| M-HUB-054 | services/core-hub/README.md:124 | Parameterized queries; ArchUnit at build time | invariant | link | INV-12; storage.md#6 | INV | legacy-docs-retirement | ArchUnit scope gap: *Defects* |  |
| M-HUB-055 | services/core-hub/README.md:125 | BigDecimal DTO, NUMERIC(4,3), double in Neo4j | requirement | link | CON; storage.md#8 | HUB | legacy-docs-retirement | |  |
| M-HUB-056 | services/core-hub/README.md:126 | Java 25 records, no Lombok | rationale | link | engineering/conventions.md | ENG | living-docs-engineering-workflow | |  |
| M-HUB-057 | services/core-hub/README.md:127 | Writes need write token; no CORS | requirement | link | http-api.md#1-2 | HUB | legacy-docs-retirement | duplicate of :69 |  |

### services/ingestion-scraper/config/sources.yaml (comments)

| Row | Source | Rule or content | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-ING-111 | services/ingestion-scraper/config/sources.yaml:1 | schedule is UTC cron; null means trigger-only | contract | link | operations/orchestration.md | OPS | living-docs-operations | comment stays |  |
| M-ING-112 | services/ingestion-scraper/config/sources.yaml:1-2 | Live sources start an hour apart, share one pool slot | requirement | link | operations/orchestration.md | OPS | living-docs-operations | |  |
| M-ING-113 | services/ingestion-scraper/config/sources.yaml:2 | rate_limit_rps is per host, per §6.5 | contract | link | connectors.md#5-6 | ING | living-docs-ingestion | comment's "§6.5" → ID at `legacy-docs-retirement` |  |
| M-ING-114 | services/ingestion-scraper/config/sources.yaml:3 | max_documents_per_run sized to the 3 h timeout | rationale | link | pipeline.md Rationale | ING | living-docs-ingestion | |  |
| M-ING-115 | services/ingestion-scraper/config/sources.yaml:4-133 | Entry values (rates, lookbacks, caps, vocabularies) | value | keep | sources.yaml | — | — | machine authority |  |

### config/models/*.yaml

| Row | Source | Rule or content | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-EXT-016 | config/models/registry.yaml:1-10 | Model entries and their fields | value | keep | registry.yaml | — | — | machine authority; extraction.md#9 names required fields |  |
| M-EXT-017 | config/models/registry.yaml:11 | deprecation_date set when provider announces end of life | requirement | ratify | extraction.md#9 | EXT | living-docs-ingestion | *ING batch*: deprecation warning (`extraction_backend.py:317-323`) | EXT-009 |
| M-EXT-018 | config/models/local_candidates.yaml:1-3 | Not loaded; register script copies entry plus live digest | requirement | link | extraction.md#9-10 | EXT | living-docs-ingestion | |  |
| M-EXT-019 | config/models/local_candidates.yaml:5-6 | num_ctx holds only with OLLAMA_CONTEXT_LENGTH ≥ num_ctx | trap | move | extraction.md Known traps | EXT | living-docs-ingestion | also root CLAUDE.md trap | docs/ingestion/extraction.md#known-traps |
| M-EXT-020 | config/models/local_candidates.yaml:37 | 4k-context build under a similar tag | trap | keep | local_candidates.yaml | — | — | config comment |  |
| M-EXT-021 | config/models/scores/ | Gate records, one per model, prompt, prefilter | value | keep | scores/ | — | — | machine authority; empty today (readiness is SETUP's) |  |

### Flyway migrations (policy comments)

| Row | Source | Rule or content | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-HUB-058 | services/core-hub/src/main/resources/db/migration/V1__signal_schema.sql:2 | Natural keys per §3.7; NUMERIC(4,3) per §10.3 | contract | keep | V1 (frozen) | HUB | living-docs-core-hub | cited by storage.md#3, #8 |  |
| M-HUB-059 | services/core-hub/src/main/resources/db/migration/V1__signal_schema.sql:53 | First observation wins for source_type | requirement | keep | V1 (frozen) | HUB | living-docs-core-hub | cited by storage.md#7 |  |
| M-COR-021 | services/core-hub/src/main/resources/db/migration/V1__signal_schema.sql:63 | Corroboration record with explicit supersession | requirement | keep | V1 (frozen) | COR | living-docs-core-hub | cited by corroboration.md#5 |  |
| M-COR-022 | services/core-hub/src/main/resources/db/migration/V2__corroboration_watermark.sql:1-2 | Watermark for incremental scan | history | keep | V2 (frozen) | — | — | dropped by V5 |  |
| M-HUB-060 | services/core-hub/src/main/resources/db/migration/V3__watchlist_schema.sql:7-9 | Single-user; multi-user path is one migration | requirement | keep | V3 (frozen) | HUB | living-docs-core-hub | cited by storage.md#13; at-risk class #12 |  |
| M-HUB-061 | services/core-hub/src/main/resources/db/migration/V4__company_level_fields.sql:1-2 | "schema 1.1"; nullable event_type/primary_company | stale | keep | V4 (frozen) | HUB | living-docs-core-hub | storage.md Known traps notes the stale version label |  |
| M-COR-023 | services/core-hub/src/main/resources/db/migration/V5__drop_corroboration_watermark.sql:1 | Scan works from pending signals | history | keep | V5 (frozen) | — | — | |  |

### docs/local-model-runbook.md (stays a runbook; requirements extracted)

| Row | Source | Rule or content | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-EXT-022 | runbook:7 | Ollama on the host; Docker cannot reach Metal | trap | link | `docs/operations/topology.md` Known traps (M-OPS-218) | — | living-docs-ingestion | extraction.md Known traps points here |  |
| M-EXT-023 | runbook:9-18 | Candidate table; clean window = cutoff + 3 months | rationale | keep | runbook | — | — | |  |
| M-EXT-024 | runbook:20 | Speed estimate; gpt-4o-mini fallback | status-note | keep | runbook | — | — | |  |
| M-EXT-025 | runbook:22 | Docker Desktop memory limit 8 GB | process | keep | runbook | — | — | memory budget is OPS (topology) |  |
| M-EXT-026 | runbook:31 | Ollama ignores per-request context; set server context | trap | link | extraction.md Known traps | EXT | living-docs-ingestion | procedure stays in runbook |  |
| M-EXT-027 | runbook:55 | Registry pins digest; re-pulled weights refused | requirement | link | extraction.md#10 | EXT | living-docs-ingestion | `test_extraction_backend.py::test_digest_mismatch_fails_at_startup` |  |
| M-EXT-028 | runbook:66 | evaluate_model prints precision, latency, estimate; writes latency record | requirement | link | extraction.md#13 | EXT | living-docs-ingestion | |  |
| M-EXT-029 | runbook:67 | Gate passes at is_signal precision ≥ 0.85 | requirement | move | extraction.md#13 | EXT | living-docs-ingestion | at-risk class #19; CHOICE "gate threshold and version labels aligned"; `test_local_model_integration.py::test_gate_record_passes_at_documented_precision_threshold` | EXT-013 |
| M-EXT-030 | runbook:67 | Service refuses model without passing record at active prompt/prefilter | requirement | move | extraction.md#12 | EXT | living-docs-ingestion | `test_extraction_backend.py::test_startup_refuses_model_without_passing_gate_record` | EXT-012 |
| M-EXT-031 | runbook:68 | Scripts run production's registry configuration | requirement | move | extraction.md#13 | EXT | living-docs-ingestion | `test_model_evaluation.py::test_evaluation_scripts_take_the_prompt_default_from_the_service` | EXT-013 |
| M-EXT-032 | runbook:72 | Model choice recorded as CHOICE from results | process | link | extraction.md#14 | EXT | living-docs-ingestion | |  |
| M-EXT-033 | runbook:92 | Unreachable server warns; digest checked before first extraction | requirement | link | extraction.md#10 | EXT | living-docs-ingestion | `test_local_model_integration.py::test_unreachable_model_server_warns_at_startup_and_checks_digest_on_first_extraction` |  |
| M-EXT-034 | runbook:92 | Failed extraction stays archived, counted failed | requirement | link | pipeline.md#3 | ING | living-docs-ingestion | `test_extraction_backend.py::test_model_server_unreachable_documents_stay_archived_and_not_published` |  |
| M-EXT-035 | runbook:94-106 | Commit records; memory budget table | process | keep | runbook | — | — | |  |

### Code-only rules surfaced by this domain (ratification items not covered above)

| Row | Source | Rule or content | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-EXT-036 | `services/ingestion-scraper/src/auspex_ingest/extraction_backend.py:199` | Content wrapped in BEGIN/END DOCUMENT markers | requirement | ratify | extraction.md#3 | EXT | living-docs-ingestion | *ING batch*; the "data, never instruction" half is divergent (M-EXT-006) | EXT-003 |
| M-EXT-037 | `services/ingestion-scraper/src/auspex_ingest/extraction_backend.py:96-102` | Digest read from Ollama `/api/tags` | requirement | ratify | extraction.md#10 | EXT | living-docs-ingestion | *ING batch*; CLAUDE.md trap says `ollama show` (stale) | EXT-010 |
| M-EXT-038 | `extraction_backend.py` registry checks | Required fields; moving alias and unknown model refused | requirement | ratify | extraction.md#9 | EXT | living-docs-ingestion | *ING batch*; `test_extraction_backend.py::test_moving_alias_rejected_at_startup` | EXT-009 |
| M-EXT-039 | `extraction_backend.py` ContextLengthError | Over-context prompt fails loudly | requirement | move | extraction.md#11 | EXT | living-docs-ingestion | archived spec extraction-backend; `::test_over_context_prompt_fails_loudly_not_truncated` | EXT-011 |
| M-EXT-040 | `extraction_backend.py` `build_extractor_from_env` | OpenAI-compatible endpoint via EXTRACTION_BASE_URL, registry parameters | requirement | ratify | extraction.md#20 | EXT | living-docs-ingestion | *ING batch*; `test_local_model_integration.py::test_instructor_client_uses_registry_mode_timeout_and_base_url` | EXT-020 |
| M-EXT-041 | `extractor.py` `resolve_trial_ids`, `EventType` | Unknown event_type → other; trial_ids rule | requirement | move | extraction.md#8 | EXT | living-docs-ingestion | CHOICE "event taxonomy…" item 3; `test_company_level_extraction.py::test_unknown_event_type_from_model_is_recorded_as_other` | EXT-008 |
| M-ING-116 | `services/ingestion-scraper/src/auspex_ingest/api.py:39-102` | /health, /sources, /ingest (404, 500), /reextract, /metrics | contract | ratify | pipeline.md#18 | ING | living-docs-ingestion | *ING batch*; `test_api.py::test_ingest_unknown_source_type_returns_404` | ING-039 |
| M-ING-117 | `services/ingestion-scraper/src/auspex_ingest/pipeline.py:~220` run log | Run summary lacks cursor before and after | requirement | divergent | pipeline.md#19 | ING | living-docs-ingestion | *Defects*; §12 :386 is the source | ING-040 |
| M-HUB-062 | `services/core-hub/src/main/java/dev/auspex/corehub/audit/RawAuditService.java:47` | Raw audit reads `ingested_at` | requirement | divergent | storage.md#12 | HUB | living-docs-core-hub | *Raw-pointer*; `RawAuditIT` uses a hand-written payload | HUB-038 |
| M-HUB-063 | `RawAuditService` | Malformed raw payload retried, not dead-lettered at once | requirement | divergent | consumption.md#4 | HUB | living-docs-core-hub | *Defects* | HUB-010 |
| M-HUB-064 | `services/core-hub/src/main/java/dev/auspex/corehub/corroboration/ScheduledCorroborationService.java:57-82` | Graph-only Signal after DLT; dual write without outbox | requirement | ratify | storage.md#4 | HUB | living-docs-core-hub | *HUB batch* (C14) | HUB-025 |
| M-COR-024 | `services/core-hub/src/main/java/dev/auspex/corehub/corroboration/ScheduledCorroborationService.java:57-76` | Corroborated event at-least-once; consumers dedup on hash | requirement | move | corroboration.md#10 | COR | living-docs-core-hub | untested, *Defects* (C8); shape/version → CON | COR-012 |
| M-COR-025 | `CorroborationScanner` entity key | entity_key = normalized name + ":" + label; one kind | requirement | ratify | corroboration.md#3 | COR | living-docs-core-hub | *HUB batch* | COR-004 |
| M-HUB-065 | `WriteTokenInterceptor` | Constant-time compare; 401 JSON; fails closed when unset | requirement | move | http-api.md#1 | HUB | living-docs-core-hub | CHOICE "login endpoint, write-token failure mode, path layout" item 3; `WriteTokenInterceptorTest::test_writes_are_refused_when_no_token_is_configured` | HUB-041 HUB-042 |
| M-HUB-066 | `application.yml` management exposure | Actuator health, info, prometheus outside /api | contract | ratify | http-api.md#7 | HUB | living-docs-core-hub | *HUB batch*; `MetricsIT::test_prometheus_endpoint_returns_200` | HUB-051 |

### the at-risk classes at-risk classes in this domain

| Row | Source | Rule or content | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-ING-118 | at-risk class #5 | Processed-marker semantics | requirement | move | pipeline.md#11 | ING | living-docs-ingestion | CHOICE "unchanged re-fetch skip with retry-safe markers"; `test_unchanged_refetch.py::test_failed_kafka_flush_marks_nothing_so_undelivered_signals_are_retried` | ING-032 |
| M-HUB-067 | at-risk class #6 | Graph edge replacement on rewrite | requirement | move | storage.md#11 | HUB | living-docs-core-hub | archived spec graph-relationship-replacement; `GraphRelationshipReplacementIT::graphAndPostgresHoldTheSameEntitiesAfterARewrite` | HUB-037 |
| M-HUB-068 | at-risk class #7 | Listener pause on store outage | requirement | move | consumption.md#7 | HUB | living-docs-core-hub | CHOICE "transient Kafka failures pause…"; `DeadLetterRecoveryIT::recordConsumedDuringANeo4jOutageIsStoredAfterRecovery` | HUB-013 |
| M-HUB-069 | at-risk class #7 | DLT replay via `corehub-dlt-replay` | requirement | move | consumption.md#10 | HUB | living-docs-core-hub | `DeadLetterRecoveryIT::replayDoesNotRepublishARecordTwice` | HUB-016 |
| M-ING-119 | at-risk class #8 | SEC budget, per-connector side (EDGAR rate, 403 stop) | requirement | move | connectors.md#6-7 | ING | living-docs-ingestion | CHOICE "SEC request budget across containers"; aggregate → OPS (`living-docs-operations/legacy-docs-retirement`) | ING-006 ING-007 |
| M-COR-026 | at-risk class #9 | Corroboration scorer formula | requirement | link | same as M-COR-018 | — | living-docs-core-hub | Duplicate of M-COR-018; the ID is carried there |  |
| M-HUB-070 | at-risk class #10 | Write token, no CORS, browser only talks to dashboard | requirement | move | http-api.md#1-2 | HUB | living-docs-core-hub | CHOICE "dashboard runs in the stack behind its own server layer"; dashboard.md links | HUB-041 HUB-043 |
| M-HUB-071 | at-risk class #12 | Single-user installation, no user_id | requirement | move | storage.md#13 | HUB | living-docs-core-hub | CHOICE "No user_id column; single-user installation, extensible" | HUB-039 |
| M-HUB-072 | at-risk class #13 | core-hub calls ClinicalTrials.gov directly | invariant | link | INV-4 exception in `docs/system/invariants.md` | INV | living-docs-system-and-contracts | CHOICE "core-hub calls ClinicalTrials.gov directly"; http-api.md#4 links |  |
| M-EXT-042 | at-risk class #19 | Extraction gate ≥ 0.85 and decision rule fixed in advance | requirement | move | extraction.md#13-14 | EXT | living-docs-ingestion | CHOICE "local model decision rule, fixed before the gate runs"; not the protocol's event-to-ticker 0.85 gate (EVA) | EXT-013 EXT-014 |

### DECISIONS.md CHOICE entries in this domain

| Row | Source (heading) | Rule or content | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-EXT-043 | 2026-08-15 — Step 0.0 — CHOICE — LLM provider changed from Anthropic to OpenAI | OpenAI SDK through instructor; gpt-4o default | history | link | extraction.md Rationale | EXT | living-docs-ingestion | history: superseded by the registry-driven backend; endpoint rule is extraction.md#20 |  |
| M-ING-120 | 2026-08-15 — Step 2.3 — CHOICE — Patent connector: PatentsView → Lens.org → EPO OPS (final) | EPO OPS; epo-app canonical stable across A1/B1 | requirement | move | connectors.md#12 | ING | living-docs-ingestion | binding | ING-018 |
| M-ING-121 | 2026-08-15 — Step 2.3 — CHOICE — Patent connector changed from Lens.org to EPO OPS | external_id is publication reference CC-NUM-KIND | requirement | move | connectors.md#12 | ING | living-docs-ingestion | binding (duplicate of M-ING-120) | ING-018 |
| M-ING-122 | 2026-08-15 — Step 0.0 — CHOICE — Ticker-restricted ingestion via pre-filter vocabulary (no architecture change) | Scope set by vocabulary; WATCHED_TICKERS, config/prefilter | history | link | pipeline.md Rationale | ING | living-docs-ingestion | history: vocabulary now per entry in sources.yaml; `config/prefilter/` deleted |  |
| M-ING-123 | 2026-08-15 — Step 0.0 — CHOICE — Watched tickers and initial pre-filter vocabulary | Eight tickers and their terms | history | delete | — | — | living-docs-ingestion | values now in sources.yaml |  |
| M-COR-027 | 2026-09-19 — Watchlist & alerts — CHOICE — Discord webhook transport | Discord webhook for alerts | history | keep | specs/hold/watchlist-alerts.md | — | living-docs-core-hub | unbuilt |  |
| M-COR-028 | 2026-09-19 — Watchlist & alerts — CHOICE — Entity-key-based watchlist, not ticker-based | watchlist_entries hold entity keys | history | delete | — | — | living-docs-core-hub | superseded: hold spec reads V3 tables |  |
| M-EXT-044 | 2026-09-19 — Historical backfill — CHOICE — Option A: local model for backfill, API model forward-only | Gate at ≥ 0.85; one-model corpus | requirement | move | extraction.md#13 | EXT | living-docs-ingestion | binding for the gate; lineage rule keeps living in specs/historical-backfill.md | EXT-013 |
| M-HUB-073 | 2026-09-20 — Watchlist backend — CHOICE — No user_id column; single-user installation, extensible | No user_id; one-migration path | requirement | move | storage.md#13 | HUB | living-docs-core-hub | binding | HUB-039 |
| M-HUB-074 | 2026-09-20 — Watchlist backend — CHOICE — core-hub calls ClinicalTrials.gov directly | Preview calls CT.gov; 5 s timeout | invariant | link | INV-4 exception in `docs/system/invariants.md` | INV | living-docs-system-and-contracts | binding |  |
| M-EXT-045 | 2026-09-20 — Option A hosting — CHOICE — A1 (MacBook) confirmed for Phase 4; A2/A3 deferred | Backfill on the Mac | history | delete | — | — | living-docs-ingestion | hosting note, no rule |  |
| M-HUB-075 | 2026-09-25 — Watchlist backend — CHOICE — live preview smoke test deferred | Live preview call deferred | history | delete | — | — | living-docs-core-hub | status only |  |
| M-ING-124 | 2026-10-07 — Live ingestion — CHOICE — unchanged re-fetch skip with retry-safe markers | Processed markers after final outcome and flush | requirement | move | pipeline.md#11 | ING | living-docs-ingestion | binding | ING-032 |
| M-EXT-046 | 2026-10-07 — Local model integration — CHOICE — gate threshold and version labels aligned | GATE_PRECISION 0.85; prompt from EXTRACTION_PROMPT_VERSION | requirement | move | extraction.md#7, #13 | EXT | living-docs-ingestion | binding; its `v1.0` label is superseded by Single-source cleanup (prompt `v1`) | EXT-007 EXT-013 |
| M-ING-125 | 2026-10-07 — EDGAR press-release content — CHOICE — filing index replaces the submissions lookup | Items 2.02/7.01/8.01; Exhibit 99.1; acceptance time UTC; ciks[0] | requirement | move | connectors.md#9, #11 | ING | living-docs-ingestion | binding; 4,000-char note → extraction.md#4 | ING-014 ING-017 |
| M-ING-126 | 2026-10-07 — Second-wave specs — CHOICE — structured filings bypass the LLM | Deterministic mapper path for Form 4, offerings | history | keep | specs/hold/structured-source-extraction.md | — | living-docs-ingestion | unbuilt (hold) |  |
| M-EXT-047 | 2026-10-07 — Company-level extraction — CHOICE — event taxonomy and identifier fields (schema 1.1) | event_type set, trial_ids rule, V4 columns, CT lead sponsor | requirement | move | extraction.md#8; storage.md#9; connectors.md#13; CON closed set | EXT | living-docs-ingestion | binding (split across EXT, HUB, ING, CON); "schema 1.1" and prompt v1.1 superseded by Single-source cleanup | EXT-008 |
| M-ING-127 | 2026-10-08 — Control-surface scoping — CHOICE — the watchlist is the single source for tracked tickers and terms | Watchlist feeds scraper config; versioned vocabulary | history | keep | specs/managed-ingestion-config.md | — | living-docs-ingestion | unbuilt; binding for that spec only |  |
| M-HUB-076 | 2026-10-08 — Control-surface scoping — CHOICE — dashboard runs in the stack behind its own server layer | Browser → dashboard only; no core-hub CORS; token on writes | requirement | move | http-api.md#1-2 | HUB | living-docs-core-hub | binding; BFF half is DSH (`living-docs-strategy-and-dashboard`) | HUB-041 HUB-043 |
| M-EXT-048 | 2026-10-08 — First run on the stack machine — CHOICE — local model decision rule, fixed before the gate runs | Eligibility and tie-break rule for the first model choice | requirement | move | extraction.md#14 | EXT | living-docs-ingestion | binding | EXT-014 |
| M-ING-128 | 2026-10-09 — Soak-test readiness — CHOICE — cursor after a run with failed documents | next_cursor never passes a failed document | requirement | move | pipeline.md#5 | ING | living-docs-ingestion | binding; DAG half → OPS | ING-026 |
| M-HUB-077 | 2026-10-09 — Soak-test readiness — CHOICE — transient Kafka failures pause instead of retrying longer | Pause on outage; 5 s/30 s back-off; replay endpoint | requirement | move | consumption.md#6, #7, #10 | HUB | living-docs-core-hub | binding | HUB-012 HUB-013 HUB-016 |
| M-ING-129 | 2026-10-09 — Soak-test readiness — CHOICE — SEC request budget across containers | EDGAR 4 + universe 5; EDGAR stops on 403 | requirement | move | connectors.md#6-7 | ING | living-docs-ingestion | binding; aggregate → operations/topology.md (`living-docs-operations`) | ING-006 ING-007 |
| M-HUB-078 | 2026-10-09 — Dashboard foundation — CHOICE — login endpoint, write-token failure mode, path layout | Item 3: write token fails closed | requirement | move | http-api.md#1 | HUB | living-docs-core-hub | binding for item 3; items 1, 2, 4, 5 are DSH (`living-docs-strategy-and-dashboard`) | HUB-041 |
| M-ING-130 | 2026-10-10 — Single-source cleanup — CHOICE — one version of each pre-rollout artifact | One prompt v1, schema 1.0, deleted duplicates | history | link | extraction.md Rationale | EXT | living-docs-ingestion | history: its effects are code and CON facts |  |
| M-EXT-049 | 2026-10-09 — Graph and connector wiring fixes — CHOICE — publish threshold default is 0.0, not the API's 0.5 | Threshold per entry, default 0.0 | requirement | move | extraction.md#2 | EXT | living-docs-ingestion | binding | EXT-002 |
| M-HUB-079 | 2026-10-09 — Graph and connector wiring fixes — CHOICE — ticker resolution details | Single-ticker match; back-fill by SEC title; failure logged | requirement | move | storage.md#10; http-api.md#4 | HUB | living-docs-core-hub | binding | HUB-034 HUB-047 |
| M-EXT-050 | 2026-10-09 — Graph and connector wiring fixes — CHOICE — calibrated publish thresholds before launch | Per-source calibration before launch | requirement | move | `docs/ingestion/extraction.md` item 21 | EXT | living-docs-ingestion | binding before launch; the calibration work itself stays in `specs/golden-set-expansion.md` | EXT-021 |
| M-HUB-080 | 2026-10-09 — Graph and connector wiring fixes — CHOICE — no VIA migration | Writer emits USES_MECHANISM; no rewrite | history | link | storage.md Rationale | HUB | living-docs-core-hub | rule itself is storage.md#9 (ArchUnit) |  |
| M-ING-131 | 2026-10-10 — Ingestion run reliability — CHOICE — schedule times, extraction cap and task timeout | Cap 150 sized to 3 h; schedules; timeout | requirement | move | pipeline.md#6 | ING | living-docs-ingestion | binding for the cap rule (value in sources.yaml); schedules and timeout → OPS | ING-027 |
| M-ING-132 | 2026-10-10 — Ingestion run reliability — CHOICE — rate limiter spaces requests evenly, with no burst | One-token bucket; even spacing | requirement | move | connectors.md#5 | ING | living-docs-ingestion | binding; `test_rate_limited_client.py::test_idle_time_does_not_bank_a_burst` | ING-005 |
| M-ING-133 | 2026-10-10 — Ingestion run reliability — CHOICE — a 403 on a filing index also stops the EDGAR run | Any SEC 403 ends the run | requirement | move | connectors.md#7 | ING | living-docs-ingestion | binding; `test_sec_edgar.py::test_index_403_stops_the_run_without_further_sec_requests` | ING-007 |
| M-ING-134 | 2026-10-10 — Ingestion run reliability — CHOICE — requirements §5 text follows the 2026-10-09 cursor decision | §5 text edited to the cursor rule | history | delete | — | — | living-docs-ingestion | doc-edit record |  |
| M-COR-029 | 2026-10-10 — Corroboration late arrivals — CHOICE — contract test signals are written pending, clear runs after the commit | Contract-test helpers write pending; clear after commit | requirement | move | corroboration.md#1, #8 | COR | living-docs-core-hub | binding | COR-001 COR-010 |
| M-COR-030 | 2026-10-10 — Consolidated code, strategy and BV audit — CHOICE — what becomes specs, what does not | Which audit findings became specs | history | delete | — | — | living-docs-core-hub | item 6 (no withdrawal of published corroborations) noted in corroboration.md Rationale |  |

### File-level summary

| Source file | Final role | Spec |
|---|---|---|
| `docs/requirements.md` §4, §5, §6, §7, §9, §11 (and §3.8–§3.10, §10.1/§10.3/§10.4 core-hub halves) | Non-normative § → ID index | `legacy-docs-retirement` (rows above feed it) |
| `services/ingestion-scraper/README.md` | Orientation, connectors table, adding-a-connector how-to, scripts table; every rule a link | `legacy-docs-retirement` |
| `services/core-hub/README.md` | Orientation and layout; every rule a link; commands link to `services/core-hub/AGENTS.md` | `legacy-docs-retirement` (commands: `agent-instruction-hierarchy`) |
| `services/ingestion-scraper/config/sources.yaml` | Machine authority for source values; comments unchanged | — |
| `config/models/registry.yaml`, `local_candidates.yaml`, `scores/` | Machine authority for models and gate records | — |
| Flyway `V1`–`V5` | Locked machine authority; comments frozen | — |
| `docs/local-model-runbook.md` | Runbook, unchanged path; links to `docs/ingestion/extraction.md` for the rules | ingestion (cites), `legacy-docs-retirement` (adds the link line) |
| `docs/ingestion/{connectors,pipeline,extraction}.md` | Owners for ING and EXT | ingestion |
| `docs/core-hub/{consumption,storage,corroboration,http-api}.md` | Owners for HUB and COR | core-hub |


## Research, strategy and dashboard (RES, EVA, STR, DSH)


Written against: `develop` @ `e51f742`. Sources were read from `/home/claude/auspex-baseline`. Namespaces: **RES, EVA, STR, DSH**. A row whose NS cell names another namespace links to an owner that another fragment writes. It is listed here so that every normative statement in these sources has a disposition.

**Targets:**
- RES: `market-data`, `universe`, `panels`, `simulation` and `backtesting` = `docs/research/<name>.md`.
- EVA: `evaluation` = `docs/research/evaluation-protocol.md`.
- STR: `contract`, `runtime`, `risk` and `trace` = `docs/strategy/{contract,runtime,risk,decision-trace}.md`.
- DSH: `dashboard` = `docs/dashboard.md`.

**Specs:**
- `research` = `specs/living-docs-research.md`;
- `strat` = `specs/living-docs-strategy-and-dashboard.md`;
- other specs by file name;
- `legacy` = `specs/legacy-docs-retirement.md`.

**Decision citations.** In the Decision cell, "PENDING — <title>" means the heading `## 2026-10-15 — Living docs — PENDING — <title>`, with the register's D-number in parentheses. Ratify rows go into one of the batches `## <date> — Living docs — PENDING — research ratification batch` or `… — strategy-and-dashboard ratification batch`, which the domain spec appends. "CHOICE <date> <topic> — <title>" stands for the full `DECISIONS.md` heading, and the DECISIONS table at the end gives each one verbatim.

**Values.** Values owned by a machine file are linked by file and key, never copied:
- `protocol.yaml`, `h*.yaml`, `registry.jsonl`;
- `config/universe/*.yaml`, `config/themes.yaml`, `config/strategies/registry.yaml`;
- `.env.example`.

**Machine-locked files are never edited by any spec:** `config/hypotheses/*`, `registry.jsonl`, `config/universe/rules.yaml` and `us_small_mid.yaml`.

### docs/requirements.md (§0.1, §0.3, §4.1 backtest clause, §6.7 research use, §8, §14 research items)

| Row | Source (path:line or §) | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-RES-001 | §0.1 (`requirements.md:11`) | System is a historical research instrument, not a live monitor | requirement | link | `docs/system/overview.md` | SYS | living-docs-system-and-contracts | Research-side consequence (forward paper and live trading gated by forward check) is EVA (M-EVA-048). FLAG `2026-09-20 Strategy layer — requirements.md §0.1 assumption flips at session 3` is history; `specs/live-trading.md` carries the §0.1 amendment |  |
| M-RES-002 | §0.3 (`:13`) | Bounded 24-month backfill is a prerequisite for the event backtest | requirement | link | `specs/historical-backfill.md` | — | legacy-docs-retirement | Plan-step text (`Step 4.0`, `Phase 4`) is history. Backfill scope now from `BACKFILL_SCOPE_START` (M-RES-031); live lookback is ING/OPS |  |
| M-RES-003 | §0.3 note (`:19`) | Forward-only collection yields too few corroborations for a backtest | rationale | move | backtesting (Rationale) | RES | living-docs-research | Non-normative |  |
| M-RES-004 | §4.1 (`:112`) | `corroborated_at = max(participant.published_date)` is the only field a backtest joins on | requirement | move | backtesting | RES | living-docs-research | Record definition is COR (`docs/core-hub/corroboration.md`); the join rule is RES. `alignment/aligner.py:10,32`; `test_point_in_time_alignment.py` |  |
| M-RES-005 | §4.1 (`:114`) | Superseded rows retained so the backtest reads the participant set as of a date | requirement | move | backtesting | RES | living-docs-research | Storage side is COR. at-risk class #2 also M-RES-160 |  |
| M-RES-006 | §6.7 (`:200`) | Non-public dates never used for point-in-time alignment | requirement | move | backtesting | RES | living-docs-research | Per-source mapping table stays ING (`docs/ingestion/connectors.md`); RES links it |  |
| M-RES-007 | §6.7 (`:206`) | Patent `filed_date` excluded from backtest joins | trap | link | `docs/ingestion/connectors.md` | ING | living-docs-ingestion | RES Known traps one-line link only |  |
| M-RES-008 | §8 (`:270`) | yfinance is the price source; unofficial, rate-limited, personal-use terms | requirement | move | market-data | RES | living-docs-research | Caveats move to Known traps (M-RES-020) |  |
| M-RES-009 | §8 (`:272`) | Every OHLCV series written to Parquet in MinIO once; backtests read the snapshot | requirement | move | market-data | RES | living-docs-research | `price_refresher.py`; `test_price_refresh.py` |  |
| M-RES-010 | §8 (`:272`) | Documented fallback: Stooq, daily OHLCV | requirement | move | market-data | RES | living-docs-research | Code falls back to Stooq (`prices/stooq.py`) |  |
| M-RES-011 | §8 heading (`:268`) | "Historical Price Data (Phase 4)" | history | delete | — | — | legacy-docs-retirement | Plan-phase label |  |
| M-RES-012 | §8 (`:272`) | "Fetch once" pattern applies to every fetched research document | requirement | move | panels | RES | living-docs-research | Generalised by every panel spec's "Requirements §8 pattern" constraint (M-RES-100) |  |
| M-RES-013 | §14 (`:412`) | UTC everywhere; free-tier-first tooling | requirement | link | `docs/system/overview.md` | SYS | living-docs-system-and-contracts | Research applies INV-9; free-only delisted prices is M-RES-041 |  |

### services/backtesting/README.md

| Row | Source (path:line or §) | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-RES-020 | `services/backtesting/README.md:85` and §8 | Yahoo rate limits; `auto_adjust` adjusts dividends; Stooq uses own symbols | trap | move | market-data (Known traps) | RES | living-docs-research | |  |
| M-RES-021 | `services/backtesting/README.md:85` | One append-only OHLCV snapshot per ticker, Yahoo then Stooq | requirement | move | market-data | RES | living-docs-research | Dup of M-RES-009/010; one ID |  |
| M-RES-022 | `services/backtesting/README.md:85` | Only settled bars stored: two hours after NYSE close, early closes included | requirement | move | market-data | RES | living-docs-research | archived `price-finality-and-split-availability`; CHOICE 2026-10-10 Price finality — edges. Delay value named, not copied |  |
| M-RES-023 | `services/backtesting/README.md:85` | Append only when response repeats last stored bar; else `SnapshotDiscontinuityError` | requirement | move | market-data | RES | living-docs-research | `test_price_finality.py` |  |
| M-RES-024 | `services/backtesting/README.md:85` | `adjusted_through` records share basis of the first download | requirement | move | market-data | RES | living-docs-research | |  |
| M-RES-025 | code `services/backtesting/src/auspex_backtesting/prices/price_fetcher.py:19-45` | Every snapshot carries `adjusted_through` and settled bars only | requirement | divergent | market-data | RES | living-docs-research | `scripts/fetch_prices.py` writes without either; `market_cap.py:36` then raises. PENDING — `defects found while scoping` (legacy `fetch_prices.py`) |  |
| M-RES-026 | `services/backtesting/README.md:37` | Split history `available`/`confirmed_empty`/`unavailable`, vouches to `covered_through` | requirement | move | market-data | RES | living-docs-research | `unavailable` never read as no splits |  |
| M-RES-027 | code `services/backtesting/src/auspex_backtesting/prices/price_refresher.py:34,59` | Each refresh includes the protocol benchmark and the EUR/USD pair | requirement | ratify | market-data | RES | living-docs-research | research ratification batch. List named by code, not copied |  |
| M-RES-028 | code `services/backtesting/src/auspex_backtesting/api.py:68-99` | Price service `GET /health`, `POST /prices/refresh`, `POST /universe/build` (409) | contract | ratify | market-data | RES | living-docs-research | `/health` code-only. Refresh and build endpoints are covered by archived specs (move) |  |
| M-RES-029 | `services/backtesting/README.md:87-97` | Price service metrics catalogue and alert thresholds | contract | link | `docs/operations/observability.md` | OPS | living-docs-operations | |  |
| M-RES-030 | `services/backtesting/README.md:7`, `services/backtesting/README.md:9-15` | Monthly members on first NYSE session of month, data public before it | requirement | move | universe | RES | living-docs-research | CHOICE 2026-10-08 Point-in-time universe — how the monthly list is derived, item 1 |  |
| M-RES-031 | `services/backtesting/README.md:9-15` | Rule values: SIC, exchanges, cap, liquidity, window | value | link | `config/universe/rules.yaml` | — | living-docs-research | Values not copied. README table deleted at cutover |  |
| M-RES-032 | `services/backtesting/README.md:17` | One biotech universe serves every study; build refuses late `PRICE_HISTORY_START` (409) | requirement | move | universe | RES | living-docs-research | CHOICE 2026-10-09 Point-in-time universe — one universe from 2014, item 2 |  |
| M-RES-033 | `services/backtesting/README.md:19` | Inputs are SEC bulk archives plus price snapshots | requirement | move | universe | RES | living-docs-research | SEC traps link ING; request budget link OPS |  |
| M-RES-034 | `services/backtesting/README.md:23` | One rules file per universe; no code names a universe; all-digit id refused | requirement | move | universe | RES | living-docs-research | CHOICE 2026-10-15 Filing text change score — second universe, items 2 and 6 |  |
| M-RES-035 | `services/backtesting/README.md:25-33` | Storage layout under `universe/{version}/`; month written once; listings and coverage rewritten | requirement | move | universe | RES | living-docs-research | |  |
| M-RES-036 | `services/backtesting/README.md:30` | Rules file pinned on first build; different file under same version refused | requirement | move | universe | RES | living-docs-research | at-risk class #16. `RulesVersionError`; `test_universe_store.py` |  |
| M-RES-037 | `services/backtesting/README.md:35` | Member row fields, `ticker_source`, exit reasons | contract | move | universe | RES | living-docs-research | |  |
| M-RES-038 | `services/backtesting/README.md:37` | Month needing unknown split history not written; next build retries | requirement | move | universe | RES | living-docs-research | CHOICE 2026-10-10 Price finality — edges |  |
| M-RES-039 | `services/backtesting/README.md:39` | `auspex_universe_build` DAG builds monthly and on first start | process | link | `docs/operations/orchestration.md` | OPS | living-docs-operations | |  |
| M-RES-040 | `services/backtesting/README.md:43-48` | Backtest trades only entry-month members; outside counted; windows bounded at delisting | requirement | move | backtesting | RES | living-docs-research | CHOICE 2026-10-08 Point-in-time universe — windows the prices do not cover |  |
| M-RES-041 | `services/backtesting/README.md:48` | Survivorship summary with −30%/0% delisting bound | requirement | move | backtesting | RES | living-docs-research | at-risk class #20. Bound values stay in code until registered: D F6 trap (M-EVA-060) |  |
| M-RES-042 | `services/backtesting/README.md:52-59` | Catalyst panel sources, known-at times, precision kept | requirement | move | panels | RES | living-docs-research | CHOICE 2026-10-09 Catalyst date panel — how documents become rows |  |
| M-RES-043 | `services/backtesting/README.md:61-66` | Catalyst rows append-only by disclosure quarter; documents kept once | requirement | move | panels | RES | living-docs-research | |  |
| M-RES-044 | `services/backtesting/README.md:68` | `as_of` returns latest row per catalyst; `binaries_between` takes aware datetimes | contract | move | panels | RES | living-docs-research | |  |
| M-RES-045 | `services/backtesting/README.md:70` | SEC 5 req/s, Federal Register 1 req/s; 403/429 ends run without retry | requirement | link | `docs/ingestion/connectors.md`; `docs/operations/orchestration.md` | ING | living-docs-research | SEC trap ING-owned; panel-specific stop rule stated in panels with link |  |
| M-RES-046 | `services/backtesting/README.md:74-81` | H10 index, cut, score, monthly read; one snapshot set per universe | requirement | move | panels | RES | living-docs-research | CHOICE 2026-10-15 Filing text change score |  |
| M-RES-047 | `services/backtesting/README.md:76` | Quarterly index stored once per finished quarter | requirement | move | panels | RES | living-docs-research | |  |
| M-RES-048 | `services/backtesting/README.md:78` | Change = 1 − cosine of term frequencies; known at later acceptance | requirement | move | panels | RES | living-docs-research | Tolerance values in code: D F6 trap |  |
| M-RES-049 | `services/backtesting/README.md:99-109` | Hash lock, shape check, `admit()` gate, promotable roles, forward-check branches | requirement | move | evaluation | EVA | living-docs-research | See protocol.yaml table |  |
| M-EVA-001 | `services/backtesting/README.md:101` | Locked files refused when changed; registry lines never edited | requirement | move | evaluation | EVA | living-docs-research | `test_preregistered_protocol.py`; `hypothesis.py` |  |
| M-EVA-002 | `services/backtesting/README.md:103` | Event-only fields refused on a portfolio hypothesis | requirement | move | evaluation | EVA | living-docs-research | |  |
| M-EVA-003 | `services/backtesting/README.md:104` | A hypothesis with `uses` is checked and promoted per use | requirement | move | evaluation | EVA | living-docs-research | |  |
| M-EVA-004 | `services/backtesting/README.md:105` | `admit()` refuses family without budget, over budget, disallowed role, instrument ceiling | requirement | move | evaluation | EVA | living-docs-research | CHOICE 2026-10-09 Slow-signal pre-registration — details, item 7 |  |
| M-EVA-005 | code `services/backtesting/src/auspex_backtesting/hypothesis.py:190-230` | Every evaluation path passes `admit()` and refuses `suspended` | requirement | divergent | evaluation | EVA | living-docs-research | `run_backtest` skips both. PENDING — `defects found while scoping`; D F3 |  |
| M-EVA-006 | `services/backtesting/README.md:106` | Filters, diagnostics, descriptive hypotheses never promoted | requirement | move | evaluation | EVA | living-docs-research | CHOICE 2026-10-07 Pre-registration — hypothesis triage |  |
| M-EVA-007 | `services/backtesting/README.md:108` | Forward check returns `invalid` on NaN/inf, negative SE, malformed months | requirement | move | evaluation | EVA | living-docs-research | archived `forward-check-input-validation` |  |
| M-EVA-008 | `services/backtesting/README.md:109` | H9 trade-date rule and component fallback from registered file | requirement | move | panels | RES | living-docs-research | Rule values in `h9.yaml` |  |
| M-EVA-009 | `services/backtesting/README.md:115` | Refusals before anything recorded: modified files, suspended, off-grid, no `N_BOOTSTRAP` | requirement | move | evaluation | EVA | living-docs-research | CHOICE 2026-10-10 Evaluation protocol — how the event evaluation reads the spec |  |
| M-EVA-010 | `services/backtesting/README.md:116` | Cells reserved before any price read, under lock with family budget check | requirement | move | evaluation | EVA | living-docs-research | CHOICE 2026-10-10 Consolidated audit, item 3 |  |
| M-EVA-011 | `services/backtesting/README.md:116` | Torn final ledger line dropped; other bad line stops reservations | requirement | move | evaluation | EVA | living-docs-research | |  |
| M-EVA-012 | `services/backtesting/README.md:117` | Last `promotion.holdout_months` not read; released only for promotable primary cell | requirement | move | evaluation | EVA | living-docs-research | Value by key |  |
| M-EVA-013 | `services/backtesting/README.md:118` | Market-model CAR vs benchmark, estimation window, clustered t, bootstrap | requirement | move | evaluation | EVA | living-docs-research | CHOICE 2026-10-07 Pre-registration — market-model; values in `abnormal_return.*`, `inference.*` |  |
| M-EVA-014 | `services/backtesting/README.md:119` | Result: primary cell, all cells, kill verdicts, walk-forward, holdout | contract | move | evaluation | EVA | living-docs-research | |  |
| M-EVA-015 | `services/backtesting/README.md:119` | Walk-forward segments are reported, never used for promotion | requirement | ratify | evaluation | EVA | living-docs-research | research ratification batch. Segment lengths in code: D F6 trap |  |
| M-RES-050 | `services/backtesting/README.md:125` | Score snapshot contract: path, columns, `known_at_max` before rebalance open | contract | move | backtesting | RES | living-docs-research | CHOICE 2026-10-11 Cross-sectional portfolio backtest, items 1–2 |  |
| M-RES-051 | `services/backtesting/README.md:128-129` | Hold bands, CIK tie-break, next-open fills, sells first, no borrowing | requirement | move | backtesting | RES | living-docs-research | |  |
| M-RES-052 | `services/backtesting/README.md:130` | `EqualRiskSizer` capped; remainder is cash, never renormalised | requirement | move | backtesting | RES | living-docs-research | CHOICE 2026-10-10 Consolidated audit, item 4 |  |
| M-RES-053 | `services/backtesting/README.md:131` | Four `CatalystGuard` modes; no data counted, never treated as clear | requirement | move | backtesting | RES | living-docs-research | |  |
| M-RES-054 | `services/backtesting/README.md:132` | Orders costed at tier size; below minimum ticket skipped and counted | requirement | move | backtesting | RES | living-docs-research | |  |
| M-RES-055 | `services/backtesting/README.md:133` | Delisted held name booked at −30% when prices stop early | requirement | move | backtesting | RES | living-docs-research | |  |
| M-RES-056 | `services/backtesting/README.md:135` | `PortfolioResult` fields | contract | move | backtesting | RES | living-docs-research | |  |
| M-EVA-016 | `services/backtesting/README.md:137-140` | Portfolio evaluation order: admit, reserve, tiers, verdict, holdout once | requirement | move | evaluation | EVA | living-docs-research | CHOICE 2026-10-11 Cross-sectional portfolio backtest, items 8–10 |  |
| M-EVA-017 | `services/backtesting/README.md:138` | In-sample `portfolio_kill_criteria` applied | requirement | move | evaluation | EVA | living-docs-research | Values by key |  |
| M-EVA-018 | `services/backtesting/README.md:139` | Deflated Sharpe with family trial count; only primary cell of promotable passes | requirement | move | evaluation | EVA | living-docs-research | |  |
| M-EVA-019 | `services/backtesting/README.md:140` | Holdout read once per use; `HoldoutRecord` created exclusively | requirement | move | evaluation | EVA | living-docs-research | |  |
| M-EVA-020 | `services/backtesting/README.md:140` | Final run refused until input manifests exist | requirement | move | evaluation | EVA | living-docs-research | `NoInputManifests`; `specs/research-input-archive.md` owns the change |  |
| M-RES-057 | `services/backtesting/README.md:144-146` | Ownership reads as of an instant: `filing_accepted_at`, never period or trade date | requirement | move | panels | RES | living-docs-research | at-risk class #17 |  |
| M-RES-058 | `services/backtesting/README.md:146` | Bulk data acceptance time = 22:00 US Eastern on filing date | requirement | move | panels | RES | living-docs-research | CHOICE 2026-10-09 SEC ownership — acceptance time from a filing date |  |
| M-RES-059 | `services/backtesting/README.md:150-154` | Ownership readers and their missing reasons | contract | move | panels | RES | living-docs-research | |  |
| M-RES-060 | `services/backtesting/README.md:156` | Shares restated to read date's split basis, else missing with reason | requirement | move | panels | RES | living-docs-research | archived `ownership-share-basis` |  |
| M-RES-061 | `services/backtesting/README.md:158` | Healthcare specialist definition; thresholds from registered `h9.yaml` | requirement | move | panels | RES | living-docs-research | Target of the frozen `#SpecialistClassifier` pointer; CHOICE 2026-10-09 SEC ownership — specialist thresholds |  |
| M-RES-062 | `services/backtesting/README.md:160-170` | Ownership object layout, write-once except share counts | contract | move | panels | RES | living-docs-research | |  |
| M-RES-063 | `services/backtesting/README.md:168` | Daily Form 4 fills until data set exists; data set preferred, disagreement logged | requirement | move | panels | RES | living-docs-research | |  |
| M-RES-064 | `services/backtesting/README.md:172` | Data sets labelled as SEC names them; CUSIP→CIK by name; unmapped counted | requirement | move | panels | RES | living-docs-research | CHOICE 2026-10-09 SEC ownership — how filings are counted |  |
| M-RES-065 | `services/backtesting/README.md:174` | `fetch_ownership.py` backfills once; panels refreshed by script, not DAG | trap | move | panels (Known traps) | RES | living-docs-research | FLAG 2026-10-09 SEC ownership — panels refreshed by a script |  |
| M-RES-066 | `services/backtesting/README.md:178-182` | Short interest known by end of FINRA publication day, never settlement | requirement | move | panels | RES | living-docs-research | at-risk class #17; CHOICE 2026-10-10 Short interest — publication dates |  |
| M-RES-067 | `services/backtesting/README.md:183` | Share and change restated to one split basis or missing | requirement | move | panels | RES | living-docs-research | CHOICE 2026-10-11 Short interest — one split basis |  |
| M-RES-068 | `services/backtesting/README.md:185` | `days_to_cover` exact ratio; `None` at zero volume; unreported stored `reported=false` | requirement | move | panels | RES | living-docs-research | |  |
| M-RES-069 | `services/backtesting/README.md:187` | Periods only appended, never rewritten | requirement | move | panels | RES | living-docs-research | |  |
| M-RES-070 | `services/backtesting/README.md:189` | Listed coverage from June 2021; H9 uses two-component variant before | requirement | move | panels | RES | living-docs-research | Start date value in `.env.example` (`SHORT_INTEREST_HISTORY_START`) |  |
| M-RES-071 | `services/backtesting/README.md:193-203` | H9 components, floor, two-component minimum, write-once snapshots | requirement | move | panels | RES | living-docs-research | CHOICE 2026-10-15 Holdings composite score |  |
| M-RES-072 | `services/backtesting/README.md:205-217` | Scripts table | command | keep | `services/backtesting/README.md` | — | living-docs-research | READMEs keep commands; docs link |  |
| M-RES-073 | `services/backtesting/README.md:219-226` | Commands table | command | keep | `services/backtesting/README.md` | — | living-docs-research | |  |
| M-RES-074 | `services/backtesting/README.md:3` | Module scope summary | status-note | keep | `services/backtesting/README.md` | — | living-docs-research | README becomes orientation plus a link per section to its RES/EVA file |  |

### services/strategy/README.md

| Row | Source (path:line or §) | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-STR-001 | `services/strategy/README.md:5-13` | Install, test, lint, kill-switch CLI, image commands | command | keep | `services/strategy/README.md` | — | living-docs-strategy-and-dashboard | Kill-switch CLI runs without Docker: STR requirement (M-STR-030) |  |
| M-STR-002 | `services/strategy/README.md:19` | Replay runs research-or-above; paper-or-above intents to risk; backtest books only | requirement | move | runtime | STR | living-docs-strategy-and-dashboard | archived `strategy-runtime`; `test_backtest_replay_is_deterministic` |  |
| M-STR-003 | `services/strategy/README.md:20` | Streaming consumes corroborated topic in own group; checkpoint after each event | requirement | move | runtime | STR | living-docs-strategy-and-dashboard | CHOICE 2026-09-20 Event-driven Kafka consumer; CHOICE 2026-10-10 Strategy runtime item 5 |  |
| M-STR-004 | code `services/strategy/src/auspex_strategy/runtime/streaming.py:189-208`, `services/strategy/src/auspex_strategy/runtime/book.py:137-151`, `services/strategy/src/auspex_strategy/risk/flow.py:22,43` | Restart re-processing books no second order; loss state survives restart | requirement | divergent | runtime | STR | living-docs-strategy-and-dashboard | Applies INV-10. FLAG 2026-10-10 Strategy runtime — live data channel; PENDING — `defects found while scoping`; E F6 |  |
| M-STR-005 | code `services/strategy/src/auspex_strategy/runtime/streaming.py:200-207` | Unreadable payload never blocks and never vanishes without a record | requirement | divergent | runtime | STR | living-docs-strategy-and-dashboard | INV-11; no DLT. CHOICE 2026-10-10 Strategy runtime item 5; PENDING — `can a DECISIONS entry narrow an invariant`; E F7 |  |
| M-STR-006 | `services/strategy/README.md:21` | `IsolatedDecider`: crash, timeout, invalid intent counted per strategy | requirement | move | runtime | STR | living-docs-strategy-and-dashboard | Timeout in streaming only; CHOICE 2026-10-10 Strategy runtime item 4 |  |
| M-STR-007 | `services/strategy/README.md:21` | Intent ids deterministic | requirement | move | trace | STR | living-docs-strategy-and-dashboard | at-risk class #14; M-STR-060 |  |
| M-STR-008 | `services/strategy/README.md:22` | Input health polled; unhealthy input pauses declaring strategies; no answer unhealthy | requirement | move | runtime | STR | living-docs-strategy-and-dashboard | `test_stale_input_source_pauses_strategy` |  |
| M-STR-009 | code `services/strategy/src/auspex_strategy/runtime/health.py:17`; no route in core-hub `src/main`; `docker/docker-compose.yml:537` | Core-hub serves `/api/v1/health/inputs` | requirement | divergent | runtime | STR | living-docs-strategy-and-dashboard | Provider contract is HUB (`docs/core-hub/http-api.md`). FLAG 2026-10-10 Strategy runtime; E F4. Compose comment is stale (M-STR-090) |  |
| M-STR-010 | `services/strategy/README.md:23` | Overlapping intents across strategies flagged | requirement | move | runtime | STR | living-docs-strategy-and-dashboard | |  |
| M-STR-011 | `services/strategy/README.md:24` | Latency recorded per intent; startup warning when median exceeds delay | requirement | move | runtime | STR | living-docs-strategy-and-dashboard | |  |
| M-STR-012 | `services/strategy/README.md:25` | Paper fills at next open; exits by rule or stop; costs and FX as simulation | requirement | move | runtime | STR | living-docs-strategy-and-dashboard | Links `docs/research/simulation.md`; `test_virtual_book_pnl_matches_market_simulation` |  |
| M-STR-013 | `services/strategy/README.md:26` | `RiskManager` protocol: one `RiskDecision` per intent with every check | contract | move | risk | STR | living-docs-strategy-and-dashboard | CHOICE 2026-10-11 Decision trace item 3 |  |
| M-STR-014 | `services/strategy/README.md:27`, code `services/strategy/src/auspex_strategy/runtime/main.py:150` | Streaming runtime reviews every intent through `RiskManager`; exits executed | requirement | divergent | risk | STR | living-docs-strategy-and-dashboard | Pass-through stub in production. FLAG 2026-10-11 Portfolio and risk — runtime still sizes with the pass-through stub; E F3 |  |
| M-STR-015 | `services/strategy/README.md:28` | Funnel counted per version and mode | requirement | move | runtime | STR | living-docs-strategy-and-dashboard | |  |
| M-STR-016 | `services/strategy/README.md:34` | `TraceRecord` fields, one `DocumentRecord` per participant | contract | move | trace | STR | living-docs-strategy-and-dashboard | at-risk class #14 |  |
| M-STR-017 | `services/strategy/README.md:35` | One validator for every mode; names each missing field | requirement | move | trace | STR | living-docs-strategy-and-dashboard | |  |
| M-STR-018 | `services/strategy/README.md:36` | `TraceStore` append-only JSONL | requirement | move | trace | STR | living-docs-strategy-and-dashboard | |  |
| M-STR-019 | `services/strategy/README.md:38` | Replay reproduces every field but `trace_id`, `approved_at`, `fill_time` | requirement | move | trace | STR | living-docs-strategy-and-dashboard | |  |
| M-STR-020 | `services/strategy/README.md:40` | Paper and live decisions are traced | requirement | divergent | trace | STR | living-docs-strategy-and-dashboard | Only backtests traced. CHOICE 2026-10-11 Decision trace (Action); FLAG 2026-10-10 Strategy runtime |  |
| M-STR-021 | `services/strategy/README.md:42` | Known-at delay from registered hypothesis `primary_cell.known_at_delay_days` | requirement | move | contract | STR | living-docs-strategy-and-dashboard | CHOICE 2026-10-10 Strategy runtime item 2 |  |
| M-STR-022 | `services/strategy/README.md:46` | Limits from `.env`; startup fails when missing or looser than protocol | requirement | move | risk | STR | living-docs-strategy-and-dashboard | CHOICE 2026-10-11 Portfolio and risk item 1 |  |
| M-STR-023 | `services/strategy/README.md:46` | Shorts rejected while protocol disables them | requirement | move | risk | STR | living-docs-strategy-and-dashboard | `protocol.yaml` `instruments` by key |  |
| M-STR-024 | `services/strategy/README.md:50` | Quarter Kelly shrinks `p`; fallback below minimum trades; per-name cap | requirement | move | risk | STR | living-docs-strategy-and-dashboard | CHOICE 2026-10-07 Pre-registration — sizing ceilings; CHOICE 2026-09-20 Minimum 20 trades |  |
| M-STR-025 | `services/strategy/README.md:51` | One position per theme; unmapped ticker rejected | requirement | move | risk | STR | living-docs-strategy-and-dashboard | at-risk class #15; `themes.yaml:3-4` |  |
| M-STR-026 | `services/strategy/README.md:52` | Binary-event guard from catalyst panel; never waived for shorts | requirement | move | risk | STR | living-docs-strategy-and-dashboard | CHOICE 2026-10-11 Portfolio and risk items 2–4 |  |
| M-STR-027 | `services/strategy/README.md:53` | Short guard ceilings; hard stop and EUR loss cap as exits | requirement | move | risk | STR | living-docs-strategy-and-dashboard | |  |
| M-STR-028 | `services/strategy/README.md:54` | Daily loss blocks the day; turnover ceiling; drawdown triggers global kill | requirement | move | risk | STR | living-docs-strategy-and-dashboard | |  |
| M-STR-029 | `services/strategy/README.md:55` | Kill switch global or per strategy; open positions keep exits | requirement | move | risk | STR | living-docs-strategy-and-dashboard | |  |
| M-STR-030 | `services/strategy/README.md:12` | Kill switch set and reset from CLI without Docker | requirement | move | runtime | STR | living-docs-strategy-and-dashboard | |  |
| M-STR-031 | `services/strategy/README.md:56` | Check order; first failure rejects; every check recorded | requirement | move | risk | STR | living-docs-strategy-and-dashboard | at-risk class #15; CHOICE 2026-10-11 Portfolio and risk item 9 |  |
| M-STR-032 | `services/strategy/README.md:57` | Kill switch, drawdown, daily loss map to `PAUSED`; approvals counted forward | requirement | move | risk | STR | living-docs-strategy-and-dashboard | |  |
| M-STR-033 | `services/strategy/README.md:59-71` | State only in `auspex-strategy` bucket, key layout | requirement | move | runtime | STR | living-docs-strategy-and-dashboard | CHOICE 2026-09-20 MinIO for virtual books; Strategy runtime item 1 |  |
| M-STR-034 | `services/strategy/README.md:64`, `services/strategy/README.md:71` | Keys `funnel/` and `risk/catalyst_holds.jsonl` | contract | ratify | runtime | STR | living-docs-strategy-and-dashboard | strategy-and-dashboard ratification batch: no archived spec names them |  |
| M-STR-035 | `services/strategy/README.md:63` | Book rows append-only, carry `strategy_version`; trade belongs to opening version | requirement | move | runtime | STR | living-docs-strategy-and-dashboard | CHOICE 2026-10-11 Strategy metrics item 1 |  |
| M-STR-036 | `services/strategy/README.md:75` | Metrics computed on request, never stored; one version in one mode | requirement | move | runtime | STR | living-docs-strategy-and-dashboard | |  |
| M-STR-037 | `services/strategy/README.md:79-84` | Funnel, trade, return, comparison, correlation, latency metrics | contract | move | runtime | STR | living-docs-strategy-and-dashboard | Abnormal return model links EVA |  |
| M-STR-038 | `services/strategy/README.md:86` | Every group carries `n`; below minimum, `insufficient_data` with nulls | requirement | move | runtime | STR | living-docs-strategy-and-dashboard | Minimum in `.env.example` (`MIN_TRADES_FOR_METRICS`) |  |
| M-STR-039 | `services/strategy/README.md:81`, `services/strategy/README.md:86` | Deflated Sharpe uses family trial count read without lock | requirement | move | runtime | STR | living-docs-strategy-and-dashboard | Links EVA ledger |  |
| M-STR-040 | `services/strategy/README.md:90-96` | HTTP `/health`, `/metrics`, `/api/v1/metrics/*` on runtime port | contract | move | runtime | STR | living-docs-strategy-and-dashboard | Port and host exposure link OPS topology |  |
| M-STR-041 | code `services/strategy/src/auspex_strategy/runtime/http.py:91`; `services/dashboard/src/lib/bff.ts:13-15` | Strategy API has no auth and no dashboard route | status-note | move | runtime (Scope) | STR | living-docs-strategy-and-dashboard | E F14 |  |

### services/dashboard/README.md

| Row | Source (path:line or §) | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-DSH-001 | `services/dashboard/README.md:3` | Dashboard in compose `app` profile on `DASHBOARD_PORT` | value | link | `docs/operations/topology.md`; `.env.example` | OPS | living-docs-operations | |  |
| M-DSH-002 | `services/dashboard/README.md:7` | Browser calls only dashboard origin; handlers hold no logic, touch no datastore | requirement | move | dashboard | DSH | living-docs-strategy-and-dashboard | CHOICE 2026-10-08 Control-surface — dashboard runs in the stack behind its own server layer. at-risk class #10 dashboard half |  |
| M-DSH-003 | `services/dashboard/README.md:11` | `/api/health` needs no session | requirement | move | dashboard | DSH | living-docs-strategy-and-dashboard | |  |
| M-DSH-004 | `services/dashboard/README.md:12` | Single-user login; bcrypt hash; signed `HttpOnly`, `SameSite=Strict` cookie | requirement | move | dashboard | DSH | living-docs-strategy-and-dashboard | CHOICE 2026-10-09 Dashboard foundation items 1, 4, 5; `auth.test.ts` |  |
| M-DSH-005 | `services/dashboard/README.md:13` | Bearer write token on every core-hub non-GET | requirement | link | `docs/core-hub/http-api.md` | HUB | living-docs-core-hub | Dashboard half stated in DSH, owner is HUB |  |
| M-DSH-006 | `services/dashboard/README.md:14` | Scraper and price writes forwarded without token (localhost threat model) | requirement | ratify | dashboard | DSH | living-docs-strategy-and-dashboard | strategy-and-dashboard ratification batch; archived `dashboard-foundation` Out of scope |  |
| M-DSH-007 | `services/dashboard/README.md:16` | Error shape; lists wrapped; failing upstream 502 | contract | move | dashboard | DSH | living-docs-strategy-and-dashboard | `bff.test.ts` |  |
| M-DSH-008 | `services/dashboard/README.md:16` | `proxy.ts` sole authorization point; pages redirect, API 401 | requirement | move | dashboard | DSH | living-docs-strategy-and-dashboard | |  |
| M-DSH-009 | `services/dashboard/README.md:18` | Components use `src/lib/api.ts` only; no `NEXT_PUBLIC_*` backend setting | requirement | move | dashboard | DSH | living-docs-strategy-and-dashboard | `api-client.test.ts`, `bundle-secrets.test.ts` |  |
| M-DSH-010 | `services/dashboard/README.md:22-28` | Configuration variables | value | link | `.env.example` | — | living-docs-strategy-and-dashboard | README keeps the table as orientation |  |
| M-DSH-011 | `services/dashboard/README.md:30-41` | Commands | command | keep | `services/dashboard/README.md` | — | living-docs-strategy-and-dashboard | |  |
| M-DSH-012 | `services/dashboard/README.md:43` | CI runs all, audits deps, checks container login and gate | process | link | `docs/engineering/verification.md` | ENG | living-docs-engineering-workflow | |  |
| M-DSH-013 | code `services/dashboard/src/lib/bff.ts:48` | BFF never forwards outside upstream base path | requirement | move | dashboard | DSH | living-docs-strategy-and-dashboard | Status `untested` (E F17); CHOICE 2026-10-09 Dashboard foundation item 2 |  |
| M-DSH-014 | code `services/dashboard/src/lib/bff.ts:68` | Upstream timeout | requirement | ratify | dashboard | DSH | living-docs-strategy-and-dashboard | strategy-and-dashboard ratification batch |  |
| M-DSH-015 | code `lib/credentials.ts` | Hash compared even for unknown username | requirement | ratify | dashboard | DSH | living-docs-strategy-and-dashboard | strategy-and-dashboard ratification batch |  |
| M-DSH-016 | root `CLAUDE.md` traps | bcrypt `$` in `.env`; Next 16 `proxy`; no `next lint` | trap | move | dashboard (Known traps) | DSH | living-docs-strategy-and-dashboard | Also in root CLAUDE.md (`living-docs-system-and-contracts`/`living-docs-operations/legacy-docs-retirement` agent rows) |  |
| M-DSH-017 | E F18 | Route handlers do not re-check session | trap | move | dashboard (Known traps) | DSH | living-docs-strategy-and-dashboard | |  |
| M-DSH-018 | CHOICE 2026-10-08 Control-surface — research config read-only | Dashboard shows research config read-only | requirement | link | evaluation | EVA | living-docs-strategy-and-dashboard | Owner EVA (M-EVA-030) |  |
| M-DSH-019 | CHOICE 2026-10-08 Control-surface — Grafana for technical health | Technical health is Grafana's; dashboard is for using the application | requirement | move | dashboard (Scope) | DSH | living-docs-strategy-and-dashboard | Links OPS observability |  |
| M-DSH-020 | archived `dashboard.md`, `watchlist-ui.md` | `NEXT_PUBLIC_API_URL` browser-to-backend calls | stale | delete | — | — | living-docs-strategy-and-dashboard | Superseded by BFF; archive keeps it as history |  |
| M-DSH-021 | — | No CORS on core-hub | requirement | link | `docs/core-hub/http-api.md` | HUB | living-docs-core-hub | at-risk class #10 |  |

### docs/strategy-research.md (rationale; stays in place, frozen path)

| Row | Source (path:line or §) | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-EVA-021 | `docs/strategy-research.md:11` | "These are invariants for all hypotheses" | stale | keep | `docs/strategy-research.md` | — | legacy-docs-retirement | Labelled non-normative in `docs/README.md`; binding parts live in `protocol.yaml` and EVA |  |
| M-EVA-022 | `docs/strategy-research.md:14-18` | Capital, friction estimate, ≥5% target abnormal return | rationale | keep | `docs/strategy-research.md` | — | living-docs-research | Capital tiers are `PAPER_CAPITAL_TIERS_EUR`; cost model is RES simulation |  |
| M-EVA-023 | `docs/strategy-research.md:21-25` | Belgian TOB, CGT, speculative-classification risk; do not short | rationale | keep | `docs/strategy-research.md` | — | living-docs-research | TOB rate value lives in `.env.example`; short ban enforced by `protocol.yaml` `instruments` (M-STR-023). FLAG 2026-09-20 Belgian speculative classification stays open |  |
| M-EVA-024 | `docs/strategy-research.md:28-29` | XBI primary benchmark; size-matched secondary | value | link | `protocol.yaml` `abnormal_return.benchmark` | — | legacy-docs-retirement | Copy of a registered value; superseded CHOICE (history) |  |
| M-EVA-025 | `docs/strategy-research.md:32` | Join on `corroborated_at`; never `ingested_at`; default delay 1 day | rationale | keep | `docs/strategy-research.md` | — | living-docs-research | Rules owned by M-RES-004, M-STR-021; delay by `h*.yaml` |  |
| M-EVA-026 | `docs/strategy-research.md:35-38` | 24-month window, 8 companies, 50–150 events | history | keep | `docs/strategy-research.md` | — | living-docs-research | Stale scope (universe replaced watchlist); `legacy-docs-retirement` adds the banner and replaces copied values with links |  |
| M-EVA-027 | `docs/strategy-research.md:42-207` | H1–H8 reasoning | rationale | keep | `docs/strategy-research.md` | — | living-docs-research | Registered definitions are `h*.yaml` |  |
| M-EVA-028 | `docs/strategy-research.md:209-237` | Triage roles and statuses, slow-signal table, family budgets | value | link | `config/hypotheses/h*.yaml`; `protocol.yaml` `families` | — | legacy-docs-retirement | Copied values; drift risk noted |  |
| M-EVA-029 | `docs/strategy-research.md:241-257` | What the 24-month backfill allows | history | keep | `docs/strategy-research.md` | — | living-docs-research | Superseded by edge research synthesis CHOICE (history) |  |

### config/hypotheses/protocol.yaml and h*.yaml (machine-locked; never edited)

| Row | Source (path:line or §) | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-EVA-030 | CHOICE 2026-10-08 Control-surface — research config read-only | Hypotheses, protocol, strategy and model registries, universe rules: read-only, dated re-registration | requirement | move | evaluation | EVA | living-docs-research | at-risk class #11 owner. Trap: `registry.py:134-142` writes `config/strategies/versions/` |  |
| M-EVA-031 | `config/hypotheses/protocol.yaml:4-11` | `abnormal_return.*` | value | keep | `protocol.yaml` | — | living-docs-research | EVA cites by key |  |
| M-EVA-032 | `config/hypotheses/protocol.yaml:12-22` | `inference.*` | value | keep | `protocol.yaml` | — | living-docs-research | `N_BOOTSTRAP` vs `inference.bootstrap_draws`: D F6 trap |  |
| M-EVA-033 | `config/hypotheses/protocol.yaml:23-32` | `trials.*` | value | keep | `protocol.yaml` | — | living-docs-research | |  |
| M-EVA-034 | `config/hypotheses/protocol.yaml:33-34` comment | Family named by hypothesis; unlisted family has no budget | requirement | move | evaluation | EVA | living-docs-research | Enforced by `admit()` |  |
| M-EVA-035 | `config/hypotheses/protocol.yaml:35-55` | `families.*`, budgets, roles, `default_event_family` | value | keep | `protocol.yaml` | — | living-docs-research | |  |
| M-EVA-036 | `config/hypotheses/protocol.yaml:40-42` comment | H10 filter cells reserved when the filter is applied | requirement | divergent | evaluation | EVA | living-docs-research | `--filter-score` does not reserve. PENDING — `defects found while scoping`; D F5 |  |
| M-EVA-037 | `config/hypotheses/protocol.yaml:56-67` | `portfolio_inference.*`; month is the unit | value | keep | `protocol.yaml` | — | living-docs-research | |  |
| M-EVA-038 | `portfolio_inference.holdout_reads` | Trial ledger and holdout records durable and shared across checkouts | requirement | divergent | evaluation | EVA | living-docs-research | Untracked local files (`.gitignore:52`; `verdict.py:308-336`). PENDING — `trial ledger and holdout as untracked local files` |  |
| M-EVA-039 | `config/hypotheses/protocol.yaml:68-72` | `promotion.*` | value | keep | `protocol.yaml` | — | living-docs-research | |  |
| M-EVA-040 | `config/hypotheses/protocol.yaml:73-83` | `sizing.*` ceilings | value | keep | `protocol.yaml` | — | living-docs-strategy-and-dashboard | STR risk cites by key |  |
| M-EVA-041 | `config/hypotheses/protocol.yaml:84-87` | Instruments are ceilings; enabling is re-registration, never `.env` | requirement | move | evaluation | EVA | living-docs-research | |  |
| M-EVA-042 | `config/hypotheses/protocol.yaml:88-164` | `kill_criteria`, `portfolio_kill_criteria` | value | keep | `protocol.yaml` | — | living-docs-research | |  |
| M-EVA-043 | `config/hypotheses/h9.yaml:18` | Cites `specs/sec-ownership-datasets.md#SpecialistClassifier` | contract | keep | `h9.yaml` | — | living-docs-research | Frozen path; spec keeps an anchored pointer line. PENDING — `spec paths cited by hash-locked hypotheses` |  |
| M-EVA-044 | `config/hypotheses/h11.yaml:8`, `config/hypotheses/h12.yaml:8` | Cite `specs/clinicaltrials-version-diffs.md`, `specs/catalyst-date-panel.md` | contract | keep | `h11.yaml`, `h12.yaml` | — | living-docs-research | Never moved or renamed (`spec paths cited by hash-locked hypotheses`) |  |
| M-EVA-045 | `services/backtesting/tests/unit/test_preregistered_protocol.py:440` | Asserts the h9 spec string | contract | keep | test | — | living-docs-research | |  |
| M-EVA-046 | `registry.jsonl` | Append-only hash registry | value | keep | `registry.jsonl` | — | living-docs-research | |  |
| M-EVA-047 | raw-byte hash (`hypothesis.py`) | Whitespace edit is a new registration | trap | move | evaluation (Known traps) | EVA | living-docs-research | |  |
| M-EVA-048 | CHOICE 2026-10-07 Second-wave — paper trading gates capital | No real capital until a forward check passes at a tier | requirement | move | evaluation | EVA | living-docs-research | Also CHOICE 2026-10-08 Edge research — portfolio paper-trading pass rule |  |
| M-EVA-049 | FLAG 2026-09-19 Phase 4 v2 | Entity-only variant reported beside full variant in all research output | requirement | move | evaluation | EVA | living-docs-research | at-risk class #3 owner; archived `backtesting`, `performance-metrics` |  |
| M-EVA-050 | CHOICE 2026-10-07 Pre-registration — trials as cells | Cells counted across the family; failed run still counts | requirement | move | evaluation | EVA | living-docs-research | |  |
| M-EVA-051 | code `services/backtesting/src/auspex_backtesting/portfolio/rules.py:76-110` | Off-grid cells refused | requirement | divergent | evaluation | EVA | living-docs-research | Event runs `tested`; portfolio `divergent` (D F5). PENDING — `defects found while scoping` |  |
| M-EVA-052 | code `services/backtesting/src/auspex_backtesting/evaluation/results.py:240-270` | Event holdout has a persistent read record | requirement | divergent | evaluation | EVA | living-docs-research | Under the `trial ledger and holdout as untracked local files` row M-EVA-038 |  |

### config/universe/rules.yaml and us_small_mid.yaml (machine-locked; never edited)

| Row | Source (path:line or §) | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-RES-080 | `config/universe/rules.yaml:1` | Cites `specs/point-in-time-universe.md` | contract | keep | `rules.yaml` | — | living-docs-research | Spec path frozen; spec stays at that path |  |
| M-RES-081 | `config/universe/rules.yaml:2-3` | Edit after first build needs new version; build refuses | requirement | move | universe | RES | living-docs-research | Same as M-RES-036 (one ID). at-risk class #16 |  |
| M-RES-082 | `config/universe/rules.yaml:5-10` comments | SIC meaning, exchange spelling, units | value | keep | `rules.yaml` | — | living-docs-research | |  |
| M-RES-083 | `config/universe/rules.yaml:13-16` | `PRICE_HISTORY_START` ≥ 45 days before window; `end: null` = current month | requirement | move | universe | RES | living-docs-research | Same as M-RES-032 |  |
| M-RES-084 | `config/universe/us_small_mid.yaml:1-5` | Broad universe for H10; empty `sic_codes` admits all | value | keep | `us_small_mid.yaml` | — | living-docs-research | Semantics of empty list stated in universe |  |

### config/themes.yaml and config/strategies/registry.yaml

| Row | Source (path:line or §) | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-STR-050 | `config/themes.yaml:1-4` | Unlisted ticker cannot be traded (`THEME_UNMAPPED`) | requirement | move | risk | STR | living-docs-strategy-and-dashboard | at-risk class #15; comment kept as is |  |
| M-STR-051 | `config/themes.yaml:6` onward | Only the 8 watched tickers mapped | trap | move | risk (Known traps) | STR | living-docs-strategy-and-dashboard | Every other universe ticker is rejected |  |
| M-STR-052 | `config/strategies/registry.yaml:1-35` | Five strategies, all `draft` | value | keep | `config/strategies/registry.yaml` | — | living-docs-strategy-and-dashboard | Read-only research config (M-EVA-030) |  |
| M-STR-053 | archived `strategy-framework` | Every strategy names a registered hypothesis; one per tradeable hypothesis | requirement | move | contract | STR | living-docs-strategy-and-dashboard | |  |
| M-STR-054 | archived `strategy-framework` | Version on code and parameter hash; change without bump refused | requirement | divergent | contract | STR | living-docs-strategy-and-dashboard | `main.py:93-97` passes no `versions_dir` (E F9). PENDING — `defects found while scoping` |  |
| M-STR-055 | `services/strategy/src/auspex_strategy/runtime/slots.py:14-18`; `services/strategy/src/auspex_strategy/runtime/book.py:30-32` | `live-confirm`/`live-auto` reserved; trade only virtual books | requirement | ratify | contract | STR | living-docs-strategy-and-dashboard | strategy-and-dashboard ratification batch (E F11) |  |
| M-STR-056 | CHOICE 2026-10-10 Single-source cleanup | Strategy parameters only in registered hypothesis | requirement | move | contract | STR | living-docs-strategy-and-dashboard | `test_strategy_parameter_files_do_not_redeclare_hypothesis_fields` |  |

### Strategy contract and trace code facts (no document source beyond archived specs)

| Row | Source (path:line or §) | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-STR-057 | `services/strategy/src/auspex_strategy/abc.py:18-24`; `services/strategy/src/auspex_strategy/runtime/context.py:52,70-72` | Records not yet known are hidden, never returned | requirement | move | contract | STR | living-docs-strategy-and-dashboard | Tested (`test_backtest_context_hides_records_not_yet_known`). PENDING — `as-of reads hide or raise`, default: hiding approved |  |
| M-STR-058 | `services/strategy/src/auspex_strategy/abc.py:18-24` docstring | Docstring promises `AsOfViolationError` raise | stale | move | contract (Known traps) | STR | living-docs-strategy-and-dashboard | Fix in a follow-up spec under `defects found while scoping`; rollout changes no code |  |
| M-STR-059 | CHOICE 2026-09-20 never see ingested_at | No context exposes `ingested_at` or `extracted_at` | requirement | move | contract | STR | living-docs-strategy-and-dashboard | at-risk class #4 STR side. a possible sixteenth invariant is written by the cutover only on the owner's CHOICE; PENDING — `processing time in as-of decisions` |  |
| M-RES-090 | `services/backtesting/src/auspex_backtesting/alignment/aligner.py:10,32` | Joining on a processing-time field raises | requirement | move | backtesting | RES | living-docs-research | at-risk class #4 RES side; same `processing time in as-of decisions` note |  |
| M-STR-060 | archived `decision-trace` | UUIDv5 intent ids over strategy, version, corroboration, `as_of`, position | requirement | move | trace | STR | living-docs-strategy-and-dashboard | at-risk class #14; CHOICE 2026-10-11 Decision trace item 2 |  |
| M-STR-061 | `services/strategy/src/auspex_strategy/runtime/replay.py:93`; `services/strategy/src/auspex_strategy/runtime/context.py:53` | Replay and streaming expose the same signals | requirement | ratify | contract | STR | living-docs-strategy-and-dashboard | strategy-and-dashboard ratification batch (E F2) |  |
| M-STR-062 | `services/strategy/src/auspex_strategy/runtime/main.py:151-152` | Live records carry ticker and source types | requirement | divergent | runtime | STR | living-docs-strategy-and-dashboard | FLAG 2026-10-10 Strategy runtime (E F5) |  |
| M-STR-063 | E F13 | `ExitOnSignal` positions never close | trap | move | runtime (Known traps) | STR | living-docs-strategy-and-dashboard | |  |
| M-STR-064 | `trace/store.py` | Kill-switch event log assumes one writer; CLI and runtime both append | trap | move | runtime (Known traps) | STR | living-docs-strategy-and-dashboard | |  |
| M-STR-065 | `prices` reads in `context.py` | Prices only for sessions before `as_of.date()`, else `PriceLookAheadError` | requirement | move | contract | STR | living-docs-strategy-and-dashboard | `test_backtest_context_refuses_a_close_that_is_not_final` |  |
| M-STR-066 | archived `strategy-framework` | `retired` raises in `decide()` and stays listed | requirement | move | contract | STR | living-docs-strategy-and-dashboard | |  |
| M-STR-067 | CHOICE 2026-09-20 Equal risk budget | Capital across promoted strategies: equal risk budget, correlation cap | requirement | divergent | risk | STR | living-docs-strategy-and-dashboard | Not implemented. PENDING — `defects found while scoping`; owner confirms still intended (E Q7) |  |

### Research code facts (D evidence)

| Row | Source (path:line or §) | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-RES-091 | `services/backtesting/src/auspex_backtesting/market_sim/fx.py:17-19` | FX rate for an order is a close known before the order | requirement | ratify | simulation | RES | living-docs-research | research ratification batch; code uses same-day close (D F14) |  |
| M-RES-092 | `services/backtesting/src/auspex_backtesting/alignment/aligner.py:46-63` | Genuine `00:00:00 UTC` treated as date-only | requirement | ratify | backtesting | RES | living-docs-research | research ratification batch |  |
| M-RES-093 | `run_portfolio_backtest.py` docstring | Score version matches cell's `floor` axis | requirement | ratify | backtesting | RES | living-docs-research | research ratification batch (D F5) |  |
| M-RES-094 | `services/backtesting/src/auspex_backtesting/market_sim/costs.py:13` | Cost semantics attributed to `docs/strategy-research.md` | stale | move | simulation (Rationale) | RES | living-docs-research | simulation.md owns cost semantics; comment fix belongs in a follow-up under `defects found while scoping` |  |
| M-RES-095 | D F6 | Result-affecting parameters outside registered files | trap | move | evaluation (Known traps) | EVA | living-docs-research | Cost vars, walk-forward, bound, threshold, H10 tolerances |  |
| M-RES-096 | D F16 | `catalyst-date-panel` and `catalyst-calendar` are two planned catalyst sources | trap | move | panels (Known traps) | RES | living-docs-research | |  |

### specs/point-in-time-universe.md (code-done; cut to Mac acceptance, path frozen)

| Row | Source (path:line or §) | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-RES-100 | `specs/point-in-time-universe.md:31` | Rules file versioned like a hypothesis; edit is a new trial | requirement | move | universe | RES | living-docs-research | M-RES-036; PENDING — `code-done specs blocked on the Mac` |  |
| M-RES-101 | `specs/point-in-time-universe.md:33-35` | Listing spans from filings; cap from filed counts × close; members on first session | requirement | move | universe | RES | living-docs-research | `code-done specs blocked on the Mac` |  |
| M-RES-102 | `specs/point-in-time-universe.md:36` | Snapshots never overwritten | requirement | move | universe | RES | living-docs-research | `code-done specs blocked on the Mac` |  |
| M-RES-103 | `specs/point-in-time-universe.md:37` | Delisted prices from free sources only, Yahoo then Stooq | requirement | move | market-data | RES | living-docs-research | CHOICE 2026-10-07 Second-wave — point-in-time universe scope |  |
| M-RES-104 | `specs/point-in-time-universe.md:39-41` | Membership spans; bounded windows; universe not watchlist | requirement | move | backtesting | RES | living-docs-research | CHOICE 2026-10-08 Control-surface — watchlist, item 4 |  |
| M-RES-105 | `specs/point-in-time-universe.md:42` | Backfill scope union from `BACKFILL_SCOPE_START` | requirement | move | universe | RES | living-docs-research | |  |
| M-RES-106 | `specs/point-in-time-universe.md:48-56` | Scope table values | value | link | `config/universe/rules.yaml` | — | living-docs-research | |  |
| M-RES-107 | `specs/point-in-time-universe.md:56` | Backfill breadth: company-scoped EDGAR/CT.gov, topic-scoped others | requirement | link | `specs/historical-backfill.md` | — | living-docs-research | Not built; stays in the backfill spec |  |
| M-RES-108 | `specs/point-in-time-universe.md:58-66` | Incomplete price history rules 1–5, bound, `survivorship_gap = material` | requirement | move | backtesting | RES | living-docs-research | at-risk class #20 |  |
| M-RES-109 | `specs/point-in-time-universe.md:72` | Current SIC only; current ticker for renamed issuers | requirement | move | universe | RES | living-docs-research | Accepted limitation |  |
| M-RES-110 | `specs/point-in-time-universe.md:80` | Every admitting field public before D; never period-end | requirement | move | universe | RES | living-docs-research | |  |
| M-RES-111 | `specs/point-in-time-universe.md:81` | Bulk archives for build; per-company ≤ 5 req/s | requirement | link | `docs/ingestion/connectors.md`; `docs/operations/orchestration.md` | ING | living-docs-research | |  |
| M-RES-112 | `specs/point-in-time-universe.md:112-125` | First build, coverage record, `backfill_scope.yaml` commit | process | keep | spec `## Remaining acceptance` | — | living-docs-research | Closes PENDING `2026-10-08 Point-in-time universe — SEC bulk URLs and first build` |  |

### specs/sec-ownership-datasets.md (code-done; path frozen)

| Row | Source (path:line or §) | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-RES-120 | `specs/sec-ownership-datasets.md:28` | 13F data sets downloaded once; universe holdings kept; unmapped counted | requirement | move | panels | RES | living-docs-research | `code-done specs blocked on the Mac` |  |
| M-RES-121 | `specs/sec-ownership-datasets.md:29` | `SpecialistClassifier` rule | requirement | move | panels | RES | living-docs-research | List item, not a heading: replaced by an anchored one-line pointer. `spec paths cited by hash-locked hypotheses`; M-RES-061 |  |
| M-RES-122 | `specs/sec-ownership-datasets.md:30-31` | Insider store fields; point-in-time readers | contract | move | panels | RES | living-docs-research | |  |
| M-RES-123 | `specs/sec-ownership-datasets.md:37` | Insider-copying event trades dropped | rationale | move | panels (Rationale) | RES | living-docs-research | |  |
| M-RES-124 | `specs/sec-ownership-datasets.md:43` | Joins use `filing_accepted_at`, never period or trade date | requirement | move | panels | RES | living-docs-research | M-RES-057 |  |
| M-RES-125 | `specs/sec-ownership-datasets.md:44-47` | SEC traps, URLs in config, UTC | requirement | link | ING / INV-6 / INV-9 | ING | living-docs-research | |  |
| M-RES-126 | `specs/sec-ownership-datasets.md:69-78` | First backfill from 2013, coverage, layout points | process | keep | spec `## Remaining acceptance` | — | living-docs-research | Closes PENDING `2026-10-09 SEC ownership — first backfill` |  |

### specs/short-interest-snapshots.md (code-done)

| Row | Source (path:line or §) | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-RES-130 | `specs/short-interest-snapshots.md:25-28` | Fetcher fields; store written once per period; derived features | requirement | move | panels | RES | living-docs-research | `code-done specs blocked on the Mac` |  |
| M-RES-131 | `specs/short-interest-snapshots.md:29` | Scheduled refresh belongs to `slow-signal-data-refresh` | status-note | keep | spec | — | living-docs-research | |  |
| M-RES-132 | `specs/short-interest-snapshots.md:41` | `as_of()` never returns a record before its publication date | requirement | move | panels | RES | living-docs-research | M-RES-066 |  |
| M-RES-133 | `specs/short-interest-snapshots.md:58-66` | FINRA credential and first fetch | process | keep | spec `## Remaining acceptance` | — | living-docs-research | Closes PENDING `2026-10-10 Short interest — first fetch` |  |

### specs/catalyst-date-panel.md (code-done; path frozen)

| Row | Source (path:line or §) | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-RES-140 | `specs/catalyst-date-panel.md:24-27` | Extractor, notices, append-only panel, coverage script | requirement | move | panels | RES | living-docs-research | `code-done specs blocked on the Mac` |  |
| M-RES-141 | `specs/catalyst-date-panel.md:31-34` | Readout guidance, live serving, outcomes out of scope | status-note | keep | spec | — | living-docs-research | Points to `catalyst-calendar` |  |
| M-RES-142 | `specs/catalyst-date-panel.md:38` | Catalyst invisible before disclosure; revision never changes earlier read | requirement | move | panels | RES | living-docs-research | |  |
| M-RES-143 | `specs/catalyst-date-panel.md:58-67` | Panel from 2014; 30-hit hand check, precision rule | process | keep | spec `## Remaining acceptance` | — | living-docs-research | Closes PENDING `2026-10-09 Catalyst date panel — sources unreachable` |  |
| M-RES-144 | FLAG 2026-10-09 Catalyst date panel — not kept current | Panels not refreshed by the stack | trap | move | panels (Known traps) | RES | living-docs-research | |  |

### specs/filing-text-change-score.md (code-done)

| Row | Source (path:line or §) | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-RES-150 | `specs/filing-text-change-score.md:20` | H10 as biotech filter and broad standalone test | rationale | move | panels (Rationale) | RES | living-docs-research | CHOICE 2026-10-08 Edge research — direction: both (history) |  |
| M-RES-151 | `specs/filing-text-change-score.md:22` | Second universe; rules file a parameter | requirement | move | universe | RES | living-docs-research | M-RES-034 |  |
| M-RES-152 | `specs/filing-text-change-score.md:26-30` | Index, archive, score, monthly read, panel build | requirement | move | panels | RES | living-docs-research | `code-done specs blocked on the Mac` |  |
| M-RES-153 | `specs/filing-text-change-score.md:41` | Score never known before later acceptance; comparison accepted earlier | requirement | move | panels | RES | living-docs-research | |  |
| M-RES-154 | `specs/filing-text-change-score.md:42` | Volume estimate | rationale | move | panels (Rationale) | RES | living-docs-research | |  |
| M-RES-155 | `specs/filing-text-change-score.md:72-83` | First build, coverage, 20-filing hand check | process | keep | spec `## Remaining acceptance` | — | living-docs-research | |  |

### specs/holdings-composite-score.md (code-done)

| Row | Source (path:line or §) | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-RES-156 | `specs/holdings-composite-score.md:23-28` | Components, ranks, two-component minimum, `known_at_max` | requirement | move | panels | RES | living-docs-research | `code-done specs blocked on the Mac` |  |
| M-RES-157 | `specs/holdings-composite-score.md:29` | Variant chosen from coverage dates only | requirement | move | panels | RES | living-docs-research | |  |
| M-RES-158 | `specs/holdings-composite-score.md:40-42` | Validate every row; CIK tie-break; write once per version, floor, date | requirement | move | panels | RES | living-docs-research | |  |
| M-RES-159 | `specs/holdings-composite-score.md:63-71` | First run on the Mac | process | keep | spec `## Remaining acceptance` | — | living-docs-research | |  |

### Archived specs cited for the at-risk classes classes 1–2 (archive unchanged)

| Row | Source (path:line or §) | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-RES-160 | `specs/done/backtest-look-ahead-fix.md:20-22` | Date-only known after close; entry at next open; calendar-day windows | requirement | move | backtesting | RES | living-docs-research | at-risk class #1; CHOICE 2026-10-07 Backtest look-ahead — entry and holding-window timing |  |
| M-RES-161 | CHOICE 2026-10-07 Backtest look-ahead — one event | One event per corroboration; weight from participants known at event | requirement | move | backtesting | RES | living-docs-research | at-risk class #2 |  |
| M-RES-162 | CHOICE 2026-10-07 Market simulation — FillModel | `FillModel` never shifts entry dates | requirement | move | simulation | RES | living-docs-research | |  |
| M-RES-163 | CHOICE 2026-10-07 Market simulation — fx_rate | `fx_rate` is EUR per USD | requirement | move | simulation | RES | living-docs-research | |  |
| M-RES-164 | CHOICE 2026-10-07 Realistic cost model | Per-ticker spread, FX fee, volume cap, gap-through stops | requirement | move | simulation | RES | living-docs-research | Values in `.env.example` |  |
| M-RES-165 | CHOICE 2026-09-20 New services/strategy | Strategy imports market simulation, never copies it | requirement | move | simulation | RES | living-docs-research | STR links |  |

### DECISIONS.md CHOICE and FLAG entries in the domain (binding or history)

**Binding** means a row above moves its rule and the heading is cited as Source. **History** means the entry stays in `DECISIONS.md` and no ID is created.

| Row | Source (path:line or §) | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-EVA-060 | `DECISIONS.md:374` `## 2026-09-20 — Strategy layer — CHOICE — XBI as primary benchmark` | XBI benchmark, IBB fallback | history | keep | `DECISIONS.md` | — | living-docs-research | Superseded by `protocol.yaml`; IBB fallback not implemented |  |
| M-EVA-061 | `DECISIONS.md:380` `## 2026-09-20 — Strategy layer — CHOICE — Known-at delay default: 1 business day after corroborated_at` | Default delay | history | keep | `DECISIONS.md` | — | living-docs-research | Delay registered per hypothesis |  |
| M-EVA-062 | `DECISIONS.md:385` `## 2026-09-20 — Strategy layer — CHOICE — Holdout: last 3 months sealed` | 3-month holdout | history | keep | `DECISIONS.md` | — | living-docs-research | Superseded by `promotion.holdout_months` |  |
| M-STR-070 | `DECISIONS.md:396` `## 2026-09-20 — Strategy layer session 2 — CHOICE — New \`services/strategy/\` service (not extending backtesting)` | Separate service, path dependency | requirement | move | runtime | STR | living-docs-strategy-and-dashboard | binding |  |
| M-STR-071 | `DECISIONS.md:402` `## 2026-09-20 — Strategy layer session 2 — CHOICE — MinIO for virtual books and traces; strategy service serves metrics API` | State in MinIO; runtime serves metrics | requirement | move | runtime | STR | living-docs-strategy-and-dashboard | binding; Flask detail history |  |
| M-STR-072 | `DECISIONS.md:407` `## 2026-09-20 — Strategy layer session 2 — CHOICE — Event-driven Kafka consumer for the strategy runtime` | Streaming consumer | requirement | move | runtime | STR | living-docs-strategy-and-dashboard | binding |  |
| M-STR-073 | `DECISIONS.md:412` `## 2026-09-20 — Strategy layer session 2 — CHOICE — Strategies never see ingested_at or extracted_at; InputHealthMonitor handles model downtime` | No processing time; health monitor | requirement | move | contract | STR | living-docs-strategy-and-dashboard | binding; at-risk class #4 |  |
| M-STR-074 | `DECISIONS.md:417` `## 2026-09-20 — Strategy layer session 2 — CHOICE — Equal risk budget per promoted strategy; correlation-aware cap` | Capital allocation | requirement | divergent | risk | STR | living-docs-strategy-and-dashboard | binding, not implemented (M-STR-067) |  |
| M-STR-075 | `DECISIONS.md:422` `## 2026-09-20 — Strategy layer session 2 — CHOICE — Minimum 20 trades before metrics and Kelly sizing` | Minimum trades | requirement | move | runtime; risk | STR | living-docs-strategy-and-dashboard | binding; values `.env.example` |  |
| M-STR-076 | `DECISIONS.md:427` `## 2026-09-20 — Strategy layer session 2 — FLAG — extracted_at missing from ResearchSignalEvent (§10.2)` | `extracted_at` nullable in trace | requirement | move | trace | STR | living-docs-strategy-and-dashboard | binding |  |
| M-STR-077 | `DECISIONS.md:432` `## 2026-09-20 — Strategy layer session 2 — FLAG — Corroboration surrogate key deferred; composite natural key in trace` | Trace keys on `(entity_key, participants_hash)` | requirement | move | trace | STR | living-docs-strategy-and-dashboard | binding |  |
| M-DSH-030 | `DECISIONS.md:438` `## 2026-09-19 — Dashboard — CHOICE — Node 22 LTS (Phase 5 resolution)` | Node 22 | history | keep | `DECISIONS.md` | — | living-docs-strategy-and-dashboard | Superseded by Node 24 |  |
| M-DSH-031 | `DECISIONS.md:969` `## 2026-10-09 — Dashboard — CHOICE — Node 24 LTS, actions on Node 24` | Node 24 | value | link | `VERSIONS.md` | — | living-docs-strategy-and-dashboard | Pin owned by VERSIONS |  |
| M-DSH-032 | `DECISIONS.md:883` `## 2026-10-09 — Dashboard foundation — CHOICE — Next 16, Vitest 5 and Tailwind 4 to clear the advisories` | Framework versions | value | link | `VERSIONS.md` | — | living-docs-strategy-and-dashboard | |  |
| M-DSH-033 | `DECISIONS.md:888` `## 2026-10-09 — Dashboard foundation — CHOICE — login endpoint, write-token failure mode, path layout` | Login, token failure mode, BFF paths | requirement | move | dashboard | DSH | living-docs-strategy-and-dashboard | binding; token half links HUB |  |
| M-DSH-034 | `DECISIONS.md:778` `## 2026-10-08 — Control-surface scoping — CHOICE — Grafana for technical health, dashboard for using the application` | Split of surfaces | requirement | move | dashboard | DSH | living-docs-strategy-and-dashboard | binding |  |
| M-DSH-035 | `DECISIONS.md:782` `## 2026-10-08 — Control-surface scoping — CHOICE — the watchlist is the single source for tracked tickers and terms` | Item 4: backtest universe not the watchlist | requirement | move | universe | RES | living-docs-research | History CHOICE (decisions table); its item 4 rule, backtest universe not the watchlist, still moves to RES; remaining items ING/HUB |  |
| M-DSH-036 | `DECISIONS.md:791` `## 2026-10-08 — Control-surface scoping — CHOICE — research config is read-only in the dashboard` | Research config read-only | requirement | move | evaluation | EVA | living-docs-research | binding; M-EVA-030 |  |
| M-DSH-037 | `DECISIONS.md:795` `## 2026-10-08 — Control-surface scoping — CHOICE — dashboard runs in the stack behind its own server layer` | BFF; same origin; token; no CORS | requirement | move | dashboard | DSH | living-docs-strategy-and-dashboard | binding; token and CORS link HUB |  |
| M-RES-170 | `DECISIONS.md:519` `## 2026-10-07 — Market simulation — CHOICE — PositionSizer \`fx_rate\` is EUR per USD` | EUR per USD | requirement | move | simulation | RES | living-docs-research | binding |  |
| M-RES-171 | `DECISIONS.md:524` `## 2026-10-07 — Market simulation — CHOICE — FillModel does not shift entry dates` | No shift | requirement | move | simulation | RES | living-docs-research | binding |  |
| M-RES-172 | `DECISIONS.md:529` `## 2026-10-07 — Market simulation — CHOICE — 11 tests, not 10; \`scripts/fetch_prices.py\`` | Test count, script | history | keep | `DECISIONS.md` | — | living-docs-research | |  |
| M-RES-173 | `DECISIONS.md:534` `## 2026-10-07 — Market simulation — PENDING — EURUSD=X and XBI not yet in MinIO` | First fetch pending | status-note | keep | `DECISIONS.md` | — | living-docs-research | Closed by first run |  |
| M-RES-174 | `DECISIONS.md:562` `## 2026-10-07 — Startup data — CHOICE — data fills itself on \`up\`; prices refresh daily` | Prices fill on up, refresh daily | requirement | move | market-data | RES | living-docs-research | binding; DAG side OPS |  |
| M-RES-175 | `DECISIONS.md:568` `## 2026-10-07 — Realistic cost model — CHOICE — per-ticker spread, FX fee, volume cap, gap-through stops` | Cost model | requirement | move | simulation | RES | living-docs-research | binding |  |
| M-EVA-063 | `DECISIONS.md:577` `## 2026-10-07 — Pre-registration — CHOICE — evaluation protocol and kill criteria locked before the backfill` | Protocol locked; holdout and trials spent | requirement | move | evaluation | EVA | living-docs-research | binding |  |
| M-EVA-064 | `DECISIONS.md:588` `## 2026-10-07 — Pre-registration — CHOICE — trials counted as cells across the hypothesis family, budget 64` | Cells across family | requirement | move | evaluation | EVA | living-docs-research | binding; budget value now per family |  |
| M-EVA-065 | `DECISIONS.md:594` `## 2026-10-07 — Pre-registration — CHOICE — market-model abnormal returns against XBI with two-way clustered errors` | Market model | requirement | move | evaluation | EVA | living-docs-research | binding |  |
| M-EVA-066 | `DECISIONS.md:600` `## 2026-10-07 — Pre-registration — CHOICE — hypothesis triage; versions 2 registered` | Roles and statuses | requirement | move | evaluation | EVA | living-docs-research | binding (role rule); version facts history |  |
| M-EVA-067 | `DECISIONS.md:606` `## 2026-10-07 — Pre-registration — CHOICE — sizing ceilings: quarter Kelly, 5% per name, one position per theme, no hold through binary events` | Sizing ceilings | requirement | move | risk | STR | living-docs-strategy-and-dashboard | binding; values `protocol.yaml` `sizing` |  |
| M-EVA-068 | `DECISIONS.md:612` `## 2026-10-07 — Pre-registration — VERIFIED — owner accepted the proposed thresholds` | Owner acceptance | history | keep | `DECISIONS.md` | — | living-docs-research | |  |
| M-RES-176 | `DECISIONS.md:633` `## 2026-10-07 — Second-wave specs — CHOICE — short interest is a market-data snapshot, not a connector` | Snapshot, not connector | requirement | move | panels | RES | living-docs-research | binding |  |
| M-RES-177 | `DECISIONS.md:648` `## 2026-10-07 — Second-wave specs — CHOICE — point-in-time universe scope` | Universe scope, free prices | requirement | move | universe | RES | living-docs-research | binding; values in rules file |  |
| M-EVA-069 | `DECISIONS.md:653` `## 2026-10-07 — Second-wave specs — CHOICE — paper trading gates capital, run at several sizes` | Paper gates capital | requirement | move | evaluation | EVA | living-docs-research | binding (M-EVA-048) |  |
| M-RES-178 | `DECISIONS.md:658` `## 2026-10-07 — Backtest look-ahead fix — FLAG — variant returns counted signals that predate their corroboration` | Fixed defect | history | keep | `DECISIONS.md` | — | living-docs-research | |  |
| M-RES-179 | `DECISIONS.md:663` `## 2026-10-07 — Backtest look-ahead fix — CHOICE — one backtest event per corroboration, not per superseding record` | One event | requirement | move | backtesting | RES | living-docs-research | binding; at-risk class #2 |  |
| M-RES-180 | `DECISIONS.md:668` `## 2026-10-07 — Backtest look-ahead fix — CHOICE — entry and holding-window timing` | Entry timing | requirement | move | backtesting | RES | living-docs-research | binding; at-risk class #1 |  |
| M-EVA-070 | `DECISIONS.md:690` `## 2026-10-07 — Edge research scoping — CHOICE — edge research synthesis: the alpha path becomes slow monthly scores` | Alpha path direction | history | keep | `DECISIONS.md` | — | living-docs-research | Rationale; RES/EVA Rationale may link |  |
| M-EVA-071 | `DECISIONS.md:709` FLAG 20-day volatility in strategy-research about three times too low | Stale number in rationale doc | stale | keep | `docs/strategy-research.md` | — | living-docs-research | Not corrected by any spec; reported |  |
| M-EVA-072 | `DECISIONS.md:714` FLAG paper trading cannot prove a monthly portfolio's edge in 12 months | Forward-check design input | rationale | move | evaluation (Rationale) | EVA | living-docs-research | |  |
| M-RES-181 | `DECISIONS.md:719` `## 2026-10-07 — Edge research scoping — CHOICE — ownership and insider data are snapshots, not connectors` | Panels are snapshots | requirement | move | panels | RES | living-docs-research | binding |  |
| M-RES-182 | `DECISIONS.md:725` FLAG a hand-made specialist fund list is look-ahead | Specialist list derived, not hand-made | requirement | move | panels | RES | living-docs-research | binding |  |
| M-EVA-073 | `DECISIONS.md:729` `## 2026-10-07 — Edge research scoping — CHOICE — deferred items` | Deferred items | history | keep | `DECISIONS.md` | — | living-docs-research | |  |
| M-RES-183 | `DECISIONS.md:737` `## 2026-10-08 — Edge research scoping — CHOICE — quarterly banded rotation; catalysts as a guard, not a trigger` | Banded rotation; catalyst guard; cost defaults | requirement | move | backtesting; simulation | RES | living-docs-research | Partly binding (guard, defaults); rotation registered in `h9.yaml` |  |
| M-EVA-074 | `DECISIONS.md:744` `## 2026-10-08 — Edge research scoping — CHOICE — two non-LLM panels before the LLM backfill` | Build order | requirement | move | `docs/research/backtesting.md` | RES | living-docs-research | Build order: the two non-LLM panels come before the LLM backfill; binding CHOICE |  |
| M-RES-184 | `DECISIONS.md:749` `## 2026-10-08 — Point-in-time universe — CHOICE — how the monthly list is derived from free SEC data` | Derivation items 1–5 | requirement | move | universe | RES | living-docs-research | binding |  |
| M-RES-185 | `DECISIONS.md:766` `## 2026-10-08 — Point-in-time universe — CHOICE — windows the prices do not cover` | Window rules 1–6 | requirement | move | backtesting | RES | living-docs-research | binding |  |
| M-RES-186 | `DECISIONS.md:809` `## 2026-10-08 — First run on the stack machine — CHOICE — price history from 2013, set before the first \`up\`` | History start | value | link | `.env.example` `PRICE_HISTORY_START` | — | living-docs-research | Rule "never extended backwards by schedule" moves to market-data |  |
| M-RES-187 | `DECISIONS.md:824` `## 2026-10-09 — Point-in-time universe — CHOICE — one universe from 2014, backfill scope from its own start` | One universe; scope start | requirement | move | universe | RES | living-docs-research | binding |  |
| M-EVA-075 | `DECISIONS.md:834` `## 2026-10-08 — Edge research scoping — CHOICE — direction: both` | Direction both | history | keep | `DECISIONS.md` | — | living-docs-research | |  |
| M-EVA-076 | `DECISIONS.md:839` `## 2026-10-08 — Edge research scoping — CHOICE — portfolio paper-trading pass rule` | Pass rule | requirement | move | evaluation | EVA | living-docs-research | binding |  |
| M-EVA-077 | `DECISIONS.md:843` `## 2026-10-08 — Edge research scoping — CHOICE — build order` | Build order | history | keep | `DECISIONS.md` | — | living-docs-research | |  |
| M-RES-188 | `DECISIONS.md:847` FLAG universe window | Window decision input | history | keep | `DECISIONS.md` | — | living-docs-research | Resolved by `:824` |  |
| M-EVA-078 | `DECISIONS.md:896` `## 2026-10-09 — Pre-launch spec audit — CHOICE — gaps closed in the spec index` | Spec index gaps | history | keep | `DECISIONS.md` | — | living-docs-research | |  |
| M-RES-189 | `DECISIONS.md:909` `## 2026-10-09 — Catalyst date panel — CHOICE — how documents become rows` | Catalyst rows | requirement | move | panels | RES | living-docs-research | binding |  |
| M-EVA-079 | `DECISIONS.md:987` `## 2026-10-09 — Slow-signal pre-registration — CHOICE — one protocol and one version per hypothesis, H9–H12 registered` | One protocol; registry append-only | requirement | move | evaluation | EVA | living-docs-research | binding; one-time reset history |  |
| M-EVA-080 | `DECISIONS.md:998` `## 2026-10-09 — Slow-signal pre-registration — CHOICE — details the spec left open` | Admission details | requirement | move | evaluation | EVA | living-docs-research | binding |  |
| M-RES-190 | `DECISIONS.md:1030` `## 2026-10-09 — SEC ownership datasets — CHOICE — acceptance time from a filing date` | 22:00 Eastern | requirement | move | panels | RES | living-docs-research | binding |  |
| M-RES-191 | `DECISIONS.md:1034` `## 2026-10-09 — SEC ownership datasets — CHOICE — how filings, amendments and trades are counted` | Counting rules | requirement | move | panels | RES | living-docs-research | binding |  |
| M-RES-192 | `DECISIONS.md:1047` FLAG panels are refreshed by a script, not a DAG | Script refresh | trap | move | panels (Known traps) | RES | living-docs-research | |  |
| M-RES-193 | `DECISIONS.md:1051` `## 2026-10-09 — SEC ownership datasets — CHOICE — specialist thresholds have one source, the registered H9` | Thresholds from h9 | requirement | move | panels | RES | living-docs-research | binding |  |
| M-EVA-081 | `DECISIONS.md:1065` `## 2026-10-10 — Pre-launch spec audit — CHOICE — portfolio verdict and the remaining blockers` | Portfolio verdict item 1 | requirement | move | evaluation | EVA | living-docs-research | binding (item 1); blockers history |  |
| M-EVA-082 | `DECISIONS.md:1100` `## 2026-10-10 — Consolidated code, strategy and BV audit — CHOICE — what becomes specs, what does not` | Items 3–4: ledger lock, cash remainder | requirement | move | evaluation; backtesting | EVA | living-docs-research | binding (items 3–4); others history |  |
| M-RES-194 | `DECISIONS.md:1111` `## 2026-10-10 — Price finality and split availability — CHOICE — edges the spec leaves open` | Settle edges | requirement | move | market-data | RES | living-docs-research | binding |  |
| M-EVA-083 | `DECISIONS.md:1125` `## 2026-10-10 — Evaluation protocol — CHOICE — how the event evaluation reads the spec` | Items 1–7 | requirement | move | evaluation | EVA | living-docs-research | binding |  |
| M-EVA-084 | `DECISIONS.md:1136` `## 2026-10-10 — Evaluation protocol — CHOICE — the raw-return backtest reserves trial cells too` | Raw-return run reserves | requirement | move | evaluation | EVA | living-docs-research | binding |  |
| M-RES-195 | `DECISIONS.md:1148` `## 2026-10-10 — Short interest snapshots — CHOICE — publication dates from FINRA's rule, published rows win` | FINRA rule; calendar wins | requirement | move | panels | RES | living-docs-research | binding |  |
| M-STR-078 | `DECISIONS.md:1154` FLAG Strategy runtime — live data channel not fully served by core-hub | Live inputs missing | status-note | keep | `DECISIONS.md` | — | living-docs-strategy-and-dashboard | Cited by divergent rows M-STR-004/009/062 |  |
| M-STR-079 | `DECISIONS.md:1162` `## 2026-10-10 — Strategy runtime — CHOICE — state placement, timing and the pass-through stub` | Items 1–5 | requirement | move | runtime | STR | living-docs-strategy-and-dashboard | binding; item 5 (no DLT) cited by divergent M-STR-005 |  |
| M-RES-196 | `DECISIONS.md:1171` `## 2026-10-11 — Cross-sectional portfolio backtest — CHOICE — how the engine reads the spec` | Items 1–11 | requirement | move | backtesting; evaluation; simulation | RES | living-docs-research | binding |  |
| M-STR-080 | `DECISIONS.md:1185` `## 2026-10-11 — Strategy metrics — CHOICE — where the spec left the metrics open` | Items 1–8 | requirement | move | runtime | STR | living-docs-strategy-and-dashboard | binding |  |
| M-RES-197 | `DECISIONS.md:1196` `## 2026-10-11 — Short interest snapshots — CHOICE — short interest share and change on one split basis` | One split basis | requirement | move | panels | RES | living-docs-research | binding |  |
| M-RES-198 | `DECISIONS.md:1199` `## 2026-10-15 — Filing text change score — CHOICE — how the panel reads EDGAR and where the second universe lives` | Panel and universe rules | requirement | move | panels; universe | RES | living-docs-research | binding |  |
| M-STR-081 | `DECISIONS.md:1210` `## 2026-10-11 — Decision trace — CHOICE — one document record per participant, deterministic intent ids, risk reviews per event` | Items 1–4 | requirement | move | trace; risk | STR | living-docs-strategy-and-dashboard | binding; at-risk class #14 |  |
| M-STR-082 | `DECISIONS.md:1216` `## 2026-10-11 — Portfolio and risk — CHOICE — catalyst and short-interest sources, units and check order` | Items 1–9 | requirement | move | risk | STR | living-docs-strategy-and-dashboard | binding; at-risk class #15 |  |
| M-STR-083 | `DECISIONS.md:1228` FLAG Portfolio and risk — pass-through stub | Runtime not wired to risk | status-note | keep | `DECISIONS.md` | — | living-docs-strategy-and-dashboard | Cited by divergent M-STR-014 |  |
| M-RES-199 | `DECISIONS.md:1232` `## 2026-10-15 — Holdings composite score — CHOICE — where the spec left the H9 score open` | H9 score rules | requirement | move | panels | RES | living-docs-research | binding |  |
| M-STR-084 | `DECISIONS.md:964` `## 2026-10-10 — Single-source cleanup — CHOICE — one version of each pre-rollout artifact` | Strategy params only in hypotheses | requirement | move | contract | STR | living-docs-strategy-and-dashboard | binding (STR part); rest other domains |  |
| M-EVA-085 | `DECISIONS.md:287` FLAG Phase 4 — directionality hindsight-exposed | Superseded by v2 | history | keep | `DECISIONS.md` | — | living-docs-research | |  |
| M-EVA-086 | `DECISIONS.md:301` `## 2026-09-19 — Phase 4 — FLAG (v2, supersedes earlier Phase 4 note) — entity-only variant required in all Phase 4 output` | Entity-only variant | requirement | move | evaluation | EVA | living-docs-research | binding FLAG with an action; at-risk class #3 |  |
| M-STR-085 | `DECISIONS.md:368` FLAG §0.1 flips at session 3 | §0.1 amendment | status-note | keep | `DECISIONS.md` | — | living-docs-strategy-and-dashboard | Gathered by `specs/live-trading.md` |  |
| M-STR-086 | `DECISIONS.md:391` FLAG Belgian speculative classification | Advisor confirmation before shorts/live | status-note | keep | `DECISIONS.md`; `docs/PREREQUISITES.md` | — | living-docs-strategy-and-dashboard | |  |

### Stale text found while checking code

| Row | Source (path:line or §) | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-STR-090 | `docker/docker-compose.yml:537` comment | Core-hub "serves the per-input health the runtime polls" | stale | delete | — | — | living-docs-operations | Untrue (M-STR-009); OPS owns compose comments |  |
| M-STR-091 | `specs/forward-paper-trading.md`, `research-results-view.md` | Link `specs/decision-trace.md` (archived) | stale | delete | — | — | living-docs-strategy-and-dashboard | Fixed to `specs/done/...` in the spec edits |  |
| M-DSH-040 | `ingestion-config-ui`, `signal-browse-views`, `pipeline-control-view` | Blocked-by `specs/dashboard-foundation.md` (archived, met) | stale | delete | — | — | living-docs-strategy-and-dashboard | Path fixed in the spec edits |  |

### the at-risk classes at-risk classes in this domain

| Row | Source (path:line or §) | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-RES-200 | at-risk class #1 | Date-only after close; next-open entry; calendar-day windows | requirement | move | backtesting | RES | living-docs-research | M-RES-160, M-RES-180 |  |
| M-RES-201 | at-risk class #2 | One backtest event per corroboration | requirement | move | backtesting | RES | living-docs-research | M-RES-161, M-RES-179 |  |
| M-EVA-090 | at-risk class #3 | Entity-only beside full variant | requirement | move | evaluation | EVA | living-docs-research | M-EVA-049, M-EVA-086 |  |
| M-STR-092 | at-risk class #4 (STR/RES side) | No processing time in as-of decisions | requirement | move | contract; backtesting | STR | living-docs-strategy-and-dashboard | M-STR-059, M-RES-090; a possible sixteenth invariant is written by the cutover only on the owner's CHOICE |  |
| M-EVA-091 | at-risk class #11 | Research config read-only | requirement | move | evaluation | EVA | living-docs-research | M-EVA-030 |  |
| M-STR-093 | at-risk class #14 | Deterministic ids; DocumentRecord per participant; every check | requirement | move | trace | STR | living-docs-strategy-and-dashboard | M-STR-016, M-STR-060, M-STR-013 |  |
| M-STR-094 | at-risk class #15 | Check order, units, kill before review, unmapped theme rejected | requirement | move | risk | STR | living-docs-strategy-and-dashboard | M-STR-031, M-STR-025, M-STR-050 |  |
| M-RES-202 | at-risk class #16 | Universe rules version lock | requirement | move | universe | RES | living-docs-research | M-RES-036, M-RES-081 |  |
| M-RES-203 | at-risk class #17 | Publication-date rules for slow data | requirement | move | panels | RES | living-docs-research | M-RES-057/058/066 |  |
| M-RES-204 | at-risk class #20 | Code-done blocked specs' requirements | requirement | move | universe; panels; backtesting | RES | living-docs-research | PENDING — `code-done specs blocked on the Mac`; tables above |  |

### File-level roles

| Source file | Final role | Spec |
|---|---|---|
| `docs/requirements.md` §0.1, §0.3, §4.1 (backtest clause), §6.7 (research use), §8 | legacy § → ID index (`fate of docs/requirements.md`) | legacy |
| `services/backtesting/README.md` | orientation, commands and scripts; links to RES/EVA IDs | research |
| `services/strategy/README.md` | orientation and commands; links to STR IDs | strat |
| `services/dashboard/README.md` | orientation, configuration and commands; links to DSH IDs | strat |
| `docs/strategy-research.md` | rationale, non-normative, frozen path, not edited | research |
| `config/hypotheses/protocol.yaml`, `h*.yaml`, `registry.jsonl` | machine authority (locked; never edited) | research |
| `config/universe/rules.yaml`, `us_small_mid.yaml` | machine authority (locked; never edited) | research |
| `config/themes.yaml` | machine authority | strat |
| `config/strategies/registry.yaml` | machine authority (read-only research config) | strat |
| `specs/point-in-time-universe.md` | active spec cut to Mac acceptance; path frozen | research |
| `specs/sec-ownership-datasets.md` | active spec cut to Mac acceptance; path frozen; anchored `SpecialistClassifier` pointer | research |
| `specs/catalyst-date-panel.md` | active spec cut to Mac acceptance; path frozen (h12) | research |
| `specs/short-interest-snapshots.md`, `filing-text-change-score.md`, `holdings-composite-score.md` | active specs cut to Mac acceptance | research |
| `specs/clinicaltrials-version-diffs.md` | active change spec; path frozen (h11); citations to IDs | research |
| `specs/catalyst-calendar.md`, `slow-signal-data-refresh.md`, `research-input-archive.md` | active change specs; Docs impact and ID citations | research |
| `specs/forward-paper-trading.md`, `live-trading.md` | active change specs; Docs impact `STR-new`; ID citations | strat |
| `specs/ingestion-config-ui.md`, `signal-browse-views.md`, `pipeline-control-view.md`, `lineage-trace-view.md`, `research-results-view.md` | active change specs; Docs impact DSH; ID citations | strat |
| `specs/done/{backtesting,performance-metrics,backtest-look-ahead-fix,market-simulation,realistic-cost-model,evaluation-protocol,cross-sectional-portfolio-backtest,price-finality-and-split-availability,ownership-share-basis,forward-check-input-validation}.md` | archive (cited as Source) | research |
| `specs/done/{strategy-framework,strategy-runtime,portfolio-and-risk,decision-trace,strategy-metrics,dashboard-foundation,dashboard,watchlist-ui}.md` | archive (cited as Source) | strat |
| `DECISIONS.md` (domain CHOICE/FLAG entries) | append-only log; binding entries cited as Source | research; strat |


## Operations (OPS) and file-level dispositions of every doc outside specs/


Written against: `develop` @ `e51f742`. Sources read from `/home/claude/auspex-baseline`. Namespace: **OPS**. Rows that name another namespace are links to an owner another fragment writes; they are listed so every normative statement in these sources has a disposition.

Targets: `topology` = `docs/operations/topology.md`, `orchestration` = `docs/operations/orchestration.md`, `observability` = `docs/operations/observability.md`, `backup` = `docs/operations/backup.md`.
Specs: `ops` = `specs/living-docs-operations.md`, `legacy` = `specs/legacy-docs-retirement.md`, `agents` = `specs/agent-instruction-hierarchy.md`, other domain specs by file name.
"Ratify" rows go into `## <date> — Living docs — PENDING — operations ratification batch`, appended by `living-docs-operations`.

### docs/requirements.md (§0.2, §1 Infrastructure, §3, §5, §6.5, §12)

| Row | Source (path:line or §) | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-OPS-001 | §0.2 (`requirements.md:13`) | Cursor state lives in Airflow Variables, read and written by the DAG task | requirement | move | orchestration | OPS | living-docs-operations | Storage side only. The cursor rule is ING (`ingestion/pipeline.md`), per design §2 seams | OPS-032 |
| M-OPS-002 | §1 Infrastructure, Kafka (`:38`) | Topics provisioned from `topics.yaml` by a one-shot, never by a producer | requirement | move | topology | OPS | living-docs-operations | Provisioning mechanism only; topic semantics and values are CON (`docker/topics.yaml`) | OPS-009 |
| M-OPS-003 | §1 PostgreSQL (`:39`) | Airflow metadata in a separate logical database, own role, no cross-grants | requirement | move | topology | OPS | living-docs-operations | `test_repo_scaffolding.py::test_airflow_metadata_is_a_separate_database` | OPS-012 |
| M-OPS-004 | §1 PostgreSQL (`:39`) | Postgres holds "price series" | stale | delete | — | — | legacy-docs-retirement | Prices are Parquet in `auspex-prices` (A C5); RES owns prices |  |
| M-OPS-005 | §1 PostgreSQL (`:39`) | Schema owned by Flyway; `ddl-auto=validate` | requirement | link | `docs/core-hub/storage.md` | HUB | living-docs-core-hub | |  |
| M-OPS-006 | §1 PostgreSQL (`:39`) | "provisioned in Step 0.2 because the init script runs only on empty data" | history | delete | — | — | legacy-docs-retirement | Plan-step text. Today's mechanism is the `airflow-db-role` one-shot (M-OPS-060) |  |
| M-OPS-007 | §1 PostgreSQL, Neo4j, Kafka version lines (`:38-41`) | Component versions; Postgres 19 is beta | value | link | `VERSIONS.md` | — | legacy-docs-retirement | Pins are owned by `VERSIONS.md` |  |
| M-OPS-008 | §1 MinIO (`:42`) | MinIO credentials come from `.env` with no defaults | requirement | move | topology | OPS | living-docs-operations | Applies INV-6. `test_repo_scaffolding.py::test_no_credential_has_a_source_default` | OPS-006 |
| M-OPS-009 | §1 MinIO (`:42`) | Every published compose port is bound to `127.0.0.1` | requirement | move | topology | OPS | living-docs-operations | `test_stack_observability_config.py::test_new_exporters_publish_no_host_ports` asserts `127.0.0.1:` for every published port (`:389-395`) | OPS-005 |
| M-OPS-010 | §3 rule 3 (`:67`) | "Source API keys are Airflow Connections" | invariant | link | `docs/system/invariants.md#INV-6` | INV | living-docs-system-and-contracts | `## 2026-10-15 — Living docs — PENDING — invariant 6 wording`. Contradicted by compose `:445-455` |  |
| M-OPS-011 | §3 rule 12 (`:89`) | Nothing dies silently: DLT depth and per-source signal age are reported | invariant | link | `docs/system/invariants.md#INV-11` | INV | living-docs-system-and-contracts | The alert and summary side is OPS (M-OPS-120, M-OPS-130) |  |
| M-OPS-012 | §5 (`:126`) | Airflow 3: `schedule` not `schedule_interval`; Variables via Task SDK | trap | move | orchestration (Known traps) | OPS | living-docs-operations | Same trap in root `CLAUDE.md` (M-OPS-210) | docs/operations/orchestration.md#known-traps |
| M-OPS-013 | §5 (`:126`) | `catchup` is set explicitly although Airflow 3 defaults it to False | requirement | move | orchestration | OPS | living-docs-operations | Merged into M-OPS-019 | OPS-025 |
| M-OPS-014 | §5 (`:128`) | Airflow owns when a source is polled; no RabbitMQ | rationale | move | orchestration (Rationale) | OPS | living-docs-operations | Non-normative | docs/operations/orchestration.md#rationale |
| M-OPS-015 | §5 (`:130`) | Pipeline stateless; `next_cursor` = earliest failed, else latest processed, else input when capped | requirement | link | `docs/ingestion/pipeline.md` | ING | living-docs-ingestion | Cursor rule owner is ING |  |
| M-OPS-016 | §5 step 1 (`:134`) | Task reads `cursor:{source_type}`; default `now − initial_lookback` in UTC | requirement | move | orchestration | OPS | living-docs-operations | `test_ingestion_dag.py::test_first_run_starts_initial_lookback_days_back_in_utc`. The lookback value is `sources.yaml` (`initial_lookback value`) | OPS-034 |
| M-OPS-017 | §5 step 2 (`:135`) | "Call `IngestionPipeline.run`" | stale | delete | — | — | legacy-docs-retirement | The DAG posts to `/ingest/<source_type>` (INV-3); `auspex_dags.py:32-48` |  |
| M-OPS-018 | §5 step 3 (`:136`) | Write back `next_cursor`, never now; fail the task after writing if any failed | requirement | move | orchestration | OPS | living-docs-operations | `test_ingestion_dag.py::test_ingestion_task_saves_the_safe_cursor_then_fails_when_documents_failed`; DECISIONS `## 2026-10-09 — Soak-test readiness — CHOICE — cursor after a run with failed documents` | OPS-035 |
| M-OPS-019 | §5 (`:141`) | Every DAG: `catchup=False`, `max_active_runs=1`; ingestion schedules staggered | requirement | move | orchestration | OPS | living-docs-operations | Tested for ingestion only (`test_ingestion_dags_disable_catchup_and_run_one_at_a_time`); price, universe, backup and health DAGs untested (F F15) | OPS-025 |
| M-OPS-020 | §5 step 4 (`:137`) | A failed request leaves the Variable untouched | requirement | move | orchestration | OPS | living-docs-operations | `test_ingestion_dag.py::test_ingestion_task_leaves_the_cursor_untouched_when_the_request_fails` | OPS-036 |
| M-OPS-021 | §5 (`:139`) | Backfill never writes the live cursor; mock runner takes the cursor as argument | requirement | link | `docs/ingestion/pipeline.md` | ING | living-docs-ingestion | |  |
| M-OPS-022 | §5 (`:141`) | Overlap "breaks at roughly 5× volume, not 100×" | rationale | move | orchestration (Rationale) | OPS | living-docs-operations | | docs/operations/orchestration.md#rationale |
| M-OPS-023 | §6.5 SEC row (`:192`) | SEC: per-host rate configured in `sources.yaml`; 403 handling | requirement | link | `docs/ingestion/connectors.md` | ING | living-docs-ingestion | Per-connector rate is ING (design §2 seams) |  |
| M-OPS-024 | §6.5 SEC row (`:192`) + at-risk class #8 | All `*.sec.gov` clients that can run together stay under 10 req/s per IP | requirement | move | topology | OPS | living-docs-operations | Aggregate owner (design §2). See M-OPS-240 | OPS-023 |
| M-OPS-025 | §12 intro (`:383`) | Failure mode is fewer or wrong corroborations while containers stay green | rationale | move | observability (Rationale) | OPS | living-docs-operations | | docs/operations/observability.md#rationale |
| M-OPS-026 | §12 bullet 1 (`:385`) | Structured JSON logs carry `source_type` and `external_id`/`event_id` where applicable | requirement | move | observability | OPS | living-docs-operations | One log-field contract with ECS names. `services/ingestion-scraper/tests/unit/test_logging.py::test_connector_error_log_includes_source_type_and_external_id`, `::test_json_logs_use_ecs_level_and_message_fields` | OPS-040 |
| M-OPS-027 | §12 bullet 2 (`:386`) | Run summary per run: full `RunResult` counts plus cursor before and after | requirement | link | `docs/ingestion/pipeline.md` | ING | living-docs-ingestion | `RunResult counters` governs the counters |  |
| M-OPS-028 | §12 bullet 3 (`:387`) | core-hub `@Scheduled` health reporter logs DLT depth and signal age | requirement | link | `docs/core-hub/http-api.md` | HUB | living-docs-core-hub | Its metric names are in the OPS catalogue (M-OPS-120) |  |
| M-OPS-029 | §12 bullet 3 (`:387`) | "from Phase 5 it emits through the notification transport" | stale | delete | — | — | legacy-docs-retirement | No transport exists (A C10); watchlist-alerts is on hold |  |
| M-OPS-030 | §12 bullet 4 (`:388`) | Cursor position is visible in the Airflow UI | requirement | move | orchestration | OPS | living-docs-operations | Holds because the cursor is a Variable. Status `untested` | OPS-033 |
| M-OPS-031 | §12 (`:390`) | "This belongs in Phases 1–2" | history | delete | — | — | legacy-docs-retirement | Plan-phase text |  |
| M-OPS-032 | §12 (`:390`) | A connector returning empty sets looks like a quiet week | rationale | move | observability (Rationale) | OPS | living-docs-operations | Motivates Source Silence and Source Quiet | docs/operations/observability.md#rationale |

### docker/README.md

| Row | Source (path:line or §) | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-OPS-040 | `docker/README.md:9-41` | Services table: image, port, purpose per container | value | keep | `docker/README.md` | — | legacy-docs-retirement | Trimmed to service → purpose → profile. Image tags (`VERSIONS.md`), ports and schedules (compose, DAG files) removed |  |
| M-OPS-041 | `docker/README.md:14` | Bucket roles: raw archive, prices, strategy state | contract | link | `docs/system/overview.md` | SYS | living-docs-system-and-contracts | The naming table is the owner |  |
| M-OPS-042 | `docker/README.md:20` | `minio-init` creates every stack bucket, no-op when present | requirement | move | topology | OPS | living-docs-operations | `services/backtesting/tests/unit/test_stack_bootstrap.py::test_stack_creates_the_raw_prices_and_strategy_buckets`, `::test_missing_buckets_are_created_and_existing_ones_left_alone` | OPS-010 |
| M-OPS-043 | `docker/README.md:21` | `price-bootstrap` fills missing snapshots; fails `up --wait` on a ticker without data | requirement | link | `docs/research/market-data.md` | RES | living-docs-research | Behaviour is RES; that it is a one-shot is M-OPS-061 |  |
| M-OPS-044 | `docker/README.md:22` | price-service endpoints `POST /prices/refresh`, `/universe/build` | contract | link | `docs/research/market-data.md`, `docs/research/universe.md` | RES | living-docs-research | The DAG that calls each one is in the OPS DAG catalogue (M-OPS-100) |  |
| M-OPS-045 | `docker/README.md:23` | Backup mirrors "both MinIO buckets" | stale | delete | — | — | legacy-docs-retirement | **Finding #8.** Three buckets are mirrored (compose `:247`). Replaced by a link to `backup` |  |
| M-OPS-046 | `docker/README.md:24`, `docker/README.md:43` | `restore` runs only under profile `restore`; app services only under `app` | requirement | move | topology | OPS | living-docs-operations | `test_stack_backup_config.py::test_restore_service_runs_only_under_the_restore_profile`; `test_dashboard_stack_config.py::test_dashboard_service_is_in_app_profile_bound_to_localhost_with_healthcheck` (dashboard only) | OPS-004 |
| M-OPS-047 | `docker/README.md:25` | `elasticsearch-setup` applies ILM; delete after 30 days | value | link | `docker/elasticsearch/ilm_policy.json` | OPS | living-docs-operations | The rule "log indices are deleted by ILM" is M-OPS-134 |  |
| M-OPS-048 | `docker/README.md:28` | strategy-runtime consumes corroborations, books in `auspex-strategy` | contract | link | `docs/strategy/runtime.md` | STR | living-docs-strategy-and-dashboard | |  |
| M-OPS-049 | `docker/README.md:30` | Airflow DAG schedules and which DAGs are active at creation | value | link | DAG files; orchestration | OPS | living-docs-operations | Schedules stay in the DAG files and `sources.yaml`; the active/paused rule is M-OPS-103 |  |
| M-OPS-050 | `docker/README.md:31-33`, `docker/README.md:37-41` | Exporters, cAdvisor, volume-usage: what each measures | requirement | move | observability | OPS | living-docs-operations | Merged with M-OPS-137 | OPS-045 |
| M-OPS-051 | `docker/README.md:34-36` | One-shots `airflow-db-role`, `airflow-state-init`, `postgres-monitor-role` re-applied on every `up` | requirement | move | topology | OPS | living-docs-operations | `test_stack_persistence_config.py::test_airflow_db_role_job_runs_before_airflow_and_after_postgres`, `::test_airflow_state_volume_is_made_writable_for_the_airflow_user_before_airflow_starts` | OPS-013 |
| M-OPS-052 | `docker/README.md:43` | Ports bound to 127.0.0.1; exporters publish none | requirement | link | topology (M-OPS-009) | OPS | living-docs-operations | Same ID as M-OPS-009 |  |
| M-OPS-053 | `docker/README.md:45` | Every service has a `mem_limit`; long-running sum fits the VM less 512 MB | requirement | move | topology | OPS | living-docs-operations | `test_stack_observability_config.py::test_every_service_has_a_memory_limit`, `::test_long_running_memory_limits_fit_the_vm_budget`. DECISIONS `## 2026-10-09 — Infrastructure observability — CHOICE — memory limits sized to 7.5 GB, first estimates` | OPS-014 |
| M-OPS-054 | `docker/README.md:47-67` | Memory budget table, MB per service | value | delete | — | — | legacy-docs-retirement | Copies `.env.example`. topology names the variables' group, never the numbers |  |
| M-OPS-055 | `docker/README.md:51-56` | Airflow one API worker and ≤ 4 tasks; Neo4j heap + page cache ≤ 75% | requirement | move | topology | OPS | living-docs-operations | `::test_airflow_runs_one_api_worker_and_at_most_four_tasks`, `::test_neo4j_heap_and_page_cache_fit_within_its_limit` | OPS-015 |
| M-OPS-056 | `docker/README.md:69-78` | Every store on the VM disk has a bound or a watch | requirement | move | topology | OPS | living-docs-operations | Source `specs/done/container-limits-and-log-rotation.md:27`. Values in the table are deleted (`.env.example`, `topics.yaml`, ILM) | OPS-016 |
| M-OPS-057 | `docker/README.md:84-88` | Compose up, down, `down -v` commands | command | link | `README.md` (stack commands) | — | legacy-docs-retirement | Root README owns stack commands (design §7.2). `down -v` keeps "destroys all data" on its line |  |
| M-OPS-058 | `docker/README.md:90` | `--wait` waits for healthchecks and one-shots; Airflow healthcheck ~60 s is normal | trap | move | topology (Known traps) | OPS | living-docs-operations | No ID; trap | docs/operations/topology.md#known-traps |
| M-OPS-059 | `docker/README.md:96-105` | Topics table: partitions, retention | value | link | `docker/topics.yaml`, `docs/system/contracts.md` | CON | living-docs-system-and-contracts | |  |
| M-OPS-060 | `docker/README.md:107` | DLT publishes to the same partition number | stale | delete | — | — | legacy-docs-retirement | **Finding #4.** Resolver returns -1 (`KafkaConfig.java:177-189`). Owner CON-005 |  |
| M-OPS-061 | `docker/README.md:109` | Fix one topic's partition count without `down -v` | process | keep | `docker/README.md` | — | legacy-docs-retirement | Operator procedure stays in the stack README |  |
| M-OPS-062 | `docker/README.md:113-122` | Two databases in one Postgres container, created on first volume init | requirement | move | topology | OPS | living-docs-operations | Same ID as M-OPS-003 plus the init script fact | OPS-012 |
| M-OPS-063 | `docker/README.md:122` | Flyway runs on every core-hub start | requirement | link | `docs/core-hub/storage.md` | HUB | living-docs-core-hub | |  |
| M-OPS-064 | `docker/README.md:126-128` | Every stateful path on a named volume; recreate picks up where it left off | requirement | move | topology | OPS | living-docs-operations | `test_stack_persistence_config.py::test_every_stateful_service_keeps_its_data_dir_on_a_declared_named_volume`; source `specs/done/stack-state-persistence.md` | OPS-017 |
| M-OPS-065 | `docker/README.md:128` | Kafka offsets outlive topic retention; cluster ID pinned; project name `auspex` | requirement | move | topology | OPS | living-docs-operations | `::test_kafka_offsets_outlive_the_longest_topic_retention`, `::test_kafka_cluster_id_is_pinned_to_the_id_existing_volumes_were_formatted_with`, `::test_compose_file_names_the_project_and_env_example_agrees` | OPS-018 |
| M-OPS-066 | `docker/README.md:128` | Fernet key, JWT secret, API secret from `.env` keep Variables readable | requirement | move | orchestration | OPS | living-docs-operations | M-OPS-108 | OPS-037 |
| M-OPS-067 | `docker/README.md:130` | `down -v` destroys all data; nothing needs it as a fix | requirement | move | topology | OPS | living-docs-operations | `::test_docs_never_offer_down_v_as_a_fix` (file list extended by legacy) | OPS-019 |
| M-OPS-068 | `docker/README.md:132-136` | Nightly backup to `BACKUP_HOST_DIR`; restore command | requirement | link | backup; `README.md` (restore command) | OPS | living-docs-operations, legacy-docs-retirement | |  |
| M-OPS-069 | `docker/README.md:138-146` | Changing a password in place, per store | process | keep | `docker/README.md` | — | legacy-docs-retirement | Cited by `SETUP.md:42` |  |
| M-OPS-070 | `docker/README.md:150` | Services log ECS JSON; Filebeat ships to daily indices | requirement | move | observability | OPS | living-docs-operations | With M-OPS-026 | OPS-040 OPS-043 |
| M-OPS-071 | `docker/README.md:152-157` | Four Grafana dashboards and their panels | value | link | `docker/grafana/provisioning/dashboards/*.json` | OPS | living-docs-operations | observability names the files and their purpose, not the panels |  |
| M-OPS-072 | `docker/README.md:159-182` | Alert table: title, condition, thresholds | requirement | move | observability (alert intent) | OPS | living-docs-operations | Titles and intent only; thresholds stay in `.env.example` and the rule YAML | OPS-055 |
| M-OPS-073 | `docker/README.md:184` | Daily health summary contents and delivery | requirement | move | observability | OPS | living-docs-operations | M-OPS-130 | OPS-059 |
| M-OPS-074 | `docker/README.md:186` | One contact point `auspex-default`; repeat every 4 h; `$$` escaping | requirement | move | observability | OPS | living-docs-operations | Repeat interval is a value in `policies.yaml`; the `$$` part is a trap | OPS-054 |
| M-OPS-075 | `docker/README.md:188` | Prometheus retention bounded by time and by size | requirement | move | observability | OPS | living-docs-operations | `::test_prometheus_retention_is_bounded_by_time_and_size`; values in `.env.example` | OPS-050 |
| M-OPS-076 | `docker/README.md:190` | Mac vs VM metrics; Mac exporter optional, info alert when absent | requirement | move | observability | OPS | living-docs-operations | `::test_mac_host_job_targets_host_docker_internal_node_exporter` | OPS-046 |
| M-OPS-077 | `docker/README.md:192` | Key metric names per service | contract | move | observability (metric catalogue) | OPS | living-docs-operations | The single catalogue (design §2) | OPS-052 |
| M-OPS-078 | `docker/README.md:194` | Grafana smoke script `docker/grafana/test_provisioning.sh` | command | link | `README.md` (stack commands) | — | legacy-docs-retirement | observability cites it under Verification |  |
| M-OPS-079 | `docker/README.md:198-205` | Environment variables to fill | process | link | `SETUP.md` step 1 | — | legacy-docs-retirement | SETUP owns the secrets list |  |
| M-OPS-080 | `docker/README.md:207` | No compose defaults; old `.env` needs new keys added | requirement | move | topology | OPS | living-docs-operations | M-OPS-090 | OPS-006 |
| M-OPS-081 | `docker/README.md:211-224` | Model server runs on the host; scraper reaches it via `host.docker.internal`; models mounted read-only | requirement | move | topology | OPS | living-docs-operations | Source `specs/done/local-model-integration.md:28` (mount); `extra_hosts` host-gateway is compose-only → ratify that half | OPS-001 OPS-002 OPS-003 |
| M-OPS-082 | `docker/README.md:226-228` | Ollama ignores per-request `num_ctx` | trap | link | `docs/ingestion/extraction.md`; `docs/local-model-runbook.md` | EXT | living-docs-ingestion | |  |
| M-OPS-083 | `docker/README.md:230-242` | Host memory budget for Ollama beside the 8 GB VM | value | delete | — | — | legacy-docs-retirement | Duplicate of `docs/local-model-runbook.md` "Memory budget"; the 8 GB VM rule is M-OPS-091 |  |

### docker/CLAUDE.md (content rows; the file's disposition is `living-docs-system-and-contracts`'s)

| Row | Source (path:line or §) | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-OPS-084 | `docker/CLAUDE.md:5-11` | Compose commands incl. `down -v` warning | command | link | `README.md` | — | agent-instruction-hierarchy | `docker/AGENTS.md` may repeat them for Codex (`agent-instruction-hierarchy` decides) |  |
| M-OPS-085 | `docker/CLAUDE.md:15-17` | `kafka-init`, `minio-init`, `price-bootstrap` are no-ops when data exists | requirement | link | topology (M-OPS-061/042) | OPS | living-docs-operations | |  |
| M-OPS-086 | `docker/CLAUDE.md:19-20` | Startup data in a one-shot; current data in a DAG; never a hand-run script | requirement | move | topology | OPS | living-docs-operations | M-OPS-092. The agent-workflow half stays in root `AGENTS.md` (design §7.2) | OPS-009 |
| M-OPS-087 | `docker/CLAUDE.md:22-25` | DLT partition parity; lowercase `.dlt`; resolver −1 | contract | link | `docs/system/contracts.md` | CON | living-docs-system-and-contracts | Finding #4 wording |  |
| M-OPS-088 | `docker/CLAUDE.md:29-31` | "Every `.env.example` variable is a bare `${VAR}` in compose" | stale | delete | — | — | legacy-docs-retirement | Literally false: 51 keys are host-script config (F F5). Restated as tested in M-OPS-090 |  |
| M-OPS-089 | `docker/CLAUDE.md:31-32` | Ports on 127.0.0.1; exporters publish none | requirement | link | topology (M-OPS-009) | OPS | living-docs-operations | |  |
| M-OPS-090 | `docker/CLAUDE.md:29-31` (as tested) | Compose gives no default to a variable `.env.example` defines; required secrets use `:?` | requirement | move | topology | OPS | living-docs-operations | `test_repo_scaffolding.py::test_compose_gives_no_default_to_env_example_variables`; DECISIONS `… — CHOICE — monitoring values only in .env.example` | OPS-006 |
| M-OPS-091 | `docker/CLAUDE.md:36-37` | Every service: `mem_limit`, log label, scrape job or probe if healthchecked | requirement | move | topology, observability | OPS | living-docs-operations | Split: limit → topology; label and scrape → observability | OPS-014 OPS-043 OPS-044 |
| M-OPS-092 | `docker/CLAUDE.md:38-39` | Shared rotating `json-file` log driver, not `local` | requirement | move | observability | OPS | living-docs-operations | `::test_every_service_uses_the_shared_rotating_log_driver`; DECISIONS `… — CHOICE — json-file log driver with rotation, not local` | OPS-042 |
| M-OPS-093 | `docker/CLAUDE.md:40-42` | Grafana expands `$VAR` in alerting files; promtool case per rule | trap | move | observability (Known traps) | OPS | living-docs-operations | Rule half: M-OPS-127 | docs/operations/observability.md#known-traps |
| M-OPS-094 | `docker/CLAUDE.md:46-50` | New stateful service: named volume, mounted into `volume-usage`; Fernet from `.env` | requirement | move | topology, orchestration | OPS | living-docs-operations | `::test_volume_usage_mounts_every_named_volume` | OPS-017 OPS-037 |
| M-OPS-095 | `docker/CLAUDE.md:51` | Never suggest `down -v`; every mention says it destroys data | requirement | link | topology (M-OPS-067) | OPS | living-docs-operations | |  |
| M-OPS-096 | `docker/CLAUDE.md:56-57` | `--wait` blocks on healthchecks; Airflow healthcheck slow | trap | link | topology (M-OPS-058) | OPS | living-docs-operations | |  |
| M-OPS-097 | `docker/CLAUDE.md:61-64` | Two databases; role re-applied every `up`; wipe recreates both | requirement | link | topology (M-OPS-062) | OPS | living-docs-operations | "If you wipe volumes" is not offered as a fix |  |

### orchestration/README.md

| Row | Source (path:line or §) | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-OPS-098 | `orchestration/README.md:3` | DAG writes `max_published_date_processed` only on success | stale | delete | — | — | legacy-docs-retirement | Pre-2026-10-09 rule (F F4). Replaced by M-OPS-018 |  |
| M-OPS-099 | `orchestration/README.md:3` | One DAG per `sources.yaml` entry; DAG holds no logic | requirement | link | orchestration; `docs/system/invariants.md#INV-3` | OPS | living-docs-operations | `test_ingestion_dag.py::test_ingestion_dag_defines_one_dag_per_sources_entry` |  |
| M-OPS-100 | `orchestration/README.md:9` | DAG catalogue: each DAG, the endpoint it posts to, its owner doc | requirement | move | orchestration | OPS | living-docs-operations | Catalogue lists all six DAG kinds; schedules by file reference | OPS-024 |
| M-OPS-101 | `orchestration/README.md:11` | DAG mount paths inside Airflow | value | link | `docker/docker-compose.yml` | — | legacy-docs-retirement | `test_stack_backup_config.py::test_backup_dag_directory_is_mounted_into_airflow` |  |
| M-OPS-102 | `orchestration/README.md:17` | "A failed run leaves the cursor unchanged" | stale | delete | — | — | legacy-docs-retirement | Wrong for a run with failed documents (F F4) |  |
| M-OPS-103 | `orchestration/README.md:9` + `SETUP.md:28` | Ingestion DAGs paused at creation until a gated model exists; others active | requirement | move | orchestration | OPS | living-docs-operations | Source DECISIONS `## 2026-10-07 — Startup data — CHOICE — data fills itself on up; prices refresh daily`. Flags `is_paused_upon_creation=False` untested (F F15) | OPS-026 |
| M-OPS-104 | `orchestration/README.md:23` | DAG entry point and its test file | status-note | keep | `orchestration/README.md` | — | legacy-docs-retirement | Pointer file |  |
| M-OPS-105 | `orchestration/README.md:29` | New source needs only a `sources.yaml` entry | invariant | link | `docs/system/invariants.md#INV-4` | INV | legacy-docs-retirement | |  |
| M-OPS-106 | `orchestration/README.md:35-36` | Airflow 3 notes | trap | link | orchestration (M-OPS-012) | OPS | living-docs-operations | |  |
| M-OPS-107 | `orchestration/README.md:37` | API keys are Airflow Connections | stale | delete | — | — | legacy-docs-retirement | `invariant 6 wording`; contradicted by compose `:445-455` |  |

### Orchestration and topology facts from code, tests and archived specs

| Row | Source (path:line or §) | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-OPS-108 | `docker/docker-compose.yml:656-658`; `specs/done/stack-state-persistence.md` | Fernet key, JWT secret, API secret are required `.env` references | requirement | move | orchestration | OPS | living-docs-operations | `::test_airflow_fernet_key_jwt_secret_and_api_secret_key_are_required_env_references` | OPS-037 |
| M-OPS-109 | `services/ingestion-scraper/tests/unit/test_stack_persistence_config.py:91` | Airflow uses no Airflow 2 `webserver.*` options | requirement | move | orchestration | OPS | living-docs-operations | `::test_airflow_uses_no_airflow_2_webserver_options`; DECISIONS VERIFIED 2026-10-10 | OPS-038 |
| M-OPS-110 | `services/ingestion-scraper/tests/unit/test_stack_persistence_config.py:97` | Admin password file sits on the `airflow_state` volume | requirement | move | orchestration | OPS | living-docs-operations | `::test_airflow_password_file_is_on_the_airflow_state_volume` | OPS-039 |
| M-OPS-111 | `services/ingestion-scraper/tests/unit/test_ingestion_dag.py:239-287` | Live sources start ≥ 30 min apart; schedule-less source never scheduled | requirement | move | orchestration | OPS | living-docs-operations | `::test_live_sources_start_at_distinct_times`, `::test_source_without_schedule_is_never_scheduled` | OPS-027 OPS-028 |
| M-OPS-112 | `services/ingestion-scraper/tests/unit/test_ingestion_dag.py:253-259` | Ingestion tasks share the single-slot `ingestion` pool, created before the scheduler | requirement | move | orchestration | OPS | living-docs-operations | `::test_ingestion_tasks_use_the_single_slot_ingestion_pool`, `::test_airflow_creates_the_ingestion_pool_before_the_scheduler_starts` | OPS-029 |
| M-OPS-113 | `services/ingestion-scraper/tests/unit/test_ingestion_dag.py:269-278` | Ingestion retries and spacing; HTTP timeout equals task timeout | requirement | move | orchestration | OPS | living-docs-operations | `::test_ingestion_tasks_retry_twice_fifteen_minutes_apart`, `::test_ingestion_http_timeout_matches_the_task_execution_timeout`. Values stay in `auspex_dags.py` | OPS-030 |
| M-OPS-114 | `services/backtesting/dags/*.py`, `services/backup/dags/backup.py`, `daily_health.py` | Non-ingestion DAGs retry and fail on any HTTP error | requirement | ratify | orchestration | OPS | living-docs-operations | Only `test_backup_dag_posts_to_the_backup_service_and_fails_on_http_error` exists; retries code-only | OPS-031 |
| M-OPS-115 | `services/ingestion-scraper/config/gunicorn.conf.py:1-6` | Scraper serves from one gunicorn process with threads | requirement | ratify | topology | OPS | living-docs-operations | `test_metrics.py::test_gunicorn_serves_from_one_process_so_metrics_are_not_split_across_workers`. Only source: CLAUDE trap and conf comment | OPS-021 |
| M-OPS-116 | `services/{backtesting,backup}/config/gunicorn.conf.py:2` | price-service and backup also run one worker | requirement | ratify | topology | OPS | living-docs-operations | Code only; untested | OPS-022 |
| M-OPS-117 | `services/*/Dockerfile` (6 files) | Each service image builds from its own directory; backup on `postgres:18.6` | requirement | move | topology | OPS | living-docs-operations | Backup half: DECISIONS `## 2026-10-10 — Stack backup — CHOICE — client tools from the server image, memory and restore semantics`. Six Dockerfiles, not five (design §2 says 5) | OPS-020 |
| M-OPS-118 | `services/backup/src/auspex_backup/api.py:33` | `POST /backup` answers 409 while a run is in progress | requirement | ratify | backup | OPS | living-docs-operations | Code and `services/backup/README.md:8` only; untested | OPS-068 |
| M-OPS-119 | `services/ingestion-scraper/tests/unit/test_stack_observability_config.py:139` | Every image pinned to an exact tag present in `VERSIONS.md` | requirement | link | `docs/engineering/conventions.md` | ENG | living-docs-engineering-workflow | Pin rule is ENG; topology links |  |

### Observability (docker README §Observability, alerting files, prometheus.yml, archived specs)

| Row | Source (path:line or §) | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-OPS-120 | `docker/README.md:192`; `specs/done/metrics.md`; alerting YAML; `health_summary.py` | One catalogue of metric names: name, emitter, type, consumers | contract | move | observability | OPS | living-docs-operations | design §2: single catalogue. Emitters: `auspex_ingest/metrics.py`, `price_metrics.py`, core-hub `KafkaConfig`, `CountingDeadLetterRecoverer`, `SignalListener`, `HealthReporter`, `ScheduledCorroborationService`, `auspex_strategy/runtime/main.py`, `volume-usage/collect.sh`, statsd mapping | OPS-052 |
| M-OPS-121 | design §2 seams | Renaming a catalogued metric changes catalogue, rules, dashboards and summary in one PR | requirement | ratify | observability | OPS | living-docs-operations | Rollout rule; only source is the design → owner ratification | OPS-053 |
| M-OPS-122 | `services/ingestion-scraper/tests/unit/test_stack_observability_config.py:120` | Every service with a healthcheck is scraped or probed | requirement | move | observability | OPS | living-docs-operations | `::test_every_compose_service_with_a_healthcheck_is_scraped_or_probed` | OPS-044 |
| M-OPS-123 | `services/ingestion-scraper/tests/unit/test_stack_observability_config.py:361` | Every service labelled for log shipping | requirement | move | observability | OPS | living-docs-operations | `::test_every_service_is_labelled_for_log_shipping` | OPS-043 |
| M-OPS-124 | `services/ingestion-scraper/tests/unit/test_stack_observability_config.py:367`, `services/ingestion-scraper/tests/unit/test_stack_observability_config.py:381` | Exporters use a read-only monitoring role; MinIO metrics internal only | requirement | move | observability | OPS | living-docs-operations | `::test_exporter_credentials_are_a_monitoring_role_not_the_app_owner`, `::test_minio_metrics_are_public_on_the_internal_network_only` | OPS-048 |
| M-OPS-125 | `contactpoints.yaml`, `policies.yaml` | One contact point from `ALERT_CONTACT_TYPE`: email or webhook | requirement | move | observability | OPS | living-docs-operations | `::test_contact_point_and_default_policy_are_provisioned`, `::test_contact_point_settings_come_from_env_placeholders` | OPS-054 |
| M-OPS-126 | `rules.yaml`, `infrastructure.yaml` (22 rules) | Alert intent: one row per rule title, what it detects, no threshold | requirement | move | observability | OPS | living-docs-operations | Sources: DECISIONS alert-definition and pipeline-alerting CHOICEs; `specs/done/infrastructure-observability.md`, `pipeline-alerting-gaps.md` | OPS-055 |
| M-OPS-127 | `services/ingestion-scraper/tests/unit/test_stack_alert_expressions.py:497` | Every alert rule has a promtool firing case and quiet case | requirement | move | observability | OPS | living-docs-operations | `::test_every_new_alert_has_a_promtool_case`, `::test_alert_expressions_fire_on_their_failure_and_stay_quiet_otherwise` | OPS-056 |
| M-OPS-128 | `services/ingestion-scraper/tests/unit/test_stack_observability_config.py:293` | Alert files reference only env vars Grafana receives | requirement | move | observability | OPS | living-docs-operations | `::test_alert_expressions_reference_only_env_vars_grafana_receives` | OPS-057 |
| M-OPS-129 | DECISIONS `## 2026-10-10 — Pipeline alerting gaps — CHOICE — Source Silence reads the last run over 7 days, and no data alerts` | Source Silence survives a scraper restart; no data counts as firing | requirement | move | observability | OPS | living-docs-operations | `::test_source_silence_counts_missing_data_as_alerting`, `test_stack_alert_expressions.py::test_source_silence_fires_when_the_run_gauge_has_been_missing_for_thirty_hours` | OPS-058 |
| M-OPS-130 | `daily_health.py`, `health_summary.py`; DECISIONS `… — CHOICE — which sources the daily summary lists` | Daily summary lists every source, marks stale ones, uses the alert contact | requirement | move | observability | OPS | living-docs-operations | `test_daily_health_summary.py::test_daily_summary_lists_every_live_source_with_its_counts`, `::test_daily_summary_marks_a_source_without_a_run_in_twenty_six_hours`, `::test_daily_summary_dag_runs_once_a_day_at_seven_utc`, `::test_summary_is_emailed_to_every_address`, `::test_summary_is_posted_to_the_webhook` | OPS-059 |
| M-OPS-131 | `docker/README.md:184` | A missing summary means the stack or the Mac is down | rationale | move | observability (Rationale) | OPS | living-docs-operations | | docs/operations/observability.md#rationale |
| M-OPS-132 | DECISIONS `## 2026-10-08 — Control-surface scoping — CHOICE — Grafana for technical health, dashboard for using the application` | Grafana covers stack health; the dashboard is the application interface | requirement | move | observability | OPS | living-docs-operations | DSH links to it | OPS-051 |
| M-OPS-133 | `services/ingestion-scraper/tests/unit/test_stack_observability_config.py:488` | Container logs rotate with a per-container cap | requirement | move | observability | OPS | living-docs-operations | `::test_log_rotation_caps_each_container_at_sixty_megabytes`; cap value from `.env.example` | OPS-042 |
| M-OPS-134 | `ilm_policy.json`; `services/ingestion-scraper/tests/unit/test_stack_observability_config.py:515` | Log indices deleted by the ILM policy; healthcheck access lines dropped | requirement | move | observability | OPS | living-docs-operations | `::test_log_indices_are_deleted_after_thirty_days`, `::test_filebeat_drops_healthcheck_access_lines`. 180 d in `specs/done/centralised-logging.md` is history (F F12) | OPS-043 |
| M-OPS-135 | `services/ingestion-scraper/tests/unit/test_stack_observability_config.py:331` | Airflow statsd mapped to DAG run and task outcomes per `dag_id` | requirement | move | observability | OPS | living-docs-operations | `::test_airflow_statsd_is_enabled_and_mapped_to_dag_outcome_metrics` | OPS-047 |
| M-OPS-136 | `services/ingestion-scraper/tests/unit/test_stack_observability_config.py:583` | Elasticsearch exporter reports read-only indices | requirement | move | observability | OPS | living-docs-operations | `::test_elasticsearch_exporter_reports_read_only_indices` | OPS-049 |
| M-OPS-137 | DECISIONS `… — CHOICE — VM and volume metrics without host bind mounts` | VM metrics via PID 1; volume sizes via `volume-usage` textfile | requirement | move | observability | OPS | living-docs-operations | `::test_volume_usage_reports_each_mounted_volume_in_bytes`, `::test_volume_usage_mounts_every_named_volume` | OPS-045 |
| M-OPS-138 | `verify_pipeline.sh:9-17` | "Smoke test" checks two core-hub REST responses only | status-note | keep | `README.md` | — | legacy-docs-retirement | Root README labels it a core-hub REST smoke check, not pipeline proof (F F16) |  |
| M-OPS-139 | `specs/done/stack-backup.md:38` | No alert on a failed or stale backup beyond DAG failure | status-note | keep | `ops` Notes | — | living-docs-operations | Gap (F F8). Not a requirement; a follow-up spec is recommended, not created here |  |

### Backup (docs/backup-restore.md, services/backup/README.md, code)

| Row | Source (path:line or §) | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-OPS-140 | `docs/backup-restore.md:3-5`; DECISIONS `## 2026-10-09 — Stack backup — CHOICE — nightly backup to a folder on the Mac` | Nightly DAG calls the backup service; output in `BACKUP_HOST_DIR` | requirement | move | backup | OPS | living-docs-operations | `test_backup_dag.py::test_backup_dag_posts_to_the_backup_service_and_fails_on_http_error`; `test_stack_backup_config.py::test_backup_destination_is_a_bind_mount_from_backup_host_dir` | OPS-060 |
| M-OPS-141 | `docs/backup-restore.md:11`; `docker/docker-compose.yml:240` | Both Postgres databases dumped in custom format, password only in env | requirement | move | backup | OPS | living-docs-operations | `test_postgres_dump.py::test_postgres_dump_runs_custom_format_pg_dump_for_both_databases_with_password_only_in_env` | OPS-061 |
| M-OPS-142 | `docs/backup-restore.md:12` | Neo4j exported whole, in one read transaction | requirement | move | backup | OPS | living-docs-operations | `test_graph.py::test_neo4j_export_writes_every_node_and_relationship_with_labels_and_properties` | OPS-062 |
| M-OPS-143 | `docs/backup-restore.md:13`; `docker/docker-compose.yml:247`; DECISIONS `## 2026-10-10 — Strategy runtime — CHOICE — state placement, timing and the pass-through stub` item 1 | Additive mirror of every bucket the stack creates | requirement | move | backup | OPS | living-docs-operations | **Finding #8: status `untested`.** No test ties `BACKUP_BUCKETS` (compose `:247`) to `stack_bootstrap.stack_buckets()` (`stack_bootstrap.py:35`) | OPS-063 |
| M-OPS-144 | `docs/backup-restore.md:13-14` | Mirror never pruned; deleted objects kept; copies only new or changed | requirement | move | backup | OPS | living-docs-operations | `test_minio_mirror.py::test_minio_mirror_keeps_objects_deleted_from_minio`, `::test_minio_mirror_copies_only_new_or_changed_objects` | OPS-064 |
| M-OPS-145 | `docs/backup-restore.md:11-12`; DECISIONS client-tools CHOICE item 3 | Dated folders strictly older than keep-days pruned; newest never | requirement | move | backup | OPS | living-docs-operations | `test_prune.py::test_dated_folders_older_than_keep_days_are_pruned_and_the_newest_never_is`. Value `BACKUP_KEEP_DAYS` in `.env.example` | OPS-066 |
| M-OPS-146 | `docs/backup-restore.md:15-17`; `services/backup/README.md:8` | `last_success.json` written last, only when every store succeeded | requirement | move | backup | OPS | living-docs-operations | `test_backup_run.py::test_manifest_is_written_last_and_only_when_every_store_succeeded`, `::test_failed_store_returns_500_naming_it_and_keeps_the_previous_manifest` | OPS-067 |
| M-OPS-147 | `specs/done/stack-backup.md:33-39` | Elasticsearch, Prometheus, Grafana and Kafka are not backed up, with reasons | requirement | move | backup | OPS | living-docs-operations | Archived spec is the only source; status `untested` (exclusion) | OPS-071 |
| M-OPS-148 | `services/backup/README.md:15` | Backup only reads the stores | requirement | move | backup | OPS | living-docs-operations | `test_backup_run.py::test_backup_reads_but_never_writes_to_minio_postgres_or_neo4j` | OPS-069 |
| M-OPS-149 | `services/backup/README.md:15`; `docs/backup-restore.md:32-34` | Restore writes the stores only when they are empty, app stopped | invariant | link | `docs/system/invariants.md#INV-2` | INV | living-docs-system-and-contracts | `## 2026-10-15 — Living docs — PENDING — restore exception to invariant 2`. backup links, never restates |  |
| M-OPS-150 | `services/backup/README.md:17` | Cypher labels allow-listed before use; values parameterised | requirement | move | backup | OPS | living-docs-operations | Applies INV-12. `test_graph.py::test_neo4j_replay_rejects_a_label_that_is_not_a_plain_identifier` | OPS-070 |
| M-OPS-151 | `services/backup/tests/unit/test_minio_mirror.py:49` | Mirror refuses a key escaping its bucket folder | requirement | move | backup | OPS | living-docs-operations | `::test_minio_mirror_refuses_a_key_that_escapes_the_bucket_folder` | OPS-065 |
| M-OPS-152 | `docs/backup-restore.md:26-28` | MinIO mirror is undated; restore pairs dated stores with latest mirror | trap | move | backup (Known traps) | OPS | living-docs-operations | Consistency risk F F9 recorded in `ops` Notes | docs/operations/backup.md#known-traps |
| M-OPS-153 | `docs/backup-restore.md:30-66` | Restore order, commands and checks | process | keep | `docs/backup-restore.md` | — | living-docs-operations | Runbook keeps its path (`restore.py:2`). `ops` adds one line linking `backup` |  |
| M-OPS-154 | `docs/backup-restore.md:51-52` | Restore needs the same Fernet key | requirement | link | orchestration (M-OPS-108) | OPS | living-docs-operations | |  |
| M-OPS-155 | `services/backup/README.md:20-27` | uv, ruff, mypy, pytest commands | command | link | `services/backup/AGENTS.md` | — | agent-instruction-hierarchy, legacy-docs-retirement | |  |
| M-OPS-156 | `services/backup/README.md:6-11` | Pieces table: endpoint, health, DAG, restore entry point | status-note | keep | `services/backup/README.md` | — | legacy-docs-retirement | Orientation table stays; behaviour columns link to `backup` |  |

### SETUP.md

| Row | Source (path:line or §) | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-OPS-160 | `SETUP.md:1-10` | Purpose; the one `up` command | process | keep | `SETUP.md` | — | legacy-docs-retirement | Frozen path (compose `:?` messages, `route.ts:10`, `prometheus.yml:63`, two tests) |  |
| M-OPS-161 | `SETUP.md:16` | `minio-init` creates `auspex-raw`, `auspex-prices` | stale | delete | — | — | legacy-docs-retirement | **Finding #8.** Fixed to the three buckets |  |
| M-OPS-162 | `SETUP.md:13-21` | Startup table omits `airflow-db-role`, `airflow-state-init` | stale | keep | `SETUP.md` | — | legacy-docs-retirement | Rows added (F F11) |  |
| M-OPS-163 | `SETUP.md:23-28` | Schedule table omits `auspex_daily_health` | stale | keep | `SETUP.md` | — | legacy-docs-retirement | Row added; schedule text copies DAG values (runbook; tolerated, noted) |  |
| M-OPS-164 | `SETUP.md:32-56` | `.env` secrets table, Fernet note, keep `.env` safe | process | keep | `SETUP.md` | — | legacy-docs-retirement | Must keep backticked `AIRFLOW_FERNET_KEY`, `AIRFLOW_JWT_SECRET`, `AIRFLOW_SECRET_KEY` (`test_new_secrets_are_documented_in_setup`) |  |
| M-OPS-165 | `SETUP.md:58-65` | Host settings: Docker 8 GB, node_exporter, Docker login, Linux sysctl | process | keep | `SETUP.md` | — | legacy-docs-retirement | The 8 GB rule's owner is topology (M-OPS-170) |  |
| M-OPS-166 | `SETUP.md:69-71` | Model must reach 0.85 `is_signal` precision | requirement | link | `docs/ingestion/extraction.md` | EXT | living-docs-ingestion | at-risk class #19 |  |
| M-OPS-167 | `SETUP.md:77-83` | Unpause regex for live ingestion | command | keep | `SETUP.md` | — | legacy-docs-retirement | Regex also matches active DAGs, harmless (F §2.1) |  |
| M-OPS-168 | `SETUP.md:85-92` | Backfill via `scripts/run_backfill.py` and `BACKFILL_*` ceilings | status-note | keep | `SETUP.md` | — | legacy-docs-retirement | Neither exists yet; step names `specs/historical-backfill.md`. Out of scope, noted |  |
| M-OPS-169 | `SETUP.md:94-101` | Before live trading: four owner items | process | keep | `SETUP.md` | — | legacy-docs-retirement | |  |

### Host and resource rules (at-risk class #8, #18; Option A hosting)

| Row | Source (path:line or §) | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-OPS-170 | DECISIONS `## 2026-09-20 — Option A hosting — CHOICE — A1 (MacBook) confirmed for Phase 4; A2/A3 deferred`; `SETUP.md:60` | Stack runs on one Mac: Docker Desktop VM capped 8 GB, model server on host | requirement | move | topology | OPS | living-docs-operations | | OPS-001 |
| M-OPS-171 | at-risk class #18; root `CLAUDE.md:197-200` | Startup data is a no-op one-shot; current data is a DAG calling a service | requirement | move | topology | OPS | living-docs-operations | Source DECISIONS `## 2026-10-07 — Startup data — CHOICE — data fills itself on up; prices refresh daily`. Same ID as M-OPS-086 | OPS-009 |
| M-OPS-172 | at-risk class #18 | Never `down -v` as a fix | requirement | link | topology (M-OPS-067) | OPS | living-docs-operations | |  |
| M-OPS-173 | at-risk class #18 | No hand-run setup scripts; Mac-only work in a spec | process | link | root `AGENTS.md` | — | agent-instruction-hierarchy | Agent workflow rule (design §7.2) |  |
| M-OPS-174 | at-risk class #8 (see M-OPS-240) | SEC budget split across containers | requirement | move | topology | OPS | living-docs-operations | | OPS-023 |
| M-OPS-175 | F F5; `.env.example` | `.env.example` configures compose and host scripts alike | requirement | ratify | topology | OPS | living-docs-operations | No doc states it correctly today (docker/CLAUDE misstates it) | OPS-007 |

### Root CLAUDE.md known traps in the ops domain (destinations coordinated with `living-docs-system-and-contracts`)

| Row | Source (path:line or §) | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-OPS-210 | `CLAUDE.md:216` | Airflow 3 `schedule` rename; Task SDK proxies Variables | trap | move | orchestration (Known traps) | OPS | living-docs-operations | | docs/operations/orchestration.md#known-traps |
| M-OPS-211 | `CLAUDE.md:217` | gunicorn one process; `prometheus_client` per process | trap | move | topology (Known traps) | OPS | living-docs-operations | Requirement half M-OPS-115 | docs/operations/topology.md#known-traps |
| M-OPS-212 | `CLAUDE.md:218` | `make_metrics()` cached per registry; `DuplicateTimeseries` | trap | move | observability (Known traps) | OPS | living-docs-operations | Observability only; other docs link to it | docs/operations/observability.md#known-traps |
| M-OPS-213 | `CLAUDE.md:219` | Grafana `$VAR` expansion; write `$$` | trap | move | observability (Known traps) | OPS | living-docs-operations | | docs/operations/observability.md#known-traps |
| M-OPS-214 | `CLAUDE.md:215` (Docker Hub) | Anonymous Docker Hub limits; compose uses publisher registries | trap | move | topology (Known traps) | OPS | living-docs-operations | CI half (`TESTCONTAINERS_HUB_IMAGE_NAME_PREFIX`) → `docs/engineering/verification.md` (ENG) | docs/operations/topology.md#known-traps |
| M-OPS-215 | `CLAUDE.md:220` | LocalStack calendar tags need a licence | trap | link | `docs/engineering/verification.md` | ENG | living-docs-engineering-workflow | Test images only |  |
| M-OPS-216 | `CLAUDE.md:221` | bcrypt `$` in `.env` must be quoted | trap | link | `docs/dashboard.md`; `SETUP.md:45` | DSH | living-docs-strategy-and-dashboard | SETUP keeps the operator instruction |  |
| M-OPS-217 | `CLAUDE.md:223` | Airflow generates a Fernet key when none set | trap | move | orchestration (Known traps) | OPS | living-docs-operations | Requirement half M-OPS-108 | docs/operations/orchestration.md#known-traps |
| M-OPS-218 | `CLAUDE.md:224` | Docker Desktop on macOS cannot use Metal; model on host | trap | move | topology (Known traps) | OPS | living-docs-operations | Requirement half M-OPS-081 | docs/operations/topology.md#known-traps |
| M-OPS-219 | `CLAUDE.md:225-226` | Ollama context length; tag re-pointing and digest | trap | link | `docs/ingestion/extraction.md`; runbook | EXT | living-docs-ingestion | |  |

### docs/PREREQUISITES.md

| Row | Source (path:line or §) | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-OPS-180 | `docs/PREREQUISITES.md:11-14` | Owner decisions: local model, FINRA credential, backfill time and budget | process | keep | `docs/PREREQUISITES.md` | — | legacy-docs-retirement | Sentences naming `BACKFILL_*` as `.env` settings are cut (M-OPS-181) |  |
| M-OPS-181 | `docs/PREREQUISITES.md:22-23` | `BACKFILL_BUDGET_CEILING`, `BACKFILL_TIME_CEILING_HOURS` in `.env` | stale | delete | — | — | legacy-docs-retirement | Dead knobs: absent from `.env.example` and code. `specs/historical-backfill.md` introduces them |  |
| M-OPS-182 | `docs/PREREQUISITES.md:24` | Backfill depth via `run_backfill.py` flags | stale | delete | — | — | legacy-docs-retirement | Script absent; owned by historical-backfill |  |
| M-OPS-183 | `docs/PREREQUISITES.md:25` | Steady-state LLM budget in `.env` | stale | delete | — | — | legacy-docs-retirement | No variable exists |  |
| M-OPS-184 | `docs/PREREQUISITES.md:33-35` | Alert destination, Mac metrics, dashboard login | status-note | delete | — | — | legacy-docs-retirement | Duplicates SETUP steps 1–2; specs done |  |
| M-OPS-185 | `docs/PREREQUISITES.md:43` | Linux `vm.max_map_count` | process | delete | — | — | legacy-docs-retirement | Duplicate of `SETUP.md:63` |  |
| M-OPS-186 | `docs/PREREQUISITES.md:51-52` | Tax advisor; IBKR account | process | keep | `docs/PREREQUISITES.md` | — | legacy-docs-retirement | |  |
| M-OPS-187 | `docs/PREREQUISITES.md:53` | Borrow availability for "H8 (negative asymmetry)" | stale | keep | `docs/PREREQUISITES.md` | — | legacy-docs-retirement | H8 strategy deleted, shorts off in `protocol.yaml`; the H8 clause is removed, row kept for live trading |  |
| M-OPS-188 | `docs/PREREQUISITES.md:54` | Delisted price source | status-note | delete | — | — | legacy-docs-retirement | Decided 2026-10-07; superseded by point-in-time universe (RES) |  |
| M-OPS-189 | `docs/PREREQUISITES.md:62-65` | `KNOWN_AT_DELAY_DAYS`, `HOLDOUT_MONTHS`, `PROMOTION_*` as `.env` | value | delete | — | — | legacy-docs-retirement | Protocol-owned (`config/hypotheses/protocol.yaml`); not in `.env.example` (F F13, R2 N8) |  |
| M-OPS-190 | `docs/PREREQUISITES.md:66-77` | Cost-model knobs with their defaults | value | link | `.env.example`; `docs/research/simulation.md` | RES | legacy-docs-retirement | Variables exist; defaults are copies. Replaced by one line naming the `.env.example` group |  |
| M-OPS-191 | `docs/PREREQUISITES.md:82` | Already configured: openFDA key; gate thresholds | stale | delete | — | — | legacy-docs-retirement | A status list, not a requirement; `fda_approval` stays an approved source (`divergent`); gate values are EXT and `protocol.yaml` |  |

### Root README.md content

| Row | Source (path:line or §) | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-OPS-192 | `README.md:9` | Architecture paragraph incl. write-token and no-CORS boundary | contract | link | `docs/system/overview.md`; `docs/core-hub/http-api.md` | SYS | legacy-docs-retirement | Kept as one orientation paragraph without rules; "Five public sources" removed |  |
| M-OPS-193 | `README.md:11`, `README.md:95-101` | Hard boundary and key constraints | invariant | link | `docs/system/invariants.md` (INV-1, INV-2, INV-13); `docs/core-hub/storage.md` | INV | legacy-docs-retirement | |  |
| M-OPS-194 | `README.md:15-21` | Services table lists 3 of 7 services; "5 connectors" | stale | keep | `README.md` | — | legacy-docs-retirement | **Finding #6.** Table lists every service directory with a link |  |
| M-OPS-195 | `README.md:27` | Infrastructure versions line | value | link | `VERSIONS.md` | — | legacy-docs-retirement | |  |
| M-OPS-196 | `README.md:33-39` | Quick start incl. `run_pipeline.py --days 30` | command | keep | `README.md` | — | legacy-docs-retirement | `run_pipeline.py` line removed (`run_pipeline.py support`) |  |
| M-OPS-197 | `README.md:45-65` | Development commands, all services | command | keep | `README.md` | — | legacy-docs-retirement | Stack-level rows stay (up, down, `down -v`, restore, smoke, Grafana smoke, kill switch); service rows → service `AGENTS.md` |  |
| M-OPS-198 | `README.md:69-85` | Project structure tree incl. `PROGRESS.md` | stale | keep | `README.md` | — | legacy-docs-retirement | **Finding #6.** `PROGRESS.md` removed; tree lists every service, `config/`, `specs/`, `docs/` |  |
| M-OPS-199 | `README.md:91` | Current status: Phase 3, EPO OPS blocked | stale | delete | — | — | legacy-docs-retirement | **Finding #6.** Status lives in `TODO.md` |  |
| M-OPS-200 | `README.md:105-107` | Watched tickers list | value | link | `.env.example` (`WATCHED_TICKERS`) | — | legacy-docs-retirement | |  |

### VERSIONS.md and docs/HISTORY.md

| Row | Source (path:line or §) | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-OPS-201 | `VERSIONS.md` (whole) | Pins and re-verification list | value | keep | `VERSIONS.md` | — | — | Machine authority (design §4); read by `test_every_new_image_is_pinned_to_an_exact_tag` |  |
| M-OPS-202 | `VERSIONS.md:18` | MinIO row names two buckets | stale | delete | — | — | legacy-docs-retirement | **Finding #8.** Bucket list removed from the note; the tag stays |  |
| M-OPS-203 | `VERSIONS.md:17,32` | "See open question 4/6" | stale | keep | `VERSIONS.md` | — | — | Dangling; not fixed by this rollout (noted in `legacy`) |  |
| M-OPS-204 | `docs/HISTORY.md` (whole) | Phases 0–3 ledger | history | keep | `docs/HISTORY.md` | — | — | Archive; labelled non-normative in `docs/README.md` |  |

### Machine authorities in the ops domain (stay; docs name them, never copy values)

| Row | Source (path:line or §) | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-OPS-205 | `docker/docker-compose.yml` | Services, profiles, healthchecks, mounts, ports, dependencies | value | keep | itself | — | living-docs-operations | topology names it under Machine-readable authorities |  |
| M-OPS-206 | `.env.example` | Limits, thresholds, retention, keep-days, intervals, env names | value | keep | itself | — | living-docs-operations | |  |
| M-OPS-207 | `docker/grafana/provisioning/alerting/*.yaml` | Rules, thresholds, contact point, policy | value | keep | itself | — | living-docs-operations | |  |
| M-OPS-208 | `docker/prometheus/prometheus.yml`, `ilm_policy.json`, `statsd-exporter/mapping.yml`, `blackbox-exporter/`, `filebeat/` | Scrape jobs, probes, log retention, metric mapping | value | keep | itself | — | living-docs-operations | |  |
| M-OPS-209 | DAG files; `sources.yaml` `schedule` | Cron strings, retries, timeouts | value | keep | itself | — | living-docs-operations | orchestration names the files; `no_cron_string_in_orchestration_doc` |  |

### the at-risk classes at-risk classes in this domain

| Row | Source (path:line or §) | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-OPS-240 | at-risk class #8; DECISIONS `## 2026-10-09 — Soak-test readiness — CHOICE — SEC request budget across containers` | EDGAR plus universe lookups stay under SEC's per-IP limit; ownership not overlapping EDGAR | requirement | move | topology | OPS | living-docs-operations | Components tested: `test_universe_sec_index.py::test_filing_index_lookups_run_at_most_five_per_second`; EDGAR rate in `sources.yaml`. Aggregate: `untested`. Filing panel and catalyst clients (host scripts) are named too | OPS-023 |
| M-OPS-241 | at-risk class #18 (ops part) | Never `down -v`; one-shot/DAG rule; ops traps | requirement | move | topology, orchestration, observability | OPS | living-docs-operations | Rows M-OPS-067, M-OPS-171, M-OPS-210…218. Process part (identity, Mac-only spec, Flyway comments) is `living-docs-system-and-contracts`/ENG/HUB | OPS-009 OPS-019 |

### DECISIONS.md CHOICE entries in the ops domain

Binding = absorbed into an OPS ID (cited as `Source`). History = superseded or carried out, no current rule.

| Row | Source (path:line or §) | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-OPS-250 | `DECISIONS.md:40` `## 2026-08-15 — Step 0.0 — CHOICE — MinIO pinned to RELEASE.2025-09-07T16-13-09Z` | MinIO image pin | history | keep | `VERSIONS.md` | — | — | History: the pin lives in `VERSIONS.md` |  |
| M-OPS-251 | `DECISIONS.md:364` `## 2026-09-20 — Option A hosting — CHOICE — A1 (MacBook) confirmed for Phase 4; A2/A3 deferred` | Stack runs on the Mac | rationale | move | topology | OPS | living-docs-operations | History CHOICE (decisions table); the current rule is carried by M-OPS-170 | docs/operations/topology.md#rationale |
| M-OPS-252 | `DECISIONS.md:562` `## 2026-10-07 — Startup data — CHOICE — data fills itself on up; prices refresh daily` | One-shots no-op; refresh by DAG; ingestion paused | requirement | move | topology, orchestration | OPS | living-docs-operations | **Binding** → M-OPS-171, M-OPS-103. The §8 append rule part is RES | OPS-009 OPS-026 |
| M-OPS-253 | `DECISIONS.md:778` `## 2026-10-08 — Control-surface scoping — CHOICE — Grafana for technical health, dashboard for using the application` | Grafana vs dashboard split | requirement | move | observability | OPS | living-docs-operations | **Binding** → M-OPS-132 | OPS-051 |
| M-OPS-254 | `DECISIONS.md:852` `## 2026-10-09 — CI — CHOICE — container images off anonymous Docker Hub` | Compose takes Elastic images from `docker.elastic.co` | trap | move | topology (Known traps) | OPS | living-docs-operations | **Binding** (compose half) → M-OPS-214; CI half ENG | OPS-008 |
| M-OPS-255 | `DECISIONS.md:857` `## 2026-10-09 — CI — CHOICE — remaining test images through mirror.gcr.io` | Test image mirror | history | link | `docs/engineering/verification.md` | ENG | living-docs-engineering-workflow | Superseded by `:974` |  |
| M-OPS-256 | `DECISIONS.md:974` `## 2026-10-09 — CI — CHOICE — one prefix for every test image` | One Testcontainers prefix | requirement | link | `docs/engineering/verification.md` | ENG | living-docs-engineering-workflow | Binding in ENG, not OPS |  |
| M-OPS-257 | `DECISIONS.md:865` `## 2026-10-09 — Stack backup — CHOICE — nightly backup to a folder on the Mac` | Nightly backup, read-only, restore separate | requirement | move | backup | OPS | living-docs-operations | **Binding** → M-OPS-140, M-OPS-148; restore boundary → INV-2 | OPS-060 OPS-069 |
| M-OPS-258 | `DECISIONS.md:870` `## 2026-10-09 — Soak-test readiness — CHOICE — cursor after a run with failed documents` | Save safe cursor, then fail | requirement | move | orchestration | OPS | living-docs-operations | **Binding** → M-OPS-018 (DAG side); ING owns `next_cursor` | OPS-035 |
| M-OPS-259 | `DECISIONS.md:880` `## 2026-10-09 — Soak-test readiness — CHOICE — SEC request budget across containers` | SEC budget across containers | requirement | move | topology | OPS | living-docs-operations | **Binding** → M-OPS-240 | OPS-023 |
| M-OPS-260 | `DECISIONS.md:921` `## 2026-10-09 — Infrastructure observability — CHOICE — monitoring role from a one-shot, not an init script` | Monitoring role from a one-shot every `up` | requirement | move | topology | OPS | living-docs-operations | **Binding** → M-OPS-051 | OPS-013 |
| M-OPS-261 | `DECISIONS.md:925` `## 2026-10-09 — Infrastructure observability — CHOICE — compose defaults for sizes and thresholds` | Compose `${VAR:-default}` | history | delete | — | — | — | **History**: replaced by `:955` the same day |  |
| M-OPS-262 | `DECISIONS.md:930` `## 2026-10-09 — Infrastructure observability — CHOICE — memory limits sized to 7.5 GB, first estimates` | Limits sum to VM less 512 MB | requirement | move | topology | OPS | living-docs-operations | **Binding** → M-OPS-053 (per-service numbers are history; `.env.example` owns) | OPS-014 |
| M-OPS-263 | `DECISIONS.md:935` `## 2026-10-09 — Infrastructure observability — CHOICE — VM and volume metrics without host bind mounts` | VM and volume metrics | requirement | move | observability | OPS | living-docs-operations | **Binding** → M-OPS-137 | OPS-045 |
| M-OPS-264 | `DECISIONS.md:940` `## 2026-10-09 — Infrastructure observability — CHOICE — alert definitions the spec left open` | Four alert definitions | requirement | move | observability | OPS | living-docs-operations | **Binding** → M-OPS-126 | OPS-055 |
| M-OPS-265 | `DECISIONS.md:955` `## 2026-10-09 — Infrastructure observability — CHOICE — monitoring values only in .env.example` | Values only in `.env.example` | requirement | move | topology | OPS | living-docs-operations | **Binding** → M-OPS-090 | OPS-006 |
| M-OPS-266 | `DECISIONS.md:959` `## 2026-10-10 — Infrastructure observability — CHOICE — dashboard memory limit and health probe` | Dashboard limit and probe | requirement | move | topology, observability | OPS | living-docs-operations | **Binding** → M-OPS-053, M-OPS-122 (the number is `.env.example`) | OPS-014 OPS-044 |
| M-OPS-267 | `DECISIONS.md:981` `## 2026-10-10 — Stack state persistence — CHOICE — required secrets and a writable state volume` | Required secrets; state volume; role via psql vars | requirement | move | orchestration, topology | OPS | living-docs-operations | **Binding** → M-OPS-108, M-OPS-051 | OPS-037 OPS-013 OPS-039 |
| M-OPS-268 | `DECISIONS.md:1054` `## 2026-10-10 — Container limits and log rotation — CHOICE — json-file log driver with rotation, not local` | json-file with rotation | requirement | move | observability | OPS | living-docs-operations | **Binding** → M-OPS-092 | OPS-042 |
| M-OPS-269 | `DECISIONS.md:1056` `## 2026-10-10 — Pipeline alerting gaps — CHOICE — Source Silence reads the last run over 7 days, and no data alerts` | Source Silence lookback | requirement | move | observability | OPS | living-docs-operations | **Binding** → M-OPS-129 | OPS-058 |
| M-OPS-270 | `DECISIONS.md:1059` `## 2026-10-10 — Pipeline alerting gaps — CHOICE — which sources the daily summary lists` | Summary lists every source | requirement | move | observability | OPS | living-docs-operations | **Binding** → M-OPS-130 | OPS-059 |
| M-OPS-271 | `DECISIONS.md:1062` `## 2026-10-10 — Pipeline alerting gaps — CHOICE — Elasticsearch read-only indices from the exporter` | ES read-only metric | requirement | move | observability | OPS | living-docs-operations | **Binding** → M-OPS-136 | OPS-049 |
| M-OPS-272 | `DECISIONS.md:1073` `## 2026-10-10 — Stack backup — CHOICE — client tools from the server image, memory and restore semantics` | Image base; partial runs; strict pruning; "empty" definition | requirement | move | backup, topology | OPS | living-docs-operations | **Binding** items 1, 3 → M-OPS-117, M-OPS-145, M-OPS-146. Item 4 ("either bucket") is the restore exception's text → INV-2, and is stale on bucket count (three). Items 2, 5, 6 history | OPS-020 OPS-066 OPS-067 |
| M-OPS-273 | `DECISIONS.md:1083` `## 2026-10-10 — Ingestion run reliability — CHOICE — schedule times, extraction cap and task timeout` | Staggered starts; task timeout shared by HTTP request | requirement | move | orchestration | OPS | living-docs-operations | **Binding** (schedule spacing, timeout) → M-OPS-111, M-OPS-113. Cap is ING. Times are values in `sources.yaml` | OPS-028 OPS-030 |
| M-OPS-274 | `DECISIONS.md:1096` `## 2026-10-10 — Ingestion run reliability — CHOICE — requirements §5 text follows the 2026-10-09 cursor decision` | Doc text aligned | history | delete | — | — | — | **History**: a doc edit, superseded by the cutover |  |
| M-OPS-275 | `DECISIONS.md:1162` `## 2026-10-10 — Strategy runtime — CHOICE — state placement, timing and the pass-through stub` | Third bucket, mirrored by backup; 160 MB | requirement | link | `docs/strategy/runtime.md` | STR | living-docs-strategy-and-dashboard | Binding in STR; OPS cites item 1 as Source of M-OPS-143. Item 7 numbers are history (`.env.example`) |  |
| M-OPS-276 | `DECISIONS.md:809` `## 2026-10-08 — First run on the stack machine — CHOICE — price history from 2013, set before the first up` | `PRICE_HISTORY_START` before first `up` | requirement | link | `docs/research/market-data.md` | RES | living-docs-research | Not OPS |  |
| M-OPS-277 | `DECISIONS.md:320` `## 2026-09-19 — CI/CD pipeline — CHOICE — GitHub-hosted runners` | CI runner choice | requirement | link | `docs/engineering/verification.md` | ENG | living-docs-engineering-workflow | Not OPS |  |
| M-OPS-278 | `DECISIONS.md:875` `## 2026-10-09 — Soak-test readiness — CHOICE — transient Kafka failures pause instead of retrying longer` | Listener pause on store outage | requirement | link | `docs/core-hub/consumption.md` | HUB | living-docs-core-hub | Not OPS |  |
| M-OPS-279 | `DECISIONS.md:261` `## 2026-09-19 — Watchlist & alerts — CHOICE — Discord webhook transport` | Alert transport for watchlist alerts | history | keep | `specs/hold/watchlist-alerts.md` | — | — | On hold; Grafana contact point is the only live alert path |  |

Non-CHOICE entries cited above, for the cutover's classification: `## 2026-10-09 — Stack state persistence — FLAG — what a container or image recreate loses` (history, carried out), `## 2026-10-09 — Infrastructure observability — PENDING — checks on the stack machine` (open; first-run step 8), `## 2026-10-09 — Infrastructure observability — VERIFIED — Grafana expands environment variables in alert provisioning` (source of M-OPS-213), `## 2026-10-10 — Stack state persistence — VERIFIED — Airflow 3.3.1 option names` (source of M-OPS-109), the 2026-10-07 Observability FIX (180-day ILM; history, F F12).

### Active specs owned by `ops`

| Row | Source (path:line or §) | Rule or content (≤ 15 words) | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-OPS-280 | `specs/soak-test-run.md:4` | Blocked-by names four specs at pre-archive paths | stale | keep | `specs/soak-test-run.md` | — | living-docs-operations | Paths fixed to `specs/done/…`; `**Docs impact:**` added |  |
| M-OPS-281 | `specs/soak-test-run.md:11,33-35,56` | Restates schedules, 7,680 MB budget, `down -v` ban, Invariant 9 | requirement | link | OPS IDs, INV-9 | OPS | living-docs-operations | Replaced by IDs; numbers name `.env.example` |  |
| M-OPS-282 | `specs/soak-test-run.md:21,99` | Report written to `docs/soak-test-report.md` | status-note | keep | `specs/soak-test-run.md` | — | living-docs-operations | A new file under `docs/` would fail check E. Needs the non-normative list in `docs-check.toml` (`docs-check-tooling`) — open problem |  |
| M-OPS-283 | `specs/first-run-on-stack-machine.md:4-58` | Restates 8 GB cap, Invariants 6 and 9, commit identity | requirement | link | OPS IDs, INV-6, INV-9, root `AGENTS.md` | OPS | living-docs-operations | `**Docs impact:**` added. Preflight line `:73` unchanged byte for byte |  |

### File-level disposition: every doc file outside `specs/`

| Source file | Final role | Spec |
|---|---|---|
| `README.md` | Human orientation: what Auspex is, quick start, **stack-level commands (owner)**, every service linked, link to `docs/README.md`. No requirements. Frozen path (read by a test) | legacy-docs-retirement |
| `CLAUDE.md` | `@AGENTS.md` only. Frozen path (read by a test) | agent-instruction-hierarchy |
| `AGENTS.md` (new) | Canonical agent instructions | agent-instruction-hierarchy |
| `SETUP.md` | Ordered manual steps (unchanged role); bucket list and missing one-shot and DAG rows fixed. Frozen path | legacy-docs-retirement |
| `TODO.md` | Spec index and session log; no longer auto-loaded | living-docs-cutover |
| `VERSIONS.md` | Machine authority for pins; MinIO row's bucket list removed. Frozen path | legacy-docs-retirement (one note), otherwise untouched |
| `DECISIONS.md` | Append-only log; ratification batch appended by each domain spec | each domain spec; living-docs-cutover |
| `docs/requirements.md` | Non-normative § → ID index (banner plus one table) | legacy-docs-retirement |
| `docs/strategy-research.md` | Rationale, labelled non-normative. Frozen path (`costs.py:13`) | living-docs-system-and-contracts (label in `docs/README.md`) |
| `docs/local-model-runbook.md` | Runbook, unchanged path | living-docs-ingestion (links) |
| `docs/backup-restore.md` | Runbook, unchanged path (`restore.py:2`); gains a link to `docs/operations/backup.md` | living-docs-operations |
| `docs/PREREQUISITES.md` | Owner-action queue; dead `.env` knobs, protocol-owned rows and resolved duplicates removed | legacy-docs-retirement |
| `docs/HISTORY.md` | Archive, unchanged | — |
| `docs/README.md` (new) | Index: domains, owners, namespaces, authority map | living-docs-system-and-contracts |
| `docs/operations/{topology,orchestration,observability,backup}.md` (new) | Living specs, OPS | living-docs-operations |
| `docker/README.md` | Operator orientation: service → purpose → profile table, topic-repair and password-change procedures, links to `docs/operations/*`. Frozen path | legacy-docs-retirement |
| `docker/CLAUDE.md` | `@AGENTS.md` (with `docker/AGENTS.md`). Frozen path | agent-instruction-hierarchy |
| `orchestration/README.md` | Pointer to `docs/operations/orchestration.md` and where DAG files live | legacy-docs-retirement |
| `services/CLAUDE.md`, `services/core-hub/CLAUDE.md`, `services/ingestion-scraper/CLAUDE.md` | `@AGENTS.md` | agent-instruction-hierarchy |
| `services/ingestion-scraper/README.md` | Layout, connectors table (statuses fixed), `sources.yaml` field table as links, scripts table; commands → `AGENTS.md` | legacy-docs-retirement |
| `services/core-hub/README.md` | Layout and packages; behaviour → `docs/core-hub/*`; commands → `AGENTS.md` | legacy-docs-retirement |
| `services/backtesting/README.md` | Layout and scripts table; behaviour → `docs/research/*`; commands → `AGENTS.md` | legacy-docs-retirement |
| `services/strategy/README.md` | Layout; behaviour → `docs/strategy/*`; commands → `AGENTS.md` | legacy-docs-retirement |
| `services/backup/README.md` | Pieces table; behaviour → `docs/operations/backup.md`; commands → `AGENTS.md` | legacy-docs-retirement |
| `services/dashboard/README.md` | Layout and configuration names; behaviour → `docs/dashboard.md`; commands → `AGENTS.md` | legacy-docs-retirement |
| `specs/README.md` (inside `specs/`, listed for completeness) | Spec format, gains `hold` and Docs impact | living-docs-engineering-workflow |

### Row counts

By class: requirement 128 · stale 23 · value 19 · trap 18 · process 12 · history 8 · status-note 8 · contract 7 · command 7 · rationale 6 · invariant 5 (241 rows; numbers M-OPS-001 … M-OPS-283 with gaps between blocks).
By disposition: move 116 · link 58 · keep 35 · delete 26 · ratify 6 (M-OPS-114, -115, -116, -118, -121, -175; M-OPS-081 is half ratify, see its note).
DECISIONS CHOICE entries classified: 30 (M-OPS-250 … M-OPS-279): 20 binding in OPS, 5 binding elsewhere (ENG ×2, STR, RES, HUB), 5 history.


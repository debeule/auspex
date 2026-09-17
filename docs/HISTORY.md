# Build History — Phases 0–3

Completed work. Test counts, pre-fix failures, and key decisions recorded here for reference.

Legend: `[x]` done, tests green & committed · `[!]` blocked (see `DECISIONS.md`)

---

## Phase 0 — Environment & Infrastructure  `branch: phase-0-infra`
- [x] **Preflight & version pinning**
  - [x] Docker daemon reachable; compose v2 present — Docker 27.4.0, Compose v2.31.0
  - [x] Every *resolve at 0.0* entry in `VERSIONS.md` pinned to an exact version — no unresolved entries
  - [x] All four runtime images pulled and healthy (Airflow is Phase 2 only)
  - [x] Toolchain: uv 0.12.5, JDK 25.0.1 (Temurin), Gradle wrapper 9.7.0 on JVM 25 — `./gradlew --version` confirmed
  - [x] `failOnNoDiscoveredTests` confirmed available on Gradle 9.7.0 `Test` task — see DECISIONS.md
  - verified by: preflight checks above  ·  tests: `n/a`
- [x] **Root scaffolding** — verified by: `uv run pytest tests/unit -q` · tests: `4 passed`
  - Pre-fix failure: `AssertionError: Legacy topic prefix found in: ['services/ingestion-scraper/tests/unit/test_step_0_1.py']` — test contained the literal search string; fixed with split construction.
  - Final: 4 passed in 0.06s (Python 3.14.2)
- [x] **Docker Compose & topic provisioning** — verified by: `uv run pytest tests/integration/test_step_0_2.py -v -m integration` · tests: `7 passed`
  - Root cause of Kafka topic-provisioning failure: `docker exec` without `-i` does not attach stdin, so `bash -s` read an empty stream and exited immediately. Fix: `docker exec -i`.
  - Root cause of Kafka AdminClient failures: librdkafka resolves `localhost` to IPv6 `[::1]`; fixed by advertising `127.0.0.1:9092` and using it in bootstrap servers.
  - Final: 7 passed in 5.44s
- [x] Phase 0 DoD met · committed to main

## Phase 1 — Core Pipeline MVP  `branch: phase-1-core-pipeline`
- [x] **Connector contract & raw storage** — verified by: `uv run pytest tests/unit/test_step_1_1.py -m step_1_1` + `uv run pytest tests/integration/test_step_1_1_storage.py -m integration` · tests: `19 unit + 3 integration`
  - Pre-fix failure: `ModuleNotFoundError: No module named 'auspex_ingest.models'` — all 19 unit tests collected as expected.
  - testcontainers race: `MinioContainer` calls `get_exposed_port()` inside the HTTP wait strategy before Docker finishes binding the port. Fixed by using plain `DockerContainer` without a built-in wait strategy and polling manually.
  - Final: 19 unit passed in 0.31s · 3 integration passed in 1.11s · full unit suite 23 passed in 0.46s
- [x] **Mock connector, pre-filter, extraction, pipeline, publish** — verified by: `uv run pytest tests/unit/test_step_1_2.py -m step_1_2` + `uv run pytest tests/integration/test_step_1_2_kafka.py -m integration` · tests: `25 unit + 1 integration`
  - Pipeline order: archive (unconditional, first) → pre-filter → canonical_id discipline → extract → normalize → publish. Matches requirements invariant 13; plan.md order was stale.
  - `raw_content: str = Field(exclude=True)` — excluded from `model_dump_json()` so the Kafka raw-topic payload is a pointer only; MinIO storage re-adds `raw_content` manually.
  - Final: 25 unit passed in 0.25s · 1 integration passed in 23.76s · full unit suite 48 passed in 0.79s
- [x] **Core hub scaffolding** — verified by: `./gradlew check timezoneCheck --rerun-tasks` · tests: `8 unit / 25 container / 1 timezoneCheck — BUILD SUCCESSFUL in 1m 3s`
  - Pre-fix failures (summary): Flyway schema missing (Spring Boot 4.1 splits FlywayAutoConfiguration into `spring-boot-flyway` — add explicitly); Kafka listeners dead (same split, `spring-boot-kafka`); DLT publishing failing (StringSerializer can't handle ResearchSignalEvent on processing failures — fixed with multi-template DLPR: byte[].class→ByteArraySerializer, Object.class→JsonSerializer); JDBC returns java.sql.Timestamp for TIMESTAMPTZ (not OffsetDateTime); Spring Kafka 4.1 DLT header names are `kafka_dlt-exception-message` / `kafka_dlt-original-topic` (old 2.x names removed).
  - DLT resolver re-verified against Spring Kafka 4.1 — see DECISIONS.md.
- [x] **Corroboration service** — verified by: `./gradlew integrationTest --tests '*CorroborationServiceIT' --rerun-tasks` · tests: `15 container`
  - `ScheduledCorroborationService`: watermark-driven scan via Neo4j, supersession via Postgres `<@` array containment, `participants_hash = sha256(sorted event_ids)`. One live row per entity per participant set.
  - Boundary documented: 90-day window is inclusive; `WINDOW_SECONDS = 90 * 24 * 60 * 60`.
  - `application-test.yml` sets `degree-cap: 4` so the cap test needs only 5 signals.
- [x] **REST API** — verified by: `./gradlew integrationTest --tests '*SignalRestIT' --rerun-tasks` · tests: `9 container`
  - `GET /api/v1/signals/{ticker}` with allowlist validation; Cypher returns direct + corroborated signals; injection test uses both Cypher-injection and MATCH DELETE payloads.
- [x] **End-to-end verification** — verified by: `./gradlew integrationTest --tests '*EndToEndIT' --rerun-tasks` · tests: `4 container`
  - Covers mock ingestion→REST response, rerunnable pipeline, archived-but-unpublished recovery, and smoke script.
- [x] **Phase 2 readiness review** — verified by: `uv run pytest tests/unit/test_sources_schema.py -v` · tests: `2 passed`
  - README records cursor rule, ticker resolution, `sources.yaml` schema, extraction-quality gate (≥0.85 precision), and backfill budget (~26,000 LLM calls, ~$65).
- [x] Phase 1 DoD: full suite green — `./gradlew check timezoneCheck --rerun-tasks` → `62 Java tests, BUILD SUCCESSFUL in 1m 32s` · `uv run pytest tests/unit -q` → `84 passed, 2 skipped`

## Phase 2 — Real Source Ingestion  `branch: phase-2-sources`
- [x] **Extraction quality harness** — verified by: `uv run pytest tests/unit/test_scoring.py -v` · tests: `4 passed`
  - Infrastructure: `src/auspex_ingest/golden.py`, `scripts/score_extraction.py`, `tests/golden/FORMAT.txt`.
  - 50 golden documents (DMD gene therapy theme); 4 source types covered; 35 signals / 15 non-signals.
  - Prefilter bug fixed: empty vocab now pass-all (`any()` over empty set was silently reject-all).
  - Extraction prompt tuned: added trial initiation as signal, tightened preclinical rule, added review/characterisation to not-signal list.
  - Final: precision=1.000 ✓ (gate ≥0.85 met), recall=0.629, TP=22 FP=0 FN=13 TN=15. Remaining FNs are structural (8 edgar metadata-only) or borderline. See DECISIONS.md.
- [x] **Airflow, DAG factory, pipeline wiring** — verified by: `uv run pytest tests/unit/test_dag_factory.py -v` · tests: `16 passed`
  - Pre-fix failure: `ModuleNotFoundError: No module named 'auspex_ingest.dag_factory'` — 16 tests collected as expected.
  - `dag_factory.py` uses `Any` for pipeline param; deferred Airflow imports (`airflow.sdk`) guarded by `type: ignore[import-not-found]`.
  - `RateLimitedClient` implements a custom token bucket with injectable clock (pyrate-limiter 4.4.0 doesn't expose clock injection).
  - Airflow added to `docker/docker-compose.yml`; DAG entry point at `dags/auspex_dags.py`.
- [x] **Academic papers connector (bioRxiv + PubMed)** — verified by: `uv run pytest tests/unit/test_academic_papers.py -q` · tests: `12 passed`
  - `BiorxivConnector`: `provides_canonical_id=True`; `external_id=biorxiv:{doi}:v{version}`; `canonical_id=doi:{doi}`; date-only strings parsed as UTC midnight; 429 retried with injectable sleep; pagination via integer cursor.
  - `PubmedConnector`: `provides_canonical_id=False`; sets `canonical_id=doi:{doi}` when DOI present in efetch XML; esearch→efetch two-step; `external_id=pubmed:{pmid}`.
  - Cross-source identity: same DOI from bioRxiv and PubMed → same `canonical_id` → same `event_id` via `uuid5(NAMESPACE_URL, canonical_id)`.
  - Full unit suite: 84 passed, 2 skipped. Ruff and mypy clean.
- [!] **Patent filings connector (EPO OPS)** — ⏳ blocked on EPO OPS credentials
- [x] **Clinical trials connector** — verified by: `uv run pytest tests/unit/test_clinical_trials.py -q` · tests: `13 passed`
  - `ClinicalTrialConnector`: `published_date` = `lastUpdatePostDateStruct.date` for amendments, else `studyFirstPostDateStruct.date`; both dates in raw_content; pagination via `nextPageToken`; 429 retried with injectable sleep.
  - Content-dedup gate added to pipeline: `archive.put()` returns `(key, is_new: bool)`; pipeline skips extraction when `is_new=False`.
  - Full unit suite: 108 passed, 2 skipped.
- [x] **Regulatory connector (FDA approvals)** — verified by: `uv run pytest tests/unit/test_fda_regulatory.py -q` · tests: `11 passed`
  - `FdaApprovalConnector`: openFDA drugsfda endpoint; `published_date` from `action_date` (YYYYMMDD → UTC midnight); 429 raises `QuotaExhaustedError` immediately (daily hard limit, not retriable); 404 → empty iterator.
  - `fda:` canonical prefix added to model allowlist.
  - Full unit suite: 108 passed.
- [x] **SEC EDGAR material disclosures connector** — verified by: `uv run pytest tests/unit/test_sec_edgar.py -q` · tests: `13 passed`
  - `SecEdgarConnector`: EFTS search for 8-K/8-K/A; 403 = IP block → backs off before retry; `User-Agent` header sent on every request (mandatory for SEC).
  - `RateLimitedClient._acquire` gains suffix matching: `{"sec.gov": 5.0}` covers `efts.sec.gov`, `data.sec.gov` etc.
  - Full unit suite: 121 passed.
- [x] **Deduplication & amendment precedence** — verified by: `uv run pytest tests/unit/test_deduplication.py -q` · tests: `9 passed`
  - Canonical marker objects at `dedup/canonical/{sha256(canonical_id)}.json` gate cross-source re-extraction.
  - Marker written only after successful publish; failed write causes at most one redundant extraction.
  - `MinioArchive` gains `get_canonical_marker` / `put_canonical_marker`; all connector test `_FakeArchive` classes updated.
  - Full unit suite: 130 passed.
- [x] **Entity & ticker resolution** — verified by: `uv run pytest tests/unit/test_entity_normalizer.py -q` · tests: `8 passed` · Java `CorroborationServiceContractTest`: `15/15 passed` (unmodified)
  - `HgncEntityNormalizer.from_mappings(gene_aliases, company_tickers)`: gene key = uppercase + hyphens stripped → HGNC alias lookup; company key → SEC ticker or raw name unchanged.
  - `load_sec_company_tickers(dict)` builds normalized-name → ticker map from SEC JSON payload.
  - Full unit suite: 138 passed, 2 skipped.
- [x] Phase 2 exit criterion met — `uv run pytest tests/unit -q` → `138 passed, 2 skipped` · `./gradlew check timezoneCheck --rerun-tasks` → `62 Java tests, BUILD SUCCESSFUL in 1m 36s` · patent connector blocked on EPO OPS credentials (see DECISIONS.md)

## Phase 3 — Corroboration Quality  `branch: phase-3-quality`
- [x] **Confidence scoring** — verified by: `./gradlew test --tests '*CorroborationScorerTest' --rerun-tasks` · tests: `5 unit` · full: `67 Java tests`
  - `CorroborationScorer`: score = 0.7 * diversity_factor + 0.3 * recency_factor, clamped [0,1]. diversity_factor = min(1, (sources-1)/4); recency_factor decays to 0 beyond the 90-day window.
  - Surfaces on `CorroboratedSignalDto.confidence`; no new field. `Clock` bean added to `SchedulingConfig` for injectable time in tests.
- [x] **Corroboration quality review** — precision: 86.7% (26/30 genuine, 4 extraction_error) — PASS ≥85%
  - Infrastructure: `scripts/sample_corroborations.py` (Postgres + Neo4j → enriched JSONL), `scripts/score_corroboration_review.py` (precision report, exits 2 if < 0.85).
  - verified by: `uv run pytest tests/unit/test_sampling.py -q` · tests: `5 passed`
  - 37 live corroborations from 4 sources (CT=203, PubMed=85, bioRxiv=11); 30 sampled seed=42; 7 entities.
  - 4 extraction errors: arginine-therapy-for-SCD (×2 records), CRISPR diagnostic, Leishmania cross-species. See DECISIONS.md.
- [x] Phase 3 exit: `uv run pytest tests/unit -q` → `145 passed` · `./gradlew check timezoneCheck --rerun-tasks` → `67 Java tests, BUILD SUCCESSFUL`

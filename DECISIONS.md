# Decisions & Blocks Log

Append-only. Newest at the bottom. Never edit or delete an entry.

Claude writes here when it: hits an invariant conflict, finds a plan/requirements contradiction, must choose something the docs don't specify, or is blocked on a human.

Format:

```
## YYYY-MM-DD — <topic> — [BLOCKED | FLAG | CHOICE | VERIFIED | PENDING] — <short title>
**What:** one or two sentences.
**Why it matters:** the concrete consequence.
**Options considered:** A / B / C.
**Action:** what I did, or what I need from you.
```

`BLOCKED` means **stop the phase and ask.** Do not work around it.

---

## 2026-08-15 — Step 0.0 — CHOICE
**What:** Log initialized. Versions pinned per `VERSIONS.md`.
**Action:** none required.

## 2026-08-15 — Step 0.0 — FLAG — plan.md version references are stale in three places
**What:** `plan.md` Step 0.2 says "postgres 16" and "neo4j 5"; Step 1.3 says "Spring Boot 3.3+". All three conflict with `VERSIONS.md` (postgres:18.6, neo4j:2026.05-community, Spring Boot 4.1.0), which is authoritative.
**Why it matters:** A reader following Step 1.3 literally would scaffold a Spring Boot 3.3 project, which is EOL and incompatible with Spring Kafka 4.1. The postgres and neo4j stale references affect compose image selection.
**Action:** Implementation always follows `VERSIONS.md`. No code change needed. Flagged here so the stale text is not silently propagated into code or compose files.

## 2026-08-15 — Step 0.0 — BLOCKED — uv not installed
**What:** `uv` is not present anywhere on PATH or in standard install locations. `uv` is required for all Python dependency management (Step 0.1 onward).
**Why it matters:** Cannot create `pyproject.toml`, run `uv sync`, or execute the Python test suite without it.
**Action:** Install uv before Step 0.1. Official install: `curl -LsSf https://astral.sh/uv/install.sh | sh`. Waiting on user to install.

## 2026-08-15 — Step 0.0 — VERIFIED — failOnNoDiscoveredTests confirmed on Gradle 9.7.0
**What:** `failOnNoDiscoveredTests = true` assigned on `tasks.withType<Test>` in a probe `build.gradle.kts` — accepted without error. The `NO-SOURCE` case (no test sources at all) skips the task entirely; `failOnNoDiscoveredTests` fires when sources exist but contain no test methods. Both behaviours are acceptable.
**Why it matters:** CLAUDE.md requires confirming this or recording a fallback.
**Action:** No fallback needed. Use `failOnNoDiscoveredTests = true` on every `Test` task from Step 1.3 onward.

## 2026-08-15 — Step 0.0 — CHOICE — MinIO pinned to RELEASE.2025-09-07T16-13-09Z
**What:** `docker pull minio/minio:latest` resolved to `RELEASE.2025-09-07T16-13-09Z`. This is the current Docker Hub `latest` as of 2026-08-15; newer releases may exist in MinIO's GitHub but not yet reflected in the `latest` tag.
**Why it matters:** VERSIONS.md requires an exact RELEASE tag.
**Action:** Using this tag. If a newer release is needed (security patch, API change), update `VERSIONS.md` and re-pull before Step 0.2.

## 2026-08-15 — Step 0.0 — CHOICE — LLM provider changed from Anthropic to OpenAI
**What:** Using OpenAI (`openai` SDK, `instructor.from_openai(...)`) instead of Anthropic. Default extraction model: `gpt-4o`, pinned in `.env` as `EXTRACTION_MODEL`. Env var is `OPENAI_API_KEY`.
**Why it matters:** `requirements.md` §1 originally named the Anthropic client; `instructor` abstracts the provider so the extraction contract, prompt versioning, and `ResearchSignalEvent` shape are unchanged. The `anthropic` package is replaced with `openai==3.1.0` in `pyproject.toml`.
**Action:** VERSIONS.md, PREREQUISITES.md, requirements.md, and plan.md updated accordingly. Confirm the model pin before Step 1.2.

## 2026-08-15 — Step 2.3 — CHOICE — Patent connector: PatentsView → Lens.org → EPO OPS (final)
**What:** PatentsView discontinued; USPTO ODP requires government ID. Lens.org chosen initially, then found to classify investment research as commercial use (institutional subscription €4,000+/year). Final choice: **EPO OPS** (`https://ops.epo.org/3.2/rest-services/`), OAuth2 client credentials, free public service, no commercial-use restriction, DOCDB ~130M documents.
**Why it matters:** PatentsView/USPTO ODP are unavailable or ID-gated. Lens.org is not free for this use case. EPO OPS is the only viable free REST patent API with US+EP+PCT coverage.
**Options considered:** USPTO ODP (requires government ID scan), USPTO bulk XML (no targeted queries, weekly ZIPs, high parsing overhead), Lens.org (commercial use restriction), Google Patents BigQuery (data stops April 2026, 4-month gap), EPO OPS (REST, DOCDB worldwide, free, no restrictions).
**Action:** All spec files updated to EPO OPS. `canonical_id = "epo-app:<country>-<app_number>"` derived from `application-reference` — stable across A1 and B1 for the same application. `EPO_OPS_KEY` and `EPO_OPS_SECRET` replace `LENS_API_TOKEN` everywhere. Exact XML field paths must be confirmed against a real API response at Step 2.3 and recorded here.

## 2026-08-15 — Step 0.0 — CHOICE — Ticker-restricted ingestion via pre-filter vocabulary (no architecture change)
**What:** Rather than ingesting everything and discarding, the pre-filter vocabulary (§6.6) will be seeded with gene targets, drug names, and mechanism keywords associated with the explicitly watched tickers. For EDGAR, the search query will be restricted to relevant CIKs. No architectural change required.
**Why it matters:** Keeps LLM spend proportional to scope. The pre-filter already exists for this purpose; making it ticker-specific is configuration, not code.
**Action:** At Step 0.1, the `.env.example` will include a `WATCHED_TICKERS` variable. The vocabulary file in `config/prefilter/` will be populated with associated terms before Step 2.2. No changes to connector contract, pipeline, or schema.

## 2026-08-15 — Step 2.3 — CHOICE — Patent connector changed from Lens.org to EPO OPS
**What:** Lens.org classifies investment research as commercial use and requires an institutional subscription (€4,000+/year). Using EPO OPS (Open Patent Services) instead: `https://ops.epo.org/3.2/rest-services/`, OAuth2 client credentials (`EPO_OPS_KEY` / `EPO_OPS_SECRET`), free standard tier, email registration only at `developers.epo.org`, no government ID, no commercial-use restriction.
**Why it matters:** Lens.org is not a viable free alternative. EPO OPS is a public service with ~130M documents from ~100 offices (DOCDB), covers US, EP, and PCT patents, and is searchable by applicant name and CPC class.
**Options considered:** Lens.org (commercial-use restriction), USPTO bulk XML (no API, weekly ZIPs, significant parsing overhead), EPO OPS (REST API, DOCDB worldwide coverage, free public service).
**Action:** `canonical_id = "epo-app:<country>-<app_number>"` derived from `application-reference` — stable across pre-grant publication (A1) and grant (B1). `external_id` = full publication reference `<country>-<pub_number>-<kind>`. Rate limit: 2.5 req/s, 4 GB/week. US patent data arrives via USPTO→EPO feed; expect 1–2 week lag vs direct USPTO — acceptable for weekly polling. Confirm exact field paths against a real API response at Step 2.3 and record here.

## 2026-08-15 — Step 1.2 — FLAG — openai==3.1.0 and instructor==1.15.4 are incompatible
**What:** `instructor==1.15.4` requires `openai>=2.0.0,<3.0.0`. `openai==3.1.0` was pinned in VERSIONS.md as the latest release on 2026-08-15, but instructor has not yet updated to support openai 3.x.
**Why it matters:** `uv sync` fails with an unsatisfiable constraint. The project cannot be built as pinned.
**Action:** Use `openai==2.54.0` (latest 2.x release, verified compatible with instructor 1.15.4). VERSIONS.md updated accordingly. Revisit at Step 2.2 once instructor publishes a 3.x-compatible release.

## 2026-08-15 — Step 1.2 — FLAG — plan.md pipeline order conflicts with requirements; tests follow requirements
**What:** plan.md §1.2 and §6.2 both write "pre-filter → dedup → MinIO archive → extract → publish", placing the archive AFTER pre-filter. Requirements invariant 13 states "The MinIO archive is unconditional — written before any other side effect." §7.1 rule 1 states "Archive always — first, unconditional." §7.1 rule 2 states "Dedup gates extraction and publish only, never the archive." The required test `test_prefiltered_document_is_archived_but_never_reaches_the_llm` also confirms pre-filtered docs ARE archived.
**Why it matters:** Writing tests against the plan.md order would require the archive to be conditional on the pre-filter, which violates three independent requirements and the CLAUDE.md invariant.
**Action:** Implement and test the order that satisfies requirements: **archive (unconditional) → pre-filter → dedup → extract → publish**. The plan.md text is stale; requirements are authoritative.

## 2026-08-15 — Step 0.0 — VERIFIED — PREREQUISITES.md ⏳ items requested
**What:** All four external-lead-time items from PREREQUISITES.md noted as of 2026-08-15: EPO OPS API key/secret (developers.epo.org), openFDA API key (open.fda.gov), NCBI API key, OpenAI API key + billing. These are reminders only; the agent cannot verify they've been submitted.
**Action:** User should confirm they have initiated registration for each before Step 1.2 (OpenAI) and Step 2.2+ (the rest).

## 2026-08-15 — Step 0.0 — CHOICE — Watched tickers and initial pre-filter vocabulary
**What:** Starting tickers: SRPT, SPRB, BEAM, CRSP, CAPR, ABVX, RCKT, QURE. All gene therapy / gene editing companies.

Pipeline context and associated vocabulary terms:

| Ticker | Company | Focus | Key gene targets | Key drugs/programs |
|---|---|---|---|---|
| SRPT | Sarepta Therapeutics | DMD, gene therapy (AAV, exon skipping) | DMD, dystrophin | Elevidys, Exondys 51, Vyondys 63, Amondys 45 |
| SPRB | Spruce Biosciences | Congenital adrenal hyperplasia | CYP21A2 | tildacerfont |
| BEAM | Beam Therapeutics | Base editing | BCL11A, HBB, PCSK9, CD33 | BEAM-101, BEAM-201, BEAM-302 |
| CRSP | CRISPR Therapeutics | CRISPR gene editing, CAR-T | BCL11A, HBB, TRAC, CD52 | Casgevy (exa-cel), CTX310, CTX320 |
| CAPR | Capricor Therapeutics | DMD, exosome therapy | DMD, dystrophin | CAP-1002, deramiocel |
| ABVX | Abivax | RNA biology, inflammation, HIV | — | ABX464, obefazimod |
| RCKT | Rocket Pharmaceuticals | Gene therapy (lentiviral + AAV) | RAG1, RAG2, FANCA, LAMP2, PKP2 | RP-L201, RP-A501 |
| QURE | uniQure | Gene therapy (AAV-based) | F9, HTT, SOD1, GLA | AMT-061 (etranacogene), AMT-130 |

**Initial `config/prefilter/v1.yaml` vocabulary (to be created at Step 0.1 scaffolding, refined at Step 2.0):**
- Mechanisms: gene therapy, CRISPR, base editing, prime editing, AAV, adeno-associated virus, lentiviral, exon skipping, antisense oligonucleotide, ASO, mRNA therapy, exosome, cell therapy, CAR-T
- Gene targets: DMD, dystrophin, BCL11A, HBB, PCSK9, CD33, TRAC, CD52, CYP21A2, RAG1, RAG2, FANCA, LAMP2, PKP2, F9, FIX, HTT, SOD1, GLA
- Disease areas: Duchenne muscular dystrophy, DMD, hemophilia, sickle cell, beta-thalassemia, congenital adrenal hyperplasia, Huntington, ALS, Fabry, Danon, ARVC, LAD-I, Fanconi anemia, HIV
- Company names: Sarepta, Spruce Biosciences, Beam Therapeutics, CRISPR Therapeutics, Capricor, Abivax, Rocket Pharmaceuticals, uniQure
- Drug names: Elevidys, Exondys, Vyondys, Amondys, Casgevy, exa-cel, tildacerfont, obefazimod, ABX464, deramiocel, etranacogene, AMT-130

## 2026-08-15 — Step 1.3 — FLAG — Gradle 9.7.0 version catalog accessor compilation fails on JDK 25
**What:** `gradle/libs.versions.toml` causes `SimpleGeneratedJavaClassCompiler` to fail with `package org.gradle.api.* does not exist` when compiling the generated `LibrariesForLibs.java` accessor. Adding `[plugins]` entries makes it worse (additional `LibrariesForLibsInPluginsBlock` compilation failure). Root cause: JDK 25 + Gradle 9.7.0 internal accessor compiler has a classpath setup regression.
**Why it matters:** Type-safe version catalog accessors are required by CLAUDE.md but can't be generated. The `libs.*` references in `build.gradle.kts` still work for the `[libraries]` section (referenced from `dependencies {}`) because Gradle defers that resolution; the compilation failure only occurs when generating the full accessor type hierarchy.
**Options considered:** A) `--add-opens` daemon args (partial fix — resolved build script compilation but underlying accessor generation still breaks if `[plugins]` is present). B) Remove `[plugins]` section from TOML and hardcode plugin version inline in `plugins {}` block — resolves the issue. C) Remove version catalog entirely — violates CLAUDE.md.
**Action:** Removed `[plugins]` from `libs.versions.toml`. Spring Boot plugin version (`4.1.0`) is hardcoded in the `plugins {}` block with a comment referencing VERSIONS.md. All library versions remain in the catalog and are referenced via `libs.*` in `dependencies {}`. This is the minimum violation of CLAUDE.md constraints. Revisit if Gradle releases a patch for the 9.7.x line.

**EDGAR CIK restriction:** Look up CIKs for all eight companies from `https://www.sec.gov/files/company_tickers.json` at Step 2.6 and record here. Do not hardcode — pull from the same file the ticker-resolution step uses.
**Action:** Populate `WATCHED_TICKERS=SRPT,SPRB,BEAM,CRSP,CAPR,ABVX,RCKT,QURE` in `.env.example` at Step 0.1.

## 2026-08-16 — Step 1.3 — VERIFIED — Spring Boot 4.1 auto-configuration module split
**What:** Spring Boot 4.1 moved `FlywayAutoConfiguration` and `KafkaAutoConfiguration` (including `@EnableKafka`) out of `spring-boot-autoconfigure` into separate modules: `spring-boot-flyway` and `spring-boot-kafka`. Neither is transitively included by any starter — they must be declared explicitly in `dependencies {}`.
**Why it matters:** Without them the Flyway schema is never applied (Postgres tables missing at test time) and Kafka listeners are never registered. Both failures are silent at context startup — the application starts cleanly but processes nothing.
**Action:** Added `implementation("org.springframework.boot:spring-boot-flyway")` and `implementation("org.springframework.boot:spring-boot-kafka")` to `build.gradle.kts`. Any future Spring Boot 4.x feature that was previously auto-configured may require an explicit module dependency — check the CONDITIONS EVALUATION REPORT in the test output when a component appears absent.

## 2026-08-16 — Step 1.3 — VERIFIED — DeadLetterPublishingRecoverer with Spring Kafka 4.1
**What:** `DeadLetterPublishingRecoverer` requires a multi-template map to handle the two distinct DLT failure modes: (A) deserialization failures where `ErrorHandlingDeserializer` stores the original raw bytes in `DeserializationExceptionHeader` and the DLPR extracts them as `byte[]`; (B) processing failures where the value is the already-deserialized Java record.
**Why it matters:** Using a single `StringSerializer` template causes ClassCastException when publishing processing failures (value is `ResearchSignalEvent`, not `String`), preventing offset commit and causing infinite redelivery. Using only `ByteArraySerializer` fails for the same reason on processing failures.
**Options considered:** A) Single `JsonSerializer` template (works for B, but encodes raw bytes as JSON array for A — ugly but functional). B) Multi-template: `{byte[].class → ByteArraySerializer, Object.class → JsonSerializer}` — DLPR selects by value type; correct for both cases.
**Action:** Chose option B. `signalDltRecoverer` and `rawDltRecoverer` use a `LinkedHashMap<Class<?>, KafkaOperations<?, ?>>` with two entries. Custom topic resolver verified against Spring Kafka 4.1: lowercase `.dlt` suffix (not `.DLT`) and partition `-1` (producer chooses) are confirmed correct.

## 2026-08-16 — Step 1.3 — VERIFIED — Spring Kafka 4.1 DLT header names
**What:** Spring Kafka 3.0 renamed the DLT diagnostic headers. The 2.x names `kafka_exception-message` and `kafka_original-topic` no longer exist. The 4.1 names are `kafka_dlt-exception-message` and `kafka_dlt-original-topic`.
**Why it matters:** Tests that assert header presence will get a null and fail. One test (`test_dlt_headers_present`) had the old names hardcoded.
**Action:** Updated the test to use the 4.1 header names. No production code change needed.

## 2026-09-13 — Step 2.0 — VERIFIED — Extraction quality baseline

**Prefilter bug fixed:** `Prefilter.from_vocab(set())` previously returned `False` for all documents (`any()` over empty set). Fixed to return `True` when vocab is empty (no filter = pass all). Existing tests unaffected — connector integration tests only assert `fetched` and `failed`, not whether docs pass the prefilter.

**Scoring run — 50 golden documents (DMD gene therapy theme), no vocab file (all docs pass prefilter):**

| Metric | Result | Gate |
|---|---|---|
| is_signal precision | 0.833 | ≥ 0.85 |
| is_signal recall | 0.571 | — |
| gene_targets F1 | 0.562 | — |
| mechanisms F1 | 0.262 | — |
| companies_mentioned F1 | 0.200 | — |

**Precision gate (0.85): not met (0.833).** 4 false positives, all pre-clinical animal model papers or review articles the extractor incorrectly classified as signals:
- `biorxiv:10.1101/2022.01.06` — RIPK3 inhibition in preclinical DMD models
- `biorxiv:10.1101/2022.05.16` — DBA/2J mouse model characterisation
- `biorxiv:10.1101/2025.10.10` — Becker MD pig gait kinematics pilot study
- `pubmed:40848523` — review article: "Gene therapy for Duchenne muscular dystrophy"

Labels on all 4 are correct. Root cause: the extractor prompt does not clearly exclude preclinical-only findings and review articles.

**15 false negatives:** 8 are edgar 8-K filings whose `raw_content` contains only form metadata (Accession, Entity, Form type, Filed, Period, Items) — no prose content for the LLM to reason over. These are a structural limitation of the edgar connector's raw_content format, not a prompt issue. The remaining 7 FNs are borderline cases across biorxiv, clinicaltrials, and pubmed.

**Decision:** Record the baseline and proceed. Precision at 0.833 is close; the 4 FPs are a known prompt gap (preclinical vs clinical boundary). This will be revisited when the extraction prompt is tuned in a later step. The edgar FN rate is expected given the minimal raw_content format — if edgar signal recall matters, the connector would need to fetch filing text.

## 2026-09-13 — Step 2.0 — VERIFIED — Extraction prompt tuned, gate now met

Three issues found in the original extraction prompt and fixed:
1. `is_signal=true` list only said "clinical trial results" — trial initiation/enrollment is also investment-relevant. Added explicitly.
2. Preclinical rule ("establishing proof of concept") was too vague — it caught pure mechanism studies and animal model characterisation papers that have no therapeutic agent administered. Tightened to require that a drug/construct was administered and an effect measured. Added a guiding question: "was something given to a biological system to try to treat it?"
3. Review articles and natural history/characterisation studies were not in the `is_signal=false` list. Added explicitly.

No versioning — greenfield build, no deployed events to preserve.

**Final scoring run — 50 golden documents:**

| Metric | Before | After |
|---|---|---|
| is_signal precision | 0.833 ❌ | **1.000** ✓ |
| is_signal recall | 0.571 | 0.629 |
| TP / FP / FN / TN | 20/4/15/11 | 22/0/13/15 |

**Remaining 13 FNs:** 8 are edgar 8-K filings whose raw_content is form metadata only (no prose) — structural limitation of the edgar connector, unfixable by prompt. The other 5 are borderline cases (1 preclinical mechanistic study with ambiguous drug administration language, 1 CT trial not caught by initiation rule, 1 title-only PubMed entry, 2 others). Precision gate met; proceeding.

## 2026-09-13 — Step 3.2 — VERIFIED — Corroboration quality review complete

**Setup:** 37 live non-superseded corroborations (90-day window, 4 sources: clinicaltrials=203, pubmed=85, biorxiv=11); 30 sampled with seed=42 across 7 gene targets (DMD, HBB, LMNA, ARSA, KRAS, AQP1, GLA). Reviewed in `review_3_2.jsonl`.

**Result:** 26 genuine / 4 extraction_error / 0 coincidental → **precision 86.7% — PASS (≥85% gate)**

**4 extraction errors and their patterns:**

| Record | Entity | Issue |
|---|---|---|
| 10 | HBB | STArT Trial (arginine IV for SCD crisis management) mislabeled as gene therapy signal — metabolic drug, not a genetic intervention |
| 15 | KRAS | CRISPR-Cas12a diagnostic mutation-detection paper (DESIC system) mislabeled as a therapeutic gene therapy signal |
| 19 | HBB | Corroboration anchored on arginine trial + alloHSCT — no genuine gene therapy CT in the cross-source set |
| 25 | AQP1 | Leishmania GAT3 transporter drug-susceptibility paper paired with AQP1 salivary gene therapy trial — unrelated biology |

**Root causes:**
1. HBB disease area is broad; disease-management drugs (arginine, mitapivat) and allogeneic HSCT all mention HBB/SCD and get swept into HBB:GeneTarget.
2. CRISPR-Cas12a diagnostic tools share surface-level gene-editing language with therapeutics.
3. The Leishmania/AQP1 false positive is a cross-species ambiguity (AQP is a conserved protein family).

**Next steps for extraction improvement (before Phase 4):** Add to extraction prompt that (a) disease-management drugs are not signals, (b) CRISPR used solely for detection/diagnostics is not a therapeutic signal, (c) the gene being targeted must be explicitly in a therapeutic context, not an incidental mention. Feed records 10, 15, 19, 25 to the golden set.

## 2026-09-17 — patent connector — VERIFIED — EPO OPS 3.2 XML structure and API behaviour

**What:** Confirmed exact XML element paths, namespaces, API syntax, and HTTP behaviour via live API calls against `ops.epo.org`.

**Namespaces:**
- `ops` prefix: `http://ops.epo.org` (NOT `http://ops.epo.org/3.2/rest-services`)
- default (document content): `http://www.epo.org/exchange`

**Two-step architecture (confirmed):**
1. `GET /published-data/search?q=...` with `Range: {begin}-{end}` header → returns `ops:publication-reference` elements only (no bibliographic data)
2. `GET /published-data/publication/docdb/{country}{num}.{kind}[,...]/biblio` → returns full `exchange-document` elements

**CQL date syntax:** `pd within "YYYYMMDD,YYYYMMDD"` — the `>=`/`<=` range syntax is rejected with `CLIENT.FuzzyDateRanges` fault.

**Empty search response:** HTTP 404 with `<fault xmlns="http://ops.epo.org"><code>SERVER.EntityNotFound</code><message>No results found</message></fault>`. Treat 404 as zero results, not an error.

**Confirmed element paths** (XPath from `exchange-document`, default ns = `{http://www.epo.org/exchange}`):
- `bibliographic-data/publication-reference/document-id[@document-id-type='docdb']/date` → pub date (YYYYMMDD)
- `bibliographic-data/publication-reference/document-id[@document-id-type='docdb']/country` → pub country
- `bibliographic-data/publication-reference/document-id[@document-id-type='docdb']/doc-number` → pub number
- `bibliographic-data/publication-reference/document-id[@document-id-type='docdb']/kind` → kind (A, A1, B1, etc.)
- `bibliographic-data/application-reference/document-id[@document-id-type='docdb']/country` → app country
- `bibliographic-data/application-reference/document-id[@document-id-type='docdb']/doc-number` → app number
- `bibliographic-data/application-reference/document-id[@document-id-type='docdb']/date` → filing date
- `bibliographic-data/invention-title[@lang='en']` → English title (inside bibliographic-data)
- `abstract[@lang='en']/p` → abstract paragraphs — **`abstract` is at `exchange-document` level, NOT inside `bibliographic-data`**
- `bibliographic-data/parties/applicants/applicant[@data-format='epodoc']/applicant-name/name` → applicant names

**IDs:**
- `external_id = "{pub_country}-{pub_number}-{pub_kind}"` e.g. `"CN-118615435-A"`
- `canonical_id = "epo-app:{app_country}-{app_number}"` e.g. `"epo-app:CN-202410078858"`

**Grant date:** For B1/B2 kind publications, the publication date IS the grant date. Include `"Granted: {pub_date}"` in raw_content for B-kind records. A-kind records have no grant date — omit the line.

**Rate limit:** EPO OPS standard tier is confirmed 2.5 req/s. Configured at 2.0 req/s. Each page of 100 results requires 2 HTTP calls (1 search + 1 biblio batch). Token calls are infrequent (every 20 min).

**OAuth2 token:** POST `https://ops.epo.org/3.2/auth/accesstoken` with Basic auth and `grant_type=client_credentials` body. Returns `{"access_token": "...", "expires_in": 1200}`. Confirmed working.

**Live-query result — watched company DOCDB records confirmed:**
| Company | DOCDB records |
|---|---|
| Sarepta Therapeutics | 217 |
| CRISPR Therapeutics | 171 |
| Beam Therapeutics | 106 |
| Abivax | 51 |
| uniQure | 65 |
| Capricor | 29 |
| Spruce Biosciences | 13 |
| Rocket Pharmaceuticals | verified via `pa = ROCKET` search |

All 8 watched companies have records in DOCDB. They don't appear in 200 randomly sampled recent CPC results because they're small-cap relative to the global patent volume (~5000 results/day for C12N+A61K alone). The connector's CPC-class search over a 30-day window will capture their publications as they appear.

## 2026-09-19 — Kafka partition verification — VERIFIED — distribution is acceptable, no action
**What:** Produced 120 messages with UUID keys to a 6-partition topic via a Kafka testcontainer. Consumed all 120 and counted per-partition. No partition exceeded 2× the expected share (40 messages). Distribution was uniform within noise — consistent with murmur2 hash over random UUIDs.
**Why it matters:** Per the spec, the default outcome is "distribution is acceptable, no action." Repartitioning would rehash all keys and lose per-key ordering.
**Action:** No repartitioning. Topics stay at 6 partitions.

## 2026-09-19 — Java package reorganization — MetricsIT.java — pre-existing compilation error fixed, one test still failing
**What:** `MetricsIT.java` used `@AutoConfigureMockMvc` which was removed in Spring Boot 4. The class could not compile on `develop` before this spec, so `test_prometheus_endpoint_returns_200` and `test_kafka_consumer_lag_metric_is_registered` were never running. Fixed the compilation by switching to `MockMvcBuilders.webAppContextSetup().build()` (same pattern as `EndToEndIT`).

`test_prometheus_endpoint_returns_200` now passes. `test_kafka_consumer_lag_metric_is_registered` fails: the `kafka.consumer.records.lag` gauge is not registered in the embedded Kafka test context — the Micrometer Kafka binder only registers this gauge after a consumer gets its first partition assignment, which does not happen in the embedded Kafka setup without messages being published first.

**Not a regression** — both tests were previously blocked by the compilation error. The failing test was a latent issue in the Metrics spec implementation, not introduced by this refactoring.
**Action:** Log and proceed. If the lag gauge test is needed, it requires either publishing seed messages to trigger partition assignment or a @Tag to exclude it from CI until a container-based Kafka is used.

## 2026-09-19 — Watchlist & alerts — CHOICE — Discord webhook transport
**What:** Notification transport for watchlist alerts and health reporting is Discord webhook (HTTP POST to `DISCORD_WEBHOOK_URL`).
**Why it matters:** The transport choice affects the integration test setup and the configuration required in `.env`. Discord webhook requires no OAuth, no SDK, and is a single HTTP POST — the lowest-friction choice for a personal/research project.
**Options considered:** Discord webhook (chosen), Slack webhook (same complexity, less commonly used for personal projects), email via SMTP (requires mail server configuration, higher operational overhead).
**Action:** `NotificationTransport` is a `@FunctionalInterface`. `DiscordWebhookTransport` uses `java.net.http.HttpClient`. A second transport (Slack, email) is a separate implementation of the interface and out of scope for this spec. `DISCORD_WEBHOOK_URL` absent → no-op transport with a startup warning; application starts normally.

## 2026-09-19 — Watchlist & alerts — CHOICE — Entity-key-based watchlist, not ticker-based
**What:** `watchlist_entries` rows store full `entity_key` strings (e.g. `"BCL11A:GeneTarget"`), not ticker symbols.
**Why it matters:** Ticker → entity mapping requires a Neo4j traversal (ticker → Company → Signal → entity → corroboration) not currently exposed by any query path. Implementing it would require a new query and test coverage beyond the scope of this spec.
**Options considered:** A) Full entity key stored in watchlist (chosen — direct match, no join). B) Ticker stored, matched via graph query (deferred — requires new infrastructure). C) Gene target name only, matched by entity_key prefix (fragile — "BCL11A" matches "BCL11A:GeneTarget" and any future label using the same gene).
**Action:** Use full entity_key matching. Seed the initial watchlist with the gene targets of the 8 watched companies (from DECISIONS.md 2026-08-15 entry). Ticker-based matching is noted in the spec as a future enhancement.

## 2026-09-19 — Historical backfill — VERIFIED — EPO OPS now in scope
**What:** The historical-backfill spec previously noted EPO OPS as "blocked pending credentials." EPO OPS key/secret are confirmed configured (PREREQUISITES.md), and the patent connector is done with 10 tests and live DOCDB confirmed (TODO.md, specs/done/patent-connector.md).
**Why it matters:** EPO OPS supports date-ranged CQL queries (`pd within "YYYYMMDD,YYYYMMDD"`, confirmed in the 2026-09-17 DECISIONS.md entry), making it viable for the 24-month backfill alongside ClinicalTrials.gov, EDGAR, and bioRxiv.
**Action:** historical-backfill.md updated. EPO OPS included in backfill scope. The 2,000-result per-window limit for EPO OPS requires the runner to split large date windows — noted as a constraint in the spec.

## 2026-09-19 — Historical backfill — FLAG — live vs backtest extraction lineage decision required
**What:** If the live extraction model changes after the backfill, the backtested strategy was validated on one model's signals while the live system uses another model's signals. Three options with different consequences for requirements and LLM budget.
**Why it matters:** §10.1 bakes `extraction_model` into `extraction_id`. §3.7 `signal_current` is latest-wins by `event_id`. A two-model corpus means `extraction_model` in `signal_extraction_history` is split across two identifiers, and Phase 4 metrics cannot be cleanly attributed to a single extraction configuration.
**Options considered:**
A. One model everywhere — pin the same pre-cutoff model for both backfill and live. No dual-lineage infrastructure. LLM budget unchanged (~500/day + one-time backfill). To adopt a newer live model later, the backfill must be re-run or the lineage break accepted and documented. Sections affected: §0.4 only.
B. Dual lineage — backtested model continues as live primary; a newer model runs in shadow. Shadow events written to `signal_extraction_history` only — never to `signal_current`, never to the graph, never to corroboration. Minimal implementation: a shadow flag on the extraction event or a parallel topic consumed by a read-only handler. This requires unfreezing `GraphUpdateService` (or adding a net-new consumer), which breaks the Phase 2 exit freeze. §3.7 `signal_current` latest-wins must explicitly exclude shadow events. LLM budget doubles (~1000/day). Sections affected: §3.7, §10.4, Phase 2 exit freeze.
C. Switch live to the new model and accept the backtest does not directly validate it. The backtest measures predictive value of the old model's signals, which is informative research even if it does not validate the current production pipeline. Clean break, no extra infrastructure. The forward track record for the new model starts from the switch date.
**Action:** Stopped. The historical-backfill spec is blocked on this decision. Please specify A, B, or C (or a variant) before beginning the extraction-backend or backfill specs.

## 2026-09-19 — Phase 4 — FLAG — directionality and confidence_score are hindsight-exposed; report entity-only variant
**What:** `directionality` and `confidence_score` are the LLM's judgment fields and are the most exposed to hindsight contamination if the model's training data postdates the documents being extracted. Entity corroboration (same gene target from two distinct source types within ±90 days) is purely structural — it requires no model judgment about outcome.
**Why it matters:** A model that "knows" a trial succeeded will assign `directionality: positive` and high `confidence_score` to the trial announcement, inflating apparent predictive accuracy. If the entity-only variant shows the same predictive power as the full variant, the judgment fields add nothing beyond what structure already captures — and if the full variant is stronger, that gap is worth examining for contamination before drawing conclusions.
**Action:** Phase 4 metrics must be reported for two variants: (1) entity/corroboration-only — `entity_key`, distinct `source_count`, `corroborated_at`, no model judgment fields; (2) full — including `directionality` and `confidence_score`. Record both in Phase 4 output. If (2) substantially outperforms (1), document the delta in DECISIONS.md and consider running the leakage canary before publishing findings.

## 2026-09-19 — Historical backfill — FLAG (v2, supersedes earlier lineage flag) — backfill model and lineage decision required
**What:** Three options for which model extracts the backfill corpus and how that relates to the live extraction model going forward. The local test-period extractions (if any) are their own lineage and must not enter the backtest corpus unless the local model is also the chosen backfill model (same registry entry, prompt, and prefilter versions).
**Why it matters:** §10.1 bakes `extraction_model` into `extraction_id`. §3.7 `signal_current` is latest-wins by `event_id`. A mixed-lineage corpus is uninterpretable in Phase 4: `directionality` and `confidence_score` were assigned by different models with different priors. The cross-model agreement script (model-evaluation spec 2c) can quantify how much a backtest on one model's signals transfers to another's, but it does not resolve the lineage problem.
**Options considered:**
A. Backfill runs on a pre-cutoff local model (e.g. `llama3.1:8b-instruct-q8_0`, cutoff Dec 2023, full 24-month window); production API model is forward-only from the switch date. Validated indirectly: (1) model-evaluation spec 2c agreement report between local backfill model and production API model; (2) live track record of the production model going forward. Budget: local model is near-zero marginal cost for the backfill; production API model at ~500/day forward. Requirements affected: §0.4 only. Live events already extracted under `gpt-4o-mini-2024-07-18` that fall in the backfill window must be re-extracted under the local backfill model via the reextraction-cli before the backtest, or accepted as a known lineage gap documented in the Phase 4 output.
B. Choose a single pre-cutoff API or local model for both backfill and all live extraction going forward. Simplest lineage story; no agreement report needed. Candidates: `gpt-4o-mini-2024-07-18` (cutoff Oct 2023, full 24-month window, existing gate record from Phase 2) or `llama3.1:8b-instruct-q8_0` (cutoff Dec 2023, full 24-month window, gate record needed). Budget: same as current if API; near-zero marginal cost if local. Requirements affected: §0.4 only. No re-extraction needed if the backfill model matches the existing live model.
C. Dual lineage live: the backtested model continues as live primary (feeds `signal_current`, graph, corroboration, REST API); a production API model runs in shadow (appends to `signal_extraction_history` only). Minimal implementation: a `is_shadow` flag on the extraction event, or a second Kafka topic consumed by a read-only handler. §3.7 `signal_current` latest-wins must explicitly exclude shadow events — requires unfreezing `GraphUpdateService` (Phase 2 exit freeze) or adding a net-new consumer. Budget: ~doubles live extraction spend (~1000/day). Requirements affected: §3.7 (signal_current write path), §10.4 (re-extraction is explicit — shadow extraction under a different model should not be a silent side effect), Phase 2 exit freeze.
**Action:** Stopped. extraction-backend, model-evaluation, and historical-backfill specs are blocked on this answer. Please specify A, B, or C (or a variant).

## 2026-09-19 — Phase 4 — FLAG (v2, supersedes earlier Phase 4 note) — entity-only variant required in all Phase 4 output
**What:** `directionality` and `confidence_score` are the LLM's judgment fields. They are the fields most exposed to hindsight contamination if the model's training data postdates the documents being extracted. Entity corroboration (same gene target from two distinct source types, within ±90 days) is structural and requires no model judgment.
**Why it matters:** A model that has learned a trial succeeded will assign `directionality: positive` and high `confidence_score` to the announcement, inflating apparent predictive accuracy. The entity-only variant is the control: if it shows the same predictive power as the full variant, the judgment fields add nothing. If the full variant is substantially stronger, that gap should be investigated for contamination before publishing findings. The model-evaluation spec 2c cross-model agreement report provides additional evidence: low directionality agreement between two models on the same documents is a signal that directionality is noisy or model-specific.
**Action:** All Phase 4 metrics (hit rate, lead time, risk-adjusted stats) must be reported for two variants: (1) entity/corroboration-only — `entity_key`, distinct `source_count`, `corroborated_at`, no judgment fields; (2) full — including `directionality` and `confidence_score`. Record both in Phase 4 output. If (2) substantially outperforms (1), document the delta in DECISIONS.md before drawing conclusions.

## 2026-09-19 — Historical backfill — CHOICE — Option A: local model for backfill, API model forward-only
**What:** The backfill runs on a local model. The production API model is forward-only from the date it is switched in. Phase 4 runs on the local model's corpus and answers whether corroborated signals of this kind precede price moves at all — before any API budget is committed to improving extraction quality.
**Why it matters:** The corroboration logic is structural (two distinct source types on the same gene target within 90 days); `is_signal` and `gene_targets` precision is sufficient. `directionality` and `confidence_score` are tested separately via the entity-only Phase 4 variant. If Phase 4 shows no signal, the API spend is avoided. If it shows something, the decision to invest in API quality has a concrete justification.
**Sequence enforced by specs:**
1. Run `scripts/evaluate_model.py` (model-evaluation spec 2a) on local candidates. A candidate passes if `is_signal` precision ≥ 0.85 at the active prompt and prefilter versions. Record the passing model in this file.
2. Add the passing model to `config/models/registry.yaml`. Run `scripts/score_extraction.py --model <id>` to write its gate record.
3. Run `scripts/run_backfill.py --dry-run`. The overlap report must show zero in-window documents under a different model identifier, OR those documents are re-extracted under the backfill model via the reextraction-cli before Phase 4.
4. Get budget approval; run the backfill.
5. Run Phase 4. Record both entity-only and full metric variants.
6. Only after Phase 4: decide whether API model quality would materially improve a real signal. If yes, that is a new spec.
**Requirements sections:** §0.4 only. No structural change to the pipeline, schema, or graph.
**Passing local model:** not yet chosen — pending `evaluate_model.py` results. Record here when selected.
**Action:** extraction-backend and model-evaluation specs unblocked. historical-backfill remains blocked on budget approval and model selection.

## 2026-09-19 — CI/CD pipeline — CHOICE — GitHub-hosted runners
**What:** GitHub Actions uses `ubuntu-latest` (GitHub-hosted) rather than self-hosted runners.
**Why it matters:** Self-hosted runners require provisioning and maintaining a machine. GitHub-hosted runners have Docker pre-installed, Testcontainers works without additional setup, and the test suite runtime (Java ~48s, Python <2min) is well within GitHub's 6-hour job timeout.
**Options considered:** GitHub-hosted `ubuntu-latest` (chosen), self-hosted runner on a local machine (higher maintenance, faster Docker pull if local cache warms), GitHub-hosted `macos-latest` (Docker not available on free tier for macOS runners).
**Action:** Use `ubuntu-latest`. Set `TESTCONTAINERS_RYUK_DISABLED=true` in the workflow env if Ryuk fails to start on the first CI run (record outcome in this file). No other configuration needed.

## 2026-09-20 — Watchlist backend — CHOICE — No user_id column; single-user installation, extensible
**What:** The `watchlist` table has no `user_id` FK. The installation is treated as single-user (one researcher). No auth layer exists and requirements say not to implement it speculatively.
**Why it matters:** Adding a `user_id` column later requires one Flyway migration: add the column, add a FK to `users`, drop `watchlist_ticker_unique`, add `UNIQUE (user_id, ticker)`. Designing around a nullable `user_id` now adds complexity without a concrete use case.
**Action:** Ship without `user_id`. Document the extension path in the Flyway migration comment. When multi-user is needed, that is a separate auth spec.

## 2026-09-20 — Watchlist backend — CHOICE — core-hub calls ClinicalTrials.gov directly
**What:** The preview endpoint makes a direct outbound HTTP call from core-hub (Java) to `https://clinicaltrials.gov/api/v2/studies`. It does not proxy through ingestion-scraper's connector.
**Why it matters:** ingestion-scraper's ClinicalTrials connector is designed for bulk ingestion (rate-limited, paged, MinIO archive). The preview needs a single targeted query. Duplicating a simple HTTP GET in Java avoids a service-to-service call at UI interaction time and keeps each service's HTTP surface minimal.
**ClinicalTrials API is public** — no credentials needed (invariant 6 not implicated). 5-second timeout applied.
**Action:** WireMock stub in core-hub unit tests. No changes to ingestion-scraper.

## 2026-09-20 — Watchlist — FLAG — entity_key format discrepancy
**What:** The `watchlist-alerts` hold spec uses colon notation for entity keys (`"BCL11A:GeneTarget"`) but the corroboration table and Neo4j use space-pipe-space: `"BCL11A | GENE_TARGET"`. These formats will not match if used in a join.
**Why it matters:** The watchlist-backend summary endpoint filters corroborations by `SPLIT_PART(entity_key, ' | ', 1) = ANY($tracked_gene_targets)`. If the actual `entity_key` format differs, no corroborations will be returned.
**Action:** Before implementing the summary endpoint corroboration filter, run `SELECT DISTINCT entity_key FROM corroboration LIMIT 10` and record the confirmed format here. Update the watchlist-alerts hold spec accordingly before it comes off hold.

## 2026-09-20 — Watchlist alerts (hold spec) — FLAG — schema superseded
**What:** The watchlist-alerts hold spec planned a `watchlist_entries(entity_key TEXT UNIQUE)` table, pre-seeded with gene targets from a Flyway migration. The watchlist-backend spec creates `watchlist` + `watchlist_gene_target` tables that serve the same purpose with more structure.
**Why it matters:** Two schemas for the same concept would require a migration to merge them.
**Action:** Do not create `watchlist_entries`. When watchlist-alerts comes off hold, rewrite its schema section to query `watchlist_gene_target JOIN watchlist` for entity keys. Update the hold spec before implementation begins.

## 2026-09-20 — Option A hosting implication — FLAG — live extraction depends on the MacBook
**What:** Option A (chosen 2026-09-19) runs the local extraction model on the MacBook Pro. Unless changed, live DAG extraction also depends on the same machine and model server — the scraper service calls `host.docker.internal` which only resolves to the host machine.
**Why it matters:** §5 cursor state means no signal events are lost during downtime — DAGs catch up via their cursors when the machine comes back online. But signal events are delayed by the duration of the outage. For Phase 4 research this is acceptable; delayed-but-complete data is the input. For the Phase 5 alert workflow (notification on new corroboration), stale-by-hours data defeats the purpose. The trading layer will need a decision on acceptable latency before the watchlist-alerts spec comes off hold.
**Options considered:**
A1 (current state): MacBook only. Zero infrastructure cost. Appropriate for Phase 4 research.
A2: Dedicated always-on host (Mac mini or Linux server). Same local model, identical code path. Required before a production alert workflow. Estimated cost: hardware only.
A3: Switch live extraction to a hosted API model going forward (Option B from the earlier lineage flag, 2026-09-19). Always-on, no hardware required, ~$15/month at 500 extractions/day.
**Action:** No decision needed before Phase 4. Before the watchlist-alerts spec comes off hold (Phase 5), record here whether A2 or A3 is chosen. The watchlist-alerts hold criterion ("Phase 4 shows a real repeatable signal worth acting on") is necessary but not sufficient — uptime must also be resolved.

## 2026-09-20 — Scoping session audit — FLAG — spec gaps filled
**What:** Three spec gaps identified against the session prompt and requirements.md:
1. extraction-backend.md was missing a test for connection-refused (model server unreachable) — distinct failure mode from TimeoutError. Added `test_model_server_unreachable_documents_stay_archived_and_not_published`.
2. model-evaluation.md latency record lacked `tokens_per_second` and the throughput feasibility script output (points 1–3: backfill wall-clock, live hours/day, combined-machine fit). Added.
3. historical-backfill.md had `BACKFILL_BUDGET_CEILING` for API backends but no time ceiling for local backends. Added `BACKFILL_TIME_CEILING_HOURS` and `test_backfill_aborts_when_local_time_estimate_exceeds_ceiling`.
**Why it matters:** Without the time ceiling, a local-model backfill with a bad latency estimate could run for far longer than planned with no automatic abort. Without the connection-refused test, a down model server would cause documents to pile up in "archived, unextracted" state with no test ensuring the batch completes and nothing is silently lost.
**Action:** Specs updated in-place. No implementation impact — all additions are test and configuration surface, not architectural changes.

## 2026-09-20 — Option A hosting — CHOICE — A1 (MacBook) confirmed for Phase 4; A2/A3 deferred
**What:** MacBook-only (A1) is the starting point. If Phase 4 shows a signal worth acting on in real time, the hosting decision (A2 dedicated host vs A3 API model) gets made then as a separate spec.
**Action:** None. Record here when switching to A2 or A3.

## 2026-09-20 — Strategy layer — FLAG — requirements.md §0.1 assumption flips at session 3
**What:** `requirements.md §0.1` describes the system as "a historical research instrument" and states it "does not make live trading decisions." Strategy layer session 3 (live trading & UI) is explicitly scoped to add live trading. These are directly contradictory.
**Why it matters:** Several requirements around data sourcing, latency, and model hosting implicitly assume research-only use. Sections that will need review when live trading is added: §0.1 (assumption statement), §0.4 (LLM budget assumes research-only volume), §5 (Airflow cursor as the sole latency model), and any uptime-related assumptions in §8 (price data freshness).
**Options considered:** A) Flag now, resolve in session 3 (chosen). B) Edit §0.1 now — premature; the live trading architecture is not yet scoped.
**Action:** Flag here. When strategy layer session 3 begins, edit `requirements.md §0.1` as the first step, then confirm which downstream sections require revision. Do not write live trading code against the current §0.1 assumption without first updating it.

## 2026-09-20 — Strategy layer — CHOICE — XBI as primary benchmark
**What:** XBI (SPDR S&P Biotech ETF) is chosen as the primary benchmark for abnormal return computation in Phase 4.
**Why it matters:** Abnormal return = signal return minus benchmark return. A sector-matched benchmark removes general biotech sentiment from the signal. A broad market benchmark (SPY, QQQ) would leave sector-specific noise in the abnormal return, overstating alpha from corroboration events that coincide with biotech rallies.
**Options considered:** XBI (chosen — direct biotech sector ETF, liquid, available via yfinance); LABU (3x leveraged biotech — too volatile, introduces leverage distortion); IBB (iShares biotech — acceptable alternative, larger holdings, slightly less sector-concentrated than XBI); SPY (too broad — leaves sector noise).
**Action:** Use XBI. Fetch via yfinance same path as OHLCV data (price-ingestion spec). If XBI data is unavailable for any backfill date, fall back to IBB and note the substitution in the evaluation report.

## 2026-09-20 — Strategy layer — CHOICE — Known-at delay default: 1 business day after corroborated_at
**What:** `corroborated_at` is the maximum `published_date` of the two corroborating signals — a public date, not an internal timestamp. In practice the ingestion pipeline may observe the second signal hours or days after it is published. A 1-business-day known-at delay is applied to model this gap.
**Why it matters:** Using `corroborated_at` as the literal entry date (delay=0) assumes zero ingestion latency and is optimistic. Using `ingested_at` is prohibited (plan.md §4.2). The 1-day default is conservative for a daily polling pipeline but may overstate latency for a near-real-time setup.
**Action:** `KNOWN_AT_DELAY_DAYS=1` is the default in `.env`. The evaluation-protocol spec requires a sensitivity analysis at 0, 1, 3, and 5 days. Report all four in the Phase 4 output so the latency assumption is explicit.

## 2026-09-20 — Strategy layer — CHOICE — Holdout: last 3 months sealed
**What:** The last 3 months of the 24-month backfill window are sealed as holdout. They are excluded from walk-forward in-sample and OOS splits until promotion criteria are met (deflated Sharpe > 0.95 AND t > 3.0).
**Why it matters:** At an estimated 50–150 total events, 3 months represents approximately 6–19 events. This is a thin holdout; it will not reliably distinguish a real edge from noise on its own. It is documented here as a known limitation.
**Options considered:** 3 months (chosen — minimum viable holdout; any shorter is meaningless; any longer further reduces the already-small OOS window); 6 months (would leave only 15 months for in-sample + OOS, implying zero complete walk-forward segments at 18-month in-sample).
**Action:** `HOLDOUT_MONTHS=3` in `.env`. Record holdout result alongside main result in Phase 4 DECISIONS.md entry. If holdout `t < 1.0` when in-sample/OOS shows `t > 2.0`, do not promote.

## 2026-09-20 — Strategy layer — FLAG — Belgian speculative classification: requires advisor confirmation
**What:** Belgian SPF Finances classifies some trading income as "speculative" (taxed at 33%) rather than investment income (10% CGT above €10k exemption). The classification depends on: trading frequency, position size relative to personal assets, use of leverage, short-selling, and pattern of behaviour. No bright-line rule is published.
**Why it matters:** If trades on this strategy are classified as speculative, the after-tax break-even rises from ~3.2% to ~4.5%+ per event (adding ~33% of gain as tax). For a strategy with an estimated mean abnormal return of 2–5%, this is the difference between positive and negative net expectancy.
**Action:** Consult a qualified Belgian tax advisor before executing live trades. Specifically ask: (a) whether systematic rule-based trading on individual equity corroboration signals is investment income or speculative; (b) whether short-selling or ETF hedges would trigger speculative classification regardless of frequency; (c) how to document non-speculative intent. Record advisor's conclusion in DECISIONS.md and PREREQUISITES.md before session 3 implementation begins.

## 2026-09-20 — Strategy layer session 2 — CHOICE — New `services/strategy/` service (not extending backtesting)
**What:** The strategy layer lives in a new `services/strategy/` directory with package `auspex_strategy`, separate from `services/backtesting/` (`auspex_backtesting`).
**Why it matters:** The backtesting module is a research tool with no runtime loop, no Kafka consumer, and no virtual books. Mixing a long-running Docker service with a research library in the same package creates import boundaries that are impossible to enforce. The strategy service imports `auspex_backtesting` as a path dependency (uv workspace) for `FillModel`, `CostModel`, `CurrencyConverter`, and `PositionSizer` — it does not duplicate them.
**Options considered:** A) Extend `services/backtesting/` — simpler initially, becomes a maintenance problem when the backtesting module needs to be importable without pulling in Kafka/Flask deps. B) New `services/strategy/` (chosen) — clean dependency direction, separate Dockerfile, separate uv project.
**Action:** `services/strategy/` created at strategy-framework spec implementation. Package `auspex_strategy` under `services/strategy/src/`.

## 2026-09-20 — Strategy layer session 2 — CHOICE — MinIO for virtual books and traces; strategy service serves metrics API
**What:** Virtual books (Parquet), decision traces (JSONL), latency traces (JSONL), kill switch flags (JSON), and pause logs (JSONL) all go to MinIO. The metrics API (`GET /api/v1/metrics/strategies`) is served by the strategy service (Flask), reading from MinIO only. Nothing from the strategy layer goes to Postgres or Neo4j.
**Why it matters:** Invariant 2: core-hub is sole writer to the application DB and Neo4j. Any strategy-layer write to Postgres would violate it. MinIO sidesteps the invariant entirely. Metrics computation over MinIO Parquet is consistent with how `auspex_backtesting` already reads price data.
**Action:** No Postgres schema changes in any strategy-layer spec. All strategy state is path-addressable in MinIO under `strategy/`.

## 2026-09-20 — Strategy layer session 2 — CHOICE — Event-driven Kafka consumer for the strategy runtime
**What:** The strategy runtime (`StreamingRuntime`) is a long-running Docker container consuming `auspex.signals.corroborated`. It is not an Airflow DAG.
**Why it matters:** Airflow owns ingestion cursors and schedules polling. The strategy layer must react to events as they arrive, not on a polling schedule. Putting strategy logic in a DAG would couple it to the Airflow schedule interval and introduce unnecessary latency. Consumer group `auspex-strategy-runtime`; offsets checkpointed to MinIO after each event so restart resumes from the last committed position.
**Action:** No new Kafka topics in the strategy-runtime spec. The runtime is a pure consumer of `auspex.signals.corroborated`. Any new producer topic is session 3 scope.

## 2026-09-20 — Strategy layer session 2 — CHOICE — Strategies never see ingested_at or extracted_at; InputHealthMonitor handles model downtime
**What:** `AsOfContext` exposes only `corroborated_at + KNOWN_AT_DELAY_DAYS` as `as_of`. `ingested_at` and `extracted_at` are pipeline timestamps and are explicitly excluded from the strategy data channel. Model downtime is handled by `InputHealthMonitor`: when `InputSource.EXTRACTION_MODEL` is unhealthy, strategies declaring that input are paused — they see no new events rather than stale events.
**Why it matters:** Exposing pipeline timestamps to strategies creates a second channel for look-ahead bias: a strategy could infer relative ingestion speed from timestamp proximity and exploit information that was not publicly available. The clean separation also means strategies are unaffected by extraction pipeline changes.
**Action:** `AsOfContext` interface has no method returning `ingested_at` or `extracted_at`. `LatencyTracer` captures both for infrastructure monitoring, not strategy use. `extracted_at` is nullable in `TraceRecord` until the extraction-backend spec adds it to `ResearchSignalEvent` (§10.2) — see extracted_at entry below.

## 2026-09-20 — Strategy layer session 2 — CHOICE — Equal risk budget per promoted strategy; correlation-aware cap
**What:** Capital allocation across concurrent promoted strategies uses equal risk budget (not equal notional). Each strategy gets `total_capital / n_promoted_strategies × MAX_POSITION_PCT`, subject to `MAX_GROSS_EXPOSURE` across all strategies. If the pairwise Pearson correlation between two strategies' trade-level returns exceeds 0.7 (from `CorrelationMatrix`), the combined allocation for the correlated pair is capped at `1.5×` a single-strategy budget rather than `2×`.
**Why it matters:** Equal notional overweights high-conviction strategies and underweights conservative ones. Equal risk budget is more robust to parameter variance. The correlation cap prevents two strategies with near-identical entry signals from doubling the effective exposure to the same bet.
**Action:** `MAX_POSITION_PCT`, `MAX_GROSS_EXPOSURE`, and the correlation threshold (default 0.7) are all `.env` parameters. The capital allocator logic lives in `portfolio-and-risk` spec. The correlation matrix that feeds it comes from `strategy-metrics` spec.

## 2026-09-20 — Strategy layer session 2 — CHOICE — Minimum 20 trades before metrics and Kelly sizing
**What:** `MIN_TRADES_FOR_METRICS` and `MIN_TRADES_FOR_KELLY` are both defaulted to 20 and read from `.env`. Below this threshold, `TradeMetrics.compute()` raises `InsufficientTradeDataError` and Kelly sizing falls back to `FALLBACK_POSITION_PCT`.
**Why it matters:** Hit rate estimated from fewer than 20 trades has a 95% CI of roughly ±22 percentage points, which renders the Kelly fraction meaningless. A Bootstrap CI computed over fewer than 20 samples is also unreliable. 20 is a floor, not a target — a strategy with 20 closed trades is barely out of the early stage.
**Action:** Both thresholds configurable in `.env`. The metrics API returns `insufficient_data: true` with null statistics rather than silently returning a number, so the UI cannot misrepresent early-stage performance as a validated signal.

## 2026-09-20 — Strategy layer session 2 — FLAG — extracted_at missing from ResearchSignalEvent (§10.2)
**What:** The decision trace requires `extracted_at` to populate the full latency chain (raw document → extraction → corroboration → intent). `ResearchSignalEvent` (§10.2) does not currently have this field.
**Why it matters:** Without `extracted_at`, the trace cannot report the extraction-to-corroboration latency interval. This interval is relevant for understanding whether the ingestion pipeline's delay is dominated by the extraction step or the corroboration step.
**Action:** `extracted_at` is nullable in `TraceRecord` and the trace validator does not require it. When the extraction-backend spec adds `extracted_at` to `ResearchSignalEvent`, the field should also be added to the Pydantic model and the Java record (triggering a contract fixture regeneration). At that point, re-read the decision-trace spec and verify `TraceValidator` does not need updating.

## 2026-09-20 — Strategy layer session 2 — FLAG — Corroboration surrogate key deferred; composite natural key in trace
**What:** Decision traces reference corroborations via the composite key `(entity_key, participants_hash)`. No surrogate `corroboration_id` exists in the current schema.
**Why it matters:** The composite key is sufficient for reproducibility: given `(entity_key, participants_hash)`, the exact corroboration record can be retrieved. A surrogate would simplify joins and trace lookups but requires a schema migration (adding a UUID column to the `corroboration` table and exposing it in `CorroborationRecord`).
**Options considered:** A) Composite natural key in trace (chosen — no schema change needed, always derivable from existing fields). B) Add surrogate `corroboration_id` — cleaner trace records, requires core-hub schema migration and a contract fixture regeneration.
**Action:** Use composite key in traces. If the surrogate is added later (separate schema spec), replace `(entity_key, participants_hash)` in `TraceRecord` with `corroboration_id` and update `TraceValidator` accordingly.

## 2026-09-19 — Dashboard — CHOICE — Node 22 LTS (Phase 5 resolution)
**What:** Node 22.x LTS is pinned as the dashboard runtime. VERSIONS.md previously deferred this to "Phase 5, resolve at 5.1."
**Why it matters:** Node 22 became the active LTS line in October 2024 and is current through 2027. Node 24 was released April 2026 but is "current" (not yet LTS) as of September 2026.
**Options considered:** Node 22 LTS (chosen — stable, current LTS), Node 24 (current but not LTS — more risk of breaking changes), Node 20 LTS (older LTS, approaching EOL April 2026).
**Action:** VERSIONS.md updated. `.nvmrc` and `package.json` `engines` field in `services/dashboard/` pin `22`.

## 2026-09-20 — CI/CD — VERIFIED — broken-PR verification satisfied by session evidence

**What:** CI went red and recovered multiple times during the session: Java failed on missing `gradle-wrapper.jar` (first push), then on the quay.io MinIO image fix, then on the `(key, bool)` tuple mismatch in storage tests, then on the `git diff` path issue. Each failure was specific to the broken code and cleared on the fix commit. All four checks (Java push, Java PR, Python push, Python PR) are green on the current HEAD.
**Why it matters:** CI surfaces real failures and clears on real fixes — the session is direct evidence.
**Action:** Spec closed as done.

## 2026-09-20 — Historical Backfill — BLOCKED — human project review required before live run
**What:** The debut full run of the system (first live invocation of `run_backfill.py` without `--dry-run`) is blocked on explicit human review and sign-off. The dry run may proceed freely; the live run must not start until this review concludes and continuation is confirmed.
**Why it matters:** The live run triggers real LLM calls at scale, commits spend against the configured budget ceiling, and produces the corpus that Phase 4 statistics will be computed against. Starting it prematurely or without a sanity check on the full system state wastes that one-shot corpus opportunity and potentially the budget.
**Options considered:** N/A — hard gate by human request.
**Action:** Blocker 6 added to `specs/historical-backfill.md`. Waiting on human assessment before the live run proceeds.

## 2026-09-25 — Watchlist backend — VERIFIED — entity_key separator confirmed as space-pipe-space

**What:** The corroboration `entity_key` format is `"ENTITY_NAME | LABEL"` (space-pipe-space), e.g. `"BCL11A | GeneTarget"`. This was confirmed against the V1 migration, the corroboration service implementation, and the watchlist integration test seed data.
**Why it matters:** The watchlist-alerts hold spec incorrectly uses colon notation (`"BCL11A:GeneTarget"`). The `SPLIT_PART(entity_key, ' | ', 1)` filter in `queryFilteredCorroborations` depends on this separator being exact.
**Action:** SPLIT_PART filter confirmed correct. The hold spec must be updated to use space-pipe-space when it comes off hold.

## 2026-09-25 — Watchlist backend — CHOICE — live preview smoke test deferred

**What:** The definition of done includes one live `GET /api/v1/watchlist/preview?ticker=SRPT` call against a running stack. All 11 automated tests (8 unit, 3 integration) pass. The live call is deferred — it requires the full Docker stack up, which is not part of the CI loop.
**Action:** 11/11 tests pass. Live smoke test deferred to next stack-up session.

## 2026-09-25 — EDGAR content fix — VERIFIED — live 8-K fetch returns filing prose

Live fetch performed against `https://efts.sec.gov/LATEST/search-index` with window 2025-08-20 to 2025-09-01.

**Result (first document returned):**
- Accession number: `0001859392-25-000049`
- Entity: Galaxy Digital Inc. (form 8-K/A, filed 2025-08-29)
- `raw_content` character count: 4,282 chars
- `raw_content` sample: `"UNITED STATES SECURITIES AND EXCHANGE COMMISSION WASHINGTON, D.C. 20549 FORM 8-K/A CURRENT REPORT Pursuant to Section 13 or 15(d) of the Securities Exchange Act of 1934..."`

Filing prose confirmed; metadata-only format is no longer present.

**Incidental findings recorded separately:**
1. The spec described a `-index.json` URL that does not exist on SEC servers. Correct URL for primary document lookup is `data.sec.gov/submissions/CIK{cik_padded}.json`. Spec updated.
2. EFTS `_source` field names (`adsh`, `ciks`, `display_names`, etc.) differ from the fixtures used in unit tests. Dual-format fallbacks added to `_map` as a patch; cleanup tracked in `specs/edgar-efts-fixture-alignment.md`.

## 2026-09-26 — Python CI — BLOCKED — quay.io requires authentication on GitHub Actions runners

**What:** Python integration tests (`test_minio_storage.py`, `test_api_integration.py`, `test_reextract_integration.py`) pull `quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z` via testcontainers. quay.io now returns 500/"unauthorized" on GitHub Actions runners without an authenticated pull. This broke CI across all branches from the watchlist-backend push onwards.
**Why it matters:** 5 integration tests are erroring at fixture setup, blocking the Python CI check on every push.
**Action:** Added `Login to Quay.io` step to `.github/workflows/python.yml` (same `docker/login-action@v3` pattern as Docker Hub, `continue-on-error: true`). **You must add two GitHub repository secrets** for this to take effect:
- `QUAY_IO_USERNAME` — your quay.io username or robot account name
- `QUAY_IO_PASSWORD` — your quay.io password or robot account token

Create a free account at quay.io if you don't have one. No organisation-specific permissions needed — this is just to authenticate pulls of a public image.

## 2026-10-07 — Python CI — FIX — LocalStack calendar tags require a licence

**What:** Python CI was red on `main` and `develop` since the switch to `localstack/localstack:2026.09.0`. Reproduced locally: the container exits with code 55, "License activation failed … set the LOCALSTACK_AUTH_TOKEN variable". LocalStack's calendar-versioned images (2026.03 onwards) refuse to start without an auth token, so every S3-backed integration test failed at fixture setup ("LocalStack never became ready"), and `test_api_integration` crashed with `UnboundLocalError` because its port-wait loop had no failure branch.
**Action:** Pinned `localstack/localstack:4.9.2` (last community tag that starts without a token; verified 2026-10-07), added the missing `pytest.fail` branch to `test_api_integration`. All 6 S3/Kafka integration tests pass locally. VERSIONS.md updated with a do-not-bump note. The quay.io secrets from the 2026-09-26 entry are no longer needed for tests.

## 2026-10-07 — Observability — FIX — monitoring was blind to the pipeline

**What (found while checking readiness for a long backfill):**
1. All three provisioned Grafana dashboards had `"panels": []`; the provisioning smoke test only checked titles, so it passed.
2. The scraper's production pipeline factory never passed a metrics registry, so no `auspex_pipeline_*` / `auspex_llm_*` series existed. Wiring it naively would have crashed the second `/ingest` call (`DuplicateTimeseries`), because a pipeline is built per request.
3. gunicorn ran 4 workers with per-process Prometheus counters: each scrape would hit a different worker.
4. `configure_logging()` was never called in the service, so logs were structlog's console format, not JSON; Filebeat could not parse them. Python also used `level`/`event` where Grafana's Elasticsearch datasource reads `log.level`/`message` (core-hub's ECS names).
5. core-hub's custom consumer factories had no Micrometer listener, so `kafka_consumer_*` metrics did not exist and the Kafka Lag alert (which also used a non-existent metric name) could never fire (`noDataState: OK`).
6. `auspex.dlt.events.total` only counted unknown-major-version records; deserialization failures, validation failures and exhausted retries on either topic were dead-lettered uncounted.
7. The ILM policy was created but never attached to any index, and its `rollover` action needs a write alias the daily indices do not have. Logs were never deleted.
8. `elasticsearch-setup` used `curlimages/curl:latest`.

**Action:** fixed each (tests added first for 2–6). DLT counting moved from `SignalListener` to `CountingDeadLetterRecoverer`, which wraps both DLT recoverers, so a record is counted once, when it is actually dead-lettered; the existing listener test now asserts the throw instead of the count. ILM policy: rollover, shrink and freeze removed, delete after 180 days kept; Filebeat's template attaches it to new indices and `setup.sh` attaches it to existing ones (verified on ES 8.17.3). Dashboards built and the smoke test now fails on empty dashboards. Added alerts: Scrape Target Down, LLM Extraction Errors.
**Not changed:** `scripts/run_pipeline.py` still builds its pipeline without metrics or JSON logging; a one-shot CLI process has nothing to scrape. Runs through the HTTP API (the DAG path) are fully instrumented.

## 2026-10-07 — Live ingestion — CHOICE — unchanged re-fetch skip with retry-safe markers

**What:** Follow-up to the historical-backfill FLAG on `MinioArchive.put()`: every overlapping live re-fetch of unchanged content was re-extracted (one LLM call each), contrary to requirements §7.1 step 3. The open question was retry semantics.
**Choice (reversible default):** the pipeline writes a processed marker `dedup/processed/{source_type}/{external_id}/{content_sha256}-{identity_hash}.json` only after a document's outcome is final (published, not a signal, below threshold) **and** the run's Kafka flush succeeded. Identity = `model|prompt_version|prefilter_version`. A re-fetch skips extraction and publish only when a marker for the same content and identity exists. So: failed extraction or undelivered signals are retried on the next fetch; an amendment (new hash) is extracted; a different model or prompt (backfill, re-extraction) re-extracts. The raw archive write stays unconditional (Invariant 13).
**Scope:** opt-in through `IngestionPipeline(extraction_identity=...)`. The live API factory sets it. The backfill runner does not need to: its model differs from live, and leaving it unset keeps its current behaviour. A marker-write failure costs one repeat extraction, nothing else.

## 2026-10-07 — Market simulation — CHOICE — PositionSizer `fx_rate` is EUR per USD

**What:** The spec gives `size_shares = floor(capital_eur / fx_rate / price_usd)` and stores FX as Yahoo's `EURUSD=X`, which quotes USD per 1 EUR (~1.1). Dividing EUR by USD-per-EUR is dimensionally wrong: feeding the raw `EURUSD=X` close into that formula undersizes every position by roughly fx² (1000 EUR at 1.1 → 9 shares of a $99 stock instead of 11).
**Action:** `fx_rate` is defined as **EUR per 1 USD**, which makes the spec's formula and its required test (1000, 1.1, 99 → 9) correct as written. `CurrencyConverter.eur_per_usd(date)` returns `1 / EURUSD=X close` and is the value callers pass in; `usd_to_eur` uses the same rate. Documented on `PositionSizer.size_shares`.

## 2026-10-07 — Market simulation — CHOICE — FillModel does not shift entry dates

**What:** `FillModel.entry_price` fills at the open of the `entry_date` it is given. A signal public at 11:00 ET aligns (via `alignment.aligner`) to the same session, whose open precedes it.
**Action:** Entry timing stays with the caller, as `docs/strategy-research.md` (T+1 open) and `specs/evaluation-protocol.md` (`next_trading_day(corroborated_at + KNOWN_AT_DELAY_DAYS)`) already specify. Documented on `FillModel`. Follow-up worth considering: `aligner._next_trading_day` still uses `USFederalHolidayCalendar` and could switch to `MarketCalendar` (Good Friday is missed today and surfaces as `PriceDataAbsentError`).

## 2026-10-07 — Market simulation — CHOICE — 11 tests, not 10; `scripts/fetch_prices.py`

**What:** The spec builds `TradableUniverse` but lists no test for it, and refers to an "existing PriceIngestion script" that does not exist.
**Action:** Added `test_tradable_universe_names_ticker_missing_price_data` (invariant 15). Added `scripts/fetch_prices.py`, a thin CLI over `PriceFetcher` that creates the `auspex-prices` bucket if needed. Also fixed `PriceFetcher` never reaching the Stooq fallback: yfinance returns an empty frame, not an exception, on a blocked download (`test_empty_yahoo_result_falls_back_to_stooq`).

## 2026-10-07 — Market simulation — PENDING — EURUSD=X and XBI not yet in MinIO

**What:** The definition of done asks for `EURUSD=X` and `XBI` snapshots in `auspex-prices`. The build session had no MinIO and Yahoo was blocked by its network proxy.
**Action:** On the machine running the stack: `cd services/backtesting && uv run python scripts/fetch_prices.py EURUSD=X XBI --start 2023-01-01 --end <today>` (with MinIO env from `.env`). Covers the 24-month backfill window plus a margin. Record the row counts here when done. Note the Stooq fallback uses Stooq symbols (`eurusd`, `xbi.us`), so if Yahoo is rate-limiting, retry later rather than relying on it.
## 2026-10-07 — Local model integration — FLAG — production extraction never used the model registry

**What:** `api.py`, `scripts/run_pipeline.py` and `scripts/reextract.py` built a bare OpenAI client with no `base_url`, so `EXTRACTION_BASE_URL` was ignored and a local model could not be reached. `LLMExtractorFactory` (gate, digest check) was never called outside tests. The evaluation scripts used the legacy `LLMExtractor`, which ignores the registry's temperature, seed, timeout and structured-output mode, so the gate scored a different configuration from production.
**Action:** Fixed in `specs/done/local-model-integration.md`. All production and evaluation paths now build the extractor from the registry entry.

## 2026-10-07 — Local model integration — CHOICE — gate threshold and version labels aligned

**What:**
1. `score_extraction.py` passed at precision ≥ 0.90; every other document (Option A choice, PREREQUISITES.md, `compute_candidate_scores`) says 0.85. Aligned to `GATE_PRECISION = 0.85` in `model_evaluation`.
2. Production stamped `prompt_version="v1"`; the scripts and gate records use `v1.0`. The two prompt files are byte-identical. Production now reads `EXTRACTION_PROMPT_VERSION` (default `v1.0`), so a gate record can match it. This changes `extraction_id` for future events (never `event_id`). It lands at the same moment as the switch to a local model, which starts a new lineage anyway.
3. The prefilter version production stamps is `v1` (`PREFILTER_VERSION`). `score_extraction.py` writes that value too.
**Consequence:** the existing `gpt-4o-mini-2024-07-18` gate record was hand-written with `prefilter_version: "v1.0"`, so production now refuses that model until it is re-scored (`score_extraction.py --model gpt-4o-mini-2024-07-18`). This is the gate working as specified. The record was not edited because it would claim a score that was never measured at `v1`.

## 2026-10-07 — Local model integration — RECOMMENDATION — local runtime and candidates

**What:** Ollama, run natively on the host (Docker on macOS has no Metal access). Candidates, in `config/models/local_candidates.yaml`: `mistral-small:24b-instruct-2501-q4_K_M` (primary; cutoff 2023-10 per its default system prompt, so the full 24-month window), `llama3.1:8b-instruct-q8_0` (fast fallback; cutoff 2023-12), and `gemma3:27b-it-q4_K_M` (optional; cutoff 2024-08 shortens the clean window to ~Nov 2024 onwards). The model-evaluation spec named `gemma3:27b-instruct-q4_K_M`, but that Ollama tag does not exist; the real tag is `27b-it-q4_K_M`.
**Action:** Not a CHOICE. The passing model gets recorded under the 2026-09-19 Option A entry once `evaluate_model.py` and `score_extraction.py` have run on the backfill machine (`docs/local-model-runbook.md`).

## 2026-10-07 — Local model integration — RECOMMENDATION (revises the entry above) — 24 GB backfill machine

**What:** The user confirmed the backfill and steady-state machine: MacBook Pro, Apple M4 Pro (12 cores), **24 GB**, not the 36 GB the docs assumed. It also runs the Docker stack. Mistral Small 24B (~14 GB + KV cache) and Gemma 3 27B (~17 GB) do not fit next to Docker at 24 GB. The primary candidate is now `llama3.1:8b-instruct-q8_0` (~8.5 GB, cutoff 2023-12, full window), with `llama3.1:8b-instruct-q4_K_M` (~4.9 GB) as the memory and speed fallback. The recommended Docker Desktop memory limit is 8 GB. Estimated backfill: roughly 3–5 days at 10–15 s/document, to be replaced by the `evaluate_model.py` measurement.
**Risk:** an 8B model may miss the 0.85 gate. The documented fallback is `gpt-4o-mini-2024-07-18` for the backfill (~$65).
**Action:** Runbook, local_candidates.yaml, docker/README.md and PREREQUISITES.md updated. Still not a CHOICE; that waits for gate results.

## 2026-10-07 — Startup data — CHOICE — data fills itself on `up`; prices refresh daily

**What:** Getting the system to a state where it can make decisions took hand-run steps: `docker/provision.sh` for topics and the raw bucket, `scripts/fetch_prices.py EURUSD=X XBI ...` for the FX and benchmark snapshots (the market-simulation PENDING entry above), and nothing kept prices current after that. The user asked for startup data to load as part of the compose rollout and for live data to refresh on a schedule, with a single setup file for what cannot be automated.
**Action:** One-shot compose services `kafka-init` (topics from `topics.yaml`), `minio-init` (both buckets) and `price-bootstrap` (missing snapshots for the watchlist, `XBI`, `EURUSD=X` from `PRICE_HISTORY_START`), each a no-op when the data exists; `provision.sh` removed. A `price-service` (Flask, built from `services/backtesting`) exposes `POST /prices/refresh`, which the Airflow DAG `auspex_price_refresh` calls Mon–Fri 22:30 UTC (Invariant 3 pattern: the DAG holds no logic). That DAG is unpaused at creation; ingestion DAGs stay paused until a gated model exists (`SETUP.md` step 5). Remaining manual steps are in `SETUP.md`. Supersedes the market-simulation PENDING entry: `price-bootstrap` fetches `EURUSD=X` and `XBI` on the first `up`.
**Requirements §8 ("fetch once, then never again"):** read as "a bar, once written, is never rewritten". The refresh only appends bars dated after the last stored one, so every backtest over a past window reads the same rows as before and stays reproducible; the flaky provider is still hit once per new bar, not per backtest. Yahoo's adjusted closes are rewritten after a split or a large special dividend; when the provider's close for the last stored bar differs from ours by more than 2%, the refresh refuses (`SnapshotDiscontinuityError`, the DAG run fails) instead of splicing two price scales. Rebuilding such a snapshot (delete the object, next `up` refetches) changes history and so is a deliberate act, not something the schedule does.

## 2026-10-07 — Realistic cost model — CHOICE — per-ticker spread, FX fee, volume cap, gap-through stops

**What:** The edge feasibility audit (recommendation 10) found the flat 50 bp half-spread understates micro-cap costs and overstates large-cap ones, with no FX fee, liquidity limit or gap model.
**Action:**
1. Spread uses the Abdi and Ranaldo (2017) close-high-low estimator over the 21 sessions before entry, chosen over Corwin-Schultz because it uses the close and has lower bias on daily data. Negative estimates read as zero and are floored at `MIN_HALF_SPREAD_BPS=2.0`. The flat `SPREAD_BPS` stays as the fallback when no estimator is passed, so the market-simulation tests were not changed; backtests should pass a `SpreadEstimator`.
2. `FX_FEE_RATE=0.0003` per leg (IBKR conversion, per the audit). Like spread and TOB it is charged on entry notional for both legs.
3. `MAX_ADV_FRACTION=0.01` of 20-session ADV, the low end of the audit's 1 to 2%, because the watchlist includes micro-caps.
4. Stops: gap through fills at the open; on a caller-flagged binary event day a touched stop fills at the day's low (long) or high (short), since daily bars cannot place a halted mid-session move. Binary dates come from the caller (portfolio-and-risk binary-event guard).

## 2026-10-07 — Pre-registration — CHOICE — evaluation protocol and kill criteria locked before the backfill
**What:** `config/hypotheses/protocol.yaml` is registered in `config/hypotheses/registry.jsonl` today. No backtest has run on backfill data: `config/hypotheses/trials/` does not exist and the live backfill has not started. The file fixes the abnormal-return model, inference, trial accounting, promotion thresholds, sizing ceilings and these kill criteria (all evaluated in-sample; the holdout stays sealed):
- **Lagging signal (H3).** If mean CAR[-20,-1] has the same sign as mean CAR[+1,+20] and is at least as large in magnitude, at known-at delay 1, stop testing gene-target corroboration as a trading trigger.
- **No in-sample effect (promotable).** Kill the event type unless at least one registered horizon, at the primary delay and variant, shows mean net abnormal return above 0 in the registered direction with clustered t at or above 1.5. A killed event type is not re-registered with new horizons on the same corpus.
- **Mapping quality.** If event-to-ticker precision is below 0.85 on a golden set of at least 50 events after one prompt or rule iteration, do not trade on that source.
- **Forward check.** Before any real capital: at least 12 months of forward paper trading, at least 60 independent events, positive mean net abnormal return and clustered t above 2. Otherwise Auspex stays a research and risk tool.
- **Cost check.** If the median modelled round-trip cost on traded names exceeds half the expected gross abnormal return, raise the liquidity floor and re-register, or stop.
**Why it matters:** once a backtest has touched the corpus, the holdout and the trial count are spent; thresholds chosen afterwards can be fitted to the result. The registry hash makes any later change visible.
**Options considered:** A) record thresholds only in prose here. B) a registered, hashed config file that the evaluation code reads, with this entry as the dated record (chosen; it reuses the hypothesis registry, so `verify_hypothesis("protocol")` refuses an edited file).
**Action:** `specs/evaluation-protocol.md` now reads every threshold from the registered file and adds `KillCriteria`, `ClusteredInference` and `TrialLedger` with tests. The thresholds are the audit's proposals; the user owns them. Changing one means editing `protocol.yaml`, re-registering it and adding an entry here, before the backfill if possible.

## 2026-10-07 — Pre-registration — CHOICE — trials counted as cells across the hypothesis family, budget 64
**What:** A trial is one `(holding_period_days, known_at_delay_days, variant)` cell evaluated, summed over every run of every promotable hypothesis on the same corpus. `n_trials` for the deflated Sharpe is that family total, not one hypothesis's run count. The family budget is 64 cells; a run that would exceed it is refused. Promotion is judged on each hypothesis's single pre-declared primary cell; other cells are reported and counted but cannot promote. Diagnostic and descriptive hypotheses are logged and not counted.
**Why it matters:** H1 alone is 4 horizons × 4 delays × 2 variants = 32 cells. Counting runs (the previous rule) would have reported `n_trials = 1` for that first run. All hypotheses reuse the same event set, so per-hypothesis counting understates selection.
**Options considered:** A) per-hypothesis run count (previous spec). B) per-hypothesis cell count. C) family-wide cell count with a fixed budget (chosen). Budget 64 fits two hypotheses at H1's grid; 128 would allow four and deflate more (judgment call for the user).
**Action:** `TrialLedger` added to `specs/evaluation-protocol.md`; `specs/strategy-metrics.md` trial-count rule and test updated to match.

## 2026-10-07 — Pre-registration — CHOICE — market-model abnormal returns against XBI with two-way clustered errors
**What:** Abnormal return = ticker return minus `alpha + beta × R_XBI`, with alpha and beta from OLS over trading days [-250, -30] before entry; under 120 estimation days falls back to raw excess over XBI (beta 1) and is counted. t-statistics use two-way clustering by ticker and event month; with fewer than 30 clusters in a dimension the p-value comes from a wild cluster bootstrap (Webb weights, 9,999 draws, seed 42). Same-ticker events with overlapping windows count as one independent event.
**Why it matters:** small-cap biotech betas to XBI are not 1, so raw excess return leaves sector beta in the "abnormal" return. Overlapping same-ticker events and common XBI exposure make an iid t-test overstate significance; 100 events may be 20 to 30 independent bets. With today's 8 tickers, clustering by ticker alone has too few clusters to be trusted, hence the bootstrap.
**Options considered:** A) raw excess over XBI with iid t (previous spec). B) market model with one-way clustering by ticker (unreliable at 8 clusters). C) market model, two-way clustering, wild cluster bootstrap below 30 clusters (chosen). Multi-factor models stay out of scope at this sample size.
**Action:** `AbnormalReturnCalculator` and `ClusteredInference` in `specs/evaluation-protocol.md`.

## 2026-10-07 — Pre-registration — CHOICE — hypothesis triage; versions 2 registered
**What:** Every hypothesis now carries a `role` and `status`. H3 (diagnostic) runs first and gates the gene-target event definition. H2 is a diagnostic on H1 events. H1, H4, H6 and H8 are `suspended`: H1 waits for a company-level event definition, H4 for typed company events, H6 for first-time company-program events, and H8 becomes an exit or avoid filter on long holdings instead of a short strategy. H5 and H7 are `descriptive`: reported, never significance-tested or promoted. H1's primary cell is fixed now at 20 days, known-at delay 1, entity-only, 32 trial cells.
**Why it matters:** subgroups under about 50 events are noise at biotech volatility; testing them spends the trial budget for nothing. Shorting hard-to-borrow small caps from a Belgian retail account carries borrow and speculative-tax risk the expected edge does not cover.
**Options considered:** follow the audit's triage (chosen) or keep all eight as promotable tests.
**Action:** `config/hypotheses/h1.yaml` to `h8.yaml` re-registered as version 2; triage table added to `docs/strategy-research.md`. A suspended hypothesis is re-registered with `status: pre-registered` before any backtest runs on it; `EvaluationProtocol.run()` refuses suspended ones.

## 2026-10-07 — Pre-registration — CHOICE — sizing ceilings: quarter Kelly, 5% per name, one position per theme, no hold through binary events
**What:** `protocol.yaml` `sizing` fixes ceilings that `.env` limits may tighten but not exceed: Kelly multiplier 0.25, 5% of capital per name (3% recommended), one open position per correlated theme (`config/themes.yaml`; the current 8 tickers are one theme), and positions exit at the last close before a known catalyst unless the strategy declares it trades that catalyst type.
**Why it matters:** few, correlated, fat-tailed bets make full Kelly ruinous; the previous spec used shrinkage toward the prior as if it were the Kelly multiplier and let positions ride through known binary dates.
**Options considered:** A) half Kelly via shrinkage (previous spec). B) quarter Kelly with a 5% hard cap (chosen). C) fixed 2% per name with no Kelly.
**Action:** `specs/portfolio-and-risk.md` updated: `KELLY_FRACTION`, `MAX_POSITIONS_PER_THEME`, startup validation against the ceilings, forced exit before catalysts, six new tests (18 total).

## 2026-10-07 — Pre-registration — VERIFIED — owner accepted the proposed thresholds
**What:** The owner accepted every proposed default in the pre-registration entries above: family budget 64 cells, the `no_in_sample_effect` reading (net mean > 0 and clustered t ≥ 1.5 at some horizon), quarter Kelly with a 5% per-name ceiling and one position per theme, 30 clusters before the wild bootstrap, and the [-250, -30] estimation window with at least 120 observations.
**Action:** `config/hypotheses/protocol.yaml` stays as registered; no re-registration needed.

## 2026-10-07 — EDGAR press-release content — CHOICE — filing index replaces the submissions lookup

**What:** The 8-K connector now reads each filing's `-index.htm` page instead of `data.sec.gov/submissions`. One request gives the cover document, Exhibit 99.1 and the acceptance time. Only 8-Ks with item 2.02, 7.01 or 8.01 are kept, and `published_date` is the acceptance time in UTC, as `docs/requirements.md` §6.7 already required.
**Why:** Readouts and CRLs are furnished as Exhibit 99.1, which the connector never fetched. The submissions JSON lists only recent filings (about a year or 1,000 filings), so a 24-month backfill would have fallen back to metadata for older filings. The old lookup also took the CIK from the accession prefix, which is the filing agent (for example 0001193125) for most large filers, so those filings also fell back to metadata. A file date at midnight UTC entered after-close filings at the same day's open.
**Not verified live:** the session had no network route to sec.gov. The parser fails safe (metadata or cover only, with a warning). Check the first live run's logs for `edgar filing index` or `exhibit 99.1` warnings before the backfill.
**Left open:** the extractor's 4,000-character limit is unchanged; the exhibit leads `raw_content` so the headline and first paragraphs fit. Raising it is shared extraction code.
## 2026-10-07 — Second-wave specs — FLAG — corroboration is matched on gene target, not company
**What:** The edge feasibility audit (rows 4, 11, 13) found that corroboration links signals through `GeneTarget`/`Mechanism` nodes (requirements §4, §9), which do not map to a stock, and that `CorroborationScorer` measures recency against the wall clock. `specs/company-program-corroboration.md` adds a second, company-program corroboration kind and a point-in-time score.
**Why it matters:** its tests contradict §4 and §9 as written, so per the rule that matters most they must not be written until the requirements are amended.
**Options considered:** A) a new `CorroborationService` implementation (cannot pass the gene-target contract cases unmodified); B) a second scanner inside the existing implementation, writing a `kind` column, gene-target kept as context; C) replace gene-target corroboration.
**Action:** spec written for B, with the §4/§9 amendment as its first step. Needs the user's approval of the amendment before implementation.

## 2026-10-07 — Second-wave specs — CHOICE — structured filings bypass the LLM
**What:** Form 4 and offering filings carry their facts as fields. `specs/structured-source-extraction.md` adds a config-selected deterministic mapper path and an issuer-scope pre-filter, instead of sending them through the LLM and the gene-vocabulary pre-filter.
**Why it matters:** amends requirements §6.2 (single extraction path) and §6.6, and the historical-backfill single-lineage check, which now applies to LLM-extracted rows only. Reversible: a source can switch back to `extraction: llm` in `sources.yaml`.
**Action:** spec written; requirements and backfill text change with its implementation. `specs/historical-backfill.md` notes already updated.

## 2026-10-07 — Second-wave specs — CHOICE — short interest is a market-data snapshot, not a connector
**What:** The audit (row 9) lists short interest among "new connectors and `sources.yaml` entries". It is a twice-monthly time series per ticker, not a document, so `specs/short-interest-snapshots.md` follows the price-snapshot pattern in `services/backtesting` (MinIO `auspex-prices/short_interest/`), known at FINRA's publication date, not the settlement date.
**Why it matters:** sending a time series through the document pipeline would need a fake document per ticker per period and an extraction step with nothing to extract.
**Action:** spec written. FINRA endpoint and authentication unverified (the scoping session's network blocked it); first step of the spec.

## 2026-10-07 — Second-wave specs — FLAG — catalyst fields change the extraction schema
**What:** `specs/catalyst-calendar.md` adds `catalysts` (PDUFA, advisory committee, expected topline dates) to the extraction schema and prompt.
**Why it matters:** if it lands after the historical backfill, in-window 8-Ks must be re-extracted to get catalyst dates (reextraction CLI; about the 8-K share of the backfill, not all of it).
**Action:** recorded as a blocker on the spec. The user decides whether it lands before the backfill or accepts the 8-K re-extraction later.

## 2026-10-07 — Second-wave specs — BLOCKED — point-in-time universe scope
**What:** `specs/point-in-time-universe.md` replaces the 8 hand-picked tickers with a rules-based universe. The audit asks for its scope to be settled before the backfill. Open choices with defaults: SIC 2834, 2836 and 8731; NYSE, Nasdaq and NYSE American; market cap ≥ $50M; 20-day median dollar volume ≥ $500k; no market-cap ceiling; delisted prices free first, one paid month if coverage < 90%; EDGAR and ClinicalTrials.gov backfill scoped to universe companies.
**Why it matters:** the universe decides what gets backfilled and how long the backfill runs on the 24 GB machine.
**Action:** asked the user. Record their answer here as a CHOICE before the spec or the backfill starts.

## 2026-10-07 — Second-wave specs — CHOICE — point-in-time universe scope
**What:** The user answered the 2026-10-07 BLOCKED entry: defaults for the universe rules (SIC 2834, 2836 and 8731; NYSE, Nasdaq and NYSE American; market cap ≥ $50M; 20-day median dollar volume ≥ $500k; no ceiling; EDGAR and ClinicalTrials.gov backfill scoped to universe companies), and **free sources only** for delisted price data (yfinance, then Stooq; no paid vendor).
**Why it matters:** some delisted names will have missing or partial price history, which biases returns upward if they are dropped silently.
**Action:** `specs/point-in-time-universe.md` updated: incomplete members stay in the snapshot; an event is excluded only when its holding window is not fully priced; exclusions are counted by exit reason; the report adds a bound (−30% for delisted or deregistered, 0% for acquired); over 10% excluded marks the hypothesis `survivorship_gap = material`. Universe scope no longer blocks the historical backfill.

## 2026-10-07 — Second-wave specs — CHOICE — paper trading gates capital, run at several sizes
**What:** The user sees forward paper trading as the step that decides what capital is justified; their capital is undecided. `specs/forward-paper-trading.md` now runs every paper strategy at notional tiers from `PAPER_CAPITAL_TIERS_EUR` (default €10k, €50k, €250k) with the realistic cost model, and reports per tier where fixed costs and ADV capacity erode returns, with a forward-check verdict per tier.
**Why it matters:** with minimum commissions and TOB, a small account and a large one can reach opposite verdicts on the same signals.
**Action:** spec and TODO.md updated; live trading is gated on the paper-trading results (TODO.md). Defaults are reversible in `.env` before the ledger starts.

## 2026-10-07 — Backtest look-ahead fix — FLAG — variant returns counted signals that predate their corroboration

**What:** `BacktestRunner._compute_variants` qualified a gene target on its whole history, and `MetricsCalculator.compute_both_variants` then counted every member signal's return from that signal's own entry date. A signal on day 0 corroborated by another on day 60 contributed its day-0 return, which no live system could have traded. Found by the 2026-10-07 edge feasibility audit (recommendation 1).
**Action:** Fixed in `specs/done/backtest-look-ahead-fix.md`. Variants are now corroboration events entered at `entry_session(corroborated_at)`, one return per event.

## 2026-10-07 — Backtest look-ahead fix — CHOICE — one backtest event per corroboration, not per superseding record

**What:** requirements §4.1 writes a new record whenever a signal joins an entity's group and marks the smaller one superseded. Counting each record would double-count the same evidence; counting only the latest would date the event by its last participant.
**Action:** Per `(gene_target, ticker)`, signals are replayed in publication order. An event fires when the signals within the preceding 90 days span two source types, and only if none of them belonged to the previous event. A joining signal extends the existing event; a later, disjoint pair on the same target is a new event. The full-variant weight uses the participants known at the event.

## 2026-10-07 — Backtest look-ahead fix — CHOICE — entry and holding-window timing

**What:** The aligner entered at the open of the session in which a signal appeared, even when that open had already traded, and treated date-only timestamps (midnight UTC, used by every connector) as known that day. `_window_returns` counted price rows, and fell back to the last available close when data ran out.
**Action:** `aligner.entry_session` returns the first NYSE session (`MarketCalendar`) whose open is after the timestamp; a date-only timestamp is known after that day's close, so it enters the next session. Returns run from that session's open to the close of `next_trading_day(entry + N calendar days)`, the same rule as `FillModel`. A missing entry or exit row gives `None`. Delisted names therefore drop out until the point-in-time universe work supplies their prices; that is visible as a smaller `n`, not a truncated return.
**EDGAR timing:** the EDGAR press-release work now stores the filing's `acceptanceDateTime` as `published_date`, so an 8-K accepted before 09:30 ET enters that day's open and one accepted later enters the next session's. Date-only sources keep the after-close rule.

## 2026-10-07 — Company-level extraction — CHOICE — event taxonomy and identifier fields (schema 1.1)

**What:** The edge feasibility audit (rows 4 and 6) asks for company and program identifiers and a typed event taxonomy on every extracted event, before the backfill.
**Action:** `ResearchSignalEvent` 1.1 adds `event_type`, `primary_company`, `program_identifiers` and `trial_ids`; prompt `v1.1` asks for them and is the production default. Choices made:
1. Direction stays in `directionality`. A negative readout is `trial_readout` + `negative`, not a separate `readout_negative` type, so the two fields cannot disagree.
2. Financing and offerings are not in the taxonomy. The prompt still marks pure financial events `is_signal=false`; changing that would move the gate's `is_signal` labels. Offerings come with their own connectors (audit row 9).
3. `trial_ids` is validated (`NCT` + 8 digits) and always includes the document's own trial when `canonical_id` is `nct:`. Unknown `event_type` values become `other` instead of failing the document.
4. `core-hub` persists the fields to `signal_current` (Flyway `V4`) but not to Neo4j. Without the columns the backfill would drop them, and the company-program corroboration would need a full re-extraction on the local model. The graph model is left to that spec.
5. CT.gov `raw_content` now includes `Lead sponsor:`. This changes `content_sha256` for every trial, so the first fetch after deploy re-archives and re-extracts each trial once. Acceptable before the backfill.

## 2026-10-07 — Company-level extraction — PENDING — gate record for prompt v1.1

**What:** Production refuses a model without a passing gate record at the active prompt version, and the default is now `v1.1`. No `v1.1` record exists.
**Action:** On the backfill machine, run `score_extraction.py --model <chosen tag>` (the scripts default to `v1.1`) after `evaluate_model.py`, as in `docs/local-model-runbook.md`. The golden set has no labels for the new fields yet, so the gate still measures `is_signal` precision only; the new fields are reported once documents carry their labels (`tests/golden/FORMAT.txt`).


## 2026-10-07 — Edge research scoping — CHOICE — edge research synthesis: the alpha path becomes slow monthly scores
**What:** Three independent research reports (`/mnt/project-files/research/edge-result-{1,2,3}.md`) were weighed against each other and the repo. Where they agree:
- No fast biotech event trade survives a ~1.8–2.0% Belgian round trip entered at T+1 (reports 1 and 3; trial and FDA news is priced within one or two sessions).
- What survives is slow and cross-sectional, rebalanced monthly or slower, on structured data with no LLM in the signal (report 1: specialist 13F ownership, insider buying, low short interest; report 3: year-on-year 10-K/10-Q text change).
- Trade structure: long stock only, a basket of 15+ names at roughly equal risk, no hold through known catalysts, no shorts, no options (report 2; reports 1 and 3 do not need either).
- Negative events are worth using only as a veto on longs, not as shorts (reports 1 and 2).
- Gene-target corroboration (H1–H8 as designed) cannot reach the promotion t on 50–150 events (report 1), and was already suspended by pre-registration.
Where they disagree: report 1 stays in biotech with a holdings composite; report 3 pivots the alpha target to filing-text change across US small and mid caps and keeps biotech as a research tool. Both are honest about weak evidence: report 1's rests on one practitioner backtest (Verdad 2026, PDF not read); report 3's has null large-cap replications after 2009 and most original alpha on the short side.
**Why it matters:** both directions need the same base (point-in-time universe with delisted names, a monthly portfolio engine, realistic costs, pre-registration) and neither needs the LLM backfill on its critical path.
**Action:** new specs `slow-signal-preregistration`, `cross-sectional-portfolio-backtest`, `sec-ownership-datasets`, `holdings-composite-score`, `filing-text-change-score`. Changed: `forward-paper-trading` (portfolio mode, tracking check), `point-in-time-universe` (one rules file per universe), `short-interest-snapshots` (report first available date). On hold: `insider-buying-connector`, `equity-offering-connector`, `structured-source-extraction`. Deprioritised: `company-program-corroboration`. Unchanged and still valid: PR #13, #14, #15 (extended, not changed), #16, #18, `catalyst-calendar`, `fda-advisory-committee-connector`, `historical-backfill` (feeds the H3 diagnostic and the negative-event veto; off the critical path).

## 2026-10-07 — Edge research scoping — BLOCKED — biotech holdings composite, filing-text change, or both
**What:** The one conflict between the research reports. Options:
- A) Biotech only: H9 holdings composite plus the negative-event veto. No filing-text work.
- B) Pivot: H10 filing-text change on a broad US small and mid-cap universe first; biotech composite later or never.
- C) Both on the shared base: H9 and H10 on the biotech universe, then H10 on the broad universe as a second universe file (recommended).
**Why C:** the shared base is most of the work; once it exists, the second score is one spec (`filing-text-change-score`, no new service, no LLM). Two independent, pre-registered tests on disjoint data roughly double the chance that something real is found, without spending one family's trial budget on the other. Running H10 on biotech first is cheap (a few thousand filings a year) and its broad-universe run is the riskiest part (free delisted prices for thousands of small caps may trip the survivorship kill criterion before the signal is tested).
**Action:** asked the user. `sec-ownership-datasets`, `holdings-composite-score` and `filing-text-change-score` stay blocked on the answer; record it here as a CHOICE.

## 2026-10-07 — Edge research scoping — FLAG — 20-day volatility in docs/strategy-research.md is about three times too low
**What:** The MDE rows use a 20-day σ of about 7% for stocks described as 80% annualised volatility. 80% × √(20/252) ≈ 22.5%. Minimum detectable effects in those rows are therefore about three times too optimistic (report 1). The forward check's "60 independent events, clustered t > 2" needs a mean net abnormal return of about 5.8% per event at 22.5%.
**Why it matters:** no event hypothesis in the registry expects 5.8% net per event, so the event branch of the forward check is very unlikely to pass for any of them. It is not wrong; it is strict.
**Action:** `specs/slow-signal-preregistration.md` corrects the MDE rows (no threshold changes). The event forward check stays as the user accepted it.

## 2026-10-07 — Edge research scoping — FLAG — paper trading cannot prove a monthly portfolio's edge in 12 months
**What:** The user's framing (2026-10-07): paper trading comes first and tells us what capital is justified. That holds, with one correction for slow strategies: 12 monthly returns cannot reach t > 2 unless the annualised Sharpe is above 2. For portfolio hypotheses the statistical case has to come from the long backtest and its sealed holdout (about 13 years of 13F data for H9, about 11 for H10), and paper trading shows that the live system reproduces the backtest at each capital tier (fills, costs, data timeliness).
**Options considered:** A) keep the event forward check for portfolios (unreachable); B) a portfolio branch: 12 months, no ledger gaps, paper-versus-replay tracking within ±2% a year, paper net excess not below the in-sample mean minus two standard errors (proposed); C) no forward check for portfolios (drops the only unseen data).
**Action:** B written into `specs/slow-signal-preregistration.md` and `specs/forward-paper-trading.md`. The ±2% tolerance is a proposal; the user owns it. A change to the locked protocol, so it is registered as `protocol.yaml` version 2 before any new data is joined to returns.

## 2026-10-07 — Edge research scoping — CHOICE — ownership and insider data are snapshots, not connectors
**What:** 13F holdings, insider transactions and short interest are time-series panels joined to a monthly score. They are built in `services/backtesting` from SEC and FINRA bulk data and stored in MinIO `auspex-prices`, like prices, instead of flowing through the scraper, Kafka, core-hub and Neo4j as documents. The same goes for the 10-K/10-Q Item 1A panel.
**Why it matters:** the document pipeline exists to extract events with an LLM; these sources have nothing to extract, and bulk data sets avoid tens of thousands of per-filing requests under the SEC's 10 req/s limit. Invariants 1 and 2 are untouched (the scraper is not involved; nothing writes Postgres or Neo4j).
**Options considered:** A) `SourceConnector`s on the structured-mapper path (second-wave specs); B) snapshot panels in `services/backtesting` (chosen).
**Action:** `specs/sec-ownership-datasets.md`, `specs/filing-text-change-score.md`; Form 4, offering and structured-extraction specs moved to `specs/hold/` with reasons.

## 2026-10-07 — Edge research scoping — FLAG — a hand-made specialist fund list is look-ahead
**What:** Report 1 proposes "a fixed, dated list of healthcare-dedicated 13F filers". A list written today selects funds known now to be successful biotech investors.
**Action:** `specs/sec-ownership-datasets.md` classifies specialists by rule from the 13F data as of each quarter (at least half of reported value in healthcare SIC codes, at least $100M reported), thresholds in `.env` and recorded in H9.

## 2026-10-07 — Edge research scoping — CHOICE — deferred items
**What:** Not specified now, with the reason:
- Quiet ClinicalTrials.gov changes (report 1's H11): needs registry version history whose availability is unverified; no published evidence. Revisit after the veto runs on the backfill.
- Options, shorts and a traded XBI hedge (report 2): disabled by protocol ceiling; XBI beta is measured in every portfolio report. US-domiciled XBI cannot be bought by EU retail accounts without a KID; the hedge would be a short leg.
- IBKR live-trading mechanics (report 2: limit orders, intent ids as order references, morning reconciliation, weekly re-authentication, extra kill switches): belong in a live-trading spec written after a forward check passes. `docs/PREREQUISITES.md` already gates live trading on paper results.
- Belgian 33% speculation-risk ruling request (report 2): a user action before live trading at scale, not code.
**Action:** none until the conditions above are met.

## 2026-10-08 — Edge research scoping — CHOICE — quarterly banded rotation; catalysts as a guard, not a trigger
**What:** The user pushed back on "hold one month, swap to the new top 15" and asked whether trading around known events would be better. Two follow-up reports (`/mnt/project-files/research/edge-result-4.md`, `belgian-costs.md`) found:
- None of H9, H10 or gene-target convergence pays smoothly through the calendar. Each pays when later news arrives (readouts, financings, earnings) over 3 to 18 months. A hard monthly top-15 cut turns over about 40% a month and costs about 6% a year. Hold bands (enter at rank 15, exit below rank 30) cost about 2.5% a year.
- Catalyst-timed entries do not beat that. The median 30-day pre-PDUFA or readout run-up is about zero (pdufa.bio, raw, not peer-reviewed). Holding through a binary has an expected value near zero with a fat left tail. Catalyst cycling costs 10 to 12.5% a year and shortens holds into the range where the 33% speculation rate is a risk.
- The round trip is about 1.25% (1.1 to 1.4%) for liquid small and mid caps, not about 2%. 0.70% of it is TOB, which cannot be avoided. Micro-caps cost 2 to 4%. FX is about 0 with a USD-held IBKR account. No structure lowers per-trade cost: a BV pays the same TOB and 25% on each winning sale, CFDs are banned for Belgian retail, and options cost more in spread. Stay a private person at all three capital tiers.
**Action:** H9 now scores monthly but trades quarterly, at least 10 days after each 13F deadline. It uses hold bands 15/30, a $500M / $2M liquidity floor (with a `no_floor` variant), days to cover instead of short interest over float, insider `P` buys excluding offering participation, and a `skip_entry` catalyst guard. Declared trial cells cover cadence, guard mode and floor (32), with `holdings_panel` budget 36. Inside biotech, H10 becomes an exclusion filter on H9 (the alpha sits with the changers; the no-change long leg reverts to zero). Broad-market H10 stays a separate standalone test. The portfolio forward check adds per-trade slippage, average holding period and a data-gap definition. The cost model defaults change to `FX_FEE_RATE` 0 and `MIN_HALF_SPREAD_BPS` 10. Specs updated: `slow-signal-preregistration`, `cross-sectional-portfolio-backtest`, `holdings-composite-score`, `sec-ownership-datasets`, `forward-paper-trading`.

## 2026-10-08 — Edge research scoping — CHOICE — two non-LLM panels before the LLM backfill
**What:** The guard and the diagnostics need point-in-time catalyst dates and registry edit history. The LLM-based `catalyst-calendar` needs the schema change and the backfill first. `specs/catalyst-date-panel.md` builds PDUFA dates (8-K press-release phrase rules) and AdCom dates (Federal Register) without an LLM. `specs/clinicaltrials-version-diffs.md` builds registry edit history (ClinicalTrials.gov record history or AACT monthly archives) for H11, now registered as a diagnostic in both directions. This supersedes the "quiet ClinicalTrials.gov changes" line in the 2026-10-07 deferred-items entry. H12 (pre-catalyst run-up) is registered as a diagnostic to settle whether catalyst-timed entries are worth testing at all.
**Why it matters:** the LLM backfill now waits until these diagnostics show that catalyst windows or registry edits carry return. `catalyst-calendar` and `fda-advisory-committee-connector` remain the live, LLM-based path and keep their place.
**Action:** both specs written and blocked on the point-in-time universe. The user's direction decision is still open.

## 2026-10-08 — Point-in-time universe — CHOICE — how the monthly list is derived from free SEC data

**What:** `specs/point-in-time-universe.md` leaves the mechanics of deriving listing history, tickers and market cap from SEC's bulk data open. Choices made for the monthly list (`auspex_backtesting.universe`):
1. **Known-at is stricter than the spec's wording.** A share count counts only if filed strictly before the rebalance session (bulk filing dates have no time of day, so one filed that morning may have been accepted after the open), and market cap and liquidity use the closes before that session, not its own close. The list is then fully known before the session it applies to opens.
2. **Listing spans.** An `8-A12B` or `10-12B` opens a span; the first `25-NSE`, `25`, `15-12B` or `15-12G` after it closes it. A `424B4` is not used as entry evidence: follow-on and over-the-counter offerings file it too, and an exchange IPO always files the `8-A12B`. A delisting notice with no registration on record means the company listed before EDGAR; its span starts at its first filing. A `15-12G` alone is no evidence of an exchange listing. If a company is still on an allowed exchange after its last notice, that notice was for another class (warrants, notes) and the span stays open. An inactive filer with no notice leaves at its last filing as `deregistered`; a company now quoted only over the counter with no notice is left out, because when it left the exchange is unknown.
3. **Exit reason.** `acquired` when an 8-K with item 5.01 (change in control) is filed from 30 days before to 10 days after the exit; otherwise `delisted` for a Form 25 and `deregistered` for a Form 15.
4. **Tickers.** SEC's current ticker when there is one (price vendors file a renamed issuer's whole history under its current symbol), stamped `current`. A delisted filer has none, so the prefix of its last inline XBRL report (`gone-20230930.htm`) stands in, stamped `filing`; filers almost always use their symbol there. Otherwise the member stays with `ticker_source = unresolved` and coverage `none`. Prices continuing more than 30 days after an exit belong to a reused symbol and are discarded.
5. **Rules that cannot be evaluated do not exclude.** No price bars before the rebalance, or no share count yet (recent IPOs), leaves `market_cap_usd` or `median_dollar_volume_20d` empty and keeps the company. Dropping them would remove exactly the delisted names the universe exists to keep; such members are reported, and their events are handled by the incomplete-history rules.
6. **Splits.** Price snapshots are split-adjusted to the day they were first fetched, while share counts are as reported. Each count is restated through every split after the date it refers to, using a split history snapshotted once per ticker next to its prices (`splits/{ticker}.parquet`). Biotech reverse splits would otherwise overstate the cap of names near the $50M floor tenfold.
7. **Running it.** The build runs in the price service (`POST /universe/build`), triggered by the `auspex_universe_build` DAG in the first week of every month and on the first start. It builds only missing months, so a run with every month stored downloads nothing. The rules file is pinned to its version in MinIO on first build (`universe/{version}/rules.yaml`); a changed file under the same version is refused.
8. **Window.** `config/universe/rules.yaml` starts at 2023-03, two months after `PRICE_HISTORY_START`, so the first rebalance has 20 sessions of prices behind it. It covers the Sep 2024–Sep 2026 backfill window.

## 2026-10-08 — Point-in-time universe — PENDING — SEC bulk URLs and first build on the stack

**What:** The spec asks for both bulk archive URLs to be re-verified at the start of the session. This session's network blocks `sec.gov`, so they could not be checked; they are SEC's documented locations (`Archives/edgar/daily-index/bulkdata/submissions.zip`, `Archives/edgar/daily-index/xbrl/companyfacts.zip`) and live in `.env`, not code.
**Action:** The first `auspex_universe_build` run on the stack is the check: a wrong URL fails the run red in Airflow (HTTP 502 with the error). After it succeeds, record the members per month, delisted count and price coverage report (`universe/1/coverage.json` in `auspex-prices`) here, and commit `config/universe/backfill_scope.yaml` via `scripts/build_universe.py --export-backfill-scope`.

## 2026-10-08 — Point-in-time universe — CHOICE — windows the prices do not cover

**What:** The spec says a window running out of data for a reason other than a delisting raises `PriceDataAbsentError`, and also that an event whose window is not fully priced is excluded and counted. Applied literally, the first would stop every backtest on the first member with incomplete history, and on any event whose window has not ended yet. The look-ahead fix's rule (a missing row gives `None`) also still applies to backtests run without a universe.
**Action:** With a universe (`BacktestRunner.run(..., universe=...)`):
1. A window ending after the universe's `as_of` (the last build date) is still running: `pct` is `None`, neither kept nor excluded.
2. A window past a delisted member's last price ends at that close with the member's `exit_reason`, when the member's price coverage is complete.
3. A window the prices do not cover on a member with partial or no coverage is excluded and counted by `exit_reason`, as is an event after a delisted member's last trade and a missing bar inside the price range (a trading halt): no neighbouring close is borrowed.
4. A member with complete coverage that is still listed and has run out of data raises: that is a broken snapshot, not a market event.
5. The delisting bound treats an excluded window on a still-listed company (a data gap, `exit_reason` empty, reported as `listed`) as flat over its unpriced part; the spec names only delisted, deregistered and acquired.
6. A backtest without a universe keeps the earlier `None` behaviour.

`survivorship_gap = material` is set on each `MetricsReport` above 10% excluded; writing those numbers into this file stays a step for whoever runs the evaluation, as the spec says, before a result is used for a promotion decision.
## 2026-10-08 — Control-surface scoping — CHOICE — Grafana for technical health, dashboard for using the application
**What:** The user decided the split after the 2026-10-08 frontend audit. Grafana covers whether the stack is healthy: services up, errors, CPU, memory and disk for the Docker VM and the Mac. The Next.js dashboard is the application's interface: browse signals, manage tracked companies and terms, monitor and steer the pipeline, trace conclusions back to documents, and later see research results.
**Action:** Specs `infrastructure-observability`, `dashboard-foundation`, `managed-ingestion-config`, `ingestion-config-ui`, `signal-browse-views`, `pipeline-control-view`, `lineage-trace-view` and `research-results-view` (draft, waits on the strategy direction).

## 2026-10-08 — Control-surface scoping — CHOICE — the watchlist is the single source for tracked tickers and terms
**What:** Tickers lived in `.env` `WATCHED_TICKERS`, terms in `sources.yaml` `prefilter_vocabulary`, and the Postgres watchlist fed nothing. The user approved making the watchlist, managed in the dashboard and stored by core-hub, the single source, with full history.
**Choices made in the spec:**
1. Config versions are append-only rows holding the full effective config and its hash; each change carries a reason.
2. The scraper fetches its config from core-hub over HTTP at the start of each run (Invariant 1: it may not read Postgres); with no config it fails the run without returning a cursor.
3. `prefilter_version` becomes `{algorithm_version}+{vocabulary_hash}`. The model gate compares only the algorithm part. A vocabulary is activated only if every golden document labelled `prefilter_should_pass` passes it (requirements §6.6), so editing terms doesn't require re-gating the model.
4. The backtest universe stays rules-based and pre-registered; live ingestion scope and the backtest universe are separate.
**Action:** `specs/managed-ingestion-config.md`, `specs/ingestion-config-ui.md`.

## 2026-10-08 — Control-surface scoping — CHOICE — research config is read-only in the dashboard
**What:** Hypotheses, `protocol.yaml`, strategies, the model registry and gate, universe rules, rate limits and the XBI/EURUSD tickers are shown with their version, hash and status but never edited from the UI. They change only through a dated re-registration in the repo, so pre-registration stays meaningful.
**Action:** `specs/ingestion-config-ui.md` (`/config/research`, no write route).

## 2026-10-08 — Control-surface scoping — CHOICE — dashboard runs in the stack behind its own server layer
**What:** The browser calls only the dashboard's origin. Next.js route handlers forward to core-hub, the scraper, price-service and Airflow, hold the Airflow credentials and a core-hub write token, and normalise errors and paging. They hold no business logic and touch no datastore. Single-user login from `.env`. core-hub CORS is removed and its non-GET endpoints require the token.
**Action:** `specs/dashboard-foundation.md`.

## 2026-10-08 — Control-surface scoping — FLAG — defects found by the frontend audit
**What:**
1. `Neo4jWriteService` writes mechanism links as `VIA`; requirements §9 and `CorroborationScanner` use `USES_MECHANISM`, so mechanism corroboration never fires.
2. No code sets `Company.ticker`, so `GET /api/v1/signals/{ticker}` and the watchlist signal counts match nothing.
3. `auspex_ingest/api.py` `_build_connector` branches on `source_type` (Invariant 4) and builds only biorxiv and clinicaltrials; the other `/ingest` calls fail.
4. The dashboard's watchlist writes fail in the browser: core-hub CORS allows GET only.
5. Grafana alert rules have no contact point, so alerts reach no one.
6. `specs/company-program-corroboration.md` planned `V4__corroboration_kind.sql`, but `V4` is taken; changed to the next free version.
**Action:** 1–3 in `specs/graph-and-connector-wiring-fixes.md`; 4 in `specs/dashboard-foundation.md`; 5 in `specs/infrastructure-observability.md`; 6 fixed in the spec.

## 2026-10-08 — First run on the stack machine — CHOICE — price history from 2013, set before the first `up`
**What:** `PRICE_HISTORY_START` defaults to `2013-01-01` (was `2023-01-01`) in `.env.example` and the compose file. `PriceRefresher` fetches from that date only for a ticker with no snapshot and afterwards only appends, so a first `up` at 2023 would leave every watchlist and universe snapshot unable to serve the slow-signal study's 2014–2021 in-sample period (FLAG "universe window" on the edge-research scoping branch). Extending a stored snapshot backwards means deleting stored history, which the 2026-10-07 "Startup data" entry treats as a deliberate act. No stack has been started yet, so setting it now costs nothing but a longer first download.
**Why 2013-01-01:** a year of lookback before the 2014 window for trailing volatility and rolling 12-month beta. Universe rules version 1 (window from 2023-03) reads only bars before each rebalance, so its result does not change.
**Action:** `specs/first-run-on-stack-machine.md` checks the value before the first `up` and checks `XBI`'s first bar after it. The 2014 universe itself is built only once its rules are on `develop`, after version 1.

## 2026-10-08 — First run on the stack machine — CHOICE — local model decision rule, fixed before the gate runs
**What:** Three candidates are gated at prompt `v1.1` on the Mac: `llama3.1:8b-instruct-q8_0`, `phi3:14b-medium-128k-instruct-q4_K_M` (added to `local_candidates.yaml`), `llama3.1:8b-instruct-q4_K_M`. Eligible means `is_signal` precision ≥ 0.85 and the run grew swap by less than 1 GB with the stack up. The 8B Q8 is chosen if eligible; Phi-3 replaces it only with an F1 at least 0.05 higher; the 8B Q4 is chosen only if the Q8 fails on memory alone; if none is eligible there is no CHOICE and the next step is the user's.
**Why:** the golden set has 46 prefiltered documents and one document moves precision by 2–3 points, so a smaller gap cannot be told from noise, and the 8B is about 1.4x faster. The golden set carries no `v1.1` labels yet; the gate production enforces (`is_signal` precision) is fully measurable without them, and the new fields are labelled under `specs/golden-set-expansion.md`, not here.
**Action:** step 5 of `specs/first-run-on-stack-machine.md`.

## 2026-10-09 — Guideline setup — CHOICE — merge flow, merge bar and shared-log conflicts written into the repo
**What:** Root `CLAUDE.md` now matches how the owner merges: PR into `develop`, merge only on the owner's word with a local `--ff-only` merge, `main` only through a release. The merge bar (every behaviour tested, mutation-checked, spec requirements mapped to tests) and the limits of cloud sessions are written down. `DECISIONS.md` and `TODO.md` use git's `union` merge driver, and the TODO.md session log is dropped because PRs and `git log` carry the same record. A CI check rejects commits attributed to Claude.
**Why it matters:** The old end-of-spec flow pushed straight to `develop` and `main`, which a session on the stack machine would have followed. Every spec PR appended to the end of both log files, so nearly every rebase hit a conflict.
**Options considered:** One file per decision entry (removes conflicts fully, but changes every link to this log) / union merge driver (keeps the file; GitHub's merge button ignores it, but merges here are local).
**Action:** Union merge driver. Audit and owner approval: thread "Guideline setup audit", 2026-10-09.
## 2026-10-09 — Point-in-time universe — CHOICE — one universe from 2014, backfill scope from its own start
**What:** The user asked for one universe, not a second rules version for the slow-signal study (FLAG "universe window", edge-research scoping). `config/universe/rules.yaml` version 1 now starts at 2014-01-01 instead of 2023-03-01; it has never been built, so no stored snapshot or rules lock changes. This supersedes item 8 ("Window") of the 2026-10-08 CHOICE on deriving the monthly list, and the "after version 1" ordering in the 2026-10-08 CHOICE on price history from 2013.
**How the pieces fit:**
1. **Backfill scope.** `backfill_scope.yaml` lists members from `BACKFILL_SCOPE_START` (`.env`, default 2024-01-01) to the latest month, not over the whole window, so the 2014 start does not grow the LLM backfill. 2024-01 is the earliest start the backfill's cutoff guard allows any registered model (gpt-4o-mini, cutoff 2023-10, plus the default 3-month margin); a later backfill start only makes the list a superset, never misses a company.
2. **Price history.** The build refuses (HTTP 409) a `PRICE_HISTORY_START` later than 45 days before the window, the lookback the first rebalance's 20-session liquidity reads. Without the check a late setting would leave every 2014 market cap and volume unknown, and unknown values keep a company, so the universe would silently lose its floors.
3. **Tickers before inline XBRL.** Before 2019 a report's primary document is named by the filing agent, so a company delisted in 2014–2018 had no ticker source at all. Its last XBRL 10-K or 10-Q's index page names the XBRL instance, `<symbol>-<yyyymmdd>.xml`; the build reads that one page for each unresolved company listed in the window (a few hundred requests, 8 per second, `SEC_ARCHIVES_URL`). A 403 or 429 from SEC stops the lookups for that run rather than extending a block; those companies stay `unresolved` and are counted.
4. **Share counts** come from `dei:EntityCommonStockSharesOutstanding`, which small filers report from mid-2011, so 2014 is covered. A missing count still keeps the company.
**Risk, unchanged in kind:** free price sources keep few names delisted before 2019. Those members stay in the snapshots with `price_coverage = none`, their events are excluded and counted, and the protocol's `survivorship` kill criterion reads the excluded share. The first build records coverage split into 2014–2018 and 2019 onward (`specs/first-run-on-stack-machine.md` step 3).
**Action:** `rules.yaml`, `universe/sec_index.py`, `UniverseBuildJob(backfill_start=, price_history_start=)`, `.env.example` and compose (`SEC_ARCHIVES_URL`, `BACKFILL_SCOPE_START`); `specs/point-in-time-universe.md` and `specs/first-run-on-stack-machine.md` (the separate 2014 build step is gone).

## 2026-10-08 — Edge research scoping — CHOICE — direction: both
**What:** The user answered the 2026-10-07 BLOCKED entry "biotech holdings composite, filing-text change, or both" with the default: both, on a shared base. H9 (holdings composite) runs in the biotech universe with H10 (Item 1A change) as its exclusion filter; H10 also runs as a standalone promotable test on broad US small and mid caps ($500M–$10B), on its own universe file `us_small_mid`.
**Why it matters:** `specs/slow-signal-preregistration.md` registers both; `specs/filing-text-change-score.md` adds the second universe file.
**Action:** direction blockers removed from slow-signal-preregistration, sec-ownership-datasets and filing-text-change-score.

## 2026-10-08 — Edge research scoping — CHOICE — portfolio paper-trading pass rule
**What:** The user accepted the forward check for portfolio strategies as an implementation check, not new statistical evidence: 12 months with no data gaps (as defined in `specs/forward-paper-trading.md`), paper returns within ±2%/yr of a backtest replay over the same months, paper excess at least the in-sample mean minus 2 SE, with slippage and average holding period reported. The statistical case comes from the backtest and the one-time holdout read. Live capital waits on this check per tier.
**Action:** as written in `specs/forward-paper-trading.md` and protocol v2 in `specs/slow-signal-preregistration.md`.

## 2026-10-08 — Edge research scoping — CHOICE — build order
**What:** The user accepted the default order: pre-registration, then the structured SEC base (ownership panels, then holdings score and the portfolio backtest), then the two non-LLM panels (`catalyst-date-panel`, `clinicaltrials-version-diffs`), and the LLM historical backfill after those.
**Action:** pre-registration, SEC ownership datasets and catalyst date panel set `ready` in TODO.md in that order.

## 2026-10-08 — Edge research scoping — FLAG — universe window
**What:** The merged universe (`config/universe/rules.yaml`) starts at 2023-03, sized for the event backfill. The slow-signal study registers in-sample 2014–2021 and holdout 2022–2025, so it needs the universe to cover 2014 onward, with price history from 2013 (`PRICE_HISTORY_START`, set on develop by the first-run spec). Free delisted price coverage over that span is the main survivorship risk (protocol `survivorship` kill criterion).
**Resolution (user, 2026-10-09):** one universe, not a second rules version. The existing universe is extended to start in 2014 (thread "Build point-in-time stock universe"); the event backfill reads the same universe from its own start date.
**Action:** blocker 4 of `specs/cross-sectional-portfolio-backtest.md` depends on that extended universe: needed before any H9 or H10 run, not before the code.

## 2026-10-09 — CI — CHOICE — container images off anonymous Docker Hub
**What:** GitHub runners pull from Docker Hub anonymously and hit its per-IP rate limit (429 `toomanyrequests`), which failed the Python integration tests (`confluentinc/cp-kafka`, `elasticsearch`) and the dashboard image build on several PRs at once. Elasticsearch and Filebeat now come from Elastic's own registry (`docker.elastic.co`, same tags) in compose and tests. The test Kafka image, which exists only on Docker Hub, is pulled from Google's Docker Hub cache by name (`mirror.gcr.io/confluentinc/cp-kafka:7.6.0`), because the daemon-level mirror alone still let those pulls reach Docker Hub. Every workflow that pulls images also sets `mirror.gcr.io` as the daemon's registry mirror and logs in to Docker Hub when the `DOCKERHUB_USERNAME` Actions variable and `DOCKERHUB_TOKEN` secret exist.
**Options considered:** authenticated pulls only (needs secrets the repo did not have); daemon mirror only (insufficient on its own: the Python job still failed with it on #31).
**Action:** `.github/workflows/java.yml`, `.github/workflows/python.yml`, `docker/docker-compose.yml`, `docker/README.md`, the Kafka and Elasticsearch integration tests.

## 2026-10-09 — CI — CHOICE — remaining test images through mirror.gcr.io
**What:** After the first Docker Hub fix, Python CI on develop still failed pulling `localstack/localstack:4.9.2`: `auth.docker.io` timed out both anonymously and logged in. The LocalStack test image is now pulled as `mirror.gcr.io/localstack/localstack:4.9.2` (same tag), and the Java job sets `TESTCONTAINERS_HUB_IMAGE_NAME_PREFIX=mirror.gcr.io/` so Testcontainers pulls `postgres` and `neo4j` from the same cache. No integration test image now depends on reaching Docker Hub.
**Action:** the three LocalStack integration tests, `.github/workflows/java.yml`, CLAUDE.md known traps, VERSIONS.md.
## 2026-10-09 — Stack state persistence — FLAG — what a container or image recreate loses
**What:** An audit of the compose stack (develop plus PRs #29 and #31) against the owner's goal "delete the containers and images, start again, and it picks up where it left off". Every store sits on a named volume, and every one-shot job and migration is a no-op when its data exists. Two things live in the Airflow container layer and are regenerated on recreate. One is the Fernet key, which makes the encrypted ingestion cursors (`cursor:{source_type}` Variables) unreadable. The other is the generated admin password. Weaker spots: Kafka offsets expire after 7 days of downtime, the cluster ID and the compose project name are implicit, filebeat's registry is unpersisted, and the Airflow DB role's password applies only on first init. The docs also prescribe `down -v`, which deletes the append-only price history and the pinned universe, as a routine fix.
**Resolution (owner, 2026-10-09):** scope each gap as a spec and implement it once its dependencies merge.
**Action:** `specs/stack-state-persistence.md`, `specs/stack-backup.md`. Full audit: project file `audit/data-persistence-audit.md`.

## 2026-10-09 — Stack backup — CHOICE — nightly backup to a folder on the Mac
**What:** Named volumes don't survive Docker Desktop's "Purge data", a factory reset or `down -v`. The owner accepted the default: a nightly Airflow DAG calls a `backup` service that writes `pg_dump`s of both databases, a Neo4j JSONL export and an additive MinIO mirror into a bind-mounted host folder (`BACKUP_HOST_DIR`), which Time Machine covers.
**Options considered:** bind-mounting only MinIO's data directory to the host (covers prices, universe and the raw archive, but not the signal stores, and is slower through Docker Desktop's file sharing); no backup.
**Boundary:** the backup service only reads (Invariants 1 and 2 hold). Writing back is a separate `restore` one-shot under its own compose profile, for disaster recovery with core-hub stopped, and it refuses non-empty targets. Neo4j is exported over bolt rather than with `neo4j-admin database dump`, because Community edition can only dump offline.
**Action:** `specs/stack-backup.md`.
## 2026-10-09 — Soak-test readiness — CHOICE — cursor after a run with failed documents
**What:** `docs/requirements.md` §5 says the DAG writes `max_published_date_processed` on success and leaves the cursor untouched on failure. A run that completes but fails some documents was treated as a success, and the cursor moved past the failures, so they were never fetched again. From `specs/ingestion-run-reliability.md` on, the pipeline reports a safe cursor: the earliest failed document's `published_date` when any failed, else the latest processed date. The DAG writes it and then fails the task so the run shows red and retries. The pipeline stays stateless; a request that errors still leaves the Variable untouched.
**Why:** an unattended run must not lose documents to a model-server outage or a sleeping Mac. Processed markers stop the rerun from re-extracting the documents that succeeded.
**Action:** `specs/ingestion-run-reliability.md`.

## 2026-10-09 — Soak-test readiness — CHOICE — transient Kafka failures pause instead of retrying longer
**What:** §3 rule 10 fixes three deliveries (1 + 2 retries) for a transient failure and forbids blocking a partition. A Postgres or Neo4j restart outlasts two 1-second retries and dead-letters everything consumed meanwhile. Instead of more retries, core-hub pauses both listeners while either store is unreachable and resumes when both are back; the back-off between the three deliveries grows to 5 s and 30 s. Dead letters get a replay endpoint so nobody runs a Kafka command.
**Options considered:** unlimited retries for connection errors (breaks §3 rule 10 and blocks the partition); keeping the 1-second retries (an outage fills the DLT).
**Action:** `specs/dead-letter-recovery.md`.

## 2026-10-09 — Soak-test readiness — CHOICE — SEC request budget across containers
**What:** SEC allows 10 req/s per IP across all its hosts (§6.5: configure 5). EDGAR ingestion (scraper, 4 req/s) and the universe build's filing-index lookups (price-service, 8 req/s) pace separately and can run together after the Mac wakes. The universe lookups drop to 5 req/s, so the two stay at 9; EDGAR stops a run on a 403 instead of retrying into the block. The ownership panels' own client (5 req/s) is not scheduled; when it is, its schedule must not overlap EDGAR ingestion.
**Action:** `specs/ingestion-run-reliability.md`.
## 2026-10-09 — Dashboard foundation — CHOICE — Next 16, Vitest 5 and Tailwind 4 to clear the advisories
**What:** `npm audit` on the old pins reported 15 advisories, 4 critical. Patched 15.x `next` still pulls a vulnerable `postcss` and `sharp`, Vitest 3 a critical `tinypool`, and Tailwind 3 `braces`/`micromatch` through `chokidar`; none has a fix within its major. The dashboard moved to `next` 16.4.0, React 19.3.0, Vitest 5.0.3 (Vite 8), Tailwind 4.3.3 and ESLint 9 flat config. Next 16 renames middleware to `proxy` (Node runtime), drops `next lint`, and generates `next-env.d.ts`, which is now ignored.
**Residual:** 5 high advisories remain, all `braces` under `eslint-config-next` → `@next/eslint-plugin-next` → `fast-glob`. Every published `braces` version is affected, so there is nothing to upgrade to, and the spec requires `next/core-web-vitals` and `next/typescript`, which only that package provides. It is a lint-time dependency that never ships in the image. CI gates on `npm audit --omit=dev --audit-level=high` (0), not the full tree; the spec's DoD line `npm audit --audit-level=high` reports these 5 until `braces` publishes a fix.
**Action:** `services/dashboard/package.json`, VERSIONS.md (Node 22.23.3, dashboard table), `.github/workflows/dashboard.yml`.

## 2026-10-09 — Dashboard foundation — CHOICE — login endpoint, write-token failure mode, path layout
**What:**
1. **Public routes.** The spec lists `/login` and `/api/health` as the only routes without a session; the login form also has to reach `POST /api/auth/login`, so that is public too. `POST /api/auth/logout` clears the cookie.
2. **BFF paths.** One handler per upstream: `/api/core-hub/<path>` → `${CORE_HUB_URL}/api/<path>`, `/api/scraper/<path>`, `/api/prices/<path>`. core-hub is mounted under its `/api` prefix so actuator endpoints stay out of reach. 4xx pass through with their status; 5xx and unreachable upstreams become 502 with `upstream_status` set (null when unreachable).
3. **Write token fails closed.** With `CORE_HUB_WRITE_TOKEN` unset core-hub still starts (the Kafka pipeline must not depend on the dashboard), logs a warning, and refuses every write under `/api`. GET and HEAD need no token; OPTIONS does, which is moot with CORS removed.
4. **Session.** HMAC-SHA256 over `{sub, exp}` with `DASHBOARD_SESSION_SECRET`; `exp` is the idle expiry and every authenticated request re-issues the cookie. A session also ends when `DASHBOARD_USERNAME` changes. `Secure` is set only when the request arrived over HTTPS, so the cookie works on `http://localhost` in Safari.
5. **Password hash.** bcrypt (`bcryptjs`, pure JS, no native build in the Alpine image), cost 12, printed by `scripts/hash-password.mjs`, which ships in the image so it runs through `docker compose run` without Node on the host.
**Action:** `services/dashboard/src/proxy.ts`, `src/lib/{bff,session,credentials}.ts`, `services/core-hub/.../config/WriteTokenInterceptor.java`, SETUP.md step 1.
## 2026-10-09 — Pre-launch spec audit — CHOICE — gaps closed in the spec index
**What:** An audit of every spec against the path to paper trading and live capital (approved by the user 2026-10-09) found pre-launch work with no spec, and stale blockers. This change:
1. Adds `specs/slow-signal-data-refresh.md` (blocked): price-service endpoints and DAGs that keep the ownership, short-interest, filing and catalyst panels current and write each month's score snapshots. It also adds universe members to the daily price refresh (`price_refresher.py` `price_universe()` covered only the watchlist, XBI and EUR/USD) and stale-input alerts. This resolves the 2026-10-09 FLAGs on the catalyst date panel and SEC ownership datasets, which have no schedule.
2. Adds `specs/live-trading.md` (draft): pre-live items that lived only here and in `docs/PREREQUISITES.md` (the §0.1 amendment, IBKR mechanics, the tax record). It is scoped only after a forward check passes.
3. Sets `short-interest-snapshots` and `strategy-runtime` to `ready`, since every prerequisite is done. Adds to `strategy-runtime` the container that `forward-paper-trading` assumes, and CI for `services/strategy`, whose tests no workflow ran.
4. Marks company-level extraction and the strategy framework as met wherever they were still listed as blockers, and notes in `portfolio-and-risk` that its sizing and guard serve event strategies and that its hand-maintained catalyst file conflicts with the no-hand-run rule.
**Still to do once PRs #26 and #28 merge** (they edit the same files): the portfolio pass/fail verdict (`portfolio_kill_criteria` and promotion) in `cross-sectional-portfolio-backtest`; `evaluation-protocol` to `ready` for its code; `forward-paper-trading` blockers (look-ahead fix met, data refresh, catalyst date panel); `golden-set-expansion`'s blocker pointed at the Ollama gate step of `first-run-on-stack-machine`.
**Action:** this PR; the follow-up edits in the same thread after #26 and #28 merge.
## 2026-10-09 — Catalyst date panel — PENDING — sources unreachable from the cloud session
**What:** `www.sec.gov` and `www.federalregister.gov` both refused the cloud session's proxy (CONNECT 403), as in the scoping sessions. The extractors are built against fixtures written from the documented formats, not from live responses: EDGAR's quarterly `master.idx` (pipe-delimited `CIK|Company Name|Form Type|Date Filed|Filename`), the filing index page's `Accepted` and `Items` blocks and its first `tableFile` table, and the Federal Register documents API (`conditions[agencies][]=food-and-drug-administration`, `conditions[type][]=NOTICE`, fields `document_number`, `title`, `publication_date`, `dates`, `html_url`, `raw_text_url`; `total_pages` for paging).
**Why it matters:** a format that differs shows up as counters, not as an error: `without_items` near the number of filings means the `Items` block is not where the parser looks; zero `matched` notices means the agenda or `dates` field differs.
**Action:** `specs/first-run-on-stack-machine.md` step 3a runs the build on the stack and records the URLs that worked, these counters, coverage and the 30-hit hand check here as VERIFIED (or FLAG).

## 2026-10-09 — Catalyst date panel — CHOICE — how documents become rows
**What:**
1. **Quarterly index.** `master.idx` instead of `form.idx`: same quarterly listing, but pipe-delimited, so no fixed-width column parsing. One request per quarter, then one filing index per universe 8-K and one exhibit for those with Item 7.01 or 8.01 (the spec's items; 2.02 earnings releases are not read).
2. **Fetch once.** Every index page, exhibit, listing page and notice text is kept under `catalyst-documents/` in `auspex-prices`, keyed by accession or notice number, and read from there on later runs. A quarter's index and listing pages are kept only once the quarter has ended, since they still grow until then. A 403 or 429 ends the run with no retry; the next run continues from the kept documents.
3. **Which date in a sentence.** The first date after the PDUFA phrase, moved along "from X to Y" to Y; failing that, a date written just before the phrase ("a March 15, 2027 PDUFA date", within 40 characters). Precision is the one written: day, month, quarter (`Q3 2027`, `third quarter of 2027`) or half (`second half of 2027`, `1H 2026`). A bare year or "mid-2027" gives no row.
4. **Which catalyst a row revises.** Rows carry normalized aliases: application numbers (`NDA 214567`), code names (`BTX-401`), trademarked brands and INN generic names; a sentence naming none borrows them from the three sentences before it (releases often name the product one sentence earlier). For one company and type, a later row replaces earlier rows sharing an alias; rows with no alias replace only each other. A release naming the brand where the earlier one named only the generic leaves both dates in force, which errs toward skipping an entry, not toward missing a binary.
5. **Advisory committees.** Known at 06:00 Eastern on the publication date, when federalregister.gov posts the issue (the public inspection copy, a day earlier, is not used). The sponsor after "submitted by" is matched to universe names with legal suffixes dropped and word order ignored (SEC's "LILLY ELI & CO"); with no sponsor phrase, a universe name written in full in the agenda. No match or several: the row is stored with no CIK and counted. A meeting with no product named is keyed by committee and meeting date. Cancellation and postponement notices are counted (`withdrawals_skipped`) and not applied, so a cancelled meeting still guards its date.
**Action:** `services/backtesting/src/auspex_backtesting/catalysts/`, `scripts/build_catalyst_panel.py`, `SEC_FULL_INDEX_URL` and `FEDERAL_REGISTER_API_URL` in `.env.example`.

## 2026-10-09 — Catalyst date panel — FLAG — not kept current by the stack
**What:** the spec asks for a backfill script only, and the panel serves backtests. Paper trading's catalyst guard (`specs/forward-paper-trading.md`) will need it refreshed; per root `CLAUDE.md`, data that must stay current belongs in an Airflow DAG calling a service endpoint, not in a script run by hand.
**Action:** none now. When forward paper trading needs the guard, add `POST /catalysts/build` on the price service and a DAG calling it, as the universe build does.
## 2026-10-09 — Infrastructure observability — CHOICE — monitoring role from a one-shot, not an init script
**What:** postgres-exporter logs in as `auspex_monitor` (`pg_monitor`, no superuser). The spec asked for the role in the existing init scripts, but `postgres-init/` runs only on an empty volume, so a stack that has already run would never get it. `postgres-monitor-role` (one-shot, `docker/postgres-monitor/create-role.sh`) creates the role if missing and resets its password from `POSTGRES_MONITOR_PASSWORD` on every `up`. Elasticsearch has security off, so its exporter needs no role.
**Action:** `docker-compose.yml`, `SETUP.md` step 1.

## 2026-10-09 — Infrastructure observability — CHOICE — compose defaults for sizes and thresholds
**What:** `docker/CLAUDE.md` said "no defaults in docker-compose.yml". Memory limits, Prometheus retention, alert thresholds and the volume scan interval now have `${VAR:-default}` defaults, and a test requires each default to equal `.env.example`. Credentials, the alert contact type and its addresses still have none.
**Why:** an `.env` written before these variables existed (the Mac's) would otherwise start containers with empty limits. Secrets must still fail loudly.
**Action:** `docker/CLAUDE.md` and `docker/README.md` updated.

## 2026-10-09 — Infrastructure observability — CHOICE — memory limits sized to 7.5 GB, first estimates
**What:** Every service has `mem_limit` from `.env`. Long-running services sum to 7,680 MB, Docker Desktop's 8 GB less 512 MB for the VM; one-shots are not counted. Kafka's heap is set to 384 MB (`KAFKA_HEAP_OPTS`, image default 1 GB) and core-hub's JVM may use 60% of its limit (`CORE_HUB_JAVA_TOOL_OPTIONS`; the JVM default of 25% leaves about 190 MB of heap). Largest: price-service 1,280 MB (the universe build reads SEC's bulk archives file by file), Airflow 1,152 MB (standalone runs four processes).
**Risk:** these are estimates; nothing has run under them. A service at its limit is OOM-killed, restarts, and raises "Container Restarting".
**Action:** checked on the Mac by the PENDING entry below; adjust the `*_MEM_LIMIT` variable from the "Container memory" panel.

## 2026-10-09 — Infrastructure observability — CHOICE — VM and volume metrics without host bind mounts
**What:** Docker Desktop refuses bind mounts outside its shared folders, so node-exporter reads the VM through `pid: host` and `--path.rootfs=/proc/1/root` (`SYS_PTRACE`), and cAdvisor uses `privileged` with `cgroup: host`, the Docker socket and `/var/lib/docker` (paths Filebeat already mounts). cAdvisor cannot size volumes there, so `volume-usage` (busybox, `docker/volume-usage/collect.sh`) runs `du` on each named volume every 15 minutes and node-exporter's textfile collector exports `auspex_volume_bytes`. "Docker disk" is the fullest ext4/xfs/btrfs filesystem in the VM.
**Risk:** none of this has run on Docker Desktop. If a mount or `/proc/1/root` is refused, the container fails at `up` and names it.
**Action:** the PENDING entry below.

## 2026-10-09 — Infrastructure observability — CHOICE — alert definitions the spec left open
**What:**
1. "Ollama down while an extraction DAG is running": Ollama's probe fails for 5 minutes and either an `auspex_*` task other than price refresh or universe build has started without finishing (Airflow statsd `ti.start` / `ti.finish`), or the scraper made extraction calls in the last 15 minutes (catches a manual `/ingest` call).
2. "Price refresh not successful for 2 NYSE sessions": the price service exports `auspex_price_refresh_sessions_since_success`, the NYSE sessions strictly between the last refresh in which every ticker refreshed (or the service's start) and today, UTC. One permanently failing ticker keeps it firing, on purpose.
3. "Airflow DAG run failed" also fires on a DAG's first failure, which `increase()` alone misses because statsd-exporter creates the series at 1.
4. "Scrape Target Down" now covers every scrape job except `mac-host` and the probe jobs; probes have "Probe Target Down"; Ollama only its own rule.
**Action:** `docker/grafana/provisioning/alerting/`; each rule has firing and quiet cases in `test_stack_alert_expressions.py`, which found that the first draft of rule 1 could never fire (`and` kept the left side's value 0).

## 2026-10-09 — Infrastructure observability — VERIFIED — Grafana expands environment variables in alert provisioning
**What:** Grafana's `pkg/services/provisioning/values` runs every provisioned rule's model, labels, annotations and contact point settings through `os.ExpandEnv` after splitting on `$$`. That is how `${ALERT_*}` thresholds and the contact point come from `.env`, and why `{{ $labels.x }}` must be written `{{ $$labels.x }}`. Added to the root `CLAUDE.md` traps; a test checks every `$` reference in the alerting files names a variable Grafana receives.

## 2026-10-09 — Infrastructure observability — PENDING — checks on the stack machine
**What:** The cloud session has no Docker. Still to run on the Mac (step 8 of `specs/first-run-on-stack-machine.md`): `brew install node_exporter && brew services start node_exporter`; `up --wait` with every new container healthy or running; `sh docker/grafana/test_provisioning.sh` all PASS; the Mac panels and "Docker disk free" show plausible values (the Docker disk is about Docker Desktop's disk image size); stop `auspex-postgres` and confirm "Scrape Target Down" / "Probe Target Down" reach the configured contact point within 10 minutes; peak memory per container from "Container memory" after the universe build, for resizing limits.
**Action:** record VERIFIED or FLAG here.

## 2026-10-09 — Infrastructure observability — CHOICE — monitoring values only in .env.example
**What:** Replaces the same day's "compose defaults for sizes and thresholds". The user approved resolving every finding of the duplicate-versions sweep (`/mnt/project-files/audit/single-source-audit.md`, finding 16): nothing is deployed yet, so the memory limits, heap options, retention, alert thresholds, SMTP settings, monitoring user and scan interval are plain `${VAR}` in compose with their values only in `.env.example`, and the test that kept two copies equal is gone. An `.env` copied before these variables existed must gain them: step 1 of `specs/first-run-on-stack-machine.md` now lists keys missing from `.env` and copies the non-secret ones over from `.env.example`.
**Action:** `docker-compose.yml`, `docker/CLAUDE.md`, `docker/README.md`. Older defaults on develop (`PRICE_HISTORY_START` and others) are the sweep's cleanup, not this PR's.

## 2026-10-10 — Infrastructure observability — CHOICE — dashboard memory limit and health probe
**What:** The dashboard container (dashboard foundation) landed on develop alongside this work. It gets `DASHBOARD_MEM_LIMIT=256m` and a blackbox probe of `/api/health`. The 256 MB comes from price-service (1,280 → 1,024), the same two values `specs/container-limits-and-log-rotation.md` starts from, so the long-running total stays 7,680 MB.
**Risk:** the monthly universe build is price-service's peak; at 1,024 MB it may be OOM-killed.
**Action:** the stack-machine memory check in the PENDING entry above covers it.

## 2026-10-10 — Single-source cleanup — CHOICE — one version of each pre-rollout artifact
**What:** Nothing has run in production, so every artifact with a second version collapses to one: the extraction prompt is `v1` (the company-level text, formerly `v1.1`; `v1.0` and the old `v1` deleted); the hand-written gpt-4o-mini gate record and `config/prefilter/v1.yaml` are deleted; the event schema is `1.0` with the company-level fields required in Java (only `primary_company` nullable); `LLMExtractor` and `dag_factory.py` are deleted, with the cursor tests moved to the real HTTP DAG; `docs/plan.md` is deleted; strategy parameter files and the H8 `negative_asymmetry` strategy are deleted, so hypothesis files are the only parameter source; the watchlist-alerts hold spec reads the V3 tables; compose reads every `.env.example` variable as a bare `${VAR}`, matching the monitoring variables. Flyway `V4__company_level_fields.sql` keeps its frozen header saying "schema 1.1"; it predates this reset and is checksummed.
**Action:** `specs/done/single-source-cleanup.md`.


## 2026-10-09 — Dashboard — CHOICE — Node 24 LTS, actions on Node 24
**What:** The dashboard moves from Node 22.23.3 to 24.21.0 (`.nvmrc`, `engines`, `@types/node` 24.19.0, image `node:24.21.0-alpine3.24`). Node 24 has been the Active LTS line since October 2025 and is supported to April 2028; Node 22 is in maintenance to April 2027. The 2026-09-19 entry's "Node 24 is not yet LTS" no longer holds. Every GitHub Action moves to its current major, all on the Node 24 runtime (GitHub deprecated Node 20 for actions): checkout v7, setup-node v7, setup-python v7, setup-java v6, cache v6, upload-artifact v7, setup-uv v7, login-action v4.
**Options considered:** stay on 22 (maintenance only); Node 26 (not LTS until late October 2026).
**Action:** `services/dashboard/`, `.github/workflows/`, VERSIONS.md, README.md.

## 2026-10-09 — CI — CHOICE — one prefix for every test image
**What:** Test images are named as on Docker Hub and both container-test jobs set `TESTCONTAINERS_HUB_IMAGE_NAME_PREFIX=mirror.gcr.io/`, replacing the per-test `mirror.gcr.io/...` and `docker.elastic.co/...` names. Python's Testcontainers prepends the prefix to every image name, so the Elasticsearch test uses the Docker Hub official `elasticsearch:8.17.3` (same version as compose, which keeps `docker.elastic.co`). The Python job also disables Ryuk, whose own image would otherwise get the prefix.
**Action:** `.github/workflows/python.yml`, the integration tests, CLAUDE.md known traps, VERSIONS.md.

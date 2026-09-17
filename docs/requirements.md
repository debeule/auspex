# Auspex — Technical Requirements & Constraints

> **How to read this.** No code exists. This is a greenfield build, and this document plus `plan.md` are its entire input. Bracketed tags like `[A3]`, `[B1]`, `[P2-5]` are provenance markers from three rounds of adversarial review of this specification — they record *why* a non-obvious decision was made and do not reference anything ever implemented. Where a note calls a choice "intuitive and wrong," read it as a warning against a plausible mistake, not as a description of existing behaviour to be migrated away from.

---

## 0. Assumptions (unresolved questions — change these first if wrong)

| # | Question | Assumed answer | What changes if wrong |
|---|---|---|---|
| 0.1 | Live monitor or historical research instrument? | **Historical.** Pairwise corroboration window (§4). | If live-only, §4 simplifies and Phase 4 is impossible. |
| 0.2 | Where does cursor state live? | **Airflow Variables, read and written by the DAG task.** The pipeline is stateless (§5). | Step 2.1 tasks only. |
| 0.3 | Backfill depth | **A bounded 24-month historical backfill is a prerequisite for Phase 4**, run once per source as Step 4.0. Live polling is forward-only with a 90-day `initial_lookback`. `[P2-1]` | If forward-only, Phase 4 cannot run for roughly a year — see the note below. |
| 0.4 | LLM budget | **≤500 extractions/day steady-state**, plus a **separate one-time backfill budget** set in Step 4.0. A cheap pre-filter runs before every LLM call (§6.6). | §11 thresholds, Step 2.0 gating, Step 4.0 feasibility. |
| 0.5 | One gene target per document? | **No — `gene_targets` is a list** (§10). | Partition key, graph writes, corroboration. |
| 0.6 | Kafka Streams: requirement or learning goal? | **Not a requirement.** Conditional Phase 6 work. | Phase ordering. |
| 0.7 | Signals with no resolvable ticker | **Stored and corroborated**, reachable by gene target, absent from ticker-keyed REST responses. | §9, REST contract. |

**On 0.3.** `[P2-1]` Forward-only collection with a 90-day lookback is incompatible with a Phase 4 backtest of whether corroborated signals precede price moves. Those are incompatible. Forward-only collection at realistic biotech signal density yields a handful of corroborations in the first quarter; Step 4.4's hit rate and lead time would be computed on a single-digit sample and would mean nothing. Either Phase 4 waits about a year, or history is backfilled. Backfill is cheap for the sources that matter — ClinicalTrials.gov, EPO OPS (patents), and EDGAR all support date-ranged bulk queries — so Step 4.0 exists and Phase 4 depends on it.

---

## 1. System Stack & Dependencies

### Scraper / Ingestion Service (`/services/ingestion-scraper`)
* **Runtime:** Python **3.14** · `pyproject.toml` managed by **uv**, `uv.lock` committed. All versions pinned exactly — see `VERSIONS.md`. `[P3-1]`
* **Execution model:** fully synchronous. No `async`/`await`. `SourceConnector.fetch_since()` returns a plain `Iterator`.
* **Core Libraries:** `httpx` (only via the shared `RateLimitedClient`, §6.5) · `feedparser` · `instructor` + OpenAI client · `pydantic` v2 · `confluent-kafka` (sync producer; `aiokafka` explicitly not used) · `minio` · `python-dotenv` · `pyrate-limiter`
* **Test Libraries (§13):** `pytest`, `pytest-cov`, `pytest-mock` · `respx`/`httpx.MockTransport` · `pytest-socket` (`--disable-socket` across the unit suite) · `testcontainers` (**required**, so the suite is self-contained on a clean checkout)

### Signal Processing / Core Hub (`/services/core-hub`)
* **Runtime:** Java **25 (Temurin LTS)** · Spring Boot **4.1.0** · **Gradle 9.7.0** (Kotlin DSL, committed wrapper, versions in `gradle/libs.versions.toml`). `[P3-1]` **The Spring Boot 3.x line reached open-source EOL on 2026-06-30**, so a project starting today must be on 4.x — most tutorials and Stack Overflow answers still assume 3.x. Boot 4.1 brings Spring Framework 7 and **Spring Kafka 4.1** — the `DeadLetterPublishingRecoverer` behaviour verified for Spring Kafka 2.x/3.x must be re-confirmed at Step 1.3 (see `VERSIONS.md`). **Lombok is dropped**: Java 25 records plus constructor injection cover our use, and Lombok has historically lagged new JDK releases — a bad dependency to have on the critical path
* **Dependencies:** Spring Web, Validation, Spring Kafka, Spring Data JPA, Spring Data Neo4j, PostgreSQL Driver, **Flyway**
* **Test:** JUnit 5, Testcontainers (kafka/postgresql/neo4j), `spring-kafka-test`, `awaitility`, **ArchUnit**

### Infrastructure
* **Kafka 4.3 (KRaft):** topics provisioned from a declarative `topics.yaml`, never as a side effect of constructing a producer.
* **PostgreSQL 18.6:** (19 is in beta — do not use) raw fetch audit, current signal state, extraction history, source observations, corroborations, price series. Airflow metadata in a separate logical database, own role, no cross-grants (provisioned in Step 0.2 because the compose init script only runs against an empty data directory). **Schema owned by Flyway; `ddl-auto=validate`.**
* **Neo4j 2026.05 (Community):** model in §9. `[P3-1]` Neo4j moved to **calendar versioning**; the 5.x line ended at the 5.26 LTS, so "Neo4j 5" no longer names a current release. The 5.26 LTS is the conservative alternative — see open question 4. Constraints created by a versioned, idempotent startup component using `CREATE CONSTRAINT ... IF NOT EXISTS FOR (n:Label) REQUIRE ...` (Neo4j 5 syntax; the 4.x `ON ... ASSERT` form is removed), recording its version on a single `(:GraphSchema {version})` node so a later change is traceable. `[P2-9]`
* **MinIO:** raw landing zone (§7). Credentials from `.env` with **no defaults**; all compose ports bound to `127.0.0.1`.

---

## 2. Kafka Topic Design

| Topic | Key | Producer | Consumer | Purpose |
|---|---|---|---|---|
| `auspex.raw.ingested` | `external_id` | Scraper | Core hub (audit) | Pointer event: bucket/key, `external_id`, `canonical_id`, `source_type`, `source_url`, `retrieved_at`, `content_sha256`, `schema_version`. No `raw_content`. |
| `auspex.signals.extracted` | `event_id` | Scraper | Core hub | `ResearchSignalEvent` JSON. |
| `auspex.signals.corroborated` | `entity_key` | Core hub | Notifications, future consumers | `CorroboratedSignal` (§4). |
| `auspex.raw.ingested.dlt` / `auspex.signals.extracted.dlt` | inherited | Core hub error handler | Manual triage | Dead letters. |

**Partitioning** `[F2, A11]`: keys are document identity. Keying on `gene_target` is the tempting choice and is wrong twice over — impossible for the pointer event (published before extraction has run) and unused by anything in Phases 1–4, since corroboration is a graph query. A future Streams topology repartitions with `groupBy`; that is Streams' job.

**Partitions and replication** `[B11]`: 6 partitions, RF 1 (single broker). **DLTs get the same partition count as their source topic** — Spring's default `DeadLetterPublishingRecoverer` publishes to the same partition number, so a smaller DLT fails to publish.

**DLT naming** `[B5]`: Spring's default resolver appends **`.DLT`** (uppercase), verified against the Javadoc. The lowercase names above require a custom `BiFunction<ConsumerRecord<?,?>, Exception, TopicPartition>` that lowercases the suffix **and** returns partition `-1` (documented: a negative partition lets the producer choose).

**Retention:** signals ≥ 90d · corroborated ≥ 90d · raw 7d · `*.dlt` ≥ 30d.

---

## 3. Architectural Boundaries & Rules

1. **Strict event-driven decoupling.** `ingestion-scraper` writes only to **MinIO and Kafka**. `[P2-5]` No exemption for cursor state: reaching Airflow's Variable store would mean the scraper needs credentials for the Airflow metadata database, which is exactly the coupling this invariant exists to prevent. Cursor state is orchestration state and belongs to the orchestrator (§5).
2. **Single database writer.** `core-hub` is the sole writer to the application database and Neo4j.
3. **Environment security.** No credentials, keys, or hosts in source. Source API keys are Airflow Connections. Logs never carry credentials or full `raw_content`.
4. **Schema symmetry.** Pydantic model and Java record match field-for-field; wire format is snake_case via an explicit `PropertyNamingStrategies.SNAKE_CASE`. The Python model generates the contract fixture (§13).
5. **Synchronous throughout.** Concurrency, if ever needed, comes from Airflow task parallelism — never from an async connector contract.
6. **Timestamps are UTC, always** — including in derived strings such as MinIO object keys, which are formatted from a UTC-converted value rather than from whatever offset arrived.
7. **Idempotent writes, per declared natural key** `[A12]`:

    | Table / node | Key | Conflict behaviour |
    |---|---|---|
    | `raw_fetch_audit` | MinIO object key | `DO NOTHING` (append-only) |
    | `signal_current` | `event_id` | `DO UPDATE` (latest extraction wins) |
    | `signal_extraction_history` | `(event_id, extraction_id)` | `DO NOTHING` (append-only) |
    | `source_observation` | `(event_id, source_type, external_id)` | `DO NOTHING` (append-only) `[P2-3]` |
    | `corroboration` | `(entity_key, participants_hash)` | `DO NOTHING`, with supersession (§4) `[P2-4]` |
    | `(:Signal)` | `event_id` | `MERGE` |
    | entity nodes | natural key per §9 | `MERGE` |

8. **Write ordering and offset commit** `[A9]`: Neo4j → Postgres → acknowledge, `ack-mode: RECORD`. The offset is never committed before both stores return. With two transaction managers present, **every `@Transactional` on application code must be qualified**, and JPA and Neo4j repositories live in separate base packages with explicit `@EnableJpaRepositories`/`@EnableNeo4jRepositories`. Enforced by an ArchUnit rule **scoped to the application's own packages** `[P2-10]`.
9. **Consumer semantics:** `auto-offset-reset: earliest`; one named group per listener; `max.poll.records` small enough to finish inside `max.poll.interval.ms`.
10. **Dead-letter handling:** deterministic failures (deserialization, validation, unknown enum, missing/out-of-range `confidence_score`, unknown major `schema_version`) → DLT immediately. Transient failures → **1 attempt + 2 retries = 3 total deliveries** with backoff, then DLT (stated explicitly because `FixedBackOff` counts retries). **`ErrorHandlingDeserializer` wraps the value deserializer on both listeners** — without it a malformed payload fails inside the poll loop before any error handler runs, and the container retries the same offset forever. Diagnostic headers on every record. Never block a partition.
11. **Parameterized queries only.** Bind parameters everywhere; allowlist validation at the controller boundary (`^[A-Z][A-Z0-9.\-]{0,9}$`). Enforced by an **ArchUnit rule plus behavioural injection tests**, not by assertions on executed query text, for which Spring Data Neo4j offers no supported seam.
12. **Nothing dies silently.** DLT depth and per-source signal age are reported (§12).

---

## 4. Correlation / Linking

Two signals **corroborate** when they reference the same normalized entity, come from **distinct `source_type`s**, and their publication dates are within 90 days **of each other**:

```
corroborates(s1, s2)  ⇔  s1.entity == s2.entity
                       ∧ s1.source_type ≠ s2.source_type
                       ∧ |s1.published_date − s2.published_date| ≤ 90 days
```

`[A4]` Read "rolling 90-day window" as `now − 90d` and two signals published three days apart in 2024 never match — Phase 4 then has nothing to test. The window is between the two signals, not between each signal and today.

### 4.1 The corroboration record `[P2-4]`

The key `(entity_key, participant_event_ids)` and the requirement "three distinct sources produce one record, not one per pair" are incompatible under growth: when a fourth signal joins an entity's group, the participant set changes, the key changes, and a second record appears for the same underlying evidence — duplicate notifications and double-counted backtest observations, the exact failure the v1 `event_id` formula caused.

The record is therefore **one row per entity per participant set, with explicit supersession**:

* `entity_key` — normalized entity name plus label.
* `participants_hash` — hash of the sorted participant `event_id`s.
* `participant_event_ids`, `distinct_source_count`.
* `corroborated_at = max(participant.published_date)` — **the only field Phase 4 may join on** `[A15]`.
* `first_detected_at` — scheduler run time; diagnostic only.
* `superseded_by` — set when a larger group containing all of this row's participants is written. A superseded row is retained (the backtest needs the participant set *as of* an evaluation date) but is excluded from notifications and from REST responses.

### 4.2 Scan strategy

The job maintains a `corroboration_watermark` (last processed `ingested_at`). Each run selects signals written since the watermark, and for each, matches against existing signals on its entities within ±90 days of **its own** `published_date`. A wall-clock filter may be used to narrow the candidate scan and must be documented as an optimization, never as the semantic definition. Entities whose degree exceeds a configurable cap (default 500) are skipped — a generic mechanism attached to thousands of signals produces combinatorial noise.

The `CorroborationService` interface stays because it is cheap; the Streams implementation is conditional Phase 6 work.

---

## 5. Orchestration and Cursor State `[P2-5]`

**Airflow 3.3.** `[P3-2]` Three Airflow 3 changes bear directly on this design: `schedule_interval` is renamed **`schedule`**; task code can no longer touch the metadata database directly, with Variables and Connections proxied through the Task SDK's Execution API (which is exactly how the cursor is accessed below, so the design holds); and `catchup` now defaults to `False` — we still set it explicitly, because a default is not a guarantee.

Airflow owns *when* each source is polled; Kafka owns what happens after extraction. RabbitMQ stays out: its per-message ack/retry/priority semantics overlap what Kafka consumer groups already give us here, and a second broker is a second thing to operate.

**The pipeline is stateless with respect to cursors.** `IngestionPipeline.run(source_type, cursor)` receives a cursor and returns a `RunResult` containing `max_published_date_processed`. It never reads or writes cursor state.

**The DAG task owns the cursor**, because Airflow already holds the connection to its own metadata database:

1. Read Variable `cursor:{source_type}`; default to `now − initial_lookback` from `sources.yaml`.
2. Call `IngestionPipeline.run(source_type, cursor)`.
3. On success, write back `result.max_published_date_processed` — **not `now`**, which would skip anything published during the run.
4. On failure, leave the Variable untouched.

`run_mock_ingestion.py` and the Step 4.0 backfill runner take the cursor as an argument. **A backfill never writes the live cursor.**

**DAG configuration is not optional** `[A14]`: `catchup=False`, `max_active_runs=1`, staggered schedules. Without them a run slower than its interval overlaps its successor from the same cursor — duplicate fetches, duplicate LLM spend, duplicate events. This breaks at roughly 5× volume, not 100×.

---

## 6. Source Connector Architecture

### 6.1 The connector contract is pure

```python
class SourceConnector(ABC):
    source_type: str

    @abstractmethod
    def fetch_since(self, cursor: datetime) -> Iterator[RawDocument]:
        """Yield documents disclosed since `cursor` (UTC-aware). Fetch and map only."""
```

`fetch_since` does not write to MinIO, call the LLM, or publish. `[A1]` The opposite reading — that `fetch_since` performs its own writes — would force all five connectors to duplicate the pipeline.

### 6.2 The pipeline is a named component

```python
class IngestionPipeline:
    def run(self, source_type: str, cursor: datetime) -> RunResult: ...
```

Per document: **pre-filter → dedup → MinIO archive → extract → publish**. It is the single caller of the connector, MinIO client, extractor, and producer.

**Per-document error isolation** `[A8]`: a failing document is recorded and the run continues. `RunResult` counts `fetched / prefiltered_out / deduped / not_signal / below_threshold / extracted / published / failed` `[P2-7]`, plus `max_published_date_processed`. The task fails only if the failure *rate* exceeds a configured threshold.

**Publish is not fire-and-forget** `[A7]`: `produce()` is asynchronous; the run must `flush()` and check delivery reports. An undelivered message fails the run.

### 6.3 `RawDocument`

`schema_version` · `external_id` · `canonical_id` (typed, §10.1) · `source_type` · `source_url` · `published_date` (§6.7) · source-specific dates retained separately · `raw_content` · `content_sha256` · `retrieved_at`.

### 6.4 Entity normalization seam `[P2-11]`

`EntityNormalizer` is defined in Phase 1 with an **identity implementation**, and every graph write goes through it from the start. Phase 2's real implementation is then a substitution, not an insertion. v2 introduced normalization in Step 2.8 while Step 1.4 already spoke of "normalized entity" — a component that did not exist yet.

### 6.5 Rate limiting is shared and configured

`[B7]` Reactive 429 handling is not compliance. Every connector issues HTTP through one `RateLimitedClient` enforcing a **per-host** token bucket from `sources.yaml`; Airflow schedules are staggered. Verified limits:

| Host | Limit | Notes |
|---|---|---|
| `eutils.ncbi.nlm.nih.gov` | 3 req/s without key, 10 with | Free key via NCBI account; `tool=`/`email=` expected. |
| `api.biorxiv.org` | none published | Configure 1 req/s. |
| `ops.epo.org` | 2.5 req/s (standard free tier), 4 GB/week data | OAuth2 client credentials; token expires after 20 min, must be refreshed. 429 carries `Retry-After`. Configure 2 req/s to stay safely under limit. |
| `api.fda.gov` | 240 req/min per IP; **1,000 req/day without a key**, 120,000 with | The daily cap binds, not the per-minute one. |
| `clinicaltrials.gov` | none published; ~50 req/min observed | Configure 1 req/s. |
| `*.sec.gov` (incl. `efts.`, `data.`) | **10 req/s aggregate across all SEC hosts** | Configure 5 req/s. Descriptive `User-Agent` with contact email mandatory (403 without). Exceeding blocks the IP ~10 minutes; retrying during the block extends it. |

### 6.6 Pre-filter before extraction `[P2-8]`

A cheap deterministic filter runs before every LLM call: the document must match at least one term from a configured vocabulary (gene symbols, mechanism keywords, modality terms) in its title or content. Rationale: most fetched documents from EDGAR and openFDA are irrelevant, extraction is the dominant cost, and Step 4.0's backfill is otherwise unaffordable. The filter is **measured on the golden set for false negatives** (§11.3) and its vocabulary is versioned alongside the prompt. `prefiltered_out` is counted in `RunResult`, so aggressive filtering is visible rather than silent.

### 6.7 Per-source timestamp mapping (authoritative)

**Rule: `published_date` is always the date the information became public.** Non-public dates are retained for analysis and never used for point-in-time alignment.

| Source | `published_date` ← | Also retained | Notes |
|---|---|---|---|
| bioRxiv | `date` of the fetched version | `version`, journal DOI when linked | A new version is a new public disclosure. |
| PubMed | earliest public availability (Entrez/ahead-of-print) | issue date | |
| Patents | **pre-grant `publication.date_published`**, else grant date | `filed_date`, `granted_date` | **`filed_date` is the trap here.** It looks like the correct look-ahead guard and is the opposite. A US application is not public at filing — it publishes ~18 months later. `filed_date` is the priority date and is excluded from Phase 4 joins. |
| Clinical trials | `studyFirstPostDateStruct.date`, or `lastUpdatePostDateStruct.date` on an amended fetch | `first_submitted_date` | Same trap: submission is private, posting is public. |
| Regulatory | submission/approval action date | application metadata | |
| SEC EDGAR | `acceptanceDateTime` | period of report | |

### 6.8 Verified source APIs (checked August 2026)

| Source | Endpoint | Auth | Status |
|---|---|---|---|
| bioRxiv/medRxiv | `https://api.biorxiv.org/details/{server}/{start}/{end}/{cursor}` | none | Live. 100/page, integer cursor. **Abstracts only, not full text.** |
| PubMed | E-utilities | optional free key | Live. |
| Patents | `https://ops.epo.org/3.2/rest-services/published-data/search` | **OAuth2 client credentials (`EPO_OPS_KEY` / `EPO_OPS_SECRET`)** | Live and stable. Free standard tier, email registration at `developers.epo.org`, no government ID, no commercial-use restriction. DOCDB: ~130M documents, covers US, EP, PCT. Both PatentsView URLs are superseded and Lens.org requires institutional subscription — see CLAUDE.md known traps. |
| Clinical trials | `https://clinicaltrials.gov/api/v2/studies` | none | Live and stable. `nextPageToken`, `pageSize` ≤ 1000, `fields` projection. v1 retired June 2024. |
| Regulatory | `https://api.fda.gov/drug/{drugsfda,label,enforcement,drugshortages}.json` | optional key (needed for the daily quota) | Live — see §6.9. |
| Material disclosures | `https://efts.sec.gov/LATEST/search-index` + `https://data.sec.gov/submissions/CIK##########.json` | none; mandatory `User-Agent` | Live. EFTS is **undocumented** — no published parameter list, schema, or stability commitment. Keep the mapping thin. |
| Ticker resolution | `https://www.sec.gov/files/company_tickers.json` | none; mandatory `User-Agent` | Live. Ticker/CIK/name for all EDGAR filers. Resolution source for §9. |

### 6.9 Regulatory connector rescoped `[B14]`

**Verified: openFDA has no designations endpoint.** Its drug domain is adverse events, labeling, NDC, recall enforcement, Orange Book, Drugs@FDA, and shortages — the complete list. Orphan designations live in a separate FDA database exposed as an HTML search with spreadsheet export; Fast Track and RMAT are not published machine-readably at all. So:

* **`fda_approval`** — openFDA Drugs@FDA, labels, shortages. Real API, free, reliable.
* **`fda_designation`** *(optional)* — the orphan designation export as a slow bulk import; Fast Track/RMAT via a company press-release feed registered as its **own `source_type`**, so its lower reliability is visible in corroboration counts.

---

## 7. Raw Storage, Deduplication, and Precedence

**The archive is unconditional.** Every successful fetch writes a MinIO snapshot before any other side effect.

**Object key** `[A16]`:

```
raw/{source_type}/{external_id}/{retrieved_at:%Y%m%dT%H%M%SZ}-{content_sha256[:8]}.json
```

Second granularity alone would turn a legitimate same-second retry into a hard collision error.

### 7.1 Precedence rule `[A7, B2, Q2]`

1. **Archive always** — first, unconditional.
2. **Dedup gates extraction and publish only**, never the archive. An archived-but-unpublished document (Kafka outage) is therefore recoverable; dedup keyed on fetch instead would make it permanently invisible.
3. **Within a document** — compare `content_sha256` against existing snapshots for `(source_type, external_id)`. Same hash → no-op re-fetch: skip extraction and publish, log. Different hash → **amendment**: extract and publish.
4. **An amendment publishes under the same `event_id`** with a new `extraction_id` (§10.1). Current state upserts, history appends. An amended trial is still one trial.
5. **Across sources** — a `canonical_id` marker object `[P2-2]`:

   ```
   dedup/canonical/{sha256(canonical_id)}.json   → { event_id, first_source_type, first_seen }
   ```

   Written **after** a successful publish. On a later fetch of the same `canonical_id` from a different source, the marker is a direct `get` (no listing), so extraction is skipped and only a `source_observation` row is recorded. v2 claimed cross-source mirrors "collapse via `canonical_id`" but provided no way to look up by canonical id — MinIO keys are organized by `external_id` — so in practice every mirrored paper would have been extracted twice at full LLM cost.

   *Known behaviour:* if publish succeeds and the marker write fails, the next fetch re-extracts. That is at-least-once, absorbed by the consumer's idempotent upsert, and is preferable to writing the marker first (which could suppress a document that never published).

6. Where no `canonical_id` exists, cross-source duplicates are accepted.

**Embedding-similarity dedup is cut** — it implied a vector store absent from the stack and an embedding call per document, to solve a problem a DOI solves.

**Downstream:** Postgres is the queryable warehouse; DuckDB over Parquet in MinIO is the free next step.

---

## 8. Historical Price Data (Phase 4)

`yfinance` remains the choice. Verified caveats: it is an unofficial wrapper that breaks when Yahoo changes endpoints; `YFRateLimitError` is a recurring, sometimes multi-hour, IP-level block even at low request rates; Yahoo's terms contemplate personal use.

**Fetch once, then never again** `[F3]`: every retrieved OHLCV series is written to Parquet in MinIO on first fetch and all backtests read the snapshot, through a cached rate-limited session. Phase 4's reproducibility requirement demands this anyway, and it converts a flaky dependency into a one-time cost. Documented fallback: **Stooq** (free, no key, daily OHLCV history).

---

## 9. Neo4j Graph Data Model

```
(:Signal {
    event_id,          // unique constraint — MERGE key
    extraction_id, source_type, source_url, external_id, canonical_id, raw_object_key,
    published_date,    // UTC — indexed
    ingested_at, title, directionality,
    confidence_score,  // stored as a double property  [P2-6]
    schema_version
})
  -[:TARGETS]->        (:GeneTarget {name})
  -[:USES_MECHANISM]-> (:Mechanism {name})
  -[:MENTIONS]->       (:Company {name, ticker})
```

**`Company` MERGEs on normalized `name`, not `ticker`** `[B1]`. Most companies extracted in Phase 2 have no ticker, and `MERGE (c:Company {ticker: null})` matches *any* null-ticker node, collapsing unrelated companies into one super-node — which Neo4j's uniqueness constraints, ignoring nulls, would not catch. `ticker` is a set-if-known property with a non-unique index.

**`confidence_score` is a `double` in the graph** `[P2-6]`, written through an explicit converter. The DTO and Postgres use `BigDecimal`/`NUMERIC(4,3)` (§10.3), but Neo4j has no decimal type and Spring Data Neo4j may otherwise persist a `BigDecimal` as a string — which silently breaks numeric comparison in Cypher, and therefore Phase 3 scoring and any ordering in the REST layer. *Verify the SDN default conversion for your pinned version; the explicit converter makes the answer irrelevant.*

**Constraints and indexes (from Step 1.3):** unique `Signal.event_id`, `GeneTarget.name`, `Mechanism.name`, `Company.name`; indexes on `Signal.published_date`, `Signal.source_type`, `Company.ticker`. Plus a single `(:GraphSchema {version})` node.

**The corroboration pattern is typed** `[B3]`:

```cypher
MATCH (s1:Signal)-[:TARGETS|USES_MECHANISM]->(e)<-[:TARGETS|USES_MECHANISM]-(s2:Signal)
```

An untyped `(:Signal)-[]->(entity)` would also match `:MENTIONS`, so two filings both naming Pfizer would corroborate.

---

## 10. Identity, Versioning, Value Contracts

### 10.1 Document identity `[Q1, P2-3]`

Two near-miss formulas to avoid. Keying on `(source_type, external_id, schema_version)` means a schema bump changes every id and duplicates every corroboration. Dropping `schema_version` but writing `uuid5(NS, f"{source_type}:{canonical_id or external_id}")` while simultaneously claiming in §7 that a shared DOI collapses two sources to one `event_id` — which that formula cannot do, since `source_type` differs. It also made identity depend on whether the source happened to populate the DOI field on a given fetch. Corrected:

```python
# canonical_id is typed: "doi:10.1101/2024.01.01.123456", "nct:NCT01234567",
#                        "epo-app:US-18123456", "edgar:0000320193-24-000058"
if canonical_id:
    event_id = uuid5(NAMESPACE_URL, canonical_id)          # source-independent
else:
    event_id = uuid5(NAMESPACE_URL, f"{source_type}:{external_id}")

extraction_id = uuid5(NAMESPACE_URL,
                      f"{event_id}:{schema_version}:{prompt_version}:{prefilter_version}:{extraction_model}")
```

* The type prefix prevents collisions between identifier namespaces.
* A source that populates `canonical_id` intermittently is a **connector defect**, not an identity variant: if a source can supply a canonical id at all, the connector must supply it for every document or fail loudly.
* When one document is observed from several sources, `signal_current.source_type` is **set from the first observation and never updated**; every observation appends to `source_observation`. Without this, last-writer-wins would let a preprint's `source_type` flip to a journal's and change corroboration counts retroactively.

### 10.2 `ResearchSignalEvent`

`schema_version`, `event_id`, `extraction_id`, `external_id`, `canonical_id`, `raw_object_key`, `source_type` (enum), `source_url`, `published_date`, `published_date_field`, `ingested_at`, `title`, `raw_text_snippet`, `gene_targets` (list), `mechanisms` (list), `companies_mentioned`, `summary`, `directionality` (enum), `confidence_score`, `prompt_version`, `prefilter_version`, `extraction_model`.

`external_id` and `raw_object_key` are what keep the chain of custody intact — without them a signal cannot be joined to its audit row, re-extracted from its snapshot, or resolved back to the per-source dates Phase 4 needs. `gene_targets` is a list because real papers name several; getting this wrong is expensive to correct once the graph and the topic key both depend on it.

### 10.3 `confidence_score`

Float, inclusive `0.0–1.0`. Pydantic `Field(ge=0.0, le=1.0)`.

**Java uses `BigDecimal` with `@NotNull @DecimalMin("0.0") @DecimalMax("1.0")`, not a primitive `double`** `[B4]`. A primitive cannot be null, so a missing field deserializes to `0.0`, passes validation, and stores as a plausible "zero confidence". And Bean Validation specifies these constraints for `BigDecimal`, `BigInteger`, `CharSequence`, and integral types — float/double is a Hibernate Validator extension the spec cautions against. `@Valid` must be applied to the listener payload explicitly; bean validation does not run on `@KafkaListener` arguments otherwise. Postgres: `NUMERIC(4,3)`. Neo4j: `double`, per §9.

Out of range or missing → DLQ. Never clamped or rescaled.

### 10.4 Schema versioning `[B6]`

`major.minor` parsed as **integers** (`"1.10"` sorts below `"1.9"` as text). Unknown major → DLQ. Minor mismatch → accept and log, which requires `FAIL_ON_UNKNOWN_PROPERTIES=false`; with Jackson's default the first additive change dead-letters everything. Emitted as a UTF-8 Kafka header as well as a field. A bump updates the Pydantic model, the Java record, and the regenerated contract fixture in one change.

**Re-extraction is an explicit operation** `[P2-12]`, invoked by a documented CLI against the MinIO archive — never a side effect of a routine run. It writes a new `extraction_id`, upserts `signal_current`, appends history, and re-runs corroboration for affected entities. Without this rule, a model or prompt bump would silently rewrite current state for every subsequent fetch while leaving already-ingested documents on the old extraction, producing a corpus that is half one version and half another with nothing recording the split.

---

## 11. Extraction Contract

### 11.1 "Not a signal" is a first-class outcome `[A5]`

```python
def extract(doc: RawDocument) -> ResearchSignalEvent | None: ...
```

The LLM response model carries `is_signal: bool` — the model makes the call, not a score threshold. `None` → archived, counted, no event. Without this path, `instructor` forces a `ResearchSignalEvent` out of every document and the model invents a `gene_target` for a press release about an executive appointment: junk nodes on real entities, inflating distinct-source counts with noise.

`min_confidence_to_publish` is **per source, default 0.0 (disabled)** `[P2-7]`. A non-zero default would apply a threshold to a score whose calibration §11.3 has not yet measured — dropping real signals invisibly. Raise it only on evidence from the Step 2.0 calibration run, and record `below_threshold` in `RunResult` so its effect stays visible.

### 11.2 Untrusted input `[B8]`

Extraction runs over arbitrary fetched text, which can contain instructions.

* Content is passed in an explicitly delimited block, with a system instruction that everything inside is data, never instruction.
* `raw_content` is truncated to a documented maximum.
* Extracted `gene_targets` are validated against a controlled vocabulary (HGNC symbols); unrecognized symbols go to a review bucket, not the graph.
* Any extracted ticker is validated against the §3.11 allowlist before a graph write.

The payoff here is content, not code execution: a document that induces a chosen target, company, and `directionality: positive` manufactures a corroboration. In a system whose output is a research conclusion that is both the highest-value attack and the least likely to be noticed. It also happens by accident.

### 11.3 Extraction quality is measured `[E2]`

The prompt is a versioned file (`prompts/extraction/v{N}.md`), referenced by `prompt_version` on every event; the pre-filter vocabulary is versioned as `prefilter_version`. A golden set of 20–30 hand-labelled real documents spanning every `source_type` scores per-field precision/recall, the `is_signal` confusion matrix, `confidence_score` calibration, and **pre-filter false negatives** `[P2-8]`. It runs manually, never in CI, and gates each connector step.

---

## 12. Observability `[B9]`

The failure mode here is not a crash — it is producing fewer or wrong corroborations while every container stays green.

* **Structured JSON logs** carrying `source_type` and, where applicable, `external_id`/`event_id`.
* **Run summary** per run: the full `RunResult` counts plus cursor before and after.
* **A `@Scheduled` health reporter** in `core-hub` logging DLT depth per topic and per-source age-of-latest-signal; from Phase 5 it emits through the notification transport.
* **Cursor position is visible** in the Airflow UI.

This belongs in Phases 1–2. A connector that silently started returning empty result sets after an API change is otherwise indistinguishable from a quiet week.

---

## 13. Testing Strategy — TDD

Tests precede implementation for every step. A step's Definition of Done is that its suite passes **and that its tests were checked against these requirements before being written** (see `plan.md` instruction 4).

**`ingestion-scraper` — pytest.** `tests/unit/` and `tests/integration/` with an `integration` marker. `pytest-socket --disable-socket` across the unit suite — this, not a naming convention, is what makes "no live API calls" true. Source APIs stubbed via `respx` against saved fixtures. The OpenAI client is injected and stubbed. MinIO and Kafka integration tests use `testcontainers`, not a manually started compose stack. An injected `now()` provider throughout.

**`core-hub` — JUnit 5 + Testcontainers.** Container-backed for consumer→store round trips, Cypher behaviour, DLQ routing, idempotent upsert. Plain unit tests, no Spring context, for DTO/JSON contract, validation, error classification, serialization, and scoring functions `[C2]`. Containers are **static singletons started once per JVM**, `testcontainers.reuse.enable=true` locally, one Spring context, no `@DirtiesContext`, truncation rather than restarts. Target: the Phase 1 Java suite under three minutes locally. `java.time.Clock` injected; `awaitility` never `Thread.sleep`. The JVM-default-timezone test runs as a **separate Gradle `Test` task** (`timezoneCheck`) with `-Duser.timezone` set on the forked JVM, never by mutating the default timezone mid-suite. Container-backed tests live in their own `integrationTest` source set and task, not mixed into `test`. ArchUnit (scoped to application packages) enforces no concatenated queries, no unqualified `@Transactional`, no source-specific branching in shared components.

**The contract fixture is generated** `[C3]`: the Python suite writes `core-hub/src/test/resources/contract/research_signal_event.json` from the Pydantic model; CI fails if the tree is dirty after `pytest`. A hand-copied fixture drifts silently and turns the one test guarding the language boundary into a test of a historical artifact.

**Named guards.** Each of these has a test that fails against the plausible-but-wrong implementation, and each is listed in the step that owns it: pairwise window, `event_id` stability across schema bumps, cross-source `event_id` collapse, corroboration supersession, tickerless companies, missing `confidence_score`, minor-version tolerance, same-second re-fetch, archived-but-unpublished recovery, per-document error isolation, rate limiting, prompt injection, patent publication-vs-filing date.

`verify_pipeline.sh` is a smoke test, never the correctness authority.

---

## 14. Settled — do not relitigate

Sync-only execution; Airflow as scheduler with Kafka as backbone; Airflow metadata in a separate logical database; first-class `SignalNode`; `confidence_score` as a 0.0–1.0 float; UTC everywhere; Testcontainers over mocks at the store boundary; free-tier-first tooling; TDD.

# Living docs: core-hub and corroboration

**Status:** blocked
**Blocked by:**
1. `specs/docs-check-tooling.md` merged into `feature/living-docs-integration`: `python3 -m tools.docs_check` with `--next`, `--paths`, check M (`--matrix … --domain NS` and `--matrix … --decisions`), and `docs-check.toml` with `[rollout] planned_domains`.
2. `specs/living-docs-system-and-contracts.md` merged into the integration branch. It provides:
   - `docs/system/invariants.md`: INV-1 … INV-15, with the restore exception under INV-2 and the ClinicalTrials.gov exception under INV-4;
   - `docs/system/contracts.md`: CON IDs for topics, the raw pointer, the signal and corroborated events, natural keys per path, closed sets, and DLT naming, partition and headers.
3. These `DECISIONS.md` entries, appended on the scoping branch. The docs cite each heading, and the later `CHOICE` once the owner answers:
   - `2026-10-15 — Living docs — PENDING — closed sets on the wire`
   - `2026-10-15 — Living docs — PENDING — restore exception to invariant 2`, consumed only through the INV-2 exception that `specs/living-docs-system-and-contracts.md` writes
   - `2026-10-15 — Living docs — PENDING — raw-pointer contract`, consumed through the CON IDs that the same spec writes
   - `2026-10-15 — Living docs — PENDING — defects found while scoping`. Its items C1 and C5–C8 are the defects in the table below. It is cited by every `divergent` or `untested` row that records a defect the other headings do not cover.

**Branch:** `feature/living-docs-core-hub`
**Docs impact:** creates `docs/core-hub/consumption.md`, `docs/core-hub/storage.md`, `docs/core-hub/corroboration.md` and `docs/core-hub/http-api.md` (namespaces HUB and COR, all new IDs). It also:
- modifies the 4 active and hold specs listed under Affected files;
- appends one `PENDING` ratification-batch entry to `DECISIONS.md`;
- fills the `ID` cells of the HUB and COR rows of `specs/living-docs-cutover-matrix.md`, and the `IDs` cells of its binding decisions rows for HUB and COR;
- removes `core-hub` from `docs-check.toml` `[rollout] planned_domains`.

It does not change `services/core-hub/README.md`, `services/core-hub/CLAUDE.md`, `services/CLAUDE.md` or `docs/requirements.md`. Those belong to `specs/agent-instruction-hierarchy.md` and `specs/legacy-docs-retirement.md`.

---

## Context

At develop `e51f742`, core-hub behaviour is stated in:

| Source | What it holds | Standing |
|---|---|---|
| `docs/requirements.md`: §3 rules 7–12 (`:73-89`); §4, §4.1, §4.2 (`:91-122`); §9 (`:276-304`); the §10.1 storage half (`:328`); the §10.3 Java half (`:338-342`); the §12 health reporter (`:388`); the §13 core-hub paragraph (`:400`) | Natural keys, write order, ack mode, consumer and DLT rules, the corroboration definition, record and scan, the graph model, `confidence_score` types, the health reporter | Normative today |
| `services/core-hub/README.md` | Write order and ack mode (`:13`); failures and dead letters (`:15-20`); data model (`:24-49`); corroboration and the **scorer formula** (`:53-63`); REST API and write token (`:67-80`); key constraints (`:120-127`) | Not normative, but the only source of the scorer formula, of the replay semantics as written, and of the ticker rules. It is wrong in places:<br>- `GET /api/v1/signals/{ticker}` "returns 404 if no signals" (`:78`), while `SignalRestIT.test_unknown_ticker_returns_empty_lists_not_500` asserts 200 with empty lists.<br>- "re-runs at steps 2.8 and 6.4" (`:63`) is a plan-step reference.<br>- `source_observation` is "one row per (event_id, source_type)" (`:33`), while the key is `(event_id, source_type, external_id)`. |
| Flyway `services/core-hub/src/main/resources/db/migration/V1…V5` | Policy comments: natural keys per §3.7 (`V1:2`); first observation wins (`V1:53`); supersession (`V1:63`); single-user installation and the multi-user path (`V3:7-9`); "schema 1.1" (`V4:1`, stale and frozen); watermark dropped (`V5:1`) | Machine authority for the schema. Checksummed, never edited |
| `DECISIONS.md` `CHOICE` entries | Listed in full under "Decision headings" below | Binding until absorbed. Each is classified in the Decisions table of `specs/living-docs-cutover-matrix.md` |

**Decision headings this spec absorbs.** Each one's text goes into the `Source` cell of the ID that carries it:
- `2026-09-20 — Watchlist backend — CHOICE — No user_id column; single-user installation, extensible` (storage)
- `2026-09-20 — Watchlist backend — CHOICE — core-hub calls ClinicalTrials.gov directly` (http-api watchlist; the exception itself is under INV-4)
- `2026-10-08 — Control-surface scoping — CHOICE — dashboard runs in the stack behind its own server layer` (http-api write token and CORS)
- `2026-10-09 — Soak-test readiness — CHOICE — transient Kafka failures pause instead of retrying longer` (consumption retries, pause and replay)
- `2026-10-09 — Dashboard foundation — CHOICE — login endpoint, write-token failure mode, path layout`, item 3 (http-api write token)
- `2026-10-09 — Graph and connector wiring fixes — CHOICE — ticker resolution details` (storage company ticker; http-api watchlist back-fill)
- `2026-10-07 — Company-level extraction — CHOICE — event taxonomy and identifier fields (schema 1.1)`, item 4 (storage graph model)
- `2026-10-10 — Corroboration late arrivals — CHOICE — contract test signals are written pending, clear runs after the commit` (corroboration contract test and clear)

**Code entry points** (under `services/core-hub/src/main/java/dev/auspex/corehub/`):
- `config/KafkaConfig.java`: consumer factories `:92-124`, error handlers, `dltRecoverer` `:177-189`.
- `config/JacksonConfig`, `config/WriteTokenInterceptor`, `config/Neo4jSchemaInitializer`.
- `kafka/SignalListener.java:40-41`, `kafka/RawListener`, `kafka/StoreAvailabilityGuard`, `kafka/DltReplayService`, `kafka/CountingDeadLetterRecoverer`.
- `audit/RawAuditService.java:47`.
- `signal/SignalIngestionService`, `signal/ResearchSignalEvent.java:20-45`, `signal/SchemaVersion`.
- `persistence/Neo4jWriteService`, `persistence/PostgresWriteService`, `persistence/CompanyTickerService`.
- `corroboration/CorroborationService`, `ScheduledCorroborationService` (`:57-82`), `CorroborationScanner`, `CorroborationScorer`, `CorroboratedSignalEvent`.
- `query/SignalQueryService`, `rest/*Controller`, `watchlist/WatchlistService`, `health/HealthReporter`.
- Configuration: `src/main/resources/application.yml`.

**Defects C1 and C5–C8, as items of `2026-10-15 — Living docs — PENDING — defects found while scoping`, re-checked against code at `e51f742`:**

| Item | Claim | What the code shows | Holds? |
|---|---|---|---|
| C1 | The raw audit reads a field the producer never sends | `RawAuditService.java:47` reads `ingested_at`, which the raw pointer the scraper publishes does not carry | Holds. The contract is settled by `2026-10-15 — Living docs — PENDING — raw-pointer contract` |
| C5 | `ack-mode: RECORD` is probably not in effect | `application.yml:33` sets `spring.kafka.listener.ack-mode: RECORD`. Both listener factories are built with `new ConcurrentKafkaListenerContainerFactory<>()` and set only the consumer factory and error handler (`KafkaConfig.java:96-98,120-122`). Nothing calls `getContainerProperties().setAckMode(...)`: `grep -ri ackmode src/` finds only `application.yml`. As far as this reading goes (UNVERIFIED: the Spring Boot source was not consulted), Boot applies `spring.kafka.listener.*` through its factory configurer to the factory it auto-configures, not to factories built by hand, so the container default (BATCH) is likely in effect. No test asserts the ack mode | The code holds as stated. The runtime effect was **not executed** here. Offsets are still committed only after the listener returns, so the rule "no commit before both stores return" is not shown to be broken |
| C6 | `@Valid` on the listener may be inactive | `SignalListener.java:41` has `@Payload @Valid`, but there is no `KafkaListenerConfigurer` and no validator registered on the listener endpoint registrar anywhere in `src/main/java`. No integration test publishes an out-of-range or missing `confidence_score` through Kafka: `grep confidence_score src/integrationTest` finds only valid values. `test_missing_confidence_score_is_rejected_not_defaulted_to_zero` uses a `Validator` directly | Holds: the wiring is absent and the path is untested. Whether validation runs was **not executed** here |
| C7 | Unknown enum value → DLT is not implemented | `directionality`, `eventType` and `sourceType` are `@NotNull String` (`ResearchSignalEvent.java:26,37,42`), and no code checks membership. `KafkaErrorHandlingIT.test_unknown_enum_value_goes_to_dlt` publishes `schema_version` `99.0` (`:49-56`), so it tests an unknown major version | Holds |
| C8 | Corroborated event unversioned, hand-mirrored, at-least-once | `CorroboratedSignalEvent` has 6 fields and no `schema_version`. `strategy/.../runtime/events.py:9-31` mirrors it by hand, and there is no generated fixture. `ScheduledCorroborationService` sends inside the transaction and waits for each acknowledgement (`:57-60,73-76`), so a commit that fails after an acknowledged send re-sends on the next scan | Holds. The event's shape and versioning are CON's; its delivery is COR's |

**Other recorded defects.** This spec writes these as `divergent` or `untested` and does not fix them. Each cites the same PENDING heading:
- A malformed raw payload throws `IllegalArgumentException`, which is retried instead of dead-lettered at once (`RawAuditService`).
- `@EnableJpaRepositories`/`@EnableNeo4jRepositories` point at packages with no repositories.
- The ArchUnit concatenation rule does not cover `persistence`, `watchlist`, `config` or `kafka`.
- A record that dead-letters after the Neo4j write leaves a graph-only `Signal`.
- Two contract test names still say "watermark": `test_watermark_advances_and_is_not_reprocessed` and `signalIngestedInTheWatermarkSecondIsCorroborated`.

`docs/core-hub/` does not exist.

### Living-doc format (enforced by checks C, D, E and K of `tools/docs_check`)

- **Header.** Line 2 of every file is `Domain: <NS> · Code: <paths> · Last reviewed against: develop @ <sha>`.
- **Sections.** Required H2s, in order: `Scope`, `Requirements`, `Verification`, `Retired requirements`. The optional `Rationale` and `Known traps` H2s go after `Requirements`.
- **Requirements.** Each requirement is one list item that starts with `<a id="HUB-NNN"></a>**HUB-NNN**` (or `COR-NNN`), followed by one normative sentence.
- **Verification table.** Columns `| ID | Source | Verified by | Status |`, with one row per active ID.
- **Status values.**
  - `tested`: Verified by names `path::name` tests.
  - `enforced`: a config, schema or build rule.
  - `untested`.
  - `divergent`: approved behaviour the code does not have; Source names the DECISIONS heading.
  - `pending-decision`: Source names the PENDING heading.
- **Retired requirements.** Each one keeps its ID, original text, date and retiring source. Retired IDs are never reused.

## What this builds

Four living specs that become the only prose authority for core-hub:

1. **`docs/core-hub/consumption.md`** (HUB). Scope: what happens from a Kafka poll to the acknowledgement or the DLT; which failures dead-letter; and DLT replay. This file is the single owner of failure classification. DLT topic naming, partition and headers belong to CON, and this file links to them. Requirements, in this order:
   1. Two listeners, one named group each (`corehub-signal`, `corehub-raw`). `auto-offset-reset` is earliest, auto-commit is off, and `max.poll.records` is small enough to finish inside the poll interval (§3.9).
   2. `ErrorHandlingDeserializer` wraps the value deserializer on both listeners, so a malformed payload reaches the error handler (§3.10).
   3. Unknown JSON properties are ignored (`FAIL_ON_UNKNOWN_PROPERTIES=false`), so a minor schema addition is accepted (§10.4, consumer half; the version rule itself is CON's).
   4. **Failure classification.** These deterministic failures go to the DLT at once, without retry (§3.10, §10.3). Every other failure is transient (requirement 6). consumption.md is the only doc that lists them. Each failure class is its own requirement with its own verification row:
      - deserialization (malformed JSON): `tested`, `services/core-hub/src/integrationTest/java/dev/auspex/corehub/KafkaErrorHandlingIT.java::test_malformed_json_goes_to_dlt_immediately`;
      - a naive (offset-less) timestamp: `tested`, `KafkaErrorHandlingIT.java::test_naive_timestamp_is_rejected_to_dlq`;
      - an unknown major `schema_version`:
        - `tested`, `services/core-hub/src/test/java/dev/auspex/corehub/model/ResearchSignalEventTest.java::test_unknown_major_schema_version_is_classified_as_deterministic_failure`;
        - also `KafkaErrorHandlingIT.java::test_unknown_enum_value_goes_to_dlt`, which despite its name publishes major version `99.0`;
      - a missing `confidence_score`, never defaulted to zero: `untested` through Kafka (defects found while scoping, item C6). The only test is `ResearchSignalEventTest.java::test_missing_confidence_score_is_rejected_not_defaulted_to_zero`, which calls a `Validator` directly. Verified by names it as unit evidence for the type rule;
      - an out-of-range `confidence_score`, never clamped: `untested`. No test publishes one (item C6);
      - an invalid closed-set value (`directionality`, `event_type`, `source_type` outside its set): `divergent`, citing `2026-10-15 — Living docs — PENDING — closed sets on the wire` (item C7). No test exercises it, and the test named for it is cited only on the unknown-major row;
      - a malformed raw payload: `divergent`, because it is retried, not dead-lettered (a defect found while scoping).

      The closed-set values, the `schema_version` rule and the timestamp format link to CON. CON states none of these classes. In the verification table, write each test as a full `path::name` from the repo root. The short file names above stand for `services/core-hub/src/integrationTest/java/dev/auspex/corehub/` and `services/core-hub/src/test/java/dev/auspex/corehub/model/`.
   5. Listener payloads are validated with `@Valid`, which requires a validator registered on the listener endpoint (§10.3). Status `untested` (defects found while scoping, item C6).
   6. A transient failure gets 1 attempt plus 2 retries, with back-off of 5 s then 30 s by default, then goes to the DLT. A record never blocks its partition (§3.10; `2026-10-09 — Soak-test readiness — CHOICE — transient Kafka failures pause instead of retrying longer`).
   7. While Postgres or Neo4j is unreachable, both listener containers are paused. They resume only when both stores answer (same CHOICE).
   8. The offset of a record is committed only after both stores have returned, record by record (`ack-mode: RECORD`) (§3.8). Status `untested` (defects found while scoping, item C5): the configured mode is not applied to the hand-built factories.
   9. A dead-lettered record is counted per source topic. The metric name links to `docs/operations/observability.md`.
   10. **DLT replay.** `POST /api/dlt/{topic}/replay` (`2026-10-09 — Soak-test readiness — CHOICE — transient Kafka failures pause instead of retrying longer`; archived spec `specs/done/dead-letter-recovery.md`):
       - re-publishes only records already on the DLT when the call starts;
       - sends them to the original topic named in the `kafka_dlt-original-topic` header, with key, value and headers minus `kafka_dlt-*`;
       - commits progress per record in group `corehub-dlt-replay`, so a later call does not replay a committed record;
       - replays only the signal and raw DLTs; any other topic is 404.

       The text says delivery is at-least-once: a crash between send and commit replays one record twice, and idempotent writes absorb that.
   11. Listener logs put `event_id` and `source_type` in the MDC and clear them after each record. The log format, and what a log line must never carry, link to the log contract in `docs/operations/observability.md`. This file restates neither.

2. **`docs/core-hub/storage.md`** (HUB). Scope: Postgres schema semantics, the Neo4j model, write order, idempotency, edge replacement, raw audit, and the single-user schema. Its Scope section says, in one sentence with a link, that the restore path's writes are the exception recorded under INV-2 in `docs/system/invariants.md`. It defines no ID for that. Requirements, in this order:
   1. Flyway owns the Postgres schema. Hibernate runs with `ddl-auto: validate`. An applied migration is never edited, because its checksum is validated (`specs/done/java-package-reorganization.md`; the "never edited" part is a ratification item from the CLAUDE.md trap).
   2. The schema applies to an empty database; there is no legacy schema to migrate from. Links to the no-legacy statement in `docs/system/overview.md`.
   3. Writes are idempotent on the natural keys that CON declares per path (applies INV-10; the key table lives in CON, not here). Nodes use `MERGE`, never `CREATE`.
   4. Each signal is written to Neo4j first, then Postgres, then acknowledged (§3.8). A record that dead-letters after the Neo4j write leaves a graph-only `Signal`, and redelivery or replay converges. This is a ratification item.
   5. Every `@Transactional` names its transaction manager (§3.8; ArchUnit). The rule "JPA and Neo4j repositories in separate base packages with explicit `@Enable…Repositories`" goes to `Retired requirements`, with its original text: no repositories exist, and writes use `JdbcTemplate` and the Neo4j `Driver`. The retirement is listed in the ratification batch.
   6. Queries bind parameters. The ArchUnit rule plus the behavioural injection tests enforce this in the service packages (applies INV-12). Coverage of `persistence`, `watchlist`, `config` and `kafka` is `untested`.
   7. `signal_current.source_type`, `external_id` and `canonical_id` are set by the first observation and never updated. Every observation appends to `source_observation` (§10.1 storage half; `V1:53`).
   8. `confidence_score` is `NUMERIC(4,3)` in Postgres and a `double` in Neo4j, written explicitly so that Cypher compares numbers (§9, §10.3). The wire type is CON's.
   9. **Graph model** (§9):
      - `(:Signal)` is keyed on `event_id`; the entity nodes are `(:GeneTarget {name})`, `(:Mechanism {name})` and `(:Company {name})`.
      - The only relationships are `TARGETS`, `USES_MECHANISM` and `MENTIONS` (ArchUnit).
      - `Neo4jSchemaInitializer` creates the unique constraints and indexes, plus one `(:GraphSchema {version})` node.
      - The company-level fields go to `signal_current` only, not to the graph (`2026-10-07 — Company-level extraction — CHOICE — event taxonomy and identifier fields (schema 1.1)`, item 4).
   10. **Company ticker** (§9; `2026-10-09 — Graph and connector wiring fixes — CHOICE — ticker resolution details`):
       - `Company` merges on its name, never on `ticker`.
       - `ticker` is set only when exactly one SEC ticker matches the normalized name, and an unmatched or ambiguous merge never clears it.
       - Adding a watchlist ticker sets it on matching companies that have no ticker.
   11. A write replaces the signal's own edges. In the same transaction it deletes each edge whose entity the event no longer lists; shared entity nodes stay (archived spec `specs/done/graph-relationship-replacement.md`).
   12. Each raw pointer appends one `raw_fetch_audit` row keyed on its MinIO object key (§3.7). Status `divergent` (defects found while scoping, item C1): `RawAuditService.java:47` reads `ingested_at`, which the producer does not send. The row cites `2026-10-15 — Living docs — PENDING — raw-pointer contract` and the CON raw-pointer IDs.
   13. The schema is single-user: no table carries a `user_id`, and the multi-user path is one migration (`2026-09-20 — Watchlist backend — CHOICE — No user_id column; single-user installation, extensible`; `V3:7-9`).

3. **`docs/core-hub/corroboration.md`** (COR). Scope: the `CorroborationService` extension point, the definition, the record, the scan, the score, the kinds, and the published event's delivery. Requirements, in this order:
   1. All corroboration sits behind `CorroborationService` (applies INV-5). Every implementation passes the abstract `CorroborationServiceContractTest` unmodified. Its helpers write signals the way the write path does: pending, with a token (`2026-10-10 — Corroboration late arrivals — CHOICE — contract test signals are written pending, clear runs after the commit`, item 1).
   2. Two signals corroborate when they share a normalized entity through `TARGETS` or `USES_MECHANISM` (never `MENTIONS`), come from distinct `source_type`s, and were published at most 90 days apart, inclusive. The window is measured between the two signals, never against now (§4; the §9 typed pattern).
   3. **Corroboration kinds.** The only kind is shared-entity corroboration over `GeneTarget` and `Mechanism`, with `entity_key` = normalized name + `:` + label. A new kind is a change to this requirement, made by the spec that adds it.
   4. **Record** (§4.1). There is one record per entity per participant set:
      - `participants_hash` is computed over the sorted participant `event_id`s;
      - `distinct_source_count`;
      - `corroborated_at` = the latest participant `published_date`, the only field a backtest joins on;
      - `first_detected_at` is diagnostic only.
   5. A larger group that contains all of a record's participants supersedes it. Superseded records are kept, and excluded from notifications and REST responses (§4.1).
   6. Every graph write marks its signal pending with a fresh write token, in the write's own transaction (§4.2).
   7. A scan reads a bounded batch of pending signals and matches each against signals on its entities within ±90 days of its own `published_date`. Entities above the degree cap (configurable, default 500) are skipped (§4.2).
   8. **Commit and clear** (§4.2; `2026-10-10 — Corroboration late arrivals — CHOICE — contract test signals are written pending, clear runs after the commit`, item 2):
      - a scan's inserts commit only after every send is acknowledged;
      - the pending flag is cleared after that commit, and only where the write token is still the one the scan read;
      - a failed send, commit or clear leaves the signals pending.
   9. No clock decides which signals a scan sees. A late commit, a lagging partition, a DLT replay and a re-extraction are all scanned once committed (§4.2, §10.4).
   10. Each new non-superseded record is published once per successful scan, keyed by `entity_key`. Delivery is at-least-once, and a consumer deduplicates on `(entity_key, participants_hash)`. Status `untested` for the duplicate path (defects found while scoping, item C8). Shape and versioning are CON's.
   11. **Score.** `score = 0.7 × diversity + 0.3 × recency`, clamped to [0, 1], where:
       - `diversity = min(1, (distinct_source_count − 1) / 4)`;
       - `recency` decays linearly from 1 to 0 over 90 days after `corroborated_at`.

       The score is computed at read time against the service clock, and is never stored or published. This is a ratification item: README `:57-59` is the only prose source, and the code is `CorroborationScorer`.
   12. A failed run, in the scan or in a send, increments the scan-failure counter. The metric name links to `docs/operations/observability.md`.

   The corroboration-review quality gate (sampled corroborations at precision ≥ 0.85) is owned by `docs/ingestion/extraction.md`. This file links to it.

4. **`docs/core-hub/http-api.md`** (HUB). Scope: the REST surface, the write token and CORS (it owns both), and the health reporter. Requirements, in this order:
   1. **Write token.** Every request under `/api` other than GET or HEAD needs `Authorization: Bearer <CORE_HUB_WRITE_TOKEN>`, compared in constant time.
      - Without the header, or with no token configured, the answer is a 401 JSON error.
      - core-hub starts without a token and then refuses every write.

      Sources: `2026-10-09 — Dashboard foundation — CHOICE — login endpoint, write-token failure mode, path layout`, item 3; `2026-10-08 — Control-surface scoping — CHOICE — dashboard runs in the stack behind its own server layer`.
   2. core-hub returns no CORS headers; browsers reach it only through the dashboard's server (the same two CHOICEs). `docs/dashboard.md` links here.
   3. **`GET /api/v1/signals/{ticker}`:**
      - the ticker must match `^[A-Z][A-Z0-9.\-]{0,9}$`, else 400 (§3.11, controller half; applies INV-12);
      - an unknown ticker returns 200 with empty lists. This is a ratification item: README `:78` says 404, which is stale;
      - the response holds direct and corroborated signals, excluding superseded records.
   4. **Watchlist endpoints** (`2026-10-09 — Graph and connector wiring fixes — CHOICE — ticker resolution details`, items 2–3; `2026-09-20 — Watchlist backend — CHOICE — core-hub calls ClinicalTrials.gov directly`; archived spec `specs/done/watchlist-backend.md`):
      - list;
      - preview: upper-cases the ticker and calls ClinicalTrials.gov. That call is the exception recorded under INV-4 in `docs/system/invariants.md`; the file links there and restates nothing;
      - add: 201, or 409 on a duplicate ticker. It back-fills matching company tickers; a back-fill failure is logged, not returned;
      - delete: 204;
      - patch gene targets;
      - summary.
   5. `POST /api/dlt/{topic}/replay` exists and needs the write token. Its semantics are in `consumption.md`.
   6. Errors are a structured JSON body, never a stack trace. Timestamps serialize as UTC `Z`, and `confidence_score` serializes in [0, 1].
   7. Actuator exposes `health`, `info` and `prometheus` outside `/api`, read-only.
   8. **Health reporter** (§12; archived spec `specs/done/pipeline-alerting-gaps.md`). A scheduled reporter exports:
      - DLT depth per topic: records after the replay group's committed offset, else after the earliest retained one;
      - the per-source age of the latest signal, read from `signal_current`, so it survives restarts.

      Metric names, and the alerts that read them, link to `docs/operations/observability.md`.

**Verification `Source` cells.** Each ID's `Source` cell contains the source reference of every matrix row that targets it, at document level: the file path, `requirements §N`, the archived spec path, or the full DECISIONS heading text. Line numbers may be added for readers but are not compared. Every citation in a verification cell is in backticks; a heading that itself contains backticks is cited with double backticks. Check M compares these references. Matrix rows whose source is an at-risk class, a scoping label or "same as …" are checked only for the ID's existence. A `divergent` or `pending-decision` row also names its DECISIONS heading.

**Ratification batch.** The implementing session appends `## <merge date> — Living docs — PENDING — core-hub ratification batch` to `DECISIONS.md`. It lists, with IDs, every requirement whose only source is code, a README, a CLAUDE.md trap or a config comment:
- consumption: replay details beyond the archived spec (header stripping, bounded end offsets, at-least-once wording); the MDC fields; the malformed raw payload as a deterministic failure.
- storage:
  - "an applied migration is never edited";
  - the graph-only `Signal` after a DLT;
  - the retirement of the repository-package rule;
  - `MERGE` never `CREATE` for entity nodes beyond §3.7's table.
- corroboration: **the scorer formula** and its read-time computation; the `entity_key` format; the single corroboration kind.
- http-api: 200 with empty lists for an unknown ticker; the constant-time comparison; actuator exposure; the error body.

Each listed row has status `pending-decision`. Its `Source` cell reads `core-hub ratification batch` plus the heading text. The rows stay that way after this spec merges. The owner approves the batch by appending `## <date> — Living docs — CHOICE — core-hub ratification batch`; neither this spec nor the cutover appends it. Once that CHOICE exists, the cutover (step 3) flips the rows to their real status and cites the CHOICE. This spec does not flip them.

**Active and hold specs edited.** For each: add `**Docs impact:**`, replace restated requirement text with IDs, and keep the spec's new work, tests and blockers.

| Spec | Restated or stale text replaced |
|---|---|
| `specs/neo4j-indexing.md` | The constraint and index list (`:12-15`) → the storage graph-model ID. The constraint "Indexes are added via a new Flyway migration (Cypher script in `src/main/resources/db/migration/neo4j/`)" (`:35`) contradicts the current `Neo4jSchemaInitializer`. The spec's `Docs impact` names the storage ID it would change, and the line is rewritten as a proposal, not a fact |
| `specs/kafka-streams-correlation.md` | "`docs/requirements.md §4`" and "§4.1" (`:51,53`) → the COR definition and supersession IDs. The contract-test rule (`:13,25,31`) → the COR contract-test ID. "Step 1.5 REST suite" (`:26`) → the http-api signals ID, with the plan-step name removed |
| `specs/company-program-corroboration.md` | The description of today's scanner and scorer (`:20-21`) → COR IDs. "Flyway `V1`–`V3`" and "next free … `V5` or later" (`:24,34`) → "the next free Flyway version" (V5 is taken). The requirements amendment (`:59`) becomes its `Docs impact`: it changes the COR kinds, definition and score IDs, and adds new COR IDs. The invariant list (`:50-54`) → INV IDs |
| `specs/hold/watchlist-alerts.md` | "Requirements §12 specifies a health reporter…" (`:11`) → the http-api health-reporter ID. The entity-key format (`:17`) → the COR kinds ID. The supersession/dedup wording (`:48`) → the COR record ID. The contract-test rule (`:85`) → the COR contract-test ID |

## Out of scope

- Any change to Java or Python code, tests, Flyway files, `application.yml` or CI. C1 and C5–C8 are recorded, not fixed.
- Owned by `specs/living-docs-system-and-contracts.md` (`docs/system/contracts.md` and `docs/system/invariants.md`):
  - event shapes, `schema_version` rules and identity formulas;
  - the natural-key table and the closed-set values;
  - DLT topic names, partition and headers, and the topic catalogue;
  - invariant text and its exceptions, including restore under INV-2 and the ClinicalTrials.gov call under INV-4.
- Owned by `specs/living-docs-operations.md`: the metric catalogue, the log contract, alert rules and Grafana. The restore runbook (`docs/backup-restore.md`) stays unchanged.
- `docs/README.md`, which `specs/living-docs-system-and-contracts.md` writes in full.
- Trimming `services/core-hub/README.md` and the `requirements.md` § index (`specs/legacy-docs-retirement.md`). `services/core-hub/AGENTS.md` (`specs/agent-instruction-hierarchy.md`).
- Approving the ratification batch (the owner appends the `CHOICE — core-hub ratification batch` entry) and flipping its rows afterwards (the cutover, step 3).
- `specs/signal-browse-views.md`, `specs/lineage-trace-view.md`, `specs/pipeline-control-view.md`: owned by `specs/living-docs-strategy-and-dashboard.md`.

## Constraints

- **Invariants.** The docs apply INV-2, INV-5, INV-10, INV-11 and INV-12 by ID and never restate them. The restore exception lives only under INV-2, and the ClinicalTrials.gov exception only under INV-4. storage.md and http-api.md link there and define no ID for either.
- **Conversion provenance.** Every requirement's `Source` is, in priority order:
  1. a still-true `requirements.md` §;
  2. a `DECISIONS.md` `CHOICE` heading;
  3. an archived spec;
  4. an invariant;
  5. the ratification batch.

  A source that contradicts the code is written as approved, with status `divergent` and a DECISIONS heading. C5 and C6 are written `untested`: not `tested`, because nothing executed proves them, and not `divergent`, because the code reading does not prove a violation.
- **Conflict policy.** Flyway files are locked. A doc that disagrees with an applied migration is wrong. The stale `V4` comment stays, and is noted in `Known traps`. Docs never follow code without a decision.
- **One owner per subject.** Failure classification belongs to `consumption.md`. DLT naming and headers belong to CON. Log format and log content belong to the OPS log contract. The scorer formula belongs to `corroboration.md`. The write token and CORS belong to `http-api.md`.
- **Frozen paths.** None of this spec's files is frozen, and it moves no frozen path.
- **ID rules.**
  - HUB and COR only, numbered with `python3 -m tools.docs_check --next HUB` and `--next COR` in the order listed above (HUB: consumption, then storage, then http-api).
  - Each ID is defined once, with `<a id="NS-NNN"></a>**NS-NNN**`.
  - Cross-domain references use INV, SYS and CON IDs, or a link to the owner file. No ING, EXT, OPS or DSH ID is cited until the spec that writes it has merged into the integration branch.
  - While `ingestion`, `operations` and `dashboard` are in `[rollout] planned_domains`, links to their files are notices, not findings.
- **Decision citations.** Use the full heading text in backticks, without the leading `## `. A defect is cited as an item of `2026-10-15 — Living docs — PENDING — defects found while scoping` (e.g. "item C5"). Cite no decision by register number.
- **Shared files.**
  - `specs/living-docs-cutover-matrix.md`: only the `ID` cells of rows whose `NS` is HUB or COR, plus the `IDs` cells of decisions-table rows classified `binding` whose fragment rows have `NS` HUB or COR (append the IDs space-separated, never remove another domain's).
  - `docs-check.toml`: the `planned_domains` line only.
  - `TODO.md`: this spec's row only.
- No "will" or future work in `docs/`, and no plan-step names.

## Dependencies

- **Needs:**
  - `specs/docs-check-tooling.md`;
  - `specs/living-docs-system-and-contracts.md`: INV, CON and `docs/README.md`;
  - the PENDING headings above.
- **Hands to later specs.** HUB and COR IDs are cited by:
  - `specs/living-docs-ingestion.md`: the ticker allowlist, and the corroboration-review gate's subject;
  - `specs/living-docs-research.md`: `corroborated_at` as the only join field;
  - `specs/living-docs-strategy-and-dashboard.md`: corroborated-event consumption, the dashboard write token;
  - `specs/living-docs-operations.md`: the health reporter, DLT replay in runbooks;
  - `specs/agent-instruction-hierarchy.md`: `services/core-hub/AGENTS.md` ID pointers;
  - `specs/legacy-docs-retirement.md`: README links, and § index rows for §3.7–§3.12, §4 and §9.

  It also hands the ratification-batch heading to `specs/living-docs-cutover.md` for its final gate.

## Affected files

| Path | Action |
|---|---|
| `docs/core-hub/consumption.md` | create |
| `docs/core-hub/storage.md` | create |
| `docs/core-hub/corroboration.md` | create |
| `docs/core-hub/http-api.md` | create |
| `DECISIONS.md` | modify (append the core-hub ratification-batch entry only) |
| `specs/living-docs-cutover-matrix.md` | modify (the `ID` cells of HUB and COR rows; the `IDs` cells of binding decisions rows whose fragment rows have `NS` HUB or COR) |
| `docs-check.toml` | modify (`[rollout] planned_domains` line only: remove `core-hub`) |
| `TODO.md` | modify (this spec's row only) |
| `specs/living-docs-core-hub.md` → `specs/done/living-docs-core-hub.md` | move (status `done`) |
| `specs/neo4j-indexing.md` | modify |
| `specs/kafka-streams-correlation.md` | modify |
| `specs/company-program-corroboration.md` | modify |
| `specs/hold/watchlist-alerts.md` | modify |
| `services/core-hub/README.md`, `services/core-hub/CLAUDE.md`, `services/CLAUDE.md`, `docs/requirements.md` | untouched-but-cited (trimmed by `specs/agent-instruction-hierarchy.md` and `specs/legacy-docs-retirement.md`) |
| `docs/README.md` | untouched (owned by `specs/living-docs-system-and-contracts.md`) |
| `services/core-hub/src/main/resources/db/migration/V1…V5__*.sql` | untouched-but-cited (frozen) |
| `services/core-hub/src/**`, `services/strategy/src/auspex_strategy/runtime/events.py` | untouched-but-cited (verification rows, items C1 and C5–C8) |

## Required tests

Run these from the repo root on the spec branch. Findings are `CHECK path:line message` lines from `python3 -m tools.docs_check`. `OWN` stands for `docs/core-hub/**,specs/neo4j-indexing.md,specs/kafka-streams-correlation.md,specs/company-program-corroboration.md,specs/hold/watchlist-alerts.md`.

- `core_hub_docs_pass_structure_check`: `python3 -m tools.docs_check --only E --paths 'docs/core-hub/**'` exits 0. Fails on a missing header line or required H2, or a `Last reviewed against` SHA that is not an ancestor of HEAD.
- `core_hub_ids_are_unique_and_resolve`: `python3 -m tools.docs_check --only C,D --paths "$OWN"` exits 0. Fails on:
  - a duplicate ID;
  - `CON-?` (a finding once `system` has left `planned_domains`);
  - an unresolved INV or CON ID;
  - a cited DECISIONS heading that does not exist;
  - a register number.
- `every_core_hub_id_has_one_verification_row_and_tested_rows_name_real_tests`: `python3 -m tools.docs_check --only K --paths 'docs/core-hub/**'` exits 0. Fails if a `tested` row's `path::name` is not a `void name(` in that Java file, or if `Source` is empty.
- `matrix_rows_for_core_hub_all_have_assigned_ids`: `python3 -m tools.docs_check --matrix specs/living-docs-cutover-matrix.md --domain HUB` exits 0. Fails on a row with no defined ID, or on an ID whose `Source` lacks the row's source reference.
- `matrix_rows_for_corroboration_all_have_assigned_ids`: the same with `--domain COR`.
- `binding_decisions_for_core_hub_carry_ids`: `python3 -m tools.docs_check --matrix specs/living-docs-cutover-matrix.md --decisions --domain HUB`, and the same with `--domain COR`, each exit 0. The eight headings under "Decision headings this spec absorbs" each have a HUB or COR ID in their `IDs` cell, and that ID's `Source` contains the heading text.
- `edited_specs_carry_docs_impact`: `python3 -m tools.docs_check --only E --paths "$OWN"` exits 0.
- `c5_to_c8_are_not_marked_tested`: `grep -nE "ack-mode|RECORD|@Valid|unknown closed-set|at-least-once" docs/core-hub/*.md | grep -E "\| tested \|"` prints nothing. Fails if any of the four is presented as proven.
- `misnamed_tests_are_not_cited_for_their_names`:
  - `grep -n "test_unknown_enum_value_goes_to_dlt" docs/core-hub/*.md` appears only on the unknown-major-version row;
  - `grep -n "test_neo4j_failure_prevents_offset_commit" docs/core-hub/*.md | grep -w tested` prints nothing, because that test does not prove the offset was not committed.
- `failure_classification_has_one_owner`: `grep -rln "never clamped\|dead-letter.*at once\|to the DLT at once" docs/` lists only `docs/core-hub/consumption.md`. Fails if another doc restates which failures dead-letter.
- `every_failure_class_has_its_own_row`: consumption.md's verification table has one row each for malformed JSON, naive timestamp, unknown major `schema_version`, missing `confidence_score`, out-of-range `confidence_score`, invalid closed-set value and malformed raw payload. The rows for malformed JSON, naive timestamp and unknown major are `tested` and name the tests listed above. The closed-set row is `divergent` and cites `closed sets on the wire`. Fails on a merged row or a missing test name.
- `logs_link_the_log_contract`: `grep -n "raw_content\|INV-6" docs/core-hub/consumption.md` prints nothing, and `grep -c "operations/observability.md" docs/core-hub/consumption.md` is at least 1.
- `scorer_formula_has_one_owner`: `grep -rln "0.7 × diversity\|0\.7 \* diversity" docs/` lists only `docs/core-hub/corroboration.md`. Fails on a copy anywhere else in `docs/`.
- `write_token_and_cors_have_one_owner`: `grep -rln "CORE_HUB_WRITE_TOKEN" docs/` lists `docs/core-hub/http-api.md`. Any other file it lists mentions the token only in a link line to `http-api.md`.
- `no_user_id_rule_is_in_storage`: `grep -n "user_id" docs/core-hub/storage.md` prints the single-user requirement line.
- `restore_exception_not_restated`: `grep -n "empty stores\|restore" docs/core-hub/storage.md` prints only one line, and that line links to `docs/system/invariants.md#INV-2`. No `HUB-` anchor is on it.
- `ctgov_exception_under_inv4`: `grep -n "ClinicalTrials.gov" docs/core-hub/http-api.md` lines link `docs/system/invariants.md#INV-4`, and none mention `INV-2`.
- `divergent_rows_cite_a_decision`: every verification row with status `divergent` or `pending-decision` in `docs/core-hub/*.md` names a `PENDING` or `CHOICE` heading. Check with `awk -F'|' '$5 ~ /divergent|pending-decision/ && $3 !~ /— (PENDING|CHOICE) —/' docs/core-hub/*.md`, which must print nothing.
- `ratification_batch_lists_every_pending_row`: the IDs whose `Source` contains `core-hub ratification batch` in `docs/core-hub/*.md` equal the IDs listed in the new `PENDING — core-hub ratification batch` entry. They are compared with `grep -o`/`sort`/`diff`, shown in the PR description.
- `stale_flyway_numbers_removed_from_company_program_spec`: `grep -n "V1\`–\`V3\|V5\` or later" specs/company-program-corroboration.md` prints nothing.
- `core_hub_left_planned_domains`: `grep -n '^planned_domains' docs-check.toml | grep -c '"core-hub"'` prints `0`, and `python3 -m tools.docs_check --only F --paths 'docs-check.toml'` exits 0.
- `no_application_file_changed`: `git diff --name-only origin/feature/living-docs-integration...HEAD` lists only the paths marked create, modify or move.

## Definition of done

```bash
git fetch origin feature/living-docs-integration
OWN='docs/core-hub/**,specs/neo4j-indexing.md,specs/kafka-streams-correlation.md,specs/company-program-corroboration.md,specs/hold/watchlist-alerts.md'
python3 -m tools.docs_check --paths "$OWN"; echo "own findings: $?"
python3 -m tools.docs_check --matrix specs/living-docs-cutover-matrix.md --domain HUB; echo "HUB matrix: $?"
python3 -m tools.docs_check --matrix specs/living-docs-cutover-matrix.md --domain COR; echo "COR matrix: $?"
python3 -m tools.docs_check --matrix specs/living-docs-cutover-matrix.md --decisions --domain HUB; echo "HUB decisions: $?"
python3 -m tools.docs_check --matrix specs/living-docs-cutover-matrix.md --decisions --domain COR; echo "COR decisions: $?"
grep -rln "0.7 × diversity" docs/
# last step: remove "core-hub" from [rollout] planned_domains in docs-check.toml, then
python3 -m tools.docs_check --only F --paths 'docs-check.toml'; echo "planned: $?"
git diff --name-only origin/feature/living-docs-integration...HEAD
```

Expected:
- `own findings: 0`;
- `HUB matrix: 0` and `COR matrix: 0`;
- `HUB decisions: 0` and `COR decisions: 0`;
- the scorer grep prints only `docs/core-hub/corroboration.md`;
- `planned: 0`;
- the diff lists exactly the create, modify and move paths in Affected files.

## Compatibility

- **Readers.** `services/core-hub/README.md`, the CLAUDE.md files and `docs/requirements.md` stay unchanged until `specs/agent-instruction-hierarchy.md` and `specs/legacy-docs-retirement.md`. Nothing reaches `develop` before cutover (`2026-10-15 — Living docs — PENDING — rollout branch model`).
- **Links.** The 4 edited specs keep their paths. `company-program-corroboration.md` keeps its `Blocked by` on the §4/§9 amendment, now phrased as the COR IDs it will change.
- **Agents.** `CorroborationServiceContractTest`, the Flyway-frozen rule and the DLT trap stay in `services/core-hub/CLAUDE.md` until `specs/agent-instruction-hierarchy.md` replaces them with ID pointers.
- **Tests.** No test reads `docs/core-hub/`, and no Java or Python test changes.

## Rollback

On `feature/living-docs-integration`, revert this spec's merge range in one PR:
1. `git revert --no-commit <integration-branch tip before the merge>..<tip after>`. The range includes the spec's first commit.
2. Keep `DECISIONS.md` as it is at the tip: `git restore --source=HEAD --staged --worktree DECISIONS.md`. A rollback never deletes a DECISIONS entry.
3. Append `## <date> — Living docs — FLAG — core-hub docs rolled back`. It names the reverted range and states that the core-hub ratification batch entry no longer has IDs behind it.
4. Commit once.

The revert removes `docs/core-hub/`. It restores the 4 specs, the matrix ID cells, the `planned_domains` line, the TODO row and the spec's path. Specs that already cite HUB or COR IDs then fail check D, and must be rebased onto the reverted head.

## Notes

- **C5 and C6 need execution to settle.** Two tests would turn `untested` into `tested` or `divergent`: a unit test asserting `factory.getContainerProperties().getAckMode()`, and an integration test publishing `confidence_score: 1.5` and a payload without it. Both belong in a fix spec that answers `2026-10-15 — Living docs — PENDING — defects found while scoping`, not here.
- **The scorer formula is a ratification item, and is time-dependent.** Its recency term uses the wall clock, so a historical score changes with the run date. `specs/company-program-corroboration.md` proposes an `as_of` parameter. Until that merges, the approved text describes today's behaviour, and its `Rationale` links the proposal.
- **Failure classification is HUB's.** `specs/living-docs-cutover-design.md` §2 and the ownership decision for the rollout give "which failures dead-letter" to `consumption.md`, and DLT naming and headers to CON. If `docs/system/contracts.md` also lists the failure classes when this spec starts, stop and flag rather than writing a second divergent row.
- **Health reporter placement.** `specs/living-docs-cutover-design.md` §2 puts the health reporter in `http-api.md`. This spec follows that.
- **Natural keys.** `specs/living-docs-cutover-design.md` §2 gives the per-path key table to `contracts.md`. `storage.md` applies it, and owns the conflict behaviour of core-hub's own writes (first observation wins, edge replacement). If `docs/system/contracts.md` does not carry the table, stop and flag rather than writing it here.
- **The README says `source_observation` is one row per (event_id, source_type)** (`README.md:33`). The key also includes `external_id`. The matrix marks the README row `delete`, because it is wrong and the key is CON's.
- `CorroborationServiceContractTest` has two tests named after the dropped watermark. Renaming them is a code change for the fix spec; the verification table cites them by their current names.
- Exact PENDING titles are those committed on the scoping branch. If one differs from the text above, use the committed one.

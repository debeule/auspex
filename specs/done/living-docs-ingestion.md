# Living docs: ingestion and extraction

> Archived. Not authoritative: current behaviour is in docs/ (see docs/README.md).

**Status:** done
**Blocked by:**
1. `specs/docs-check-tooling.md` merged into `feature/living-docs-integration`: `python3 -m tools.docs_check` with `--next`, `--paths`, check M (`--matrix … --domain NS` and `--matrix … --decisions`) and `docs-check.toml` with `[rollout] planned_domains`.
2. `specs/living-docs-system-and-contracts.md` merged into the integration branch: `docs/system/invariants.md` (INV-1 … INV-15) and `docs/system/contracts.md` (CON IDs for the raw pointer, the signal event, identity, closed sets and the DLT) must exist before this spec cites them. No `CON-?` placeholder may be left.
3. These `DECISIONS.md` entries, appended on the scoping branch. The docs cite each heading, and the later `CHOICE` once the owner answers:
   - `2026-10-15 — Living docs — PENDING — initial_lookback value`
   - `2026-10-15 — Living docs — PENDING — fda_approval source`
   - `2026-10-15 — Living docs — PENDING — run_pipeline.py support`
   - `2026-10-15 — Living docs — PENDING — raw-pointer contract`, consumed only through the CON IDs that `specs/living-docs-system-and-contracts.md` writes
   - `2026-10-15 — Living docs — PENDING — RunResult counters`
   - `2026-10-15 — Living docs — PENDING — defects found while scoping`, cited by every `divergent` row below that the headings above do not cover

**Branch:** `feature/living-docs-ingestion`
**Docs impact:** creates `docs/ingestion/connectors.md`, `docs/ingestion/pipeline.md`, `docs/ingestion/extraction.md` (namespaces ING and EXT, all new IDs). Modifies the 7 active and hold specs listed under Affected files (adds `Docs impact`, replaces restated requirements with IDs). Appends one `PENDING` ratification-batch entry to `DECISIONS.md`. Fills the `ID` cells of the ING and EXT rows of `specs/living-docs-cutover-matrix.md` and the `IDs` cells of its binding decisions rows for ING and EXT. Removes `ingestion` from `docs-check.toml` `[rollout] planned_domains`. Does not change `services/ingestion-scraper/README.md`, `docs/requirements.md` or `docs/local-model-runbook.md` (`specs/legacy-docs-retirement.md` trims the first two; the runbook keeps its role).

---

## Context

At develop `e51f742` the ingestion and extraction rules are spread over seven kinds of source. None of them is the single owner:

| Source | What it holds | Standing |
|---|---|---|
| `docs/requirements.md` §5, §6.1–§6.9, §7, §7.1, §10.4 (re-extraction paragraph), §11.1–§11.3, §12 (scraper half), §13 (named guards) | Connector contract, pipeline, rate limits, timestamps, verified APIs, archive and dedup, extraction contract, golden set | Normative today, but stale in places. §6.2 (`requirements.md:167`) gives the order "pre-filter → dedup → MinIO archive", while the code archives first (`services/ingestion-scraper/src/auspex_ingest/pipeline.py:84`), and §7 (`:234`), §7.1 (`:246`) and invariant 13 agree with the code. §0.3 (`:13`) says a 90-day `initial_lookback`, but `services/ingestion-scraper/config/sources.yaml:22,47,71,95,114` set 30 |
| `services/ingestion-scraper/README.md` | Pipeline stages (`:7-18`), scheduling (`:20-22`), connectors table (`:26-35`), adding a connector (`:39-45`), `sources.yaml` schema (`:49-62`), scripts (`:90-101`), known API constraints (`:105-111`) | Not normative, but the only home of several rules (processed markers, extraction cap, 409, SEC split, corroboration-review gate). Also wrong in places. Stage 7 names `HgncEntityNormalizer`, while production wires `IdentityNormalizer` (`pipeline_factory.py:52`). Stage 8 says the raw pointer goes out for "(all)" documents, while `pipeline.py:159` publishes it only for published signals. `fda_approval` is listed "Active" but is absent from `sources.yaml`. `epo_ops` is listed "Blocked" but is scheduled (`sources.yaml:111-112`) |
| `services/ingestion-scraper/config/sources.yaml:1-3` | Comments on schedule, `rate_limit_rps`, `max_documents_per_run` | Machine authority for values |
| `config/models/registry.yaml`, `config/models/local_candidates.yaml:1-17` | Model entries; the comment that `num_ctx` holds only with `OLLAMA_CONTEXT_LENGTH` ≥ `num_ctx` | Machine authority. `config/models/scores/` holds only `.gitkeep`, so no model passes the gate today |
| `docs/local-model-runbook.md` | Install, register, gate and switch to an Ollama model | Runbook. Requirements in it: gate at `is_signal` precision ≥ 0.85 (`:67`), refusal without a passing record (`:67`), digest pinning (`:55`), context length (`:31`) |
| `DECISIONS.md` `CHOICE` entries | Processed markers, cursor rule, extraction cap, rate limiter, EDGAR 403 stop, SEC budget, EDGAR filing index, publish threshold default, calibrated thresholds before launch, gate threshold, model decision rule, company-level fields, the patent source | Binding until absorbed. Each is classified in the Decisions table of `specs/living-docs-cutover-matrix.md` |
| Code and scripts | `model_evaluation.py:11` `GATE_PRECISION = 0.85`; `scripts/score_corroboration_review.py:23` `PRECISION_THRESHOLD = 0.85`, exit 2 below it (`:81`); `scripts/check_leakage.py:18` `_FLAG_THRESHOLD = 0.70`; `extraction_backend.py:29` `_MAX_CONTENT_CHARS = 4_000` | The only source for the corroboration-review gate, the leakage canary and the truncation limit |

Code entry points are all under `services/ingestion-scraper/src/auspex_ingest/`:
- `connectors/base.py` (`SourceConnector`) and `connectors/registry.py:49,71,114` (`UnknownSourceTypeError`, `register`, `default_registry`).
- `connectors/rate_limited_client.py`.
- The six registered connectors plus `mock.py`. `fda_approval.py:138` registers `fda_approval`, which no `sources.yaml` entry configures; `tests/unit/test_fda_regulatory.py` has 11 tests for it.
- `sources.py:9-27`: `SourceEntry`, `extra="forbid"`, `min_confidence_to_publish` default 0.0.
- `pipeline.py`: `RunResult` `:16-29`; archive `:84`; publish `:159-160`; canonical marker `:168`; flush `:189`; processed markers `:205`.
- `storage/minio_client.py:13-64`: object key, processed and canonical markers.
- `messaging/kafka_producer.py`.
- `prefilter.py`: `PREFILTER_VERSION`; `passes` reads only `raw_content` (`:17-20`).
- `extraction_backend.py`: `ollama_digest_lookup` reads `/api/tags` (`:96-102`); `_verify_digest` `:120`; `_check_gate` `:136`; delimited block `:199`; vocabulary drop `:229-230`; deprecation warning `:317-323`.
- `extractor.py` (`EventType`, `resolve_trial_ids`), `model_evaluation.py`, `sampling.py`, `reextract.py`.
- `api.py`: routes `:39-102`; per-source lock and 409 `:37,60-62`.
- Scripts: `services/ingestion-scraper/scripts/*.py` (9 files).

Defects already found and recorded, not fixed here. Each one is written `divergent` or `untested` and cites `2026-10-15 — Living docs — PENDING — defects found while scoping` unless another heading is named:
- The canonical marker is written before `flush()` (`pipeline.py:168` vs `:189`).
- A cross-source canonical hit records no observation (`pipeline.py:102-105`).
- `RunResult` has no `deduped`/`extracted`, and dedup skips count as `prefiltered_out` (heading: `RunResult counters`).
- Two §11.2 tests are vacuous: `test_injected_instruction_in_raw_content_does_not_change_extracted_entities` and `test_gene_target_outside_controlled_vocabulary_is_flagged_not_written`.
- The prompt has no "data, never instruction" statement, and production passes no gene vocabulary.
- `ReextractionRunner` ignores `skip_prefilter`. `POST /reextract` ignores `prompt_version` and `model`. `since`/`until` replace the offset (`reextract.py:27-28,52`).
- PubMed month-only dates default to day 1 (`pubmed.py` `_parse_date`).
- Source-specific dates live only inside `raw_content`.
- The run summary has no "cursor before and after".
- No test exercises delivery-report failure against the real producer client.
- The golden set has no `epo_ops` document.

`docs/ingestion/` does not exist.

### Living-doc format (enforced by checks C, D, E and K of `tools/docs_check`)

- **Header.** Line 2 of every file reads `Domain: <NS> · Code: <paths> · Last reviewed against: develop @ <sha>`.
- **Sections.** Required H2s, in order: `Scope`, `Requirements`, `Verification`, `Retired requirements`. `Rationale` and `Known traps` are optional H2s placed after `Requirements`.
- **Requirements.** Each requirement is one list item. It starts with its anchor and bold ID, `<a id="ING-NNN"></a>**ING-NNN**`, followed by one normative sentence (more only where needed).
- **Verification table.** Columns `| ID | Source | Verified by | Status |`. One row per active ID.
- **Status values:** `tested` (Verified by names `path::name` tests), `enforced` (a config or build rule), `untested`, `divergent` (approved behaviour the code does not have; Source names the DECISIONS heading), `pending-decision` (Source names the PENDING heading).
- **Retired requirements.** Each entry keeps its ID, its original text, the date and the DECISIONS heading or source that retired it. Retired IDs are never reused.

## What this builds

Three living specs that become the only prose authority for ingestion and extraction:

1. **`docs/ingestion/connectors.md`** (ING). Scope: the `SourceConnector` contract; the registry and `sources.yaml` semantics (the doc names the file and never copies a value from it); `RawDocument` as connector output; typed `canonical_id` per source; per-source `published_date` rules; rate limiting per host; verified source APIs; and the source traps (SEC, EPO OPS, openFDA, ClinicalTrials.gov, patents, PubMed). Requirements, in this order:
   1. `fetch_since` fetches and maps only, is synchronous and returns an iterator. It never writes MinIO, calls the model or publishes (§6.1; applies INV-3, INV-8).
   2. A new source is a connector module registered with `REGISTRY.register` plus a `sources.yaml` entry. An unregistered `source_type` raises `UnknownSourceTypeError` naming the registered ones (applies INV-4).
   3. `sources.yaml` is parsed strictly: unknown fields and duplicate `source_type`s are rejected at parse time.
   4. A source with no saved cursor starts at now minus its `initial_lookback`, read from its `sources.yaml` entry. The doc names the field and copies no number. Status `pending-decision`, citing `2026-10-15 — Living docs — PENDING — initial_lookback value`.
   5. Every HTTP request goes through one `RateLimitedClient`, with one bucket per registered host, shared by subdomains and by every connector on that host. Requests are evenly spaced with no burst, and wait for their slot instead of failing (§6.5; `2026-10-10 — Ingestion run reliability — CHOICE — rate limiter spaces requests evenly, with no burst`).
   6. Each configured `rate_limit_rps` stays at or below the verified limit of its host. The §6.5 host table, including the openFDA row (1,000 requests a day without a key), is kept in this doc as verified API facts. The cross-container SEC budget links to `docs/operations/topology.md`; this doc owns only the per-connector rate (`2026-10-09 — Soak-test readiness — CHOICE — SEC request budget across containers`).
   7. A 403 from any `*.sec.gov` request ends the EDGAR run with `SecRequestRefused`, with no further SEC requests (`2026-10-10 — Ingestion run reliability — CHOICE — a 403 on a filing index also stops the EDGAR run`).
   8. `canonical_id` is typed (`doi:`, `nct:`, `edgar:`, `epo-app:`, `fda:`) or absent. A source that can supply one supplies it for every document or fails loudly (§10.1). PubMed is `divergent`: it marks itself `provides_canonical_id=False` while sometimes carrying a DOI.
   9. `published_date` is the moment the information became public, UTC-aware. Non-public dates never feed point-in-time alignment (§6.7 rule). There is one requirement per source row:
      - bioRxiv: version date.
      - PubMed: earliest public availability. `divergent`: partial dates default to day 1 (`pubmed.py` `_parse_date`).
      - Patents: pre-grant publication, else grant.
      - ClinicalTrials.gov: first post, or last update post on an amended fetch.
      - EDGAR: acceptance time converted from US Eastern to UTC, else the file date after the filing cutoff.
      - Regulatory (`fda_approval`): action date.
   10. Source-specific non-public dates are retained (§6.3). `divergent`: they are kept only inside `raw_content`.
   11. EDGAR keeps 8-Ks with item 2.02, 7.01 or 8.01. Exhibit 99.1 leads `raw_content`, followed by the cover. Documents and acceptance time come from the filing's `-index.htm`. The company CIK is `ciks[0]` (`2026-10-07 — EDGAR press-release content — CHOICE — filing index replaces the submissions lookup`).
   12. Patents come from EPO OPS. `canonical_id` is `epo-app:` from the application reference, so the pre-grant publication and its grant share one `event_id`; `external_id` is the publication reference `CC-NUM-KIND` (`2026-08-15 — Step 2.3 — CHOICE — Patent connector: PatentsView → Lens.org → EPO OPS (final)`; `2026-08-15 — Step 2.3 — CHOICE — Patent connector changed from Lens.org to EPO OPS`).
   13. ClinicalTrials.gov `raw_content` carries the lead sponsor (`2026-10-07 — Company-level extraction — CHOICE — event taxonomy and identifier fields (schema 1.1)`, item 5).
   14. `fda_approval` is an approved source (FDA approvals, labels and shortages through openFDA, §6.9). Status `divergent`, citing `2026-10-15 — Living docs — PENDING — fda_approval source`: the connector is registered and tested, but no `sources.yaml` entry configures it. The status changes when a config spec adds the entry, or when the owner's answer retires the requirement.

   `Retired requirements` holds one entry: the optional `fda_designation` source_type (§6.9), with its original text. Its reason is that openFDA has no designations endpoint (§6.9) and the source was never built. It is listed in the ratification batch.

   Known traps: the SEC `User-Agent`, the IP block and how retrying extends it, EFTS field names, the `submissions` window, the filing-agent CIK; PatentsView and Lens.org are unusable; EPO token refresh; openFDA has no designations endpoint, and its daily cap binds without a key; ClinicalTrials.gov `filter.advanced` syntax; patent `filed_date` and trial `first_submitted_date` are not public dates. Each trap names the requirement it protects.

2. **`docs/ingestion/pipeline.md`** (ING, continuing the numbering). Scope: everything between a connector yielding a document and Kafka acknowledging it, plus the scraper HTTP API. Requirements, in this order:
   1. For each document the stages run in this order: archive, unchanged re-fetch check, cross-source canonical check, pre-filter, extraction cap, extract, normalize, publish. The archive write is unconditional and comes before every other side effect (applies INV-13). The `Rationale` section records that `requirements.md` §6.2 listed a different order, and that order was stale.
   2. `IngestionPipeline` is the single caller of the connector, archive, extractor and producer (§6.2).
   3. A failing document is recorded and the run continues (§6.2, per-document isolation).
   4. `RunResult` fields and what each counts, as the code has them. A field no test asserts is `untested`. Status `pending-decision`, citing `2026-10-15 — Living docs — PENDING — RunResult counters`. `deduped` and `extracted` from §6.2 go to `Retired requirements` under the same heading.
   5. The pipeline is stateless with respect to cursors. It takes a cursor and returns `next_cursor` (§5; `2026-10-09 — Soak-test readiness — CHOICE — cursor after a run with failed documents`):
      - the earliest `published_date` among failed documents;
      - else the latest processed date;
      - or the input cursor, when the run stopped at the cap or delivery was not confirmed.

      The DAG side (save, then fail; Variables under Fernet) links to `docs/operations/orchestration.md`.
   6. A run sends at most `max_documents_per_run` documents to extraction. Documents skipped as already processed do not count (`2026-10-10 — Ingestion run reliability — CHOICE — schedule times, extraction cap and task timeout`).
   7. `POST /ingest/<source_type>` refuses a second concurrent run of the same source with 409, and does not block other sources.
   8. Publish is not fire-and-forget: the run flushes and checks delivery reports, and an undelivered message fails the run (§6.2). Status `untested` for the real client.
   9. The archive object key is `raw/{source_type}/{external_id}/{retrieved_at UTC}-{sha8}.json` (§7; applies INV-9). A same-second re-fetch of identical content is a no-op, not an error.
   10. Dedup gates extraction and publish only, never the archive (§7.1.2).
   11. Processed markers are written only after a document's outcome is final and the run's flush succeeded. They are keyed on content hash and on the identity `model|prompt_version|prefilter_version`. A re-fetch with a matching marker skips extraction and publish (§7.1.3; `2026-10-07 — Live ingestion — CHOICE — unchanged re-fetch skip with retry-safe markers`).
   12. An amendment (different content hash) is extracted and published under the same `event_id`, with a new `extraction_id` (§7.1.4). The identity formula links to CON.
   13. Cross-source canonical markers are written after a successful publish (§7.1.5). `divergent`: they are written before `flush()`.
   14. A later fetch of a canonical id first published by another source skips extraction and records an observation (§7.1.5). `divergent`: nothing is recorded. The raw-pointer scope in CON follows `2026-10-15 — Living docs — PENDING — raw-pointer contract`.
   15. Without a `canonical_id`, cross-source duplicates are accepted (§7.1.6).
   16. A deterministic vocabulary pre-filter runs before every model call, and its rejections are counted (§6.6). The vocabulary is per source in `sources.yaml`. It is matched against `raw_content`, which `RawDocument` uses for title and body alike. This is a ratification item: §6.6 says "title or content".
   17. Entity values pass through the `EntityNormalizer` seam on every event; production wires the identity implementation (§6.4).
   18. The HTTP API (applies INV-3):
       - `GET /health`;
       - `GET /sources`;
       - `POST /ingest/<source_type>`: 404 for an unconfigured source, 500 with the error on a pipeline exception, and an absent cursor means connectors requirement 4;
       - `POST /reextract` (semantics in extraction.md);
       - `GET /metrics`.

       Metric names, metric-registration traps and alert intent link to `docs/operations/observability.md`.
   19. Each run logs its `RunResult` summary (§12). The log format and the fields every log line carries (structured JSON, `source_type`, `external_id`/`event_id`, nothing sensitive) are owned by the log contract in `docs/operations/observability.md`; pipeline.md links it and restates none of it. The run summary's "cursor before and after" (§12) is `divergent`.

   pipeline.md also:
   - states that the scraper writes only MinIO and Kafka, by linking INV-1;
   - states that the raw pointer and the signal event are CON IDs (no field list here);
   - says in its Scope note that `scripts/run_pipeline.py` carries no requirement until `2026-10-15 — Living docs — PENDING — run_pipeline.py support` is answered (a Scope note, not an ID).

3. **`docs/ingestion/extraction.md`** (EXT). Scope: the extraction contract; untrusted input; prompt and pre-filter versioning; the model registry and digest; the gate; re-extraction; and the quality tooling that decides whether a model or a corroboration sample is good enough. Requirements, in this order:
   1. `extract` returns an event or `None`, and the model decides through `is_signal`. `None` is archived, counted as `not_signal`, and publishes nothing (§11.1).
   2. `min_confidence_to_publish` is set per source, default 0.0 (off). A raised threshold counts drops as `below_threshold` (§11.1; `2026-10-09 — Graph and connector wiring fixes — CHOICE — publish threshold default is 0.0, not the API's 0.5`).
   3. Content reaches the model inside a delimited block, with a system instruction that everything inside is data. `divergent`: the prompt has no such statement.
   4. `raw_content` is truncated to the documented maximum, `_MAX_CONTENT_CHARS` in `extraction_backend.py` (§11.2). The doc names the constant.
   5. Extracted `gene_targets` are checked against a controlled vocabulary, and unknown symbols go to review, not the graph. `divergent`: production passes no vocabulary, and a set vocabulary drops symbols silently.
   6. An extracted ticker is validated before a graph write. `untested` on the scraper side; the controller allowlist is HUB's (link to `docs/core-hub/http-api.md`).
   7. The prompt is a versioned file under `services/ingestion-scraper/prompts/extraction/`. Every event carries `prompt_version` and `prefilter_version`. Production reads `EXTRACTION_PROMPT_VERSION` (§11.3; `2026-10-07 — Local model integration — CHOICE — gate threshold and version labels aligned`).
   8. An unknown `event_type` from the model is recorded as `other`. `trial_ids` keep only `NCT` + 8 digits, upper-cased, and always include the document's own trial when `canonical_id` is `nct:` (`2026-10-07 — Company-level extraction — CHOICE — event taxonomy and identifier fields (schema 1.1)`, item 3). The closed set itself links to CON.
   9. Every registry entry carries the required fields. A local entry pins a digest. An unknown model or a moving alias fails at startup.
   10. At startup the registered digest is compared with the model server's `/api/tags` listing, and a mismatch refuses to start. An unreachable server logs a warning, and the digest is checked before the first extraction.
   11. A prompt longer than `num_ctx` fails loudly instead of being truncated.
   12. The service refuses a model without a passing gate record at the active prompt and pre-filter versions (`GateNotPassedError`).
   13. The model gate passes at `is_signal` precision ≥ 0.85 on the golden set (`GATE_PRECISION`). `score_extraction.py` writes the gate record (`2026-10-07 — Local model integration — CHOICE — gate threshold and version labels aligned`; `2026-09-19 — Historical backfill — CHOICE — Option A: local model for backfill, API model forward-only`).
   14. A model choice follows a decision rule recorded in `DECISIONS.md` before any gate run. The rule in force is `2026-10-08 — First run on the stack machine — CHOICE — local model decision rule, fixed before the gate runs`. Status `untested`, since it is a process rule.
   15. The golden set (§11.3):
       - spans every configured `source_type` and both `is_signal` classes;
       - scores per-field precision and recall, the confusion matrix, calibration and pre-filter false negatives;
       - runs by hand, never in CI.

       Status `divergent` for `epo_ops` coverage.
   16. The leakage canary flags a model whose answers are correct in at least the canary threshold of months after its claimed cutoff. It is deterministic given a seed (`check_leakage.py`; ratification item).
   17. Cross-model comparison reports agreement (Jaccard, directionality, confidence correlation), deterministic given a seed (`compare_models.py`; ratification item).
   18. A corroboration sample is reviewed by hand and passes at precision ≥ 0.85. `score_corroboration_review.py` exits non-zero below it, and sampling is deterministic given a seed. This is a ratification item: its only sources are the README and `docs/HISTORY.md:96`. `sample_corroborations.py` reads Postgres and Neo4j; that read-only scope is stated under INV-1 (link).
   19. Re-extraction is an explicit operation over the MinIO archive (CLI and `POST /reextract`), never a side effect of a routine run. It writes a new `extraction_id` under the same `event_id` and never touches the cursor (§10.4). `divergent` items:
       - `skip_prefilter` is ignored;
       - the HTTP path ignores `prompt_version` and `model`;
       - `since`/`until` replace the offset.
   20. The model server is reached through an OpenAI-compatible endpoint (`EXTRACTION_BASE_URL`), using the registry's mode, timeout, temperature and seed (archived spec `specs/done/local-model-integration.md`).
   21. Before launch, every source's `min_confidence_to_publish` is calibrated on the golden set and set from that calibration (`2026-10-09 — Graph and connector wiring fixes — CHOICE — calibrated publish thresholds before launch`). Status `untested`: the work is owned by `specs/golden-set-expansion.md`, which the row names in `Verified by`.

   Machine-readable authorities: `config/models/registry.yaml`, `config/models/local_candidates.yaml` and `config/models/scores/` (gate records). Readiness ("no passing record yet") is not stated here; it belongs to `SETUP.md` and `specs/first-run-on-stack-machine.md`. Known traps: Ollama context length and tag re-pointing, each pointing to `docs/local-model-runbook.md` for the procedure. The Docker Desktop/Metal trap (the model server runs on the host) is owned by `docs/operations/topology.md`; extraction.md links to it and restates nothing.

The `Verification` table of each file names a real test as `path::name` for every `tested` row. The candidate tests are listed in the matrix rows' Notes. The two vacuous tests named under Context are never cited as `tested`.

**Verification `Source` cells.** Each ID's `Source` cell contains the source reference of every matrix row that targets it, at document level: the file path, `requirements §N`, the archived spec path, or the full DECISIONS heading text. Line numbers may be added for readers but are not compared. Every citation in a verification cell is in backticks; a heading that itself contains backticks is cited with double backticks. Check M compares these references. Matrix rows whose source is an at-risk class, a scoping label or "same as …" are checked only for the ID's existence. A `divergent` or `pending-decision` row also names its DECISIONS heading.

**Ratification batch.** The implementing session appends `## <merge date> — Living docs — PENDING — ingestion ratification batch` to `DECISIONS.md`. The entry lists, with its ID, each requirement whose only source is code, a README, a CLAUDE.md trap or a config comment, plus the one retirement that has no decision behind it:
- connectors:
  - the registry error naming registered types;
  - strict `sources.yaml` parsing;
  - the `fda:` prefix;
  - EDGAR `-index.htm` details beyond the CHOICE (inline-XBRL links, EFTS dedup by accession);
  - ClinicalTrials.gov `filter.advanced`;
  - EPO token refresh;
  - the `fda_designation` retirement.
- pipeline:
  - the 409 per-source lock;
  - the exact position of the canonical check and the cap in the stage order;
  - `raw_content` as the pre-filter's text;
  - the identity normalizer wired in production;
  - the HTTP API status codes.
- extraction:
  - delimited block markers;
  - required registry fields and moving-alias refusal;
  - the digest read from `/api/tags` (the CLAUDE.md trap says `ollama show`, which is stale);
  - the deprecation warning;
  - the leakage canary;
  - cross-model comparison;
  - the corroboration-review gate;
  - `EXTRACTION_BASE_URL`.

Each row in the batch has status `pending-decision`, and its `Source` cell reads `ingestion ratification batch` plus the heading text. The rows stay that way after this spec merges. The owner approves the batch by appending `## <date> — Living docs — CHOICE — ingestion ratification batch`; neither this spec nor the cutover appends it. Once that CHOICE exists, the cutover (step 3) flips the rows to their real status and cites the CHOICE. This spec does not flip them.

**Active and hold specs edited** (add `**Docs impact:**`; replace restated requirement text with IDs; keep each spec's own new work, tests and blockers):

| Spec | Restated text replaced with IDs |
|---|---|
| `specs/historical-backfill.md` | Replace restated text with IDs:<br>- the lineage paragraph's "skipped by content-hash dedup (§7.1)" (`:37`) → the processed-marker ID;<br>- the invariant list (`:62-65`) → `INV-1`, `INV-3`, `INV-13`, `INV-10`;<br>- the PubMed rate (`:69`) → the connectors rate ID;<br>- "≥0.85 precision" (`:5`) → the gate ID;<br>- re-extraction "(§10.4)" → the EXT re-extraction ID.<br>**`Blocked by` rewrite:**<br>- Drop the blockers that are already done: item 3 (`extraction-backend`, archived as `specs/done/extraction-backend.md`) and item 4 (`model-evaluation`, archived as `specs/done/model-evaluation.md`).<br>- Drop the "Recommended before starting: `edgar-content-fix`" paragraph (archived as `specs/done/edgar-content-fix.md`).<br>- Item 2 keeps only the open part: a local model passes the gate (the gate ID), with its gate record written.<br>- Items 1, 5, 6 and 7 stay.<br>- Add one item: the two non-LLM panels gate, citing `2026-10-08 — Edge research scoping — CHOICE — two non-LLM panels before the LLM backfill`, worded as "the LLM backfill waits until the catalyst-date and ClinicalTrials.gov version-diff diagnostics have run and show whether catalyst windows or registry edits carry return", and linking the RES requirement for that gate in `docs/research/backtesting.md` (written by `specs/living-docs-research.md`).<br>The result matches the TODO note that `specs/legacy-docs-retirement.md` rewrites. The spec keeps "a backfill never writes the live cursor", which is unbuilt work it still owns |
| `specs/golden-set-expansion.md` | "§11.1 forbids a threshold…" (`:35`) → publish-threshold ID; "0.85 gate precision" (`:4,38,80,90`) → gate ID. Its `Docs impact` names the calibrated-thresholds EXT ID (extraction requirement 21) as the ID its completion turns `tested`. The calibration rules stay, as unbuilt work |
| `specs/fda-advisory-committee-connector.md` | "record them … the requirements §6.8 table" (`:16`) → the verified-APIs section of `connectors.md`; the invariant list (`:34`) → INV IDs |
| `specs/managed-ingestion-config.md` | Replace restated text with IDs:<br>- "Requirements §6.6 …" (`:22,57`) → the pre-filter and golden-set IDs;<br>- "§5" (`:36`) → the cursor ID;<br>- the invariant list (`:50-56`) → INV IDs.<br>Its `Docs impact` lists the IDs it will change: the pre-filter vocabulary source and the `prefilter_version` format.<br>**`Blocked by` rewrite:** both listed blockers are done (`specs/done/graph-and-connector-wiring-fixes.md`, `specs/done/dashboard-foundation.md`), so the header becomes `**Blocked by:** —`. Its `Status` line is left as it is: whether it becomes `ready` is the owner's call. The PR description says so. This matches the TODO note that `specs/legacy-docs-retirement.md` rewrites |
| `specs/hold/structured-source-extraction.md` | The stale order quoted at `:14` is deleted and replaced with the stage-order ID. "amends §6.2 and §6.6" (`:63,67`) → a `Docs impact` naming the stage-order and pre-filter IDs it would change |
| `specs/hold/insider-buying-connector.md` | "requirements §7.1 amendment rule" (`:27`) → amendment ID; the invariant list (`:37`) → INV IDs. "SEC traps from `CLAUDE.md` apply: …" (`:18`) → "The SEC traps in `docs/ingestion/connectors.md` (Known traps) apply", a link to the connectors SEC rate and 403 IDs, with the restated trap text removed |
| `specs/hold/equity-offering-connector.md` | The invariant list (`:41`) → INV IDs; the acceptance-time rule (`:42`) → EDGAR timestamp ID. "SEC traps from `CLAUDE.md` apply (…)" (`:24`) → "The SEC traps in `docs/ingestion/connectors.md` (Known traps) apply", with the parenthesised restatement removed |

## Out of scope

- Any change to application code, tests, `sources.yaml`, `config/models/*`, prompts or scripts. Divergences are recorded, not fixed.
- Event shapes, identity formulas, closed sets, DLT naming and topic semantics (`docs/system/contracts.md`, written by `specs/living-docs-system-and-contracts.md`), and invariant text (same spec).
- These belong to `specs/living-docs-operations.md`:
  - DAG schedules, pool, retries, timeouts and cursor storage (`docs/operations/orchestration.md`);
  - the metric catalogue, metric-registration traps, alerts and the log contract (`docs/operations/observability.md`);
  - the cross-container SEC budget (`docs/operations/topology.md`).
- The RES requirement for the two non-LLM panels gate (`specs/living-docs-research.md`). This spec only links it from `specs/historical-backfill.md`.
- Trimming `services/ingestion-scraper/README.md`, the root `README.md` mention of `run_pipeline.py`, and the `docs/requirements.md` § index (`specs/legacy-docs-retirement.md`). Agent files (`specs/agent-instruction-hierarchy.md`).
- `docs/README.md`: `specs/living-docs-system-and-contracts.md` writes it in full, links to these three files included.
- Approving the ratification batch (the owner appends the `CHOICE — ingestion ratification batch` entry) and flipping its rows afterwards (the cutover, step 3).
- Other domain specs own these: `specs/first-run-on-stack-machine.md`, `specs/soak-test-run.md`, `specs/research-input-archive.md`, `specs/clinicaltrials-version-diffs.md`, `specs/ingestion-config-ui.md`, `specs/pipeline-control-view.md`.

## Constraints

- **Invariants.** The docs apply INV-1, INV-3, INV-4, INV-8, INV-9, INV-13 and INV-14 by ID and never restate their text.
- **Conversion provenance.** Every requirement's `Source` is, in priority order:
  1. a still-true `requirements.md` §;
  2. a `DECISIONS.md` `CHOICE` heading;
  3. an archived spec;
  4. an invariant;
  5. the ratification batch.

  A source that contradicts the code is written as approved, with status `divergent` and a DECISIONS heading. The doc is never edited to follow the code.
- **Conflict policy.** Machine authorities win on values: `sources.yaml` rates, lookbacks, caps, vocabularies and thresholds, and the registry's model fields, are named, never copied. Docs win on approved behaviour.
- **Frozen paths.** `docs/local-model-runbook.md` keeps its path. No file in `docs-check.toml` `frozen_paths` is moved or renamed.
- **ID rules.** ING and EXT only. Numbers come from `python3 -m tools.docs_check --next ING` and `--next EXT`, assigned in the order listed above. Each ID is defined once, with `<a id="NS-NNN"></a>**NS-NNN**`.
- **Cross-domain references.** Go to INV, SYS and CON IDs (merged first) or to the owner file by link. No HUB, COR, OPS or RES ID is cited until the spec that writes it has merged into the integration branch. While `core-hub`, `operations` and `research` are still in `[rollout] planned_domains`, links to their files are notices, not findings.
- **One owner per subject.** Log format and log fields belong to OPS, DLT naming and headers to CON, and dead-letter classification to HUB; ING and EXT link to them. The Ollama context-length and tag re-pointing traps are EXT's; the Docker Desktop/Metal trap is OPS topology's, linked from EXT.
- **Decision citations.** Use the full heading text in backticks, without the leading `## `, e.g. `2026-10-15 — Living docs — PENDING — fda_approval source`. Cite no decision by register number.
- **Shared files.**
  - `specs/living-docs-cutover-matrix.md`: only the `ID` cells of rows whose `NS` is ING or EXT, and the `IDs` cells of decisions-table rows classified `binding` whose fragment rows have `NS` ING or EXT (append the IDs space-separated, never remove another domain's).
  - `docs-check.toml`: only the `planned_domains` line.
  - `TODO.md`: only this spec's row.
- No "will"/"should eventually" in `docs/`; future work stays in change specs. No plan-step names.

## Dependencies

- **Needs:**
  - `specs/docs-check-tooling.md`: the checker, `--next`, `--paths`, check M;
  - `specs/living-docs-system-and-contracts.md`: INV and CON IDs, and `docs/README.md`;
  - the PENDING headings above, on the scoping branch.
- **Hands to later specs:** the ING and EXT IDs that these specs cite:
  - `specs/living-docs-core-hub.md`: raw audit, ticker allowlist;
  - `specs/living-docs-research.md`: the leakage canary as an evaluation precondition, published-date rules;
  - `specs/living-docs-operations.md`: cursor, SEC budget, metrics links;
  - `specs/agent-instruction-hierarchy.md`: `services/ingestion-scraper/AGENTS.md` pointers;
  - `specs/legacy-docs-retirement.md`: README links, `requirements.md` § index rows for §5–§7 and §11.

  It also hands the ratification-batch heading to `specs/living-docs-cutover.md` for the final gate.

## Affected files

| Path | Action |
|---|---|
| `docs/ingestion/connectors.md` | create |
| `docs/ingestion/pipeline.md` | create |
| `docs/ingestion/extraction.md` | create |
| `DECISIONS.md` | modify (append the ingestion ratification-batch entry only) |
| `specs/living-docs-cutover-matrix.md` | modify (the `ID` cells of ING and EXT rows; the `IDs` cells of binding decisions rows whose fragment rows have `NS` ING or EXT) |
| `docs-check.toml` | modify (`[rollout] planned_domains` line only: remove `ingestion`) |
| `TODO.md` | modify (this spec's row only) |
| `specs/living-docs-ingestion.md` → `specs/done/living-docs-ingestion.md` | move (status `done`) |
| `specs/historical-backfill.md` | modify |
| `specs/golden-set-expansion.md` | modify |
| `specs/fda-advisory-committee-connector.md` | modify |
| `specs/managed-ingestion-config.md` | modify |
| `specs/hold/structured-source-extraction.md` | modify |
| `specs/hold/insider-buying-connector.md` | modify |
| `specs/hold/equity-offering-connector.md` | modify |
| `docs/requirements.md`, `services/ingestion-scraper/README.md`, `README.md` | untouched-but-cited (`specs/legacy-docs-retirement.md` trims them) |
| `docs/README.md` | untouched (owned by `specs/living-docs-system-and-contracts.md`) |
| `docs/local-model-runbook.md`, `services/ingestion-scraper/config/sources.yaml`, `config/models/*.yaml` | untouched-but-cited |
| `services/ingestion-scraper/src/**`, `scripts/**`, `tests/**` | untouched-but-cited (verification rows) |

## Required tests

All of these run from the repo root on the spec branch. "Findings" are lines of `python3 -m tools.docs_check` output in the form `CHECK path:line message`. `OWN` stands for the path list `docs/ingestion/**,specs/historical-backfill.md,specs/golden-set-expansion.md,specs/fda-advisory-committee-connector.md,specs/managed-ingestion-config.md,specs/hold/structured-source-extraction.md,specs/hold/insider-buying-connector.md,specs/hold/equity-offering-connector.md`.

- `ingestion_docs_pass_structure_check`: `python3 -m tools.docs_check --only E --paths 'docs/ingestion/**'` exits 0. Each file has the header line and the H2s `Scope`, `Requirements`, `Verification` and `Retired requirements`, and a `Last reviewed against` SHA that is an ancestor of HEAD. Fails if a section is missing or the SHA is a feature-branch commit.
- `ingestion_ids_are_unique_and_resolve`: `python3 -m tools.docs_check --only C,D --paths "$OWN"` exits 0. Fails on any of:
  - a duplicate ID;
  - a `CON-?` placeholder (a finding once `system` has left `planned_domains`);
  - an unresolved INV or CON ID;
  - a cited DECISIONS heading that does not exist;
  - a register number.
- `every_ingestion_id_has_one_verification_row_and_tested_rows_name_real_tests`: `python3 -m tools.docs_check --only K --paths 'docs/ingestion/**'` exits 0. Fails if a `tested` row's `path::name` is not a `def name` in that file, or if `Source` is empty.
- `matrix_rows_for_ingestion_all_have_assigned_ids`: `python3 -m tools.docs_check --matrix specs/living-docs-cutover-matrix.md --domain ING` exits 0. Fails if any ING row with disposition move, ratify, divergent or retire has no ID that check C finds defined, or if the ID's `Source` cell lacks the row's source reference.
- `matrix_rows_for_extraction_all_have_assigned_ids`: the same with `--domain EXT`.
- `binding_decisions_for_ingestion_carry_ids`: `python3 -m tools.docs_check --matrix specs/living-docs-cutover-matrix.md --decisions --domain ING` and the same with `--domain EXT` each exit 0. Every binding decisions row whose fragment rows have `NS` ING or EXT has an ING or EXT ID in its `IDs` cell, and that ID's `Source` contains the heading text. Fails on an empty cell, or on an ID whose Source omits the heading.
- `edited_specs_carry_docs_impact`: `python3 -m tools.docs_check --only E --paths "$OWN"` exits 0. Fails if one of the 7 specs lacks `**Docs impact:**`.
- `edited_specs_drop_done_blockers_and_claude_md_citations`: `grep -nE "extraction-backend. spec must be done|model-evaluation. spec must be done|edgar-content-fix" specs/historical-backfill.md` prints nothing; `grep -n "two non-LLM panels before the LLM backfill" specs/historical-backfill.md` prints the new Blocked-by item; `grep -n "^\*\*Blocked by:\*\* —" specs/managed-ingestion-config.md` prints one line; `grep -n "traps from \`CLAUDE.md\`" specs/hold/equity-offering-connector.md specs/hold/insider-buying-connector.md` prints nothing.
- `stale_stage_order_is_gone_from_ingestion_owners`: `grep -rn "pre-filter → dedup → MinIO archive" docs/ingestion specs/hold/structured-source-extraction.md` prints nothing. Fails while the stale order survives in an owner or in the hold spec.
- `no_sources_yaml_value_copied`: `grep -rnE "initial_lookback[^a-z]*(7|30|90)|rate_limit_rps[^a-z]*[0-9]|max_documents_per_run[^a-z]*[0-9]" docs/ingestion` prints nothing. Fails if a doc restates a value that `sources.yaml` owns.
- `no_vacuous_test_cited_as_tested`: `grep -nE "test_injected_instruction_in_raw_content_does_not_change_extracted_entities|test_gene_target_outside_controlled_vocabulary_is_flagged_not_written" docs/ingestion/*.md | grep -w tested` prints nothing.
- `divergent_rows_cite_a_decision`: every verification row whose status is `divergent` or `pending-decision` contains a `Living docs — PENDING` or `CHOICE` heading. `awk -F'|' '$5 ~ /divergent|pending-decision/ && $3 !~ /— (PENDING|CHOICE) —/' docs/ingestion/*.md` prints nothing. Fails on a divergence without a heading.
- `fda_approval_is_active_and_divergent`: `grep -n "fda_approval source" docs/ingestion/connectors.md` shows the heading in an active verification row whose status is `divergent`, and `fda_designation` appears only under `## Retired requirements`. Fails if `fda_approval` is retired.
- `log_contract_is_linked_not_restated`: `grep -nE "external_id.*event_id|structured JSON" docs/ingestion/pipeline.md` prints nothing outside a sentence that links `docs/operations/observability.md`. Fails on a second statement of the log fields.
- `ratification_batch_lists_every_pending_row`: the set of IDs whose `Source` contains `ingestion ratification batch` in `docs/ingestion/*.md` equals the set of IDs listed under the new `PENDING — ingestion ratification batch` entry in `DECISIONS.md`. The comparison is a two-line `grep -o`/`sort`/`diff`, shown in the PR description. Fails on a missing or extra ID.
- `ingestion_left_planned_domains`: `grep -n '^planned_domains' docs-check.toml | grep -c '"ingestion"'` prints `0`, and `python3 -m tools.docs_check --only F --paths 'docs-check.toml'` exits 0.
- `no_application_file_changed`: `git diff --name-only origin/feature/living-docs-integration...HEAD` lists only the paths marked create, modify or move above.

## Definition of done

```bash
git fetch origin feature/living-docs-integration
OWN='docs/ingestion/**,specs/historical-backfill.md,specs/golden-set-expansion.md,specs/fda-advisory-committee-connector.md,specs/managed-ingestion-config.md,specs/hold/structured-source-extraction.md,specs/hold/insider-buying-connector.md,specs/hold/equity-offering-connector.md'
python3 -m tools.docs_check --paths "$OWN"; echo "own findings: $?"
python3 -m tools.docs_check --matrix specs/living-docs-cutover-matrix.md --domain ING; echo "ING matrix: $?"
python3 -m tools.docs_check --matrix specs/living-docs-cutover-matrix.md --domain EXT; echo "EXT matrix: $?"
python3 -m tools.docs_check --matrix specs/living-docs-cutover-matrix.md --decisions --domain ING; echo "ING decisions: $?"
python3 -m tools.docs_check --matrix specs/living-docs-cutover-matrix.md --decisions --domain EXT; echo "EXT decisions: $?"
grep -rn "pre-filter → dedup → MinIO archive" docs/ingestion specs/hold/structured-source-extraction.md; echo "stale order: $?"
# last step: remove "ingestion" from [rollout] planned_domains in docs-check.toml, then
python3 -m tools.docs_check --only F --paths 'docs-check.toml'; echo "planned: $?"
git diff --name-only origin/feature/living-docs-integration...HEAD
```

Expected:
- `own findings: 0`
- `ING matrix: 0`, `EXT matrix: 0`
- `ING decisions: 0`, `EXT decisions: 0`
- `stale order: 1` (grep found nothing)
- `planned: 0`
- the diff lists exactly the create, modify and move paths in Affected files.

## Compatibility

- **Readers.** `docs/requirements.md` and the scraper README are unchanged until `specs/legacy-docs-retirement.md`, so nothing a reader follows today disappears during the rollout. The integration branch reaches `develop` only at cutover (`2026-10-15 — Living docs — PENDING — rollout branch model`), so `develop` readers never see a half-written owner.
- **Links.** The 7 edited specs keep their paths and headings. Archived specs and `DECISIONS.md` entries that cite "requirements §6.2" keep resolving through the § index that `specs/legacy-docs-retirement.md` writes.
- **Agents.** Today's `CLAUDE.md` files still load. The routing to `docs/ingestion/` arrives with `specs/agent-instruction-hierarchy.md`.
- **Tests.** No test reads `docs/ingestion/`, and no Python or Java test changes. `test_docs_never_offer_down_v_as_a_fix` is unaffected.

## Rollback

On `feature/living-docs-integration`, revert this spec's merge range in one PR:

1. Run `git revert --no-commit <integration-branch tip before the merge>..<tip after>`. The range includes the spec's first commit.
2. Keep `DECISIONS.md` as it is at the tip: `git restore --source=HEAD --staged --worktree DECISIONS.md`. A rollback never deletes a DECISIONS entry.
3. Append `## <date> — Living docs — FLAG — ingestion docs rolled back`. It names the reverted range and states that the ingestion ratification batch entry no longer has IDs behind it.
4. Commit once.

The revert removes `docs/ingestion/`, restores the 7 specs, the matrix ID cells, the `planned_domains` line, the TODO row and the spec's path. Specs that already cite ING or EXT IDs then fail check D on the integration branch, and must be rebased onto the reverted head.

## Notes

- **fda_approval.** The connector is built and tested (`connectors/fda_approval.py:138`, `tests/unit/test_fda_regulatory.py`, 11 tests); only the `sources.yaml` entry is missing. §6.9 keeps `fda_approval` as the reliable half of FDA data; the missing designations endpoint retires only `fda_designation`. So this spec writes `fda_approval` as an approved source, `divergent` until a config spec adds the entry. If the owner instead answers the PENDING entry with retirement, the requirement moves to `Retired requirements` with that CHOICE. The registered connector code would then need a deletion spec.
- **RunResult counters live here, not in core-hub.** `RunResult` is the scraper's (`pipeline.py:16-29`), so the `RunResult counters` heading is cited by pipeline requirement 4. `specs/living-docs-cutover-design.md` §11 lists that decision under core-hub; this spec takes it.
- **Metric names and logs.** The single metric catalogue and the log contract are in `docs/operations/observability.md` (`specs/living-docs-cutover-design.md` §2). `pipeline.md` links to them and names no metric and no log field.
- **Ratification heading wording.** One heading per domain, `ingestion`, covers ING and EXT together. The `Source` token is `ingestion ratification batch`.
- **Exact PENDING titles** are those committed on the scoping branch. If one differs from the text above, use the committed one.
- **As built: answered decisions.** Three of the PENDING headings had a `CHOICE` by 2026-10-17, so the docs cite both and write the chosen option instead of a `pending-decision` row: `initial_lookback value` (ING-004, `tested`), `RunResult counters` (ING-025, `tested`; the two unused counters are retired as ING-041) and `fda_approval source` (option A: ING-015 and ING-020 stay active and `divergent` until a config spec adds the entry). `run_pipeline.py support` is cited in the `pipeline.md` Scope, since the script carries no requirement.
- **As built: raw pointer stage.** Defect C1 is fixed on `develop` (`specs/done/raw-pointer-contract-fix.md`), so ING-022's stage order includes the raw pointer published right after a new archive object, and the docs cite the CON IDs that `docs/system/contracts.md` assigns (CON-005, CON-006, CON-018, CON-019 among them) instead of the `raw-pointer contract` PENDING heading.
- **As built: partly sourced requirements.** Where one requirement joins an approved source with a new rule (ING-008, ING-017, ING-022, ING-037, ING-038, EXT-003, EXT-010, EXT-020), the row keeps the status of the approved part, and the new part is listed under "Partly sourced" in the ingestion ratification batch. Two new traps (the EPO OPS token and the ClinicalTrials.gov `filter.advanced` trap) sit in Known traps without an ID and are listed in the batch the same way.
- **As built: ID layout.** The `published_date` requirement is split into ING-009 (the rule) and ING-010 to ING-015 (one per source), so each source's test has its own verification row. Retired IDs are numbered after each file's active IDs: ING-021 (`fda_designation`) and ING-041 (the `deduped` and `extracted` counters). EXT has no retirement.
- **As built: matrix.** M-SYS-147 (the §0.4 extraction budget) maps to EXT-007, whose Source cites §0.4, rather than ING-037, because the budget constrains extraction identity and cost, not the pre-filter.
- **As built: edited specs.** `specs/managed-ingestion-config.md` drops its done blockers (`**Blocked by:** —`) but keeps Status `blocked`: setting it `ready` is a scoping decision outside this spec. `specs/historical-backfill.md` keeps its Blocked-by numbering (1, 2, 5, 6, 7, then the new 8) so references to those items still resolve. ING-029 (flush and delivery reports) is `untested`: the existing tests use fakes, and none fails a delivery report on the real producer client.

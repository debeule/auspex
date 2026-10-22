# Source connectors

Domain: ING · Code: `services/ingestion-scraper/src/auspex_ingest/connectors/`, `services/ingestion-scraper/src/auspex_ingest/sources.py`, `services/ingestion-scraper/src/auspex_ingest/models.py`, `services/ingestion-scraper/config/sources.yaml` · Last reviewed against: develop @ b7582c3

## Scope

What a source connector is and what it must produce: the `SourceConnector` contract, the connector registry and the meaning of a `services/ingestion-scraper/config/sources.yaml` entry, `RawDocument` as the connector's output, the typed `canonical_id` per source, the per-source `published_date` rules, per-host rate limiting, the verified source APIs, and the traps of each source.

`services/ingestion-scraper/config/sources.yaml` is the machine authority for every source value: schedules, request rates, lookbacks, extraction caps, vocabularies and publish thresholds. This doc names its fields and copies none of its values.

Not in this file:
- what happens to a document after the connector yields it (archive, deduplication, pre-filter, publish, run result, cursor): [pipeline.md](pipeline.md);
- extraction, the model and the gate: [extraction.md](extraction.md);
- the wire form of `RawDocument` as a raw pointer, the identity formulas and the `canonical_id` prefix set: [contracts.md](../system/contracts.md) (CON-005, CON-018, CON-020);
- DAG schedules, the Airflow pool and cursor storage: [orchestration.md](../operations/orchestration.md);
- the SEC request budget shared across containers: [topology.md](../operations/topology.md). This doc owns only each connector's own rate.

## Requirements

- <a id="ING-001"></a>**ING-001** — `SourceConnector.fetch_since(cursor)` fetches and maps only: it takes a UTC-aware cursor, is synchronous, returns an `Iterator` of `RawDocument`, and never writes MinIO, calls the model or publishes. Applies INV-3 and INV-8.
- <a id="ING-002"></a>**ING-002** — A new source is a connector module that registers itself with `REGISTRY.register` plus an entry in `services/ingestion-scraper/config/sources.yaml`; asking the registry for an unregistered `source_type` raises `UnknownSourceTypeError`, whose message names every registered type. Applies INV-4.
- <a id="ING-003"></a>**ING-003** — `services/ingestion-scraper/config/sources.yaml` is parsed strictly: an unknown field in an entry or at the top level, or a `source_type` that appears twice, is rejected when the file is loaded.
- <a id="ING-004"></a>**ING-004** — A source with no saved cursor starts at now minus the `initial_lookback` days of its `sources.yaml` entry; the file is the authority for the value.
- <a id="ING-005"></a>**ING-005** — Every HTTP request of every connector goes through one shared `RateLimitedClient`, which keeps one bucket per registered host, shared by that host's subdomains and by every connector on it, at the `rate_limit_rps` of the entry. Requests are spaced evenly with no burst, and a request whose slot is not yet due waits for it instead of failing.
- <a id="ING-006"></a>**ING-006** — The `rate_limit_rps` configured for each source stays at or below the verified limit of its host in the [verified host limits](#verified-host-limits) table; the [verified source APIs](#verified-source-apis) table records each source's endpoint and authentication.
- <a id="ING-007"></a>**ING-007** — A 403 from any `*.sec.gov` request, the search, a filing index or a filing document, ends the EDGAR run with `SecRequestRefused`, and the run makes no further SEC request.
- <a id="ING-008"></a>**ING-008** — A document's `canonical_id` is typed (`doi:`, `nct:`, `edgar:`, `epo-app:`, `fda:`) or absent. A connector that can supply one declares `provides_canonical_id` and supplies it on every document, and a document it yields without one fails.
- <a id="ING-009"></a>**ING-009** — `published_date` is the moment the information became public, as a UTC-aware datetime. A date at which the information was not yet public never feeds point-in-time alignment.
- <a id="ING-010"></a>**ING-010** — bioRxiv: `published_date` is the date of the fetched version; a new version is a new public disclosure.
- <a id="ING-011"></a>**ING-011** — PubMed: `published_date` is the earliest public availability (electronic or ahead-of-print).
- <a id="ING-012"></a>**ING-012** — Patents: `published_date` is the pre-grant publication date, else the grant date.
- <a id="ING-013"></a>**ING-013** — ClinicalTrials.gov: `published_date` is the first post date, or the last update post date when the fetched record is an amended one.
- <a id="ING-014"></a>**ING-014** — EDGAR: `published_date` is the filing's acceptance time, converted from US Eastern time to UTC, else the filing date at the end of that day's filing window.
- <a id="ING-015"></a>**ING-015** — Regulatory (`fda_approval`): `published_date` is the action date of the submission.
- <a id="ING-016"></a>**ING-016** — Each document keeps its source-specific dates that are not `published_date` (submission, filing, grant, issue and period dates) as their own fields, apart from `raw_content`.
- <a id="ING-017"></a>**ING-017** — EDGAR keeps only 8-K filings that carry item 2.02, 7.01 or 8.01, one document per accession number. A filing's documents and acceptance time come from its `-index.htm` page, located under the company's CIK, `ciks[0]`; an inline-XBRL viewer link there is followed to its document. Exhibit 99.1, when the filing has one, leads `raw_content`, followed by the cover document.
- <a id="ING-018"></a>**ING-018** — Patents come from EPO OPS. `canonical_id` is `epo-app:` followed by the application reference, so a pre-grant publication and its later grant share one `event_id`; `external_id` is the publication reference `CC-NUM-KIND`.
- <a id="ING-019"></a>**ING-019** — ClinicalTrials.gov `raw_content` names the trial's lead sponsor.
- <a id="ING-020"></a>**ING-020** — `fda_approval` is a source: FDA approvals, labels and shortages through openFDA (Drugs@FDA, labels, shortages), with a `canonical_id` of type `fda:`.

### Verified host limits

External facts about each host, checked August 2026 (requirements §6.5). The rate each source uses is the `rate_limit_rps` of its entry in `services/ingestion-scraper/config/sources.yaml`; ING-006 keeps it at or below the limit here.

| Host | Published limit | Notes |
|---|---|---|
| `eutils.ncbi.nlm.nih.gov` | 3 requests a second without a key, 10 with | Free key from an NCBI account; `tool=` and `email=` parameters expected |
| `api.biorxiv.org` | none published | |
| `ops.epo.org` | 2.5 requests a second on the free standard tier, 4 GB of data a week | OAuth2 client credentials (Known traps) |
| `api.fda.gov` | 240 requests a minute per IP; 1,000 requests a day without a key, 120,000 with | The daily cap binds, not the per-minute one |
| `clinicaltrials.gov` | none published; about 50 requests a minute observed | |
| `*.sec.gov`, including `efts.` and `data.` | 10 requests a second, aggregate across all SEC hosts | Shared with every other container that calls SEC: [topology.md](../operations/topology.md) |

### Verified source APIs

Checked August 2026 (requirements §6.8). Each row is a dated fact about an external service, not a promise about it.

| Source | Endpoint | Auth | Status |
|---|---|---|---|
| bioRxiv and medRxiv | `https://api.biorxiv.org/details/{server}/{start}/{end}/{cursor}` | none | Live. 100 a page, integer cursor. Abstracts only, not full text |
| PubMed | E-utilities | optional free key | Live |
| Patents | `https://ops.epo.org/3.2/rest-services/published-data/search` | OAuth2 client credentials (`EPO_OPS_KEY`, `EPO_OPS_SECRET`) | Live. Free standard tier, registration at `developers.epo.org`, no government ID, no commercial-use restriction. DOCDB covers US, EP and PCT |
| Clinical trials | `https://clinicaltrials.gov/api/v2/studies` | none | Live. `nextPageToken`, `pageSize` up to 1000, `fields` projection. v1 retired June 2024 |
| Regulatory | `https://api.fda.gov/drug/{drugsfda,label,enforcement,drugshortages}.json` | optional key, needed for the daily quota | Live. No designations endpoint (Known traps) |
| Material disclosures | `https://efts.sec.gov/LATEST/search-index` and `https://www.sec.gov/Archives/edgar/data/{cik}/{accession_nodash}/{accession}-index.htm` | none; descriptive `User-Agent` mandatory | Live. EFTS is undocumented: no published parameter list, schema or stability commitment |
| Ticker resolution | `https://www.sec.gov/files/company_tickers.json` | none; descriptive `User-Agent` mandatory | Live. Ticker, CIK and name of every EDGAR filer; core-hub reads it ([storage.md](../core-hub/storage.md)) |

## Known traps

Sources: requirements §6.5, §6.7, §6.8, §6.9; `CLAUDE.md:210-214` (Known traps); `services/ingestion-scraper/README.md:107-111` (known API constraints). The EPO token refresh and the ClinicalTrials.gov `filter.advanced` syntax below have no approval beyond that README and the code; they are items of `2026-10-22 — Living docs — PENDING — ingestion ratification batch`.

- **SEC refuses a request without a descriptive `User-Agent`** (403), and blocks the IP for about ten minutes once all `*.sec.gov` hosts together pass 10 requests a second; retrying during the block extends it. `data.sec.gov` counts against the same bucket. This is why ING-005 keys SEC on one host and ING-007 stops at the first 403.
- **EFTS is undocumented and its `_source` field names are `adsh`, `ciks` and `display_names`**, not `accession_no`, `entity_id` or `entity_name` (fixture names that were once invented; `specs/done/edgar-efts-fixture-alignment.md`). Keep the mapping thin. Protects ING-017.
- **`data.sec.gov/submissions` lists only recent filings**, so it misses most of a 24-month window, and the `index.json` directory endpoint carries no document types. The filing's `-index.htm` page has both the document table and the acceptance time, which is US Eastern time. Protects ING-014 and ING-017.
- **The accession number's prefix is the filing agent's CIK** for most large filers, not the company's; the company is `ciks[0]`. Protects ING-017.
- **Both PatentsView URLs are superseded and Lens.org is not free for this use.** `api.patentsview.org` was discontinued on 2025-05-01 and `search.patentsview.org` moved to USPTO ODP, which requires a government ID; Lens.org classes investment research as commercial use. EPO OPS has neither restriction. Protects ING-018.
- **An EPO OPS access token expires after 20 minutes** and is refreshed before it expires, including between a search page and its bibliographic fetch; a 429 carries `Retry-After`. Protects ING-018.
- **A patent's `filed_date` looks like the look-ahead guard and is the opposite.** A US application is not public at filing; it publishes about 18 months later. `filed_date` is the priority date and never feeds alignment. Protects ING-009 and ING-012.
- **A trial's `first_submitted_date` is private**; the post date is public. Protects ING-009 and ING-013.
- **ClinicalTrials.gov v2 filters by date only through `filter.advanced`** with the range syntax `AREA[LastUpdatePostDate]RANGE[start,end]`. Protects ING-013.
- **openFDA has no designations endpoint.** Its drug domain is adverse events, labelling, NDC, recall enforcement, the Orange Book, Drugs@FDA and shortages. Orphan designations are an HTML search with a spreadsheet export, and Fast Track and RMAT are not published machine-readably at all. Protects ING-020 and is why the designation source is retired below.
- **openFDA's daily cap of 1,000 requests binds without a key**, long before the per-minute limit; the connector raises `QuotaExhaustedError` on a 429. Protects ING-006 and ING-020.

## Rationale

Non-normative.

- **Connectors do not write** (requirements §6.1). If `fetch_since` archived, extracted or published, every connector would carry its own copy of the pipeline, and the archive-first rule (INV-13) would hold only as long as each copy kept it.
- **Rates are configured, not reactive** (requirements §6.5). Handling a 429 after it arrives is not compliance with a published limit, and against SEC it extends a block.

## Verification

| ID | Source | Verified by | Status |
|---|---|---|---|
| ING-001 | requirements §6.1, §6.3; INV-3; INV-8; `services/ingestion-scraper/CLAUDE.md` (lines 18, 20) | `services/ingestion-scraper/tests/unit/test_connector_contract.py::test_fetch_since_performs_no_io_beyond_http`; `services/ingestion-scraper/tests/unit/test_connector_contract.py::test_fetch_since_is_not_a_coroutine_and_returns_an_iterator`; `services/ingestion-scraper/tests/unit/test_connector_contract.py::test_rawdocument_rejects_naive_datetime` | tested |
| ING-002 | INV-4; `services/ingestion-scraper/README.md` (lines 41-45); the error naming the registered types: `2026-10-22 — Living docs — PENDING — ingestion ratification batch` | `services/ingestion-scraper/tests/unit/test_connector_registry.py::test_unknown_source_type_raises_a_named_error_listing_registered_types`; `services/ingestion-scraper/tests/unit/test_connector_registry.py::test_every_source_in_sources_yaml_builds_a_connector_through_the_registry`; `services/ingestion-scraper/tests/unit/test_connector_registry.py::test_no_source_type_equality_branch_in_shared_modules` | pending-decision |
| ING-003 | `services/ingestion-scraper/README.md` (line 62); `2026-10-22 — Living docs — PENDING — ingestion ratification batch` | `services/ingestion-scraper/tests/unit/test_sources_schema.py::test_unknown_field_in_sources_yaml_is_rejected_at_parse_time`; `services/ingestion-scraper/tests/unit/test_sources_schema.py::test_duplicate_source_type_is_rejected` | pending-decision |
| ING-004 | requirements §5, §0.3 (its 90-day value is superseded); `2026-10-15 — Living docs — PENDING — initial_lookback value`; `2026-10-17 — Living docs — CHOICE — initial_lookback value` (option A: `sources.yaml` is the authority, and the doc names the file without copying the number) | `services/ingestion-scraper/tests/unit/test_api.py::test_ingest_absent_cursor_defaults_to_initial_lookback` | tested |
| ING-005 | requirements §6.5, §1 (`httpx` only through the shared client); `2026-10-10 — Ingestion run reliability — CHOICE — rate limiter spaces requests evenly, with no burst`; `services/ingestion-scraper/CLAUDE.md` (line 21) | `services/ingestion-scraper/tests/unit/test_rate_limited_client.py::test_two_connectors_on_the_same_host_share_one_bucket`; `services/ingestion-scraper/tests/unit/test_rate_limited_client.py::test_idle_time_does_not_bank_a_burst`; `services/ingestion-scraper/tests/unit/test_rate_limited_client.py::test_rate_limited_client_waits_for_a_token_instead_of_raising`; `services/ingestion-scraper/tests/unit/test_rate_limited_client.py::test_rate_limited_client_never_exceeds_the_rate_across_threads`; `services/ingestion-scraper/tests/unit/test_sec_edgar.py::test_sec_hosts_share_one_rate_limit_bucket` | tested |
| ING-006 | requirements §6.5, §6.8; `2026-10-09 — Soak-test readiness — CHOICE — SEC request budget across containers` (the per-connector half; the aggregate is in [topology.md](../operations/topology.md)); at-risk class #8 | `services/ingestion-scraper/tests/unit/test_sources_schema.py::test_source_rates_follow_the_requirements_limits` | tested |
| ING-007 | requirements §6.5; `2026-10-10 — Ingestion run reliability — CHOICE — a 403 on a filing index also stops the EDGAR run`; `2026-10-09 — Soak-test readiness — CHOICE — SEC request budget across containers` | `services/ingestion-scraper/tests/unit/test_sec_edgar.py::test_index_403_stops_the_run_without_further_sec_requests`; `services/ingestion-scraper/tests/unit/test_sec_edgar.py::test_edgar_stops_on_a_refused_request_without_retrying` | tested |
| ING-008 | requirements §10.1; CON-020; the `fda:` prefix: `2026-10-22 — Living docs — PENDING — ingestion ratification batch`; PubMed: `2026-10-15 — Living docs — PENDING — defects found while scoping`, `2026-10-17 — Living docs — CHOICE — defects found while scoping` | `services/ingestion-scraper/tests/unit/test_connector_contract.py::test_canonical_id_is_typed_or_absent_rejects_bare`; `services/ingestion-scraper/tests/unit/test_ingestion_pipeline.py::test_connector_supplying_canonical_id_intermittently_fails_loudly`; `services/ingestion-scraper/tests/unit/test_fda_regulatory.py::test_canonical_id_uses_fda_prefix`. PubMed declares `provides_canonical_id=False` and sets no `doi:` id, though some of its records carry a DOI | divergent |
| ING-009 | requirements §6.7 | `services/ingestion-scraper/tests/unit/test_epo_ops.py::test_filing_date_and_granted_date_are_retained_in_raw_content_but_excluded_from_alignment`; `services/ingestion-scraper/tests/unit/test_connector_contract.py::test_rawdocument_normalizes_offset_to_utc` | tested |
| ING-010 | requirements §6.7 | `services/ingestion-scraper/tests/unit/test_academic_papers.py::test_published_date_is_the_public_posting_date_not_retrieved_at`; `services/ingestion-scraper/tests/unit/test_academic_papers.py::test_new_biorxiv_version_of_the_same_doi_is_an_amendment_not_a_duplicate` | tested |
| ING-011 | requirements §6.7; `2026-10-15 — Living docs — PENDING — defects found while scoping`; `2026-10-17 — Living docs — CHOICE — defects found while scoping` | a date with no day or month becomes day 1 or January 1 (`_parse_date` in `services/ingestion-scraper/src/auspex_ingest/connectors/pubmed.py`) | divergent |
| ING-012 | requirements §6.7 | `services/ingestion-scraper/tests/unit/test_epo_ops.py::test_published_date_is_the_public_disclosure_date_not_filing_date`; `services/ingestion-scraper/tests/unit/test_epo_ops.py::test_pending_filing_with_no_grant_date_is_handled` | tested |
| ING-013 | requirements §6.7 | `services/ingestion-scraper/tests/unit/test_clinical_trials.py::test_published_date_is_a_post_date_not_the_submission_date`; `services/ingestion-scraper/tests/unit/test_clinical_trials.py::test_amended_trial_creates_a_new_snapshot_and_a_new_extraction_under_the_same_event_id` | tested |
| ING-014 | requirements §6.7; `2026-10-07 — EDGAR press-release content — CHOICE — filing index replaces the submissions lookup` | `services/ingestion-scraper/tests/unit/test_sec_edgar.py::test_published_date_is_the_acceptance_time_converted_from_eastern_to_utc`; `services/ingestion-scraper/tests/unit/test_sec_edgar.py::test_acceptance_time_converts_to_utc_across_daylight_saving_changes`; `services/ingestion-scraper/tests/unit/test_sec_edgar.py::test_published_date_without_acceptance_time_is_the_file_date_after_the_filing_cutoff` | tested |
| ING-015 | requirements §6.7; `2026-10-15 — Living docs — PENDING — fda_approval source`; `2026-10-17 — Living docs — CHOICE — fda_approval source` | the connector is tested (`services/ingestion-scraper/tests/unit/test_fda_regulatory.py::test_published_date_is_the_action_date_not_retrieved_at`), but no `sources.yaml` entry configures it, so it never runs | divergent |
| ING-016 | requirements §6.3; `2026-10-15 — Living docs — PENDING — defects found while scoping`; `2026-10-17 — Living docs — CHOICE — defects found while scoping` | the dates are kept only as text inside `raw_content` (`services/ingestion-scraper/tests/unit/test_clinical_trials.py::test_both_date_fields_retained_separately` asserts exactly that) | divergent |
| ING-017 | `2026-10-07 — EDGAR press-release content — CHOICE — filing index replaces the submissions lookup`; `services/ingestion-scraper/README.md` (line 107); inline-XBRL links and one document per accession: `2026-10-22 — Living docs — PENDING — ingestion ratification batch` | `services/ingestion-scraper/tests/unit/test_sec_edgar.py::test_8k_without_press_release_items_is_skipped_before_any_document_fetch`; `services/ingestion-scraper/tests/unit/test_sec_edgar.py::test_exhibit_99_1_press_release_is_fetched_and_leads_raw_content`; `services/ingestion-scraper/tests/unit/test_sec_edgar.py::test_edgar_filing_is_located_by_company_cik_not_accession_prefix`; `services/ingestion-scraper/tests/unit/test_sec_edgar.py::test_one_document_per_accession_across_search_pages` | tested |
| ING-018 | `2026-08-15 — Step 2.3 — CHOICE — Patent connector: PatentsView → Lens.org → EPO OPS (final)`; `2026-08-15 — Step 2.3 — CHOICE — Patent connector changed from Lens.org to EPO OPS` | `services/ingestion-scraper/tests/unit/test_epo_ops.py::test_pregrant_publication_and_its_later_grant_resolve_to_one_event_id`; `services/ingestion-scraper/tests/unit/test_epo_ops.py::test_epo_payload_maps_to_rawdocument` | tested |
| ING-019 | `2026-10-07 — Company-level extraction — CHOICE — event taxonomy and identifier fields (schema 1.1)` (item 5) | `services/ingestion-scraper/tests/unit/test_clinical_trials.py::test_clinicaltrials_raw_content_names_lead_sponsor` | tested |
| ING-020 | requirements §6.9, §6.5 (the openFDA daily cap); `2026-10-15 — Living docs — PENDING — fda_approval source`; `2026-10-17 — Living docs — CHOICE — fda_approval source` (option A: approve it as a source, recorded `divergent` until a small config spec adds the entry) | the connector is registered and tested (`services/ingestion-scraper/tests/unit/test_fda_regulatory.py::test_connector_runs_through_the_unchanged_ingestion_pipeline`), but no `sources.yaml` entry configures it | divergent |

## Retired requirements

- **ING-021** — retired 2026-10-22, from requirements §6.9: "**`fda_designation`** *(optional)* — the orphan designation export as a slow bulk import; Fast Track/RMAT via a company press-release feed registered as its **own `source_type`**, so its lower reliability is visible in corroboration counts." openFDA has no designations endpoint (requirements §6.9) and the source was never built; listed in `2026-10-22 — Living docs — PENDING — ingestion ratification batch`.

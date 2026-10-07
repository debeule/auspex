# ingestion-scraper

Pulls documents from 5 public biotech sources, archives raw content to MinIO (unconditionally, before any other side effect), pre-filters on vocabulary, runs LLM extraction via instructor/OpenAI, and publishes `ResearchSignalEvent` to Kafka. Stateless — no database access; cursor state lives in Airflow Variables.

---

## Pipeline stages

1. `fetch_since(cursor)` — connector fetches and maps to `RawDocument`
2. MinIO archive — unconditional write; returns `(key, is_new)`
3. Unchanged re-fetch check — when the pipeline has an `extraction_identity` (model + prompt; the live API sets it), a document whose identical content was already fully processed under that identity and prefilter version is skipped (requirements §7.1 step 3). Markers live under `dedup/processed/` and are written only after Kafka delivery is confirmed, so failed documents are retried and a new model re-extracts.
4. Pre-filter — vocabulary gate; skips LLM cost on irrelevant docs
5. Canonical dedup check — skips re-extraction when content hash has been seen before
6. LLM extract — `instructor` + OpenAI returns `ResearchSignalEvent | None`, including the company-level fields (`event_type`, `primary_company`, `program_identifiers`, `trial_ids`; NCT IDs validated)
7. Normalize — `HgncEntityNormalizer` resolves gene aliases and company tickers
8. Publish — Kafka `auspex.signals.extracted` (signals only) + `auspex.raw.ingested` (all)

---

## Connectors

| Source | Class | `source_type` | Status |
|---|---|---|---|
| bioRxiv | `BiorxivConnector` | `biorxiv` | Active |
| PubMed | `PubmedConnector` | `pubmed` | Active |
| ClinicalTrials.gov | `ClinicalTrialConnector` | `clinicaltrials` | Active — `raw_content` includes the lead sponsor |
| SEC EDGAR | `SecEdgarConnector` | `edgar` | Active — 8-Ks with items 2.02, 7.01 or 8.01; Exhibit 99.1 press release plus cover text, found via the filing's `-index.htm`; `published_date` is the acceptance time |
| openFDA approvals | `FdaApprovalConnector` | `fda` | Active |
| EPO OPS patents | `EpoOpsConnector` | `epo_ops` | Blocked — needs EPO OPS credentials |

---

## Adding a connector

1. Implement `SourceConnector` in `src/auspex_ingest/connectors/` (inherit `base.py`, implement `fetch_since(cursor) -> Iterator[RawDocument]`)
2. Add an entry to `config/sources.yaml`
3. Register in `dags/auspex_dags.py` `_build_connector()`

No changes to `IngestionPipeline` or any shared code.

---

## Configuration — `sources.yaml` schema

| Field | Type | Description |
|---|---|---|
| `source_type` | `str` | Unique connector identifier (e.g. `biorxiv`, `epo_ops`). |
| `schedule` | `str` | Airflow 3 schedule expression (e.g. `@daily`, `0 6 * * 1`). Not `schedule_interval`. |
| `rate_limit_rps` | `float` | Maximum requests per second the connector may issue. |
| `initial_lookback` | `int` | Days of history to fetch on first run (no cursor Variable yet). |
| `max_documents_per_run` | `int` | Hard cap on documents fetched per DAG run. |
| `prefilter_vocabulary` | `list[str]` | Terms the pre-filter checks before spending LLM calls. |
| `source_config` | `dict` | Connector-specific configuration (base URLs, filters, etc.). |

Unknown fields are rejected at parse time (`extra = "forbid"`).

---

## Development commands

```bash
uv sync --all-extras                                          # install
uv run pytest tests/unit -q                                   # inner loop — fast, no containers
uv run pytest tests/unit/test_ingestion_pipeline.py -q        # one file
uv run pytest -q                                              # everything
uv run ruff check . && uv run mypy src                        # lint + types
uv run python scripts/run_pipeline.py --days 30 --sources clinicaltrials pubmed
```

---

## Testing layout

| Path | What runs | Tool |
|---|---|---|
| `tests/unit/` | pytest-socket disables network; respx stubs all HTTP; 138+ tests | `pytest tests/unit -q` |
| `tests/integration/` | testcontainers (MinIO, Kafka); self-contained; no running stack needed | `pytest -m integration` |
| `tests/golden/` | 50 hand-labelled docs for extraction quality evaluation (see FORMAT.txt) | `scripts/score_extraction.py` |
| `tests/fixtures/` | Saved API responses used by respx for unit test stubs | — |

---

## Scripts

| Script | Purpose |
|---|---|
| `scripts/run_pipeline.py` | Run one source from CLI without Airflow |
| `scripts/score_extraction.py` | Precision/recall against the golden set (writes gate record) |
| `scripts/evaluate_model.py` | Candidate comparison: precision, latency, feasibility; writes `config/models/latency/<slug>.json` |
| `scripts/check_leakage.py` | Leakage canary: flags months ≥70% correct after claimed cutoff |
| `scripts/compare_models.py` | Cross-model agreement: Jaccard, directionality, confidence correlation |
| `scripts/register_local_model.py` | Add a pulled Ollama model to `config/models/registry.yaml` with its live digest (fields from `config/models/local_candidates.yaml`) |
| `scripts/sample_corroborations.py` | Pull N corroborations from live DB for review |
| `scripts/score_corroboration_review.py` | Score completed review JSONL against 0.85 gate |

---

## Known API constraints

- **SEC** blocks IPs at 10 req/s aggregate across all `*.sec.gov` (including `data.sec.gov`). Descriptive `User-Agent` is mandatory (403 without it). Filing documents are found on `Archives/edgar/data/{company_cik}/{accession_nodash}/{accession}-index.htm`, whose document table carries the type (`8-K`, `EX-99.1`) and whose `Accepted` field is the acceptance time in US Eastern time; the `index.json` directory endpoint has no type metadata, and `data.sec.gov/submissions` only lists recent filings (about a year or 1,000 filings), too few for a backfill. Use the company CIK from `ciks[0]`, not the accession prefix, which names the filing agent for most large filers. Inline-XBRL documents link as `/ix?doc=/Archives/...`. Full-text search may return a hit per filed document, so hits are deduplicated by accession. The EFTS `_source` schema uses `adsh`/`ciks`/`display_names` — not `accession_no`/`entity_id`/`entity_name`.
- **EPO OPS**: OAuth2 client credentials, free standard tier at 2.5 req/s. Register at developers.epo.org.
- **openFDA**: 1,000 requests/day without key; key raises limit significantly. No designations endpoint (no Fast Track/RMAT/orphan data).
- **ClinicalTrials API v2**: uses `filter.advanced=AREA[LastUpdatePostDate]RANGE[start,end]` syntax — the `filter.lastUpdatePostDate` param was removed.
- **Patents**: `filed_date` is NOT the public disclosure date. A US application publishes ~18 months after filing. Use the pre-grant publication date.

# ingestion-scraper

Pulls documents from public biotech sources, archives each one to MinIO, pre-filters on a vocabulary, extracts signals with a language model, and publishes `ResearchSignalEvent` to Kafka. Airflow calls it over HTTP (`POST /ingest/<source_type>`), one source per run. Its requirements are owned by [docs/ingestion/](../../docs/ingestion/): [connectors.md](../../docs/ingestion/connectors.md), [pipeline.md](../../docs/ingestion/pipeline.md) and [extraction.md](../../docs/ingestion/extraction.md); its payloads by [docs/system/contracts.md](../../docs/system/contracts.md).

Commands: [AGENTS.md](AGENTS.md).

---

## Layout

| Path | Holds |
|---|---|
| `src/auspex_ingest/` | the package: API, pipeline, extractor, identity, models |
| `src/auspex_ingest/connectors/` | one module per source, the shared `RateLimitedClient` and the connector registry |
| `src/auspex_ingest/messaging/` | the Kafka producer |
| `src/auspex_ingest/storage/` | the MinIO archive client |
| `config/sources.yaml` | one entry per source |
| `prompts/extraction/` | versioned extraction prompts |
| `dags/` | the ingestion DAGs and the daily health summary |
| `scripts/` | developer and evaluation scripts (below) |
| `tests/unit/` | unit tests, no network |
| `tests/integration/` | Testcontainers tests (LocalStack's S3 API standing in for MinIO, Kafka) |
| `tests/golden/` | hand-labelled documents for extraction quality (see `FORMAT.txt`) |
| `tests/fixtures/` | saved API responses the unit tests stub HTTP with |

## Pipeline

The stages and their order are ING-022 in [pipeline.md](../../docs/ingestion/pipeline.md); what a run returns, the extraction cap and the cursor it reports are ING-025 to ING-027 there. Scheduling, retries and the cursor Variable are in [docs/operations/orchestration.md](../../docs/operations/orchestration.md).

---

## Connectors

| Source | Class | `source_type` | Status |
|---|---|---|---|
| bioRxiv | `BiorxivConnector` | `biorxiv` | Active |
| PubMed | `PubmedConnector` | `pubmed` | Active |
| ClinicalTrials.gov | `ClinicalTrialConnector` | `clinicaltrials` | Active |
| SEC EDGAR | `SecEdgarConnector` | `edgar` | Active |
| EPO OPS patents | `EpoOpsConnector` | `epo_ops` | Active |
| openFDA approvals | `FdaApprovalConnector` | `fda_approval` | Approved source, not configured yet: no `sources.yaml` entry ([ING-020](../../docs/ingestion/connectors.md#ING-020)) |
| Test double | `MockConnector` | `mock` | Unscheduled; runs only when triggered |

What each connector fetches and how it dates a document is in [connectors.md](../../docs/ingestion/connectors.md); the `sources.yaml` fields, the verified host limits and the known API constraints are there too.

## Adding a connector

1. Implement `SourceConnector` in a new module in `src/auspex_ingest/connectors/` (inherit `base.py`, implement `fetch_since(cursor) -> Iterator[RawDocument]`).
2. In the same module, register a builder: `@REGISTRY.register("<source_type>", rate_limit_host="<api host>")` on a function taking a `BuildContext` (shared rate-limited client, the `sources.yaml` entry, the environment for credentials) and returning the connector.
3. Add an entry to `config/sources.yaml`.

`default_registry()` imports every module in `connectors/`, so the scraper API and `scripts/run_pipeline.py` pick the connector up with no change to shared code. The rule is ING-002 in [connectors.md](../../docs/ingestion/connectors.md).

---

## Scripts

| Script | Purpose |
|---|---|
| `scripts/run_pipeline.py` | Developer tool: run one source from the command line without Airflow |
| `scripts/reextract.py` | Re-extract archived documents under a new model or prompt |
| `scripts/score_extraction.py` | Precision and recall against the golden set; writes the gate record |
| `scripts/evaluate_model.py` | Candidate comparison: precision, latency, feasibility; writes `config/models/latency/<slug>.json` |
| `scripts/check_leakage.py` | Leakage canary for a model's claimed cutoff |
| `scripts/compare_models.py` | Cross-model agreement: Jaccard, directionality, confidence correlation |
| `scripts/register_local_model.py` | Add a pulled Ollama model to `config/models/registry.yaml` with its live digest (fields from `config/models/local_candidates.yaml`) |
| `scripts/sample_corroborations.py` | Pull a sample of corroborations from the live stores for review |
| `scripts/score_corroboration_review.py` | Score a completed corroboration review |

What the evaluation scripts gate on is in [extraction.md](../../docs/ingestion/extraction.md).

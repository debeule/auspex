# Scraper HTTP API

**Status:** ready
**Blocked by:** [Centralised logging](centralised-logging.md) — structlog must be configured before the API starts emitting logs
**Branch:** `feature/scraper-api`

---

## Context

`IngestionPipeline` is already stateless: `run(source_type, cursor) → RunResult`. The cursor lives in Airflow Variables; the pipeline just receives it and returns the updated value. This maps directly onto a request/response HTTP interface with no architectural change.

The problem today: `auspex_dags.py` imports `auspex_ingest` directly inside the Airflow container. The base `apache/airflow:3.3.1` image does not have confluent-kafka, instructor, minio, or openai installed. The current workaround is a volume-mounted `PYTHONPATH`, but the third-party dependencies are missing — DAG tasks would fail on first import. The API layer removes this entirely: Airflow makes HTTP calls, needs no Python dependencies beyond `requests` (already in the base Airflow image).

Relevant existing code:
- `src/auspex_ingest/pipeline.py` — `IngestionPipeline.run()`, stateless
- `src/auspex_ingest/dag_factory.py` — `run_with_cursor()`, already abstracts cursor read/write around `pipeline.run()`; `build_dags()` accepts injected `get_var`/`set_var`
- `dags/auspex_dags.py` — current DAG entry point; will be replaced by an HTTP-calling version
- `src/auspex_ingest/reextract.py` — `ReextractionRunner` (from the re-extraction CLI spec); the `/reextract` route delegates to it
- `scripts/run_pipeline.py` — shows the pattern for wiring together pipeline components from environment variables

## What this builds

A Flask application in `src/auspex_ingest/api.py` with a `create_app()` factory, served by Gunicorn.

**Routes:**

| Method | Path | Body | Response |
|---|---|---|---|
| `GET` | `/health` | — | `{"status": "ok", "service": "ingestion-scraper"}` |
| `GET` | `/sources` | — | `{"sources": ["biorxiv", "clinicaltrials", ...]}` |
| `POST` | `/ingest/{source_type}` | `{"cursor": "<ISO-8601 UTC>"}` | `RunResult` as JSON + counts |
| `POST` | `/reextract` | re-extraction params (mirrors CLI flags) | counts JSON |

`POST /ingest/{source_type}`:
- `cursor` is optional. If absent, falls back to `now - initial_lookback` from `sources.yaml`.
- Unknown `source_type` → 404.
- Pipeline errors → 500 with `{"error": "<message>"}`. Per-document failures are counted in `RunResult.failed`, not a 500.
- Response includes all `RunResult` fields: `fetched`, `prefiltered_out`, `published`, `not_signal`, `below_threshold`, `failed`, `max_published_date_processed`.

`POST /reextract` body mirrors the CLI: `source_type` (optional), `since`, `until`, `prompt_version`, `model`, `schema_version`, `prefilter_version`, `skip_prefilter`, `dry_run`.

**Gunicorn config** at `config/gunicorn.conf.py`:
- `workers = 4` (each worker handles one concurrent source run independently)
- `timeout = 3600` — ingestion runs can take tens of minutes per source
- `bind = "0.0.0.0:8000"`

**DAG file rewrite** — `dags/auspex_dags.py` is rewritten to call HTTP instead of importing `auspex_ingest`:

```python
# cursor read/write stays in the DAG task (requirements §5)
# pipeline.run() is now POST /ingest/{source_type}
def _make_http_task(source_type, initial_lookback, scraper_url):
    def _task():
        cursor = Variable.get(f"cursor:{source_type}", default_var=None)
        if cursor is None:
            cursor = (datetime.now(UTC) - timedelta(days=initial_lookback)).isoformat()
        resp = requests.post(
            f"{scraper_url}/ingest/{source_type}",
            json={"cursor": cursor},
            timeout=3600,
        )
        resp.raise_for_status()
        result = resp.json()
        if result.get("max_published_date_processed"):
            Variable.set(f"cursor:{source_type}", result["max_published_date_processed"])
    return _task
```

`SCRAPER_API_URL` is read from environment (e.g. `http://ingestion-scraper:8000` in compose, `http://localhost:8000` on host). The DAG file no longer imports anything from `auspex_ingest` — it only needs `requests`, `airflow`, and stdlib.

`dag_factory.py` is unchanged. The new DAG file replaces the old one and does not use `dag_factory.build_dags()` — the factory's Python-callable abstraction is no longer needed when Airflow calls HTTP. Keep `dag_factory.py` for `run_with_cursor()` and `load_sources_config()`, which are still used by `scripts/run_pipeline.py`.

## Out of scope

- Authentication or API keys on the routes — this is an internal service on a private Docker network, not exposed externally.
- Async request handling — Invariant 8 (sync Python throughout) applies. Flask routes call `pipeline.run()` synchronously. Gunicorn multi-process handles concurrency.
- Rate limiting at the API layer — already handled per-host inside `RateLimitedClient`.
- API versioning — a `/v1/` prefix is acceptable but not required.
- The DAG scheduling cadence — unchanged from `sources.yaml`.

## Constraints

- **Invariant 8**: no `async`/`await` anywhere in the Flask application or route handlers. Flask is WSGI (synchronous); Gunicorn workers are separate processes. This is not a limitation — it is the correct model for CPU-bound/IO-bound synchronous work.
- **Invariant 1**: the API process writes only to MinIO and Kafka. Routes must not write to Postgres, Neo4j, or Airflow Variables.
- **Cursor ownership stays with Airflow** (requirements §5). The API never reads or writes `cursor:{source_type}` Variables. It receives a cursor in the request body and returns `max_published_date_processed` in the response. The DAG task does the Variable read/write.
- `create_app()` is a factory function, not a module-level app object. This is required for Flask test client isolation in unit tests.
- The pipeline factory inside `create_app()` follows the same wiring pattern as `scripts/run_pipeline.py` and `dags/auspex_dags.py` — construct connector, archive, extractor, producer from environment variables.
- `SCRAPER_API_URL` must be set in both the Airflow container (pointing to `http://ingestion-scraper:8000` in compose) and `.env.example`. Add to `docker/CLAUDE.md`.

## Required tests

**Unit (`tests/unit/test_api.py`)** — use Flask test client, mock `IngestionPipeline` and `ReextractionRunner`:

- `test_health_returns_200_with_service_name`
- `test_sources_returns_all_configured_source_types`
- `test_ingest_calls_pipeline_run_with_cursor_from_request_body`
- `test_ingest_returns_all_run_result_fields`
- `test_ingest_absent_cursor_defaults_to_initial_lookback`
- `test_ingest_unknown_source_type_returns_404`
- `test_ingest_pipeline_exception_returns_500_with_error_message`
- `test_reextract_dry_run_returns_estimated_count_without_publishing`
- `test_reextract_delegates_to_reextraction_runner_with_correct_params`

**Integration (`tests/integration/test_api_integration.py`)** — real MinIO + Kafka via testcontainers, stubbed LLM:

- `test_ingest_round_trip_publishes_signal_to_kafka` — POST `/ingest/biorxiv` with a fixture cursor; confirm a `ResearchSignalEvent` appears on `auspex.signals.extracted`

## Definition of done

```bash
cd services/ingestion-scraper && uv run pytest tests/unit/test_api.py -q
cd services/ingestion-scraper && uv run pytest tests/integration/test_api_integration.py -v -m integration
```

All pass.

```bash
cd services/ingestion-scraper && uv run gunicorn "auspex_ingest.api:create_app()" --timeout 3600 -w 4 -b 0.0.0.0:8000
curl http://localhost:8000/health
```

Returns `{"status": "ok", "service": "ingestion-scraper"}`.

Manual smoke test: bring up the compose stack (infra only), run the scraper on host, trigger a biorxiv ingestion via `POST /ingest/biorxiv`. Confirm `RunResult` in the response.

## Notes

- Add `flask` and `gunicorn` to `pyproject.toml` and re-lock. Pin versions in `VERSIONS.md`.
- `_PROMPT_DIR` in `extractor.py` is relative to the source file: `Path(__file__).parent.parent.parent / "prompts" / "extraction"`. In the API container this path must resolve correctly — the `prompts/` directory must be included in the Dockerfile COPY (handled in the containerisation spec).
- `run_pipeline.py` and `reextract.py` scripts remain as standalone CLI tools. They are not replaced by the API — they serve different purposes (manual one-shot runs, local dev). The API and the CLI both call the same underlying `IngestionPipeline` and `ReextractionRunner`.
- Gunicorn worker count of 4 means up to 4 concurrent source ingestion runs. With 5 sources and staggered Airflow schedules, one source may queue briefly. This is acceptable; do not increase workers beyond the number of sources.
- Long-running request concern: Airflow's `PythonOperator` with `requests.post(..., timeout=3600)` will hold a connection open for the duration of the run. This is fine — HTTP/1.1 keep-alive, single connection per task execution.
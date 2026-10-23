# ingestion-scraper

## Owners

- `docs/ingestion/connectors.md`, `docs/ingestion/pipeline.md`, `docs/ingestion/extraction.md`.
- Payloads and fixtures: `docs/system/contracts.md`.

## Commands

Run from `services/ingestion-scraper/`.

```bash
uv sync --all-extras                                     # install
uv run pytest tests/unit -q                              # unit, inner loop
uv run pytest tests/unit/test_ingestion_pipeline.py -q   # one file
uv run pytest -q                                         # everything (integration needs Docker; CI)
uv run ruff check . && uv run mypy src                   # lint + types
uv run pytest tests/unit/test_contract_fixture.py        # regenerate the signal fixture
uv run pytest tests/unit/test_raw_pointer_contract.py    # regenerate the raw pointer fixture
```

## Layout

- `src/auspex_ingest/`: package; connectors in `connectors/`, producer in `messaging/`.
- `tests/unit/`, `tests/integration/` (Testcontainers), `tests/fixtures/` (saved API responses), `tests/golden/`.
- `services/ingestion-scraper/config/sources.yaml`, `prompts/extraction/`, `scripts/`, `dags/`.

## Requirements that bite here

- INV-1: writes MinIO and Kafka only.
- INV-3: no pipeline logic in `fetch_since()`.
- INV-8: synchronous Python.
- INV-9: UTC, MinIO keys included.
- ING-001: `fetch_since` fetches and maps.
- ING-005: every request through `RateLimitedClient`.
- ENG-005: inject clients and `now()`; stub APIs with `respx`.
- ENG-004: no sockets in unit tests.
- ENG-006: Testcontainers, never a hand-started stack.
- ING-029: flush and check delivery reports.
- EXT-001: `is_signal` decides; `extract()` may return `None`.
- OPS-021: one gunicorn process with threads.
- ENG-051: logging configured once, in `create_app()`.
- CON-009: regenerate and commit the fixture on a model change.

## Trap pointers

- ING-029: `produce()` is asynchronous: `docs/ingestion/pipeline.md`, Known traps.
- ING-030: `strftime` on a non-UTC datetime: `docs/ingestion/pipeline.md`, Known traps.
- EXT-001: `instructor` invents values: `docs/ingestion/extraction.md`, Known traps.
- OPS-021: metrics are per process: `docs/operations/topology.md`, Known traps.

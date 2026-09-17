# CLAUDE.md — services/ingestion-scraper

Auto-loaded when working in this directory, in addition to the root CLAUDE.md.

## Commands
```bash
uv sync --all-extras                  # install
uv run pytest tests/unit -q           # inner loop — fast, no containers
uv run pytest tests/unit/test_ingestion_pipeline.py -q  # one file
uv run pytest -q                      # everything
uv run ruff check . && uv run mypy src
```

## Naming
Importable package `auspex_ingest` under `src/`. MinIO bucket `auspex-raw`. Topics `auspex.*`.

## Rules specific to this service
- **Sync only.** No `async`, no `await`, no `aiokafka`. `fetch_since` returns an `Iterator`.
- **This service writes to MinIO and Kafka. Nothing else.** No Postgres, no Neo4j, no Airflow Variables, no local state files.
- **`fetch_since()` fetches and maps. That is all.** No archiving, no extraction, no publishing — those belong to `IngestionPipeline`.
- **Every HTTP call goes through `RateLimitedClient`.** Never construct a bare `httpx.Client` in a connector.
- **Every datetime is timezone-aware**, converted to UTC before serialization *and* before formatting into a MinIO key.
- **Inject, don't construct:** the OpenAI client, MinIO client, Kafka producer, and `now()` provider are all constructor arguments. A test that cannot substitute one means the seam is missing.

## Testing
- `pytest-socket` disables sockets across the unit suite. That is what makes "no live API calls" true — not naming conventions. If a unit test needs a socket, it is an integration test.
- Source APIs are stubbed with `respx` against saved fixtures in `tests/fixtures/`. Never call a real API from a test.
- Integration tests use `testcontainers`, never a manually started compose stack.
- `tests/unit/test_contract_fixture.py` **generates** the Java contract fixture. If the Pydantic model changes, run it and commit the regenerated JSON.

## Traps
- `confluent-kafka` `produce()` is async — `flush()` and check delivery reports, or a run can publish nothing and report success.
- `strftime` on a non-UTC aware datetime writes local wall time with a `Z` suffix. Convert first.
- `instructor` with a non-optional response model will invent field values rather than return nothing. That is why `extract()` returns `ResearchSignalEvent | None` and the model carries `is_signal`.

# Python Module Layout

**Status:** done
**Blocked by:** —
**Branch:** `feature/python-module-layout`

---

## Context

`auspex_ingest/` already has two sub-packages: `connectors/` (the SourceConnector ABC and all source implementations) and `storage/` (the MinIO client). Everything else is a flat module at the top level of the package. Two flat modules belong in sub-packages by the same logic that created `storage/`:

- `kafka_producer.py` is an infrastructure adapter for Kafka, parallel to `storage/minio_client.py` for MinIO. There is no `messaging/` sub-package yet.
- `rate_limited_client.py` defines `RateLimitedClient`, which is imported by every connector. It is a connector-layer HTTP infrastructure concern and belongs alongside the connectors that depend on it.

There is also a domain modeling inconsistency: `models.py` contains both the wire-format domain models (`RawDocument`, `ResearchSignalEvent`) and `RunResult`, which is a pipeline execution summary. `RunResult` is only meaningful in the context of `IngestionPipeline.run()` — it is a return type, not a domain model. It lives in `models.py` because it was added there for convenience. Moving it to `pipeline.py` makes `models.py` purely about what a document or signal is.

## What this builds

Three targeted changes, each a mechanical move with no logic changes:

### 1. `messaging/` sub-package

Create `src/auspex_ingest/messaging/__init__.py` and move `kafka_producer.py` into it:

```
auspex_ingest/
  messaging/
    __init__.py        # exports KafkaProducerClient
    kafka_producer.py  # moved from top level, unchanged
```

`messaging/__init__.py` re-exports `KafkaProducerClient` so the import path `from auspex_ingest.messaging import KafkaProducerClient` works cleanly. The old path `from auspex_ingest.kafka_producer import KafkaProducerClient` no longer resolves — update all callers.

**Callers to update:**
- `scripts/run_pipeline.py` line 87: `from auspex_ingest.kafka_producer import KafkaProducerClient` → `from auspex_ingest.messaging import KafkaProducerClient`
- Any future callers introduced by the scraper-api spec will use the new path.

### 2. `rate_limited_client.py` moves into `connectors/`

`RateLimitedClient` is used by exactly six connectors and nothing else at the call site level. Move it next to its callers:

```
auspex_ingest/
  connectors/
    rate_limited_client.py  # moved from top level, unchanged
    __init__.py             # update to re-export RateLimitedClient if needed
    base.py, biorxiv.py, clinicaltrials.py, ...
```

**Import changes in connectors** (six files): `from ..rate_limited_client import RateLimitedClient` → `from .rate_limited_client import RateLimitedClient`

**Import change in `scripts/run_pipeline.py`** line 91: `from auspex_ingest.rate_limited_client import RateLimitedClient` → `from auspex_ingest.connectors import RateLimitedClient`

`connectors/__init__.py` re-exports `RateLimitedClient` so the import path `from auspex_ingest.connectors import RateLimitedClient` works.

### 3. `RunResult` moves from `models.py` to `pipeline.py`

Delete `RunResult` from `models.py`. Add it to `pipeline.py` above the `IngestionPipeline` class.

**Import changes:**
- `pipeline.py`: remove `from .models import RunResult` (definition is now local).
- `dag_factory.py` line 12: `from .models import RunResult` → `from .pipeline import RunResult`
- Any test file that imports `RunResult` from `models`: update to `from auspex_ingest.pipeline import RunResult`.

`models.py` then contains only `RawDocument` and `ResearchSignalEvent` — the wire-format domain models.

## Out of scope

- Changes to any class body or function logic
- Moving any other flat modules (`identity.py`, `normalizer.py`, `prefilter.py`, `sources.py`, `sampling.py`, `golden.py`) — they are legitimate top-level domain modules
- Moving `dag_factory.py` — it is an application layer entry point, correctly at the top level
- The `extractor.py` LLMExtractor — discussed and deferred; the OpenAI coupling is tight but not unreasonably so at this scale
- Any changes to `pyproject.toml` — no new packages or dependencies
- Any changes to the connector implementations

## Constraints

- `confluent-kafka`'s `produce()` is async — `flush()` and check delivery reports. The `KafkaProducerClient` class body is moved verbatim; do not accidentally modify it during the move.
- `_PROMPT_DIR` in `extractor.py` is resolved relative to `__file__`. This spec does not move `extractor.py`, so the path resolution is unaffected.
- Invariant 8: synchronous Python. `KafkaProducerClient` uses synchronous confluent-kafka — unchanged by this spec.
- `pytest-socket` disables sockets across the unit suite. The move must not introduce any socket-requiring import at module load time. Verify by running `uv run pytest tests/unit -q` after the move.

## Required tests

**New import-path smoke tests in `tests/unit/test_module_layout.py`:**

- `test_kafka_producer_client_is_importable_from_messaging` — `from auspex_ingest.messaging import KafkaProducerClient` succeeds; the imported name is a class.
- `test_rate_limited_client_is_importable_from_connectors` — `from auspex_ingest.connectors import RateLimitedClient` succeeds.
- `test_run_result_is_importable_from_pipeline` — `from auspex_ingest.pipeline import RunResult` succeeds; the imported name is a dataclass.
- `test_models_module_contains_only_domain_models` — `import auspex_ingest.models as m`; assert `hasattr(m, 'RawDocument')` and `hasattr(m, 'ResearchSignalEvent')` are true; assert `hasattr(m, 'RunResult')` is false.

Beyond these four, no tests need to change logic — only import paths in test files that previously imported `RunResult` from `models`.

## Definition of done

```bash
cd services/ingestion-scraper && uv run pytest tests/unit -q --rerun-all-on-no-tests-ran
```

All unit tests pass with no count regression. Specifically, `test_ingestion_pipeline.py`, `test_dag_factory.py`, and the new `test_module_layout.py` all pass.

```bash
cd services/ingestion-scraper && uv run pytest -q
```

Full suite (unit + integration) passes.

```bash
cd services/ingestion-scraper && uv run ruff check . && uv run mypy src
```

No new lint or type errors.

## Notes

- `connectors/__init__.py` currently exists (the file is present). Check whether it already exports anything before adding the `RateLimitedClient` re-export.
- The `messaging/__init__.py` re-export pattern mirrors how `connectors/__init__.py` could expose `RateLimitedClient`: the sub-package's `__init__` is the public API, the module file is the implementation.
- The `reextraction-cli` spec (already `ready`) imports from `auspex_ingest` — verify its import of `KafkaProducerClient` uses the new path once that spec is implemented. The re-extraction spec was written before this layout change; its implementation session should use `auspex_ingest.messaging`.
- `dag_factory.py` is the only internal caller of `RunResult` from `models`. External callers (scripts, tests) import it for type hints. The move is transparent as long as all callers are updated.

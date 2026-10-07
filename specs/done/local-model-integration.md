# Local Model Integration

**Status:** done
**Branch:** `feature/local-model-integration`

---

## Context

`LLMExtractorFactory` (`src/auspex_ingest/extraction_backend.py`) validates `config/models/registry.yaml`, compares a local model's digest and refuses a model without a passing gate record. It was built and tested in isolation but never wired in: `api.py` (`/ingest`, `/reextract`), `scripts/run_pipeline.py` and `scripts/reextract.py` still build a bare `openai.OpenAI(api_key=...)` with no `base_url`, so every extraction goes to OpenAI whatever `EXTRACTION_BASE_URL` says. The evaluation scripts (`score_extraction.py`, `evaluate_model.py`, `compare_models.py`) use the legacy `LLMExtractor`, which ignores the registry's `temperature`, `seed`, `timeout` and `structured_output_mode`. So the gate measures a different configuration from the one production would run.

Other gaps found while reading the code:
- `structured_output_mode` and `timeout` are required registry fields but nothing reads them.
- Nothing in production looks up a local model's digest (`model_info_fn` is never passed), and the health check the extraction-backend spec describes was not built.
- `score_extraction.py` passes at precision ≥ 0.90, while the documented gate (DECISIONS.md 2026-09-19 Option A, PREREQUISITES.md, `model_evaluation.compute_candidate_scores`) is ≥ 0.85.
- Production extracts with `prompt_version="v1"`, while the scripts default to `v1.0`. The two prompt files are byte-identical, so the gate record can never match production.
- Ollama's OpenAI-compatible endpoint does not accept `num_ctx`. The server's context window (default 4096) is set by `OLLAMA_CONTEXT_LENGTH`, so the registry's `num_ctx` is only honoured when the server is started with at least that value.
- `docker-compose.yml` passes `OPEN_AI_EXTRACTION_MODEL` to the scraper, not `EXTRACTION_*`, and the root `config/models/` is not in the image.

## What this builds

- `make_instructor_client(entry, base_url, api_key)`: one place that builds the instructor client from a registry entry (mode from `structured_output_mode`, request timeout from `timeout`). Used by the factory and all evaluation scripts.
- `ollama_digest_lookup(base_url)`: resolves `<tag>` to `<tag>@sha256:<hex>` from Ollama's native `/api/tags`. A tag that is not pulled fails loudly.
- An unreachable model server at startup logs a WARNING and defers the digest check to the first extraction. A mismatch then fails that document without publishing anything, and startup never hangs on a stopped model server.
- `build_extractor_from_env(...)`: the single env-driven construction path (`EXTRACTION_MODEL`, `EXTRACTION_BASE_URL`, `EXTRACTION_API_KEY`, `EXTRACTION_PROMPT_VERSION` default `v1.0`, `EXTRACTION_REGISTRY_PATH`, `EXTRACTION_SCORES_DIR`). `api.py`, `run_pipeline.py` and `reextract.py` use it. In `api.py` it is built lazily on the first request, so a missing gate record turns into a 500 naming the model instead of a crash-looping container.
- `GATE_PRECISION = 0.85` and `gate_record(...)` in `model_evaluation`, used by `score_extraction.py`.
- `config/models/local_candidates.yaml` lists pre-filled registry entries without digests for the recommended local models. `scripts/register_local_model.py <tag>` reads the digest from the running Ollama and appends the full entry to `registry.yaml`.
- Compose passes `EXTRACTION_*` to the scraper and mounts `config/models` read-only.
- Runbook: `docs/local-model-runbook.md`.

## Out of scope

Choosing the model (that needs real gate results on the user's machine, recorded as a CHOICE in DECISIONS.md). The backfill runner. Replacing the `if source_type ==` connector selection in `api.py`/`run_pipeline.py`, which predates this spec and should be a separate fix. The leakage canary manifest content.

## Constraints

- Invariant 6: the Ollama host comes only from `EXTRACTION_BASE_URL`. No host or port in source.
- Invariant 14: changing model or prompt label changes `extraction_id`, not `event_id`.
- §12: misconfiguration fails at startup or first use with a message naming the model.
- §13: unit suite stays socket-free (`respx` for the Ollama tags endpoint).

## Required tests

In `tests/unit/test_local_model_integration.py`:
- `test_ollama_digest_lookup_reads_native_tags_endpoint`
- `test_ollama_digest_lookup_fails_when_tag_not_pulled`
- `test_unreachable_model_server_warns_at_startup_and_checks_digest_on_first_extraction`
- `test_unknown_structured_output_mode_is_rejected`
- `test_instructor_client_uses_registry_mode_timeout_and_base_url`
- `test_extractor_from_env_targets_configured_model_and_base_url`
- `test_extractor_from_env_refuses_gate_record_for_other_prompt_version`
- `test_gate_record_passes_at_documented_precision_threshold`
- `test_register_local_model_appends_loadable_entry_with_live_digest`
- `test_register_local_model_refuses_tag_already_registered`

## Definition of done

```bash
cd services/ingestion-scraper && uv run pytest tests/unit -q && uv run ruff check . && uv run mypy src
```

Expected: all unit tests pass (225 before this spec, plus 10), ruff and mypy clean.

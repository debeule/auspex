# Extraction Backend

**Status:** ready
**Branch:** `feature/extraction-backend`

---

## Context

`services/ingestion-scraper/src/auspex_ingest/llm_extractor.py` uses `instructor` with an OpenAI-compatible client. `EXTRACTION_MODEL` is read from `.env`. `extraction_model` is already a field on `ResearchSignalEvent` (§10.2) and is part of the `extraction_id` formula (§10.4). The existing `scripts/score_extraction.py` runs the golden set against the active model.

Currently `EXTRACTION_MODEL=gpt-4o-mini` — a moving alias that can be re-pointed by OpenAI at any time. The backtesting requirement adds two new demands: the model identifier in every event must be stable and pinned (so extraction_id is reproducible), and the system must refuse to use a model with no verified quality record at the active prompt/prefilter versions.

The Phase 2 golden-set score (precision=1.000 at `prompt_version=v1.0`, `prefilter_version=v1.0`) already exists. It must be formalised as a gate record for the pinned identifier before that identifier can extract.

## What this builds

- `config/models/registry.yaml`: one entry per model. All fields required unless marked optional:
  - `backend`: `api` or `local`
  - `cutoff_date`: YYYY-MM-DD, knowledge cutoff
  - `cutoff_source`: URL of the model card or published documentation stating the cutoff
  - `num_ctx`: integer; maximum context tokens the model will be asked to handle
  - `timeout`: seconds; per-document extraction timeout
  - `temperature`: must be 0
  - `seed`: integer; for reproducibility
  - `structured_output_mode`: instructor mode string (e.g. `JSON`, `JSON_SCHEMA`)
  - `deprecation_date`: optional; API models only; ISO date of announced end-of-life
  - `digest`: required for local backend; the fully-qualified `model:tag@sha256:...` string Ollama reports on `ollama show`

- `config/models/scores/`: one JSON file per model written by `score_extraction.py`. Format: `{model_id, prompt_version, prefilter_version, precision, passed, scored_at}`. Startup checks that a file exists for the active model with `passed: true` at the active prompt and prefilter versions.

- `LLMExtractorFactory` validates the registry and score file at construction time; fails loudly before any extraction runs. No `if backend == ...` branching in the factory or extractor — backend differences live entirely in the registry entry and the `instructor.Mode` it maps to.

- `scripts/score_extraction.py --model <registry_key>` runs the golden set for the named entry and writes the score file. Switching model = add registry entry → `score_extraction.py --model <new_id>` → update `EXTRACTION_MODEL` in `.env`.

- `ExtractionBackendContractTest`: abstract pytest class. `LocalBackendContractTest` and `ApiBackendContractTest` inherit it and must pass unmodified, as `CorroborationServiceContractTest` does in Java.

- Python service startup emits a `WARNING`-level structured log when the active model's `deprecation_date` is within 60 days. Visible in the existing logging infrastructure.

- For `backend: local`, `LLMExtractorFactory` also attempts a lightweight health check (e.g. `GET /api/tags` on the Ollama endpoint) at construction time and emits `WARNING` if unreachable. Construction succeeds — the service starts — but the warning surfaces before any extraction attempt. Model server downtime must never lose documents: a `ConnectionRefusedError` during extraction is treated as a per-document failure (archived, counted, nothing published, batch continues).

- Every model switch must produce a DECISIONS.md entry (from, to, effective date) and is reflected in the `model_id` field of all future run manifests.

## Out of scope

Re-extraction of already-published events (reextraction-cli spec). The cutoff guard in the backfill runner (historical-backfill spec). Changes to `ResearchSignalEvent` schema (extraction_model is already §10.2). Model benchmarking beyond the golden-set gate.

## Constraints

- Invariant 6: no URL, credential, or host in source. `EXTRACTION_BASE_URL` and `EXTRACTION_API_KEY` from `.env` only.
- §10.4: `extraction_id` includes `extraction_model`. Changing `EXTRACTION_MODEL` to a pinned identifier changes future `extraction_id`s. Events in `signal_extraction_history` carrying the old alias value (`gpt-4o-mini`) are not rewritten — this is a traceable lineage transition per §10.4. Never rewrite history.
- §12: misconfigured registry or missing score file must fail at startup with a message naming the model and what is missing.
- §13: `pytest-socket --disable-socket` across the unit suite — LLM never called live.
- §11.2: `raw_content` is truncated to its documented maximum before building the prompt. After truncation, `system_prompt + content_block + response_budget` must fit within `num_ctx`. If it does not fit, fail loudly with a message stating the token counts — never send a silently truncated prompt to the model.
- Local backend trap — Docker/Metal: the Docker stack on macOS cannot use Metal. The model server runs on the host; the scraper reaches it via `host.docker.internal` set in `.env` as `EXTRACTION_BASE_URL`. Document this in `docker/README.md` and in the known traps section of `CLAUDE.md`.
- Local backend trap — tag re-pointing: `ollama pull gemma3:27b` downloads whatever HEAD is at that tag. The registry pins the digest; startup compares the registered digest against `ollama show <model>` output. A mismatch fails before any extraction runs.
- Local backend trap — memory: the Docker stack and the model share 36 GB. Document a measured memory budget (Docker Desktop allocation + model weight memory + KV cache at the configured `num_ctx`) and the recommended Docker Desktop memory limit in `docker/README.md`.
- Long local runs: document `caffeinate -i scripts/run_backfill.py ...` in the backfill spec notes; the runner resumes from checkpoints so an interruption is safe.

## Required tests

Unit tests in `tests/unit/test_extraction_backend.py`:
- `test_extraction_base_url_is_read_from_env` — `EXTRACTION_BASE_URL` present → client initialised with that base URL; absent → default OpenAI endpoint; value never in source
- `test_moving_alias_rejected_at_startup` — `EXTRACTION_MODEL=gpt-4o-mini` (no date suffix, not in registry) → `LLMExtractorFactory` raises `ConfigurationError` naming the model
- `test_unknown_model_fails_loudly_at_startup` — `EXTRACTION_MODEL=gpt-x-9999` → same error path; message names the missing key
- `test_registry_entry_missing_cutoff_source_is_rejected` — entry without `cutoff_source` → registry loading raises before any client is built
- `test_registry_entry_missing_digest_is_rejected_for_local_backend` — `backend: local` entry without `digest` → raises
- `test_registry_entry_missing_num_ctx_is_rejected` — entry without `num_ctx` → raises
- `test_digest_mismatch_fails_at_startup` — registered digest differs from the value returned by the injected model-info client → raises with a message naming the model and both digests
- `test_over_context_prompt_fails_loudly_not_truncated` — constructed prompt token count exceeds `num_ctx` → raises `ContextLengthError`; nothing sent to the model
- `test_malformed_json_response_is_counted_and_nothing_is_published` — model returns unparseable JSON → counted in `RunResult.failed`; no event published; batch continues
- `test_timeout_is_isolated_to_document_and_batch_continues` — model call raises `TimeoutError` on one document → that document counted as failed; next document processed
- `test_model_server_unreachable_documents_stay_archived_and_not_published` — local backend raises `ConnectionRefusedError` (not `TimeoutError`) on every call in a two-document batch → both documents archived in MinIO, none published to Kafka, failure count equals document count; distinct from the timeout test because connection-refused means the server is down, not slow
- `test_extraction_parameters_come_from_registry_not_hardcoded` — constructed request carries `temperature`, `seed`, and `num_ctx` from the registry entry, not literals
- `test_startup_refuses_model_without_passing_gate_record` — no score file for the active `(model_id, prompt_version, prefilter_version)` → `LLMExtractorFactory` raises `GateNotPassedError` naming the model
- `test_llm_is_never_called_live` — `pytest-socket` enforces zero outbound connections across the unit suite

Abstract contract tests in `tests/unit/test_extraction_backend_contract.py` (both `LocalBackendContractTest` and `ApiBackendContractTest` inherit unmodified):
- `test_backend_extract_returns_signal_event_or_none`
- `test_backend_timeout_does_not_abort_batch`
- `test_backend_malformed_response_counted_not_published`
- `test_backend_parameters_match_registry_entry`

## Definition of done

```bash
cd services/ingestion-scraper && uv run pytest tests/unit/test_extraction_backend.py tests/unit/test_extraction_backend_contract.py -q
```

Expected: 18+ passed.

Then:
- `config/models/registry.yaml` contains at least one pinned API entry (`gpt-4o-mini-2024-07-18`) with all required fields.
- `config/models/scores/gpt-4o-mini-2024-07-18.json` exists with `passed: true` for `prompt_version=v1.0`, `prefilter_version=v1.0` (derived from the Phase 2 golden-set run; re-run `score_extraction.py --model gpt-4o-mini-2024-07-18` to generate).
- `.env.example` documents `EXTRACTION_BASE_URL` (optional), `EXTRACTION_API_KEY`.
- `docker/README.md` updated: Docker/Metal limitation, `host.docker.internal`, memory budget table.
- One manual live check against a running local server recorded below.

**Manual live check (complete before marking done):**
```
model: <registry_key>
endpoint: <EXTRACTION_BASE_URL value>
document: <external_id of one archived document>
result: <extracted or None>
latency_s: <wall-clock seconds>
recorded: <YYYY-MM-DD>
```

## Notes

`gpt-4o-mini-2024-07-18` knowledge cutoff is October 2023 per the OpenAI model card. Events already in `signal_extraction_history` with `extraction_model=gpt-4o-mini` (the alias) are preserved unchanged. Future events carry the pinned identifier. The two values coexist in history; they are distinguishable by the `extraction_model` field.

The `structured_output_mode` registry field maps to an `instructor.Mode` enum value. `instructor.from_openai(client, mode=Mode.JSON)` works for both API and Ollama-compatible local servers with no branching.

For Ollama digest: run `ollama show <model>:<tag>` after pulling; copy the sha256 from the Model field. The format in the registry must be `<model>:<tag>@sha256:<hex>` so the startup check can re-derive the tag and compare.

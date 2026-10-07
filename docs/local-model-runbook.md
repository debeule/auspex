# Local extraction model: install, gate, switch

How to run extraction on a local model through Ollama instead of the OpenAI API. Run every step on the machine that will do the backfill. Scripts run from `services/ingestion-scraper/`.

## Recommended setup

**Runtime: Ollama, installed natively on the host.** Docker Desktop on macOS cannot reach the Apple GPU (Metal), so a model inside Docker would run on CPU only, several times slower. The scraper container reaches the host's Ollama through `host.docker.internal`.

**Candidates** (pre-filled in `config/models/local_candidates.yaml`):

| Ollama tag | Weights | Knowledge cutoff | Clean backfill window* | Role |
|---|---|---|---|---|
| `mistral-small:24b-instruct-2501-q4_K_M` | ~14 GB | 2023-10 | full 24 months | **Primary.** Strong instruction following and JSON output. Apache 2.0. |
| `llama3.1:8b-instruct-q8_0` | ~8.5 GB | 2023-12 | full 24 months | Fast fallback if the 24B is too slow; weaker on borderline `is_signal` calls. |
| `gemma3:27b-it-q4_K_M` | ~17 GB | 2024-08 | ~Nov 2024 onwards | Likely the best extractor, but its later cutoff leaks hindsight into the first ~2 months of the window. |

\* The window is the knowledge cutoff plus a 3-month margin, against the planned Sep 2024 to Sep 2026 backfill. A model that already knows how a trial ended inflates `directionality` and `confidence_score` (DECISIONS.md, 2026-09-19).

**Hardware.** All three fit on a 36 GB Apple-silicon Mac next to a 14 GB Docker Desktop allocation. Speed scales with memory bandwidth: an M-series Pro or Max chip is comfortable with the 24B model, while a base M-series chip may push the backfill towards several days. `evaluate_model.py` measures this, so trust its numbers over these estimates. On Linux with an NVIDIA GPU, the 24B model at Q4 needs about 16 GB of VRAM.

## 1. Install and configure Ollama

```bash
brew install ollama            # or the macOS app from ollama.com
ollama --version               # record it in VERSIONS.md (Infrastructure, "Ollama (host)")
```

Ollama's OpenAI-compatible endpoint ignores a per-request context size. The server default is 4096 tokens, and longer prompts are **silently truncated**. Raise it to the registry's `num_ctx` (8192):

```bash
# macOS app: set once, then quit and reopen Ollama
launchctl setenv OLLAMA_CONTEXT_LENGTH 8192
launchctl setenv OLLAMA_NUM_PARALLEL 1      # one request at a time keeps memory predictable

# or, running the server in a terminal instead of the app
OLLAMA_CONTEXT_LENGTH=8192 OLLAMA_NUM_PARALLEL=1 ollama serve
```

## 2. Pull and register the candidates

```bash
ollama pull mistral-small:24b-instruct-2501-q4_K_M
ollama pull llama3.1:8b-instruct-q8_0
ollama pull gemma3:27b-it-q4_K_M          # optional third candidate

cd services/ingestion-scraper
export EXTRACTION_BASE_URL=http://localhost:11434/v1 EXTRACTION_API_KEY=ollama
uv run python scripts/register_local_model.py mistral-small:24b-instruct-2501-q4_K_M
uv run python scripts/register_local_model.py llama3.1:8b-instruct-q8_0
```

`register_local_model.py` copies the candidate entry into `config/models/registry.yaml` with the digest your server reports. That pins the exact weights. If the tag is later re-pulled with different weights, the scraper refuses to extract until a new entry and gate record exist.

## 3. Evaluate and gate

Keep the Mac awake for long runs (`caffeinate -i <command>`). Run each candidate:

```bash
uv run python scripts/evaluate_model.py --model mistral-small:24b-instruct-2501-q4_K_M
uv run python scripts/score_extraction.py --model mistral-small:24b-instruct-2501-q4_K_M
```

- `evaluate_model.py` prints precision, recall, mean and p95 latency, and the backfill wall-clock estimate. It writes `config/models/latency/<tag>.json`.
- `score_extraction.py` writes the gate record `config/models/scores/<tag>.json`. The gate passes at `is_signal` precision ≥ 0.85. The service refuses any model without a passing record at the active prompt and prefilter versions.
- Both run the exact registry configuration production uses (temperature 0, fixed seed, JSON mode, timeout).

Optional before the backfill: `scripts/compare_models.py --model-a <local> --model-b gpt-4o-mini-2024-07-18` (needs a populated MinIO archive and an OpenAI key) and `scripts/check_leakage.py` (needs a real 10 to 15 entry outcome manifest; the current one is a 3-entry test fixture).

**Send the printed output back in the project thread.** The model choice is recorded as a CHOICE entry in `DECISIONS.md` from these results, not before.

## 4. Switch the pipeline to the chosen model

In `.env`:

```
EXTRACTION_MODEL=<chosen tag>
EXTRACTION_BASE_URL=http://host.docker.internal:11434/v1
EXTRACTION_API_KEY=ollama
EXTRACTION_PROMPT_VERSION=v1.0
```

Then rebuild the scraper and run one source as a test:

```bash
docker compose --profile app -f docker/docker-compose.yml --env-file .env up -d --build --wait ingestion-scraper
curl -s -X POST localhost:8000/ingest/biorxiv -H 'Content-Type: application/json' -d '{}'
```

A gate or digest problem comes back as a 500 that names the model and what is missing. If Ollama is down when the scraper starts, the scraper logs a WARNING and checks the digest before its first extraction. Documents that fail extraction stay archived in MinIO and are counted as `failed`; nothing is lost.

Commit `config/models/registry.yaml`, `config/models/scores/<tag>.json` and `config/models/latency/<tag>.json`.

## Memory budget (36 GB Mac)

| Component | 24B Q4 | 8B Q8 | 27B Q4 |
|---|---|---|---|
| Model weights | ~14 GB | ~8.5 GB | ~17 GB |
| KV cache at 8192 ctx | ~1–2 GB | ~1 GB | ~2–3 GB |
| Docker Desktop allocation | 14 GB | 14 GB | 14 GB |
| macOS + other apps | ~4 GB | ~4 GB | ~4 GB |
| **Total** | **~34 GB** | **~28 GB** | **~38 GB (too tight; drop Docker to 12 GB or close apps)** |

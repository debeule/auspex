# First Run on the Stack Machine

**Status:** blocked
**Blocked by:** the stack machine. This spec runs only on the user's MacBook Pro (Apple M4 Pro, 24 GB), started there by name. Cloud sessions and CI cannot run any of it: they have no Docker stack, no Ollama, and their network blocks `sec.gov` and model downloads, so a session anywhere else skips it. On the Mac nothing else blocks it; each step names its own precondition, and a step whose precondition is not met is skipped and reported, never worked around.
**Branch:** `feature/first-run-on-stack-machine`

---

## Context

Everything the cloud sessions could build and test is merged into `develop`. What is left needs the real stack, the real network and the Mac's GPU:

| Pending item | Recorded in | Why only the Mac |
|---|---|---|
| First point-in-time universe build; SEC bulk URL check; coverage numbers; `config/universe/backfill_scope.yaml` | `specs/point-in-time-universe.md` (blocked only on this), `DECISIONS.md` 2026-10-08 PENDING "SEC bulk URLs and first build on the stack" | `sec.gov` and Yahoo are unreachable from cloud sessions |
| `XBI` and `EURUSD=X` snapshots in MinIO | `DECISIONS.md` 2026-10-07 PENDING (market simulation), superseded by `price-bootstrap` but never confirmed | same |
| Local model gate at prompt `v1.1` | `DECISIONS.md` 2026-10-07 PENDING "gate record for prompt v1.1", `docs/local-model-runbook.md` | model weights and the GPU |
| Price history reaching back to 2013 | `DECISIONS.md` 2026-10-08 FLAG "universe window" and CHOICE "price history from 2013" | snapshots only grow forward, so this must be set before the first `up` |
| Historical backfill dry run | `specs/historical-backfill.md`, draft PR #8 | needs the stack, the gated model and its latency record |

Machine facts: Docker Desktop is capped at **8 GB** (`SETUP.md` step 2), which leaves about 10–12 GB for the model. Ollama runs natively on the host because Docker on macOS has no Metal access; containers reach it at `host.docker.internal:11434`, host scripts at `localhost:11434`.

Model choice research (thread "Research: best local model for extraction", 2026-10-07): **Llama 3.1 8B Instruct Q8_0** is the primary candidate (cutoff Dec 2023, best documented instruction following that fits). **Phi-3-medium 14B Q4_K_M** is the only challenger worth gating (cutoff Oct 2023, more biomedical knowledge, ~1.4x slower, fills the memory budget). **Llama 3.1 8B Q4_K_M** is the memory fallback. Mistral Small 24B and Gemma 3 27B stay in `local_candidates.yaml` but are not gated here: neither fits next to Docker, and Gemma's cutoff (Aug 2024) is inside the window.

The golden set (`services/ingestion-scraper/tests/golden/`, 50 documents, 46 pass the prefilter, 35 of those are signals) carries **no `v1.1` labels** (`event_type`, `primary_company`, `program_identifiers`, `trial_ids`). The gate production enforces is `is_signal` precision ≥ 0.85 at the active prompt and prefilter versions, and that is fully measurable today. The new fields are reported by `score_extraction.py` only for documents carrying their labels, so this run reports them as "not measured". Adding those labels is file work for a cloud session under `specs/golden-set-expansion.md`; it does not block this gate and is not done here. A model answering "signal" every time already scores 35/46 = 0.76, and one golden document moves precision by 2–3 points, which is why the decision rule in step 5 needs a margin before preferring the slower model.

The automated bake-off sketched in the research report (compose profile, McNemar test, hallucinated-symbol rate) was never built. This spec runs the existing per-candidate scripts instead, with the decision rule fixed below before any result exists.

## What this builds

When done, on the Mac:
1. The full stack runs healthy with price history from 2013-01-01.
2. The universe (rules version 1) is built for every month from 2014-01, its coverage is recorded, `backfill_scope.yaml` (members from `BACKFILL_SCOPE_START`, 2024-01) is committed, and `specs/point-in-time-universe.md` is `done`.
3. A local model is chosen against a rule fixed in advance, with its registry entry (digest pinned), gate record and latency record committed, and a CHOICE entry in `DECISIONS.md`.
4. The scraper extracts with that model end to end on one source.
5. If PR #8 has merged by then: the backfill dry run has been run for all five sources and recorded. Lowest priority; the live backfill is **not** part of this spec.

Every result goes into one PR from `feature/first-run-on-stack-machine` into `develop`.

## Out of scope

- The live historical backfill (any `run_backfill.py` call without `--dry-run`). Hard human gate (`DECISIONS.md` 2026-09-20 BLOCKED), and per the 2026-10-08 build-order CHOICE the LLM backfill comes after the non-LLM data builds.
- Writing or changing code, prompts, golden-set labels or rules files. If a step fails because of a bug, record it in `DECISIONS.md` as a FLAG with the exact error and stop that step; fixes go through a cloud spec.
- Editing `config/universe/rules.yaml` once version 1 has been built: the build pins the file's bytes and refuses a changed file under the same version (`RulesVersionError`), comments included.
- The gpt-4o-mini fallback and any OpenAI spend.
- Unpausing live ingestion DAGs without the user saying yes in the session (step 6).

## Constraints

- **Never print secrets.** Check that `.env` keys are set with `grep -c '^KEY=.\+'`, never `cat .env`. Never commit `.env`.
- Invariant 6: nothing from `.env` goes into a tracked file.
- Invariant 9: all recorded dates in UTC.
- Commits: author and committer are the user (`git config user.name` / `user.email` must be the user's own identity, `matthias.debeule <debeulematthias@gmail.com>`); no `Co-Authored-By` or other Claude trailers; message style per root `CLAUDE.md` (`subject: detail1, detail2`, lowercase, no body). PR body without Claude footers.
- Long steps (universe build, model pulls, evaluation) run in the background with bounded polling; keep the Mac awake with `caffeinate -i` for anything over a few minutes.
- One heavy job at a time while measuring: run model evaluation only when the universe build is not running, so latency and memory reflect the steady stack and not a build.
- Commands run from the repo root unless a step says otherwise. Host scripts read `.env` with `uv run --env-file`, not `source .env` (`SEC_USER_AGENT` contains a space).

## Steps and their checks

Each step lists its precondition, the commands, and a **Check** that must hold before the next step starts. A failed check stops that step: record what failed in `DECISIONS.md` (FLAG, with the command and output, secrets removed), tell the user, and continue only with steps that do not depend on it.

### 1. Preflight

```bash
uname -s && sysctl -n hw.memsize                          # Darwin, 25769803776
git fetch origin && git checkout develop && git pull --ff-only origin develop
git checkout -b feature/first-run-on-stack-machine
git config user.name; git config user.email                # the user's identity, not a bot
docker info --format '{{.MemTotal}}'                       # about 8 GB (8.0e9 to 8.6e9 bytes)
command -v uv jq curl
test -f .env && for k in POSTGRES_PASSWORD AIRFLOW_DB_PASSWORD NEO4J_PASSWORD MINIO_ACCESS_KEY MINIO_SECRET_KEY GRAFANA_ADMIN_PASSWORD AIRFLOW_SECRET_KEY SEC_USER_AGENT NCBI_API_KEY OPENFDA_API_KEY EPO_OPS_KEY EPO_OPS_SECRET PRICE_HISTORY_START SEC_SUBMISSIONS_BULK_URL SEC_COMPANYFACTS_BULK_URL SEC_ARCHIVES_URL BACKFILL_SCOPE_START; do printf '%s %s\n' "$k" "$(grep -c "^$k=.\+" .env)"; done
grep '^PRICE_HISTORY_START=' .env
docker volume ls --format '{{.Name}}' | grep '^auspex_' || echo "no auspex volumes"
```

**Check:** Darwin with 24 GB; the branch is created from an up-to-date `develop`; git identity is the user's; Docker memory about 8 GB (if not, ask the user to set Docker Desktop → Resources → Memory to 8 GB, the one manual setting); every key prints `1`; `PRICE_HISTORY_START=2013-01-01`. If `.env` still says `2023-01-01`, change only that line to `2013-01-01` (it is not a secret). If `.env` is missing, stop and point the user at `SETUP.md` step 1: the secrets are theirs to fill.

If auspex volumes already exist, the stack has run before. Run step 2's price check right after `up`; if `XBI` starts after 2013-01-31 the old snapshots were fetched from 2023 and will never reach back. Rebuilding them changes stored history (`DECISIONS.md` 2026-10-07 "Startup data"), so ask the user before deleting anything; only the objects in `auspex-prices` need to go, and only if no backtest has been run on them.

### 2. Stack up

```bash
docker compose --profile app -f docker/docker-compose.yml --env-file .env up -d --build --wait
docker compose --profile app -f docker/docker-compose.yml --env-file .env ps --format '{{.Name}} {{.State}} {{.Health}}'
docker logs auspex-price-bootstrap 2>&1 | tail -20
CORE_HUB_URL=http://localhost:8080 ./verify_pipeline.sh
curl -s localhost:9090/api/v1/targets | jq -r '.data.activeTargets[] | "\(.labels.job) \(.health)"'
cd services/backtesting && uv sync && uv run --env-file ../../.env python -c "
import os
from minio import Minio
from auspex_backtesting.prices.snapshot_store import PriceSnapshotStore
m = Minio(os.environ['MINIO_ENDPOINT'], access_key=os.environ['MINIO_ACCESS_KEY'], secret_key=os.environ['MINIO_SECRET_KEY'], secure=False)
s = PriceSnapshotStore(m)
for t in ['XBI', 'EURUSD=X'] + os.environ['WATCHED_TICKERS'].split(','):
    df = s.load(t.strip())
    print(t, 'MISSING' if df is None else f'{len(df)} rows {df.index.min().date()}..{df.index.max().date()}')
"; cd ../..
```

**Check:** `up --wait` exits 0; every long-running service is `running` and `healthy` where it has a health check, and the one-shots (`kafka-init`, `minio-init`, `price-bootstrap`, `elasticsearch-setup`) exited 0; `verify_pipeline.sh` prints `all checks passed`; every Prometheus target is `up`; `XBI` and `EURUSD=X` start on or before 2013-01-04 and end on the last NYSE session (or the last weekday for `EURUSD=X`). Watched tickers start at 2013-01-0x or at their listing date if later (e.g. a 2023 IPO). If `up --wait` fails on `price-bootstrap`, `docker logs auspex-price-bootstrap` names the ticker; Yahoo rate limits are the usual cause, so wait and run the same `up` again (`SETUP.md`).

Record in `DECISIONS.md`: a VERIFIED entry closing the 2026-10-07 market-simulation PENDING with the `XBI` and `EURUSD=X` row counts and date ranges.

### 3. First universe build (rules version 1, window from 2014-01)

Precondition: step 2 passed. There is one universe: it serves the slow-signal study from 2014 and the event backfill, which reads its members from `BACKFILL_SCOPE_START` (2024-01). This run is also the first real check of the SEC bulk URLs. The first run downloads two archives of a few GB each, reads a few hundred filing indexes (tickers of names delisted before 2019, paced under SEC's limit) and fetches price history from 2013 for every company listed since late 2013, so expect hours; built months are kept if a run fails, and a retry builds only what is missing.

```bash
docker exec auspex-airflow airflow dags list-runs auspex_universe_build
# If no run started within 10 minutes of `up` (the schedule fires on days 1-7 of the month):
docker exec auspex-airflow airflow dags trigger auspex_universe_build
# Poll every 15 minutes in the background until the run is success or failed:
docker exec auspex-airflow airflow dags list-runs auspex_universe_build
docker logs --since 15m auspex-price-service 2>&1 | grep -i universe | tail -5
```

When the run is `success`, read the summary (all months are stored, so this downloads nothing and returns at once):

```bash
curl -s -X POST localhost:8001/universe/build -H 'Content-Type: application/json' -d '{}' > /tmp/universe-summary.json
jq '{rules_version, already_stored, price_failures, coverage}' /tmp/universe-summary.json
cd services/backtesting && UNIVERSE_RULES_PATH=../../config/universe/rules.yaml uv run --env-file ../../.env python scripts/build_universe.py --export-backfill-scope ../../config/universe/backfill_scope.yaml && cd ../..
cd services/backtesting && uv run pytest tests/unit/test_universe.py -q --strict-markers && cd ../..
```

**Check:**
- The DAG run is `success`. A `failed` run with HTTP 409 naming `PRICE_HISTORY_START` means `.env` sets it later than 2013-11-17; that cannot be fixed without deleting stored price history, so record a FLAG and stop this step. A `failed` run whose log shows HTTP 502 naming a `sec.gov` URL means a bulk URL is wrong: find the current location on SEC's "Bulk data" page, put it in `.env` only (and in `.env.example`, which holds no secrets), restart the price service, trigger again, and record old and new URL in `DECISIONS.md`. A 403 means `SEC_USER_AGENT` is missing or rejected. A price-service log line "SEC refused ... no further index lookups" means SEC rate-limited the filing index reads: the build still succeeds, with more unresolved tickers; record the count.
- `rules_version` is `1`; `already_stored` equals the number of months from 2014-01 to the current month; `coverage` lists members, delisted count and members with partial or no price history.
- `config/universe/backfill_scope.yaml` exists and is non-empty, with CIKs, tickers and names, and its `window.start` is `2024-01`.
- `test_universe.py`: 52 passed.

Then, per the point-in-time universe spec's definition of done:
- `DECISIONS.md`: VERIFIED entry closing the 2026-10-08 PENDING, with the URLs that worked, members per month (min, median, max), delisted and acquired counts, price coverage (complete, partial, none) and the unresolved-ticker count, each also split into 2014–2018 and 2019 onward (free sources keep few delisted names from before 2019, and the protocol's `survivorship` kill criterion reads this).
- `docs/PREREQUISITES.md` "Delisted ticker price data source" row and `services/backtesting/README.md`: the measured delisted coverage replaces "recorded after the first build".
- Move `specs/point-in-time-universe.md` to `specs/done/`, set its status to `done`, update its `TODO.md` row and link.
- Commit: `point-in-time universe first build: coverage, backfill scope, spec done`.

### 3a. Catalyst date panel (after step 3)

Precondition: step 3 passed (the panel matches catalysts to the universe's companies) and `services/backtesting/src/auspex_backtesting/catalysts/` exists on `develop`; otherwise record "not run" with the reason and skip. This is the first live read of EDGAR's quarterly index and the Federal Register API (`DECISIONS.md` 2026-10-09 PENDING "sources unreachable from the cloud session"). It reads one index per quarter from 2014, then a filing index for every universe 8-K and an exhibit for those with Item 7.01 or 8.01, at 5 requests per second, so expect many hours. Every document read is kept in MinIO: a run SEC stops (exit 1, `"complete": false`) continues where it left off when run again. Do not run it alongside step 5.

```bash
for k in SEC_FULL_INDEX_URL FEDERAL_REGISTER_API_URL; do printf '%s %s\n' "$k" "$(grep -c "^$k=.\+" .env)"; done
# A key printing 0: copy its line from .env.example into .env (neither is a secret).
cd services/backtesting
UNIVERSE_RULES_PATH=../../config/universe/rules.yaml caffeinate -i uv run --env-file ../../.env \
  python scripts/build_catalyst_panel.py --since 2014-01-01 > /tmp/catalyst-summary.json
jq '{complete, added, edgar, federal_register, coverage}' /tmp/catalyst-summary.json
uv run pytest tests/unit/test_catalyst_panel.py -q --strict-markers
cd ../..
```

Then draw 30 random PDUFA and matched AdCom rows (`CatalystPanel(minio).rows()`, fixed seed, seed recorded) and check each by hand against its `evidence` and `document_url`: the date and precision match what the document says, and the CIK is the company the document is about.

**Check:**
- `complete` is `true` (run again until it is); `edgar.filings` and `edgar.exhibits_read` are non-zero, and `edgar.without_items` is a small share of `edgar.filings` (a share near all of them means the filing index's `Items` block is not where the parser looks: FLAG and stop this step); `federal_register.matched` is non-zero.
- `test_catalyst_panel.py`: 10 passed.
- Hand-check precision (correct rows / 30) is at least 0.9. Below that, record a FLAG with the wrong rows and what the rule did; tightening the phrase rules is code, so it goes to a cloud session (once, per the spec), and this step is rerun after it merges. If the second build is still below 0.9, record the precision; the guard then runs with it stated.

Record in `DECISIONS.md`: a VERIFIED entry closing the 2026-10-09 PENDING, with the URLs that worked, the counters, the coverage (catalysts per year, the share of members with any catalyst, unmatched AdCom notices, PDUFA hits by precision) and the hand-check precision with the seed. Then move `specs/catalyst-date-panel.md` to `specs/done/`, set its status to `done`, update its `TODO.md` row and link, and commit: `catalyst date panel first build: coverage, hand check, spec done`.

### 4. Install Ollama and pull the candidates

Can start while step 3 runs: pulls are network-bound. Do not run step 5 until step 3 has finished.

```bash
brew install ollama || true          # or the macOS app; either is fine
ollama --version
launchctl setenv OLLAMA_CONTEXT_LENGTH 8192
launchctl setenv OLLAMA_NUM_PARALLEL 1
# Quit and reopen the Ollama app, or run `brew services restart ollama`, so the server picks these up.
ollama pull llama3.1:8b-instruct-q8_0
ollama pull llama3.1:8b-instruct-q4_K_M
ollama pull phi3:14b-medium-128k-instruct-q4_K_M
ollama show phi3:14b-medium-128k-instruct-q4_K_M | grep -i 'context length'
curl -s localhost:11434/api/tags | jq -r '.models[].name'

cd services/ingestion-scraper && uv sync --all-extras
export EXTRACTION_BASE_URL=http://localhost:11434/v1 EXTRACTION_API_KEY=ollama
for m in llama3.1:8b-instruct-q8_0 llama3.1:8b-instruct-q4_K_M phi3:14b-medium-128k-instruct-q4_K_M; do
  uv run python scripts/register_local_model.py "$m"
done
cd ../..
```

**Check:** `ollama --version` prints a version, recorded in `VERSIONS.md` (row "Ollama (host, not a container)", replacing *resolve at install*); all three tags are listed; Phi-3's context length is 131072 (the 128k build; a 4096 here means the wrong tag was pulled); `register_local_model.py` prints `Registered <tag> with digest ...` three times and `config/models/registry.yaml` gains three `backend: local` entries with a `digest`.

To confirm the context setting reached the server, once step 5's first evaluation has loaded a model: `ollama ps` shows a context of 8192 for it (older Ollama versions print no context column; then the server log shows it, `~/.ollama/logs/server.log` for the app). If it shows 4096, the `launchctl` values did not reach the server: restart Ollama and repeat.

### 5. Gate the candidates at prompt v1.1

Precondition: step 3 finished (success or a recorded failure), step 4 passed, the stack from step 2 still up. Close other heavy apps. Per candidate, in this order: Llama Q8, Phi-3, Llama Q4.

```bash
cd services/ingestion-scraper
export EXTRACTION_BASE_URL=http://localhost:11434/v1 EXTRACTION_API_KEY=ollama
m=llama3.1:8b-instruct-q8_0     # then phi3:14b-medium-128k-instruct-q4_K_M, then llama3.1:8b-instruct-q4_K_M
sysctl vm.swapusage
caffeinate -i uv run python scripts/evaluate_model.py --model "$m" | tee "/tmp/eval-$m.txt"
caffeinate -i uv run python scripts/score_extraction.py --model "$m" | tee "/tmp/score-$m.txt"
ollama ps
sysctl vm.swapusage
cd ../..
```

`evaluate_model.py`'s memory warning only knows 8B, 24B and 27B tags; for Phi-3 use `ollama ps` (model size) and the swap delta instead.

**Check, per candidate:**
- `config/models/latency/<slug>.json` (the tag with `:` replaced by `_`) and `config/models/scores/<tag>.json` exist; the score record has `prompt_version` `v1.1`, the production prefilter version, and `passed` true or false.
- Precision, recall, mean and p95 latency and the backfill estimate are copied from the output into the notes for the DECISIONS entry. Compute `F1 = 2PR/(P+R)`.
- Swap used grew by less than 1 GB during the run ("fits": the model and the stack ran side by side without paging).
- The new-field report reads "not measured" (no `v1.1` labels). If it shows numbers, the golden set gained labels since this spec was written; record them too.

**Decision rule (fixed before any result):**
1. Eligible = gate passed (`is_signal` precision ≥ 0.85) and fits.
2. Pick `llama3.1:8b-instruct-q8_0` if eligible.
3. Phi-3 replaces it only if Phi-3 is eligible and its F1 is at least **0.05** higher (two or more golden documents' worth). A smaller gap is noise at n ≈ 46, and the 8B is faster.
4. If the Q8 is not eligible only because it does not fit, pick `llama3.1:8b-instruct-q4_K_M` if eligible.
5. If none is eligible: no CHOICE. Record a FLAG with all three results and stop steps 6 and 8. The next options are the user's: a prompt `v1.2` with one worked example (a cloud spec, since a prompt change is a new version) or the `gpt-4o-mini-2024-07-18` fallback for the backfill only (needs re-scoring and budget approval). Do neither here.

Record in `DECISIONS.md`: a CHOICE entry "Local model — CHOICE — <tag> for extraction at v1.1" under the 2026-09-19 Option A entry's instruction, with every candidate's precision, recall, F1, latency, backfill estimate, swap delta and the rule line that decided it; and a VERIFIED entry closing the 2026-10-07 PENDING "gate record for prompt v1.1". Update `docs/PREREQUISITES.md` "Local model selection" to done. Commit the registry, all gate and latency records and `VERSIONS.md`: `local model gate at v1.1: <tag> chosen, gate and latency records`.

### 6. Point the pipeline at the chosen model

Precondition: a CHOICE from step 5.

In `.env` (not tracked):

```
EXTRACTION_MODEL=<chosen tag>
EXTRACTION_BASE_URL=http://host.docker.internal:11434/v1
EXTRACTION_API_KEY=ollama
EXTRACTION_PROMPT_VERSION=v1.1
```

```bash
docker compose --profile app -f docker/docker-compose.yml --env-file .env up -d --build --wait ingestion-scraper
curl -s -X POST localhost:8000/ingest/biorxiv -H 'Content-Type: application/json' -d '{}' | jq
docker logs --since 10m auspex-ingestion-scraper 2>&1 | grep -i -E 'digest|gate|extract' | tail -10
```

**Check:** the scraper starts healthy; the ingest call returns 200 with a run summary (documents fetched, archived, extracted, failed); no 500 naming a missing gate record or digest mismatch; `failed` is not every document. A 500 that names the model and what is missing means the registry entry, gate record and `.env` disagree: compare the three, fix `.env`, rebuild.

Then ask the user whether to start live ingestion now. It runs the model on a schedule from then on. If yes:

```bash
docker exec auspex-airflow airflow dags unpause -y --treat-dag-id-as-regex '^auspex_(?!price_refresh$|universe_build$|mock$)'
docker exec auspex-airflow airflow dags list | grep auspex_
```

**Check (only if unpaused):** after the first scheduled run of each source DAG, list its runs; record which succeed and which fail, with the error, in `DECISIONS.md` (a source that the scraper API does not serve yet fails here; that is a known open bug, not something to fix in this spec).

### 7. Backfill dry run (lowest priority)

Precondition: PR #8 merged into `develop` (`test -f services/ingestion-scraper/scripts/run_backfill.py` after pulling `develop`) and a CHOICE from step 5. If either is missing, record "not run" with the reason in the PR and skip. The dry run makes no LLM calls and writes no archive or Kafka messages.

```bash
cd services/ingestion-scraper
for s in biorxiv pubmed clinicaltrials epo_ops edgar; do
  uv run --env-file ../../.env python scripts/run_backfill.py --source-type "$s" \
    --start-date 2024-09-01 --end-date 2026-09-30 --dry-run | tee "/tmp/dryrun-$s.txt"
done
cd ../..
```

Host scripts reach Ollama and core-hub on `localhost`: if `.env` holds the `host.docker.internal` URL from step 6, prefix the command with `EXTRACTION_BASE_URL=http://localhost:11434/v1 CORE_HUB_URL=http://localhost:8080`. Use the window and flags the merged `specs/historical-backfill.md` gives if they differ from these.

**Check:** each source prints documents, LLM calls after the prefilter, an estimated wall-clock from the latency record, the lineage overlap, and a run id; no LLM call is made (`ollama ps` shows no model loaded by it, the scraper log shows no extraction). Record all five in `DECISIONS.md` (the historical-backfill definition of done asks for exactly this) with the sum of estimated hours and a suggested `BACKFILL_TIME_CEILING_HOURS` (sum plus a third). Then stop: the live run waits for the user's sign-off.

### 8. Stack checks other specs left for this machine

Specs built after this one was written may end their definition of done with a check "on the stack" (for example the wiring fixes' `POST /ingest/pubmed` and `VIA` count, or the infrastructure observability spec's `node_exporter` on the Mac). Precondition: the spec is in `specs/done/` on `develop`.

```bash
grep -l -i -E 'on the stack|stack machine' specs/done/*.md
```

For each hit whose stack check has no VERIFIED entry in `DECISIONS.md` yet, run the check as that spec words it (installs it names on the host, such as `node_exporter`, are allowed; code changes are not), and record the outcome as a VERIFIED or FLAG entry. Specs still in `specs/` are not built yet: skip them.

**Check:** every hit is either recorded in `DECISIONS.md` by this run or listed in the PR as skipped with the reason.

### 9. Deliver

```bash
git status --short          # no .env, no /tmp files, no build output
git push -u origin feature/first-run-on-stack-machine
```

Open a PR into `develop` (`gh pr create --base develop` if `gh` is installed, otherwise give the user the compare link). The body lists each step as done, skipped (with the reason) or failed (with the DECISIONS entry). Move this spec to `specs/done/` in the same PR if steps 1–6 are done; steps 7–8 may be recorded as skipped.

## Required tests

Committed by this PR:
- `test_gated_local_candidate_registers_into_a_loadable_registry` (parametrized over the three gated tags) — each tag step 4 registers is in `config/models/local_candidates.yaml` with the fields the registry needs and at least 8192 context, so registration cannot fail on the Mac for a config reason.

Checks run on the Mac, each falsifiable and each tied to a step above:
- `check_host_is_the_24gb_stack_machine_with_docker_capped_at_8gb` — step 1
- `check_price_history_reaches_back_to_2013_before_any_build` — steps 1–2 (`XBI` first bar ≤ 2013-01-04)
- `check_every_stack_service_healthy_and_prometheus_targets_up` — step 2
- `check_universe_build_succeeds_against_the_configured_sec_bulk_urls` — step 3
- `check_universe_summary_covers_every_month_from_window_start` — step 3 (`already_stored` = month count)
- `check_backfill_scope_exported_and_non_empty` — step 3
- `check_catalyst_panel_build_complete_with_hand_checked_precision` — step 3a
- `check_phi3_tag_is_the_128k_context_build` — step 4
- `check_each_candidate_has_a_gate_record_at_prompt_v1_1` — step 5
- `check_candidate_fits_without_swap_growth_over_1gb` — step 5
- `check_choice_follows_the_pre_registered_decision_rule` — step 5 (DECISIONS entry names the rule line)
- `check_scraper_extracts_one_source_with_the_chosen_model` — step 6
- `check_backfill_dry_run_calls_no_llm` — step 7, when its precondition holds
- `check_every_done_spec_stack_check_is_recorded_or_skipped` — step 8

## Definition of done

On the Mac, after step 9:

```bash
cd services/ingestion-scraper && uv run pytest tests/unit/test_local_model_integration.py -q --strict-markers && cd ../..
cd services/backtesting && uv run pytest tests/unit/test_universe.py -q --strict-markers && cd ../..
test -s config/universe/backfill_scope.yaml && echo scope-ok
test -f specs/done/point-in-time-universe.md && echo universe-spec-done
test -f specs/done/catalyst-date-panel.md && echo catalyst-spec-done
ls config/models/scores/ config/models/latency/ | grep -c -E 'llama3.1|phi3'     # 6: three gate records, three latency records
grep -c -E 'Local model — (CHOICE|FLAG)' DECISIONS.md                              # at least 1
grep -E '^\| Ollama' VERSIONS.md | grep -v 'resolve at install' && echo ollama-pinned
```

Expected: 13 passed; 52 passed; `scope-ok`; `universe-spec-done`; `catalyst-spec-done` (or step 3a recorded as not run or flagged); `6`; a count of 1 or more; `ollama-pinned`. The PR into `develop` is open with CI green.

## Notes

- Why price history from 2013 now: `PriceRefresher` fetches from `PRICE_HISTORY_START` only for a ticker with no snapshot and afterwards only appends. A first `up` at 2023 would leave every snapshot unable to serve the universe from 2014 and the 2014–2021 in-sample period without deleting stored history. 2013-01-01 gives the 2014 window a year of lookback (trailing volatility, rolling beta); the universe build refuses a `PRICE_HISTORY_START` later than 45 days before its window. `DECISIONS.md` 2026-10-08 CHOICE.
- Time budget, rough: first `up` with builds under an hour; universe build several hours from 2014 (unmeasured); pulls ~22 GB; evaluation 1–2 hours for three candidates on 50 documents.
- The research report's speed-ups (prefix caching with `keep_alive: -1`, 2–4 parallel requests) matter for the backfill, not the gate. `OLLAMA_NUM_PARALLEL=1` stays for the gate so latency is comparable across candidates.
- `check_leakage.py` and `compare_models.py` are optional and skipped: the leakage manifest is a 3-entry test fixture and the comparison needs an OpenAI key.

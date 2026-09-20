# Model Evaluation

**Status:** ready
**Branch:** `feature/model-evaluation`

---

## Context

Three manual scripts, never run in CI. Same operational status as `scripts/score_extraction.py` and `scripts/sample_corroborations.py`. They exist to make model selection decisions auditable, not to gate production.

The existing `scripts/score_extraction.py` measures quality on the golden set against the active prompt. These three scripts answer separate questions: (a) how do candidates compare before committing to one, (b) does a model already know the outcomes it will extract, and (c) how interchangeable are two models' signals for backtesting purposes.

Candidate local models being evaluated for the test period and potential backfill use:
- `gemma3:27b-instruct-q4_K_M` — ~17 GB, knowledge cutoff claimed ~Aug 2024 (verify against model card before use)
- `llama3.1:8b-instruct-q8_0` — ~8 GB, knowledge cutoff Dec 2023 (stated by Meta)

## What this builds

### a. Candidate comparison — `scripts/evaluate_model.py`

Runs one or more registry entries against the full golden set. Reports per-model: `is_signal` precision, recall, confusion matrix, per-document extraction latency (mean and p95), tokens/second, and pass/fail against the ≥0.85 precision gate. Writes a latency record to `config/models/latency/<model_key_slug>.json` (format: `{model_id, mean_latency_s, p95_latency_s, tokens_per_second, token_budget, measured_at}`). The backfill runner reads this file when estimating wall-clock time for a local backend.

For local candidates, the script also prints throughput feasibility to stdout: (1) estimated wall-clock time for the full 24-month backfill at mean latency; (2) hours/day required to extract the 500-document steady-state live budget (§0.4); (3) whether (1) and (2) can coexist on one machine assuming Docker Desktop is running (baseline: ~8 GB reserved for containers; model KV cache at configured `num_ctx`; print a warning if combined memory exceeds 30 GB).

### b. Leakage canary — `scripts/check_leakage.py`

For a seeded sample of in-window documents with publicly known outcomes (completed trials with posted results, FDA approvals), asks the model — identifiers and title only, no raw content — what happened. Scores binary responses against a hand-curated manifest at `tests/fixtures/leakage_outcomes.jsonl` (format: `{event_id, source_type, published_month, question, correct_answer}`).

Reports correct-answer rate per source type and per publication month. Flags any month at ≥70% correct after the model's claimed cutoff: `"Model {id} claims cutoff {date}; rate in {month} is {pct:.0%} — record in DECISIONS.md."` The 70% threshold is not a hard gate; it's a signal worth investigating. Never publishes events.

### c. Cross-model agreement — `scripts/compare_models.py`

Takes two registry keys and a seed. Draws a seeded sample from the MinIO raw archive. Runs both models over the same documents. Reports:
- `is_signal` agreement rate (both signal / both not / disagree)
- `gene_targets` Jaccard overlap (mean over cases where both extracted a signal)
- `mechanisms` Jaccard overlap
- `directionality` agreement rate
- `confidence_score` Pearson correlation

Used to quantify how far a backtest validated on model A transfers to model B. A high `is_signal` disagreement or low Jaccard means the two models effectively extract different corpora; a backtest on one does not validate the other.

## Out of scope

Automated scheduling or CI inclusion. Writing events to Kafka or MinIO. Replacing `score_extraction.py` (which remains the gate-record writer; these scripts are for candidate evaluation, not gating).

## Constraints

- All three scripts are read-only with respect to the pipeline: no `IngestionPipeline.run()`, no Kafka produce, no MinIO put (except the latency record written by `evaluate_model.py`).
- LLM calls are made live when the scripts run; unit tests stub the LLM client and disable sockets.
- The leakage canary manifest (`leakage_outcomes.jsonl`) must not be empty at run time; unit tests use a synthetic three-entry fixture.
- The cross-model comparison script must pull documents from the MinIO archive, not call connectors — results must be reproducible from archived data alone.

## Required tests

In `tests/unit/test_model_evaluation.py`:

Script a (candidate comparison):
- `test_candidate_comparison_is_deterministic_given_a_seed` — same `--seed` produces the same sampled subset of the golden set on repeated runs
- `test_candidate_comparison_reproduces_hand_computed_scores_on_toy_set` — three-document fixture with known `is_signal` labels and stubbed model responses; precision and mean latency match hand-computed expected values

Script b (leakage canary):
- `test_leakage_canary_sampling_is_deterministic_given_a_seed` — same `--seed` on the same manifest always yields the same sample
- `test_leakage_canary_scoring_reproduces_hand_computed_result_on_toy_set` — three-entry fixture with known correct answers and stubbed responses; per-month rates match hand-computed expected values

Script c (cross-model agreement):
- `test_cross_model_agreement_is_deterministic_given_a_seed` — same `--seed` and same archive state produce the same document sample
- `test_cross_model_agreement_reproduces_hand_computed_metrics_on_toy_set` — two-document fixture; is_signal agreement and Jaccard values match hand-computed expected values

## Definition of done

```bash
cd services/ingestion-scraper && uv run pytest tests/unit/test_model_evaluation.py -q
```

Expected: 6 passed.

Then: at least one live run of `evaluate_model.py` recorded per candidate, with the latency record committed to `config/models/latency/`. Results and the model-selection decision recorded in `DECISIONS.md` before starting the backfill.

## Notes

**Fallback (Option B)**: if no local candidate reaches ≥0.85 precision on the golden set, fall back to `gpt-4o-mini-2024-07-18` for the backfill. Record this in DECISIONS.md. The lineage remains clean; the dry-run API cost estimate applies. No latency record is needed (wall-clock estimate only applies to local backends).

**Candidate usable backfill windows** (24-month window = Sep 2024–Sep 2026; 3-month cutoff margin):
- `gpt-4o-mini-2024-07-18`: cutoff Oct 2023 → earliest start Jan 2024 → full 24 months covered
- `llama3.1:8b-instruct-q8_0`: cutoff Dec 2023 (Meta-stated) → earliest start Mar 2024 → full 24 months covered
- `gemma3:27b-instruct-q4_K_M`: cutoff ~Aug 2024 → earliest start ~Nov 2024 → ~22 months (Nov 2024–Sep 2026); **verify actual cutoff against the model card before committing** — if it is Sep 2024 or later the window shrinks further

**Leakage canary**: chance baseline is ~50% for binary outcomes. A rate of 70%+ in months after the claimed cutoff is the flag threshold. Build the manifest from ClinicalTrials.gov trial statuses (machine-readable post-completion) and FDA approval dates for the 8 watched companies. Aim for 10–15 entries across at least two source types.

**Cross-model agreement**: if `is_signal` agreement between the local backfill model and the production API model is below ~85%, the two models are extracting materially different signals. A backtest on the local model's corpus does not validate the API model's live signals, and the Phase 4 finding will not generalise. Record the agreement rate in DECISIONS.md alongside the lineage decision.

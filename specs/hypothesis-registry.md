# Hypothesis Registry

**Status:** ready
**Branch:** `feature/hypothesis-registry`

---

## Context

`docs/strategy-research.md` defines 8 hypotheses (H1–H8) for Phase 4 evaluation. Testing multiple hypotheses on the same corpus without pre-registration is a known source of inflated false-positive rates (Harvey, Liu & Zhu 2016; Bailey & López de Prado 2014). This spec provides the pre-registration mechanism: each hypothesis is a versioned file committed before any backtest runs against it. The backtesting module refuses to run against a hypothesis whose content differs from its registration.

The deflated Sharpe ratio computation in the evaluation-protocol spec reads the trial counter — the number of times a hypothesis has been tested — from the append-only log this spec creates.

## What this builds

A pre-registration system for hypotheses. When this spec is done:
- `config/hypotheses/h1.yaml` through `config/hypotheses/h8.yaml` exist, each committed before any backtest runs against them.
- `config/hypotheses/registry.jsonl` is an append-only log: one entry per registration event (hypothesis id, file hash, registered_at). Never edited.
- `config/hypotheses/trials/` holds one `.jsonl` file per hypothesis: append-only, one line per backtest run (run_id, hypothesis_id, file_hash, started_at, result_summary). Never edited.
- `scripts/register_hypothesis.py`: writes or updates a hypothesis YAML file and appends to `registry.jsonl`. Idempotent on content — same content twice is a no-op (no new registry entry).
- `auspex_backtesting/hypothesis.py`: `load_hypothesis(hypothesis_id)` reads the YAML; `verify_hypothesis(hypothesis_id)` recomputes the SHA-256 of the current file and compares against the most recent registry entry. Raises `HypothesisModifiedError` if they differ.
- The backtesting module's `run_backtest()` calls `verify_hypothesis()` at startup. An unregistered hypothesis id raises `HypothesisNotRegisteredError`. A modified hypothesis raises `HypothesisModifiedError`. Both are loud failures, not warnings.

### Hypothesis YAML schema

```yaml
id: h1
version: 1
description: "Structural convergence premium — entity-only corroboration precedes abnormal return"
signal_definition:
  variant: entity-only
  filter: none
  join_field: corroborated_at
entry_timing_days: 1
holding_period_days: [5, 10, 20, 30]
benchmark: XBI
exit: fixed_horizon_close
status: pre-registered
registered_at: "2026-09-20T00:00:00Z"
```

A content change (any field other than `registered_at`) requires a new registration, which updates `registered_at` and appends a new entry to `registry.jsonl`. The old trial records are preserved — they are associated with the old hash.

## Out of scope

UI for hypothesis management. Version migration. Marking hypotheses promoted or rejected — that is a manual DECISIONS.md entry. Integration with the evaluation-protocol spec (that spec reads the trial count from `trials/h<n>.jsonl` directly).

## Constraints

- `registry.jsonl` and all `trials/*.jsonl` files are append-only by convention and must never be edited. The module does not enforce this at the filesystem level (no special file modes) — it is a process constraint documented here.
- Hash is SHA-256 of the YAML file bytes as written to disk (UTF-8, no normalisation).
- A hypothesis YAML that has never been registered produces `HypothesisNotRegisteredError`, not a silent pass.
- No invariant from root CLAUDE.md is directly implicated (this is pure config and scripts, not pipeline or DB).

## Required tests

In `tests/unit/test_hypothesis_registry.py`:

- `test_backtest_refuses_unregistered_hypothesis_id` — `run_backtest()` called with a hypothesis_id that has no entry in `registry.jsonl` raises `HypothesisNotRegisteredError`
- `test_backtest_refuses_modified_hypothesis` — hypothesis YAML registered, then file content changed without re-registration; `verify_hypothesis()` raises `HypothesisModifiedError`
- `test_registration_is_idempotent_on_content` — `register_hypothesis.py` called twice with identical YAML content; `registry.jsonl` has exactly one entry for that id and hash
- `test_content_change_creates_new_registry_entry` — YAML content changed and re-registered; `registry.jsonl` has two entries for the same id with different hashes; both are preserved
- `test_trial_log_entry_is_appended_on_each_run` — two backtest runs on the same hypothesis append two lines to `trials/h1.jsonl`; no lines are modified
- `test_verify_hypothesis_passes_when_content_is_unchanged` — registered, file unchanged, `verify_hypothesis()` returns without error

## Definition of done

```bash
cd services/backtesting && uv run pytest tests/unit/test_hypothesis_registry.py -q
```

Expected: 6 passed.

Then: all 8 hypothesis YAML files (`config/hypotheses/h1.yaml` through `h8.yaml`) committed, each matching a `registry.jsonl` entry. No backtest in the session log was run before registration.

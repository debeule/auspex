# Specs

Each file in this directory is a self-contained feature spec. One spec = one independently executable unit of work. The rules for specs are ENG-016 to ENG-018 and ENG-028 in [`docs/engineering/change-workflow.md`](../docs/engineering/change-workflow.md); this page explains them.

---

## What a spec must be

These three properties are ENG-017.

**Self-contained.** A new session opening only the spec file and root `AGENTS.md` must have everything needed to start. Do not write a spec that says "see also spec X" or "after spec Y is done." If something is a prerequisite, it goes in `Blocked by`.

**Scoped to one deliverable.** If two features can be built and tested independently, they get separate specs. A spec that takes more than one focused session to execute is probably two specs.

**Named after what it does.** `historical-backfill.md`, not `phase-4-step-0.md`. The filename and title survive the plan that motivated them.

---

## Required fields

Every spec must have all of these before status can be set to `ready` (ENG-017; Docs impact is ENG-018). Check E reads the list of required fields and sections from `docs-check.toml` `[specs]`; this table gives their meanings.

| Field | What it must contain |
|---|---|
| **Status** | `draft` · `ready` · `blocked` · `hold` · `done` |
| **Blocked by** | External dependency preventing start — credential, user decision, or another spec. Omit if not blocked. |
| **Branch** | Suggested branch name. Descriptive, not `phase-4`. |
| **Docs impact** | The requirement IDs the spec adds (as `NS-new`, with the owner doc), changes or retires, or `none — <reason>`. |
| **Context** | What already exists that this spec builds on. Enough that a cold session knows where to look. |
| **What this builds** | Concrete deliverable in plain language. Not "implement X" — what the system can do when done that it cannot do now. |
| **Out of scope** | Hard boundary. Prevents scope creep mid-execution. At least one line. |
| **Constraints** | Which invariants (`docs/system/invariants.md`, `INV-n`) and which owner-doc requirements apply, cited by ID, never restated. Any specific traps for this feature. |
| **Required tests** | Minimum list written before implementation. Each must be falsifiable — name after the behaviour, not the task. See rules below. |
| **Definition of done** | The exact command(s) that must pass plus the expected output. One block, runnable as-is. |

**Notes** is optional but encouraged for non-obvious decisions and open questions.

---

## Test naming rules

A test name is a claim (ENG-047). The name must make the claim falsifiable:

| Bad | Good |
|---|---|
| `test_backfill_works` | `test_backfill_does_not_advance_the_live_cursor` |
| `test_price_ingestion` | `test_price_series_is_read_from_minio_when_present` |
| `test_step_4_0_dry_run` | `test_backfill_dry_run_reports_estimates_without_calling_llm` |

Do not reference plan steps, phase numbers, or spec filenames in test names, function names, or file names (ENG-049). Name what the thing does.

---

## Statuses

The statuses and where each spec lives are ENG-016; an archived spec is not edited (ENG-036).

| Status | Meaning |
|---|---|
| `draft` | Spec exists but is incomplete — missing tests, tasks too vague, or scope unclear. Not executable yet. |
| `ready` | All required fields are complete. Can be handed to a session and executed. |
| `blocked` | Has a complete definition but cannot start — external credential, user decision, or depends on another spec that is not done. |
| `hold` | Parked by an owner decision; the file lives in `specs/hold/`; it returns to `blocked` or `ready` by a decision. |
| `done` | Implemented, tests green, committed. Move the file to `specs/done/` and point its `TODO.md` row there, in the same PR. Do not delete — the constraints and test list are useful reference. |

A spec moves from `draft` to `ready` in a scoping session. Scoping means filling in required tests and the definition of done — not implementation (ENG-017).

---

## Citing decisions

Cite a `DECISIONS.md` entry by its full heading in backticks, for example `` `## 2026-10-09 — CI — CHOICE — one prefix for every test image` ``; use double backticks when the heading itself contains a backtick. Never cite an entry by a register number (ENG-026).

---

## Handoff

When a session stops before the spec is done, it adds a `## Handoff` section to the spec with these seven lines (ENG-028):

- `Written against: develop @ <sha>`, plus the branch and how many commits it is ahead
- `Done`
- `Not done`
- `Next`
- `Docs`
- `Open decisions`
- `Verify`

The next session re-reads whatever changed on `develop` since that SHA before relying on it.

---

## Template

Copy `_template.md` when creating a new spec.

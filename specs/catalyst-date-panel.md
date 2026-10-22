# Catalyst Date Panel

**Status:** blocked
**Blocked by:** the first panel build on the stack machine (Definition of done, second block; `specs/first-run-on-stack-machine.md` step 3a). All code and all 10 required tests are in (`auspex_backtesting.catalysts`, `scripts/build_catalyst_panel.py`); neither SEC nor the Federal Register is reachable from cloud sessions (`DECISIONS.md` 2026-10-09 PENDING).
**Branch:** `feature/catalyst-date-panel`
**Docs impact:** None: behaviour approved in RES-041…RES-044; the remaining work is acceptance on the stack machine.

---

## Context

The code is merged at the integration base (`auspex_backtesting.catalysts`, `scripts/build_catalyst_panel.py`). The panel is defined by RES-041…RES-044 in [docs/research/panels.md](../docs/research/panels.md), with the shared panel rules RES-026…RES-030; `CatalystGuard` reads it (RES-078). The first build runs in `specs/first-run-on-stack-machine.md` step 3a.

## What this builds

1. PDUFA dates from 8-K exhibits and advisory committee meetings from Federal Register notices, each known at its document's time: RES-041.
2. Precision kept as written: RES-042.
3. `CatalystPanel`: revisions as new rows, `as_of`, every document kept: RES-043.
4. `binaries_between` for the guard, on aware datetimes: RES-044, RES-078.
5. `scripts/build_catalyst_panel.py`: each document fetched once, universe companies only: RES-029, RES-030.

## Out of scope

- Readout guidance ("topline data expected in Q2"). It is too varied for phrase rules and is left to the LLM-based `specs/catalyst-calendar.md`.
- Live serving through core-hub (`specs/catalyst-calendar.md`).
- Any LLM call.
- Outcomes (approved, CRL, vote results).

## Constraints

- Point-in-time, and a revision never changes an earlier read: RES-026, RES-043.
- SEC `User-Agent`, pacing and blocks: the SEC traps in [docs/ingestion/connectors.md](../docs/ingestion/connectors.md).
- INV-6: URLs in config. INV-9: UTC.
- Each document fetched once: RES-029.
- Unit tests open no network socket: ENG-004.

## Required tests

Merged. Each test is cited in the `Verified by` cell of its RES ID. Definition of done reruns them.

Acceptance on the stack machine:
- `check_catalyst_panel_builds_from_2014` — the build finishes (`"complete": true`).
- `check_catalyst_coverage_recorded` — catalysts per year, the share of members with any catalyst, unmatched notices and hits by precision are in `DECISIONS.md`.
- `check_catalyst_hand_check_precision` — 30 random hits checked by hand (date and company right); precision ≥ 0.9, or the phrase rules tightened once and the result recorded.

## Definition of done

```bash
cd services/backtesting && uv run pytest tests/unit/test_catalyst_panel.py -q --strict-markers
```

Expected: 10 passed.

On the stack machine:
- The run: the panel built for 2014 onward (`specs/first-run-on-stack-machine.md` step 3a).
- The coverage record, in `DECISIONS.md`.
- The hand check: 30 random hits. If precision is below 0.9, tighten the phrase rules once; if it is still below, record it and run the guard with that precision stated.
- Closes `## 2026-10-09 — Catalyst date panel — PENDING — sources unreachable from the cloud session`.

## Notes

- A run SEC stops (exit 1, `"complete": false`) continues where it left off when run again. Do not run it alongside the Ollama gate (first-run step 5).

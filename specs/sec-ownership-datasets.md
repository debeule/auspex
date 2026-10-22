# SEC Ownership Datasets (13F Holdings and Insider Transactions)

**Status:** blocked
**Blocked by:** the first backfill on the stack machine (Definition of done, second block). All code and the 15 required tests are in `auspex_backtesting.ownership`; what remains is running `scripts/fetch_ownership.py` against SEC and recording coverage, which cloud sessions cannot reach (`specs/first-run-on-stack-machine.md` step 3b, `DECISIONS.md` 2026-10-09 PENDING).
**Branch:** `feature/sec-ownership-datasets`
**Docs impact:** None: behaviour approved in RES-026…RES-036; the remaining work is acceptance on the stack machine.

---

## Context

The code is merged at the integration base (`auspex_backtesting.ownership`, `scripts/fetch_ownership.py`). The 13F holdings panel, the specialist rule and the insider panel are defined by RES-026…RES-036 in [docs/research/panels.md](../docs/research/panels.md). The first backfill runs in `specs/first-run-on-stack-machine.md` step 3b.

## What this builds

1. `Form13FDatasetStore`, the CUSIP mapping and how reports and amendments are counted: RES-032.
2. <a id="SpecialistClassifier"></a>**`SpecialistClassifier`** — defined in RES-033 ([docs/research/panels.md#RES-033](../docs/research/panels.md#RES-033)). This item is cited by the registered H9 hypothesis (`config/hypotheses/h9.yaml:18`); do not rename or remove it.
3. `InsiderTransactionStore`, the daily Form 4 fill and the offering-participation flag: RES-034.
4. Point-in-time readers on acceptance time, on one split basis, with their input times: RES-031, RES-035, RES-036.
5. `scripts/fetch_ownership.py`: each data set fetched once, universe companies only, missing with a reason: RES-027, RES-028, RES-029, RES-030.

## Out of scope

- The composite score itself (`specs/holdings-composite-score.md`).
- Insider-copying event trades (dropped by the research: the reaction ends within two to three sessions).
- Form 13D/13G, Form 144, N-PORT.
- Live alerting on Form 4s.

## Constraints

- Point-in-time on acceptance time: RES-026, RES-031.
- SEC `User-Agent`, pacing and blocks: the SEC traps in [docs/ingestion/connectors.md](../docs/ingestion/connectors.md).
- Each data set fetched once: RES-029.
- INV-9: UTC acceptance times.
- INV-6: data-set URLs in config, not code.
- Unit tests open no network socket: ENG-004.

## Required tests

Merged. Each test is cited in the `Verified by` cell of its RES ID. Definition of done reruns them.

Acceptance on the stack machine:
- `check_ownership_backfill_completes_from_2013` — `scripts/fetch_ownership.py` finishes for 2013 onward.
- `check_ownership_coverage_recorded` — the first data set of each kind, issuer coverage, the unmapped CUSIP share and the three layout points the readmes leave open are in `DECISIONS.md`.

## Definition of done

```bash
cd services/backtesting && uv run pytest tests/unit/test_ownership_datasets.py -q --strict-markers
```

Expected: 15 passed.

On the stack machine:
- The run: `scripts/fetch_ownership.py` from 2013 (`specs/first-run-on-stack-machine.md` step 3b).
- The coverage record: the first available data set of each kind, issuer coverage, the unmapped CUSIP share and the three layout points, in `DECISIONS.md`.
- The hand check: the three layout points against the real files.
- Closes `## 2026-10-09 — SEC ownership datasets — PENDING — first backfill on the stack machine`.

## Notes

- CUSIP to CIK is the weakest link: over 10% of universe market value unmapped in any quarter is flagged in `DECISIONS.md` before H9 runs.
- Run it after the universe build and the catalyst panel have finished, not alongside either, so the runs stay under SEC's limit together.

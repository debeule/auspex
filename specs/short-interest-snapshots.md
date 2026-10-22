# Short Interest Snapshots

**Status:** blocked
**Blocked by:** the first fetch on the stack machine (Definition of done, second block). All code and the 9 required tests are in `auspex_backtesting.short_interest`; what remains is a FINRA API credential (`docs/PREREQUISITES.md`) and running `scripts/fetch_short_interest.py` against FINRA, which cloud sessions cannot reach (`specs/first-run-on-stack-machine.md` step 3c, `DECISIONS.md` 2026-10-10 PENDING).
**Branch:** `feature/short-interest-snapshots`
**Docs impact:** None: behaviour approved in RES-037…RES-040; the remaining work is acceptance on the stack machine.

---

## Context

The code is merged at the integration base (`auspex_backtesting.short_interest`, `scripts/fetch_short_interest.py`). Short interest is defined by RES-037…RES-040 in [docs/research/panels.md](../docs/research/panels.md), with the shared panel rules RES-026…RES-030. The first fetch runs in `specs/first-run-on-stack-machine.md` step 3c.

## What this builds

1. Publication dates from FINRA's rule and published calendar, and `as_of` on publication: RES-037.
2. `ShortInterestStore`: the record, days to cover, absent periods and the coverage report: RES-038.
3. The share of shares outstanding and the change since the previous period, on one split basis: RES-039.
4. The history start and the FINRA credential: RES-040.
5. Each period fetched once and appended, never rewritten: RES-027, RES-029.

## Out of scope

- Daily short-sale volume (Reg SHO) files: different measure, separate decision.
- Borrow fees and availability (IBKR, see `docs/PREREQUISITES.md`).
- Hypotheses using short interest (registered separately).
- Wiring into `ShortGuard` (portfolio-and-risk), which reads `as_of()` when that spec is implemented.

## Constraints

- INV-9: UTC; dates are NYSE session dates.
- Point-in-time on publication: RES-026, RES-037.
- Each period fetched once: RES-029.
- Unit tests open no network socket: ENG-004.

## Required tests

Merged. Each test is cited in the `Verified by` cell of its RES ID. Definition of done reruns them.

Acceptance on the stack machine:
- `check_finra_credential_present` — `.env` has the FINRA API credential (`docs/PREREQUISITES.md`).
- `check_short_interest_fetch_completes` — the first fetch for the universe tickers finishes from `SHORT_INTEREST_HISTORY_START`.
- `check_short_interest_coverage_recorded` — the first settlement date, the empty periods and the gaps are in `DECISIONS.md`.

## Definition of done

```bash
cd services/backtesting && uv run pytest tests/unit/test_short_interest.py -q --strict-markers
```

Expected: 9 passed.

On the stack machine:
- The run: the FINRA credential obtained, then the first fetch for the universe tickers (`specs/first-run-on-stack-machine.md` step 3c).
- The coverage record: the first available settlement date, the empty periods and the gaps, in `DECISIONS.md`.
- Closes `## 2026-10-10 — Short interest snapshots — PENDING — first fetch on the stack machine`.

## Notes

- FINRA is not SEC, so the fetch may run alongside the ownership backfill.

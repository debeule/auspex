# Holdings Composite Score

**Status:** blocked
**Blocked by:** the first score run on the stack machine (Definition of done, second block, `specs/first-run-on-stack-machine.md` step 3e). All code and the 12 required tests are in `auspex_backtesting.scores`; the run needs the universe build (step 3) and the ownership backfill (step 3b), which cloud sessions cannot reach (no `sec.gov`).
- Met in code: `specs/sec-ownership-datasets.md` (readers), `specs/done/ownership-share-basis.md` (one split basis, missing with a reason), `specs/short-interest-snapshots.md` (`ShortInterestStore`), `specs/point-in-time-universe.md` (monthly snapshots with market cap and dollar volume), `specs/done/slow-signal-preregistration.md` (H9 registered).
**Branch:** `feature/holdings-composite-score`
**Docs impact:** None: behaviour approved in RES-050…RES-054; the remaining work is acceptance on the stack machine.

---

## Context

The code is merged at the integration base (`auspex_backtesting.scores`, `scripts/compute_holdings_scores.py`). The H9 score is defined by RES-050…RES-054 in [docs/research/panels.md](../docs/research/panels.md); it reads the ownership and short-interest panels (RES-031…RES-040). The first run is `specs/first-run-on-stack-machine.md` step 3e.

## What this builds

1. Every parameter from the registered H9, inputs read at the rebalance open: RES-050.
2. The tradable floor and the no-floor cells: RES-051.
3. Components, missing rules, percentile ranks and `known_at_max`: RES-052.
4. The component variant chosen from coverage dates only: RES-053.
5. `HoldingsScoreBuild` and `scripts/compute_holdings_scores.py`: snapshots once per version, floor and date, with the coverage report: RES-054, RES-075.

## Out of scope

- Portfolio construction, costs, evaluation (`specs/done/cross-sectional-portfolio-backtest.md`).
- Any LLM input. Gene-target or mechanism peer momentum (report 1's suggested use of corroboration as an input) is a later, separately registered variant.
- Re-weighting components after seeing results.

## Constraints

- Point-in-time throughout, every row valid: RES-026, RES-054.
- Deterministic ranks: RES-052.
- Snapshots written once: RES-027, RES-054.
- Unit tests open no network socket: ENG-004.

## Required tests

Merged. Each test is cited in the `Verified by` cell of its RES ID. Definition of done reruns them.

Acceptance on the stack machine:
- `check_holdings_scores_computed_from_2014` — scores for every month from 2014, floor and no-floor.
- `check_holdings_coverage_and_variant_recorded` — the coverage report and the component variant used are in `DECISIONS.md`.

## Definition of done

```bash
cd services/backtesting && uv run pytest tests/unit/test_holdings_composite.py -q --strict-markers
```

Expected: 15 passed (the 12 required tests and 3 supporting ones).

On the stack machine:
- The run: scores computed for 2014 onward, floor and no-floor (`specs/first-run-on-stack-machine.md` step 3e).
- The coverage record: the coverage report and the component variant used, in `DECISIONS.md`.

## Notes

- The run needs the universe build and the ownership backfill first; short interest only decides the variant, so a missing FINRA fetch gives the two-component variant by its pre-registered rule.

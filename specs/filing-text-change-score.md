# Filing Text Change Score

**Status:** blocked
**Blocked by:** the first panel build on the stack machine (`specs/first-run-on-stack-machine.md` step 3d: both universes' panels, coverage and a 20-filing hand check in `DECISIONS.md`). The code and its tests are done; the earlier blockers (point-in-time universe, H10 registered in `specs/done/slow-signal-preregistration.md`) are met. Score snapshots use `ScoreSnapshot` from `specs/done/cross-sectional-portfolio-backtest.md`.
**Branch:** `feature/filing-text-change-score`
**Docs impact:** None: behaviour approved in RES-045…RES-049 and RES-013; the remaining work is acceptance on the stack machine.

---

## Context

The code is merged at the integration base (`auspex_backtesting.filings`, `scripts/build_filing_panel.py`, the `us_small_mid` rules file). The filing panel and the H10 score are defined by RES-045…RES-049 in [docs/research/panels.md](../docs/research/panels.md); the second universe by RES-013 in [docs/research/universe.md](../docs/research/universe.md). The first build runs in `specs/first-run-on-stack-machine.md` step 3d.

## What this builds

1. A second universe as its own rules file, snapshots apart: RES-013, RES-020.
2. `FilingIndex`: quarterly index rows stored once, membership applied on use: RES-045.
3. `FilingSectionArchive`: Item 1A cut from originals, missing with a reason: RES-046.
4. `TextChangeScore`: comparison filing and change score, known at acceptance: RES-047.
5. `RiskFactorChangeScore`: the monthly `ScoreSnapshot` per universe: RES-048, RES-075.
6. `scripts/build_filing_panel.py`: each filing fetched once, a SEC refusal stops before scoring: RES-029, RES-049.

## Out of scope

- Items 3 and 7 (Legal Proceedings, MD&A): a later, separately registered variant if Item 1A shows anything.
- LLM labelling of what changed (report 3 suggests it as optional; it adds a category, not the core signal).
- Portfolio construction and evaluation (`specs/done/cross-sectional-portfolio-backtest.md`).
- Non-US filers (20-F, 40-F).

## Constraints

- Point-in-time on the later filing's acceptance: RES-026, RES-047.
- SEC `User-Agent`, pacing and blocks: the SEC traps in [docs/ingestion/connectors.md](../docs/ingestion/connectors.md).
- Each filing fetched once: RES-029.
- INV-9: UTC; INV-6: URLs in config.
- Unit tests open no network socket: ENG-004; the MinIO round trip runs in CI (`tests/integration/test_filing_panel_storage.py`, RES-048).

## Required tests

Merged. Each test is cited in the `Verified by` cell of its RES ID. Definition of done reruns them.

Acceptance on the stack machine:
- `check_filing_panels_build_for_both_universes` — the biotech universe's panel, then `us_small_mid`'s, built for 2014 onward.
- `check_filing_panel_coverage_recorded` — filings found, sections by status, missing and unscored by reason, and members scored per month are in `DECISIONS.md`.
- `check_filing_section_hand_check` — 20 random filings' Item 1A cuts checked by hand, with the hit rate in `DECISIONS.md`, before scoring.

## Definition of done

```bash
cd services/backtesting && uv run pytest tests/unit/test_filing_text_change.py -q --strict-markers
cd services/backtesting && uv run pytest tests/unit/test_universe.py -q --strict-markers
cd services/backtesting && uv run pytest tests/unit/test_filing_panel.py -q --strict-markers
```

Expected: 13 passed; 58 passed; 3 passed. The integration test passes in CI.

On the stack machine:
- The run: the panel built for 2014 onward over the biotech universe, then `us_small_mid` (`specs/first-run-on-stack-machine.md` step 3d).
- The coverage record, in `DECISIONS.md`.
- The hand check: 20 random filings, recorded in `DECISIONS.md` before scoring.

## Notes

- Survivorship is the main threat to the broad-universe test: free price sources drop many delisted small caps. Read the universe coverage report before the score is run.
- The broad universe is built first by its own `build_universe.py --rules` run, which fetches price history for every listed US company; expect it to take longer than the biotech build.

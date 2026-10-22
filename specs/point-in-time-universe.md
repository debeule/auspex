# Point-in-Time Stock Universe

**Status:** blocked
**Blocked by:** the first universe build on the stack machine (Definition of done, second block). All code and all 23 required tests are in; what remains is recording the measured member counts and price coverage in `DECISIONS.md` and committing `config/universe/backfill_scope.yaml`, which needs SEC and Yahoo access from the stack (`DECISIONS.md` 2026-10-08 PENDING).
**Branch:** `feature/point-in-time-universe`
**Docs impact:** None: behaviour approved in RES-013…RES-025 and RES-072…RES-073; the remaining work is acceptance on the stack machine.

---

## Context

The code is merged at the integration base (`auspex_backtesting.universe`, the `auspex_universe_build` DAG, `scripts/build_universe.py`). The universe is defined by RES-013…RES-025 in [docs/research/universe.md](../docs/research/universe.md), and a backtest with a universe by RES-064, RES-072 and RES-073 ([simulation.md](../docs/research/simulation.md), [backtesting.md](../docs/research/backtesting.md)). The first build runs in `specs/first-run-on-stack-machine.md` step 3.

## What this builds

1. One rules file per universe, locked by its version, rules-based rather than the watchlist, with accepted limitations: RES-013, RES-014, RES-019, RES-022, RES-023.
2. Admission at the first NYSE session of the month on data public by then, unknowns never excluding: RES-015, RES-016, RES-018.
3. Listing spans, exits and ticker history from filings: RES-017.
4. Monthly snapshots written once under the rules version: RES-020.
5. Members without complete price history kept and reported, prices from free sources only: RES-024, RES-001.
6. Backtest integration (membership spans, windows past a delisting, events outside the universe, the survivorship summary): RES-064, RES-072, RES-073.
7. The backfill scope export: RES-021.
8. SEC bulk archives and pacing for the build: RES-025.

## Out of scope

- Changing ingestion connectors or `sources.yaml` to filter by universe (the historical-backfill spec reads `backfill_scope.yaml`; live ingestion scoping is a separate change).
- Removing the user's watchlist. The watchlist stays as the user's curated view in the dashboard; it no longer defines the backtest universe.
- Point-in-time SIC reclassification (SEC publishes current SIC only; a reclassified company is classified by today's code, recorded as a known limitation).
- Factor exposures and sector neutralization.

## Constraints

- INV-6: the SEC `User-Agent` and the bulk URLs come from `.env`.
- INV-9: UTC throughout; the rebalance date is RES-015.
- INV-15: test-first.
- Point-in-time admission: RES-015.
- SEC rate limit and bulk archives: RES-025; the SEC traps in [docs/ingestion/connectors.md](../docs/ingestion/connectors.md).
- Price snapshots fetched once: RES-001.
- Unit tests open no network socket: ENG-004.

## Required tests

Merged. Each test is cited in the `Verified by` cell of its RES ID. Definition of done reruns them.

Acceptance on the stack machine:
- `check_universe_build_succeeds_against_the_configured_sec_bulk_urls` — the first build from 2014-01 completes.
- `check_universe_coverage_recorded` — member counts per month, the delisted count and the coverage split 2014–2018 / 2019 on are in `DECISIONS.md`.
- `check_backfill_scope_exported_and_non_empty` — `config/universe/backfill_scope.yaml` is committed.

## Definition of done

```bash
cd services/backtesting && uv run pytest tests/unit/test_universe.py -q --strict-markers
```

Expected: 58 passed (the 23 required tests among them).

On the stack machine:
- The run: the universe built from 2014-01 (`specs/first-run-on-stack-machine.md` step 3).
- The coverage record: member counts per month, the delisted count and the price coverage split 2014–2018 / 2019 on, in `DECISIONS.md`.
- The files to commit: `config/universe/backfill_scope.yaml`.
- Closes `## 2026-10-08 — Point-in-time universe — PENDING — SEC bulk URLs and first build on the stack`.

## Notes

- The first build downloads two SEC archives of a few GB each and fetches price history for every member; built months are kept if a run fails, and a retry builds only what is missing.
- Ticker history is the weakest link: unresolved members are listed in the coverage report, never silently dropped. Read that list before recording coverage.

# Holdings Composite Score

**Status:** blocked
**Blocked by:** the first score run on the stack machine (Definition of done, second block, `specs/first-run-on-stack-machine.md` step 3e). All code and the 12 required tests are in `auspex_backtesting.scores`; the run needs the universe build (step 3) and the ownership backfill (step 3b), which cloud sessions cannot reach (no `sec.gov`).
- Met in code: `specs/sec-ownership-datasets.md` (readers), `specs/done/ownership-share-basis.md` (one split basis, missing with a reason), `specs/short-interest-snapshots.md` (`ShortInterestStore`), `specs/point-in-time-universe.md` (monthly snapshots with market cap and dollar volume), `specs/done/slow-signal-preregistration.md` (H9 registered).

**Progress (2026-10-15):** Red before implementation: `ModuleNotFoundError: No module named 'auspex_backtesting.scores'` at collection of `test_holdings_composite.py`. 12 required tests plus 3 supporting in the same file (tie break by CIK, version per floor, the build wired over the stores) and 2 in `test_ownership_parsing.py` (the input times the panels report), 19 mutations caught. Choices made while building are in `DECISIONS.md` (2026-10-15, Holdings composite score).

**Branch:** `feature/holdings-composite-score`

---

## Context

Research report 1 (2026-10-07) ranks one biotech signal family as still paying a slow long-only trader after Belgian costs: who owns the stock (healthcare specialist funds), whether insiders are buying, and how heavily it is shorted, ranked monthly across US small and mid-cap biotech. Its evidence is moderate to weak: one net-of-cost practitioner backtest 2015–2025 (Verdad, January 2026; the PDF itself was not read), an older blog study, and pre-2005 short-interest evidence. Its estimate, after publication decay and costs, is +3 to +5% a year over XBI for the long-only top quintile, marked inferred. The main failure mode it names: the top quintile may be small-cap biotech beta that XBI does not capture.

H9 is registered in `config/hypotheses/h9.yaml` by the slow-signal pre-registration spec. This spec computes its score; the cross-sectional portfolio backtest runs it.

## What this builds

In `services/backtesting/src/auspex_backtesting/scores/holdings_composite.py`, every parameter read from the registered `config/hypotheses/h9.yaml` (component names are its keys):

1. **`HoldingsCompositeScore.compute(rebalance_date) → HoldingsScoredMonth`**: the month's `ScoreSnapshot`, the member count, members under the floor and members left out, by CIK, and missing ownership reads by reason. Inputs are read as of the rebalance session's open. H9's tradable floor ($500M market cap and $2M 20-day median dollar volume, from the universe snapshot of that month; unknown is under the floor) applies unless the `no_floor` cells are being built, which keep the universe's own floors.
   - `specialist_13f_ownership` — `HoldingsPanel.specialist_ownership`; higher ranks higher; missing when its share basis is unknown.
   - `net_insider_buying` — `InsiderPanel.net_insider_buying` over 90 days by acceptance time, scaled by market cap; higher ranks higher; zero for no activity (not missing); missing without a market cap. Purchases flagged as offering participation are excluded.
   - `days_to_cover` — the ticker's record in FINRA's latest settlement period published before the rebalance day (FINRA gives no time of day, so a period published that day is too late); lower ranks higher. A ticker absent from that period, or with no record for it, is missing, not zero; an older period is never carried forward. Days to cover replaces short interest over float (2026-10-08 research: it measures how crowded the short is relative to liquidity, and does not need float).
   - Percentile ranks per component among the names scored that month (best 1.0, worst 1/n, ties broken by CIK); `score` = mean of a name's available ranks. A name with fewer than two components is left out and counted.
   - `known_at_max` per row = the latest of its inputs' times: the 13F reports and the share count the ownership read used, the Form 4s the insider figure counted, and midnight after FINRA's publication day in New York.
2. **Component selection** — `component_variant(h9, short_interest_start)`: the two-component variant when the first reported short interest settlement date is after the in-sample start (2014-01-01), or there is none; the snapshot's `variant` column records which. Never chosen by looking at returns.
3. **`HoldingsScoreBuild.run()`** and **`scripts/compute_holdings_scores.py`** (`--no-floor` for the no-floor cells): one `ScoreSnapshot` per universe month whose rebalance date has passed and has none, under `scores/h9/1/` (`1-no_floor`), and a coverage report: the variant, per month members, under the floor, scored and left out, per year the correlation of each pair of component ranks (a composite of three near-identical ranks is one signal).

## Out of scope

- Portfolio construction, costs, evaluation (`specs/done/cross-sectional-portfolio-backtest.md`).
- Any LLM input. Gene-target or mechanism peer momentum (report 1's suggested use of corroboration as an input) is a later, separately registered variant.
- Re-weighting components after seeing results.

## Constraints

- Point-in-time throughout; `ScoreSnapshot.validate()` must pass for every row.
- Deterministic ranks: ties broken by CIK.
- Snapshots are written once per `(hypothesis version, floor, rebalance date)`.
- `pytest-socket`; synthetic panels in unit tests.

## Required tests

In `services/backtesting/tests/unit/test_holdings_composite.py`:
- `test_name_below_h9_tradable_floor_is_not_scored_unless_no_floor_variant`
- `test_short_interest_published_after_rebalance_is_not_used`
- `test_lower_days_to_cover_ranks_higher`
- `test_offering_participation_purchase_is_excluded_from_insider_buying`
- `test_no_insider_activity_scores_zero_not_missing`
- `test_missing_short_interest_is_missing_not_zero`
- `test_name_with_fewer_than_two_components_is_left_out_and_counted`
- `test_score_is_mean_of_available_component_percentile_ranks`
- `test_known_at_max_is_latest_input_time_and_before_rebalance_open`
- `test_two_component_variant_is_chosen_by_short_interest_start_date_only`
- `test_snapshot_for_a_rebalance_date_is_never_overwritten`
- `test_coverage_report_includes_component_rank_correlations`

Supporting: `test_ties_are_broken_by_cik`, `test_score_version_keeps_floor_variants_apart`, `test_build_from_stores_reads_panels_and_chooses_variant_from_short_interest`; in `test_ownership_parsing.py`, `test_specialist_ownership_known_at_is_latest_report_read_or_share_count` and `test_net_insider_buying_known_at_is_latest_counted_transaction`.

## Definition of done

```bash
cd services/backtesting && uv run pytest tests/unit/test_holdings_composite.py -q --strict-markers
```

Expected: 15 passed (the 12 required tests and 3 supporting ones).

Then: scores computed for 2014 onward on the stack machine, floor and no-floor (`specs/first-run-on-stack-machine.md` step 3e); coverage report and the component variant used recorded in `DECISIONS.md`. The H9 backtest is run by `scripts/run_portfolio_backtest.py`, in-sample first; the holdout is read once, in a session the user starts.

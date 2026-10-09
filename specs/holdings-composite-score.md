# Holdings Composite Score

**Status:** blocked
**Blocked by:**
1. `specs/sec-ownership-datasets.md` — specialist ownership and net insider buying readers.
2. `specs/short-interest-snapshots.md` — `ShortInterestStore.as_of()` and the first available settlement date.
3. Met in code: `specs/point-in-time-universe.md` (PR #21, #22) — monthly universe snapshots and `MarketCapEstimator`. Runs on the stack need its first build.
4. `specs/slow-signal-preregistration.md` — H9 registered (components, floors, variants, two-component fallback rule).

**Branch:** `feature/holdings-composite-score`

---

## Context

Research report 1 (2026-10-07) ranks one biotech signal family as still paying a slow long-only trader after Belgian costs: who owns the stock (healthcare specialist funds), whether insiders are buying, and how heavily it is shorted, ranked monthly across US small and mid-cap biotech. Its evidence is moderate to weak: one net-of-cost practitioner backtest 2015–2025 (Verdad, January 2026; the PDF itself was not read), an older blog study, and pre-2005 short-interest evidence. Its estimate, after publication decay and costs, is +3 to +5% a year over XBI for the long-only top quintile, marked inferred. The main failure mode it names: the top quintile may be small-cap biotech beta that XBI does not capture.

H9 is registered in `config/hypotheses/h9.yaml` by the slow-signal pre-registration spec. This spec computes its score; the cross-sectional portfolio backtest runs it.

## What this builds

In `services/backtesting/src/auspex_backtesting/scores/holdings_composite.py`:

1. **`HoldingsCompositeScore.compute(score_date) → ScoreSnapshot`** for the universe snapshot of that month, after H9's tradable floor ($500M market cap and $2M 20-day median dollar volume as of the score date; the `no_floor` variant skips it and uses the universe's own floors):
   - `specialist_ownership` — higher ranks higher.
   - `insider_buying` — net open-market buying over 90 days by acceptance time, scaled by market cap; higher ranks higher; zero for no activity (not missing). Purchases flagged as offering participation by the ownership reader are excluded.
   - `days_to_cover` — latest **published** short interest over its average daily volume; lower ranks higher. Missing for a ticker in a published period → the component is missing for that name, not zero. Days to cover replaces short interest over float (2026-10-08 research: it measures how crowded the short is relative to liquidity, and does not need float).
   - `score` = mean of available component percentile ranks; a name with fewer than two components is left out and counted.
   - `known_at_max` per row = the latest acceptance or publication time among its inputs.
2. **Component selection** — reads H9's pre-registered rule: if short-interest history starts after the in-sample start, the two-component variant runs and the snapshot records which. Never chosen by looking at returns.
3. **`scripts/compute_holdings_scores.py`** — writes one `ScoreSnapshot` per rebalance month over the window, and a coverage report: names scored, names dropped for missing components, component correlations per year (a composite of three near-identical ranks is one signal).

## Out of scope

- Portfolio construction, costs, evaluation (`specs/cross-sectional-portfolio-backtest.md`).
- Any LLM input. Gene-target or mechanism peer momentum (report 1's suggested use of corroboration as an input) is a later, separately registered variant.
- Re-weighting components after seeing results.

## Constraints

- Point-in-time throughout; `ScoreSnapshot.validate()` must pass for every row.
- Deterministic ranks: ties broken by CIK.
- Snapshots are written once per `(hypothesis version, rebalance date)`.
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

## Definition of done

```bash
cd services/backtesting && uv run pytest tests/unit/test_holdings_composite.py -q --strict-markers
```

Expected: 12 passed.

Then: scores computed for 2014 onward on the stack machine; coverage report and the component variant used recorded in `DECISIONS.md`. The H9 backtest is run by `scripts/run_portfolio_backtest.py`, in-sample first; the holdout is read once, in a session the user starts.

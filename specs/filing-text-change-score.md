# Filing Text Change Score

**Status:** blocked
**Blocked by:**
1. Met in code: `specs/point-in-time-universe.md` (PR #21, #22) — universe snapshots. The broad universe's rules file is item 0 below.
2. `specs/slow-signal-preregistration.md` — H10 registered.

**Branch:** `feature/filing-text-change-score`

---

## Context

Research report 3 (2026-10-07) found one direction with peer-reviewed evidence whose payoff builds slowly enough to survive Belgian costs: firms whose 10-K and 10-Q text barely changes from a year earlier outperform firms whose text changes (Cohen, Malloy and Nguyen, "Lazy Prices", JF 2020, 1995–2014; up to 188 bp a month on Risk Factors changes, t = 2.76). Its out-of-sample evidence is weak: hobby and student replications on large caps after 2009 find nothing for the whole 10-K, and only Risk Factors shows a weak spread after 2015 (t about 2). Most of the original alpha is on the short side (the changers), which this project does not trade. Nobody has tested US small and mid caps after 2014, which is what this spec makes testable. Report 3's estimate is 0 to +2% a year over a passive ETF, its own judgment.

H10 is registered in `config/hypotheses/h10.yaml`. The score is deterministic text similarity; no LLM.

What exists: `connectors/sec_edgar.py` in the scraper (EFTS, `data.sec.gov/submissions` lookup, acceptance time after PR #16) and the SEC traps in root `CLAUDE.md`. The scraper writes only to MinIO and Kafka (Invariant 1) and its pipeline is built for documents that go to extraction. A filing panel for a backtest is reference data, so it lives in `services/backtesting` like prices and ownership data, with its own small SEC client using the shared limiter settings from `.env`.

## What this builds

Direction decided 2026-10-08 (both): H10 runs as an exclusion filter inside the biotech universe and as a standalone test on broad US small and mid caps.

0. **A second universe.** The merged universe code reads one file, `config/universe/rules.yaml`, and stores snapshots under `universe/{rules_version}/`. Make the rules file a parameter: `config/universe/<universe_id>.yaml`, with `rules.yaml` kept as the biotech universe's file so its stored snapshots stay valid, snapshots under `universe/{universe_id}/{rules_version}/` for any new universe, and an empty SIC list meaning every SIC code. Add `us_small_mid.yaml`: all SIC codes, the same exchanges, liquidity floor and window as the biotech universe, market cap $500M–$10B (an optional ceiling). It is a second market, not a second version of the biotech universe: each universe has one rules file. Nothing in the code names a universe.

In `services/backtesting/src/auspex_backtesting/filings/`:

1. **`FilingIndex`** — EDGAR quarterly `form.idx` (full-index) per quarter, kept rows for `10-K`, `10-K405`, `10-KT`, `10-Q` and their `/A` forms whose CIK is a universe member in that month. Stored once per quarter in MinIO.
2. **`FilingSectionArchive`** — for each kept filing, the primary document (via the submissions JSON, known trap), Item 1A (Risk Factors) cut out by heading rules tested on fixtures (10-K "Item 1A" through "Item 1B"/"Item 2"; 10-Q Part II "Item 1A" through "Item 2"), normalised to plain text, stored at `auspex-prices/filings/item1a/{cik}/{accession}.txt` with `acceptance_datetime`, form, fiscal period. A filing whose section cannot be cut is recorded as `section_missing` with the reason; 10-Qs that only say "no material changes" are recorded as `no_change_statement`.
3. **`TextChangeScore`** — for each filing, the comparison filing is the same form and fiscal period one year earlier from the same CIK. Score = 1 − cosine similarity of term-frequency vectors (lowercased, tokens of letters, no stemming), with Jaccard similarity stored alongside. `no_change_statement` scores 0 change. Known at the later filing's acceptance time.
4. **`RiskFactorChangeScore.compute(rebalance_date) → ScoreSnapshot`** — for each universe member, the most recent score accepted before the rebalance open within the last 120 days; members without one are left out and counted. Score sign: least change ranks highest.
5. **`scripts/build_filing_panel.py`** — fetches, cuts and scores for the window, then writes monthly `ScoreSnapshot`s; prints coverage: filings found, sections cut, missing by reason, members scored per month.

## Out of scope

- Items 3 and 7 (Legal Proceedings, MD&A): a later, separately registered variant if Item 1A shows anything.
- LLM labelling of what changed (report 3 suggests it as optional; it adds a category, not the core signal).
- Portfolio construction and evaluation (`specs/cross-sectional-portfolio-backtest.md`).
- Non-US filers (20-F, 40-F).

## Constraints

- Point-in-time: a score is never known before its later filing's acceptance time; the comparison filing must also be accepted before that.
- SEC: descriptive `User-Agent`, ≤ 5 req/s through the shared limiter, no retry during a block. Volume: report 3 estimates about 60,000 filings for a 1,500-filer sample over 2014–2025; for the biotech universe it is a few thousand a year. Archive sections, not full documents, to keep the Mac's disk budget small.
- Requirements §8 pattern: each filing fetched once.
- Invariant 9: UTC; Invariant 6: URLs in config.
- `pytest-socket`; fixture filings in unit tests.

## Required tests

In `services/backtesting/tests/unit/test_universe.py` (added to the universe suite):
- `test_two_universe_rules_files_build_and_snapshot_independently`
- `test_biotech_rules_file_keeps_its_existing_snapshot_prefix`
- `test_empty_sic_list_admits_every_sic_code`
- `test_market_cap_ceiling_excludes_larger_members`

In `services/backtesting/tests/unit/test_filing_text_change.py`:
- `test_item_1a_is_cut_from_a_10k_fixture_matching_golden_text`
- `test_item_1a_is_cut_from_a_10q_part_ii_fixture`
- `test_section_that_cannot_be_cut_is_recorded_missing_with_reason`
- `test_no_material_changes_statement_scores_zero_change`
- `test_identical_sections_score_zero_change`
- `test_fixture_pair_scores_within_0_001_of_hand_computed_value`
- `test_comparison_filing_is_same_form_and_fiscal_period_one_year_earlier`
- `test_score_known_at_is_later_filing_acceptance_time_not_filing_date`
- `test_score_accepted_after_rebalance_open_is_not_used`
- `test_member_without_score_in_last_120_days_is_left_out_and_counted`
- `test_least_changed_filer_ranks_highest`
- `test_filing_already_archived_is_not_refetched`
- `test_requests_carry_the_configured_user_agent`

## Definition of done

```bash
cd services/backtesting && uv run pytest tests/unit/test_filing_text_change.py -q --strict-markers
cd services/backtesting && uv run pytest tests/unit/test_universe.py -q --strict-markers
```

Expected: 13 passed, then the universe suite with the 4 new tests passing and every existing universe test unchanged.

Then: the panel built on the stack machine for 2014 onward over the biotech universe, then `us_small_mid`; coverage recorded in `DECISIONS.md`. The H10 backtest runs through `scripts/run_portfolio_backtest.py`; the holdout (2021–2025) is read once, in a session the user starts.

## Notes

- Survivorship is the main threat to the broad-universe test: free price sources drop many delisted small caps, and the protocol's `survivorship` kill criterion (over 10% of member-months unpriced) may stop the broad test before it says anything about the signal. The biotech universe has the same problem at a smaller scale. The coverage report from the point-in-time universe spec is read before the score is run.
- Section cutting is the hard, error-prone part. Spot-check 20 random filings by hand and record the hit rate in `DECISIONS.md` before scoring.

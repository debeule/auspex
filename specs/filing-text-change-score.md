# Filing Text Change Score

**Status:** blocked
**Blocked by:** the first panel build on the stack machine (`specs/first-run-on-stack-machine.md` step 3d: both universes' panels, coverage and a 20-filing hand check in `DECISIONS.md`). The code and its tests are done; the earlier blockers (point-in-time universe, H10 registered in `specs/done/slow-signal-preregistration.md`) are met. Score snapshots use `ScoreSnapshot` from `specs/done/cross-sectional-portfolio-backtest.md`.

**Branch:** `feature/filing-text-change-score`

---

## Context

Research report 3 (2026-10-07) found one direction with peer-reviewed evidence whose payoff builds slowly enough to survive Belgian costs: firms whose 10-K and 10-Q text barely changes from a year earlier outperform firms whose text changes (Cohen, Malloy and Nguyen, "Lazy Prices", JF 2020, 1995–2014; up to 188 bp a month on Risk Factors changes, t = 2.76). Its out-of-sample evidence is weak: hobby and student replications on large caps after 2009 find nothing for the whole 10-K, and only Risk Factors shows a weak spread after 2015 (t about 2). Most of the original alpha is on the short side (the changers), which this project does not trade. Nobody has tested US small and mid caps after 2014, which is what this spec makes testable. Report 3's estimate is 0 to +2% a year over a passive ETF, its own judgment.

H10 is registered in `config/hypotheses/h10.yaml`. The score is deterministic text similarity; no LLM.

What exists: the catalyst panel's EDGAR reader in `services/backtesting` (`catalysts/press_releases.py`: quarterly `master.idx`, filing `-index.htm` pages with acceptance time and documents by type, a paced `HttpSource`, a `DocumentCache`) and the SEC traps in root `CLAUDE.md`. The scraper writes only to MinIO and Kafka (Invariant 1) and its pipeline is built for documents that go to extraction. A filing panel for a backtest is reference data, so it lives in `services/backtesting` like prices and ownership data, reusing that reader.

## What this builds

Direction decided 2026-10-08 (both): H10 runs as an exclusion filter inside the biotech universe and as a standalone test on broad US small and mid caps.

0. **A second universe.** The universe code read one file, `config/universe/rules.yaml`, and stored snapshots under `universe/{rules_version}/`. The rules file is now a parameter: `config/universe/<universe_id>.yaml`, with `rules.yaml` kept as the biotech universe's file under its existing prefix, snapshots under `universe/{universe_id}/{rules_version}/` for any other universe (`UniverseStore.for_rules_file`; an all-digit id is refused, so it never collides with a version), an empty SIC list meaning every SIC code and an optional `max_market_cap_usd` ceiling. `us_small_mid.yaml`: all SIC codes, the same exchanges and window as the biotech universe, market cap $500M–$10B and a $2M median dollar volume floor, the bounds H10 registered for this universe in `config/hypotheses/h10.yaml` (a test keeps the two equal). It is a second market, not a second version of the biotech universe: each universe has one rules file. Nothing in the code names a universe. `scripts/build_universe.py --rules PATH` builds it (the DAG builds only `UNIVERSE_RULES_PATH`'s), `scripts/run_portfolio_backtest.py --universe-rules PATH` trades it, and `PortfolioBacktest.input_keys` asks the universe store for its snapshot keys.

In `services/backtesting/src/auspex_backtesting/filings/`:

1. **`FilingIndex`** — EDGAR's quarterly `master.idx` (full index, CIK first; the copy the catalyst panel keeps is read instead when there is one), rows for `10-K`, `10-K405`, `10-KT`, `10-Q` and their `/A` forms from any filer, stored once per finished quarter at `auspex-prices/filings/index/{yyyy}-q{q}.json` (the quarter in progress is read again each run). Universe membership is applied when the rows are used: a filing is kept when its CIK is a member in its filing month or the 17 months after (long enough to be scored at a rebalance or be the comparison of a filing that is), so one stored index serves every universe.
2. **`FilingSectionArchive`** — for each kept original filing (amendments are counted, not cut: an amendment rarely restates Item 1A), the filing's `-index.htm` page, which gives the acceptance time, the period of report and the primary document by its Type column (the `index.json` directory listing of the known trap has no type; the submissions JSON is not needed), then the primary document. Item 1A (Risk Factors) is cut by heading rules tested on fixtures: a heading counts only at the start of a line, and the longest span from an "Item 1A" heading to the next end heading wins, which skips the table of contents (10-K end: "Item 1B", "Item 1C" or "Item 2"; 10-Q end: Part II "Item 2" to "Item 6"). The text is normalised (one line per HTML block, whitespace collapsed, entities decoded, page numbers dropped) and kept with acceptance time, form, filing date and period of report at `auspex-prices/filings/item1a/{cik}/{accession}.json.gz`. A filing whose section cannot be cut is kept as `section_missing` with its reason (`no_item_1a_heading`, `no_end_heading`, `not_provided` for a smaller reporting company's "not required", `no_acceptance_time`, `no_period_of_report`, `no_primary_document`, `filing_index_not_found`, `primary_document_not_found`); a section of at most 150 words that says "no material changes" and no "except" or "set forth below" is `no_change_statement`. Neither SEC page is kept.
3. **`TextChangeScore`** — for each filing, the comparison filing is the same form family (10-K, 10-K405 and 10-KT together; 10-Q) from the same CIK, whose period of report is one year earlier within ±45 days and which was accepted before it (the closest period wins). Change = 1 − cosine similarity of term-frequency vectors (lowercased, tokens of letters, no stemming), with Jaccard similarity stored alongside. `no_change_statement` scores 0 change. Known at the later filing's acceptance time. Filings without a score are counted by reason (`section_missing`, `no_comparison`, `comparison_without_text`).
4. **`RiskFactorChangeScore.compute(rebalance_date) → ScoredMonth`** — for each member of that month's universe snapshot, the most recent score accepted before the rebalance open within the last 120 days, as a `ScoreSnapshot` (`cik, ticker, score, known_at_max` plus `change, jaccard, accession, form, comparison_accession`); members without one are left out and returned with the member count. Score sign: `score` = −change, so the least change ranks highest. Snapshots of one H10 version are kept apart per universe: `scores/h10/{version}/` for the biotech universe, `scores/h10/{version}-{universe_id}/` for another (`1-us_small_mid`).
5. **`scripts/build_filing_panel.py --rules PATH`** — `FilingPanelBuild`: indexes from 550 days before the universe's first month, archives, scores, then writes a `ScoreSnapshot` for every stored universe month that has none and whose rebalance day has passed (a filing accepted before that day's open reaches the next night's index); prints coverage: filings found, amendments not cut, sections by status, missing by reason, unscored by reason, members scored and left out per month. A refusal from SEC stops the run before scoring, with `complete: false`; the next run continues from what was archived.

## Out of scope

- Items 3 and 7 (Legal Proceedings, MD&A): a later, separately registered variant if Item 1A shows anything.
- LLM labelling of what changed (report 3 suggests it as optional; it adds a category, not the core signal).
- Portfolio construction and evaluation (`specs/done/cross-sectional-portfolio-backtest.md`).
- Non-US filers (20-F, 40-F).

## Constraints

- Point-in-time: a score is never known before its later filing's acceptance time; the comparison filing must also be accepted before that.
- SEC: descriptive `User-Agent`, ≤ 5 req/s through the shared limiter, no retry during a block. Volume: report 3 estimates about 60,000 filings for a 1,500-filer sample over 2014–2025; for the biotech universe it is a few thousand a year. Archive sections, not full documents, to keep the Mac's disk budget small.
- Requirements §8 pattern: each filing fetched once.
- Invariant 9: UTC; Invariant 6: URLs in config.
- `pytest-socket`; fixture filings in unit tests. The MinIO round trip runs in CI against LocalStack (`tests/integration`, new `Run integration tests` step in the backtesting job).

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

Added with the build (not counted in the 13): `test_us_small_mid_rules_are_the_universe_h10_registered` and `test_portfolio_run_reads_universe_snapshots_under_its_store_prefix` in `test_universe.py`; three panel-build tests in `tests/unit/test_filing_panel.py` (a snapshot per universe month with coverage, a rerun fetches nothing and rewrites nothing, a run SEC stops writes no snapshot); `tests/integration/test_filing_panel_storage.py` (archive, index and snapshots round-trip through S3).

## Definition of done

```bash
cd services/backtesting && uv run pytest tests/unit/test_filing_text_change.py -q --strict-markers
cd services/backtesting && uv run pytest tests/unit/test_universe.py -q --strict-markers
cd services/backtesting && uv run pytest tests/unit/test_filing_panel.py -q --strict-markers
```

Expected: 13 passed; 58 passed (the 4 new tests and 2 more among them, every existing universe test unchanged); 3 passed. The integration test passes in CI.

Then: the panel built on the stack machine for 2014 onward over the biotech universe, then `us_small_mid` (`specs/first-run-on-stack-machine.md` step 3d); coverage recorded in `DECISIONS.md`. The H10 backtest runs through `scripts/run_portfolio_backtest.py`; the holdout (2021–2025) is read once, in a session the user starts.

## Notes

- Survivorship is the main threat to the broad-universe test: free price sources drop many delisted small caps, and the protocol's `survivorship` kill criterion (over 10% of member-months unpriced) may stop the broad test before it says anything about the signal. The biotech universe has the same problem at a smaller scale. The coverage report from the point-in-time universe spec is read before the score is run.
- Section cutting is the hard, error-prone part. Spot-check 20 random filings by hand and record the hit rate in `DECISIONS.md` before scoring.

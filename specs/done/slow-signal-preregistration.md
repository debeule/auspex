# Slow-Signal Pre-registration

**Status:** done
**Blocked by:** none. The direction decision was taken 2026-10-08 (`DECISIONS.md`, "direction: both"): H9 in biotech with H10 as its filter, and the standalone H10 test on broad US small and mid caps.

**Branch:** `feature/slow-signal-preregistration`

---

## Context

The 2026-10-07 edge research (three independent reports, `/mnt/project-files/research/edge-result-{1,2,3}.md`, synthesis in `DECISIONS.md` 2026-10-07 "edge research synthesis") moved the alpha path from single events to slow, monthly cross-sectional scores:
- **H9, biotech holdings composite**: specialist 13F ownership, insider open-market buying, low short interest, ranked monthly across the point-in-time biotech universe.
- **H10, risk-factor change ("lazy prices")**: year-on-year change in a filer's 10-K/10-Q Item 1A text; firms that changed least are held.
- **H8, negative-event veto**: H8 was suspended on PR #15 with the call "rework as an exit or avoid filter". The veto is that rework.

PR #15 locks an evaluation protocol written for event studies: market-model abnormal returns per event, two-way clustered t, a family budget of 64 `(holding_period, known_at_delay, variant)` cells, and a forward check of "12 months, 60 independent events, clustered t > 2". Two parts of it do not fit monthly portfolios:
1. A portfolio's unit of observation is a month, not an event. Its inference is a time-series t on monthly excess returns with autocorrelation-robust errors.
2. The forward check cannot be met by any realistic portfolio in 12 months: t > 2 on 12 monthly returns needs an annualised Sharpe above 2. Report 1 puts a realistic long-only excess Sharpe for H9 well below that.

A third finding affects the existing protocol: `docs/strategy-research.md` uses a 20-day σ of about 7% for stocks it describes as 80% annualised volatility. 80% annualised is about 22.5% over 20 trading days (80% × √(20/252)). At 22.5%, t > 2 on 60 independent events needs a mean net abnormal return of about 5.8% per event, which no hypothesis in the registry expects.

Two follow-up reports (2026-10-08, `/mnt/project-files/research/edge-result-4.md` and `belgian-costs.md`) changed the design. None of these ideas pays smoothly through the calendar: each pays when later news arrives (readouts, financings, earnings) over 3 to 18 months, so a hard monthly top-15 swap is partly random and costs about 6% a year in turnover. Timing entries around catalysts does not beat a slow banded rotation either. The median 30-day pre-PDUFA run-up is about zero, holding through a binary has an expected value near zero with a fat left tail, and catalyst cycling costs 10 to 12.5% a year. It also shortens holds into the range where the 33% speculation-tax risk applies. The corrected round trip is about 1.25% (1.1 to 1.4%) for liquid small and mid caps, of which 0.70% is TOB, and 2 to 4% for micro-caps. So the design scores monthly, trades quarterly with hold bands, uses catalysts only as a guard, and adds a liquidity floor.

Everything here must be registered **before** any of the new data (13F, Form 4 data sets, short interest, 10-K/10-Q sections) is joined to returns. Once a backtest has seen it, the holdout and trial count are spent.

## What this builds

1. **`protocol.yaml`**, the single current protocol (nothing has been evaluated yet, so it replaces the earlier version rather than sitting beside it), with a `DECISIONS.md` entry, adding:
   - `families`: trial budgets are counted per **corpus** (`event_backfill`, `holdings_panel`, `filing_text_panel`, `registry_panel`, `catalyst_panel`), each with its own budget. A hypothesis declares its family. Rationale: the deflated Sharpe corrects for selection across tests on the same data; tests on disjoint data do not select from each other. The event family keeps budget 64. `holdings_panel` gets 36: H9's declared grid is 4 cadences × 4 guards × 2 floors = 32 cells, plus the H10 exclusion filter on and off at the primary and the no-floor cell (4). `filing_text_panel` gets 8. `registry_panel` and `catalyst_panel` hold diagnostics only, which never count.
   - `portfolio_inference` for hypotheses with `evaluation: portfolio`: monthly net excess return over the declared benchmark, Newey-West t with lag 6 (holding up to 6 months overlaps rebalances), deflated Sharpe on monthly returns with the family's trial count, an in-sample window and a sealed holdout window given as calendar years, read once.
   - `portfolio_kill_criteria`:
     - `no_in_sample_spread`: top-minus-bottom quintile spread Newey-West t below 2.0, or long-only top quintile net excess return over the universe equal-weight below 0 in-sample → drop.
     - `holdout_check`: holdout net excess of the traded portfolio below 1% a year or Newey-West t below 1.5 → drop (report 3's threshold for the pivot, applied to every slow hypothesis).
     - `survivorship`: more than 10% of universe member-months without price coverage → result not used for promotion (matches the point-in-time universe threshold).
     - `turnover_cost`: modelled yearly cost drag above half the in-sample gross excess → re-register with a lower-turnover variant or stop.
   - `forward_check` gains a `portfolio` branch: 12 months of paper trading with no ledger gaps, a paper-versus-replay **tracking difference** within ±2% a year (the paper ledger and a backtest replay of the same months, with the same score snapshots, must agree; this tests the implementation, data timeliness and costs, not the edge), and paper net excess return not below the backtest's in-sample mean minus two standard errors. The event branch is unchanged.
   - The `portfolio` forward-check branch also records, per tier: per-trade slippage against the cost model, average holding period (a Belgian tax-risk metric, reported, not judged), and a **data gap** definition: a rebalance or close-out session whose required score snapshot, universe snapshot or closing prices were not available before the session's open.
   - `sizing.default_sizer: equal_risk` with `min_names: 15`. Kelly stays capped at the existing ceilings and is used only for strategies with at least `min_trades_for_kelly` closed trades. The 5% per-name ceiling already implies 20 or more names; `min_names` makes the floor explicit for portfolio hypotheses.
   - `shorts_enabled: false` and `options_enabled: false` as ceilings. A later change is a protocol re-registration, not an `.env` edit.
2. **Hypotheses**, each a `config/hypotheses/h<n>.yaml` with `evaluation`, `family`, `role`, `primary_cell`, `trial_cells`, and the existing fields:
   - `h9.yaml` holdings composite (family `holdings_panel`):
     - **Tradable set**: the point-in-time biotech universe with a pre-registered liquidity floor of $500M market cap and $2M 20-day median dollar volume at rebalance (applied in the score, not the universe). A `no_floor` variant uses the universe's own $50M / $500k floors, so the floor's effect is measured.
     - **Components**: specialist 13F ownership (the rule in `specs/sec-ownership-datasets.md`, never a hand list); net insider open-market buying (Form 4 code `P` only, excluding 10b5-1 trades and purchases on or within two days of an offering by the same issuer); **days to cover** (latest published short interest over average daily volume; lower ranks higher) instead of short interest over float. `score: rank_mean`. The pre-registered two-component fallback without short interest still applies, chosen only by short-interest history depth.
     - **Cadence and bands**: scores are computed monthly; trades happen **quarterly**, on the first NYSE session at least 10 calendar days after each 13F deadline (45 days after quarter end). A name is bought when it ranks in the top 15 and sold only when it drops below rank 30 (hold bands).
     - **Catalyst guard**: `skip_entry` (do not buy a name with a scheduled binary known before the next rebalance date). Held names stay through their binaries.
     - **Primary cell**: quarterly, bands 15/30, `skip_entry`, liquidity floor, equal-risk weights, benchmark XBI for abnormal return and universe equal-weight for excess.
     - **Declared trial cells**, all counted against the `holdings_panel` budget: cadence (monthly hard top 15, quarterly hard top 15, quarterly bands 15/30, semi-annual bands 15/30); catalyst guard (`none`, `skip_entry`, `exit_and_reenter`, `exit_low_score_only`); floor (`floor`, `no_floor`).
     - **Diagnostics** (reported, not promotable): H9 returns split into catalyst windows (±5 sessions around a known binary) versus other days; a holding-period sweep of 1, 3, 6 and 12 months for the top-15 entry cohort, with the average holding period for every cell.
     - In-sample 2014–2021, holdout 2022–2025.
   - `h10.yaml` risk-factor change (family `filing_text_panel`). Score = 1 − cosine similarity of Item 1A term frequencies against the same fiscal period a year earlier, known at the later filing's acceptance time. The report found the alpha sits with the changers, while the no-change long leg reverts to zero, so H10 has two registered uses:
     - **Inside biotech, an exclusion filter on H9** (`role: filter`): names in the most-changed quintile at the last 10-K/10-Q are not bought, and held names that move into it are sold at the next quarterly rebalance. It is evaluated as the change in H9's net return with and without it, and as a diagnostic, the long and short legs within biotech are reported separately. A filter is never promoted on its own.
     - **Broad US small and mid caps, a standalone test** (`role: promotable`), on its own universe file ($500M–$10B, same liquidity floor): the variant `exclude_most_changed_quintile` (hold the universe minus the changers, the low-turnover form) is the primary cell. Quarterly cadence with the same bands, held 3 to 12 months. In-sample 2015–2020, holdout 2021–2025. Registered only if the direction decision includes the broad test.
   - `h8.yaml`, negative-event veto (family `event_backfill`, `role: filter`): event types `trial_readout` with negative directionality, `complete_response_letter`, `clinical_hold` (placed), `trial_halted` — the company-level extraction enum (PR #18); entry is never taken and held names exit for 20 trading days; evaluated as the CAR[+1,+20] it avoids and as the change in the host portfolio's net return with and without the veto; never a short. A filter is not promoted on its own and counts one trial cell per horizon.
   - `h11.yaml` registry edits (family `registry_panel`, `role: diagnostic` now). It measures returns after quiet ClinicalTrials.gov edits (completion date slip of at least 180 days, enrolment cut of at least 20%, primary-outcome change, status to terminated, suspended or withdrawn, with no 8-K from the sponsor in the prior 5 days), **in both directions**, for CAR[+1,+20] and up to the next readout. It also reports whether the registry edit or the 8-K came first. The report found the direction ambiguous (outcome switches go with about 16% larger reported effects), so H11 is diagnostic. It may only be re-registered as a veto, never a long or short trigger, after the diagnostic is read. Its data comes from `specs/clinicaltrials-version-diffs.md`.
   - `h12.yaml` pre-catalyst run-up (family `catalyst_panel`, `role: diagnostic`): the XBI-adjusted CAR[-30,-1] before PDUFA dates and AdComs on a point-in-time calendar (`specs/catalyst-date-panel.md`). Reported only. It settles whether a catalyst-timed entry is worth registering at all.
3. **Volatility correction**: `docs/strategy-research.md` MDE rows use 22.5% for a 20-day window (and the matching figure per window), with a dated note. No hypothesis's thresholds change; the event kill criteria were never based on the MDE rows.
4. **`verify_hypothesis()` and `EvaluationProtocol.run()`** (from PR #15) learn `evaluation: portfolio` and `family`, and refuse a portfolio hypothesis that names an event-only field and vice versa.

## Out of scope

- Computing any score, fetching any data, running any backtest (the score and backtest specs).
- Changing the event-family thresholds PR #15 locked, except the forward-check branch split.
- Any options or short hypothesis.
- Promoting H11 or H12 (diagnostics only).

## Constraints

- Invariant 15 and the rule that matters most: the registration tests below assert what the protocol says; if a test can only pass by contradicting `docs/requirements.md`, stop and flag.
- One version per file: every hypothesis and the protocol are version 1, with one line each in `registry.jsonl`. Nothing has been evaluated, so earlier drafts are not kept. From the first evaluation on, a change is a new registry line and earlier lines are never edited.
- No backtest on the new corpora may run before this lands. `EvaluationProtocol.run()` refuses a hypothesis whose family has no registered budget.
- No plan-step references in names (root `CLAUDE.md`).

## Required tests

In `services/backtesting/tests/unit/test_preregistered_protocol.py` (extends PR #15's file):
- `test_registry_holds_one_registration_per_file`
- `test_trial_budget_is_counted_per_family_not_across_families` — 40 cells in `event_backfill` and 10 in `holdings_panel` leave both under budget
- `test_portfolio_hypothesis_without_holdout_years_is_refused`
- `test_portfolio_hypothesis_naming_known_at_delay_cells_is_refused` — event-only field on a portfolio hypothesis
- `test_event_hypothesis_naming_rebalance_frequency_is_refused`
- `test_forward_check_branch_follows_the_hypothesis_evaluation_kind`
- `test_portfolio_forward_check_fails_on_tracking_difference_above_two_percent_a_year`
- `test_portfolio_forward_check_fails_on_any_ledger_gap`
- `test_shorts_and_options_are_disabled_by_protocol_ceiling`
- `test_equal_risk_is_the_default_sizer_with_fifteen_name_minimum`
- `test_h9_specialist_component_references_the_rule_not_a_fixed_list`
- `test_h9_two_component_variant_is_preregistered_with_its_selection_rule`
- `test_h8_v3_is_a_filter_and_cannot_be_promoted`
- `test_h8_v3_event_types_are_members_of_the_extraction_event_type_enum`
- `test_hypothesis_family_without_budget_is_refused_by_evaluation`
- `test_h9_declared_trial_cells_are_counted_against_the_holdings_budget`
- `test_h9_quarterly_trade_date_is_first_session_ten_days_after_13f_deadline`
- `test_h10_in_biotech_is_a_filter_and_cannot_be_promoted`
- `test_diagnostic_hypotheses_do_not_count_against_any_budget`
- `test_portfolio_forward_check_defines_a_data_gap_as_inputs_missing_before_open`

## Definition of done

```bash
cd services/backtesting && uv run pytest tests/unit/test_preregistered_protocol.py -q --strict-markers
```

Expected: 33 passed (13 existing, 20 new).

Then: `DECISIONS.md` CHOICE entry with the protocol changes, the registry hashes, and confirmation that no backtest has joined the new corpora to returns (`config/hypotheses/trials/` has no entry for the new families).

## Notes

- The ±2% tracking tolerance is a proposal. It is wide enough for fill-model noise and narrow enough to catch a stale data feed or a cost model that is off by a whole spread. The user owns it.
- Why the forward check changes for portfolios but not events: a slow portfolio's statistical evidence comes from its long backtest and holdout (13 years of 13F data for H9, about 11 for H10). Paper trading's job is then to show the live system produces what the backtest says it would, at each capital tier, which 12 months can show.

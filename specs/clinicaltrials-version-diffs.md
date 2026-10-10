# ClinicalTrials.gov Version Diffs

**Status:** blocked
**Blocked by:**
1. Met in code: `specs/point-in-time-universe.md` (PR #21, #22) — lead sponsors are matched to universe companies. Runs on the stack need its first build.
2. Met: `specs/done/slow-signal-preregistration.md` — H11 registered as a diagnostic before any registry edit is joined to returns.

**Branch:** `feature/clinicaltrials-version-diffs`

---

## Context

The user expects design changes on a trial (a new primary endpoint, a cut in enrolment, a slipped completion date) to be priced only when the trial reads out, not when the registry is edited. The 2026-10-08 research (`/mnt/project-files/research/edge-result-4.md`) found that nobody has published a study of stock reactions to ClinicalTrials.gov edits, so the view is untested. The direction is also ambiguous: trials that switch a primary outcome report effects about 16% larger (JAMA Network Open 2019), so a switch can come before a *positive* topline. Auspex has to measure this itself, and for a long-only book the use is a veto, not a trade.

The scraper's ClinicalTrials.gov connector stores the current record when it sees it. It keeps no history, and a backtest needs history from 2014. Two candidate history sources, neither verified from the scoping sessions:
- **ClinicalTrials.gov record history**: each study page shows its posted versions with dates. Whether the v2 API exposes them, and on what terms, is unknown.
- **AACT** (Duke CTTI), a public PostgreSQL copy of ClinicalTrials.gov with monthly static archives. Diffing consecutive monthly archives gives changes with up to a month's resolution, dated by `last_update_posted`.

Verify both at the start of the session and record which one is used, and from what date, in `DECISIONS.md`. Like the other reference panels, this is a backtesting-side panel (prices, ownership, filings), not a change to the scraper connector.

## What this builds

In `services/backtesting/src/auspex_backtesting/registry/`:

1. **`TrialVersionStore`** — for trials whose lead sponsor matches a universe member (by normalised name; unmatched sponsors counted), one row per posted version: `nct_id, version_posted_at` (= `last_update_posted`, the known-at date), `overall_status, primary_completion_date, enrollment, enrollment_type, primary_outcomes` (normalised text), and the source (`history` or `aact:<archive month>`). Stored as Parquet in MinIO `auspex-prices/registry/{yyyy}q{q}.parquet`, written once per quarter.
2. **`RegistryEditDetector`** — compares each version with the previous one and emits edits of these types:
   - `completion_slip`: primary completion date moved later by at least 180 days.
   - `enrollment_cut`: target enrolment cut by at least 20%.
   - `primary_outcome_change`: primary-outcome text changed beyond whitespace and punctuation.
   - `status_stop`: status changed to terminated, suspended or withdrawn.
   Each edit carries the sponsor CIK and the edit's known-at date.
3. **Quiet flag** — an edit is `quiet` when the sponsor filed no 8-K in the 5 sessions before its known-at date (from the EDGAR quarterly form index). The panel also records the first 8-K after the edit, so that whether the registry or the 8-K came first can be reported.
4. **`scripts/build_registry_panel.py`** — builds the panel from 2014 onward, then prints edits per year by type, the quiet share, the unmatched-sponsor share, and the version resolution of the source.

## Out of scope

- Any trading use: H11 is a diagnostic. A veto may be registered only after the diagnostic is read (slow-signal pre-registration).
- Results postings and adverse-event tables.
- Changes to the scraper's ClinicalTrials.gov connector.

## Constraints

- Point-in-time: an edit is known at its version's `last_update_posted`, never at the date it says the change took effect. `first_submitted_date` is private (known trap). With monthly archives, an edit is never dated earlier than it was posted.
- Invariant 6: source URLs and any database credentials in `.env`. Invariant 9: UTC.
- Requirements §8 pattern: each archive or history page is fetched once.
- `pytest-socket` in unit tests, with fixture versions.

## Required tests

In `services/backtesting/tests/unit/test_registry_diffs.py`:
- `test_completion_slip_of_180_days_or_more_is_an_edit_and_less_is_not`
- `test_enrollment_cut_of_20_percent_or_more_is_an_edit`
- `test_primary_outcome_whitespace_change_is_not_an_edit`
- `test_primary_outcome_text_change_is_an_edit`
- `test_status_change_to_terminated_is_a_status_stop`
- `test_edit_is_known_at_last_update_posted_not_effective_date`
- `test_edit_with_sponsor_8k_in_prior_five_sessions_is_not_quiet`
- `test_first_8k_after_edit_is_recorded_for_ordering`
- `test_unmatched_sponsor_is_counted_not_dropped_silently`
- `test_quarter_already_stored_is_not_refetched`

## Definition of done

```bash
cd services/backtesting && uv run pytest tests/unit/test_registry_diffs.py -q --strict-markers
```

Expected: 10 passed.

Then: the panel built on the stack machine. Record the source, its start date and resolution, edit counts and the quiet share in `DECISIONS.md`. Run the H11 diagnostic only after that entry exists.

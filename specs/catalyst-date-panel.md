# Catalyst Date Panel

**Status:** blocked
**Blocked by:** the first panel build on the stack machine (Definition of done, second block; `specs/first-run-on-stack-machine.md` step 3a). All code and all 10 required tests are in (`auspex_backtesting.catalysts`, `scripts/build_catalyst_panel.py`); neither SEC nor the Federal Register is reachable from cloud sessions (`DECISIONS.md` 2026-10-09 PENDING).
**Was blocked by:** none. `specs/point-in-time-universe.md` is done in code (PR #21, #22) and supplies the CIKs, names and ticker history that catalysts are matched to; the stack backfill needs its first build. EDGAR press-release content (PR #16, merged) supplies the Exhibit 99.1 selection rules this spec reuses for its own fetches.

**Branch:** `feature/catalyst-date-panel`

---

## Context

Every slow strategy now uses known binary events, not as a trigger but as a guard. Don't buy a name with a binary due before the next trade date, or measure what exiting around it costs (`specs/cross-sectional-portfolio-backtest.md`, `CatalystGuard`). Two diagnostics also need these dates: H9's return split into catalyst windows versus other days, and the H12 pre-catalyst run-up (2026-10-08 research, `/mnt/project-files/research/edge-result-4.md`). A backtest can only use dates as they were known at the time. Today's aggregator calendars drop failed companies and store only the final date (inferred in that report), so they would leak.

`specs/catalyst-calendar.md` builds the live calendar through LLM extraction into core-hub. That needs the extraction schema change and, for history, the LLM backfill. The research asks for catalyst dates **before** the LLM backfill. This spec builds a backtest panel without the LLM, from two sources whose wording is regular enough for deterministic rules:
- **PDUFA dates** in 8-K press releases (Exhibit 99.1), for example "PDUFA target action date of March 15, 2027". Revisions such as a three-month extension appear in later releases.
- **FDA advisory committee meetings** in Federal Register notices, published at least 15 days ahead (21 CFR 14.20). The free JSON API is `https://www.federalregister.gov/api/v1/documents.json` (no key).

Neither source was reachable from the scoping sessions (proxy-blocked). Verify both at the start of the session and record the results in `DECISIONS.md`.

## What this builds

In `services/backtesting/src/auspex_backtesting/catalysts/`:

1. **`PressReleaseCatalystExtractor`** — for each universe CIK, fetches 8-K filings with Item 7.01 or 8.01 and an Exhibit 99.1 from the EDGAR quarterly form index, using the same exhibit selection rules as the scraper's EDGAR connector. It applies phrase rules for PDUFA dates (`PDUFA`, `target action date`, `goal date`), each with its date and a precision (`day`, `month`, `quarter`, `half`; "second half of 2027" never becomes a day). Each hit is stored with the sentence it came from. Known at the 8-K's acceptance time.
2. **`AdvisoryCommitteeNotices`** — FDA meeting notices from the Federal Register API, with the meeting date and committee from the notice. The sponsor and product from the notice text are matched to universe names. Unmatched notices are kept and counted, never forced onto a company. Known at the publication date.
3. **`CatalystPanel`** — Parquet in MinIO `auspex-prices/catalysts/{source}/{yyyy}q{q}.parquet`, append-only. A revision is a new row. `as_of(cik, date)` returns the effective upcoming catalysts: for each `(cik, catalyst_type, application or product)`, the latest row known on or before `date`. `binaries_between(cik, start, end, as_of)` serves `CatalystGuard`.
4. **`scripts/build_catalyst_panel.py`** — backfills from 2014. It prints coverage: catalysts per year, the share of universe members with any catalyst, unmatched AdCom notices, and phrase-rule hits by precision.

## Out of scope

- Readout guidance ("topline data expected in Q2"). It is too varied for phrase rules and is left to the LLM-based `specs/catalyst-calendar.md`.
- Live serving through core-hub (`specs/catalyst-calendar.md`).
- Any LLM call.
- Outcomes (approved, CRL, vote results).

## Constraints

- Point-in-time: a catalyst is invisible before its disclosing document's acceptance or publication time, and a revision never changes an earlier `as_of` read.
- SEC traps: a descriptive `User-Agent`, a shared limiter at ≤ 5 req/s and no retry during a block. Federal Register at 1 req/s.
- Invariant 6: URLs in config. Invariant 9: UTC.
- Requirements §8 pattern: each document is fetched once.
- `pytest-socket` in unit tests, with fixture press releases and notices.

## Required tests

In `services/backtesting/tests/unit/test_catalyst_panel.py`:
- `test_pdufa_date_with_day_precision_is_extracted_from_press_release_fixture`
- `test_half_year_pdufa_guidance_keeps_half_precision`
- `test_catalyst_is_invisible_before_its_8k_acceptance_time`
- `test_extension_appends_a_row_and_later_as_of_returns_the_new_date`
- `test_earlier_as_of_still_returns_the_original_date_after_extension`
- `test_adcom_notice_known_at_publication_date_not_meeting_date`
- `test_unmatched_adcom_notice_is_kept_and_counted`
- `test_binaries_between_returns_only_catalysts_known_as_of_the_trade_date`
- `test_press_release_without_catalyst_phrase_yields_nothing`
- `test_document_already_fetched_is_not_refetched`

## Definition of done

```bash
cd services/backtesting && uv run pytest tests/unit/test_catalyst_panel.py -q --strict-markers
```

Expected: 10 passed.

Then: the panel built for 2014 onward on the stack machine. Record coverage and a hand check of 30 random hits (date and company right) in `DECISIONS.md`. If precision is below 0.9, tighten the phrase rules once. If it is still below, record it and run the guard with that precision stated.

## Notes

- Coverage will be partial: not every company names its PDUFA date in an 8-K. The guard reports members with no known catalyst data, so a thin calendar shows up as a number, not as a falsely clean book.

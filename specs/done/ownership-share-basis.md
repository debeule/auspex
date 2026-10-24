# Ownership share basis

> Archived. Not authoritative: current behaviour is in docs/ (see docs/README.md).

**Status:** done
**Blocked by:** none (price-finality-and-split-availability is done)
**Branch:** `feature/ownership-share-basis`

---

## Context

`services/backtesting/src/auspex_backtesting/ownership/panels.py` (`HoldingsPanel.specialist_ownership`) sums the shares specialist filers report for an issuer in their latest 13F accepted before `as_of` and divides by `ShareCountPanel.shares_outstanding` (`ownership/reference.py`), the latest cover-page count filed before `as_of`. The 13F numerator is the raw `SSHPRNAMT` as of each report's `period_of_report` (`ownership/form13f.py`); the denominator is the raw count as of its own `end` date. Neither is restated through stock splits, so the two can be on different share bases.

Split histories exist per ticker in `auspex-prices` (`prices/splits.py`, `SplitStore`), and `universe/market_cap.py` already restates a share count through the splits after its `end` date. There is no ticker history: the universe resolves **one** ticker per CIK (`ListingHistory.ticker`, with `ticker_source` `current`, `filing` or `unresolved`) and uses it for every listing span, and `ListingSpan` (`universe/model.py`) holds only entry and exit dates. `UniverseBuilder._load_prices` already refuses a ticker whose bars run on long after the CIK's exit (the symbol was reused by another issuer) and records `price_coverage` (`complete`, `partial`, `none`) on each `UniverseMember`.

Found by the consolidated audit of 2026-10-10 (finding C1; the audit file is in the project's `audit/` folder) and checked against `develop` at `d615504`. A fund holds 1M of 10M shares at quarter end; a 1:10 reverse split follows, and the next cover-page count (1M) is filed before the fund's next 13F is public. The ratio reads 1M / 1M = 100% instead of 10%. A forward split shrinks it the same way. H9 ranks on this ratio, so a split moves an issuer's rank with no change in ownership. The audit reproduced the 100% with the exact method.

No ownership panel has been built yet (first-run step 3b), so nothing stored needs to be rebuilt.

## What this builds

- **One share basis per read.** `specialist_ownership(cik, as_of)` restates each specialist report's shares from its `period_of_report`, and the share count from its `end`, to the share basis on `as_of`, by the product of split ratios dated after each one's date and on or before `as_of`, and then divides. Each filer's report is restated from its own period, so filers on different quarters are aligned.
- **Splits by CIK, only where the ticker is trustworthy over the interval.** A `SplitFactors` protocol, `factor(cik, after: date, through: date) -> float | None`. It takes the CIK's ticker from the universe snapshots of every month in `(after, through]` and uses that ticker's split history only when all of these hold; otherwise it returns `None` with a reason:
  - the CIK is a member in each of those months with the same ticker, `ticker_source` `current`, and `price_coverage` `complete` (a continuous price series under that symbol across the interval is the evidence that the provider tracks this issuer under it, through any earlier symbol change). A `filing` ticker (an old symbol read from filings), an `unresolved` one, a member missing from a month, or partial or no coverage gives `ticker_history_uncertain`; the reuse case is already `price_coverage` `none`.
  - the split history is not `unavailable` and covers `through` (its `covered_through`, from `specs/price-finality-and-split-availability.md`); otherwise `split_history_unavailable`.
  There is no ticker-history table to build: an interval this rule cannot vouch for is missing, not guessed.
- **One share class per read.** When a read's specialist holdings for the CIK span more than one CUSIP, the numerator and the cover-page total may count different classes, so the read is missing with reason `multiple_share_classes`.
- **Unknown basis is missing, not a ratio.** When any factor the read needs is `None`, `specialist_ownership` returns `None`, and the reason (`no_share_count`, `ticker_history_uncertain`, `split_history_unavailable`, `multiple_share_classes`) is available from `specialist_ownership_reason(cik, as_of)` so the score and coverage reports can count it. An issuer no specialist holds still reads `0.0`.

## Out of scope

- Normalizing several share classes to one basis (a read spanning them is missing instead).
- A historical ticker table (symbol changes are trusted only where the rule above vouches for them).
- Corporate actions other than splits.
- Any change to the specialist rule, its registered thresholds, H9's components or the composite score.
- Insider transactions (`InsiderPanel`), which are valued in dollars, not shares.

## Constraints

- Point in time: only splits dated on or before `as_of` are applied; a split history fetched later is a list of past events and does not leak values that were unknown then.
- Unknown stays unknown: no code path turns a missing split history or ticker into a factor of 1.
- The specialist thresholds stay read from the registered `config/hypotheses/h9.yaml`.

## Required tests

Unit (`services/backtesting/tests/unit/test_ownership_parsing.py`):
- `test_specialist_ownership_is_unchanged_by_a_reverse_split_before_the_share_count` — 1M of 10M held at quarter end, 1:10 reverse split, count of 1M filed before `as_of`: 0.10
- `test_specialist_ownership_is_unchanged_by_a_forward_split_before_the_share_count` — 2:1 forward split: 0.10
- `test_specialist_ownership_without_splits_is_the_raw_ratio` — control
- `test_filers_on_different_report_periods_are_each_restated_from_their_own_period` — two specialists, one reporting before and one after the split: their shares add on one basis
- `test_split_after_as_of_is_not_applied`
- `test_unavailable_split_history_makes_specialist_ownership_missing` — returns `None`, reason `split_history_unavailable`
- `test_ticker_change_inside_the_interval_with_continuous_prices_is_restated` — the CIK's current ticker, `complete` coverage across a symbol change and a 1:10 reverse split: 0.10
- `test_old_filing_ticker_makes_specialist_ownership_missing` — `ticker_source` `filing`: `None`, reason `ticker_history_uncertain`
- `test_reused_ticker_makes_specialist_ownership_missing` — the member's `price_coverage` is `none` because the symbol trades long after the CIK's exit: reason `ticker_history_uncertain`
- `test_member_absent_from_a_month_in_the_interval_is_missing` — reason `ticker_history_uncertain`
- `test_split_history_covering_less_than_as_of_is_missing` — `covered_through` before `as_of`: reason `split_history_unavailable`
- `test_holdings_under_two_share_classes_are_missing` — specialists hold the CIK under two CUSIPs: reason `multiple_share_classes`
- `test_issuer_held_by_no_specialist_reads_zero` — control: share count known, no holder, `0.0`

Added while implementing, for mutants the list above let through:
- `test_share_count_dated_before_the_split_is_restated` — the count's own restatement (every listed case had the count after the split)
- `test_ticker_differing_between_months_is_missing` — two `current` tickers inside one interval: reason `ticker_history_uncertain`

## Definition of done

```bash
cd services/backtesting && uv run pytest tests/unit -q
cd services/backtesting && uv run ruff check . && uv run mypy src
```

Expected: the 15 tests above pass with the rest of the unit suite; no failures.

## Notes

- **Restate to `as_of`, not to today:** every read uses the basis of its own date, so a split after `as_of` cannot change a historical read, and the result does not depend on when the panel was built.
- The alternative the audit offered (compute each filer's ratio at its report date against a count from the same date, then carry it forward) was not chosen: cover-page counts and report periods rarely share a date, so it needs the same restatement and adds staleness.

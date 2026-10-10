# SEC Ownership Datasets (13F Holdings and Insider Transactions)

**Status:** ready
**Blocked by:** none. `specs/point-in-time-universe.md` is done in code (PR #21, #22) and supplies the CIK and ticker set the panels are filtered to and `MarketCapEstimator` for scaling; the stack backfill needs its first build. Direction decided 2026-10-08 (both).

**Branch:** `feature/sec-ownership-datasets`

---

## Context

The holdings composite (H9, `specs/done/slow-signal-preregistration.md`) needs two point-in-time panels from SEC data:
- **Institutional holdings**: who holds each biotech stock, from Form 13F. A quarter's holdings are public only when the 13F is filed, up to 45 days after quarter end, and amendments arrive later.
- **Insider transactions**: open-market purchases and sales by officers, directors and 10% owners, from Forms 3, 4 and 5.

Both exist as SEC bulk data sets (quarterly ZIPs of tab-separated tables), which avoids tens of thousands of per-filing requests against the SEC's 10 req/s limit (known trap). Neither URL, layout nor history depth could be checked from the scoping session (proxy-blocked); the SEC's "Form 13F Data Sets" and "Insider Transactions Data Sets" pages are the expected sources, starting around 2013 and 2006. Verify at the start of the session and record start dates in `DECISIONS.md`.

These are time-series panels joined to a monthly score, not documents with something to extract. They follow the price and short-interest snapshot pattern in `services/backtesting` (MinIO bucket `auspex-prices`), not the ingestion pipeline. `DECISIONS.md` 2026-10-07 "ownership and insider data are snapshots, not connectors" records why; it supersedes `specs/hold/insider-buying-connector.md` for this use.

The research report recommended a "fixed, dated list of healthcare-dedicated 13F filers". A list written in 2026 would pick funds known **today** to be good biotech investors, which is look-ahead. This spec derives specialists by rule from the 13F data itself, as of each quarter.

## What this builds

In `services/backtesting/src/auspex_backtesting/ownership/`:

1. **`Form13FDatasetStore`** — downloads each quarterly 13F data set once, keeps holdings rows whose issuer maps (CUSIP → CIK via the data set's issuer name and the universe's ticker history; unmapped CUSIPs counted) to the universe, and writes `auspex-prices/ownership/13f/{yyyy}q{q}.parquet` with `filer_cik, issuer_cik, shares, value_usd, period_of_report, filing_accepted_at, is_amendment`. Written once per quarter, never rewritten; a later amendment appears in a later quarter's data set and is stored there.
2. **`SpecialistClassifier`** — a 13F filer is a healthcare specialist as of date D if, across its 13Fs accepted before D in the trailing four quarters, at least `SPECIALIST_HEALTHCARE_SHARE` (default 0.5) of reported value is in issuers with SIC 2834, 2836, 8731 or 3841, and its total reported value is at least `SPECIALIST_MIN_AUM_USD` (default $100M). Both thresholds from `.env`, recorded in the hypothesis. The classification table per quarter is stored next to the holdings.
3. **`InsiderTransactionStore`** — quarterly insider data sets → `auspex-prices/ownership/insider/{yyyy}q{q}.parquet` with `issuer_cik, owner_cik, role, transaction_code, shares, price, transaction_date, filing_accepted_at, is_10b5_1`. For the current quarter, before its data set is published, the same rows are filled from the daily form index and each Form 4's XML; when the quarterly set arrives it replaces nothing (the daily rows stay in a separate `daily/` prefix and the panel reader prefers the quarterly set, reporting any disagreement).
4. **Point-in-time readers** — `specialist_ownership(issuer_cik, as_of)`: shares held by specialists in the latest 13F per filer **accepted before `as_of`**, over shares outstanding as of `as_of`; `net_insider_buying(issuer_cik, as_of, days=90)`: open-market purchases (code `P`) minus sales (code `S`) excluding 10b5-1 plan trades, by `filing_accepted_at` in the window, in USD over market cap. A purchase whose transaction date is within two days of a `424B4` or `424B5` filed by the same issuer is flagged `offering_participation` and excluded: insiders buying into their own financing is not an information signal. Offering dates come from the EDGAR quarterly form index, stored once per quarter alongside the insider panel.
5. **`scripts/fetch_ownership.py`** — backfills both panels for the configured window and prints coverage: quarters stored, universe issuers with any 13F holder, unmapped CUSIP share, insider filings per quarter.

## Out of scope

- The composite score itself (`specs/holdings-composite-score.md`).
- Insider-copying event trades (dropped by the research: the reaction ends within two to three sessions).
- Form 13D/13G, Form 144, N-PORT.
- Live alerting on Form 4s.

## Constraints

- Point-in-time: every join uses `filing_accepted_at`, never `period_of_report` or `transaction_date` (same trap class as patent `filed_date`).
- SEC traps: descriptive `User-Agent` from `.env`, shared limiter at ≤ 5 req/s, no retry during a block.
- Requirements §8 pattern: each quarter is fetched once and read from MinIO thereafter.
- Invariant 9: UTC acceptance times.
- Invariant 6: data-set URLs in config, not code.
- `pytest-socket` in unit tests; fixtures cut from real data-set files once verified.

## Required tests

In `services/backtesting/tests/unit/test_ownership_datasets.py`:
- `test_13f_holding_is_invisible_before_its_filing_acceptance_time` — period end 31 March, accepted 14 May; `as_of` 13 May uses the prior quarter
- `test_13f_amendment_accepted_later_does_not_change_earlier_as_of_reads`
- `test_specialist_classification_uses_only_filings_accepted_before_as_of`
- `test_filer_below_healthcare_share_is_not_a_specialist`
- `test_filer_below_minimum_aum_is_not_a_specialist`
- `test_specialist_ownership_divides_by_shares_outstanding_as_of_date`
- `test_unmapped_cusip_is_counted_not_dropped_silently`
- `test_insider_purchase_counts_only_code_p_and_sale_only_code_s`
- `test_10b5_1_plan_trades_are_excluded_from_net_buying`
- `test_purchase_within_two_days_of_issuer_offering_is_flagged_and_excluded`
- `test_insider_window_is_by_filing_acceptance_not_transaction_date`
- `test_quarter_already_stored_is_not_refetched`
- `test_daily_form4_rows_fill_the_quarter_before_its_dataset_exists`
- `test_quarterly_dataset_is_preferred_and_disagreement_is_reported`
- `test_requests_carry_the_configured_user_agent`

## Definition of done

```bash
cd services/backtesting && uv run pytest tests/unit/test_ownership_datasets.py -q --strict-markers
```

Expected: 15 passed.

Then: `scripts/fetch_ownership.py` run on the stack machine for 2013 onward; first available quarter of each data set, issuer coverage and unmapped-CUSIP share recorded in `DECISIONS.md`. `.env.example` gains the two specialist thresholds; `services/backtesting/README.md` lists the panels.

## Notes

- Effort: if the session runs long, split insider transactions (items 3 and the insider half of 4) into its own spec.
- CUSIP to CIK is the weakest link: 13F reports CUSIPs, the universe uses CIKs. The data set's issuer name plus the universe's names and ticker history resolve most; the unmapped share is reported, and over 10% of universe market value unmapped in any quarter is flagged in `DECISIONS.md` before H9 runs.

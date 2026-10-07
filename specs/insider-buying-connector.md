# Insider Buying Connector (SEC Form 4)

**Status:** blocked
**Blocked by:**
1. Company-level event extraction (in progress, first wave) — event type and company identifier fields on `ResearchSignalEvent`.
2. `specs/structured-source-extraction.md` — the deterministic mapper path and the issuer-scope pre-filter.
3. Soft: `specs/point-in-time-universe.md` for the issuer list. Until it lands, the issuer scope is a configured CIK list (the watchlist companies).

**Branch:** `feature/insider-buying-connector`

---

## Context

Open-market purchases by officers and directors are a company-level, free and orthogonal signal (2026-10-07 edge feasibility audit, row 9; the audit marks its biotech-specific value as inferred, not verified). They are reported on SEC Form 4 within two business days of the trade, as XML (`ownershipDocument`).

What exists: `connectors/sec_edgar.py` (EFTS search plus `data.sec.gov/submissions` for 8-Ks), `connectors/rate_limited_client.py`, `SEC_USER_AGENT` in `.env`. SEC traps from `CLAUDE.md` apply: 10 req/s aggregate across `*.sec.gov` (configure 5), mandatory descriptive `User-Agent`, retrying during a block extends it.

Discovery without per-company polling: EDGAR's daily form index `https://www.sec.gov/Archives/edgar/daily-index/{yyyy}/QTR{q}/form.{yyyymmdd}.idx` lists every filing of the day by form type (one request per day; quarterly `full-index` for the backfill). Verify the URL, the index layout, and whether a Form 4 appears under the issuer, the reporting owner, or both at the start of the session; record the result in `DECISIONS.md`.

## What this builds

- `connectors/sec_form4.py` — `SecForm4Connector`, `source_type = "sec_form4"`. `fetch_since(cursor)` reads the daily indexes from the cursor date, keeps form `4` and `4/A` rows, fetches each filing's XML, and yields one `RawDocument` per filing. `published_date` = the filing's `acceptanceDateTime` (from the filing header), never the transaction date. `canonical_id = "edgar:<accession>"`.
- `extraction/mappers/insider_transactions.py` — `InsiderTransactionsMapper`: a filing is a signal only if it has at least one non-derivative transaction with code `P` (open-market purchase). Event fields: event type `insider_purchase`, issuer CIK and ticker as filed, reporting owner role (director, officer and title, 10% owner), total shares and USD value of `P` transactions, whether the filing marks the trades as made under a Rule 10b5-1 plan. Sales, grants, option exercises and derivative transactions → `not_signal` (counted).
- `sources.yaml` entry: `extraction: structured`, `structured_mapper: insider_transactions`, `prefilter: issuer_scope`, `rate_limit_rps` sharing the SEC host bucket.
- A `4/A` amendment publishes under the original filing's `event_id` (requirements §7.1 amendment rule) when it amends a Form 4 already ingested.

## Out of scope

- Clustering of buys across insiders, and any hypothesis using them (registered separately through the hypothesis registry).
- Form 3, Form 5 and Form 144.
- Historical backfill runs (the historical-backfill spec drives them; this connector must simply support date-ranged cursors).

## Constraints

- Invariants 1, 3, 4, 6, 9, 13. `fetch_since()` fetches and maps only.
- Known-at date is `acceptanceDateTime`, UTC. `transactionDate` is retained as a source-specific date and never used for alignment (same trap class as patent `filed_date`).
- All SEC requests through the shared rate limiter.
- Unit tests use saved fixtures (respx); `pytest-socket` blocks the network.

## Required tests

In `services/ingestion-scraper/tests/unit/test_sec_form4.py`:
- `test_daily_index_rows_other_than_form_4_are_skipped`
- `test_form4_published_date_is_acceptance_time_not_transaction_date`
- `test_open_market_purchase_maps_to_insider_purchase_event`
- `test_sale_only_filing_is_not_a_signal`
- `test_option_exercise_and_grant_are_not_signals`
- `test_officer_title_and_ten_percent_owner_flags_are_carried`
- `test_10b5_1_plan_purchase_is_flagged`
- `test_amendment_publishes_under_original_event_id`
- `test_out_of_scope_issuer_is_prefiltered_out`
- `test_requests_carry_the_configured_user_agent`
- `test_requests_go_through_the_shared_sec_rate_limiter`
- `test_backfill_window_reads_quarterly_full_index`

## Definition of done

```bash
cd services/ingestion-scraper && uv run pytest tests/unit/test_sec_form4.py -q --strict-markers && uv run pytest tests/unit -q && uv run ruff check . && uv run mypy src
```

Expected: 12 passed; full unit suite green.

Then: one live `fetch_since` over a recent week on the stack machine; filing count, purchase count and any surprises recorded in `DECISIONS.md`. `services/ingestion-scraper/README.md` connectors table and known API constraints updated.

# Equity Offering Connector (SEC S-3 and 424B)

**Status:** hold
**Hold reason (2026-10-07 edge research):** no biotech-specific study of offering returns was found, and trading them needs shorts, which the protocol disables. Comes off hold if offerings are pre-registered as a veto on long holdings. `DECISIONS.md` 2026-10-07 "ownership and insider data are snapshots, not connectors".
**Blocked by:**
1. Met: company-level event extraction (`specs/done/company-level-extraction.md`) — event type and company identifier fields on `ResearchSignalEvent`.
2. `specs/hold/structured-source-extraction.md` — the deterministic mapper path and the issuer-scope pre-filter.
3. Soft: `specs/point-in-time-universe.md` for the issuer list. Until it lands, the issuer scope is a configured CIK list.

**Branch:** `feature/equity-offering-connector`

---

## Context

Cash-burning biotechs raise equity often, and offerings are a predictable negative for the stock (2026-10-07 edge feasibility audit, row 9, marked inferred). They are also useful as a risk filter: a long position into an imminent raise is a known way to lose money. Offerings leave a structured trail on EDGAR, keyed by form type:

| Form | Meaning | Event type |
|---|---|---|
| `S-3`, `S-3ASR` | Shelf registration: capacity to raise later | `shelf_registered` |
| `424B5` | Prospectus supplement under a shelf: a priced follow-on, registered direct, or an at-the-market (ATM) programme | `offering_priced` or `atm_established` |
| `424B4` | Final prospectus outside a shelf (IPO or non-shelf follow-on) | `offering_priced` |

What exists: `connectors/sec_edgar.py`, `connectors/rate_limited_client.py`, `SEC_USER_AGENT`. SEC traps from `CLAUDE.md` apply (10 req/s aggregate, mandatory `User-Agent`, blocks extend on retry). Discovery uses EDGAR's daily form index (`https://www.sec.gov/Archives/edgar/daily-index/{yyyy}/QTR{q}/form.{yyyymmdd}.idx`, quarterly `full-index` for the backfill), verified at the start of the session and recorded in `DECISIONS.md`.

## What this builds

- `connectors/sec_offerings.py` — `SecOfferingsConnector`, `source_type = "sec_offerings"`. Reads the daily indexes from the cursor date, keeps the forms above, fetches the primary document and the filing-fee exhibit when present, yields one `RawDocument` per filing. `published_date` = `acceptanceDateTime`. `canonical_id = "edgar:<accession>"`.
- `extraction/mappers/equity_offerings.py` — `EquityOfferingsMapper`: event type from the form type, `atm_established` when the 424B5 text names an "at-the-market" sales agreement (a deterministic phrase match, tested on fixtures), and offering size in USD from the filing-fee exhibit when it is machine-readable; size is nullable, never guessed.
- `sources.yaml` entry: `extraction: structured`, `structured_mapper: equity_offerings`, `prefilter: issuer_scope`.

## Out of scope

- LLM parsing of offering terms (price, discount, warrants). If size and price turn out to matter, that is a later extraction change.
- 8-K Item 1.01 underwriting agreements (the EDGAR press-release content work covers 8-K text).
- Debt and convertible offerings.
- Hypotheses on offerings (registered separately).

## Constraints

- Invariants 1, 3, 4, 6, 9, 13.
- Known-at date is `acceptanceDateTime`. Many offerings are announced by press release the evening before the 424B5 is filed; the 8-K/press-release path captures that earlier time. This connector must not back-date to it.
- All SEC requests through the shared rate limiter. Unit tests on saved fixtures.

## Required tests

In `services/ingestion-scraper/tests/unit/test_sec_offerings.py`:
- `test_s3_maps_to_shelf_registered`
- `test_424b5_priced_offering_maps_to_offering_priced`
- `test_424b5_naming_an_at_the_market_agreement_maps_to_atm_established`
- `test_424b4_maps_to_offering_priced`
- `test_offering_published_date_is_acceptance_time`
- `test_offering_size_is_read_from_fee_exhibit_and_null_when_absent`
- `test_other_form_types_are_skipped`
- `test_out_of_scope_issuer_is_prefiltered_out`
- `test_requests_go_through_the_shared_sec_rate_limiter`
- `test_s3asr_maps_to_shelf_registered`

## Definition of done

```bash
cd services/ingestion-scraper && uv run pytest tests/unit/test_sec_offerings.py -q --strict-markers && uv run pytest tests/unit -q && uv run ruff check . && uv run mypy src
```

Expected: 10 passed; full unit suite green.

Then: one live `fetch_since` over a recent month; counts per event type and fee-exhibit coverage recorded in `DECISIONS.md`. `services/ingestion-scraper/README.md` connectors table and known API constraints updated.

## Notes

- Whether filing-fee exhibits are reliably machine-readable for 424B filings in the backfill window is unverified (the SEC phased in structured fee exhibits from 2022). The fixture-based test fixes the parsing; the live check records the coverage.

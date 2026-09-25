# EDGAR Content Fix

**Status:** done
**Branch:** `feature/edgar-content-fix`

---

## Context

`SecEdgarConnector` fetches 8-K filings via the EDGAR full-text search API (`https://efts.sec.gov/LATEST/search-index`). The current `raw_content` field is populated from search result metadata: Accession Number, Entity Name, Form Type, Filed Date, Period of Report, Items. No document prose.

Phase 2 extraction: 8 of 13 false negatives were EDGAR 8-Ks with metadata-only `raw_content`. The LLM cannot extract a signal from a form header. EDGAR is included in the historical backfill; without this fix, the backfill will produce no corroborations from EDGAR documents.

## What this builds

An extension to `SecEdgarConnector.fetch_since()` that fetches primary document text for each search result:

1. Extract the CIK from the accession number: the first 10 digits, strip leading zeros (`0001234567-23-456789` → CIK `1234567`).
2. Fetch `https://data.sec.gov/submissions/CIK{cik_zero_padded_10}.json` to get `filings.recent.primaryDocument[i]` for the matching accession number.
3. Fetch the document from `https://www.sec.gov/Archives/edgar/data/{cik}/{accession_no_nodashes}/{primary_doc}`.
4. Strip HTML tags; use the result as `raw_content`.

Note: the `Archives/{cik}/{accession_nodash}/index.json` directory endpoint exists but carries no sequence or form-type metadata — it cannot identify the primary document. The submissions API at `data.sec.gov` is the correct source. Both `data.sec.gov` and `www.sec.gov` subdomains count against the same 10 req/s SEC aggregate rate limit bucket.

Each 8-K requires two additional HTTP calls (submissions lookup + document). Both must flow through the existing `rate_limited_client`. Throughput with document fetching: ~3 documents/second at the limit.

**Fallback**: if either additional request fails (4xx, 5xx, network timeout), log at `WARNING` with accession number and status code; use the metadata-only content. Do not abort the batch. A future re-extraction via reextraction-cli can recover the full text.

## Out of scope

Changes to the LLM extraction prompt. Changes to `IngestionPipeline`. New fields on `RawDocument` or `ResearchSignalEvent`. Other connectors.

## Constraints

- Invariant 4: no `if source_type == "edgar"` in shared code. The document-fetch logic lives entirely within `SecEdgarConnector`.
- SEC rate limit: 10 req/s aggregate across all `*.sec.gov` and `data.sec.gov` hosts. Both additional calls per document must flow through `rate_limited_client`.
- Descriptive `User-Agent` header is mandatory — already an existing requirement (SEC blocks by IP without it).
- `pytest-socket --disable-socket` across the unit suite. The document-fetch HTTP calls must be stubbed.

## Required tests

New tests in the existing EDGAR connector test file (all existing tests must still pass):

- `test_edgar_raw_content_is_filing_text_not_form_metadata` — stub the document-fetch response with sample 8-K HTML; assert `raw_content` contains stripped body text and does not consist solely of metadata fields (Accession Number, Form Type, etc.)
- `test_edgar_cik_extracted_from_accession_number` — `0001234567-23-456789` → CIK `1234567`; `0000320193-23-000077` → CIK `320193`
- `test_edgar_document_fetch_uses_rate_limiter` — mock the rate limiter; assert it is called for both the index request and the document request, not only for the initial search
- `test_edgar_document_fetch_failure_falls_back_to_metadata` — stub the document request to return 503; assert `raw_content` is the metadata string and no exception is raised; assert a WARNING is logged
- `test_edgar_html_stripped_from_primary_document` — stub response with `<p>Pursuant to the requirements...</p>` HTML; assert `raw_content` is `Pursuant to the requirements...` with no HTML tags

## Definition of done

```bash
cd services/ingestion-scraper && uv run pytest tests/unit/test_edgar_connector.py -q
```

Expected: prior passing count + 5 new tests passed.

Then: one live fetch of an 8-K filing (any watched-company 8-K from the past 12 months) with the fixed connector; confirm `raw_content` contains filing prose rather than form metadata. Record accession number, entity name, and `raw_content` character count in `DECISIONS.md`.

# EDGAR Press-Release Content

**Status:** done
**Blocked by:** —
**Branch:** `feature/edgar-press-release-content`

---

## Context

`SecEdgarConnector` (`services/ingestion-scraper/src/auspex_ingest/connectors/sec_edgar.py`) searched every 8-K through EFTS and fetched only the cover document, located through `data.sec.gov/submissions` using the CIK taken from the accession prefix. `published_date` was the file date at midnight UTC.

The edge feasibility audit (2026-10-07, recommendation 5 and the EDGAR part of recommendation 2) found three problems:

- Trial readouts, CRLs and clinical holds are press releases furnished as Exhibit 99.1. The cover document says only "a press release is furnished as Exhibit 99.1", so the extractor never saw the news.
- Most 8-Ks (officer changes, agreements, votes) carry no price-relevant text for this system.
- `docs/requirements.md` §6.7 maps EDGAR `published_date` to `acceptanceDateTime`. A file date at midnight puts an after-close filing at the same day's open: look-ahead.

## What this builds

1. Item filter: only 8-Ks carrying item 2.02, 7.01 or 8.01 are kept, before any document request.
2. One document per accession, even when full-text search returns a hit per filed document.
3. The filing index (`Archives/edgar/data/{company_cik}/{accession_nodash}/{accession}-index.htm`) is read for the cover document, `EX-99.1` and the acceptance time.
4. `raw_content` is the Exhibit 99.1 text followed by the cover text, so the readout falls inside the extractor's first 4,000 characters.
5. `published_date` is the acceptance time (US Eastern on the index page) converted to UTC. Without it, the fallback is 17:30 ET on the file date, the latest an acceptance can be for that file date.
6. The company CIK comes from `ciks[0]`, not the accession prefix (the filing agent for most large filers).

## Out of scope

- Raising the extractor's 4,000-character limit (`extractor.py`, `extraction_backend.py`). That is shared code and belongs with company-level extraction; leading with the exhibit covers the readout headline and first paragraphs.
- Exhibits other than 99.1 (99.2 is usually an investor deck).
- Other connectors.

## Constraints

- Every request goes through `RateLimitedClient` under the shared `sec.gov` bucket, with the `User-Agent` header (CLAUDE.md SEC trap).
- `fetch_since()` only fetches and maps; archive-first and idempotency stay in `IngestionPipeline`.
- `event_id` stays `edgar:{accession}`: content and timestamp changes do not change identity (invariant 14).
- UTC everywhere (invariant 9): acceptance times are converted from `America/New_York`.

## Required tests

All in `services/ingestion-scraper/tests/unit/test_sec_edgar.py`, with respx and HTML fixtures in `tests/fixtures/` (`edgar_filing_index.htm`, `edgar_8k_cover.htm`, `edgar_ex99_1_readout.htm`).

- `test_exhibit_99_1_press_release_is_fetched_and_leads_raw_content`
- `test_readout_in_exhibit_99_1_reaches_the_extractor_input_window`
- `test_filing_without_exhibit_99_1_uses_the_primary_document_only`
- `test_exhibit_fetch_failure_keeps_the_primary_document_and_warns`
- `test_8k_without_press_release_items_is_skipped_before_any_document_fetch` (3 cases)
- `test_8k_with_a_press_release_item_is_kept` (3 cases)
- `test_one_document_per_accession_when_search_returns_a_hit_per_filed_document`
- `test_published_date_is_the_acceptance_time_converted_from_eastern_to_utc`
- `test_acceptance_time_in_winter_uses_the_standard_time_offset`
- `test_unparseable_acceptance_time_falls_back_to_the_file_date_cutoff`
- `test_published_date_without_acceptance_time_is_the_file_date_after_the_filing_cutoff` (replaces the midnight file-date test)
- `test_edgar_filing_is_located_by_company_cik_not_accession_prefix`
- `test_edgar_every_sec_request_goes_through_rate_limiter_with_user_agent` (replaces the submissions rate-limiter test)

Red before implementation: 16 failed, 16 passed, every failure an `AssertionError` (metadata-only `raw_content`, midnight `published_date`, non-press-release 8-Ks still yielded, submissions URL requested instead of the index).

## Definition of done

```bash
cd services/ingestion-scraper && uv run pytest tests/unit/test_sec_edgar.py -q
```

Expected: **32 passed**. Unit suite 266 passed; ruff and mypy clean.

## Notes

- The index page layout and the Eastern-time `Accepted` field were not verified live from the implementation session (no network route to sec.gov there). A wrong parse fails safe: the document falls back to metadata or the cover, with a warning in the logs. Check the first live run's logs for `edgar filing index` warnings before starting the backfill.
- The fixtures describe a fictional company (Northwind Gene Therapeutics, NWG-301) so they cannot be mistaken for real readouts.

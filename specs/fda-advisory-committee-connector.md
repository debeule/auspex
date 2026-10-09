# FDA Advisory Committee Connector (Federal Register)

**Status:** blocked
**Blocked by:**
1. Met: company-level event extraction (`specs/done/company-level-extraction.md`, schema 1.1) — company and program identifiers on `ResearchSignalEvent`.
2. `specs/catalyst-calendar.md` — the `catalysts` extraction fields and the core-hub calendar this connector's events land in.

**Branch:** `feature/fda-advisory-committee-connector`

---

## Context

FDA advisory committee meetings on a specific application are scheduled binary events: the committee's vote often moves the sponsor's stock more than the later approval decision. They are announced as notices in the Federal Register, typically weeks before the meeting. The 2026-10-07 edge feasibility audit lists advisory committee dates among the free company-level sources to add (row 9).

The Federal Register publishes a free JSON API without a key: `https://www.federalregister.gov/api/v1/documents.json`, filterable by agency (`food-and-drug-administration`), document type (`NOTICE`), search term, and publication date range, with each document's full text at a linked URL. Not reachable from the scoping session (proxy-blocked); verify the endpoint, parameters and rate expectations at the start of the session and record them in `DECISIONS.md` and the requirements §6.8 table.

Notice text names the committee, meeting date and, for product-specific meetings, the application number, product and sponsor, in prose. Mapping that prose to a company and program needs the LLM path, so this is a regular (LLM-extracted) connector, not a structured one.

## What this builds

- `connectors/federal_register.py` — `FederalRegisterConnector`, `source_type = "fda_adcomm"`. `fetch_since(cursor)` pages FDA notices published since the cursor whose title matches "Advisory Committee; Notice of Meeting" (and the agency's variants, listed in `source_config`), fetches the full text, yields one `RawDocument` per notice. `published_date` = Federal Register publication date. `canonical_id = "fr:<document_number>"`.
- `sources.yaml` entry with a pre-filter vocabulary of committee names relevant to the universe (oncology, cellular tissue and gene therapies, peripheral and central nervous system, and so on), so general-matter meetings are filtered before the LLM.
- Extraction fills `catalysts` with `catalyst_type = adcomm`, the meeting date, and the application id when given. Meeting cancellations and postponements (also published as notices) map to `status = withdrawn` or a new date, as a new disclosure.

## Out of scope

- PDUFA dates (`specs/catalyst-calendar.md`).
- Meeting outcomes and votes (published later on fda.gov, not in the Federal Register notice).
- Device and food committees.

## Constraints

- Invariants 1, 3, 4, 6, 9, 13. The base URL lives in `sources.yaml` `source_config`, not in code.
- Known-at date is the Federal Register publication date; the meeting date is the catalyst date, never the known-at date.
- Requests through `RateLimitedClient`; configure 1 req/s (no published limit).
- Unit tests on saved fixtures; `pytest-socket` blocks the network.

## Required tests

In `services/ingestion-scraper/tests/unit/test_federal_register.py`:
- `test_only_fda_meeting_notices_are_yielded`
- `test_published_date_is_federal_register_publication_date_not_meeting_date`
- `test_canonical_id_is_federal_register_document_number`
- `test_pagination_follows_next_page_until_exhausted`
- `test_postponement_notice_is_yielded_as_a_new_document`
- `test_general_matters_meeting_is_prefiltered_out`
- `test_requests_go_through_the_rate_limited_client`
- `test_cancellation_notice_is_yielded_as_a_new_document`

## Definition of done

```bash
cd services/ingestion-scraper && uv run pytest tests/unit/test_federal_register.py -q --strict-markers && uv run pytest tests/unit -q && uv run ruff check . && uv run mypy src
```

Expected: 8 passed; full unit suite green.

Then: a live fetch over the last six months; notice count, product-specific meetings found, and extraction spot-check (company and date correct on 10 notices) recorded in `DECISIONS.md`. `services/ingestion-scraper/README.md` connectors table and known API constraints updated.

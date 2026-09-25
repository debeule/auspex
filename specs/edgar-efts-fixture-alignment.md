# EDGAR EFTS Fixture Alignment

**Status:** ready
**Branch:** `feature/edgar-efts-fixture-alignment`

---

## Context

The EDGAR connector unit test fixtures (`edgar_efts_page1.json`, `edgar_efts_multi_item.json`) use invented field names that never matched the real EFTS `_source` schema. Discovered during edgar-content-fix live fetch testing when the connector returned zero documents against the live API.

Real EFTS `_source` field names (confirmed 2026-09-25 against `https://efts.sec.gov/LATEST/search-index`):

| Fixture field (invented) | Real EFTS field | Notes |
|---|---|---|
| `accession_no` | `adsh` | Same dash-separated format |
| `entity_id` | `ciks[0]` | List of one zero-padded CIK string |
| `entity_name` | `display_names[0]` | Includes ` (TICKER)  (CIK XXXXXXXXXX)` suffix — strip at `(` |
| `form_type` | `form` | Also present as `file_type`; both are identical strings |
| `period_of_report` | `period_ending` | Same `YYYY-MM-DD` format |
| `items` | `items` | List of strings in real API; scalar string in fixtures |
| `file_date` | `file_date` | Unchanged |

During edgar-content-fix, dual-format fallbacks were added to `_map` to paper over this (`source.get("accession_no") or source.get("adsh")`, etc.). This spec removes those fallbacks.

## What this builds

1. Update `tests/fixtures/edgar_efts_page1.json` and `tests/fixtures/edgar_efts_multi_item.json` to use real field names.
2. Simplify `SecEdgarConnector._map` — remove all dual-format fallbacks, read only the real field names.
3. Update any test assertions that check metadata-format strings tied to the old field names (e.g., `"BEAM THERAPEUTICS" in doc.raw_content`).

`edgar_efts_empty.json` needs no changes — it has no hits.

## Out of scope

New connector behaviour. Changes to `raw_content` format or document-fetch logic. Other connectors.

## Constraints

- Invariant 4: no `if source_type == "edgar"` in shared code — unchanged.
- `entity_id` for the `source_url` build needs the CIK with leading zeros preserved (`ciks[0]` is already zero-padded).
- `display_names[0]` contains ` (TICKER)  (CIK XXXXXXXXXX)` — strip from the first `(` for `entity_name` used in metadata fallback.
- `items` is a list in the real API — join with `", "` for the metadata fallback string.

## Required tests

No new tests. All **18** existing tests in `tests/unit/test_sec_edgar.py` must pass after the fixture and `_map` changes. That count is the definition of done.

The existing test `test_efts_payload_maps_to_rawdocument` checks `"BEAM THERAPEUTICS" in doc.raw_content`. After this spec, `raw_content` in the fallback path uses `entity_name` derived from `display_names[0]`. Update the fixture's `display_names` value to include "BEAM THERAPEUTICS" so the assertion still passes — or update the assertion to match the new fixture's entity name.

## Definition of done

```bash
cd services/ingestion-scraper && uv run pytest tests/unit/test_sec_edgar.py -q
```

Expected: **18 passed**.

Then: re-run the live fetch from the edgar-content-fix spec verification step — confirm `raw_content` now contains filing prose for a real 8-K, and record the result in `DECISIONS.md`.

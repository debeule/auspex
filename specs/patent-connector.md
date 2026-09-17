# Patent Filings Connector (EPO OPS)

**Status:** blocked
**Blocked by:** `EPO_OPS_KEY` and `EPO_OPS_SECRET` — register at `developers.epo.org`
**Branch:** `feature/patent-connector`

---

## Context

Four connectors are live (bioRxiv, PubMed, ClinicalTrials, EDGAR, FDA). This adds a fifth. The connector pattern is established in `src/auspex_ingest/connectors/base.py` — implement `SourceConnector`, add an entry to `config/sources.yaml`, register in `dags/auspex_dags.py`. No changes to `IngestionPipeline` or any shared code.

Both PatentsView URLs are dead and Lens.org requires a commercial licence for this use case. EPO OPS is the correct source — see `DECISIONS.md` and root `CLAUDE.md` known traps.

## What this builds

A connector that polls EPO OPS for patent publications matching biotech CPC classes (C12N, A61K, A61P, C07K), archives them to MinIO, and feeds them through the extraction pipeline. Covers EP, PCT (WO), and US patents via the DOCDB feed.

## Out of scope

Grant-stage analysis, claim parsing, citation graphs. This connector ingests publication metadata + abstract only, same as every other connector.

## Constraints

- Invariant 1: writes only to MinIO and Kafka.
- Invariant 4: connector + `sources.yaml` entry only — no `if source_type == "epo_ops"` anywhere.
- **`published_date` = pre-grant publication date (A1/A2 `date_published`), never `filing_date`.** A US application is not public at filing — it publishes ~18 months later. Getting this wrong inverts the look-ahead-bias guard.
- `canonical_id = "epo-app:<country>-<app_number>"` — stable across the A1 pre-grant and its B1 grant for the same application. `external_id` = full DOCDB publication reference `<country>-<pub_number>-<kind>`.
- OAuth2 client credentials; token expires in 20 minutes — cache and refresh before expiry.
- Rate limit: 2.5 req/s standard tier.

## Required tests

- `test_epo_payload_maps_to_rawdocument` — fixture-driven
- `test_published_date_is_the_public_disclosure_date_not_filing_date` — fixture with an 18-month gap between filing and publication; must fail if fields are swapped
- `test_filing_date_and_granted_date_are_retained_in_raw_content_but_excluded_from_alignment`
- `test_pregrant_publication_and_its_later_grant_resolve_to_one_event_id` — A1 and B1 share the same `application-reference` → one `canonical_id` → one `event_id`
- `test_oauth_token_is_refreshed_before_expiry`
- `test_429_respects_the_retry_after_header`
- `test_missing_credentials_fail_with_clear_message_not_deep_401`
- `test_pending_filing_with_no_grant_date_is_handled`
- `test_pct_application_with_us_and_ep_designations_produces_one_document`
- `test_connector_runs_through_the_ingestion_pipeline_unchanged`

## Definition of done

```bash
cd services/ingestion-scraper && uv run pytest tests/unit/test_epo_ops.py -q
```

Expected: 10+ passed. Plus one manual live query returning at least one result per watched company. Confirm EPO OPS standard-tier rate limit from documentation and record in `DECISIONS.md`.

## Notes

Confirm the exact XML element path for `application-reference` against a real API response and record in `DECISIONS.md` — the plan-level spec was written without a live API to verify against.

# Ingestion Config UI

**Status:** blocked
**Blocked by:** `specs/managed-ingestion-config.md` (config API, versions, vocabulary validation) and `specs/dashboard-foundation.md` (BFF, login, API client).
**Branch:** `feature/ingestion-config-ui`

---

## Context

Decided 2026-10-08: the dashboard is where the user manages what Auspex tracks. Research config is shown but never edited, so pre-registration stays meaningful.

After the blockers are done:
- core-hub serves the effective config per source, its version history with diffs, the watchlist with aliases, and `PUT` endpoints that require a `reason`.
- The scraper serves `POST /config/validate-vocabulary`, which reports golden documents a candidate term list would drop.
- The dashboard has a BFF, a single-user login, a typed API client, and watchlist and company-detail pages.

Locked research config lives in the repo: `config/hypotheses/*.yaml` with `registry.jsonl` (SHA-256 per file, checked by `auspex_backtesting.hypothesis.verify_hypothesis`), `config/hypotheses/protocol.yaml`, `config/strategies/*.yaml` (name, version, status), and `config/models/registry.yaml` with gate records in `config/models/scores/`. No API exposes any of it today.

## What this builds

1. **Companies** (`/config/companies`, extending the watchlist): add or deactivate a company; edit its CIK, aliases (name variants, drug and program names) and gene targets. Every save asks for a one-line reason.
2. **Sources** (`/config/sources`, `/config/sources/[source_type]`): per source, the term list, query parameters, and the "include watchlist terms" switch. Before saving a term list, the page calls vocabulary validation and shows the result. A list that would drop a golden document cannot be saved, and the page names the documents it would drop.
3. **History** (`/config/history`): versions newest first, with time (UTC), reason and diff; each version links to the extractions that ran under it (filtered by `prefilter_version`).
4. **Research config, read-only** (`/config/research`): each hypothesis with id, version, registered hash and whether the file still matches it; the protocol hash; each strategy's name, version and status; the active extraction model, its digest and its gate result. Served by a new read-only `GET /research-config` on price-service (`auspex_backtesting.api`), which mounts `config/` read-only. The page has no edit controls, and the BFF exposes no write route for it.

## Out of scope

- Editing hypotheses, protocol, strategies, model registry, rate limits or universe rules. These change only through a dated re-registration in the repo.
- Source schedules, pause and trigger (`specs/pipeline-control-view.md`).
- Bulk import or export of config.

## Constraints

- Invariant 2: every write goes through core-hub.
- Pre-registration: `/research-config` reads and hashes files, never writes; `verify_hypothesis` runs per request, never cached across file changes.
- Invariant 9: times shown in UTC.
- TSDoc conventions; the shared API client from the dashboard foundation.

## Required tests

Dashboard (Vitest), `src/__tests__/`:
- `CompaniesConfig.test.tsx`
  - `test_save_without_reason_is_blocked`
  - `test_alias_and_gene_target_edits_are_sent_with_reason`
  - `test_deactivating_a_company_keeps_it_listed_as_inactive`
- `SourcesConfig.test.tsx`
  - `test_term_list_is_validated_before_save`
  - `test_term_list_dropping_golden_documents_cannot_be_saved_and_names_them`
  - `test_include_watchlist_terms_switch_is_saved`
- `ConfigHistory.test.tsx`
  - `test_versions_show_reason_time_in_utc_and_diff`
  - `test_version_links_to_extractions_with_its_prefilter_version`
- `ResearchConfig.test.tsx`
  - `test_research_config_page_has_no_edit_controls`
  - `test_modified_hypothesis_is_shown_as_not_matching_its_registered_hash`
- `bff-routes.test.ts`
  - `test_bff_exposes_no_write_route_for_research_config`

backtesting, `tests/unit/test_research_config_api.py`:
- `test_research_config_lists_hypotheses_with_registered_hash_and_match_flag`
- `test_edited_hypothesis_file_reports_mismatch`
- `test_research_config_lists_strategy_status_and_active_model_gate`
- `test_research_config_endpoint_rejects_non_get_methods`

## Definition of done

```bash
cd services/dashboard && npm run lint && npx tsc --noEmit && npm run test:ci && npm run build
cd services/backtesting && uv run pytest tests/unit/test_research_config_api.py -q --strict-markers
```

Expected: all dashboard tests pass, with the 11 above included; 4 passed for the research-config API.

Then on the stack: add an alias to a company with a reason; it appears in `/config/history` with its diff, and the next ingestion run for a source that includes watchlist terms carries the new `prefilter_version`.

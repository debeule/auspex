# Signal Browse Views

**Status:** blocked
**Blocked by:** `specs/graph-and-connector-wiring-fixes.md` (mechanism links and `Company.ticker`, without which these views show missing data) and `specs/dashboard-foundation.md` (BFF, login, API client).
**Branch:** `feature/signal-browse-views`

---

## Context

The dashboard is the place to use what Auspex produces (decided 2026-10-08). Today core-hub offers only `GET /api/v1/signals/{ticker}`, which returns direct signals and corroborations for one ticker, plus the watchlist endpoints. There is no list, search or filter, no corroboration endpoint, and no company view. No list endpoint pages its results.

The data exists:
- Postgres `signal_current`: one row per `event_id` with title, summary, source, `published_date`, directionality, confidence, `event_type`, `primary_company`, `program_identifiers`, `trial_ids`.
- Postgres `corroboration`: `entity_key`, `participants_hash`, `participant_event_ids`, `distinct_source_count`, `corroborated_at`, `superseded_by`.
- Neo4j: `Signal` linked to `GeneTarget`, `Mechanism` and `Company`.
- `CorroborationScorer` computes a confidence at read time.

Requirements §4.1: a superseded corroboration row is excluded from REST responses. §3.11: bind parameters everywhere and allowlist validation at the controller boundary.

## What this builds

1. **core-hub read endpoints**, all keyset-paged (`limit` ≤ 200, opaque `cursor`, response `{items, next_cursor}`):
   - `GET /api/v1/signals`: filters `source_type`, `event_type`, `directionality`, `from`/`to` on `published_date`, `min_confidence`, `company`, `gene_target`, `mechanism`, and `q` (case-insensitive match on title and summary). Newest first.
   - `GET /api/v1/corroborations`: filters `entity`, `from`/`to` on `corroborated_at`, `min_sources`. Excludes superseded rows. Each item carries its participants' titles and source types, and the score with its parts (diversity, recency) and the `as_of` it was computed at.
   - `GET /api/v1/companies`: name, ticker if known, signal count, latest signal date, whether it is on the watchlist. `GET /api/v1/companies/{name}` (normalized name) adds its signals, gene targets, mechanisms and corroborations.
   - `GET /api/v1/entities/{label}/{name}` for a `GeneTarget` or `Mechanism`: its signals and corroborations.
2. **Dashboard views:** `/signals` (filterable table, filters kept in the URL), `/corroborations`, `/companies` and `/companies/[name]`, `/entities/[label]/[name]`. Every row links to its company, entities and participants. The existing ticker search on `/` becomes a global search box that routes to the matching company, entity or signal list.

## Out of scope

- The full lineage chain per document (`specs/lineage-trace-view.md`).
- Graph visualisation (node-link diagrams).
- Persisting scores or adding corroboration kinds.
- Write actions.

## Constraints

- Invariant 12 and §3.11: every filter is a bind parameter. Enum filters (`source_type`, `event_type`, `directionality`, entity `label`) are validated against allowlists; `q` is escaped for `LIKE`; dates parse as ISO-8601 UTC or return 400.
- §4.1: superseded corroborations never appear in these responses.
- Invariant 9: all timestamps in responses are UTC ISO-8601.
- Keyset pagination is stable under concurrent inserts: a row inserted while paging never duplicates or skips an already-returned row.

## Required tests

core-hub, `src/integrationTest/java/.../query/SignalBrowseIT.java`:
- `signalListIsNewestFirstAndPagesWithoutDuplicatesUnderConcurrentInserts`
- `eachSignalFilterNarrowsTheResult` (parametrized per filter)
- `textSearchMatchesTitleAndSummaryCaseInsensitively`
- `likeWildcardsInQueryAreMatchedLiterally`
- `unknownEnumFilterValueReturns400`
- `malformedDateReturns400`
- `limitAbove200IsRejected`
- `injectionPayloadInEveryStringFilterIsTreatedAsData` (parametrized)

core-hub, `src/integrationTest/java/.../query/CorroborationBrowseIT.java`:
- `supersededCorroborationsAreExcluded`
- `corroborationItemCarriesParticipantsAndScoreParts`
- `scoreAsOfIsReturnedWithTheScore`
- `minSourcesFilterExcludesSmallerGroups`

core-hub, `src/integrationTest/java/.../query/CompanyBrowseIT.java`:
- `companyListShowsTickerOnlyWhenKnown`
- `companyDetailListsSignalsEntitiesAndCorroborations`
- `entityDetailListsSignalsAndCorroborationsForGeneTargetAndMechanism`

Dashboard (Vitest):
- `SignalsBrowse.test.tsx`
  - `test_filters_are_reflected_in_the_url_and_restored_on_load`
  - `test_next_page_uses_the_returned_cursor`
  - `test_empty_result_shows_empty_state`
- `CorroborationsBrowse.test.tsx`
  - `test_score_shows_its_parts_and_as_of_time`
  - `test_participant_links_go_to_signal_and_company`
- `GlobalSearch.test.tsx`
  - `test_ticker_routes_to_company_and_gene_symbol_routes_to_entity`

## Definition of done

```bash
cd services/core-hub && ./gradlew test integrationTest --rerun-tasks
cd services/dashboard && npm run lint && npx tsc --noEmit && npm run test:ci && npm run build
```

Expected: all green, including the 15 Java and 6 dashboard tests above (parametrized cases counted once).

Then on the stack: open `/corroborations`, follow one to a participant's company, and filter `/signals` to that company.

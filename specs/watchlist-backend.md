# Watchlist Backend

**Status:** ready
**Branch:** `feature/watchlist-backend`

---

## Context

The current watchlist is a static env var (`WATCHED_TICKERS=SRPT,SPRB,...`). There is no persistence, no REST interface, and no user-facing way to change it. The `watchlist-alerts` hold spec assumes a persisted watchlist with entity keys — this spec provides that foundation (superseding the `watchlist_entries` table the hold spec planned to create; see Notes).

No auth exists and requirements say not to implement it speculatively. The schema is designed for single-user installation. Multi-user support requires one Flyway migration (add `user_id` FK, drop `watchlist_ticker_unique`, add `UNIQUE (user_id, ticker)`) — documented in migration comments.

## What this builds

### Postgres schema (new Flyway migration)

```sql
CREATE TABLE watchlist (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker      VARCHAR(10)   NOT NULL,
    company_name TEXT          NOT NULL,
    added_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    notes       TEXT,
    -- Single-user installation. For multi-user: add user_id UUID NOT NULL REFERENCES users(id),
    -- drop watchlist_ticker_unique, add CONSTRAINT UNIQUE (user_id, ticker).
    CONSTRAINT watchlist_ticker_unique UNIQUE (ticker)
);

CREATE TABLE watchlist_gene_target (
    watchlist_id UUID  NOT NULL REFERENCES watchlist(id) ON DELETE CASCADE,
    gene_target  TEXT  NOT NULL,
    source       TEXT  NOT NULL CHECK (source IN ('graph', 'clinicaltrials', 'manual')),
    added_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (watchlist_id, gene_target)
);

CREATE INDEX ON watchlist_gene_target (gene_target);
```

`gene_target` stores normalized gene target names that match `GeneTarget.name` in Neo4j (e.g., `"DMD"`, `"HBB"`, `"BCL11A"`). The exact format must be verified against live Neo4j data before seeding (see Notes re entity_key format).

### REST endpoints (core-hub)

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/watchlist` | List all entries with gene targets |
| `GET` | `/api/v1/watchlist/preview?ticker={ticker}` | Resolve company name + auto-detect gene targets. No write. |
| `POST` | `/api/v1/watchlist` | Add ticker. Body: `{ticker, company_name, gene_targets: [{name, source}]}` |
| `DELETE` | `/api/v1/watchlist/{ticker}` | Remove entry; cascades to gene targets |
| `PATCH` | `/api/v1/watchlist/{ticker}/gene-targets` | Body: `{add: ["HBB"], remove: ["DMD"]}` |
| `GET` | `/api/v1/watchlist/{ticker}/summary` | Enhanced signal summary for the company detail page |

### Preview endpoint — `GET /api/v1/watchlist/preview?ticker={ticker}`

Three lookups performed in parallel before any write:

1. **Company name** — load `https://www.sec.gov/files/company_tickers.json` at JVM startup, cache in memory (`Map<String, String>` ticker → name). ~5 MB, changes infrequently. If ticker absent: `company_name: null`. Do not re-fetch on every request.
2. **Graph gene targets** — Cypher: `MATCH (s:Signal)-[:MENTIONS]->(c:Company {ticker: $ticker}), (s)-[:TARGETS]->(g:GeneTarget) RETURN DISTINCT g.name AS name, count(s) AS signal_count ORDER BY signal_count DESC`.
3. **ClinicalTrials programs** — `GET https://clinicaltrials.gov/api/v2/studies?query.spons={company_name}&fields=protocolSection.conditionsModule.conditions,protocolSection.armsInterventionsModule.interventions.interventionMeshTerms&pageSize=50`. Returns condition names and intervention mesh terms as `ct_suggestions`. If `company_name` is null, skip this step.

Response:
```json
{
  "ticker": "SRPT",
  "company_name": "Sarepta Therapeutics",
  "graph_gene_targets": [{"name": "DMD", "signal_count": 14}],
  "ct_suggestions": [{"term": "Duchenne Muscular Dystrophy", "type": "condition"}, {"term": "AAV9-micro-dystrophin", "type": "intervention"}]
}
```

### Add endpoint — `POST /api/v1/watchlist`

The client sends the confirmed data (after the user reviewed the preview). Core-hub:
1. Validates ticker format (`^[A-Z][A-Z0-9.\-]{0,9}$`).
2. Returns 409 on duplicate ticker.
3. Requires `company_name` non-empty — the preview must be run first.
4. Inserts `watchlist` row and `watchlist_gene_target` rows from the request body.
5. Returns the created entry.

Auto-detect is not repeated here — the preview is where detection runs; POST saves what the user confirmed.

### Summary endpoint — `GET /api/v1/watchlist/{ticker}/summary`

Extends the existing `GET /api/v1/signals/{ticker}` query with gene target breakdown and stats:

```json
{
  "ticker": "SRPT",
  "company_name": "Sarepta Therapeutics",
  "gene_targets": [{"name": "DMD", "source": "graph", "signal_count": 14, "last_seen": "2026-09-15"}],
  "direct_signals": [...],
  "corroborations": [...],
  "stats": {
    "total_direct": 47,
    "total_corroborations": 12,
    "most_active_gene_target": "DMD",
    "last_signal_at": "2026-09-15T14:30:00Z"
  }
}
```

Corroborations are pre-filtered to entity keys matching the ticker's tracked gene targets: `WHERE SPLIT_PART(entity_key, ' | ', 1) = ANY($tracked_gene_targets)`. This format must be confirmed against the actual `entity_key` values in the `corroboration` table before implementation (see Notes).

## Out of scope

Pre-filter vocabulary updates when gene targets are added (separate spec — connector change). Notifications on new corroborations (watchlist-alerts hold spec). Multi-user auth. Price chart data (requires MinIO reader endpoint — separate spec). The `WATCHED_TICKERS` env var is left in `.env.example` as deprecated for one release cycle; it is not removed here.

## Constraints

- Invariant 2: core-hub is sole writer to application DB and Neo4j. ✓
- Invariant 6: no credentials in source. SEC JSON and ClinicalTrials API are public; no API key needed.
- The SEC JSON cache is populated at JVM startup. Startup must not fail if the SEC URL is unreachable — log at WARNING and leave the cache empty (company name resolution returns null until the next restart).
- ClinicalTrials is an outbound HTTP call from core-hub. This must be stubbed in unit tests (WireMock). The preview endpoint must not be slow if ClinicalTrials is slow — apply a 5-second timeout.
- Gene target values stored in `watchlist_gene_target` must match the case and format of `GeneTarget.name` in Neo4j. Normalize input: trim and uppercase before insertion.
- Removing a watchlist entry does NOT remove signals or corroborations — historical data is preserved.
- `corroboration.entity_key` format: verify the separator used in the live implementation before writing the SPLIT_PART query. The format observed in test data is `"ENTITY_NAME | LABEL"` (space-pipe-space); the watchlist-alerts hold spec incorrectly uses colon notation. Record the confirmed format in DECISIONS.md.

## Required tests

Unit tests (`WatchlistServiceTest.java`, 8 tests):
- `test_preview_resolves_company_name_from_cached_sec_mapping` — SRPT present in cache → "Sarepta Therapeutics"; unknown ticker → null
- `test_preview_skips_ct_lookup_when_company_name_null` — ticker not in SEC cache → ClinicalTrials HTTP never called
- `test_preview_returns_graph_gene_targets_ordered_by_signal_count` — Neo4j stub returns two gene targets with different counts; response ordered descending
- `test_preview_returns_ct_suggestions_from_wiremock_stub` — WireMock stub returns known ClinicalTrials JSON; conditions and interventions extracted correctly
- `test_add_persists_entry_and_gene_targets`
- `test_add_duplicate_ticker_returns_409`
- `test_patch_gene_targets_adds_and_removes_selectively` — initial set [DMD]; PATCH {add: [HBB], remove: [DMD]} → final set [HBB]
- `test_summary_corroborations_filtered_to_tracked_gene_targets` — two corroborations in Postgres stub: one with `entity_key` matching tracked gene target, one not; only the matching one returned

Integration tests (`WatchlistIT.java`, 3 tests):
- `test_watchlist_entry_persists_and_cascades_on_delete` — add entry + gene targets; verify in Postgres; DELETE; verify both rows gone via CASCADE
- `test_summary_queries_neo4j_and_postgres` — seed Neo4j with Company node + Signal nodes + GeneTarget; seed Postgres corroboration; GET summary → correct gene target counts and corroboration count
- `test_company_name_null_graceful` — SEC cache miss; POST with null company_name → 400 with message naming the field

## Definition of done

```bash
cd services/core-hub && ./gradlew test --tests '*WatchlistServiceTest' --rerun-tasks
cd services/core-hub && ./gradlew integrationTest --tests '*WatchlistIT' --rerun-tasks
```

Expected: 8 unit + 3 integration = 11 passed.

Then: one live preview call against a running stack — `GET /api/v1/watchlist/preview?ticker=SRPT`; confirm company name resolves and graph gene targets return. Record response in DECISIONS.md.

## Notes

**watchlist-alerts hold spec conflict**: the hold spec planned a `watchlist_entries(entity_key TEXT UNIQUE)` table. Do not create that table. When watchlist-alerts comes off hold, it should read entity keys from `SELECT gene_target FROM watchlist_gene_target JOIN watchlist ON watchlist_id = watchlist.id` — the `watchlist_gene_target.gene_target` column is the functional equivalent. The hold spec's Flyway migration and seeding section should be replaced with a query against this schema. Update the hold spec before implementing it.

**entity_key format**: the watchlist-alerts hold spec uses `"BCL11A:GeneTarget"` but the corroboration table and graph use space-pipe-space: `"BCL11A | GENE_TARGET"`. Verify the actual format in the running implementation before writing the SPLIT_PART corroboration filter. Record the confirmed format in DECISIONS.md.

**SEC JSON freshness**: the public SEC company tickers file changes when companies are added or change their names. For a single-user local installation, a restart-only refresh is acceptable. If freshness matters, add a scheduled refresh (once per 24h) as a follow-on.

# Neo4j Indexing at Scale

**Status:** blocked
**Blocked by:** Historical backfill — this spec requires production-scale graph data (tens of thousands of signals) to make index optimizations meaningful. The backfill spec is itself blocked pending budget approval.
**Branch:** `feature/neo4j-indexing`

---

## Context

Constraint and index existence is tested from Phase 1 (`SchemaIT`). The constraints in place are:

- Unique: `Signal.event_id`, `GeneTarget.name`, `Mechanism.name`, `Company.name`
- Indexes (non-unique): `Signal.published_date`, `Signal.source_type`, `Company.ticker`

The corroboration query in `CorroborationScanner.findGroups()` and the REST query in `SignalQueryService.queryDirectSignals()` are the two hot paths. Both are currently untested at scale.

This spec runs once the historical backfill has populated the graph with ≥ 24 months of data across all 8 watched companies.

## What this builds

Query plan analysis for the two hot-path Cypher queries. Additional traversal indexes if and only if the query planner demonstrably does not use an existing index on the execution path. The test suite enforces the optimization holds at a representative node count.

Target scale (tentative — confirm after backfill): ~20,000 Signal nodes, ~500 GeneTarget nodes, ~200 Mechanism nodes, ~50 Company nodes. These are rough estimates based on the watched companies' public patent and publication counts.

## Out of scope

Schema changes. New relationship types. Indexes on fields not queried by existing code. Full-text search indexes (separate concern).

## Constraints

- `test_hot_path_queries_use_indexes_not_full_scans` asserts on `EXPLAIN` output (`IndexSeek` or `NodeIndexSeek` present), not on wall-clock time. Wall-clock latency is environment-dependent and unsuitable for a committed test.
- Only add an index if `EXPLAIN` confirms it is used. Unused indexes impose write overhead on every signal ingest.
- Indexes are added via a new Flyway migration (Cypher script in `src/main/resources/db/migration/neo4j/`). Not via ad-hoc Cypher in a startup bean.

## Required tests

Integration tests against a populated Neo4j Testcontainer:

- `test_corroboration_query_uses_index_on_signal_ingested_at` — seed at least 1,000 Signal nodes with varied `ingested_at` values; run `EXPLAIN` on the corroboration watermark query; assert the plan contains `NodeIndexSeek` on `ingested_at`. Determine the exact plan shape after running against the backfill-scale graph.
- `test_ticker_query_uses_index_on_company_ticker` — seed at least 100 Company nodes; run `EXPLAIN` on the `MATCH (s:Signal)-[:MENTIONS]->(c:Company {ticker: $ticker})` query; assert the plan uses the ticker index, not a full label scan.
- `test_p95_latency_within_threshold_at_representative_scale` — populate a Testcontainer with the backfill-scale node count; measure 100 executions of each hot-path query; assert p95 < 200ms. Threshold is tentative — revise after first measurement against real data.

## Definition of done

```bash
cd services/core-hub && ./gradlew integrationTest --tests '*Neo4jIndexIT' --rerun-tasks
```

All 3 tests pass at a node count matching the post-backfill graph. Latency threshold confirmed from measurement and recorded in `DECISIONS.md`.

## Notes

- Node count and latency thresholds are placeholders. Finalize them on first run against the populated graph and edit this spec before declaring the spec `ready` (the spec is currently `blocked`; it will need a scoping pass once the backfill is complete).
- If the existing indexes are sufficient (plans already show `NodeIndexSeek`), the spec's deliverable is the test suite alone — confirming no optimization is needed. The spec is done even if no new index is added.
- `EXPLAIN` in the Testcontainer context uses a small graph; plan shapes can differ at scale. Cross-check plan assertions against a separate run on the real populated graph before committing.

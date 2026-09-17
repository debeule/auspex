# Neo4j Indexing at Scale

**Status:** draft
**Blocked by:** —
**Branch:** `feature/neo4j-indexing`

---

## Context

Constraint and index *existence* is tested in `core-hub` from Phase 1 (`KafkaErrorHandlingIT`, `GraphUpdateService` tests). This spec is about query performance as the graph grows — it is only meaningful once the historical backfill has populated the graph with real-scale data.

## What this builds

Query plan analysis and, if needed, additional traversal indexes to keep the `GET /api/v1/signals/{ticker}` Cypher query within acceptable latency at production-scale node counts.

## Out of scope

Schema changes, new relationship types. This spec only adds indexes to existing graph structure.

## Constraints

- `test_ticker_query_uses_index_not_full_scan` asserts on query plan, not wall clock — wall clock is environment-dependent.
- Only add indexes that the query planner demonstrably uses. Unused indexes are write overhead.

## Required tests

- `test_ticker_query_uses_index_not_full_scan` — query plan analysis
- `test_p95_latency_within_threshold_at_scaled_node_count` — at a node count representative of the full backfill

## Definition of done

Both tests pass at backfill-scale node counts.

## Notes

Needs scoping before `ready`: what is the target node count? What is the acceptable p95 latency threshold? Both depend on the historical backfill completing first.

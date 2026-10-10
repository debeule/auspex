# Graph relationship replacement

**Status:** done
**Branch:** `feature/graph-relationship-replacement`

---

## Context

`services/core-hub/src/main/java/dev/auspex/corehub/persistence/Neo4jWriteService.java` (`upsert`) writes a signal in one transaction: `MERGE (s:Signal {event_id})` with its properties, then `MERGE` of each `TARGETS` (`GeneTarget`), `USES_MECHANISM` (`Mechanism`) and `MENTIONS` (`Company`) relationship in the event. It never removes a relationship. `PostgresWriteService` replaces `gene_targets`, `mechanisms` and `companies_mentioned` in `signal_current` on every write, and keeps each extraction in `signal_extraction_history`.

A signal is written again under the same `event_id` when it is re-extracted (`scripts/reextract.py` in the scraper, invariant 14: `event_id` never changes), replayed from the DLT, or redelivered.

Found by the consolidated audit of 2026-10-10 (finding C5; the audit file is in the project's `audit/` folder) and checked against `develop` at `d615504`. A re-extraction that corrects gene A to gene B, or drops a false company mention, leaves the old edge in the graph next to the new one while Postgres holds only the new values. The corroboration scan joins on those edges, so a removed entity can still produce a corroboration, and graph queries disagree with Postgres.

## What this builds

- **A write replaces the signal's own relationships.** In the same transaction as the merges, `upsert` deletes each outgoing `TARGETS`, `USES_MECHANISM` and `MENTIONS` relationship of that `Signal` whose target is not in the event's lists (compared on the same normalized names the merges use). Graph and Postgres then hold the same current entities for every signal.
- **Shared nodes stay.** Only relationships are deleted. A `GeneTarget`, `Mechanism` or `Company` node stays even when no signal points to it any more; other signals' edges to it are untouched.
- A repeated write with the same lists changes nothing.

## Out of scope

- Withdrawing or recomputing corroborations already stored or published from a removed edge (nothing consumes `auspex.signals.corroborated` yet; recorded in `DECISIONS.md` for when something does).
- Removing orphaned entity nodes.
- Signal history in the graph (Postgres `signal_extraction_history` stays the record of past extractions).
- When the corroboration scan sees a rewritten signal (`specs/done/corroboration-late-arrivals.md`).

## Constraints

- Invariant 2: core-hub is the only writer.
- Invariant 10: writes stay idempotent on `event_id`; a replay of the same event leaves the same graph.
- Invariant 12: the lists are parameters (`$genes`, `$mechanisms`, `$companies`), never concatenated.
- Write order stays Neo4j → Postgres → acknowledge, and the delete is inside the Neo4j transaction, so a failed write leaves the previous relationships whole.
- Trap: delete with `MATCH (s:Signal {event_id: $event_id})-[r:TARGETS]->(g) WHERE NOT g.name IN $genes DELETE r` and the like, never `DETACH DELETE` on a shared node.

## Required tests

Integration (`./gradlew integrationTest`, new `GraphRelationshipReplacementIT` in `persistence/`):
- `rewriteWithADifferentGeneReplacesTheTargetsEdge` — gene A then gene B: one `TARGETS` edge, to B
- `rewriteWithoutACompanyRemovesTheMentionsEdge`
- `rewriteWithoutAMechanismRemovesTheUsesMechanismEdge`
- `sharedEntityNodeAndOtherSignalsEdgesSurviveARewrite` — two signals target gene A; one is rewritten to gene B; gene A and the other signal's edge remain
- `repeatedIdenticalWriteLeavesTheGraphUnchanged`
- `graphAndPostgresHoldTheSameEntitiesAfterARewrite` — after a rewrite through the listener, the signal's edges match `signal_current`'s arrays

## Definition of done

```bash
cd services/core-hub && ./gradlew test --rerun-tasks
cd services/core-hub && ./gradlew integrationTest --rerun-tasks
```

Expected: the 6 tests above pass with the rest of both suites; test counts read from `build/reports/tests/`. Integration tests need Docker and run in CI.

## Notes

- The audit's alternative (versioned relationships filtered by active extraction) was not chosen: Postgres already keeps extraction history, and every graph query would need the filter.

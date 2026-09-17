# Kafka Streams Correlation

**Status:** draft
**Blocked by:** conditional — do not build unless the scheduled corroboration query is measurably inadequate
**Branch:** `feature/kafka-streams-correlation`

---

## Context

`ScheduledCorroborationService` in `core-hub` runs a watermark-driven Neo4j scan on a schedule. This spec replaces it with a Kafka Streams topology if and only if the scheduled approach proves measurably too slow or too expensive.

**Precondition:** record a latency or cost measurement against the production-scale graph first. If it is acceptable, do not build this. The abstract `CorroborationServiceContractTest` must still pass unmodified against the new implementation.

## What this builds

A Kafka Streams topology keyed by normalized entity that emits `CorroboratedSignal` on 2+ distinct source types within a 90-day window. Swaps the `CorroborationService` binding by Spring profile.

## Out of scope

Changes to the REST API, signal ingestion, or any non-corroboration logic.

## Constraints

- `CorroborationServiceContractTest` (abstract, in `core-hub`) must pass unmodified. Any test requiring an edit indicates a leaked implementation detail.
- The Step 1.5 REST suite must pass unmodified under the Streams profile.
- Two open risks must be resolved before starting implementation (see Notes).

## Required tests

- Full `CorroborationServiceContractTest` contract suite passes unmodified
- `test_topology_with_topologytestdriver`
- `test_out_of_order_event_within_window_still_corroborates`
- `test_late_arrival_past_grace_period_handled_per_documented_policy`
- `test_state_store_survives_restart`
- `test_duplicate_event_id_does_not_double_count`
- REST suite passes under the Streams profile

## Definition of done

```bash
cd services/core-hub && ./gradlew integrationTest --rerun-tasks
```

All above tests pass. REST suite passes with `--spring.profiles.active=streams`.

## Notes

Two open risks to verify before starting implementation:

1. **Stream time vs. historical replay**: Streams windows advance on stream time. Replaying historical records interleaves with live records — the pairwise semantics in `docs/requirements.md §4` are straightforward in Cypher but not in a windowed store. Verify behaviour before committing.

2. **Supersession semantics**: `docs/requirements.md §4.1` supersession has no natural expression in a windowed aggregation. Resolve the design before writing code.

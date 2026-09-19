# Kafka Partition Verification

**Status:** done
**Blocked by:** —
**Branch:** `feature/kafka-partition-verification`

---

## Context

Topics were created with 6 partitions in Phase 0 (`docker/topics.yaml`). Six was chosen deliberately so this verification step is a check, not a change — altering partition count rehashes every key and loses per-key ordering.

## What this builds

A measurement: verify that key distribution across the 6 partitions is not pathological. If distribution is genuinely skewed, record the measurement in `DECISIONS.md` and stop. Do not repartition without deciding it is worth losing per-key ordering.

## Out of scope

Repartitioning (only if measurement shows it's necessary and the ordering trade-off is accepted). Kafka Streams (separate conditional spec).

## Constraints

- This is a check, not a change. The default outcome is "distribution is acceptable, no action."
- If repartitioning is undertaken: `test_repartitioning_preserves_per_key_ordering` is required.

## Required tests

- `test_key_distribution_across_partitions` — asserts that no single partition holds more than an acceptable skew fraction of messages

## Definition of done

```bash
cd services/ingestion-scraper && uv run pytest tests/integration/test_partition_distribution.py -v -m integration
```

Expected: 1 passed. Measurement recorded in `DECISIONS.md`.

# Point-in-Time Alignment

**Status:** ready
**Blocked by:** —
**Branch:** `feature/point-in-time-alignment`

---

## Context

`services/backtesting/` exists after the price ingestion spec. Signals and corroborations have a `published_date` and `corroborated_at` respectively. Price series are stored as Parquet in MinIO. This spec builds the join layer that aligns signals to price windows without look-ahead bias.

## What this builds

An alignment module that joins signal/corroboration records to price windows using only public timestamps. Rejects any attempt to join on a non-public timestamp. The output is an aligned dataset ready for the backtesting spec.

**Correct timestamps to use:**
- Signals: `published_date`
- Corroborations: `corroborated_at` (latest participant publication date — not `first_detected_at`, not `retrieved_at`, not `ingested_at`)
- Patents: pre-grant publication date (A1 `date_published`) — NOT `filing_date`
- Clinical trials: `studyFirstPostDateStruct.date` or `lastUpdatePostDateStruct.date` — NOT `first_submitted_date`

Signals published after market close align to the next trading session. Signals on market holidays align to the next trading day.

## Out of scope

Backtest calculations, performance metrics. This spec only produces the aligned dataset.

## Constraints

- Read-only — reads MinIO snapshots, reads from Postgres/Neo4j. Writes nothing.
- `retrieved_at`, `ingested_at`, `first_detected_at` must never appear in a join condition. The module should raise explicitly if one is attempted.
- Superseded corroborations are evaluated with their own participant set, not the latest superseding set.

## Required tests

- `test_signal_excluded_from_price_window_predating_disclosure`
- `test_corroboration_aligns_to_corroborated_at_not_first_detected_at`
- `test_superseded_corroboration_uses_its_own_participant_set_not_the_latest`
- `test_patent_aligns_to_publication_date_not_filing_date` — fixture with 18-month gap
- `test_trial_aligns_to_post_date_not_submission_date`
- `test_retrieved_at_far_later_than_published_date_uses_published_date`
- `test_backfilled_document_does_not_leak_into_an_earlier_window`
- `test_join_attempt_using_ingested_at_raises`
- `test_signal_published_after_market_close_aligns_to_next_session`
- `test_signal_on_market_holiday_aligns_to_next_trading_day`

## Definition of done

```bash
cd services/backtesting && uv run pytest tests/unit/test_alignment.py -q
```

Expected: 10+ passed.

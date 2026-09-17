# Watchlist & Alerts

**Status:** draft
**Blocked by:** —
**Branch:** `feature/watchlist-alerts`

---

## Context

`core-hub` publishes to `auspex.signals.corroborated`. The health reporter (§12 of `docs/requirements.md`) is not yet wired. This spec adds a watchlist and notification system to `core-hub`.

## What this builds

- A ticker/gene-target watchlist checked against new corroborated signals
- Notifications on new corroborated signals matching the watchlist (transport TBD — Discord, Slack, or email)
- Health reporting wired to the same transport: DLT depth and per-source age-of-latest-signal

The same corroboration notifies exactly once — including after a re-extraction that changes `extraction_id` but not `event_id`. Supersession produces one notification for the new evidence, not another for the old.

## Out of scope

Dashboard visualisation (separate spec). Rate-of-change alerts, price alerts.

## Constraints

- Notification deduplication on `event_id`, not `extraction_id`.
- Transport failure: retry then log — never block the corroboration pipeline.
- DLT depth threshold must be configurable.

## Required tests

- `test_matching_signal_triggers_notification` — stubbed transport
- `test_non_matching_signal_does_not_notify`
- `test_same_corroboration_notifies_once_after_reextraction`
- `test_supersession_notifies_once_for_new_evidence_not_again_for_old`
- `test_notification_transport_failure_is_retried_then_logged`
- `test_dlt_depth_above_threshold_notifies`

## Definition of done

Suite passes and a test watchlist entry triggers a real notification within one polling cycle.

## Notes

Needs scoping before `ready`: which transport(s) to support? What's the watchlist storage model — config file, DB table, or Airflow Variable? What are the health thresholds?

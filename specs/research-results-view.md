# Research Results View

**Status:** draft
**Blocked by:**
1. The strategy direction decision (scoping PR #19: event-driven signals vs a slow monthly score held as a long-only basket). The shapes below are deliberately strategy-agnostic, but the first results to show depend on it.
2. Producers of the results: `specs/forward-paper-trading.md` (paper ledger). The evaluation report and verdicts (EVA-019, EVA-024), the runtime's books (STR-027) and the decision traces (STR-058, `specs/done/decision-trace.md`) already exist; none defines a read API.
3. `specs/lineage-trace-view.md` (the trace page this view extends).
**Branch:** `feature/research-results-view`
**Docs impact:** `DSH-new` ([docs/dashboard.md](../docs/dashboard.md)): the `/research` overview and per-strategy pages. `STR-new` ([docs/strategy/runtime.md](../docs/strategy/runtime.md)): the strategy-agnostic results read API and the decision references. Uses EVA-006, EVA-019, EVA-024 and EVA-027 (`docs/research/evaluation-protocol.md`).

---

## Context

Decided 2026-10-08: the dashboard is where the user sees whether Auspex works: backtest results against the pre-registered kill criteria, forward paper trading per capital tier, and the decisions behind each trade, traced back to the documents. Today all of these are, or will be, written to MinIO by Python services and read only by scripts (`scripts/paper_report.py`, the evaluation report). The user does not run scripts by hand.

Planned writers and stores:
- Evaluation protocol: a per-hypothesis report with kill-criteria verdicts, clustered t, deflated Sharpe, holdout status.
- Strategy runtime and forward paper trading: `PaperLedger` Parquet per NYSE session (intents, fills, exits, marks, heartbeats, per capital tier), `VirtualBook` per strategy and mode; gap gauges in Prometheus.
- Decision trace: append-only `TraceRecord` JSONL under `strategy/traces/<strategy>/<mode>/`, one `event_id` per trace.

## What this builds

To be confirmed at scoping.

1. **One strategy-agnostic read API** in the strategy service over MinIO, with generic resources: `GET /strategies` (name, version, mode, status, hypothesis id and hash), `GET /strategies/{name}/{version}/{mode}/runs` (backtest and evaluation runs with their verdicts), `.../ledger?from=&to=&tier=`, `.../metrics` (with `n` beside every statistic), `.../traces`. Strategy-specific fields travel as an `attributes` map, so no endpoint is shaped around one hypothesis.
2. **Decision references for lineage:** the strategy runtime publishes a small reference per decision (trace id, strategy name and version, mode, corroboration key or document key, intent id, ticker, direction, outcome, `attributes`) on a new topic, and core-hub stores it so the trace view's "Decisions" section can show it. The topic follows the DLT rules (Invariant 11).
3. **Dashboard:** `/research` overview (each hypothesis: kill-criteria status, forward-check verdict per tier, ledger gaps); per-strategy pages for runs, ledger with P&L per tier, and metrics; decisions appear in `/trace`.

## Out of scope

- Computing any statistic in the dashboard or the BFF. The API is the computation boundary (as `specs/done/strategy-metrics.md` already states).
- Editing hypotheses or strategies (locked; `specs/ingestion-config-ui.md` shows them read-only).
- Live trading controls.

## Constraints

- Invariant 2: the strategy service writes no database; core-hub stores decision references from the topic.
- EVA-006, EVA-019, EVA-024 and EVA-027: results are shown against the locked `protocol.yaml`; the view never recomputes a verdict with different thresholds.
- STR-033: every statistic carries its `n`; an insufficient sample shows "insufficient", never a number.

## Required tests

Provisional; confirm at scoping.

- `test_strategy_list_includes_hypothesis_hash_and_status`
- `test_ledger_endpoint_filters_by_tier_and_session_range`
- `test_metrics_without_n_are_rejected_by_the_response_model`
- `test_insufficient_sample_is_returned_as_insufficient_not_a_number`
- `test_strategy_specific_fields_are_returned_in_attributes`
- `test_decision_reference_is_stored_by_core_hub_and_shown_in_the_trace`
- `test_malformed_decision_reference_goes_to_the_dlt_with_headers`
- `test_research_overview_shows_kill_criteria_and_verdict_per_tier`
- `test_dashboard_renders_insufficient_instead_of_a_statistic`

## Definition of done

To be written at scoping, once the strategy direction is settled and the producer specs fix their output formats.

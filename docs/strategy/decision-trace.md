# Decision trace

Domain: STR · Code: `services/strategy/src/auspex_strategy/trace/`, `services/strategy/src/auspex_strategy/runtime/engine.py` · Last reviewed against: develop @ `b7582c3`

## Scope

The chain of custody for each trading decision: the `TraceRecord` of a risk-reviewed intent, from its raw documents through extraction, corroboration, strategy and risk to fill and P&L; the one validator; the append-only `TraceStore`; deterministic intent ids; and the replay that reproduces a trace.

Only backtest replays are traced today. The streaming runtime has no tracer (STR-061), so a paper decision leaves no trace.

Not in this file: the risk checks a trace records ([risk.md](risk.md)); the runtime and its books ([runtime.md](runtime.md)); the raw archive and extraction records a trace points to ([contracts.md](../system/contracts.md)).

## Requirements

- <a id="STR-055"></a>**STR-055** — Every risk-reviewed intent of a `paper`-or-above strategy has one `TraceRecord` holding: one `DocumentRecord` per participant of the corroboration (`event_id`, `raw_object_key`, `extraction_id`, extraction model, prompt and prefilter versions, `extracted_at`); the corroboration key `(entity_key, participants_hash)` with `corroborated_at` and the source types; the strategy's name, version, code hash and hypothesis, `as_of`, `intent_id` and rationale; the risk checks in run order with the outcome, the rejection or pause reason, overlaps and netting; the sizing and approval; and the execution, position and P&L fields, empty until a fill is traced. `research` strategies never reach risk and are not traced.
- <a id="STR-056"></a>**STR-056** — A `DocumentRecord`'s `extracted_at` is nullable and the validator does not require it, because the corroborated event does not carry it yet.
- <a id="STR-057"></a>**STR-057** — One validator applies to backtest, paper and live traces. It names every missing field, a participant's as `documents[i].<field>`, and requires the shares of an approved intent, the rejection reason of a rejected one and the pause reason of a paused one.
- <a id="STR-058"></a>**STR-058** — `TraceStore` appends traces as JSON lines to `traces/<strategy>/<mode>/traces.jsonl` in the strategy bucket and never edits a line: a later stage of the same intent is a new line. It refuses an incomplete trace, so a decision from the pass-through stub (no risk checks) or an intent on an event without archived documents cannot be traced.
- <a id="STR-059"></a>**STR-059** — An intent's id is a UUIDv5, under one fixed namespace, of the strategy name and version, the corroboration's entity key, participants hash and `corroborated_at`, the `as_of` and the intent's position in the strategy's output, so replaying the same events names the same intents.
- <a id="STR-060"></a>**STR-060** — Replaying a backtest's events reproduces every field of its traces except `trace_id`, `approved_at` and `fill_time`.
- <a id="STR-061"></a>**STR-061** — Paper and live decisions are traced like backtest decisions.

## Verification

| ID | Source | Verified by | Status |
|---|---|---|---|
| STR-055 | `## 2026-10-11 — Decision trace — CHOICE — one document record per participant, deterministic intent ids, risk reviews per event` (items 1 and 4); `## 2026-09-20 — Strategy layer session 2 — FLAG — Corroboration surrogate key deferred; composite natural key in trace`; at-risk class #14; archived `specs/done/decision-trace.md` [`services/strategy/README.md`] | `services/strategy/tests/unit/test_decision_trace.py::test_every_intent_gets_a_trace_record`, `services/strategy/tests/unit/test_decision_trace.py::test_rejected_intent_trace_has_rejection_reason`, `services/strategy/tests/unit/test_decision_trace.py::test_netted_intent_trace_has_netted_into_reference` | `tested` |
| STR-056 | `## 2026-09-20 — Strategy layer session 2 — FLAG — extracted_at missing from ResearchSignalEvent (§10.2)` | `services/strategy/tests/unit/test_decision_trace.py::test_every_intent_gets_a_trace_record` validates traces whose documents have no `extracted_at` | `tested` |
| STR-057 | `## 2026-10-11 — Decision trace — CHOICE — one document record per participant, deterministic intent ids, risk reviews per event` (item 1); archived `specs/done/decision-trace.md` [`services/strategy/README.md`] | `services/strategy/tests/unit/test_decision_trace.py::test_trace_with_missing_extraction_id_fails_validation`, `services/strategy/tests/unit/test_decision_trace.py::test_trace_with_approved_approval_but_null_shares_fails_validation`, `services/strategy/tests/unit/test_decision_trace.py::test_backtest_paper_live_traces_pass_same_validator` | `tested` |
| STR-058 | `## 2026-10-11 — Decision trace — CHOICE — one document record per participant, deterministic intent ids, risk reviews per event` (item 4); archived `specs/done/decision-trace.md` [`services/strategy/README.md`] | `services/strategy/tests/unit/test_trace_components.py::test_trace_store_round_trips_and_filters_by_as_of`, `services/strategy/tests/unit/test_trace_components.py::test_trace_store_refuses_an_incomplete_trace`, `services/strategy/tests/unit/test_trace_components.py::test_intent_on_an_event_without_archived_documents_cannot_be_traced`, `services/strategy/tests/unit/test_trace_components.py::test_pass_through_risk_decisions_cannot_be_traced` | `tested` |
| STR-059 | `## 2026-10-11 — Decision trace — CHOICE — one document record per participant, deterministic intent ids, risk reviews per event` (item 2); at-risk class #14; archived `specs/done/decision-trace.md` [`services/strategy/README.md`, `services/strategy/src/auspex_strategy/runtime/engine.py`] | `services/strategy/tests/unit/test_strategy_runtime.py::test_backtest_replay_is_deterministic`, `services/strategy/tests/unit/test_decision_trace.py::test_replaying_backtest_produces_identical_non_time_fields` | `tested` |
| STR-060 | archived `specs/done/decision-trace.md` [`services/strategy/README.md`] | `services/strategy/tests/unit/test_decision_trace.py::test_replaying_backtest_produces_identical_non_time_fields`, `services/strategy/tests/unit/test_trace_components.py::test_backtest_replay_with_fills_traces_every_intent` | `tested` |
| STR-061 | archived `specs/done/decision-trace.md`; `## 2026-10-11 — Decision trace — CHOICE — one document record per participant, deterministic intent ids, risk reviews per event` (Action); `## 2026-10-10 — Strategy runtime — FLAG — the live data channel is not fully served by core-hub yet`; `## 2026-10-15 — Living docs — PENDING — defects found while scoping` (item E F3), answered by `## 2026-10-17 — Living docs — CHOICE — defects found while scoping` [`services/strategy/README.md`, `services/strategy/src/auspex_strategy/runtime/main.py`] | no production code constructs `DecisionTracer`; only `trace/replay.py` does. Paper tracing also needs core-hub to expose each participant's raw object key and extraction to the runtime | `divergent` |

## Known traps

- Wiring a tracer before the risk layer stops the run: the pass-through stub records no checks, so `TraceStore` refuses every trace (STR-058). The tracer follows STR-053 in [risk.md](risk.md), not the other way round.
- Catalyst holds are read from `risk/catalyst_holds.jsonl` in the strategy bucket, not from the trace, until the trace records them itself.

## Rationale

- The corroboration is keyed by `(entity_key, participants_hash)` because no surrogate id exists in the schema; adding one is a core-hub schema change (`## 2026-09-20 — Strategy layer session 2 — FLAG — Corroboration surrogate key deferred; composite natural key in trace`).
- Random intent ids made replay equality impossible, since overlap and netting references are not time fields (`## 2026-10-11 — Decision trace — CHOICE — one document record per participant, deterministic intent ids, risk reviews per event`, item 2).

## Retired requirements

None.

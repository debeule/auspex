# Decision Trace

**Status:** blocked
**Blocked by:**
1. Met: `specs/done/strategy-framework.md` — `TradeIntent`, `IntentRationale`, and `ApprovalDecision` must be defined
2. `specs/strategy-runtime.md` — runtime populates the trace as events flow through the pipeline

**Branch:** `feature/decision-trace`

---

## Context

The decision trace is a complete, immutable record of every decision path from raw document through to realised P&L. It serves two purposes: explainability (why did the system trade, or not trade?) and reproducibility (replay the archived data and verify the trace is identical). Backtest, paper, and live modes emit the same trace format.

`extracted_at` is not currently a field on `ResearchSignalEvent` (§10.2). The trace requires it. This is flagged in DECISIONS.md 2026-09-20; the extraction-backend spec must add this field before the full latency chain in the trace can be populated. Until then, `extracted_at` is nullable and backfilled when the field becomes available.

`corroboration_id` as a surrogate key is also flagged — see DECISIONS.md 2026-09-20.

## What this builds

### `services/strategy/src/auspex_strategy/trace/`

**`TraceRecord`** — frozen dataclass, the full decision chain:

```python
@dataclass(frozen=True)
class TraceRecord:
    trace_id: UUID           # generated at trace creation
    mode: TraceMode          # BACKTEST | PAPER | LIVE

    # Raw document chain
    raw_object_key: str      # MinIO key; enough to re-fetch and re-extract

    # Extraction chain
    event_id: UUID
    extraction_id: UUID
    extraction_model: str
    prompt_version: str
    prefilter_version: str
    extracted_at: datetime | None   # nullable until extraction-backend adds this field

    # Corroboration chain
    entity_key: str
    participants_hash: str          # (entity_key, participants_hash) is the corroboration key
    corroborated_at: datetime
    source_types: tuple[str, ...]

    # Strategy chain
    strategy_name: str
    strategy_version: str
    strategy_code_hash: str
    hypothesis_id: str
    as_of: datetime                 # known-at time at which decide() was called
    intent_id: UUID
    rationale: dict                 # structured IntentRationale as a dict for immutability

    # Risk chain (ordered list; first failure short-circuits)
    risk_checks: tuple[RiskCheckRecord, ...]  # each: check_name, inputs_snapshot, passed
    final_approval: ApprovalStatus  # APPROVED | REJECTED | PAUSED

    # Rejection / pause chain (populated when final_approval != APPROVED)
    rejection_reason: str | None
    rejection_check_name: str | None
    is_paused: bool
    pause_reason: str | None

    # Overlap flag
    overlaps_with_intent_ids: tuple[UUID, ...]  # empty if no overlap

    # Netting flag
    is_netted: bool
    netted_into_intent_id: UUID | None

    # Sizing chain (populated when APPROVED)
    kelly_inputs: dict | None       # p_estimate, b_estimate, shrinkage_factor
    shares_proposed: int | None

    # Approval chain (populated when APPROVED)
    approved_at: datetime | None
    approved_by: str | None         # "auto" for live-auto; user identifier for live-confirm

    # Execution chain (populated post-fill)
    order_id: str | None
    order_submitted_at: datetime | None
    fill_price_usd: float | None
    fill_time: datetime | None

    # Position chain
    entry_date: date | None
    exit_date: date | None
    exit_reason: str | None

    # P&L chain
    gross_pnl_usd: float | None
    total_costs_usd: float | None
    net_pnl_eur: float | None
    estimated_tax_eur: float | None  # 0.0 until session 3 adds tax computation
```

**`RiskCheckRecord`** — within `risk_checks`:
```python
@dataclass(frozen=True)
class RiskCheckRecord:
    check_name: str        # e.g. "KILL_SWITCH", "GROSS_EXPOSURE"
    inputs_snapshot: dict  # parameter values at time of check; required for reproducibility
    passed: bool
```

**`TraceStore`**
- Append-only JSONL storage in MinIO: `strategy/traces/<strategy_name>/<mode>/traces.jsonl`
- `TraceStore.append(record: TraceRecord)` — serialises to JSON line; never edits existing lines
- `TraceStore.read(strategy_name, mode, since=None) → Iterator[TraceRecord]`

**`TraceValidator`**
- `TraceValidator.validate(record: TraceRecord) → None` — raises `TraceIncompleteError(missing_fields)` if:
  - Any of `raw_object_key, event_id, extraction_id, entity_key, corroborated_at, strategy_name, strategy_version, strategy_code_hash, hypothesis_id, as_of, intent_id` is null or empty
  - `risk_checks` is empty (at minimum the kill-switch check must always run)
  - `final_approval = APPROVED` but `shares_proposed` is null
  - `final_approval = REJECTED` but `rejection_reason` is null

**`TraceReplayer`**
- `TraceReplayer.replay(events: list[CorroborationRecord], strategy, risk_manager_stub) → list[TraceRecord]`
- Given the same archived events, produces traces where all fields except `trace_id` (always a fresh UUID), `approved_at`, and `fill_time` are identical to the original run. Verifies this by comparing field-by-field on all non-time fields.

### Rejected, filtered, paused, and netted decisions

Every `TradeIntent` produced by `decide()` gets a `TraceRecord`, regardless of whether it ends up filled. The `final_approval` field records the outcome:
- `REJECTED`: risk check failed; `rejection_reason` and `rejection_check_name` populated
- `PAUSED`: strategy was health-gated; `is_paused = True, pause_reason` populated
- `APPROVED` + `is_netted = True`: intent was netted against an opposing intent before order submission; `netted_into_intent_id` points to the surviving intent

"Why didn't it trade?" is always answerable from the trace.

## Out of scope

UI for trace exploration (session 3). Tax computation beyond the placeholder field. Broker order traces (execution chain fields remain null until session 3). Trace deletion or editing.

## Constraints

- `TraceRecord` is frozen. The only valid mutation is appending to `TraceStore` — never updating an existing line.
- `raw_object_key` must be present on every trace. A strategy that fires on an event without a `raw_object_key` in the corroboration record cannot be traced and should not run (the chain of custody is broken).
- Backtest, paper, and live traces are stored in separate JSONL files (different `mode` paths in MinIO) but validated by the same `TraceValidator`.
- `pytest-socket --disable-socket` across unit tests.
- Invariant 6: MinIO credentials from `.env`.

## Required tests

In `tests/unit/test_decision_trace.py`:

- `test_every_intent_gets_a_trace_record` — process three intents (one approved, one rejected, one paused) through a synthetic pipeline; `TraceStore` contains exactly three records; all pass `TraceValidator`
- `test_trace_with_missing_extraction_id_fails_validation` — construct `TraceRecord` with `extraction_id = None`; `TraceValidator.validate()` raises `TraceIncompleteError` naming `extraction_id`
- `test_trace_with_approved_approval_but_null_shares_fails_validation` — `final_approval = APPROVED, shares_proposed = None`; validation raises
- `test_replaying_backtest_produces_identical_non_time_fields` — replay same 5-event sequence twice; for each trace pair, all fields except `trace_id`, `approved_at`, `fill_time` are equal
- `test_rejected_intent_trace_has_rejection_reason` — intent rejected by `GROSS_EXPOSURE` check; `TraceRecord.rejection_reason` is non-empty; `rejection_check_name = "GROSS_EXPOSURE"`
- `test_netted_intent_trace_has_netted_into_reference` — two opposing intents netted; both `TraceRecord`s have `is_netted = True`; one has `netted_into_intent_id` pointing to the other's `intent_id`
- `test_backtest_paper_live_traces_pass_same_validator` — construct one synthetic trace per mode; all three pass `TraceValidator.validate()` without modification

## Definition of done

```bash
cd services/strategy && uv run pytest tests/unit/test_decision_trace.py -q
```

Expected: 7 passed.

Then: a `BacktestReplayRunner` run (from strategy-runtime spec) with decision-trace wired produces a `TraceStore` with at least one valid `TraceRecord` per intent. `TraceValidator` passes on all records in the store.

## Notes

**`extracted_at` field gap**: `ResearchSignalEvent` does not currently have `extracted_at`. This field is needed to populate the latency chain from extraction to intent. When the extraction-backend spec is implemented, `extracted_at` should be added to `ResearchSignalEvent` (§10.2) and to the Pydantic model and Java record (triggering a contract fixture regeneration). Until then, `extracted_at` in the trace is null. DECISIONS.md 2026-09-20 flags this.

**Corroboration reference**: traces reference a corroboration via `(entity_key, participants_hash)` — the composite natural key. If a surrogate `corroboration_id` is added to the schema (see DECISIONS.md 2026-09-20 flag), replace with the surrogate. Until then, the composite key is sufficient for trace reproduction.

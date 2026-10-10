# Forward-check input validation

**Status:** ready
**Branch:** `feature/forward-check-input-validation`

---

## Context

`services/backtesting/src/auspex_backtesting/protocol.py` applies the registered portfolio forward check (`config/hypotheses/protocol.yaml`, `kill_criteria` → `forward_check` → `portfolio`) to one capital tier with `evaluate_portfolio_forward_check(record, protocol)`. `PortfolioForwardRecord` carries the paper and replay monthly net excess returns as two plain sequences, the ledger gap sessions, and the in-sample mean and standard error. The function checks that the two sequences have the same length, then compares the tracking difference and the paper mean with the registered bounds. Its only callers today are the tests in `test_preregistered_protocol.py`; the forward paper ledger (`specs/forward-paper-trading.md`) will be the real one.

Found by the consolidated audit of 2026-10-10 (finding C6; the audit file is in the project's `audit/` folder) and checked against `develop` at `d615504`:

1. **NaN and infinity pass.** Every comparison with NaN is false, so a ledger with an all-NaN or one-NaN month, or an infinite return, reports `pass`. The audit reproduced all three with the exact functions.
2. **Months are not identified.** Two sequences of the same length pass the length check even when they cover different or shifted months, or repeat one.
3. **A negative standard error is accepted** and moves the bound the wrong way.

This is a helper defect: no forward check has run, and no verdict needs recomputing.

## What this builds

- **Monthly returns keyed by month.** `PortfolioForwardRecord.paper_monthly_net_excess` and `replay_monthly_net_excess` become `Mapping[str, float]` keyed by `YYYY-MM`.
- **Invalid input is its own verdict.** `ForwardCheckVerdict.status` gains `"invalid"`, decided before anything else. Its `reasons` name each problem: `non_finite_return` (with the months), `non_finite_in_sample`, `negative_standard_error`, `month_mismatch` (months in one ledger but not the other), `malformed_month` (a key that is not `YYYY-MM`), `months_not_consecutive` (a missing month inside the range). An invalid record is never `pass`, `fail` or `insufficient`; the economic comparison does not run.
- Valid finite records get the same `pass`, `fail` and `insufficient` outcomes as today.

## Out of scope

- The trial ledger, holdout handling and any other part of the research executor.
- Any change to the registered thresholds or to `protocol.yaml`.
- Per-month readiness evidence beyond the existing `ledger_gap_sessions` and `is_data_gap`.

## Constraints

- The registered `protocol.yaml` is untouched, so its registration hash still verifies.
- `"invalid"` is not a kill: it means the record could not be evaluated. The forward paper ledger must treat it as a data problem to fix, not as a verdict on the strategy.

## Required tests

Unit (`services/backtesting/tests/unit/test_preregistered_protocol.py`):
- `test_forward_check_with_an_all_nan_ledger_is_invalid`
- `test_forward_check_with_one_nan_month_is_invalid` — reason `non_finite_return` names that month
- `test_forward_check_with_an_infinite_return_is_invalid` — both `+inf` and `-inf`
- `test_forward_check_with_non_finite_in_sample_values_is_invalid`
- `test_forward_check_with_a_negative_standard_error_is_invalid`
- `test_forward_check_with_shifted_months_is_invalid` — paper 2027-01..2027-12, replay 2027-02..2028-01: `month_mismatch`
- `test_forward_check_with_a_missing_month_inside_the_range_is_invalid` — `months_not_consecutive`
- `test_forward_check_with_a_malformed_month_key_is_invalid`
- The existing forward-check tests keep their outcomes with month-keyed records (finite passing and failing controls).

## Definition of done

```bash
cd services/backtesting && uv run pytest tests/unit/test_preregistered_protocol.py -q
cd services/backtesting && uv run pytest tests/unit -q
cd services/backtesting && uv run ruff check . && uv run mypy src
```

Expected: the 8 new tests pass alongside the existing ones; no failures.

## Notes

- A duplicate month cannot be represented in a mapping, which is why the keys replace the sequences rather than a separate list of months.

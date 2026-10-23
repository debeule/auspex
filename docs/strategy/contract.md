# Strategy contract

Domain: STR · Code: `services/strategy/src/auspex_strategy/abc.py`, `services/strategy/src/auspex_strategy/models.py`, `services/strategy/src/auspex_strategy/registry.py`, `services/strategy/src/auspex_strategy/runtime/context.py`, `services/strategy/src/auspex_strategy/runtime/slots.py`, `services/strategy/src/auspex_strategy/strategies/` · Last reviewed against: develop @ `b7582c3`

## Scope

What a strategy is and what it may see: the `Strategy` interface, the `AsOfContext` data channel and its look-ahead rules, the strategy registry, versioning, the lifecycle statuses and the `TradeIntent` a strategy returns.

Not in this file: how the runtime runs strategies, fills their intents and reports their metrics ([runtime.md](runtime.md)); sizing and risk checks ([risk.md](risk.md)); decision traces ([decision-trace.md](decision-trace.md)); the hypothesis files, their hash lock and the read-only research config ([evaluation-protocol.md](../research/evaluation-protocol.md)); what a backtest knows when ([backtesting.md](../research/backtesting.md)). Forward paper trading and live trading are not built; their specs (`specs/forward-paper-trading.md`, `specs/live-trading.md`) stay in `specs/` until then.

## Machine-readable authorities

- `config/strategies/registry.yaml` — one entry per strategy: `name`, `module`, `class`, `version`, `hypothesis_id`, `status`. This file names the keys and never copies an entry.
- `config/hypotheses/h*.yaml` — each strategy's parameters and its known-at delay (`primary_cell.known_at_delay_days`), locked by hash ([EVA-001](../research/evaluation-protocol.md#EVA-001)) and read-only outside the repository ([EVA-006](../research/evaluation-protocol.md#EVA-006)).

## Requirements

*The interface.*
- <a id="STR-001"></a>**STR-001** — A strategy subclasses `Strategy` and declares `name`, `version`, `hypothesis_id`, `description`, `subscriptions`, `declared_inputs` and `parameters()`. Its `decide()` is a pure function of the `AsOfContext` and the trigger it is given: no network, clock, randomness or shared state, so identical contexts give identical intents in a replay and in the runtime.
- <a id="STR-002"></a>**STR-002** — A strategy's parameters live only in its registered hypothesis file; no strategy parameter file redeclares a field of its hypothesis.

*The data channel.*
- <a id="STR-003"></a>**STR-003** — `AsOfContext` is the only data channel `decide()` has. A corroboration is known at its `corroborated_at` plus the strategy's known-at delay, read from the strategy's registered hypothesis (its primary cell's delay, or the single value the hypothesis lists), and the runtime runs `decide()` for an event as of that known-at time.
- <a id="STR-004"></a>**STR-004** — A record whose known-at time is after `as_of` is not returned by any context read: the production contexts drop such records when they are built, so no context returns a record past its known-at boundary.
- <a id="STR-005"></a>**STR-005** — A price read is allowed only for a session strictly before `as_of`'s date; a read of any later session, the `as_of` date's own close included, raises `PriceLookAheadError`.
- <a id="STR-006"></a>**STR-006** — No context method exposes a record's processing time (`ingested_at`, `extracted_at`): as-of decisions use only publication or corroboration time plus the known-at delay. The backtest aligner states the same rule for its own mechanism in [RES-067](../research/backtesting.md#RES-067).
- <a id="STR-007"></a>**STR-007** — A replay and the streaming runtime expose the same signals to a strategy.

*The registry.*
- <a id="STR-008"></a>**STR-008** — Every registered strategy names a hypothesis registered in `config/hypotheses/registry.jsonl`; loading the registry with an unregistered `hypothesis_id` raises `HypothesisNotRegisteredError`.
- <a id="STR-009"></a>**STR-009** — There is one strategy per tradeable hypothesis.
- <a id="STR-010"></a>**STR-010** — Adding a strategy needs only its module and a registry entry: the contract suite discovers every registered strategy and runs its `decide()`.
- <a id="STR-011"></a>**STR-011** — A `retired` strategy stays listed in the registry and raises `StrategyRetiredError` when `decide()` is called.
- <a id="STR-012"></a>**STR-012** — A strategy version is bound to the hash of its module's source and of its parameters file; a change to either without a version bump is refused when the registry loads, in production as in tests.

*Lifecycle and intents.*
- <a id="STR-013"></a>**STR-013** — A strategy's status is one of `draft`, `research`, `paper`, `live-confirm`, `live-auto` (in that order) or `retired`; `draft` and `retired` strategies never run in the runtime.
- <a id="STR-014"></a>**STR-014** — `live-confirm` and `live-auto` are reserved: no broker exists, so a strategy at either status trades only virtual books. Live trading is `specs/live-trading.md`.
- <a id="STR-015"></a>**STR-015** — A `TradeIntent` carries the ticker, direction, conviction, holding rule (`FixedDays`, `ExitOnSignal` or `StopLossPct`), exit conditions, a rationale naming the corroboration, its entity key, source types and `as_of`, and the strategy's name, version and hypothesis. `StopLossPct` is in percent (10.0 is a 10% stop).

## Verification

| ID | Source | Verified by | Status |
|---|---|---|---|
| STR-001 | archived `specs/done/strategy-framework.md` [`services/strategy/src/auspex_strategy/abc.py`] | `services/strategy/tests/unit/test_strategy_framework.py::test_contract_suite_auto_discovers_all_registered_strategies`, `services/strategy/tests/unit/test_strategy_framework.py::test_decide_is_deterministic_given_identical_context` | `tested` |
| STR-002 | `## 2026-10-10 — Single-source cleanup — CHOICE — one version of each pre-rollout artifact`; `## 2026-10-10 — Strategy runtime — CHOICE — state placement, timing and the pass-through stub` (item 2) | `services/strategy/tests/unit/test_strategy_framework.py::test_strategy_parameter_files_do_not_redeclare_hypothesis_fields` | `tested` |
| STR-003 | `## 2026-10-10 — Strategy runtime — CHOICE — state placement, timing and the pass-through stub` (item 2); archived `specs/done/strategy-framework.md` [`services/strategy/README.md`, `services/strategy/src/auspex_strategy/runtime/slots.py`] | `services/strategy/tests/unit/test_runtime_components.py::test_known_at_delay_comes_from_the_registered_hypothesis` | `tested` |
| STR-004 | `## 2026-10-17 — Living docs — CHOICE — as-of reads hide or raise` (option A: hiding is the approved behaviour; the docstring is fixed later), answering `## 2026-10-15 — Living docs — PENDING — as-of reads hide or raise`; archived `specs/done/strategy-framework.md` [`services/strategy/src/auspex_strategy/abc.py`, `services/strategy/src/auspex_strategy/runtime/context.py`] | `services/strategy/tests/unit/test_runtime_components.py::test_backtest_context_hides_records_not_yet_known` | `tested` |
| STR-005 | archived `specs/done/strategy-framework.md` (a strategy cannot request data from the future) [the `price` read in `context.py`, `services/strategy/src/auspex_strategy/runtime/context.py`] | `services/strategy/tests/unit/test_runtime_components.py::test_backtest_context_refuses_a_close_that_is_not_final` | `tested` |
| STR-006 | `## 2026-09-20 — Strategy layer session 2 — CHOICE — Strategies never see ingested_at or extracted_at; InputHealthMonitor handles model downtime`; `## 2026-10-17 — Living docs — CHOICE — processing time in as-of decisions` (option A, adopted: the cutover writes the rule as the sixteenth invariant); at-risk class #4 (STR/RES side) [`services/strategy/src/auspex_strategy/abc.py`] | `AsOfContext` declares no method that returns either timestamp; no test asserts it | `untested` |
| STR-007 | `## 2026-10-23 — Living docs — PENDING — strategy-and-dashboard ratification batch` [`services/strategy/src/auspex_strategy/runtime/replay.py`, `services/strategy/src/auspex_strategy/runtime/context.py`]: a replay passes the signals it was given, the streaming runtime passes none, and signals are filtered on `published_at` with no known-at delay | — | `pending-decision` |
| STR-008 | archived `specs/done/strategy-framework.md` | `services/strategy/tests/unit/test_strategy_framework.py::test_unregistered_hypothesis_id_raises_at_construction` | `tested` |
| STR-009 | archived `specs/done/strategy-framework.md`; `## 2026-10-10 — Single-source cleanup — CHOICE — one version of each pre-rollout artifact` (the H8 strategy deleted) | `services/strategy/tests/unit/test_strategy_framework.py::test_registry_lists_one_strategy_per_tradeable_hypothesis` | `tested` |
| STR-010 | archived `specs/done/strategy-framework.md` | `services/strategy/tests/unit/test_strategy_framework.py::test_adding_strategy_requires_no_change_outside_module_and_registry`, `services/strategy/tests/unit/test_strategy_framework.py::test_contract_suite_auto_discovers_all_registered_strategies` | `tested` |
| STR-011 | archived `specs/done/strategy-framework.md` | `services/strategy/tests/unit/test_strategy_framework.py::test_retired_strategy_decide_raises`, `services/strategy/tests/unit/test_strategy_framework.py::test_retired_strategy_remains_in_registry` | `tested` |
| STR-012 | archived `specs/done/strategy-framework.md`; `## 2026-10-15 — Living docs — PENDING — defects found while scoping` ("production `load_registry` passes no `versions_dir`"), answered by `## 2026-10-17 — Living docs — CHOICE — defects found while scoping` [`services/strategy/src/auspex_strategy/runtime/main.py`] | `services/strategy/tests/unit/test_strategy_framework.py::test_parameter_change_without_version_bump_raises` and `services/strategy/tests/unit/test_strategy_framework.py::test_strategy_without_parameters_file_versions_on_code_hash` pass a `versions_dir`; `load_registry` in `services/strategy/src/auspex_strategy/runtime/main.py` passes none, so production never checks | `divergent` |
| STR-013 | archived `specs/done/strategy-framework.md` (status meanings) [`services/strategy/src/auspex_strategy/runtime/slots.py`] | `services/strategy/tests/unit/test_strategy_runtime.py::test_research_strategy_does_not_run_in_streaming_mode` covers `research`; nothing tests `draft`, `retired` or the order of the two live statuses | `untested` |
| STR-014 | `## 2026-10-23 — Living docs — PENDING — strategy-and-dashboard ratification batch` [`services/strategy/src/auspex_strategy/runtime/slots.py`, `services/strategy/src/auspex_strategy/runtime/book.py`]: both statuses map to virtual books filled by `PaperBroker`, and `BookMode.LIVE` is unused | — | `pending-decision` |
| STR-015 | archived `specs/done/strategy-framework.md`; `## 2026-10-11 — Portfolio and risk — CHOICE — catalyst and short-interest sources, units and check order` (item 6) [`services/strategy/src/auspex_strategy/models.py`] | `services/strategy/tests/unit/test_runtime_components.py::test_stop_loss_exits_at_the_market_simulation_stop_fill` | `tested` |

## Known traps

- The `AsOfContext` docstring in `services/strategy/src/auspex_strategy/abc.py` still says implementations raise `AsOfViolationError` on a read past the boundary. That is stale: the production contexts drop unknown records when they are built (STR-004), so the raise in `corroborations()` cannot fire, and only `StubAsOfContext` in `services/strategy/src/auspex_strategy/testing.py` raises, for the framework's two raise tests. A fix spec corrects the docstring under `## 2026-10-17 — Living docs — CHOICE — defects found while scoping`.
- With `versions_dir` set, the version check writes `config/strategies/versions/<name>/<version>.json` on first use. The runtime mounts `config/strategies` read-only and [EVA-006](../research/evaluation-protocol.md#EVA-006) forbids runtime writes to research config, so closing STR-012 cannot simply pass `versions_dir` in production.
- The live context holds only the corroborations the runtime has consumed, so after a restart its history starts at the checkpoint ([runtime.md](runtime.md)).

## Rationale

- Hiding rather than raising: a context built from records the caller already holds is cheaper and cannot be misused by a strategy, and `## 2026-10-17 — Living docs — CHOICE — as-of reads hide or raise` approved it.
- Processing time stays out of the channel because a strategy could otherwise infer ingestion speed from timestamp proximity and trade on information that was not public.

## Retired requirements

None.

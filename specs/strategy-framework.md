# Strategy Framework

**Status:** ready
**Branch:** `feature/strategy-framework`

---

## Context

`services/strategy/` is a new Python service (see DECISIONS.md 2026-09-20 — placement flag). The backtesting module (`services/backtesting/`) already has price ingestion, alignment, market simulation, and evaluation protocol. The strategy service imports those as a path dependency (uv workspace or local editable install) rather than duplicating them.

The hypothesis registry (`specs/hypothesis-registry.md`) must be populated with H1–H8 YAML files before the seed strategy stubs can run against real hypothesis IDs. Unit tests use synthetic YAML fixtures and do not depend on hypothesis-registry being done first.

## What this builds

The plugin contract. When this spec is done:
- A `Strategy` ABC that every trading strategy implements.
- An `AsOfContext` that is the only data channel a strategy may read.
- A `TradeIntent` dataclass that is the only output a strategy may produce.
- A `StrategyRegistry` that loads `config/strategies/registry.yaml` and validates each entry.
- A contract test suite (`tests/unit/test_strategy_framework.py`) that auto-discovers every registered strategy and runs the full suite against it.
- Eight seed strategy stub modules (`auspex_strategy/strategies/h1_structural_convergence.py` through `h8_negative_asymmetry.py`) with class definitions only — no decision logic — to prove the interface accommodates all eight hypothesis patterns.

### Package placement

`services/strategy/src/auspex_strategy/` — see DECISIONS.md 2026-09-20 for the placement decision and alternatives.

### `Strategy` ABC

```python
class Strategy(ABC):
    name: str           # unique, stable identifier
    version: str        # "1.0", "1.1"; any logic or parameter change requires a new version
    hypothesis_id: str  # must match an entry in config/hypotheses/registry.jsonl
    description: str

    @property
    @abstractmethod
    def subscriptions(self) -> frozenset[SubscriptionType]:
        """Which input triggers call decide(). CORROBORATION_NEW | CORROBORATION_SUPERSEDED
        | SIGNAL_NEW | PRICE_TICK | CALENDAR_TICK."""

    @property
    @abstractmethod
    def declared_inputs(self) -> frozenset[InputSource]:
        """For health gating. CORROBORATION_STORE | PRICE_DATA | GRAPH_QUERY
        | EXTRACTION_MODEL."""

    @abstractmethod
    def decide(self, context: AsOfContext, trigger: Trigger) -> list[TradeIntent]:
        """Pure, deterministic, side-effect-free. No network, no clock, no random."""

    @classmethod
    @abstractmethod
    def parameters(cls) -> StrategyParameters:
        """Loaded from config/strategies/<name>.yaml, validated on registry load."""
```

At construction time `StrategyRegistry` verifies:
- `hypothesis_id` is present in `config/hypotheses/registry.jsonl`.
- `version` concatenated with `name` maps to a stored `(code_hash, parameters_hash)` in `config/strategies/versions/<name>/<version>.json`. If the entry is absent, it is written on first use. If it is present and the current hashes differ, `VersionConflictError` is raised — changing logic or parameters requires bumping `version`.

### `AsOfContext`

The only data channel available to `decide()`. All methods enforce the as-of boundary:

```python
class AsOfContext:
    as_of: datetime  # known-at time = corroborated_at + KNOWN_AT_DELAY_DAYS (business days)

    def corroborations(self, *, ticker: str | None = None,
                       entity_key: str | None = None,
                       min_source_count: int = 2) -> list[CorroborationRecord]: ...

    def signals(self, *, entity_key: str | None = None,
                source_type: str | None = None) -> list[SignalRecord]: ...

    def price(self, ticker: str, date: date) -> float: ...

    def prior_corroborations(self, ticker: str, entity_key: str) -> int:
        """Count of corroborations for (ticker, entity_key) before as_of."""

    def is_trading_day(self, date: date) -> bool: ...
```

Any method call where the earliest matching record has `corroborated_at + KNOWN_AT_DELAY_DAYS > as_of` raises `AsOfViolationError`. This makes look-ahead impossible by construction. The constraint applies in both directions: a strategy cannot request data from the future, and cannot request data that was published but whose `known-at` time is still in the future relative to `as_of`.

`AsOfContext` is an abstract base class with two concrete implementations injected by the runtime:
- `BacktestAsOfContext` — reads from MinIO price Parquet + corroboration snapshot
- `LiveAsOfContext` — calls core-hub REST API for corroborations; reads MinIO for prices

Strategies never import either concrete class.

### `TradeIntent`

```python
@dataclass(frozen=True)
class TradeIntent:
    intent_id: UUID                     # generated at construction
    ticker: str
    direction: Direction                # LONG | SHORT
    conviction: float                   # 0.0–1.0; feeds Kelly sizing
    holding_rule: HoldingRule           # FIXED_DAYS(n) | EXIT_ON_SIGNAL | STOP_LOSS_PCT(p)
    exit_conditions: tuple[ExitCondition, ...]
    rationale: IntentRationale          # structured: corroboration_id, entity_key, as_of,
                                        # source_types, directionality, confidence_scores used
    strategy_name: str
    strategy_version: str
    hypothesis_id: str
    as_of: datetime
```

### `config/strategies/registry.yaml` schema

```yaml
strategies:
  - name: structural_convergence
    module: auspex_strategy.strategies.h1_structural_convergence
    class: StructuralConvergenceStrategy
    version: "1.0"
    hypothesis_id: h1
    status: draft           # draft | research | paper | live-confirm | live-auto | retired
    parameters_file: config/strategies/structural_convergence.yaml
```

Status meanings:
- `draft`: code exists, no backtest run
- `research`: runs in backtest only; no virtual book
- `paper`: runs live on real corroboration events; virtual book; no real capital
- `live-confirm`: allocation applied; each intent requires explicit per-trade confirmation before order submission
- `live-auto`: allocation applied; intents execute automatically within risk limits
- `retired`: emits nothing; history and metrics preserved; wind-down configurable

### Seed hypothesis → strategy mapping

| Hypothesis | Class | Module | Notes |
|---|---|---|---|
| H1 | `StructuralConvergenceStrategy` | `h1_structural_convergence.py` | Long on entity-only corroboration; `holding_period_days` configurable |
| H2 | (H1 parameterization) | — | H2 tests multiple holding periods on H1 events; registered as separate H1 versions with different `holding_period_days` values, not a distinct strategy class |
| H3 | — | — | H3 is a diagnostic decomposition, not a trading strategy; it does not produce `TradeIntent`s. See Notes. |
| H4 | `DirectionalConvergenceStrategy` | `h4_directional_convergence.py` | H1 + requires matching directionality on both participants |
| H5 | `SourceCompositionStrategy` | `h5_source_composition.py` | H1 + filter on source_type pair; one registered version per tested pair |
| H6 | `GeneTargetNoveltyStrategy` | `h6_gene_target_novelty.py` | H1 + fires only on first (ticker, entity_key) corroboration within the data window |
| H7 | `ConfidenceGradientStrategy` | `h7_confidence_gradient.py` | H1 + requires mean confidence_score of participants above configurable threshold |
| H8 | `NegativeAsymmetryStrategy` | `h8_negative_asymmetry.py` | Short on negative-directionality corroboration pair; draft status until tax/borrow prerequisites resolved (PREREQUISITES.md) |

## Out of scope

Decision logic inside any strategy class. Risk checking, sizing, execution, virtual books (strategy-runtime spec). Metrics (strategy-metrics spec). Decision trace (decision-trace spec). Live order routing (session 3).

## Constraints

- `decide()` must be pure: no network calls, no clock access, no shared state, no randomness. `pytest-socket --disable-socket` enforces this.
- The `AsOfContext` is the only data access a strategy has. Importing `minio`, `psycopg`, or `neo4j` from a strategy module raises an ArchUnit-equivalent import check in CI.
- `TradeIntent` is frozen — immutable after construction.
- Invariant 6: no credentials in source. Strategy modules read only from `AsOfContext` and `StrategyParameters` (config).
- Invariant 8 (sync throughout): no `async`, no threads inside strategy modules.
- H3 does not produce `TradeIntent`s and does not subclass `Strategy`. It is an analysis script in `scripts/`, consistent with `evaluate_model.py`. This is the one hypothesis that does not map to the plugin contract; see Notes.

## Required tests

In `tests/unit/test_strategy_framework.py`:

- `test_contract_suite_auto_discovers_all_registered_strategies` — registry.yaml loaded; every entry is imported, instantiated with synthetic context, and runs all contract assertions; no manual list of strategy names in the test
- `test_adding_strategy_requires_no_change_outside_module_and_registry` — add `SyntheticTestStrategy` module + registry entry; run auto-discovery again; suite finds it without touching any existing file
- `test_as_of_context_raises_when_reading_beyond_as_of` — request corroboration with `corroborated_at + KNOWN_AT_DELAY_DAYS > as_of`; raises `AsOfViolationError`
- `test_as_of_context_raises_for_data_published_but_not_yet_known_at` — `corroborated_at = as_of - 0.5 days`, `KNOWN_AT_DELAY_DAYS = 1` → known-at = `as_of + 0.5 days`; `AsOfViolationError` raised even though the record's `corroborated_at` predates `as_of`
- `test_decide_is_deterministic_given_identical_context` — call `decide()` twice with identical `AsOfContext`; intents are equal (same fields; `intent_id` excluded from equality, it is always fresh)
- `test_unregistered_hypothesis_id_raises_at_construction` — strategy with `hypothesis_id: h99`; no matching entry in `registry.jsonl`; `StrategyRegistry.load()` raises `HypothesisNotRegisteredError`
- `test_parameter_change_without_version_bump_raises` — strategy version "1.0" registered; parameters changed; version still "1.0"; `StrategyRegistry.load()` raises `VersionConflictError`
- `test_retired_strategy_decide_raises` — strategy with `status: retired`; calling `decide()` raises `StrategyRetiredError`
- `test_retired_strategy_remains_in_registry` — after retiring, `StrategyRegistry.get("name")` still returns the entry with `status: retired`

## Definition of done

```bash
cd services/strategy && uv run pytest tests/unit/test_strategy_framework.py -q
```

Expected: 9 passed.

Then:
- `config/strategies/registry.yaml` has 8 entries, one per seed strategy, each with `status: draft`.
- All 8 strategy stub files exist in `auspex_strategy/strategies/` with class definitions and `raise NotImplementedError` in `decide()`.
- Contract suite auto-discovers and instantiates all 8 stubs without error (stubs return `[]` from `decide()` by design; `StrategyRetiredError` only applies to `status: retired`).

## Notes

**H3 (pre-announcement drift)** does not fit the `Strategy` interface: it measures returns in the `[T-20, T-1]` window before a corroboration rather than producing trade intents after one. It is an analysis script (`scripts/drift_diagnostic.py`), parallel to `evaluate_model.py`, not a strategy plugin. This is the only hypothesis in `docs/strategy-research.md` that does not map to the plugin contract. The interface is not changed to accommodate it; the research approach is different.

**H2 (time decay)** maps to parameterized versions of H1 strategy. Once H1's holding-period analysis (evaluation-protocol) identifies the optimal holding period, H1 is registered with that value. H2 is not a separate class.

**Version storage**: `config/strategies/versions/<name>/<version>.json` contains `{code_hash, parameters_hash, created_at}`. Code hash = SHA-256 of the module file bytes. Parameters hash = SHA-256 of the canonical parameters YAML. Both are recomputed at registry load time and compared. This keeps old traces explainable even after the module is edited: the stored hash records what code ran for each historical version.

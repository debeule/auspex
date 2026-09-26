import json
import sys
import types
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml

from auspex_strategy.abc import AsOfContext, Strategy
from auspex_strategy.errors import (
    AsOfViolationError,
    HypothesisNotRegisteredError,
    StrategyRetiredError,
    VersionConflictError,
)
from auspex_strategy.models import (
    CorroborationRecord,
    InputSource,
    StrategyParameters,
    SubscriptionType,
    TradeIntent,
    Trigger,
)
from auspex_strategy.registry import RegistryEntry, StrategyRegistry
from auspex_strategy.testing import StubAsOfContext

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
_HYPOTHESIS_REGISTRY = _REPO_ROOT / "config" / "hypotheses" / "registry.jsonl"
_STRATEGY_REGISTRY = _REPO_ROOT / "config" / "strategies" / "registry.yaml"

_AS_OF = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
_TRIGGER = Trigger(trigger_type=SubscriptionType.CORROBORATION_NEW)


def _load_real_registry() -> StrategyRegistry:
    return StrategyRegistry.load(
        _STRATEGY_REGISTRY,
        hypothesis_registry_path=_HYPOTHESIS_REGISTRY,
    )


def test_contract_suite_auto_discovers_all_registered_strategies() -> None:
    registry = _load_real_registry()
    entries = registry.all()
    assert len(entries) == 6

    context = StubAsOfContext(as_of=_AS_OF)

    for entry in entries:
        assert isinstance(entry, RegistryEntry)
        assert issubclass(entry.strategy_class, Strategy)
        assert entry.name
        assert entry.version
        assert entry.hypothesis_id
        result = entry.decide(context, _TRIGGER)
        assert isinstance(result, list)
        assert all(isinstance(i, TradeIntent) for i in result)


def test_adding_strategy_requires_no_change_outside_module_and_registry(tmp_path: Path) -> None:
    class SyntheticTestStrategy(Strategy):
        name = "synthetic_test"
        version = "1.0"
        hypothesis_id = "h1"
        description = "Synthetic strategy for testing auto-discovery"

        @property
        def subscriptions(self) -> frozenset[SubscriptionType]:
            return frozenset({SubscriptionType.CORROBORATION_NEW})

        @property
        def declared_inputs(self) -> frozenset[InputSource]:
            return frozenset({InputSource.CORROBORATION_STORE})

        def decide(self, context: AsOfContext, trigger: Trigger) -> list[TradeIntent]:
            return []

        @classmethod
        def parameters(cls) -> StrategyParameters:
            return StrategyParameters(raw={})

    module_name = "auspex_strategy.strategies._synthetic_test"
    fake_module = types.ModuleType(module_name)
    fake_module.SyntheticTestStrategy = SyntheticTestStrategy  # type: ignore[attr-defined]
    sys.modules[module_name] = fake_module

    try:
        registry_content = {
            "strategies": [{
                "name": "synthetic_test",
                "module": module_name,
                "class": "SyntheticTestStrategy",
                "version": "1.0",
                "hypothesis_id": "h1",
                "status": "draft",
                "parameters_file": "config/strategies/structural_convergence.yaml",
            }]
        }
        registry_path = tmp_path / "registry.yaml"
        registry_path.write_text(yaml.dump(registry_content))

        registry = StrategyRegistry.load(
            registry_path,
            hypothesis_registry_path=_HYPOTHESIS_REGISTRY,
        )
        names = {e.name for e in registry.all()}
        assert "synthetic_test" in names

        context = StubAsOfContext(as_of=_AS_OF)
        entry = registry.get("synthetic_test")
        assert entry is not None
        result = entry.decide(context, _TRIGGER)
        assert isinstance(result, list)
    finally:
        sys.modules.pop(module_name, None)


def test_as_of_context_raises_when_reading_beyond_as_of() -> None:
    future_record = CorroborationRecord(
        entity_key="BCL11A | GeneTarget",
        ticker="BEAM",
        corroborated_at=_AS_OF + timedelta(days=2),
        source_count=2,
        source_types=frozenset({"biorxiv", "clinicaltrials"}),
        participant_event_ids=("evt-001", "evt-002"),
    )
    context = StubAsOfContext(as_of=_AS_OF, corroborations=[future_record])

    with pytest.raises(AsOfViolationError):
        context.corroborations()


def test_as_of_context_raises_for_data_published_but_not_yet_known_at() -> None:
    half_day = timedelta(hours=12)
    record = CorroborationRecord(
        entity_key="BCL11A | GeneTarget",
        ticker="BEAM",
        corroborated_at=_AS_OF - half_day,
        source_count=2,
        source_types=frozenset({"biorxiv", "clinicaltrials"}),
        participant_event_ids=("evt-001", "evt-002"),
    )
    # known_at = corroborated_at + 1 day = _AS_OF + 0.5 days — still in the future
    context = StubAsOfContext(as_of=_AS_OF, corroborations=[record], known_at_delay_days=1)

    with pytest.raises(AsOfViolationError):
        context.corroborations()


def test_decide_is_deterministic_given_identical_context() -> None:
    registry = _load_real_registry()
    entry = registry.get("structural_convergence")
    assert entry is not None

    context = StubAsOfContext(as_of=_AS_OF)
    result1 = entry.decide(context, _TRIGGER)
    result2 = entry.decide(context, _TRIGGER)

    assert len(result1) == len(result2)
    for i1, i2 in zip(result1, result2):
        assert i1.matches(i2)


def test_unregistered_hypothesis_id_raises_at_construction(tmp_path: Path) -> None:
    registry_content = {
        "strategies": [{
            "name": "structural_convergence",
            "module": "auspex_strategy.strategies.h1_structural_convergence",
            "class": "StructuralConvergenceStrategy",
            "version": "1.0",
            "hypothesis_id": "h99",
            "status": "draft",
            "parameters_file": "config/strategies/structural_convergence.yaml",
        }]
    }
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(yaml.dump(registry_content))

    with pytest.raises(HypothesisNotRegisteredError):
        StrategyRegistry.load(
            registry_path,
            hypothesis_registry_path=_HYPOTHESIS_REGISTRY,
        )


def test_parameter_change_without_version_bump_raises(tmp_path: Path) -> None:
    versions_dir = tmp_path / "versions"
    entry_versions = versions_dir / "structural_convergence"
    entry_versions.mkdir(parents=True)
    (entry_versions / "1.0.json").write_text(json.dumps({
        "code_hash": "0" * 64,
        "parameters_hash": "0" * 64,
        "created_at": "2026-09-20T00:00:00+00:00",
    }))

    with pytest.raises(VersionConflictError):
        StrategyRegistry.load(
            _STRATEGY_REGISTRY,
            hypothesis_registry_path=_HYPOTHESIS_REGISTRY,
            versions_dir=versions_dir,
            config_root=_REPO_ROOT,
        )


def test_retired_strategy_decide_raises(tmp_path: Path) -> None:
    registry_content = {
        "strategies": [{
            "name": "structural_convergence",
            "module": "auspex_strategy.strategies.h1_structural_convergence",
            "class": "StructuralConvergenceStrategy",
            "version": "1.0",
            "hypothesis_id": "h1",
            "status": "retired",
            "parameters_file": "config/strategies/structural_convergence.yaml",
        }]
    }
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(yaml.dump(registry_content))

    registry = StrategyRegistry.load(
        registry_path,
        hypothesis_registry_path=_HYPOTHESIS_REGISTRY,
    )
    entry = registry.get("structural_convergence")
    assert entry is not None

    context = StubAsOfContext(as_of=_AS_OF)
    with pytest.raises(StrategyRetiredError):
        entry.decide(context, _TRIGGER)


def test_retired_strategy_remains_in_registry(tmp_path: Path) -> None:
    registry_content = {
        "strategies": [{
            "name": "structural_convergence",
            "module": "auspex_strategy.strategies.h1_structural_convergence",
            "class": "StructuralConvergenceStrategy",
            "version": "1.0",
            "hypothesis_id": "h1",
            "status": "retired",
            "parameters_file": "config/strategies/structural_convergence.yaml",
        }]
    }
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(yaml.dump(registry_content))

    registry = StrategyRegistry.load(
        registry_path,
        hypothesis_registry_path=_HYPOTHESIS_REGISTRY,
    )
    entry = registry.get("structural_convergence")
    assert entry is not None
    assert entry.status == "retired"

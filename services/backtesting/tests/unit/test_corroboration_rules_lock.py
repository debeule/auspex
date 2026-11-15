import hashlib
from pathlib import Path

import portfolio_support
import pytest
from evaluation_support import (
    CONFIG_DIR,
    TEST_HYPOTHESIS,
    evaluation_protocol,
    registered_config,
    run_fixture,
)

from auspex_backtesting import protocol as protocol_module
from auspex_backtesting.hypothesis import (
    HypothesisModifiedError,
    HypothesisNotRegisteredError,
    register_hypothesis,
    run_backtest,
)
from auspex_backtesting.portfolio import HoldoutRecord, PortfolioEvaluation


def _without_rules_registration(tmp_path: Path) -> tuple[Path, Path]:
    config_dir = tmp_path / "hypotheses"
    config_dir.mkdir()
    registry = config_dir / "registry.jsonl"
    registry.write_text("", encoding="utf-8")
    register_hypothesis(
        "protocol", (CONFIG_DIR / "protocol.yaml").read_text(encoding="utf-8"),
        config_dir=config_dir, registry_path=registry,
    )
    register_hypothesis("h1", TEST_HYPOTHESIS, config_dir=config_dir, registry_path=registry)
    rules = tmp_path / "corroboration" / "entity-rules.yaml"
    rules.parent.mkdir()
    rules.write_bytes((CONFIG_DIR.parent / "corroboration" / "entity-rules.yaml").read_bytes())
    return config_dir, registry


def _refused_on_every_event_path(
    config_dir: Path, registry: Path, error: type[Exception], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("N_BOOTSTRAP", "200")
    prices, events, _ = run_fixture()
    with pytest.raises(error, match="corroboration_rules"):
        evaluation_protocol(config_dir, registry, prices).run("h1", events, "entity-only")
    with pytest.raises(error, match="corroboration_rules"):
        run_backtest("h1", [], {}, config_dir=config_dir, registry_path=registry,
                     trials_dir=config_dir / "trials")
    assert not (config_dir / "trials").exists()


def test_event_evaluation_refuses_an_unregistered_corroboration_rules_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_dir, registry = _without_rules_registration(tmp_path)

    _refused_on_every_event_path(config_dir, registry, HypothesisNotRegisteredError, monkeypatch)


def test_event_evaluation_refuses_corroboration_rules_changed_since_registration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_dir, registry = registered_config(tmp_path)
    rules = tmp_path / "corroboration" / "entity-rules.yaml"
    rules.write_bytes(rules.read_bytes() + b"# edited\n")

    _refused_on_every_event_path(config_dir, registry, HypothesisModifiedError, monkeypatch)


def test_event_result_records_the_corroboration_rules_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("N_BOOTSTRAP", "200")
    config_dir, registry = registered_config(tmp_path)
    expected = hashlib.sha256(
        (tmp_path / "corroboration" / "entity-rules.yaml").read_bytes()
    ).hexdigest()
    prices, events, _ = run_fixture()

    result = evaluation_protocol(config_dir, registry, prices).run(
        "h1", events, "entity-only", holding_period_days=[20], known_at_delay_days=[1]
    )
    report = run_backtest("h1", [], {}, config_dir=config_dir, registry_path=registry,
                          trials_dir=config_dir / "trials")

    assert result.corroboration_rules_hash == expected
    assert result.to_report()["corroboration_rules_hash"] == expected
    assert report.corroboration_rules_hash == expected


def test_portfolio_evaluation_never_reads_the_corroboration_rules(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checked: list[object] = []
    monkeypatch.setattr(
        protocol_module, "verify_corroboration_rules", lambda *a, **k: checked.append(a)
    )
    config_dir, registry = portfolio_support.registered_config(tmp_path)
    assert not (tmp_path / "corroboration").exists()
    evaluation = PortfolioEvaluation(
        portfolio_support.evaluation_protocol(config_dir, registry),
        portfolio_support.world(100).engine(),
        _Pinned(),
        HoldoutRecord(tmp_path / "holdout"),
    )

    report = evaluation.run(
        "h9", {"cadence": "monthly_top15", "catalyst_guard": "none"},
        portfolio_support.monthly_rule(), 1, [10_000.0],
    )

    assert report.verdict.status
    assert checked == []


class _Pinned:
    def missing(self, keys: object) -> list[str]:
        return []

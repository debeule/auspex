import json
from pathlib import Path

import pytest

from auspex_backtesting.evaluation import TrialBudgetExhaustedError
from auspex_backtesting.hypothesis import (
    HypothesisModifiedError,
    HypothesisNotRegisteredError,
    register_hypothesis,
    run_backtest,
    verify_hypothesis,
)

_H1_YAML = """\
id: h1
version: 1
description: "Structural convergence premium"
role: promotable
signal_definition:
  variant: entity-only
  filter: none
  join_field: corroborated_at
entry_timing_days: 1
holding_period_days: [5, 10, 20, 30]
benchmark: XBI
exit: fixed_horizon_close
status: pre-registered
registered_at: "2026-09-20T00:00:00Z"
"""

_H1_YAML_V2 = """\
id: h1
version: 2
description: "Structural convergence premium — revised entry timing"
role: promotable
signal_definition:
  variant: entity-only
  filter: none
  join_field: corroborated_at
entry_timing_days: 2
holding_period_days: [5, 10, 20, 30]
benchmark: XBI
exit: fixed_horizon_close
status: pre-registered
registered_at: "2026-09-21T00:00:00Z"
"""


_PROTOCOL_YAML = (
    Path(__file__).resolve().parents[4] / "config" / "hypotheses" / "protocol.yaml"
).read_text(encoding="utf-8")


def _dirs(tmp_path: Path) -> tuple[Path, Path, Path]:
    config_dir = tmp_path / "hypotheses"
    config_dir.mkdir()
    trials_dir = tmp_path / "trials"
    trials_dir.mkdir()
    registry_path = tmp_path / "registry.jsonl"
    registry_path.write_text("")
    register_hypothesis(
        "protocol", _PROTOCOL_YAML, config_dir=config_dir, registry_path=registry_path
    )
    return config_dir, registry_path, trials_dir


def test_backtest_refuses_unregistered_hypothesis_id(tmp_path: Path) -> None:
    config_dir, registry_path, trials_dir = _dirs(tmp_path)
    (config_dir / "h1.yaml").write_text(_H1_YAML)

    with pytest.raises(HypothesisNotRegisteredError):
        run_backtest(
            "h1", [], {},
            config_dir=config_dir,
            registry_path=registry_path,
            trials_dir=trials_dir,
        )


def test_backtest_refuses_modified_hypothesis(tmp_path: Path) -> None:
    config_dir, registry_path, _trials_dir = _dirs(tmp_path)

    register_hypothesis("h1", _H1_YAML, config_dir=config_dir, registry_path=registry_path)
    (config_dir / "h1.yaml").write_text(_H1_YAML_V2)

    with pytest.raises(HypothesisModifiedError):
        verify_hypothesis("h1", config_dir=config_dir, registry_path=registry_path)


def test_registration_is_idempotent_on_content(tmp_path: Path) -> None:
    config_dir, registry_path, _ = _dirs(tmp_path)

    register_hypothesis("h1", _H1_YAML, config_dir=config_dir, registry_path=registry_path)
    register_hypothesis("h1", _H1_YAML, config_dir=config_dir, registry_path=registry_path)

    lines = [l for l in registry_path.read_text().splitlines() if l.strip()]
    h1_entries = [json.loads(l) for l in lines if json.loads(l)["hypothesis_id"] == "h1"]
    assert len(h1_entries) == 1


def test_content_change_creates_new_registry_entry(tmp_path: Path) -> None:
    config_dir, registry_path, _ = _dirs(tmp_path)

    register_hypothesis("h1", _H1_YAML, config_dir=config_dir, registry_path=registry_path)
    register_hypothesis("h1", _H1_YAML_V2, config_dir=config_dir, registry_path=registry_path)

    lines = [l for l in registry_path.read_text().splitlines() if l.strip()]
    h1_entries = [json.loads(l) for l in lines if json.loads(l)["hypothesis_id"] == "h1"]
    assert len(h1_entries) == 2
    hashes = {e["file_hash"] for e in h1_entries}
    assert len(hashes) == 2


def test_trial_log_entry_is_appended_on_each_run(tmp_path: Path) -> None:
    config_dir, registry_path, trials_dir = _dirs(tmp_path)
    register_hypothesis("h1", _H1_YAML, config_dir=config_dir, registry_path=registry_path)

    run_backtest(
        "h1", [], {},
        config_dir=config_dir,
        registry_path=registry_path,
        trials_dir=trials_dir,
    )
    run_backtest(
        "h1", [], {},
        config_dir=config_dir,
        registry_path=registry_path,
        trials_dir=trials_dir,
    )

    trial_file = trials_dir / "h1.jsonl"
    lines = [l for l in trial_file.read_text().splitlines() if l.strip()]
    assert len(lines) == 2
    entries = [json.loads(l) for l in lines]
    assert entries[0]["hypothesis_id"] == "h1"
    assert entries[1]["hypothesis_id"] == "h1"
    assert entries[0]["run_id"] != entries[1]["run_id"]


def test_verify_hypothesis_passes_when_content_is_unchanged(tmp_path: Path) -> None:
    config_dir, registry_path, _ = _dirs(tmp_path)
    register_hypothesis("h1", _H1_YAML, config_dir=config_dir, registry_path=registry_path)

    verify_hypothesis("h1", config_dir=config_dir, registry_path=registry_path)


def test_backtest_with_a_universe_logs_events_dropped_outside_it(tmp_path: Path) -> None:
    from datetime import UTC, date, datetime

    from auspex_backtesting.backtest.membership import UniverseMembership
    from auspex_backtesting.backtest.runner import BacktestEvent

    config_dir, registry_path, trials_dir = _dirs(tmp_path)
    register_hypothesis("h1", _H1_YAML, config_dir=config_dir, registry_path=registry_path)
    event = BacktestEvent("e1", "ZZZZ", datetime(2024, 3, 4, 12, tzinfo=UTC), "raw/e1.json")

    report = run_backtest(
        "h1", [event], {},
        config_dir=config_dir,
        registry_path=registry_path,
        trials_dir=trials_dir,
        universe=UniverseMembership([], [], as_of=date(2024, 12, 31)),
    )

    assert report.outside_universe == 1
    (line,) = (trials_dir / "h1.jsonl").read_text().splitlines()
    assert len(json.loads(line)["cells"]) == 6


def test_backtest_reserves_its_cells_in_the_trial_ledger_before_reading_returns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from auspex_backtesting.backtest import runner as runner_module

    config_dir, registry_path, trials_dir = _dirs(tmp_path)
    register_hypothesis("h1", _H1_YAML, config_dir=config_dir, registry_path=registry_path)
    lines_at_run: list[int] = []
    original_run = runner_module.BacktestRunner.run

    def run(self: object, *args: object, **kwargs: object) -> object:
        lines_at_run.append(len((trials_dir / "h1.jsonl").read_text().splitlines()))
        return original_run(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(runner_module.BacktestRunner, "run", run)

    for _ in range(10):
        run_backtest(
            "h1", [], {},
            config_dir=config_dir,
            registry_path=registry_path,
            trials_dir=trials_dir,
        )
    assert lines_at_run[0] == 1

    with pytest.raises(TrialBudgetExhaustedError):
        run_backtest(
            "h1", [], {},
            config_dir=config_dir,
            registry_path=registry_path,
            trials_dir=trials_dir,
        )
    assert len(lines_at_run) == 10

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from auspex_backtesting.backtest.runner import BacktestEvent, BacktestReport, BacktestRunner


class HypothesisNotRegisteredError(Exception):
    pass


class HypothesisModifiedError(Exception):
    pass


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _last_entry(hypothesis_id: str, registry_path: Path) -> dict[str, Any] | None:
    if not registry_path.exists():
        return None
    last: dict[str, Any] | None = None
    for line in registry_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        entry = json.loads(line)
        if entry.get("hypothesis_id") == hypothesis_id:
            last = entry
    return last


def load_hypothesis(hypothesis_id: str, config_dir: Path | None = None) -> dict[str, Any]:
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ImportError("pyyaml is required for load_hypothesis()") from exc
    path = _hypothesis_path(hypothesis_id, config_dir)
    return yaml.safe_load(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def verify_hypothesis(
    hypothesis_id: str,
    *,
    config_dir: Path | None = None,
    registry_path: Path | None = None,
) -> None:
    reg = _resolve_registry(registry_path)
    entry = _last_entry(hypothesis_id, reg)
    if entry is None:
        raise HypothesisNotRegisteredError(hypothesis_id)
    path = _hypothesis_path(hypothesis_id, config_dir)
    current_hash = _sha256_bytes(path.read_bytes())
    if current_hash != entry["file_hash"]:
        raise HypothesisModifiedError(
            f"{hypothesis_id}: registered hash {entry['file_hash']!r} != current {current_hash!r}"
        )


def register_hypothesis(
    hypothesis_id: str,
    yaml_content: str,
    *,
    config_dir: Path | None = None,
    registry_path: Path | None = None,
) -> None:
    content_bytes = yaml_content.encode("utf-8")
    new_hash = _sha256_bytes(content_bytes)
    reg = _resolve_registry(registry_path)
    last = _last_entry(hypothesis_id, reg)
    if last is not None and last["file_hash"] == new_hash:
        return
    path = _hypothesis_path(hypothesis_id, config_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content_bytes)
    entry = {
        "hypothesis_id": hypothesis_id,
        "file_hash": new_hash,
        "registered_at": datetime.now(UTC).isoformat(),
    }
    with reg.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


def run_backtest(
    hypothesis_id: str,
    events: list[BacktestEvent],
    price_data: dict[str, Any],
    *,
    config_dir: Path | None = None,
    registry_path: Path | None = None,
    trials_dir: Path | None = None,
    windows: tuple[int, ...] = (5, 20, 60),
) -> BacktestReport:
    verify_hypothesis(hypothesis_id, config_dir=config_dir, registry_path=registry_path)
    reg = _resolve_registry(registry_path)
    entry = _last_entry(hypothesis_id, reg)
    assert entry is not None

    runner = BacktestRunner(windows=windows)
    report = runner.run(events, price_data)

    _append_trial(hypothesis_id, entry["file_hash"], report, trials_dir=trials_dir)
    return report


def _append_trial(
    hypothesis_id: str,
    file_hash: str,
    report: BacktestReport,
    *,
    trials_dir: Path | None = None,
) -> None:
    tdir = _resolve_trials_dir(trials_dir)
    tdir.mkdir(parents=True, exist_ok=True)
    trial_file = tdir / f"{hypothesis_id}.jsonl"
    record = {
        "run_id": str(uuid.uuid4()),
        "hypothesis_id": hypothesis_id,
        "file_hash": file_hash,
        "started_at": datetime.now(UTC).isoformat(),
        "result_summary": {
            "results_count": len(report.results),
            "entity_only_groups": len(report.entity_only.groups) if report.entity_only else 0,
            "full_groups": len(report.full.groups) if report.full else 0,
        },
    }
    with trial_file.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


def _hypothesis_path(hypothesis_id: str, config_dir: Path | None) -> Path:
    base = config_dir if config_dir is not None else Path("config/hypotheses")
    return base / f"{hypothesis_id}.yaml"


def _resolve_registry(registry_path: Path | None) -> Path:
    if registry_path is not None:
        return registry_path
    return Path("config/hypotheses/registry.jsonl")


def _resolve_trials_dir(trials_dir: Path | None) -> Path:
    if trials_dir is not None:
        return trials_dir
    return Path("config/hypotheses/trials")

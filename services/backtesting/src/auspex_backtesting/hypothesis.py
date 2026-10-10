from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from auspex_backtesting.backtest.membership import UniverseMembership
from auspex_backtesting.backtest.runner import BacktestEvent, BacktestReport, BacktestRunner


class HypothesisNotRegisteredError(Exception):
    pass


class HypothesisModifiedError(Exception):
    pass


class HypothesisInvalidError(Exception):
    pass


EVALUATION_KINDS = frozenset({"event", "portfolio"})
ROLES = frozenset({"promotable", "filter", "diagnostic", "descriptive"})
EVENT_ONLY_FIELDS = frozenset({"known_at_delay_days", "entry_timing_days", "holding_period_days"})
PORTFOLIO_ONLY_FIELDS = frozenset(
    {
        "score_frequency",
        "rebalance_frequency",
        "trade_date_rule",
        "hold_bands",
        "catalyst_guard",
        "in_sample_years",
        "holdout_years",
    }
)
_PROTOCOL_ID = "protocol"


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


def hypothesis_views(hypothesis: dict[str, Any]) -> list[dict[str, Any]]:
    """One view per registered use of a hypothesis.

    A hypothesis with a `uses` list (one score registered as a filter in one universe and as a
    promotable test in another) yields each use merged over the shared top-level fields, with
    the use's id under `use`. Any other hypothesis is its own single view.
    """
    uses = hypothesis.get("uses")
    if uses is None:
        return [hypothesis]
    shared = {k: v for k, v in hypothesis.items() if k != "uses"}
    return [{**shared, **use, "id": hypothesis.get("id"), "use": use["id"]} for use in uses]


def validate_hypothesis(hypothesis: dict[str, Any]) -> None:
    """Refuse a hypothesis whose fields do not fit its evaluation kind.

    Raises HypothesisInvalidError naming the offending field.
    """
    for view in hypothesis_views(hypothesis):
        _validate_view(view)


def _validate_view(view: dict[str, Any]) -> None:
    name = str(view.get("id", "?")) + (f"/{view['use']}" if "use" in view else "")
    kind = view.get("evaluation", "event")
    if kind not in EVALUATION_KINDS:
        raise HypothesisInvalidError(
            f"{name}: evaluation {kind!r} is not one of {sorted(EVALUATION_KINDS)}"
        )
    if view.get("role") not in ROLES:
        raise HypothesisInvalidError(
            f"{name}: role {view.get('role')!r} is not one of {sorted(ROLES)}"
        )

    forbidden = EVENT_ONLY_FIELDS if kind == "portfolio" else PORTFOLIO_ONLY_FIELDS
    named = set(view) | set(view.get("primary_cell") or {}) | set(view.get("trial_grid") or {})
    clash = sorted(named & forbidden)
    if clash:
        raise HypothesisInvalidError(f"{name}: {kind} hypothesis names {', '.join(clash)}")

    if kind == "portfolio":
        if not view.get("family"):
            raise HypothesisInvalidError(f"{name}: portfolio hypothesis names no family")
        in_sample = _year_window(name, view, "in_sample_years")
        holdout = _year_window(name, view, "holdout_years")
        if holdout[0] <= in_sample[1]:
            raise HypothesisInvalidError(f"{name}: holdout_years must start after in_sample_years")

    grid = view.get("trial_grid")
    if grid is not None:
        cells = 1
        for values in grid.values():
            cells *= len(values)
        if view.get("trial_cells") != cells:
            raise HypothesisInvalidError(f"{name}: trial_cells must equal the trial_grid's {cells}")
        for axis, value in (view.get("primary_cell") or {}).items():
            if value not in grid.get(axis, []):
                raise HypothesisInvalidError(
                    f"{name}: primary_cell {axis}={value!r} is not in trial_grid"
                )


def _year_window(name: str, view: dict[str, Any], field: str) -> tuple[int, int]:
    window = view.get(field)
    if (
        not isinstance(window, list)
        or len(window) != 2
        or not all(isinstance(y, int) for y in window)
        or window[0] > window[1]
    ):
        raise HypothesisInvalidError(f"{name}: {field} must be [first_year, last_year]")
    return window[0], window[1]


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
    if hypothesis_id != _PROTOCOL_ID:
        validate_hypothesis(load_hypothesis(hypothesis_id, config_dir))


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
    universe: UniverseMembership | None = None,
) -> BacktestReport:
    verify_hypothesis(hypothesis_id, config_dir=config_dir, registry_path=registry_path)
    reg = _resolve_registry(registry_path)
    entry = _last_entry(hypothesis_id, reg)
    assert entry is not None

    runner = BacktestRunner(windows=windows)
    report = runner.run(events, price_data, universe)

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
            "outside_universe": report.outside_universe,
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

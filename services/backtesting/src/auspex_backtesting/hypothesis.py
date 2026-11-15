from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from auspex_backtesting.backtest.episodes import EntityRules
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
CORROBORATION_RULES_ID = "corroboration_rules"


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


def corroboration_rules_path(config_dir: Path | None) -> Path:
    """`config/corroboration/entity-rules.yaml`, beside the hypotheses directory."""
    base = config_dir if config_dir is not None else Path("config/hypotheses")
    return base.parent / "corroboration" / "entity-rules.yaml"


def register_corroboration_rules(rules_path: Path, *, registry_path: Path | None = None) -> None:
    """Append the rules file's hash under `corroboration_rules` unless it is the latest one."""
    new_hash = _sha256_bytes(rules_path.read_bytes())
    reg = _resolve_registry(registry_path)
    last = _last_entry(CORROBORATION_RULES_ID, reg)
    if last is not None and last["file_hash"] == new_hash:
        return
    entry = {
        "hypothesis_id": CORROBORATION_RULES_ID,
        "file_hash": new_hash,
        "registered_at": datetime.now(UTC).isoformat(),
    }
    with reg.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


def verify_corroboration_rules(rules_path: Path, *, registry_path: Path | None = None) -> str:
    """The rules file's hash, after refusing a file never registered or changed since (EVA-029)."""
    entry = _last_entry(CORROBORATION_RULES_ID, _resolve_registry(registry_path))
    if entry is None:
        raise HypothesisNotRegisteredError(CORROBORATION_RULES_ID)
    current = _sha256_bytes(rules_path.read_bytes()) if rules_path.is_file() else None
    if current is None or current != entry["file_hash"]:
        raise HypothesisModifiedError(
            f"{CORROBORATION_RULES_ID}: registered hash {entry['file_hash']!r} != current"
            f" {current!r} ({rules_path})"
        )
    return current


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
    corroboration_rules: Path | None = None,
) -> BacktestReport:
    """Raw window returns per corroboration group, after reserving them as trial cells.

    Each window of each variant is one cell in the trial ledger, reserved before any return is
    read, so a look at raw returns spends the family's budget like an evaluation does. The
    corroboration rules file (default beside `config_dir`) must match its registration; its
    rules build the groups and its hash is on the report.
    """
    from auspex_backtesting.evaluation.ledger import TrialLedger

    verify_hypothesis(_PROTOCOL_ID, config_dir=config_dir, registry_path=registry_path)
    verify_hypothesis(hypothesis_id, config_dir=config_dir, registry_path=registry_path)
    rules_path = corroboration_rules or corroboration_rules_path(config_dir)
    rules_hash = verify_corroboration_rules(rules_path, registry_path=registry_path)
    rules = EntityRules.load(rules_path.read_bytes())
    protocol = load_hypothesis(_PROTOCOL_ID, config_dir)
    hypothesis = load_hypothesis(hypothesis_id, config_dir)
    base = config_dir if config_dir is not None else Path("config/hypotheses")
    registered = {
        path.stem: load_hypothesis(path.stem, config_dir)
        for path in sorted(base.glob("*.yaml"))
        if path.stem != _PROTOCOL_ID
    }
    cells = [
        {
            "window_days": w,
            "known_at_delay_days": hypothesis.get("entry_timing_days"),
            "variant": variant,
        }
        for w in windows
        for variant in ("entity-only", "full")
    ]
    TrialLedger(_resolve_trials_dir(trials_dir), protocol, registered).reserve(
        hypothesis_id, cells, run_id=str(uuid.uuid4())
    )
    report = BacktestRunner(windows=windows, rules=rules).run(events, price_data, universe)
    return replace(report, corroboration_rules_hash=rules_hash)


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

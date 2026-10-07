import json
import shutil
from pathlib import Path

import pytest
import yaml

from auspex_backtesting.hypothesis import (
    HypothesisModifiedError,
    register_hypothesis,
    verify_hypothesis,
)

_CONFIG_DIR = Path(__file__).resolve().parents[4] / "config" / "hypotheses"
_REGISTRY = _CONFIG_DIR / "registry.jsonl"
_HYPOTHESIS_IDS = [f"h{n}" for n in range(1, 9)]


def _load(file_id: str) -> dict:
    return yaml.safe_load((_CONFIG_DIR / f"{file_id}.yaml").read_text(encoding="utf-8"))


@pytest.mark.parametrize("file_id", ["protocol", *_HYPOTHESIS_IDS])
def test_committed_file_matches_its_latest_registration(file_id: str) -> None:
    verify_hypothesis(file_id, config_dir=_CONFIG_DIR, registry_path=_REGISTRY)


def test_edited_protocol_is_refused_until_reregistered(tmp_path: Path) -> None:
    config_dir = tmp_path / "hypotheses"
    shutil.copytree(_CONFIG_DIR, config_dir)
    registry = config_dir / "registry.jsonl"
    protocol = config_dir / "protocol.yaml"
    edited = protocol.read_text(encoding="utf-8").replace(
        "clustered_t_min: 3.0", "clustered_t_min: 2.0"
    )
    protocol.write_text(edited, encoding="utf-8")

    with pytest.raises(HypothesisModifiedError):
        verify_hypothesis("protocol", config_dir=config_dir, registry_path=registry)

    lines_before = registry.read_text(encoding="utf-8").splitlines()
    register_hypothesis("protocol", edited, config_dir=config_dir, registry_path=registry)
    verify_hypothesis("protocol", config_dir=config_dir, registry_path=registry)
    lines_after = registry.read_text(encoding="utf-8").splitlines()
    assert lines_after[: len(lines_before)] == lines_before
    assert json.loads(lines_after[-1])["hypothesis_id"] == "protocol"


def test_protocol_holds_the_accepted_thresholds() -> None:
    protocol = _load("protocol")
    assert protocol["abnormal_return"]["model"] == "market_model"
    assert protocol["abnormal_return"]["estimation_window_trading_days"] == [-250, -30]
    assert protocol["abnormal_return"]["min_estimation_obs"] == 120
    assert protocol["inference"]["cluster_by"] == ["ticker", "event_month"]
    assert protocol["inference"]["min_clusters_per_dimension"] == 30
    assert protocol["trials"]["counting"] == "cells"
    assert protocol["trials"]["scope"] == "family"
    assert protocol["trials"]["family_budget_cells"] == 64
    assert protocol["promotion"] == {
        "judged_on": "primary_cell",
        "clustered_t_min": 3.0,
        "deflated_sharpe_min": 0.95,
        "holdout_months": 3,
    }
    assert protocol["sizing"]["max_kelly_fraction"] == 0.25
    assert protocol["sizing"]["max_position_pct"] == 0.05
    assert protocol["sizing"]["max_positions_per_theme"] == 1

    kill = {k["id"]: k for k in protocol["kill_criteria"]}
    assert set(kill) == {
        "lagging_signal",
        "no_in_sample_effect",
        "mapping_quality",
        "forward_check",
        "cost_check",
    }
    assert kill["no_in_sample_effect"]["min_clustered_t"] == 1.5
    assert kill["no_in_sample_effect"]["min_mean_net_abnormal_return"] == 0.0
    assert kill["mapping_quality"]["min_event_to_ticker_precision"] == 0.85
    assert kill["mapping_quality"]["min_golden_set_events"] == 50
    assert kill["forward_check"]["min_months"] == 12
    assert kill["forward_check"]["min_independent_events"] == 60
    assert kill["forward_check"]["min_clustered_t"] == 2.0
    assert kill["cost_check"]["max_cost_to_gross_ratio"] == 0.5


def test_hypothesis_triage_roles_and_statuses() -> None:
    expected = {
        "h1": ("promotable", "suspended"),
        "h2": ("diagnostic", "pre-registered"),
        "h3": ("diagnostic", "pre-registered"),
        "h4": ("promotable", "suspended"),
        "h5": ("descriptive", "pre-registered"),
        "h6": ("promotable", "suspended"),
        "h7": ("descriptive", "pre-registered"),
        "h8": ("promotable", "suspended"),
    }
    actual = {h: (_load(h)["role"], _load(h)["status"]) for h in _HYPOTHESIS_IDS}
    assert actual == expected
    for h, (_, status) in expected.items():
        if status == "suspended":
            assert _load(h)["suspended_reason"]


def test_declared_trial_grid_contains_primary_cell_and_matches_cell_count() -> None:
    protocol = _load("protocol")
    total = 0
    for h in _HYPOTHESIS_IDS:
        hyp = _load(h)
        if "primary_cell" not in hyp:
            continue
        cell = hyp["primary_cell"]
        assert cell["holding_period_days"] in hyp["holding_period_days"]
        assert cell["known_at_delay_days"] in hyp["known_at_delay_days"]
        assert cell["variant"] in hyp["variants"]
        assert hyp["known_at_delay_days"] == protocol["trials"]["known_at_delay_days"]
        cells = (
            len(hyp["holding_period_days"]) * len(hyp["known_at_delay_days"]) * len(hyp["variants"])
        )
        assert hyp["trial_cells"] == cells
        total += cells
    assert 0 < total <= protocol["trials"]["family_budget_cells"]

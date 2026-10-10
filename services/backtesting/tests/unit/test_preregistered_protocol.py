import ast
import json
import shutil
from datetime import date
from pathlib import Path
from typing import Any

import pytest
import yaml

from auspex_backtesting.hypothesis import (
    HypothesisInvalidError,
    HypothesisModifiedError,
    register_hypothesis,
    verify_hypothesis,
)
from auspex_backtesting.market_sim.calendar import MarketCalendar
from auspex_backtesting.protocol import (
    EvaluationProtocol,
    FamilyNotBudgetedError,
    NotPromotableError,
    PortfolioForwardRecord,
    ProtocolCeilingError,
    TrialBudgetExceededError,
    check_promotable,
    check_trial_budgets,
    count_trials,
    evaluate_portfolio_forward_check,
    forward_check_branch,
    is_data_gap,
    quarterly_trade_date,
    select_component_variant,
)

_CONFIG_DIR = Path(__file__).resolve().parents[4] / "config" / "hypotheses"
_REGISTRY = _CONFIG_DIR / "registry.jsonl"
_HYPOTHESIS_IDS = [f"h{n}" for n in range(1, 13)]
_EVENT_HYPOTHESIS_IDS = [f"h{n}" for n in range(1, 9)]
_EXTRACTOR = (
    Path(__file__).resolve().parents[3] / "ingestion-scraper/src/auspex_ingest/extractor.py"
)


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
    assert protocol["families"]["event_backfill"]["budget_cells"] == 64
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
    event_forward_check = kill["forward_check"]["event"]
    assert event_forward_check["min_months"] == 12
    assert event_forward_check["min_independent_events"] == 60
    assert event_forward_check["min_clustered_t"] == 2.0
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
        "h8": ("filter", "pre-registered"),
    }
    actual = {h: (_load(h)["role"], _load(h)["status"]) for h in _EVENT_HYPOTHESIS_IDS}
    assert actual == expected
    for h, (_, status) in expected.items():
        if status == "suspended":
            assert _load(h)["suspended_reason"]


def test_declared_trial_grid_contains_primary_cell_and_matches_cell_count() -> None:
    protocol = _load("protocol")
    total = 0
    for h in _EVENT_HYPOTHESIS_IDS:
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
    assert 0 < total <= protocol["families"]["event_backfill"]["budget_cells"]


def _copy_config(tmp_path: Path) -> tuple[Path, Path]:
    config_dir = tmp_path / "hypotheses"
    shutil.copytree(_CONFIG_DIR, config_dir)
    return config_dir, config_dir / "registry.jsonl"


def _register_edited(
    config_dir: Path, registry: Path, file_id: str, content: dict[str, Any]
) -> None:
    register_hypothesis(
        file_id,
        yaml.safe_dump(content, sort_keys=False),
        config_dir=config_dir,
        registry_path=registry,
    )


def _forward_record(**overrides: Any) -> PortfolioForwardRecord:
    fields: dict[str, Any] = {
        "paper_monthly_net_excess": [0.01] * 12,
        "replay_monthly_net_excess": [0.01] * 12,
        "ledger_gap_sessions": [],
        "in_sample_mean_annual_net_excess": 0.08,
        "in_sample_standard_error_annual": 0.03,
    }
    fields.update(overrides)
    return PortfolioForwardRecord(**fields)


def test_registry_holds_one_registration_per_file() -> None:
    entries = [json.loads(line) for line in _REGISTRY.read_text(encoding="utf-8").splitlines()]
    registered = [entry["hypothesis_id"] for entry in entries]
    assert sorted(registered) == sorted(["protocol", *_HYPOTHESIS_IDS])
    for file_id in ["protocol", *_HYPOTHESIS_IDS]:
        assert _load(file_id)["version"] == 1
        verify_hypothesis(file_id, config_dir=_CONFIG_DIR, registry_path=_REGISTRY)


def test_trial_budget_is_counted_per_family_not_across_families() -> None:
    protocol = _load("protocol")
    event = {"id": "a", "evaluation": "event", "family": "event_backfill", "role": "promotable"}
    holdings = {
        "id": "b",
        "evaluation": "portfolio",
        "family": "holdings_panel",
        "role": "promotable",
    }

    spec_case = [{**event, "trial_cells": 40}, {**holdings, "trial_cells": 10}]
    assert count_trials(spec_case, protocol) == {"event_backfill": 40, "holdings_panel": 10}
    check_trial_budgets(spec_case, protocol)

    # 76 cells in total exceeds the event family's 64, which only a global count would refuse.
    check_trial_budgets([{**event, "trial_cells": 40}, {**holdings, "trial_cells": 36}], protocol)

    with pytest.raises(TrialBudgetExceededError, match="event_backfill"):
        check_trial_budgets(
            [{**event, "trial_cells": 65}, {**holdings, "trial_cells": 1}], protocol
        )


def test_portfolio_hypothesis_without_holdout_years_is_refused(tmp_path: Path) -> None:
    config_dir, registry = _copy_config(tmp_path)
    h9 = _load("h9")
    del h9["holdout_years"]
    _register_edited(config_dir, registry, "h9", h9)

    with pytest.raises(HypothesisInvalidError, match="holdout_years"):
        verify_hypothesis("h9", config_dir=config_dir, registry_path=registry)


def test_portfolio_hypothesis_naming_known_at_delay_cells_is_refused(tmp_path: Path) -> None:
    config_dir, registry = _copy_config(tmp_path)
    h9 = _load("h9")
    h9["known_at_delay_days"] = [0, 1, 3, 5]
    _register_edited(config_dir, registry, "h9", h9)

    with pytest.raises(HypothesisInvalidError, match="known_at_delay_days"):
        verify_hypothesis("h9", config_dir=config_dir, registry_path=registry)


def test_event_hypothesis_naming_rebalance_frequency_is_refused(tmp_path: Path) -> None:
    config_dir, registry = _copy_config(tmp_path)
    h3 = _load("h3")
    h3["rebalance_frequency"] = "quarterly"
    _register_edited(config_dir, registry, "h3", h3)

    with pytest.raises(HypothesisInvalidError, match="rebalance_frequency"):
        verify_hypothesis("h3", config_dir=config_dir, registry_path=registry)


def test_forward_check_branch_follows_the_hypothesis_evaluation_kind() -> None:
    protocol = _load("protocol")
    forward_check = next(k for k in protocol["kill_criteria"] if k["id"] == "forward_check")

    assert forward_check_branch(_load("h9"), protocol) == forward_check["portfolio"]
    assert forward_check_branch(_load("h3"), protocol) == forward_check["event"]
    assert (
        forward_check_branch(_load("h10"), protocol, use="broad_small_mid")
        == (forward_check["portfolio"])
    )


def test_portfolio_forward_check_fails_on_tracking_difference_above_two_percent_a_year() -> None:
    protocol = _load("protocol")
    replay = [0.01] * 12

    # Paper trails the replay by 0.25% a month: 3% a year.
    lagging = _forward_record(
        paper_monthly_net_excess=[r - 0.0025 for r in replay], replay_monthly_net_excess=replay
    )
    verdict = evaluate_portfolio_forward_check(lagging, protocol)
    assert verdict.status == "fail"
    assert "tracking_difference" in verdict.reasons

    # 0.15% a month: 1.8% a year, inside the tolerance.
    close = _forward_record(
        paper_monthly_net_excess=[r - 0.0015 for r in replay], replay_monthly_net_excess=replay
    )
    assert evaluate_portfolio_forward_check(close, protocol).status == "pass"


def test_portfolio_forward_check_fails_on_any_ledger_gap() -> None:
    protocol = _load("protocol")
    assert evaluate_portfolio_forward_check(_forward_record(), protocol).status == "pass"

    one_gap = _forward_record(ledger_gap_sessions=[date(2027, 2, 16)])
    verdict = evaluate_portfolio_forward_check(one_gap, protocol)
    assert verdict.status == "fail"
    assert verdict.reasons == ["ledger_gap"]

    short = _forward_record(
        paper_monthly_net_excess=[0.01] * 11, replay_monthly_net_excess=[0.01] * 11
    )
    assert evaluate_portfolio_forward_check(short, protocol).status == "insufficient"


def test_shorts_and_options_are_disabled_by_protocol_ceiling() -> None:
    protocol = _load("protocol")
    assert protocol["instruments"] == {"shorts_enabled": False, "options_enabled": False}

    evaluation = EvaluationProtocol(config_dir=_CONFIG_DIR, registry_path=_REGISTRY)
    long_only = _load("h9")
    evaluation.check_admissible(long_only)
    with pytest.raises(ProtocolCeilingError, match="short"):
        evaluation.check_admissible({**long_only, "direction": "short"})
    with pytest.raises(ProtocolCeilingError, match="option"):
        evaluation.check_admissible({**long_only, "instrument": "options"})


def test_equal_risk_is_the_default_sizer_with_fifteen_name_minimum() -> None:
    sizing = _load("protocol")["sizing"]
    assert sizing["default_sizer"] == "equal_risk"
    assert sizing["min_names"] == 15
    assert sizing["min_trades_for_kelly"] == 20
    assert sizing["max_kelly_fraction"] == 0.25
    assert _load("h9")["sizing"] == "equal_risk"


def test_h9_specialist_component_references_the_rule_not_a_fixed_list() -> None:
    specialist = _load("h9")["components"]["specialist_13f_ownership"]
    assert specialist["rule"] == "specs/sec-ownership-datasets.md#SpecialistClassifier"
    assert specialist["as_of"] == "13f_accepted_before_rebalance"
    assert set(specialist["thresholds"]) == {
        "SPECIALIST_HEALTHCARE_SHARE",
        "SPECIALIST_MIN_AUM_USD",
    }
    assert not any(isinstance(value, list) for value in specialist.values())


def test_h9_two_component_variant_is_preregistered_with_its_selection_rule() -> None:
    h9 = _load("h9")
    variants = h9["component_variants"]
    assert set(variants["three_component"]) == set(h9["components"])
    assert set(variants["two_component"]) == {"specialist_13f_ownership", "net_insider_buying"}

    assert select_component_variant(h9, short_interest_history_start=date(2013, 6, 1)) == (
        "three_component"
    )
    assert select_component_variant(h9, short_interest_history_start=date(2014, 1, 1)) == (
        "three_component"
    )
    assert select_component_variant(h9, short_interest_history_start=date(2014, 1, 2)) == (
        "two_component"
    )


def test_h8_v3_is_a_filter_and_cannot_be_promoted() -> None:
    h8 = _load("h8")
    assert h8["role"] == "filter"
    assert h8["direction"] == "none"
    with pytest.raises(NotPromotableError):
        check_promotable(h8)
    check_promotable(_load("h9"))


def test_h8_v3_event_types_are_members_of_the_extraction_event_type_enum() -> None:
    tree = ast.parse(_EXTRACTOR.read_text(encoding="utf-8"))
    literal = next(
        node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "EventType" for t in node.targets)
    )
    assert isinstance(literal, ast.Subscript)
    assert isinstance(literal.slice, ast.Tuple)
    enum = {elt.value for elt in literal.slice.elts if isinstance(elt, ast.Constant)}

    event_types = set(_load("h8")["event_types"])
    assert event_types == {
        "trial_readout",
        "complete_response_letter",
        "clinical_hold",
        "trial_halted",
    }
    assert event_types <= enum


def test_hypothesis_family_without_budget_is_refused_by_evaluation(tmp_path: Path) -> None:
    config_dir, registry = _copy_config(tmp_path)
    h9 = _load("h9")
    h9["family"] = "options_panel"
    _register_edited(config_dir, registry, "h9", h9)
    evaluation = EvaluationProtocol(config_dir=config_dir, registry_path=registry)

    with pytest.raises(FamilyNotBudgetedError, match="options_panel"):
        evaluation.admit("h9")

    committed = EvaluationProtocol(config_dir=_CONFIG_DIR, registry_path=_REGISTRY)
    diagnostic = {**_load("h12"), "family": "options_panel"}
    with pytest.raises(FamilyNotBudgetedError, match="h12: family 'options_panel'"):
        committed.check_admissible(diagnostic)
    assert committed.admit("h9")["id"] == "h9"


def test_h9_declared_trial_cells_are_counted_against_the_holdings_budget(tmp_path: Path) -> None:
    protocol = _load("protocol")
    h9 = _load("h9")
    grid = h9["trial_grid"]
    assert len(grid["cadence"]) * len(grid["catalyst_guard"]) * len(grid["floor"]) == 32
    assert h9["trial_cells"] == 32
    assert h9["family"] == "holdings_panel"

    hypotheses = [_load(h) for h in _HYPOTHESIS_IDS]
    counts = count_trials(hypotheses, protocol)
    assert counts["holdings_panel"] == 36
    assert protocol["families"]["holdings_panel"]["budget_cells"] == 36
    check_trial_budgets(hypotheses, protocol)

    # The budget is spent: one more holdings cell is refused once H9 and the H10 filter count.
    evaluation = EvaluationProtocol(config_dir=_CONFIG_DIR, registry_path=_REGISTRY)
    with pytest.raises(TrialBudgetExceededError, match="holdings_panel"):
        evaluation.check_admissible({**h9, "id": "h13", "trial_grid": None, "trial_cells": 1})

    config_dir, registry = _copy_config(tmp_path)
    _register_edited(config_dir, registry, "h9", {**h9, "trial_cells": 31})
    with pytest.raises(HypothesisInvalidError, match="trial_cells"):
        verify_hypothesis("h9", config_dir=config_dir, registry_path=registry)


def test_h9_quarterly_trade_date_is_first_session_ten_days_after_13f_deadline() -> None:
    rule = _load("h9")["trade_date_rule"]
    calendar = MarketCalendar()

    # Q4 2023: deadline 2024-02-14; +10 days is Saturday 2024-02-24, so Monday the 26th.
    assert quarterly_trade_date(date(2023, 12, 31), rule, calendar) == date(2024, 2, 26)
    # Q1 2024: deadline 2024-05-15; +10 days is Saturday 05-25, Monday 05-27 is Memorial Day.
    assert quarterly_trade_date(date(2024, 3, 31), rule, calendar) == date(2024, 5, 28)
    # Q2 2024: deadline 2024-08-14; +10 days is Saturday 08-24, so Monday the 26th.
    assert quarterly_trade_date(date(2024, 6, 30), rule, calendar) == date(2024, 8, 26)
    # Q3 2024: deadline 2024-11-14; +10 days is Sunday 11-24, so Monday the 25th.
    assert quarterly_trade_date(date(2024, 9, 30), rule, calendar) == date(2024, 11, 25)

    with pytest.raises(ValueError, match="quarter end"):
        quarterly_trade_date(date(2024, 2, 29), rule, calendar)


def test_h10_in_biotech_is_a_filter_and_cannot_be_promoted() -> None:
    h10 = _load("h10")
    with pytest.raises(NotPromotableError):
        check_promotable(h10, use="biotech_exclusion_filter")
    check_promotable(h10, use="broad_small_mid")
    with pytest.raises(NotPromotableError, match="use"):
        check_promotable(h10)


def test_diagnostic_hypotheses_do_not_count_against_any_budget() -> None:
    protocol = _load("protocol")
    for h in ("h11", "h12"):
        assert _load(h)["role"] == "diagnostic"
    assert _load("h11")["family"] == "registry_panel"
    assert _load("h12")["family"] == "catalyst_panel"

    diagnostic = {
        "id": "d",
        "evaluation": "event",
        "family": "registry_panel",
        "role": "diagnostic",
        "trial_cells": 500,
    }
    assert count_trials([diagnostic], protocol) == {}
    check_trial_budgets([diagnostic], protocol)

    evaluation = EvaluationProtocol(config_dir=_CONFIG_DIR, registry_path=_REGISTRY)
    evaluation.check_admissible(diagnostic)
    with pytest.raises(TrialBudgetExceededError, match="registry_panel"):
        evaluation.check_admissible({**diagnostic, "role": "promotable", "trial_cells": 1})
    with pytest.raises(FamilyNotBudgetedError, match="registry_panel"):
        evaluation.check_admissible({**diagnostic, "role": "promotable", "trial_cells": 0})


def test_portfolio_forward_check_defines_a_data_gap_as_inputs_missing_before_open() -> None:
    protocol = _load("protocol")
    forward_check = next(k for k in protocol["kill_criteria"] if k["id"] == "forward_check")
    data_gap = forward_check["portfolio"]["data_gap"]
    assert set(data_gap["required_inputs"]) == {
        "score_snapshot",
        "universe_snapshot",
        "closing_prices",
    }
    assert data_gap["available_before"] == "session_open"

    from datetime import UTC, datetime

    session_open = datetime(2024, 2, 26, 14, 30, tzinfo=UTC)
    before = datetime(2024, 2, 26, 6, 0, tzinfo=UTC)
    after = datetime(2024, 2, 26, 15, 0, tzinfo=UTC)
    all_before = {"score_snapshot": before, "universe_snapshot": before, "closing_prices": before}

    assert not is_data_gap(session_open, all_before, protocol)
    assert is_data_gap(session_open, {**all_before, "closing_prices": after}, protocol)
    assert is_data_gap(session_open, {**all_before, "score_snapshot": session_open}, protocol)
    missing = {k: v for k, v in all_before.items() if k != "universe_snapshot"}
    assert is_data_gap(session_open, missing, protocol)

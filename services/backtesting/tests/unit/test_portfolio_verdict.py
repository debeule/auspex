import json
from datetime import date

import numpy as np
import pytest
import yaml
from portfolio_support import (
    PROTOCOL_YAML,
    RUN_START,
    evaluation_protocol,
    monthly_rule,
    plant_top_quintile_edge,
    registered_config,
    world,
)

from auspex_backtesting.hypothesis import HypothesisModifiedError
from auspex_backtesting.portfolio import (
    HoldoutAlreadyReadError,
    HoldoutRecord,
    HoldoutSealedError,
    PortfolioEvaluation,
    PortfolioEvidence,
    PortfolioVerdict,
    newey_west_t,
    write_report,
)

LAG = 6
PRIMARY = {"cadence": "monthly_top15", "catalyst_guard": "none"}


def with_t(target_t, n=96, seed=11):
    """A monthly series whose Newey-West t at the protocol lag is `target_t`."""
    noise = np.random.default_rng(seed).normal(0.0, 0.02, n)
    noise -= noise.mean()
    scale = newey_west_t(noise + 1.0, LAG) / 1.0  # t of a unit mean over the same noise
    return list(noise + target_t / scale)


def evidence(**overrides):
    fields = {
        "monthly_net_excess": [0.02 + 0.001 * ((-1) ** k) for k in range(96)],
        "monthly_gross_excess": [0.03] * 96,
        "quintile_spread": with_t(4.0),
        "top_quintile_net_excess_annual": 0.05,
        "yearly_cost_drag": 0.02,
        "unpriced_member_month_share": 0.02,
    }
    fields.update(overrides)
    return PortfolioEvidence(**fields)


def criterion(report, criterion_id):
    (verdict,) = [v for v in report.criteria if v.criterion_id == criterion_id]
    return verdict


@pytest.fixture
def verdict(tmp_path):
    config_dir, registry = registered_config(tmp_path)
    return PortfolioVerdict(evaluation_protocol(config_dir, registry), "h9")


def test_no_in_sample_spread_fires_below_registered_t_or_non_positive_top_quintile_excess(verdict):
    def fired(t, top):
        report = verdict.in_sample(
            evidence(quintile_spread=with_t(t), top_quintile_net_excess_annual=top),
            n_trials=4,
            is_primary_cell=True,
        )
        return criterion(report, "no_in_sample_spread").fired

    assert newey_west_t(with_t(1.9), LAG) == pytest.approx(1.9)
    assert fired(1.9, 0.02)
    assert fired(2.5, -0.005)
    assert not fired(2.5, 0.02)


def test_turnover_cost_fires_when_cost_drag_exceeds_half_of_gross_excess(verdict):
    gross = [0.10 / 12] * 96
    heavy = verdict.in_sample(
        evidence(monthly_gross_excess=gross, yearly_cost_drag=0.06),
        n_trials=4,
        is_primary_cell=True,
    )
    light = verdict.in_sample(
        evidence(monthly_gross_excess=gross, yearly_cost_drag=0.04),
        n_trials=4,
        is_primary_cell=True,
    )
    assert criterion(heavy, "turnover_cost").fired
    assert heavy.status == "killed"
    assert heavy.killed_by == "turnover_cost"
    assert not criterion(light, "turnover_cost").fired


def test_survivorship_marks_result_not_usable_above_unpriced_member_month_share(verdict):
    patchy = verdict.in_sample(
        evidence(unpriced_member_month_share=0.12), n_trials=4, is_primary_cell=True
    )
    covered = verdict.in_sample(
        evidence(unpriced_member_month_share=0.08), n_trials=4, is_primary_cell=True
    )
    assert criterion(patchy, "survivorship").fired
    assert patchy.status == "not_usable"
    assert not criterion(covered, "survivorship").fired
    assert covered.status == "in_sample_passed"


def test_portfolio_deflated_sharpe_uses_monthly_returns_and_family_trial_count(verdict):
    monthly = list(np.random.default_rng(2).normal(0.004, 0.02, 96))
    few = verdict.in_sample(evidence(monthly_net_excess=monthly), n_trials=4, is_primary_cell=True)
    many = verdict.in_sample(
        evidence(monthly_net_excess=monthly), n_trials=36, is_primary_cell=True
    )
    assert many.deflated_sharpe < few.deflated_sharpe
    assert few.n_trials == 4 and many.n_trials == 36


def test_promotion_requires_deflated_sharpe_minimum_and_no_in_sample_kill_on_primary_cell(verdict):
    strong = verdict.in_sample(evidence(), n_trials=4, is_primary_cell=True)
    assert strong.deflated_sharpe >= 0.95
    assert strong.status == "in_sample_passed"
    assert (
        verdict.in_sample(evidence(), n_trials=4, is_primary_cell=False).status == "not_promotable"
    )

    weak = list(np.random.default_rng(2).normal(0.001, 0.03, 96))
    low = verdict.in_sample(evidence(monthly_net_excess=weak), n_trials=36, is_primary_cell=True)
    assert low.deflated_sharpe < 0.95
    assert low.status == "not_promotable"

    killed = verdict.in_sample(
        evidence(quintile_spread=with_t(1.0)), n_trials=4, is_primary_cell=True
    )
    assert killed.status == "killed"
    assert killed.killed_by == "no_in_sample_spread"


def test_filter_use_is_never_promotable(tmp_path):
    config_dir, registry = registered_config(tmp_path, with_filter=True)
    protocol = evaluation_protocol(config_dir, registry)
    report = PortfolioVerdict(protocol, "h10", "biotech_exclusion_filter").in_sample(
        evidence(), n_trials=4, is_primary_cell=True
    )
    assert report.status == "not_promotable"
    with pytest.raises(HoldoutSealedError):
        PortfolioVerdict(protocol, "h10", "biotech_exclusion_filter").holdout(report, [0.02] * 12)


class Pinned:
    def missing(self, keys):
        return []


def _stable_edge_world():
    """Scores never change, and the top quintile earns 1% a month over the universe: a real,
    low-turnover edge that should pass in-sample and in the holdout."""
    w = world(100, score_fn=lambda i, d: -float(i))
    plant_top_quintile_edge(w, 0.01, RUN_START, date(2022, 12, 31))
    return w


def test_holdout_sealed_until_in_sample_verdict_passes_then_read_once(tmp_path):
    config_dir, registry = registered_config(tmp_path)
    protocol = evaluation_protocol(config_dir, registry)
    record = HoldoutRecord(tmp_path / "holdout")
    evaluation = PortfolioEvaluation(protocol, _stable_edge_world().engine(), Pinned(), record)

    trial = evaluation.run("h9", PRIMARY, monthly_rule(), 1, [10_000.0])
    assert trial.verdict.status == "in_sample_passed"
    assert trial.verdict.n_trials == protocol.ledger().family_trial_count("holdings_panel") == 1
    assert not trial.holdout and not record.was_read("h9", None)

    final = evaluation.run("h9", PRIMARY, monthly_rule(), 1, [10_000.0, 50_000.0], final=True)
    assert final.verdict.status == "promoted"
    assert final.verdict.holdout_read
    assert set(final.holdout) == {10_000.0, 50_000.0}
    assert final.holdout[10_000.0].months[0].month == "2022-01"
    assert record.was_read("h9", None)
    with pytest.raises(HoldoutAlreadyReadError):
        evaluation.run("h9", PRIMARY, monthly_rule(), 1, [10_000.0], final=True)

    other_dir = tmp_path / "noedge"
    other_dir.mkdir()
    config_dir, registry = registered_config(other_dir)
    sealed = HoldoutRecord(other_dir / "holdout")
    no_edge = PortfolioEvaluation(
        evaluation_protocol(config_dir, registry), world(100).engine(), Pinned(), sealed
    )
    failed = no_edge.run("h9", PRIMARY, monthly_rule(), 1, [10_000.0], final=True)
    assert failed.verdict.status == "killed"
    assert not failed.holdout and not sealed.was_read("h9", None)


def test_holdout_check_fires_below_registered_net_excess_or_t_and_kills(verdict):
    passed = verdict.in_sample(evidence(), n_trials=4, is_primary_cell=True)
    small = verdict.holdout(passed, [0.005 / 12 + 0.0001 * ((-1) ** k) for k in range(48)])
    noisy = verdict.holdout(passed, with_t(1.2, n=48))
    good = verdict.holdout(passed, [0.03 / 12 + 0.0005 * ((-1) ** k) for k in range(48)])
    assert small.status == "killed" and small.killed_by == "holdout_check"
    assert noisy.status == "killed"
    assert criterion(noisy, "holdout_check").inputs["annual_net_excess"] > 0.01
    assert good.status == "promoted"
    assert not criterion(good, "holdout_check").fired


def test_kill_thresholds_come_from_registered_protocol(tmp_path):
    stricter = yaml.safe_load(PROTOCOL_YAML)
    spread = next(
        c for c in stricter["portfolio_kill_criteria"] if c["id"] == "no_in_sample_spread"
    )
    spread["min_top_minus_bottom_quintile_newey_west_t"] = 3.0
    strict_dir = tmp_path / "strict"
    strict_dir.mkdir()
    config_dir, registry = registered_config(strict_dir, yaml.safe_dump(stricter, sort_keys=False))
    strict = PortfolioVerdict(evaluation_protocol(config_dir, registry), "h9")

    plain_dir = tmp_path / "plain"
    plain_dir.mkdir()
    plain_config, plain_registry = registered_config(plain_dir)
    plain = PortfolioVerdict(evaluation_protocol(plain_config, plain_registry), "h9")

    middling = evidence(quintile_spread=with_t(2.5))
    assert criterion(
        strict.in_sample(middling, n_trials=4, is_primary_cell=True), "no_in_sample_spread"
    ).fired
    assert not criterion(
        plain.in_sample(middling, n_trials=4, is_primary_cell=True), "no_in_sample_spread"
    ).fired

    protocol_file = plain_config / "protocol.yaml"
    protocol_file.write_text(
        protocol_file.read_text(encoding="utf-8") + "\n# edited\n", encoding="utf-8"
    )
    with pytest.raises(HypothesisModifiedError):
        PortfolioVerdict(evaluation_protocol(plain_config, plain_registry), "h9")


def test_report_and_verdict_are_written_side_by_side_as_json(tmp_path):
    config_dir, registry = registered_config(tmp_path)
    protocol = evaluation_protocol(config_dir, registry)
    evaluation = PortfolioEvaluation(
        protocol, world(100).engine(), Pinned(), HoldoutRecord(tmp_path / "h")
    )
    report = evaluation.run("h9", PRIMARY, monthly_rule(), 1, [10_000.0, 50_000.0], run_id="run-1")
    report_path, verdict_path = write_report(report, tmp_path / "out")
    assert report_path.name == "h9-run-1.json"
    assert verdict_path.name == "h9-run-1-verdict.json"
    body = json.loads(report_path.read_text(encoding="utf-8"))
    assert set(body["in_sample"]) == {"10000.0", "50000.0"}
    assert len(body["in_sample"]["10000.0"]["months"]) == 24
    verdict = json.loads(verdict_path.read_text(encoding="utf-8"))
    assert verdict["status"] == report.verdict.status
    assert {c["criterion_id"] for c in verdict["criteria"]} == {
        "no_in_sample_spread",
        "turnover_cost",
        "survivorship",
    }

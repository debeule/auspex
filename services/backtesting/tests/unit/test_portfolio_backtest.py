from dataclasses import replace
from datetime import date, timedelta

import numpy as np
import pytest
from portfolio_support import (
    CALENDAR,
    COSTS,
    FILTER,
    RUN_END,
    RUN_START,
    SCORE,
    SESSIONS,
    Binary,
    Catalysts,
    cik,
    evaluation_protocol,
    first_sessions,
    h9_quarterly_rule,
    member,
    monthly_rule,
    plant_top_quintile_edge,
    registered_config,
    ticker,
    utc,
    world,
    zigzag,
)

from auspex_backtesting.market_sim import CostModel, CostParameters
from auspex_backtesting.portfolio import (
    EqualRiskSizer,
    HoldoutAlreadyReadError,
    HoldoutRecord,
    InputsNotPinnedError,
    InsufficientNamesError,
    NoInputManifests,
    PortfolioEvaluation,
    PortfolioEvidence,
    PortfolioVerdict,
    ScoreLookaheadError,
    newey_west_t,
)
from auspex_backtesting.protocol import quarterly_trade_date

TOP_QUINTILE = monthly_rule(selection="top_quintile")


def _mean(values):
    return float(np.mean(list(values)))


def _cost_fractions(result):
    return [m.cost_usd / m.start_value_usd for m in result.months]


def _run(w, rule, tier=250_000.0, start=RUN_START, end=RUN_END, **engine):
    return w.engine(**engine).run(rule, 1, tier, start, end)


def test_planted_monthly_edge_is_recovered_net_of_costs():
    w = world(100)
    plant_top_quintile_edge(w, 0.01, RUN_START, RUN_END)
    result = _run(w, TOP_QUINTILE)
    costs = _mean(_cost_fractions(result))
    assert costs > 0.003
    assert _mean(m.gross_return for m in result.months) == pytest.approx(0.01, abs=0.0015)
    assert _mean(m.net_return for m in result.months) == pytest.approx(0.01 - costs, abs=0.0015)


def test_no_edge_universe_returns_minus_costs():
    result = _run(world(100), TOP_QUINTILE)
    excess = _mean(m.excess_over_universe_ew for m in result.months)
    costs = _mean(_cost_fractions(result))
    assert excess < 0
    assert excess == pytest.approx(-costs, abs=0.002)


def test_score_known_at_or_after_rebalance_open_is_rejected():
    d = date(2020, 3, 2)
    opens = CALENDAR.session_open(d)
    w = world(20)
    w.scores.put(SCORE, d, {cik(i): float(i) for i in range(20)}, known_at=opens)
    snapshot = w.scores.read(SCORE.hypothesis_id, SCORE.version, d)
    with pytest.raises(ScoreLookaheadError):
        snapshot.validate(CALENDAR)
    with pytest.raises(ScoreLookaheadError):
        _run(w, TOP_QUINTILE, start=date(2020, 3, 1), end=date(2020, 4, 30))

    w.scores.put(
        SCORE, d, {cik(i): float(i) for i in range(20)}, known_at=opens - timedelta(seconds=1)
    )
    w.scores.read(SCORE.hypothesis_id, SCORE.version, d).validate(CALENDAR)


def test_orders_fill_at_first_session_open_after_rebalance_date():
    w = world(100)
    result = _run(w, TOP_QUINTILE, start=date(2020, 1, 1), end=date(2020, 2, 28))
    first = result.decisions[0]
    assert first.decision_date == date(2020, 1, 2)
    assert first.fill_date == date(2020, 1, 3)
    opening = [t for t in result.trades if t.session <= first.fill_date]
    assert len(opening) == 20
    for trade in opening:
        assert trade.session == date(2020, 1, 3)
        frame = w.prices.frames[trade.ticker]
        assert trade.price_usd == frame.loc[frame.index.date == date(2020, 1, 3), "open"].iloc[0]


def test_exclude_bottom_quintile_turns_over_less_than_top_quintile():
    w = world(100)
    top = _run(w, TOP_QUINTILE)
    broad = _run(w, monthly_rule(selection="exclude_bottom_quintile"), max_weight=0.05)
    assert sum(m.turnover for m in broad.months) < sum(m.turnover for m in top.months)
    assert _mean(_cost_fractions(broad)) < _mean(_cost_fractions(top))


def test_equal_risk_weights_are_inverse_trailing_volatility_capped_at_ceiling():
    vols = {f"N{i}": 0.02 for i in range(30)}
    vols["LOW"] = 0.002
    weights = EqualRiskSizer(0.05, 15).weights(vols).weights
    assert weights["LOW"] == pytest.approx(0.05)
    others = [weights[f"N{i}"] for i in range(30)]
    assert others == pytest.approx([0.95 / 30] * 30)

    uncapped = (
        EqualRiskSizer(0.05, 15)
        .weights({**{f"A{i}": 0.01 for i in range(20)}, **{f"B{i}": 0.04 for i in range(20)}})
        .weights
    )
    assert uncapped["A0"] == pytest.approx(4 * uncapped["B0"])
    assert sum(uncapped.values()) == pytest.approx(1.0)

    mixed = (
        EqualRiskSizer(0.05, 15)
        .weights({**{f"A{i}": 0.01 for i in range(10)}, **{f"B{i}": 0.05 for i in range(30)}})
        .weights
    )
    assert mixed["A0"] == pytest.approx(0.05)
    assert mixed["B0"] == pytest.approx(0.5 / 30)


def test_equal_risk_sizer_refuses_fewer_than_minimum_names():
    with pytest.raises(InsufficientNamesError):
        EqualRiskSizer(0.05, 15).weights({f"N{i}": 0.02 for i in range(14)})


def test_equal_risk_weights_never_exceed_the_ceiling_and_the_rest_is_cash():
    fifteen = EqualRiskSizer(0.05, 15).weights({f"N{i}": 0.02 for i in range(15)})
    assert list(fifteen.weights.values()) == pytest.approx([0.05] * 15)
    assert fifteen.cash == pytest.approx(0.25)

    rng = np.random.default_rng(3)
    many = EqualRiskSizer(0.05, 15).weights(
        {f"N{i}": float(v) for i, v in enumerate(rng.uniform(0.01, 0.05, 25))}
    )
    assert sum(many.weights.values()) == pytest.approx(1.0)
    assert max(many.weights.values()) <= 0.05 + 1e-12
    assert many.cash == pytest.approx(0.0, abs=1e-12)


def test_trailing_volatility_uses_only_sessions_before_rebalance():
    rule = monthly_rule(enter_rank=5, exit_rank=5)
    start, end = date(2020, 1, 1), date(2020, 3, 31)
    calm = world(8, score_fn=lambda i, d: -i)
    spiked = world(8, score_fn=lambda i, d: -i)
    decision = date(2020, 2, 3)
    returns = zigzag(len(SESSIONS), 0)
    k = SESSIONS.index(decision)
    returns[k : k + 10] = [0.4, -0.4] * 5
    spiked.set_returns(0, returns)
    a = _run(calm, rule, start=start, end=end, max_weight=0.5, min_names=3)
    b = _run(spiked, rule, start=start, end=end, max_weight=0.5, min_names=3)
    assert a.decisions[1].decision_date == decision
    assert b.decisions[1].weights == pytest.approx(a.decisions[1].weights)
    assert b.decisions[2].weights[ticker(0)] < a.decisions[2].weights[ticker(0)]


def _ending(w, i, last_day):
    frame = w.prices.frames[ticker(i)]
    w.prices.frames[ticker(i)] = frame[frame.index.date <= last_day]
    later = {
        d.strftime("%Y-%m") for d in SESSIONS if d.strftime("%Y-%m") > last_day.strftime("%Y-%m")
    }
    for month in later:
        w.universe.excluded.setdefault(month, set()).add(cik(i))


def test_member_delisted_mid_month_is_closed_at_last_close():
    w = world(4, score_fn=lambda i, d: -i)
    last_day = date(2020, 6, 15)
    w.universe.members[0] = member(0, exited_on=date(2020, 6, 16), exit_reason="acquired")
    _ending(w, 0, last_day)
    result = _run(
        w,
        monthly_rule(enter_rank=3, exit_rank=3),
        start=RUN_START,
        end=date(2020, 9, 30),
        max_weight=0.34,
        min_names=3,
    )
    (closeout,) = result.closeouts
    last_close = w.prices.frames[ticker(0)]["close"].iloc[-1]
    assert closeout.ticker == ticker(0)
    assert closeout.last_date == last_day
    assert closeout.price_usd == pytest.approx(last_close)
    assert not closeout.delisting_bound
    assert result.delisting_bound_months == ()


def test_delisting_with_missing_tail_is_booked_at_minus_thirty_percent_and_flagged():
    w = world(4, score_fn=lambda i, d: -i)
    w.universe.members[0] = member(0, exited_on=date(2020, 8, 31), exit_reason="delisted")
    _ending(w, 0, date(2020, 6, 15))
    result = _run(
        w,
        monthly_rule(enter_rank=3, exit_rank=3),
        start=RUN_START,
        end=date(2020, 9, 30),
        max_weight=0.34,
        min_names=3,
    )
    (closeout,) = result.closeouts
    assert closeout.delisting_bound
    assert closeout.price_usd == pytest.approx(0.7 * closeout.last_close_usd)
    assert result.delisting_bound_months == ("2020-06",)


def test_members_without_catalyst_data_are_counted_not_assumed_clear():
    w = world(6, score_fn=lambda i, d: -i)
    far = date(2025, 1, 15)
    w.catalysts = Catalysts([Binary(cik(i), far, far, utc(date(2019, 1, 2))) for i in (0, 1)])
    rule = monthly_rule(enter_rank=4, exit_rank=4, catalyst_guard="skip_entry")
    result = _run(w, rule, start=RUN_START, end=date(2020, 2, 28), max_weight=0.25, min_names=3)
    guard = result.decisions[0].guard
    assert guard.members_without_catalyst_data == 4
    assert guard.checked == 4
    assert guard.clear == 2
    assert guard.no_data == 2
    assert guard.binary == 0


def test_tiered_pricing_charges_less_than_fixed_on_a_small_ticket():
    fixed = CostModel(COSTS)
    tiered = CostModel(COSTS.with_overrides(pricing="tiered"))
    shares, price = 36, 20.0
    assert tiered.commission_usd(shares) < fixed.commission_usd(shares)
    assert tiered.commission_usd(shares) == pytest.approx(max(0.35, 0.0035 * 36) + 0.0032 * 36)
    assert float(tiered.leg_cost_usd("T000", price, shares)) < float(
        fixed.leg_cost_usd("T000", price, shares)
    )
    assert tiered.commission_usd(2_000) > fixed.commission_usd(2_000)


def test_ticket_below_commission_minimum_is_skipped_and_counted():
    w = world(100)
    result = _run(w, TOP_QUINTILE, tier=1_500.0, start=date(2020, 1, 1), end=date(2020, 2, 28))
    assert CostModel(COSTS).min_ticket_usd() == pytest.approx(100.0)
    assert result.trades == ()
    assert result.skipped_tickets == sum(len(d.weights) for d in result.decisions) == 40


def test_result_reports_excess_over_xbi_and_universe_equal_weight():
    w = world(30)
    for i in range(0, 30, 3):
        w.set_returns(i, zigzag(len(SESSIONS), i) + 0.002)
    result = _run(w, monthly_rule(), start=RUN_START, end=date(2020, 6, 30))
    march = next(m for m in result.months if m.month == "2020-03")

    def close(t, d):
        frame = w.prices.frames[t]
        return frame.loc[frame.index.date == d, "close"].iloc[0]

    base, end = date(2020, 2, 28), date(2020, 3, 31)
    assert march.xbi_return == pytest.approx(close("XBI", end) / close("XBI", base) - 1)
    ew = np.mean([close(ticker(i), end) / close(ticker(i), base) - 1 for i in range(30)])
    assert abs(ew) > 0.005
    assert march.universe_ew_return == pytest.approx(ew)
    assert march.excess_over_xbi == pytest.approx(march.net_return - march.xbi_return)
    assert march.excess_over_universe_ew == pytest.approx(march.net_return - ew)
    assert march.cash_share == pytest.approx(0.25, abs=0.01)
    assert march.excess_over_invested_universe_ew == pytest.approx(
        march.net_return - march.invested_share * ew
    )


def test_newey_west_t_uses_protocol_lag(tmp_path):
    config_dir, registry = registered_config(tmp_path)
    verdict = PortfolioVerdict(evaluation_protocol(config_dir, registry), "h9")
    rng = np.random.default_rng(5)
    noise = rng.normal(0, 0.01, 60)
    series = list(0.003 + np.convolve(noise, np.ones(4) / 2, mode="same"))
    evidence = PortfolioEvidence(series, series, series, 0.02, 0.0, 0.0)
    report = verdict.in_sample(evidence, n_trials=4, is_primary_cell=True)
    assert report.newey_west_t == pytest.approx(newey_west_t(series, 6))
    assert report.newey_west_t != pytest.approx(newey_west_t(series, 0))


class Pinned:
    def missing(self, keys):
        return []


def _evaluation(tmp_path, w, manifests):
    config_dir, registry = registered_config(tmp_path)
    protocol = evaluation_protocol(config_dir, registry)
    record = HoldoutRecord(tmp_path / "holdout")
    return PortfolioEvaluation(protocol, w.engine(), manifests, record), protocol, record


PRIMARY = {"cadence": "monthly_top15", "catalyst_guard": "none"}


def test_holdout_cannot_be_read_twice(tmp_path):
    record = HoldoutRecord(tmp_path / "once")
    record.claim("h9", None, "run-1")
    with pytest.raises(HoldoutAlreadyReadError):
        record.claim("h9", None, "run-2")

    evaluation, protocol, holdout = _evaluation(tmp_path, world(100), Pinned())
    holdout.claim("h9", None, "earlier")
    with pytest.raises(HoldoutAlreadyReadError):
        evaluation.run("h9", PRIMARY, monthly_rule(), 1, [10_000.0], final=True)
    assert protocol.ledger().family_trial_count("holdings_panel") == 0


def test_final_run_over_a_snapshot_without_an_input_manifest_is_refused(tmp_path):
    w = world(100)
    reads = []
    original = w.scores.read
    w.scores.read = lambda *a: reads.append(a) or original(*a)
    evaluation, protocol, holdout = _evaluation(tmp_path, w, NoInputManifests())
    with pytest.raises(InputsNotPinnedError):
        evaluation.run("h9", PRIMARY, monthly_rule(), 1, [10_000.0], final=True)
    assert not holdout.was_read("h9", None)
    assert protocol.ledger().family_trial_count("holdings_panel") == 0
    assert reads == []


def test_backtest_is_deterministic_for_identical_inputs():
    a = _run(world(60, seed=4), monthly_rule())
    b = _run(world(60, seed=4), monthly_rule())
    assert a.months == b.months
    assert a.trades == b.trades
    assert a.decisions == b.decisions


def test_each_capital_tier_is_costed_separately():
    w = world(100)
    small = _run(w, TOP_QUINTILE, tier=10_000.0)
    large = _run(w, TOP_QUINTILE, tier=250_000.0)
    assert small.capital_usd == pytest.approx(12_500.0)
    assert large.capital_usd == pytest.approx(312_500.0)
    small_share = small.cost_by_component["commission"] / sum(small.cost_by_component.values())
    large_share = large.cost_by_component["commission"] / sum(large.cost_by_component.values())
    assert small_share > 2 * large_share
    assert _mean(_cost_fractions(small)) > _mean(_cost_fractions(large))


def _rank_path(ranks_by_month):
    """Name 39's rank per month; the others rank by index."""

    def score(i, d):
        if i != 39:
            return -float(i)
        rank = ranks_by_month.get(d.strftime("%Y-%m"), 40)
        return -(rank - 1) + 0.5

    return score


def test_hold_band_keeps_a_name_until_it_falls_below_exit_rank():
    w = world(40, score_fn=_rank_path({"2020-01": 10, "2020-02": 25, "2020-03": 35}))
    result = _run(
        w, monthly_rule(enter_rank=15, exit_rank=30), start=RUN_START, end=date(2020, 3, 31)
    )
    held = [ticker(39) in d.weights for d in result.decisions]
    assert held == [True, True, False]
    position, closed_on = 0, []
    for trade in (t for t in result.trades if t.ticker == ticker(39)):
        position += trade.shares
        if position == 0:
            closed_on.append(trade.session)
    assert closed_on == [result.decisions[2].fill_date]


def test_hard_cut_turns_over_more_than_hold_band_on_the_same_scores():
    w = world(60)
    cut = _run(w, monthly_rule(enter_rank=15, exit_rank=15))
    band = _run(w, monthly_rule(enter_rank=15, exit_rank=30))
    assert sum(m.turnover for m in cut.months) > sum(m.turnover for m in band.months)


def test_quarterly_trade_date_is_first_session_offset_days_after_13f_deadline():
    rule = h9_quarterly_rule()
    dates = rule.decision_dates(date(2021, 1, 1), date(2021, 12, 31), CALENDAR)
    assert dates == [date(2021, 2, 24), date(2021, 5, 25), date(2021, 8, 24), date(2021, 11, 24)]
    assert dates[1] == quarterly_trade_date(date(2021, 3, 31), dict(rule.trade_date_rule), CALENDAR)
    semi = replace(rule, cadence="semi_annual_after_13f")
    assert semi.decision_dates(date(2021, 1, 1), date(2021, 12, 31), CALENDAR) == [
        date(2021, 2, 24),
        date(2021, 8, 24),
    ]


def test_scores_newer_than_last_trade_date_do_not_trade_before_next_cadence_date():
    w = world(60)
    result = _run(w, h9_quarterly_rule(catalyst_guard="none"))
    fills = {d.fill_date for d in result.decisions}
    assert len(fills) == 8
    assert {t.session for t in result.trades} <= fills
    assert result.decisions[1].score_date == date(2020, 5, 1)


def _two_month_guard(w, rule, **engine):
    return _run(w, rule, start=RUN_START, end=date(2020, 2, 28), **engine)


def test_skip_entry_guard_skips_buy_but_keeps_held_name_through_binary():
    w = world(6, score_fn=lambda i, d: 10.0 if i == 3 and d.month == 2 else -i)
    known = utc(date(2020, 1, 15))
    w.catalysts = Catalysts(
        [Binary(cik(i), date(2020, 2, 18), date(2020, 2, 18), known) for i in (0, 3)]
    )
    rule = monthly_rule(enter_rank=3, exit_rank=4, catalyst_guard="skip_entry")
    result = _two_month_guard(w, rule, max_weight=0.34, min_names=3)
    february = result.decisions[1]
    assert february.guard.skipped == (cik(3),)
    assert ticker(3) not in february.weights
    assert ticker(0) in february.weights
    assert not [t for t in result.trades if t.ticker == ticker(0) and t.shares < 0]


def test_exit_and_reenter_guard_books_an_extra_round_trip():
    w = world(4, score_fn=lambda i, d: -i)
    w.catalysts = Catalysts(
        [Binary(cik(0), date(2020, 2, 18), date(2020, 2, 18), utc(date(2020, 1, 15)))]
    )
    rule = monthly_rule(enter_rank=3, exit_rank=3, catalyst_guard="exit_and_reenter")
    guarded = _two_month_guard(w, rule, max_weight=0.34, min_names=3)
    plain = _two_month_guard(w, replace(rule, catalyst_guard="none"), max_weight=0.34, min_names=3)
    moves = [
        (t.session, t.reason)
        for t in guarded.trades
        if t.ticker == ticker(0) and t.reason != "rebalance"
    ]
    assert moves == [(date(2020, 2, 14), "guard_exit"), (date(2020, 2, 19), "guard_reentry")]
    assert guarded.decisions[1].guard.exited == (cik(0),)
    assert sum(guarded.cost_by_component.values()) > sum(plain.cost_by_component.values())
    assert len(guarded.trades) == len(plain.trades) + 2


def test_exit_low_score_only_guard_exits_only_names_outside_entry_band():
    def score(i, d):
        if d.month == 2:
            return {0: 10.0, 2: 9.0, 1: 8.0}.get(i, -i)
        return -float(i)

    w = world(5, score_fn=score)
    known = utc(date(2020, 1, 15))
    w.catalysts = Catalysts(
        [Binary(cik(i), date(2020, 2, 18), date(2020, 2, 18), known) for i in (0, 1)]
    )
    rule = monthly_rule(enter_rank=2, exit_rank=4, catalyst_guard="exit_low_score_only")
    result = _two_month_guard(w, rule, max_weight=0.5, min_names=2)
    assert result.decisions[1].ranks[cik(1)] == 3
    assert result.decisions[1].guard.exited == (cik(1),)
    exits = [t.ticker for t in result.trades if t.reason == "guard_exit"]
    assert exits == [ticker(1)]


def test_exclusion_filter_sells_held_name_at_next_trade_date():
    w = world(6, score_fn=lambda i, d: -i)
    for d in first_sessions(date(2019, 12, 1), date(2020, 3, 1)):
        bottom = 0 if d >= date(2020, 2, 1) else 5
        w.scores.put(FILTER, d, {cik(i): (-100.0 if i == bottom else float(i)) for i in range(6)})
    rule = monthly_rule(enter_rank=4, exit_rank=4, exclusion=FILTER)
    result = _two_month_guard(w, rule, max_weight=0.34, min_names=3)
    assert ticker(0) in result.decisions[0].weights
    assert result.decisions[1].excluded_by_filter == (cik(0),)
    sells = [t for t in result.trades if t.ticker == ticker(0) and t.shares < 0]
    assert [t.session for t in sells] == [result.decisions[1].fill_date]
    bought = sum(t.shares for t in result.trades if t.ticker == ticker(0) and t.shares > 0)
    assert -sells[0].shares == bought


def test_result_reports_average_holding_period_and_yearly_cost_drag():
    w = world(20, score_fn=lambda i, d: -i)
    result = _run(w, monthly_rule(selection="exclude_bottom_quintile"), max_weight=0.1)
    first_fill = result.decisions[0].fill_date
    held_days = (CALENDAR.sessions_between(first_fill, RUN_END)[-1] - first_fill).days
    assert result.average_holding_days == pytest.approx(held_days, rel=0.02)
    assert set(result.holding_days_by_name) == {ticker(i) for i in range(16)}
    years = (CALENDAR.sessions_between(first_fill, RUN_END)[-1] - first_fill).days / 365.25
    mean_value = _mean(m.end_value_usd for m in result.months)
    total_cost = sum(m.cost_usd for m in result.months)
    assert result.yearly_cost_drag == pytest.approx(total_cost / mean_value / years)
    assert result.yearly_cost_drag == pytest.approx(
        result.average_round_trip_cost * result.round_trips_per_year
    )


def test_catalyst_window_returns_are_split_from_other_days():
    w = world(4, score_fn=lambda i, d: -i)
    binary = date(2020, 6, 15)
    returns = zigzag(len(SESSIONS), 0)
    returns[SESSIONS.index(binary)] += np.log(1.2)
    w.set_returns(0, returns)
    w.catalysts = Catalysts([Binary(cik(0), binary, binary, utc(date(2020, 5, 1)))])
    result = _run(
        w,
        monthly_rule(enter_rank=3, exit_rank=3),
        start=RUN_START,
        end=date(2020, 9, 30),
        max_weight=0.34,
        min_names=3,
    )
    assert result.catalyst_window_days == 11
    assert result.catalyst_window_return == pytest.approx(0.2 / 3, abs=0.02)
    assert abs(result.other_days_return) < 0.03
    assert result.other_days > 100


def test_fx_fee_defaults_to_zero_and_min_half_spread_to_ten_bps():
    defaults = CostParameters.from_env({})
    assert defaults.fx_fee_rate == 0.0
    assert defaults.min_half_spread_bps == 10.0
    assert defaults.pricing == "fixed"
    assert CostParameters.from_env({"IBKR_PRICING": "tiered"}).pricing == "tiered"
    with pytest.raises(ValueError):
        CostParameters.from_env({"IBKR_PRICING": "flat"})

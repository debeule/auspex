import json
import shutil
from dataclasses import fields
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from auspex_backtesting.hypothesis import HypothesisModifiedError
from auspex_backtesting.market_sim import CostModel, CostParameters
from auspex_backtesting.short_interest.model import ShortInterestRecord

from auspex_strategy.__main__ import main as cli
from auspex_strategy.models import Direction
from auspex_strategy.risk import (
    BookState,
    KellyEstimates,
    KillSwitch,
    LimitAboveCeilingError,
    LimitMissingError,
    PanelCatalysts,
    RiskLimits,
    ShortInterestView,
    StoreShortInterest,
    ThemeMap,
)
from auspex_strategy.runtime import MinioObjectStore, StreamingRuntime
from auspex_strategy.testing import InMemoryObjectStore, StaticCatalysts

from .risk_fakes import (
    AS_OF,
    REPO_ROOT,
    closed_trades,
    held,
    intent,
    known_catalyst,
    limits,
    limits_env,
    manager,
    market,
)
from .runtime_fakes import (
    FixedClock,
    broker,
    flat_bars,
    long_on_trigger,
    ohlcv,
    signal,
    slot,
    utc,
)
from .s3_fake import FakeS3

_PROTOCOL_DIR = REPO_ROOT / "config" / "hypotheses"
_ENV_NAMES = [f.name.upper() for f in fields(RiskLimits) if f.name != "shorts_enabled"]


class _ShortInterest:
    def __init__(self, view: ShortInterestView | None) -> None:
        self._view = view

    def view(self, ticker: str, as_of: date) -> ShortInterestView | None:
        return self._view


# Limits from .env and the protocol ceilings


@pytest.mark.parametrize("name", _ENV_NAMES)
def test_each_limit_is_read_from_env(name: str) -> None:
    env = limits_env()
    # A value distinct from every other limit, and within the protocol ceilings.
    env[name] = {
        "MIN_TRADES_FOR_KELLY": "37",
        "MAX_POSITIONS_PER_THEME": "0",
        "MAX_POSITIONS_PER_STRATEGY": "7",
        "CATALYST_GUARD_DAYS": "6",
    }.get(name, "0.0123")

    loaded = RiskLimits.from_env(env, protocol_dir=_PROTOCOL_DIR)

    assert getattr(loaded, name.lower()) == pytest.approx(float(env[name]))


@pytest.mark.parametrize("name", _ENV_NAMES)
def test_each_missing_limit_fails_startup_naming_it(name: str) -> None:
    env = limits_env()
    del env[name]

    with pytest.raises(LimitMissingError, match=name):
        RiskLimits.from_env(env, protocol_dir=_PROTOCOL_DIR)


def test_unparseable_limit_fails_startup_naming_it() -> None:
    with pytest.raises(LimitMissingError, match="MAX_DRAWDOWN_PCT"):
        RiskLimits.from_env(limits_env(MAX_DRAWDOWN_PCT="ten"), protocol_dir=_PROTOCOL_DIR)


@pytest.mark.parametrize(("name", "value", "ceiling"), [
    ("FALLBACK_POSITION_PCT", "0.06", "0.05"),
    ("MAX_POSITIONS_PER_THEME", "2", "1"),
    ("MIN_TRADES_FOR_KELLY", "10", "20"),
])
def test_limit_looser_than_protocol_fails_startup(name: str, value: str, ceiling: str) -> None:
    with pytest.raises(LimitAboveCeilingError) as excinfo:
        RiskLimits.from_env(limits_env(**{name: value}), protocol_dir=_PROTOCOL_DIR)

    assert name in str(excinfo.value)
    assert ceiling in str(excinfo.value)


def test_limits_at_the_protocol_ceilings_load() -> None:
    env = limits_env(KELLY_FRACTION="0.25", MAX_POSITION_PCT="0.05", MIN_TRADES_FOR_KELLY="20",
                     FALLBACK_POSITION_PCT="0.05", MAX_POSITIONS_PER_THEME="1")

    loaded = RiskLimits.from_env(env, protocol_dir=_PROTOCOL_DIR)

    assert loaded.kelly_fraction == 0.25
    assert loaded.max_position_pct == 0.05


def test_shorts_follow_the_protocol_instruments_ceiling() -> None:
    assert RiskLimits.from_env(limits_env(), protocol_dir=_PROTOCOL_DIR).shorts_enabled is False


def test_modified_protocol_fails_startup(tmp_path: Path) -> None:
    shutil.copy(_PROTOCOL_DIR / "protocol.yaml", tmp_path / "protocol.yaml")
    shutil.copy(_PROTOCOL_DIR / "registry.jsonl", tmp_path / "registry.jsonl")
    protocol = tmp_path / "protocol.yaml"
    protocol.write_text(
        protocol.read_text(encoding="utf-8").replace("max_kelly_fraction: 0.25",
                                                     "max_kelly_fraction: 1.0"),
        encoding="utf-8",
    )

    with pytest.raises(HypothesisModifiedError):
        RiskLimits.from_env(limits_env(KELLY_FRACTION="0.5"), protocol_dir=tmp_path)


def test_env_example_documents_every_limit() -> None:
    example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    env = {
        line.partition("=")[0]: line.partition("=")[2]
        for line in example.splitlines() if "=" in line and not line.startswith("#")
    }
    loaded = RiskLimits.from_env(env, protocol_dir=_PROTOCOL_DIR)

    assert loaded.kelly_fraction <= 0.25


# Sizing


def test_kelly_estimates_come_from_closed_trades() -> None:
    estimates = KellyEstimates.from_trades(closed_trades(wins=6, losses=4, win_eur=300.0,
                                                         loss_eur=100.0))

    assert estimates.n_trades == 10
    assert estimates.p == pytest.approx(0.6)
    assert estimates.b == pytest.approx(3.0)


def test_record_without_kelly_edge_is_rejected_as_too_small() -> None:
    risk = manager(limits=limits(MIN_TRADES_FOR_KELLY=20))
    book = BookState(closed_trades={"strategy_a": closed_trades(wins=5, losses=20, win_eur=100.0)})

    decision = risk.evaluate(intent("SRPT"), book, market())

    assert not decision.approved
    assert decision.check_name == "POSITION_TOO_SMALL"


def test_kelly_sizing_is_used_once_history_is_long_enough() -> None:
    risk = manager(limits=limits(MIN_TRADES_FOR_KELLY=20, MAX_POSITION_PCT=0.05))
    book = BookState(closed_trades={"strategy_a": closed_trades(wins=14, losses=6, win_eur=150.0,
                                                                loss_eur=100.0)})

    decision = risk.evaluate(intent("SRPT"), book, market())

    assert decision.approved
    assert decision.sizing_result is not None
    assert decision.sizing_result.method == "kelly"
    # p 0.7 shrinks to 0.6; b 1.5; quarter Kelly of (0.6 * 2.5 - 1) / 1.5 = 1/3 is 1/12.
    assert decision.sizing_result.fraction == pytest.approx(1 / 12)


def test_approval_lists_every_check_in_order() -> None:
    decision = manager().evaluate(intent("SRPT"), BookState(), market())

    assert decision.approved
    assert [c.check_name for c in decision.checks] == [
        "MAX_DRAWDOWN", "KILL_SWITCH", "SIZING", "STRATEGY_POSITION_LIMIT", "THEME_LIMIT",
        "POSITION_LIMIT", "GROSS_EXPOSURE", "NET_EXPOSURE", "CATALYST_GUARD",
        "DAILY_LOSS_LIMIT", "DAILY_TURNOVER",
    ]
    assert all(c.passed for c in decision.checks)
    assert decision.shares == 50


# Position limits


def test_strategy_position_count_limit_rejects() -> None:
    risk = manager(limits=limits(MAX_POSITIONS_PER_STRATEGY=1))
    book = BookState(positions=[held("strategy_a", "OTHR", shares=10)])

    decision = risk.evaluate(intent("SRPT"), book, market())

    assert decision.check_name == "STRATEGY_POSITION_LIMIT"


def test_per_name_cap_cuts_shares_when_the_name_is_already_held() -> None:
    risk = manager(limits=limits(MAX_POSITIONS_PER_THEME=2, MAX_POSITION_PCT=0.03,
                                 FALLBACK_POSITION_PCT=0.02))
    # EUR 2,000 of SRPT held; the cap leaves EUR 1,000, which is 50 shares at $25 and 0.8.
    book = BookState(positions=[held("strategy_b", "SRPT", shares=100)])

    decision = risk.evaluate(intent("SRPT"), book, market())

    assert decision.approved
    assert decision.sizing_result is not None and decision.sizing_result.shares == 100
    assert decision.adjusted_shares == 50
    assert decision.shares == 50


def test_held_position_without_price_rejects_rather_than_counting_zero() -> None:
    book = BookState(positions=[held("strategy_b", "OTHR", shares=10)])

    decision = manager().evaluate(intent("SRPT"), book, market(prices={"SRPT": 25.0}))

    assert decision.check_name == "PRICE_UNAVAILABLE"


def test_short_counts_against_net_exposure_in_its_direction() -> None:
    risk = manager(limits=limits(MAX_GROSS_EXPOSURE=2.0, MAX_NET_EXPOSURE=0.5))
    book = BookState(positions=[held("strategy_a", "OTHR", shares=2_500)])
    short = intent("SRPT", direction=Direction.SHORT)

    decision = risk.evaluate(short, book, market())

    assert [c.check_name for c in decision.checks if c.check_name == "NET_EXPOSURE"]
    assert next(c for c in decision.checks if c.check_name == "NET_EXPOSURE").passed


def test_theme_map_loads_every_watched_ticker() -> None:
    themes = ThemeMap.load(REPO_ROOT / "config" / "themes.yaml")
    example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    watched = next(line for line in example.splitlines() if line.startswith("WATCHED_TICKERS="))

    for ticker in watched.partition("=")[2].split(","):
        assert themes.theme(ticker) is not None, ticker


# Binary-event guard


def test_short_is_blocked_by_a_catalyst_its_strategy_trades() -> None:
    catalysts = StaticCatalysts([known_catalyst("SRPT", "readout", date(2026, 3, 11))])
    risk = manager(limits=limits(shorts_enabled=True), catalysts=catalysts,
                   catalyst_types={"strategy_a": frozenset({"readout"})})

    decision = risk.evaluate(intent("SRPT", direction=Direction.SHORT), BookState(), market())

    assert decision.check_name == "CATALYST_GUARD"


def test_long_entry_through_a_declared_catalyst_is_allowed_and_recorded() -> None:
    store = InMemoryObjectStore()
    catalysts = StaticCatalysts([known_catalyst("SRPT", "readout", date(2026, 3, 11))])
    risk = manager(store=store, catalysts=catalysts,
                   catalyst_types={"strategy_a": frozenset({"readout"})})

    decision = risk.evaluate(intent("SRPT"), BookState(), market())

    assert decision.approved
    hold = json.loads(store.get("strategy/risk/catalyst_holds.jsonl") or b"")
    assert hold["action"] == "entry"


def test_declaring_one_catalyst_type_does_not_cover_another() -> None:
    catalysts = StaticCatalysts([known_catalyst("SRPT", "pdufa", date(2026, 3, 11))])
    risk = manager(catalysts=catalysts, catalyst_types={"strategy_a": frozenset({"readout"})})

    assert risk.evaluate(intent("SRPT"), BookState(), market()).check_name == "CATALYST_GUARD"


def test_catalyst_beyond_the_guard_window_does_not_block() -> None:
    catalysts = StaticCatalysts([known_catalyst("SRPT", "pdufa", date(2026, 3, 13))])
    risk = manager(catalysts=catalysts, limits=limits(CATALYST_GUARD_DAYS=3))

    assert risk.evaluate(intent("SRPT"), BookState(), market()).approved


def test_ticker_the_catalyst_source_cannot_answer_for_is_rejected() -> None:
    class _NoAnswer:
        def between(self, ticker: str, start: date, end: date, as_of: datetime) -> list[object]:
            raise LookupError("no CIK")

    decision = manager(catalysts=_NoAnswer()).evaluate(  # type: ignore[arg-type]
        intent("SRPT"), BookState(), market())

    assert decision.check_name == "CATALYST_UNKNOWN"


def test_exit_never_falls_before_today() -> None:
    # The PDUFA is today: the last close before it has passed, so the exit is today's close.
    catalysts = StaticCatalysts([known_catalyst("SRPT", "pdufa", date(2026, 3, 9))])
    book = BookState(positions=[held("strategy_a", "SRPT", shares=10)])

    exits = manager(catalysts=catalysts).catalyst_exits(book, AS_OF)

    assert [e.exit_on for e in exits] == [date(2026, 3, 9)]


def test_exit_before_a_monday_catalyst_is_the_friday_close() -> None:
    friday = datetime(2026, 3, 13, 14, 0, tzinfo=UTC)
    catalysts = StaticCatalysts([
        known_catalyst("SRPT", "adcom", date(2026, 3, 16), known_at=friday - timedelta(days=1)),
    ])
    book = BookState(positions=[held("strategy_a", "SRPT", shares=10)])

    exits = manager(catalysts=catalysts).catalyst_exits(book, friday)

    assert [e.exit_on for e in exits] == [date(2026, 3, 13)]


def test_panel_catalysts_map_rows_and_refuse_a_ticker_without_cik() -> None:
    row = SimpleNamespace(catalyst_type="pdufa", period_start=date(2026, 3, 11),
                          period_end=date(2026, 3, 11), known_at=AS_OF - timedelta(days=30))
    calls: list[tuple[str, date, date, datetime]] = []

    class _Panel:
        def binaries_between(self, cik: str, start: date, end: date,
                             as_of: datetime) -> list[SimpleNamespace]:
            calls.append((cik, start, end, as_of))
            return [row]

    source = PanelCatalysts(_Panel(), {"SRPT": "0000873303"}.get)

    found = source.between("SRPT", date(2026, 3, 9), date(2026, 3, 12), AS_OF)

    assert calls == [("0000873303", date(2026, 3, 9), date(2026, 3, 12), AS_OF)]
    assert [(c.ticker, c.catalyst_type, c.period_start) for c in found] == [
        ("SRPT", "pdufa", date(2026, 3, 11))]
    with pytest.raises(LookupError):
        source.between("ZZZZ", date(2026, 3, 9), date(2026, 3, 12), AS_OF)


# Short guard


def test_shorts_are_rejected_while_the_protocol_disables_them() -> None:
    decision = manager().evaluate(intent("SRPT", direction=Direction.SHORT), BookState(), market())

    assert decision.check_name == "SHORTS_DISABLED"


@pytest.mark.parametrize(("view", "check"), [
    (ShortInterestView(pct_of_shares=35.0, days_to_cover=2.0), "SHORT_INTEREST"),
    (ShortInterestView(pct_of_shares=5.0, days_to_cover=9.0), "DAYS_TO_COVER"),
])
def test_short_guard_rejects_crowded_shorts(view: ShortInterestView, check: str) -> None:
    risk = manager(limits=limits(shorts_enabled=True, MAX_SHORT_INTEREST_PCT=20.0,
                                 MAX_DAYS_TO_COVER=5.0),
                   short_interest=_ShortInterest(view))

    decision = risk.evaluate(intent("SRPT", direction=Direction.SHORT), BookState(), market())

    assert decision.check_name == check


def test_short_without_short_interest_data_passes_the_crowding_checks() -> None:
    risk = manager(limits=limits(shorts_enabled=True), short_interest=_ShortInterest(None))

    assert risk.evaluate(intent("SRPT", direction=Direction.SHORT), BookState(), market()).approved


def test_short_interest_is_read_as_published_the_day_before() -> None:
    asked: list[date] = []

    class _Store:
        def features(self, ticker: str, as_of: date, shares: object) -> SimpleNamespace:
            asked.append(as_of)
            record = ShortInterestRecord.from_counts(
                ticker, date(2026, 2, 27), date(2026, 3, 10),
                short_interest_shares=1_000, average_daily_volume=500)
            return SimpleNamespace(record=record, short_interest_pct_of_shares=12.5)

    view = StoreShortInterest(_Store(), None).view("SRPT", date(2026, 3, 9))  # type: ignore[arg-type]

    assert asked == [date(2026, 3, 8)]
    assert view == ShortInterestView(pct_of_shares=12.5, days_to_cover=2.0)


@pytest.mark.parametrize(("price", "shares", "check"), [
    (29.0, 10, "SHORT_HARD_STOP"),  # 16% against a 15% stop
    (27.0, 2_000, "SHORT_LOSS_CAP"),  # 8% against, but $4,000 x 0.8 = EUR 3,200 lost
])
def test_open_short_is_closed_at_its_stop_or_loss_cap(price: float, shares: int,
                                                      check: str) -> None:
    risk = manager(limits=limits(SHORT_HARD_STOP_PCT=15.0, MAX_LOSS_PER_SHORT_EUR=2_000.0))
    book = BookState(positions=[
        held("strategy_a", "SRPT", shares=shares, direction=Direction.SHORT, entry_price=25.0),
        held("strategy_b", "BEAM", shares=shares, entry_price=25.0),
    ])

    exits = risk.short_exits(book, market(prices={"SRPT": price, "BEAM": price}))

    assert [(e.ticker, e.check_name, e.exit_on) for e in exits] == [
        ("SRPT", check, AS_OF.date())]


# Loss, drawdown and turnover


def test_daily_loss_block_lasts_the_day_and_lifts_the_next() -> None:
    risk = manager(limits=limits(DAILY_LOSS_LIMIT_EUR=-1_000.0))
    risk.evaluate(intent("SRPT"), BookState(), market(day_pnl_eur=-1_500.0))

    recovered_today = risk.evaluate(intent("SRPT"), BookState(), market(day_pnl_eur=500.0))
    next_day = AS_OF + timedelta(days=1)
    tomorrow = risk.evaluate(intent("SRPT", as_of=next_day), BookState(),
                             market(day_pnl_eur=0.0, as_of=next_day))

    assert recovered_today.check_name == "DAILY_LOSS_LIMIT"
    assert tomorrow.approved


def test_turnover_ceiling_rejects() -> None:
    risk = manager(limits=limits(DAILY_TURNOVER_CEILING_PCT=0.2))

    decision = risk.evaluate(intent("SRPT"), BookState(), market(turnover_today_eur=19_500.0))

    assert decision.check_name == "DAILY_TURNOVER"


def test_drawdown_at_the_limit_does_not_kill() -> None:
    risk = manager(limits=limits(MAX_DRAWDOWN_PCT=0.2))

    decision = risk.evaluate(intent("SRPT"), BookState(),
                             market(book_value_eur=80_000.0, peak_book_value_eur=100_000.0))

    assert decision.approved
    assert not risk.kill_switch.is_active()


# Kill switch


def test_kill_switch_reset_and_event_log() -> None:
    store = InMemoryObjectStore()
    switch = KillSwitch(store, clock=lambda: AS_OF)
    switch.trigger("bad fills", strategy_name="strategy_a", triggered_by="me")
    assert switch.is_active("strategy_a")
    assert not switch.is_active("strategy_b")
    assert not switch.is_active()

    switch.reset("checked", strategy_name="strategy_a", triggered_by="me")

    assert not switch.is_active("strategy_a")
    events = [json.loads(line) for line in
              (store.get("strategy/killswitch/events.jsonl") or b"").decode().splitlines()]
    assert [(e["action"], e["scope"], e["reason"], e["triggered_by"]) for e in events] == [
        ("trigger", "strategy_a", "bad fills", "me"),
        ("reset", "strategy_a", "checked", "me"),
    ]
    assert events[0]["triggered_at"] == AS_OF.isoformat()


def test_kill_switch_refuses_a_name_that_is_not_a_strategy_name() -> None:
    with pytest.raises(ValueError):
        KillSwitch(InMemoryObjectStore()).trigger("x", strategy_name="../global")


def test_kill_cli_help_prints_usage(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli(["kill", "--help"], env={})

    assert excinfo.value.code == 0
    assert "--strategy" in capsys.readouterr().out


@pytest.mark.enable_socket
def test_kill_cli_resets_one_strategy() -> None:
    with FakeS3() as s3:
        env = {"MINIO_ENDPOINT": s3.endpoint, "MINIO_ACCESS_KEY": "a", "MINIO_SECRET_KEY": "b"}
        assert cli(["kill", "--strategy", "strategy_a", "--reason", "x"], env=env) == 0
        switch = KillSwitch(MinioObjectStore(s3.client()))
        assert switch.is_active("strategy_a")

        assert cli(["kill", "--strategy", "strategy_a", "--reset"], env=env) == 0

        assert not switch.is_active("strategy_a")


def test_kill_cli_without_minio_settings_names_them(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        cli(["kill"], env={})

    assert "MINIO_ENDPOINT" in capsys.readouterr().err


def test_streaming_runtime_drops_intents_of_a_killed_strategy() -> None:
    objects = InMemoryObjectStore()
    snapshots = {
        "SRPT": ohlcv(flat_bars(date(2026, 1, 1), date(2026, 3, 31), 100.0)),
        "EURUSD=X": ohlcv(flat_bars(date(2026, 1, 1), date(2026, 3, 31), 1.25)),
    }
    switch = KillSwitch(objects)
    switch.trigger("test", strategy_name="killed")
    paper = broker(objects, snapshots)
    runtime = StreamingRuntime(
        [slot("killed", "paper", long_on_trigger()), slot("running", "paper", long_on_trigger())],
        broker=paper,
        risk=_PassThrough(),
        ticker_for=lambda entity_key: "SRPT",
        clock=FixedClock(utc(2026, 3, 10, 22, 0)),
        timeout_seconds=5.0,
        kill_switch=switch,
    )

    runtime.process(signal("e-1", utc(2026, 3, 5, 14, 0)))

    from auspex_strategy.runtime import BookMode
    assert paper.book("killed", BookMode.PAPER).snapshot().is_empty()
    assert not paper.book("running", BookMode.PAPER).snapshot().is_empty()


class _PassThrough:
    def review(self, intents: list[object]) -> list[object]:
        from auspex_strategy.runtime import ApprovedIntent
        return [ApprovedIntent(i, 10_000.0) for i in intents]  # type: ignore[arg-type]


def test_cost_model_reports_its_borrow_fee() -> None:
    assert CostModel(CostParameters(borrow_fee_annual_pct=7.5)).borrow_fee_annual_pct("SRPT") == 7.5


def test_break_even_trade_is_not_a_win() -> None:
    trades = closed_trades(wins=1, losses=0) + closed_trades(wins=0, losses=1, loss_eur=0.0)

    assert KellyEstimates.from_trades(trades).p == pytest.approx(0.5)


def test_net_exposure_limit_rejects_short_excess() -> None:
    risk = manager(limits=limits(shorts_enabled=True, MAX_GROSS_EXPOSURE=2.0,
                                 MAX_NET_EXPOSURE=0.5))
    book = BookState(positions=[
        held("strategy_a", "OTHR", shares=2_500, direction=Direction.SHORT)])

    decision = risk.evaluate(intent("SRPT", direction=Direction.SHORT), book, market())

    assert decision.check_name == "NET_EXPOSURE"


def test_later_checks_see_the_capped_share_count() -> None:
    risk = manager(limits=limits(MAX_POSITIONS_PER_THEME=2, MAX_POSITION_PCT=0.03,
                                 FALLBACK_POSITION_PCT=0.02, DAILY_TURNOVER_CEILING_PCT=0.2))
    book = BookState(positions=[held("strategy_b", "SRPT", shares=100)])

    # EUR 19,000 traded today; the capped EUR 1,000 reaches the 20% ceiling exactly, the
    # uncapped EUR 2,000 would pass it.
    decision = risk.evaluate(intent("SRPT"), book, market(turnover_today_eur=19_000.0))

    assert decision.approved
    assert decision.shares == 50


def test_open_short_is_exited_before_a_catalyst_its_strategy_trades() -> None:
    catalysts = StaticCatalysts([known_catalyst("SRPT", "readout", date(2026, 3, 11))])
    risk = manager(catalysts=catalysts, catalyst_types={"strategy_a": frozenset({"readout"})})
    book = BookState(positions=[
        held("strategy_a", "SRPT", shares=10, direction=Direction.SHORT)])

    exits = risk.catalyst_exits(book, AS_OF)

    assert [(e.ticker, e.exit_on) for e in exits] == [("SRPT", date(2026, 3, 10))]

import json
import math
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest
from auspex_backtesting.market_sim import CostModel, CostParameters

from auspex_strategy.models import Direction
from auspex_strategy.risk import (
    BookState,
    KellyEstimates,
    KellySizer,
    KillSwitch,
    LimitAboveCeilingError,
    RiskLimits,
)
from auspex_strategy.runtime import MinioObjectStore
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
from .s3_fake import FakeS3

_PROTOCOL_DIR = REPO_ROOT / "config" / "hypotheses"


def test_kelly_sizer_shrinks_estimate_toward_prior() -> None:
    sizer = KellySizer(limits(KELLY_SHRINKAGE_FACTOR=0.5, KELLY_FRACTION=0.25))

    fraction = sizer.kelly_fraction(KellyEstimates(p=0.9, b=2.0, n_trades=50))

    assert fraction == pytest.approx(0.1375)


def test_kelly_fraction_above_protocol_ceiling_fails_startup() -> None:
    env = limits_env(KELLY_FRACTION="0.5")

    with pytest.raises(LimitAboveCeilingError) as excinfo:
        RiskLimits.from_env(env, protocol_dir=_PROTOCOL_DIR)

    assert "KELLY_FRACTION" in str(excinfo.value)
    assert "0.25" in str(excinfo.value)


def test_max_position_pct_above_protocol_ceiling_fails_startup() -> None:
    env = limits_env(MAX_POSITION_PCT="0.10")

    with pytest.raises(LimitAboveCeilingError) as excinfo:
        RiskLimits.from_env(env, protocol_dir=_PROTOCOL_DIR)

    assert "MAX_POSITION_PCT" in str(excinfo.value)
    assert "0.05" in str(excinfo.value)


def test_second_position_in_same_theme_is_rejected() -> None:
    risk = manager()
    book = BookState(positions=[held("strategy_a", "SRPT", shares=10)])

    decision = risk.evaluate(intent("BEAM", strategy="strategy_b"), book, market())

    assert not decision.approved
    assert decision.check_name == "THEME_LIMIT"


def test_ticker_without_theme_is_rejected() -> None:
    decision = manager().evaluate(intent("ZZZZ"), BookState(), market(prices={"ZZZZ": 10.0}))

    assert not decision.approved
    assert decision.check_name == "THEME_UNMAPPED"


def test_open_position_is_exited_before_known_catalyst() -> None:
    # AS_OF is Monday 2026-03-09; the readout is on Wednesday, so the last close before it is
    # Tuesday's.
    catalysts = StaticCatalysts([known_catalyst("SRPT", "readout", date(2026, 3, 11))])
    risk = manager(catalysts=catalysts)
    book = BookState(positions=[held("strategy_a", "SRPT", shares=10)])

    exits = risk.catalyst_exits(book, AS_OF)

    assert len(exits) == 1
    assert exits[0].ticker == "SRPT"
    assert exits[0].strategy_name == "strategy_a"
    assert exits[0].exit_on == date(2026, 3, 10)
    assert exits[0].check_name == "CATALYST_GUARD"


def test_strategy_trading_the_catalyst_type_may_hold_through_it() -> None:
    catalysts = StaticCatalysts([known_catalyst("SRPT", "readout", date(2026, 3, 11))])
    store = InMemoryObjectStore()
    risk = manager(
        store=store,
        catalysts=catalysts,
        catalyst_types={"strategy_a": frozenset({"readout"})},
    )
    book = BookState(positions=[held("strategy_a", "SRPT", shares=10)])

    exits = risk.catalyst_exits(book, AS_OF)

    assert exits == []
    holds = [json.loads(line) for line in store.get("strategy/risk/catalyst_holds.jsonl")
             .decode().splitlines()]
    assert len(holds) == 1
    assert holds[0]["strategy_name"] == "strategy_a"
    assert holds[0]["ticker"] == "SRPT"
    assert holds[0]["catalyst_type"] == "readout"
    assert holds[0]["action"] == "hold"


def test_kelly_sizer_caps_at_max_position_pct() -> None:
    risk_limits = limits(MAX_POSITION_PCT=0.03, MIN_TRADES_FOR_KELLY=20)
    sizer = KellySizer(risk_limits)
    capital, fx, price = 100_000.0, 0.8, 25.0
    # A strong record: quarter Kelly on it is far above 3% of capital.
    estimates = KellyEstimates(p=0.9, b=3.0, n_trades=40)
    assert sizer.kelly_fraction(estimates) > 0.03

    shares = sizer.size(intent("SRPT"), estimates, capital, fx, price)

    assert shares == math.floor(0.03 * capital / fx / price)


def test_kelly_falls_back_below_minimum_trade_count() -> None:
    sizer = KellySizer(limits(MIN_TRADES_FOR_KELLY=20, FALLBACK_POSITION_PCT=0.01))
    history = closed_trades(wins=9, losses=1)
    estimates = KellyEstimates.from_trades(history)
    assert estimates.n_trades == 10
    capital, fx, price = 100_000.0, 0.8, 25.0

    shares = sizer.size(intent("SRPT"), estimates, capital, fx, price)

    assert shares == math.floor(0.01 * capital / fx / price)


def test_gross_exposure_limit_rejects_intent_at_ceiling() -> None:
    risk = manager(limits=limits(MAX_GROSS_EXPOSURE=0.5, MAX_NET_EXPOSURE=1.0))
    # 2,500 shares at $25 and 0.8 EUR/USD is EUR 50,000: half of EUR 100,000.
    book = BookState(positions=[held("strategy_a", "OTHR", shares=2_500)])

    decision = risk.evaluate(intent("SRPT"), book, market())

    assert not decision.approved
    assert decision.check_name == "GROSS_EXPOSURE"


def test_net_exposure_limit_rejects_directional_excess() -> None:
    risk = manager(limits=limits(MAX_GROSS_EXPOSURE=2.0, MAX_NET_EXPOSURE=0.5))
    book = BookState(positions=[held("strategy_a", "OTHR", shares=2_500)])

    decision = risk.evaluate(intent("SRPT"), book, market())

    assert not decision.approved
    assert decision.check_name == "NET_EXPOSURE"


def test_binary_event_guard_blocks_entry_within_catalyst_window() -> None:
    catalysts = StaticCatalysts([known_catalyst("SRPT", "pdufa", date(2026, 3, 11))])
    risk = manager(catalysts=catalysts, limits=limits(CATALYST_GUARD_DAYS=3))

    decision = risk.evaluate(intent("SRPT"), BookState(), market())

    assert not decision.approved
    assert decision.check_name == "CATALYST_GUARD"


def test_short_guard_blocks_entry_above_borrow_fee_cap() -> None:
    costs = CostModel(CostParameters(borrow_fee_annual_pct=25.0))
    risk = manager(
        limits=limits(MAX_BORROW_FEE_ANNUAL_PCT=10.0, shorts_enabled=True),
        costs=costs,
    )

    decision = risk.evaluate(intent("SRPT", direction=Direction.SHORT), BookState(), market())

    assert not decision.approved
    assert decision.check_name == "BORROW_FEE"


def test_daily_loss_limit_blocks_all_intents_when_breached() -> None:
    risk = manager(limits=limits(DAILY_LOSS_LIMIT_EUR=-1_000.0))

    decision = risk.evaluate(intent("SRPT"), BookState(), market(day_pnl_eur=-1_500.0))

    assert not decision.approved
    assert decision.check_name == "DAILY_LOSS_LIMIT"


def test_drawdown_limit_triggers_global_kill_switch() -> None:
    risk = manager(limits=limits(MAX_DRAWDOWN_PCT=0.2))
    crashed = market(book_value_eur=75_000.0, peak_book_value_eur=100_000.0)

    first = risk.evaluate(intent("SRPT"), BookState(), crashed)

    assert not first.approved
    assert risk.kill_switch.is_active()
    recovered = market(book_value_eur=100_000.0, peak_book_value_eur=100_000.0)
    for strategy in ("strategy_a", "strategy_b"):
        later = risk.evaluate(intent("SRPT", strategy=strategy), BookState(), recovered)
        assert not later.approved
        assert later.check_name == "KILL_SWITCH"


def test_global_kill_switch_blocks_all_strategies() -> None:
    risk = manager()
    risk.kill_switch.trigger("test")

    for strategy in ("strategy_a", "strategy_b"):
        decision = risk.evaluate(intent("SRPT", strategy=strategy), BookState(), market())
        assert not decision.approved
        assert decision.check_name == "KILL_SWITCH"


def test_per_strategy_kill_switch_blocks_only_named_strategy() -> None:
    risk = manager()
    risk.kill_switch.trigger("test", strategy_name="strategy_a")

    killed = risk.evaluate(intent("SRPT", strategy="strategy_a"), BookState(), market())
    other = risk.evaluate(intent("SRPT", strategy="strategy_b"), BookState(), market())

    assert not killed.approved
    assert killed.check_name == "KILL_SWITCH"
    assert other.approved


@pytest.mark.enable_socket
def test_kill_switch_reachable_from_cli_without_docker() -> None:
    with FakeS3() as s3:
        env = {
            **os.environ,
            "MINIO_ENDPOINT": s3.endpoint,
            "MINIO_ACCESS_KEY": "test",
            "MINIO_SECRET_KEY": "test-secret",
        }
        completed = subprocess.run(
            [sys.executable, "-m", "auspex_strategy", "kill", "--reason", "test"],
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
            cwd=Path(__file__).parent,
        )
        assert completed.returncode == 0, completed.stderr

        flag = json.loads(s3.objects[("auspex-strategy", "strategy/killswitch/global.json")])
        assert flag["active"] is True
        assert flag["reason"] == "test"
        assert KillSwitch(MinioObjectStore(s3.client())).is_active()

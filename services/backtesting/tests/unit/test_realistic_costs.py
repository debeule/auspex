import io
import math
from datetime import date
from unittest.mock import MagicMock

import pandas as pd
import pytest
from minio.error import S3Error

from auspex_backtesting.market_sim import (
    CostModel,
    CostParameters,
    FillModel,
    PositionSizer,
    PositionTooSmallError,
    PriceDataAbsentError,
    PriceSnapshotStore,
    SpreadEstimator,
    VolumeCap,
)

_PARAMS = CostParameters(
    usd_min_commission=1.00,
    ibkr_rate_per_share=0.005,
    spread_bps=50.0,
    tob_rate=0.0035,
    borrow_fee_annual_pct=3.0,
    fx_fee_rate=0.0003,
    min_half_spread_bps=2.0,
)

# Ten March 2025 sessions; the estimator and volume cap read the ones before the entry date.
_SESSIONS = [
    "2025-03-03",
    "2025-03-04",
    "2025-03-05",
    "2025-03-06",
    "2025-03-07",
    "2025-03-10",
    "2025-03-11",
    "2025-03-12",
    "2025-03-13",
    "2025-03-14",
]


def _bars(rows: dict[str, tuple[float, float, float, float, float]]) -> pd.DataFrame:
    """rows maps ISO date -> (open, high, low, close, volume), in the stored PriceFetcher schema."""
    idx = pd.DatetimeIndex(list(rows), tz="UTC", name="date")
    return pd.DataFrame(
        rows.values(), index=idx, columns=["open", "high", "low", "close", "volume"]
    )


def _bouncing(bid: float, ask: float, volume: float = 100_000.0) -> pd.DataFrame:
    """Closes alternate between bid and ask with a constant range [bid, ask], so the
    Abdi-Ranaldo estimate is exactly ln(ask / bid)."""
    return _bars(
        {d: (bid, ask, bid, ask if i % 2 == 0 else bid, volume) for i, d in enumerate(_SESSIONS)}
    )


def _store(snapshots: dict[str, pd.DataFrame]) -> PriceSnapshotStore:
    def get_object(bucket: str, key: str) -> MagicMock:
        ticker = key.removesuffix(".parquet")
        if ticker not in snapshots:
            raise S3Error(
                MagicMock(), "NoSuchKey", "The specified key does not exist.", "/", "", ""
            )
        buf = io.BytesIO()
        snapshots[ticker].to_parquet(buf)
        response = MagicMock()
        response.read.return_value = buf.getvalue()
        return response

    minio = MagicMock()
    minio.get_object.side_effect = get_object
    return PriceSnapshotStore(minio_client=minio)


def test_spread_estimator_recovers_bid_ask_bounce_spread():
    estimator = SpreadEstimator(_store({"CAPR": _bouncing(bid=9.90, ask=10.10)}))
    half = estimator.half_spread("CAPR", as_of=date(2025, 3, 14))
    assert half == pytest.approx(math.log(10.10 / 9.90) / 2)


def test_spread_estimator_ignores_bars_on_or_after_as_of_date():
    clean = _bouncing(bid=9.90, ask=10.10)
    tainted = clean.copy()
    tainted.loc[tainted.index >= pd.Timestamp("2025-03-12", tz="UTC"), ["high", "close"]] = 30.0
    as_of = date(2025, 3, 12)
    assert SpreadEstimator(_store({"CAPR": tainted})).half_spread("CAPR", as_of) == pytest.approx(
        SpreadEstimator(_store({"CAPR": clean})).half_spread("CAPR", as_of)
    )


def test_spread_estimator_raises_without_two_prior_sessions():
    estimator = SpreadEstimator(_store({"CAPR": _bouncing(bid=9.90, ask=10.10)}))
    with pytest.raises(PriceDataAbsentError):
        estimator.half_spread("CAPR", as_of=date(2025, 3, 4))
    with pytest.raises(PriceDataAbsentError):
        estimator.half_spread("SRPT", as_of=date(2025, 3, 14))


def test_cost_model_charges_per_ticker_spread_from_estimator():
    store = _store(
        {
            "CAPR": _bouncing(bid=9.50, ask=10.50),  # ~10% wide, micro-cap
            "SRPT": _bouncing(bid=99.95, ask=100.05),  # ~10 bp wide
        }
    )
    model = CostModel(_PARAMS, spread_estimator=SpreadEstimator(store))
    entry = date(2025, 3, 14)
    capr = model.round_trip_cost_usd("CAPR", 10.0, 100, False, 20, entry_date=entry)
    srpt = model.round_trip_cost_usd("SRPT", 10.0, 100, False, 20, entry_date=entry)
    assert capr.spread == pytest.approx(10.0 * 100 * math.log(10.50 / 9.50))
    assert srpt.spread == pytest.approx(10.0 * 100 * math.log(100.05 / 99.95))
    assert capr.spread > 10 * srpt.spread


def test_cost_model_floors_estimated_spread_at_minimum():
    flat = _bars({d: (10.0, 10.0, 10.0, 10.0, 100_000.0) for d in _SESSIONS})
    model = CostModel(_PARAMS, spread_estimator=SpreadEstimator(_store({"SRPT": flat})))
    cost = model.round_trip_cost_usd("SRPT", 10.0, 100, False, 20, entry_date=date(2025, 3, 14))
    assert cost.spread == pytest.approx(10.0 * 100 * 2.0 / 10_000 * 2)


def test_cost_model_requires_entry_date_when_estimating_spread():
    model = CostModel(_PARAMS, spread_estimator=SpreadEstimator(_store({})))
    with pytest.raises(ValueError, match="entry_date"):
        model.round_trip_cost_usd("CAPR", 10.0, 100, False, 20)


def test_cost_model_round_trip_includes_fx_conversion_fee():
    price, shares = 40.0, 100
    cost = CostModel(_PARAMS).round_trip_cost_usd("BEAM", price, shares, False, 20)
    without_fx = CostModel(_PARAMS.with_overrides(fx_fee_rate=0.0)).round_trip_cost_usd(
        "BEAM", price, shares, False, 20
    )
    assert cost.fx_fee == pytest.approx(price * shares * 0.0003 * 2)
    assert cost == pytest.approx(without_fx + cost.fx_fee)
    assert sum(cost.components().values()) == pytest.approx(cost)
    assert set(cost.components()) == {"commission", "spread", "tob", "fx_fee", "borrow_fee"}


def test_volume_cap_limits_shares_to_fraction_of_average_daily_volume():
    volumes = [80_000.0, 120_000.0] * 5
    bars = _bars({d: (10.0, 10.5, 9.5, 10.0, v) for d, v in zip(_SESSIONS, volumes, strict=True)})
    cap = VolumeCap(_store({"CAPR": bars}), max_adv_fraction=0.01, lookback_sessions=4)
    max_shares = cap.max_shares("CAPR", as_of=date(2025, 3, 14))
    assert max_shares == 1_000  # mean of the 4 sessions before 03-14 is 100k
    sized = PositionSizer().size_shares(
        capital_eur=1_000_000, fx_rate=0.9, price_usd=10.0, max_shares=max_shares
    )
    assert sized == 1_000


def test_volume_cap_rejects_position_when_cap_is_below_one_share():
    thin = _bars({d: (10.0, 10.5, 9.5, 10.0, 50.0) for d in _SESSIONS})
    max_shares = VolumeCap(_store({"CAPR": thin}), max_adv_fraction=0.01).max_shares(
        "CAPR", as_of=date(2025, 3, 14)
    )
    assert max_shares == 0
    with pytest.raises(PositionTooSmallError, match="volume"):
        PositionSizer().size_shares(
            capital_eur=1_000, fx_rate=0.9, price_usd=10.0, max_shares=max_shares
        )


def _one_day(open_: float, high: float, low: float, close: float) -> PriceSnapshotStore:
    return _store({"BEAM": _bars({"2025-03-10": (open_, high, low, close, 100_000.0)})})


def test_stop_fills_at_open_when_price_gaps_through_it():
    fills = FillModel(_one_day(open_=15.0, high=16.0, low=14.0, close=15.5))
    assert fills.stop_exit_price("BEAM", date(2025, 3, 10), stop_price=20.0) == 15.0
    # A short's buy stop above the market gaps the other way.
    short = FillModel(_one_day(open_=25.0, high=26.0, low=24.5, close=25.5))
    assert short.stop_exit_price("BEAM", date(2025, 3, 10), stop_price=22.0, is_short=True) == 25.0


def test_stop_fills_at_stop_price_on_an_ordinary_intraday_cross():
    fills = FillModel(_one_day(open_=21.0, high=21.5, low=19.0, close=19.5))
    assert fills.stop_exit_price("BEAM", date(2025, 3, 10), stop_price=20.0) == 20.0


def test_stop_fills_at_worst_price_of_the_day_on_a_binary_event_day():
    fills = FillModel(_one_day(open_=21.0, high=21.5, low=8.0, close=9.0))
    assert (
        fills.stop_exit_price("BEAM", date(2025, 3, 10), stop_price=20.0, binary_event=True) == 8.0
    )


def test_stop_is_not_triggered_when_range_stays_clear():
    fills = FillModel(_one_day(open_=21.0, high=22.0, low=20.5, close=21.5))
    assert fills.stop_exit_price("BEAM", date(2025, 3, 10), stop_price=20.0) is None


def test_spread_estimator_reads_negative_estimate_as_zero_and_cost_model_floors_it():
    # Closes at each day's high in a steady uptrend make every cross product negative.
    rising = _bars(
        {d: (10.0 + i, 10.1 + i, 9.9 + i, 10.1 + i, 100_000.0) for i, d in enumerate(_SESSIONS)}
    )
    store = _store({"SRPT": rising})
    assert SpreadEstimator(store).half_spread("SRPT", as_of=date(2025, 3, 14)) == 0.0
    model = CostModel(_PARAMS, spread_estimator=SpreadEstimator(store))
    cost = model.round_trip_cost_usd("SRPT", 10.0, 100, False, 20, entry_date=date(2025, 3, 14))
    assert cost.spread == pytest.approx(10.0 * 100 * 2.0 / 10_000 * 2)


def test_spread_estimator_skips_bars_with_missing_or_nonpositive_prices():
    clean = _bouncing(bid=9.90, ask=10.10)
    gappy = clean.copy()
    gappy.loc[pd.Timestamp("2025-03-06", tz="UTC"), "high"] = float("nan")
    gappy.loc[pd.Timestamp("2025-03-07", tz="UTC"), "low"] = 0.0
    half = SpreadEstimator(_store({"CAPR": gappy})).half_spread("CAPR", as_of=date(2025, 3, 14))
    assert math.isfinite(half)
    assert half == pytest.approx(math.log(10.10 / 9.90) / 2, rel=0.25)


def test_spread_estimator_raises_when_window_has_no_usable_bars():
    broken = _bouncing(bid=9.90, ask=10.10)
    broken["close"] = float("nan")
    with pytest.raises(PriceDataAbsentError):
        SpreadEstimator(_store({"CAPR": broken})).half_spread("CAPR", as_of=date(2025, 3, 14))


def test_cost_model_without_estimator_charges_flat_spread_and_ignores_entry_date():
    cost = CostModel(_PARAMS).round_trip_cost_usd(
        "CAPR", 10.0, 100, False, 20, entry_date=date(2025, 3, 14)
    )
    assert cost.spread == pytest.approx(10.0 * 100 * 50 / 10_000 * 2)


def test_cost_parameters_read_new_settings_from_env():
    params = CostParameters.from_env(
        {"FX_FEE_RATE": "0.0005", "MIN_HALF_SPREAD_BPS": "3.5", "SPREAD_BPS": "40"}
    )
    assert params.fx_fee_rate == 0.0005
    assert params.min_half_spread_bps == 3.5
    assert params.spread_bps == 40.0
    defaults = CostParameters.from_env({})
    assert defaults.fx_fee_rate == 0.0003
    assert defaults.min_half_spread_bps == 2.0


def test_volume_cap_reads_fraction_from_env(monkeypatch):
    monkeypatch.setenv("MAX_ADV_FRACTION", "0.02")
    bars = _bars({d: (10.0, 10.5, 9.5, 10.0, 100_000.0) for d in _SESSIONS})
    assert VolumeCap(_store({"CAPR": bars})).max_shares("CAPR", date(2025, 3, 14)) == 2_000
    monkeypatch.delenv("MAX_ADV_FRACTION")
    assert VolumeCap(_store({"CAPR": bars})).max_shares("CAPR", date(2025, 3, 14)) == 1_000


def test_volume_cap_ignores_bars_on_or_after_as_of_date():
    bars = _bars({d: (10.0, 10.5, 9.5, 10.0, 100_000.0) for d in _SESSIONS})
    bars.loc[bars.index >= pd.Timestamp("2025-03-12", tz="UTC"), "volume"] = 10_000_000.0
    cap = VolumeCap(_store({"CAPR": bars}), max_adv_fraction=0.01)
    assert cap.max_shares("CAPR", as_of=date(2025, 3, 12)) == 1_000


def test_volume_cap_raises_without_volume_history():
    bars = _bars({d: (10.0, 10.5, 9.5, 10.0, 100_000.0) for d in _SESSIONS})
    cap = VolumeCap(_store({"CAPR": bars}), max_adv_fraction=0.01)
    with pytest.raises(PriceDataAbsentError):
        cap.max_shares("CAPR", as_of=date(2025, 3, 3))  # no session before the first bar
    with pytest.raises(PriceDataAbsentError):
        cap.max_shares("SRPT", as_of=date(2025, 3, 14))  # no snapshot
    no_volume = bars.copy()
    no_volume["volume"] = float("nan")
    with pytest.raises(PriceDataAbsentError):
        VolumeCap(_store({"CAPR": no_volume}), max_adv_fraction=0.01).max_shares(
            "CAPR", as_of=date(2025, 3, 14)
        )


def test_volume_cap_rejects_position_when_stock_did_not_trade():
    halted = _bars({d: (10.0, 10.0, 10.0, 10.0, 0.0) for d in _SESSIONS})
    max_shares = VolumeCap(_store({"CAPR": halted}), max_adv_fraction=0.01).max_shares(
        "CAPR", as_of=date(2025, 3, 14)
    )
    assert max_shares == 0
    with pytest.raises(PositionTooSmallError):
        PositionSizer().size_shares(capital_eur=1_000, fx_rate=0.9, price_usd=10.0, max_shares=0)


def test_position_sizer_keeps_affordable_shares_when_below_volume_cap():
    assert (
        PositionSizer().size_shares(capital_eur=900, fx_rate=0.9, price_usd=10.0, max_shares=5_000)
        == 100
    )


def test_short_stop_fills_at_stop_on_intraday_cross_and_at_high_on_binary_day():
    fills = FillModel(_one_day(open_=20.0, high=23.0, low=19.5, close=22.5))
    d = date(2025, 3, 10)
    assert fills.stop_exit_price("BEAM", d, stop_price=22.0, is_short=True) == 22.0
    assert (
        fills.stop_exit_price("BEAM", d, stop_price=22.0, is_short=True, binary_event=True) == 23.0
    )
    assert fills.stop_exit_price("BEAM", d, stop_price=24.0, is_short=True) is None


def test_binary_day_stop_not_triggered_when_range_stays_clear():
    fills = FillModel(_one_day(open_=21.0, high=22.0, low=20.5, close=21.5))
    assert (
        fills.stop_exit_price("BEAM", date(2025, 3, 10), stop_price=20.0, binary_event=True) is None
    )


def test_stop_touching_exactly_at_low_fills_at_stop():
    fills = FillModel(_one_day(open_=21.0, high=21.5, low=20.0, close=20.5))
    assert fills.stop_exit_price("BEAM", date(2025, 3, 10), stop_price=20.0) == 20.0


def test_stop_raises_when_bar_is_absent():
    fills = FillModel(_one_day(open_=21.0, high=21.5, low=20.0, close=20.5))
    with pytest.raises(PriceDataAbsentError):
        fills.stop_exit_price("BEAM", date(2025, 3, 11), stop_price=20.0)
    with pytest.raises(PriceDataAbsentError):
        fills.stop_exit_price("CRSP", date(2025, 3, 10), stop_price=20.0)

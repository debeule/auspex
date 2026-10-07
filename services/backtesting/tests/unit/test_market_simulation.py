import io
from datetime import date
from unittest.mock import MagicMock

import pandas as pd
import pytest
from minio.error import S3Error

from auspex_backtesting.market_sim import (
    CostModel,
    CostParameters,
    CurrencyConverter,
    FillModel,
    MarketCalendar,
    MissingPriceDataError,
    PositionSizer,
    PositionTooSmallError,
    PriceDataAbsentError,
    PriceSnapshotStore,
    TradableUniverse,
)


def _ohlcv(rows: dict[str, tuple[float, float]]) -> pd.DataFrame:
    """rows maps ISO date -> (open, close), in the stored PriceFetcher schema."""
    idx = pd.DatetimeIndex(list(rows), tz="UTC", name="date")
    opens = [o for o, _ in rows.values()]
    closes = [c for _, c in rows.values()]
    return pd.DataFrame(
        {
            "open": opens,
            "high": [max(o, c) + 1.0 for o, c in rows.values()],
            "low": [min(o, c) - 1.0 for o, c in rows.values()],
            "close": closes,
            "volume": [100_000.0] * len(rows),
        },
        index=idx,
    )


def _minio_with(snapshots: dict[str, pd.DataFrame]) -> MagicMock:
    def get_object(bucket: str, key: str) -> MagicMock:
        ticker = key.removesuffix(".parquet")
        if ticker not in snapshots:
            raise S3Error(MagicMock(), "NoSuchKey", "The specified key does not exist.", "/", "", "")
        buf = io.BytesIO()
        snapshots[ticker].to_parquet(buf)
        response = MagicMock()
        response.read.return_value = buf.getvalue()
        return response

    mock = MagicMock()
    mock.get_object.side_effect = get_object
    return mock


def _store(snapshots: dict[str, pd.DataFrame]) -> PriceSnapshotStore:
    return PriceSnapshotStore(minio_client=_minio_with(snapshots))


_PARAMS = CostParameters(
    usd_min_commission=1.00,
    ibkr_rate_per_share=0.005,
    spread_bps=50.0,
    tob_rate=0.0035,
    borrow_fee_annual_pct=3.0,
)


def test_market_calendar_skips_weekends():
    calendar = MarketCalendar()
    assert calendar.is_trading_day(date(2025, 3, 8)) is False  # Saturday
    assert calendar.is_trading_day(date(2025, 3, 9)) is False  # Sunday
    assert calendar.is_trading_day(date(2025, 3, 10)) is True  # Monday


def test_market_calendar_skips_nyse_holidays():
    calendar = MarketCalendar()
    assert date(2025, 7, 4).weekday() == 4  # Friday
    assert calendar.is_trading_day(date(2025, 7, 4)) is False
    assert calendar.next_trading_day(date(2025, 7, 4)) == date(2025, 7, 7)


def test_fill_model_uses_open_price_for_entry():
    store = _store({"BEAM": _ohlcv({"2025-03-10": (21.50, 22.75), "2025-03-11": (22.80, 23.10)})})
    assert FillModel(store).entry_price("BEAM", date(2025, 3, 10)) == 21.50


def test_fill_model_uses_close_price_for_exit():
    # 2025-03-10 + 5 calendar days = Saturday 2025-03-15 -> exit on Monday 2025-03-17 close
    store = _store(
        {
            "BEAM": _ohlcv(
                {
                    "2025-03-10": (21.50, 22.75),
                    "2025-03-14": (24.00, 24.40),
                    "2025-03-17": (25.10, 26.30),
                }
            )
        }
    )
    assert FillModel(store).exit_price("BEAM", date(2025, 3, 10), holding_calendar_days=5) == 26.30


def test_fill_model_raises_when_price_data_absent():
    store = _store({"BEAM": _ohlcv({"2025-03-10": (21.50, 22.75)})})
    fills = FillModel(store)
    with pytest.raises(PriceDataAbsentError):
        fills.entry_price("CRSP", date(2025, 3, 10))  # no snapshot for this ticker
    with pytest.raises(PriceDataAbsentError):
        fills.entry_price("BEAM", date(2025, 3, 11))  # snapshot, but no row for this date


def test_cost_model_round_trip_includes_tob():
    price, shares = 40.0, 100
    with_tob = CostModel(_PARAMS).round_trip_cost_usd("BEAM", price, shares, False, 20)
    without_tob = CostModel(_PARAMS.with_overrides(tob_rate=0.0)).round_trip_cost_usd(
        "BEAM", price, shares, False, 20
    )
    assert with_tob == pytest.approx(without_tob + price * shares * 0.0035 * 2)
    assert with_tob.tob == pytest.approx(price * shares * 0.0035 * 2)
    assert with_tob.commission == pytest.approx(2 * max(1.00, 0.005 * shares))
    assert with_tob.spread == pytest.approx(price * shares * 50 / 10_000 * 2)
    assert with_tob.borrow_fee == 0.0


def test_cost_model_short_includes_borrow_fee():
    price, shares, days = 40.0, 100, 30
    model = CostModel(_PARAMS)
    long_cost = model.round_trip_cost_usd("BEAM", price, shares, False, days)
    short_cost = model.round_trip_cost_usd("BEAM", price, shares, True, days)
    expected_fee = price * shares * 3.0 / 100 * days / 365
    assert short_cost == pytest.approx(long_cost + expected_fee)
    assert short_cost.borrow_fee == pytest.approx(expected_fee)


def test_position_sizer_floors_to_integer_shares():
    assert PositionSizer().size_shares(capital_eur=1000, fx_rate=1.1, price_usd=99.0) == 9


def test_position_sizer_raises_when_capital_too_small():
    with pytest.raises(PositionTooSmallError):
        PositionSizer().size_shares(capital_eur=50, fx_rate=1.1, price_usd=200.0)


def test_currency_converter_raises_when_fx_data_absent():
    with pytest.raises(PriceDataAbsentError):
        CurrencyConverter(_store({})).usd_to_eur(1000.0, date(2025, 3, 10))

    fx = _store({"EURUSD=X": _ohlcv({"2025-03-10": (1.08, 1.08)})})
    with pytest.raises(PriceDataAbsentError):
        CurrencyConverter(fx).usd_to_eur(1000.0, date(2025, 3, 11))


def test_tradable_universe_names_ticker_missing_price_data():
    covered = _ohlcv({"2025-03-03": (10.0, 10.5), "2025-03-31": (11.0, 11.5)})
    late_listing = _ohlcv({"2025-03-20": (5.0, 5.5), "2025-03-31": (6.0, 6.5)})
    universe = TradableUniverse(_store({"BEAM": covered, "CAPR": late_listing}))

    universe.validate(["BEAM"], date(2025, 3, 3), date(2025, 3, 31))
    with pytest.raises(MissingPriceDataError, match=r"CAPR.*2025-03-03.*2025-03-31"):
        universe.validate(["BEAM", "CAPR", "CRSP"], date(2025, 3, 3), date(2025, 3, 31))

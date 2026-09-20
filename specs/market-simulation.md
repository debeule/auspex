# Market Simulation

**Status:** blocked
**Blocked by:** backtesting module entity-only variant (`specs/backtesting.md`) — `BacktestRunner` must exist before `FillModel` can integrate with it. Price data (`specs/done/price-ingestion.md`) and alignment (`specs/done/point-in-time-alignment.md`) are already done.

**Branch:** `feature/market-simulation`

---

## Context

`services/backtesting/` has price ingestion (OHLCV Parquet in MinIO), point-in-time alignment, and the backtesting runner (entity-only variant). The backtesting runner currently returns a report of signal counts and lag distributions but does not compute P&L or account for execution costs. This spec adds the execution environment: trading calendar, fill model, cost model (including Belgian-specific taxes), currency conversion, and integer position sizing.

The market-simulation module is used by the evaluation-protocol spec (evaluation-protocol.md, currently a separate blocked spec) to convert abnormal return calculations into net-of-cost P&L.

The cost model constants (TOB rate, IBKR commission schedule, FX spread) are configurable via `.env` so they can be updated without code changes if IBKR's commission schedule or Belgian tax rates change.

## What this builds

`auspex_backtesting/market_sim.py` (or a `market_sim/` sub-package if more than one file):

**`MarketCalendar`**
- `is_trading_day(date: date) → bool` — NYSE calendar (via `pandas-market-calendars`)
- `next_trading_day(date: date) → date` — next NYSE open after `date` (same day if open)
- `trading_days_in(start: date, end: date) → int` — count of NYSE trading days between start and end inclusive

**`FillModel`**
- `entry_price(ticker: str, entry_date: date) → float` — open price on `entry_date` from MinIO Parquet; raises `PriceDataAbsentError` if no data for that date
- `exit_price(ticker: str, entry_date: date, holding_calendar_days: int) → float` — close price on the exit trading day (= next trading day at or after `entry_date + timedelta(holding_calendar_days)`); raises `PriceDataAbsentError` if absent

**`CostModel`**
- `round_trip_cost_usd(ticker: str, price_usd: float, shares: int, is_short: bool, holding_calendar_days: int) → float` — total friction in USD:
  - IBKR commission: `max(USD_MIN_COMMISSION, IBKR_RATE_PER_SHARE × shares)` per leg × 2 legs; `USD_MIN_COMMISSION` and `IBKR_RATE_PER_SHARE` read from `.env` (defaults: 1.00 and 0.005)
  - Spread: `price_usd × shares × SPREAD_BPS / 10_000 × 2` (entry + exit); `SPREAD_BPS` read from `.env` (default: 50)
  - Belgian TOB: `price_usd × shares × TOB_RATE × 2` (buy + sell); `TOB_RATE` read from `.env` (default: 0.0035)
  - Borrow fee (short only): `price_usd × shares × BORROW_FEE_ANNUAL_PCT / 100 × holding_calendar_days / 365`; `BORROW_FEE_ANNUAL_PCT` read from `.env` (default: 3.0)
- All four components exposed individually as properties on the return value for debugging

**`CurrencyConverter`**
- `usd_to_eur(amount_usd: float, date: date) → float` — reads USD/EUR daily close from MinIO Parquet for ticker `EURUSD=X` (same format as OHLCV price data); raises `PriceDataAbsentError` if no FX data for `date`
- XBI (benchmark) data is also fetched via this same price-ingestion path (ticker `XBI`)

**`PositionSizer`**
- `size_shares(capital_eur: float, fx_rate: float, price_usd: float) → int` — `floor(capital_eur / fx_rate / price_usd)`; raises `PositionTooSmallError` if result is 0 (capital insufficient for one share at current FX and price)

**`TradableUniverse`**
- `validate(tickers: list[str], start: date, end: date)` — confirms price data exists in MinIO for all tickers in `[start, end]`; raises `MissingPriceDataError` naming the ticker and date range on first failure

New dependency in `services/backtesting/pyproject.toml`: `pandas-market-calendars` (pin to a specific version; resolve at Step 0.0 of this spec's branch and record in `VERSIONS.md`).

## Out of scope

Order routing, IBKR API connectivity, live fills, margin calculations. Multi-leg options or futures. CGT computation (tax is a post-trade accounting step, not part of position sizing). Intraday fill timing (open/close only). Slippage models beyond the configurable spread parameter.

## Constraints

- All data reads from MinIO Parquet only. No live API calls. `pytest-socket --disable-socket` must pass across all unit tests.
- USD/EUR FX data must be fetched and stored via the same yfinance price-ingestion path as OHLCV data — no separate FX client.
- The FX ticker `EURUSD=X` and XBI benchmark ticker must be pre-fetched using the existing `PriceIngestion` script before running a backtest. If the Parquet is absent, `CurrencyConverter` and the benchmark comparison fail loudly.
- All cost parameters (`USD_MIN_COMMISSION`, `IBKR_RATE_PER_SHARE`, `SPREAD_BPS`, `TOB_RATE`, `BORROW_FEE_ANNUAL_PCT`) come from `.env`; no hardcoding. Defaults noted above match the values in `docs/strategy-research.md` cost estimates.
- Invariant 6: no credentials in source code.

## Required tests

In `tests/unit/test_market_simulation.py`:

- `test_market_calendar_skips_weekends` — a Saturday and Sunday both return `is_trading_day = False`; the following Monday returns `True`
- `test_market_calendar_skips_nyse_holidays` — NYSE Independence Day (July 4 when a weekday) returns `is_trading_day = False`
- `test_fill_model_uses_open_price_for_entry` — fixture with known open price; `entry_price()` returns the open column value
- `test_fill_model_uses_close_price_for_exit` — fixture with known close price; `exit_price()` returns the close column value on the correct exit calendar day
- `test_fill_model_raises_when_price_data_absent` — Parquet absent for the requested ticker and date; `entry_price()` raises `PriceDataAbsentError`
- `test_cost_model_round_trip_includes_tob` — cost with `TOB_RATE=0.0035` equals cost without TOB plus `price × shares × 0.0035 × 2`
- `test_cost_model_short_includes_borrow_fee` — `round_trip_cost_usd(is_short=True)` exceeds the non-short cost by `price × shares × BORROW_FEE_ANNUAL_PCT / 100 × days / 365`
- `test_position_sizer_floors_to_integer_shares` — `capital_eur=1000, fx_rate=1.1, price_usd=99.0` → `floor(1000/1.1/99.0) = 9` shares
- `test_position_sizer_raises_when_capital_too_small` — `capital_eur=50, fx_rate=1.1, price_usd=200.0` → `floor(50/1.1/200.0) = 0` → raises `PositionTooSmallError`
- `test_currency_converter_raises_when_fx_data_absent` — no Parquet for `EURUSD=X` on the target date → raises `PriceDataAbsentError`

## Definition of done

```bash
cd services/backtesting && uv run pytest tests/unit/test_market_simulation.py -q
```

Expected: 10 passed.

Then: `EURUSD=X` and `XBI` price data fetched and committed to MinIO (or recorded as fetched in DECISIONS.md) so the evaluation-protocol spec can use them without re-fetching.

## Notes

`pandas-market-calendars` uses the `exchange_calendars` package internally. The NYSE calendar is available as `mcal.get_calendar("NYSE")`. Pin the exact version at the start of this spec's branch.

The default `SPREAD_BPS=50` is a conservative estimate for the mid-cap end of this watchlist (SRPT, CRSP). For micro-cap names (CAPR, SPRB) spread may exceed 100 bps. The parameter should be set per-ticker in a future pass if execution analysis becomes important.

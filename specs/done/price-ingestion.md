# Price Data Ingestion

**Status:** done
**Blocked by:** —
**Branch:** `feature/price-ingestion`

---

## Context

New module at `services/backtesting/`. Nothing in this module exists yet. This spec is a prerequisite for the point-in-time alignment and backtesting specs — build it first. MinIO is already running and accessible.

## What this builds

A price data fetcher in `services/backtesting/` that:
- Fetches daily OHLCV series from `yfinance` via a cached, rate-limited session
- Writes every fetched series to Parquet in MinIO on first fetch and **never re-fetches** — `YFRateLimitError` is a recurring IP-level block even at low rates, and Yahoo's terms contemplate personal use
- On subsequent calls, reads from the MinIO Parquet snapshot — no network call
- Named fallback if Yahoo is unavailable: **Stooq** (`pandas-datareader` stooq endpoint)

## Out of scope

Real-time prices, intraday data, options, any other asset class. Alignment logic and backtest calculations are separate specs.

## Constraints

- New module `services/backtesting/` — does not import from `auspex_ingest`.
- All prices stored UTC. `published_date` on signals is UTC; the price join must be on the same timezone.
- MinIO snapshot is the source of truth once written — never overwrite it from a live fetch.

## Required tests

- `test_ohlcv_maps_to_storage_schema` — fixture-driven; asserts column names, types, UTC dates
- `test_price_series_is_read_from_minio_when_present` — second call makes zero network calls
- `test_missing_ticker_returns_empty_not_exception`
- `test_delisted_ticker_with_partial_history_is_handled`
- `test_price_dates_are_stored_utc`

## Definition of done

```bash
cd services/backtesting && uv run pytest tests/unit/test_price_ingestion.py -q
```

Expected: 5+ passed. Plus: prices for at least one watched ticker (e.g. BEAM) successfully stored in MinIO.

"""Fetch daily OHLCV series into the auspex-prices MinIO bucket, once.

The stack fills and extends the snapshots of the watchlist, XBI and EURUSD=X by itself
(the price-bootstrap job and the auspex_price_refresh DAG). Use this for any other ticker.

Usage:
    uv run python scripts/fetch_prices.py MRNA VRTX --start 2023-01-01 --end 2026-10-01

Run from services/backtesting with MINIO_ENDPOINT, MINIO_ACCESS_KEY and MINIO_SECRET_KEY set
(see .env.example). A ticker already in the bucket is left untouched. Exits non-zero if any
ticker comes back empty from both Yahoo and Stooq.
"""

import argparse
import os
import sys
from datetime import date

from minio import Minio

from auspex_backtesting.prices.price_fetcher import PriceFetcher
from auspex_backtesting.prices.snapshot_store import PRICES_BUCKET


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("tickers", nargs="+")
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    args = parser.parse_args()

    client = Minio(
        os.environ["MINIO_ENDPOINT"],
        access_key=os.environ["MINIO_ACCESS_KEY"],
        secret_key=os.environ["MINIO_SECRET_KEY"],
        secure=False,
    )
    if not client.bucket_exists(PRICES_BUCKET):
        client.make_bucket(PRICES_BUCKET)

    fetcher = PriceFetcher(minio_client=client)
    empty = []
    for ticker in args.tickers:
        df = fetcher.fetch(ticker, args.start, args.end)
        if df.empty:
            empty.append(ticker)
            print(f"{ticker}: no data", file=sys.stderr)
        else:
            print(f"{ticker}: {len(df)} rows, {df.index.min().date()}..{df.index.max().date()}")
    if empty:
        sys.exit(1)


if __name__ == "__main__":
    main()

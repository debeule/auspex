"""One-shot jobs run by Docker Compose on every `up`. Both are no-ops when the data is
already there.

    python -m auspex_backtesting.stack_bootstrap buckets   # create the MinIO buckets
    python -m auspex_backtesting.stack_bootstrap prices    # fill missing price snapshots

`prices` exits non-zero only when a ticker still has no snapshot afterwards, because
backtests and the FX conversion cannot run without one. A snapshot that exists but could not
be extended is logged and left for the scheduled refresh to retry.
"""

import argparse
import logging
import os
import sys
from collections.abc import Iterable

from minio import Minio

from auspex_backtesting.api import refresher_from_env
from auspex_backtesting.prices.price_refresher import (
    PriceDataUnavailableError,
    PriceRefresher,
    SnapshotDiscontinuityError,
    price_universe,
)
from auspex_backtesting.prices.snapshot_store import PRICES_BUCKET

log = logging.getLogger("auspex_backtesting.stack_bootstrap")


def ensure_buckets(minio: Minio, buckets: Iterable[str]) -> None:
    for bucket in buckets:
        if minio.bucket_exists(bucket):
            log.info("bucket %s already exists", bucket)
        else:
            minio.make_bucket(bucket)
            log.info("bucket %s created", bucket)


def fill_prices(refresher: PriceRefresher, tickers: Iterable[str]) -> bool:
    ok = True
    for ticker in tickers:
        try:
            result = refresher.refresh(ticker)
            log.info("%s: %d bars added, last %s", ticker, result.rows_added, result.last_date)
        except PriceDataUnavailableError as exc:
            log.error("%s", exc)
            ok = False
        except SnapshotDiscontinuityError as exc:
            log.error("%s", exc)
    return ok


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("job", choices=["buckets", "prices"])
    job = parser.parse_args().job

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    minio = Minio(
        os.environ["MINIO_ENDPOINT"],
        access_key=os.environ["MINIO_ACCESS_KEY"],
        secret_key=os.environ["MINIO_SECRET_KEY"],
        secure=False,
    )
    if job == "buckets":
        ensure_buckets(minio, [os.environ["MINIO_BUCKET"], PRICES_BUCKET])
        return
    tickers = price_universe(os.environ.get("WATCHED_TICKERS", ""))
    sys.exit(0 if fill_prices(refresher_from_env(), tickers) else 1)


if __name__ == "__main__":
    main()

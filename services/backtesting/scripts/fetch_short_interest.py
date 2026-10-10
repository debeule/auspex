"""Backfill and extend FINRA short interest for every universe ticker.

Fetches each FINRA settlement period from SHORT_INTEREST_HISTORY_START that is published by
today and not stored yet, writes it to MinIO `auspex-prices/short_interest/{ticker}.parquet`,
and prints coverage as JSON: the first available settlement date, periods FINRA returned
nothing for, gaps, and tickers FINRA never reported.

Usage:
    uv run --env-file ../../.env python scripts/fetch_short_interest.py

Run from services/backtesting after the universe has been built, with the MinIO, FINRA_* and
SHORT_INTEREST_HISTORY_START variables of .env.example set; FINRA_API_CLIENT_ID and
FINRA_API_CLIENT_SECRET are a FINRA API console credential. UNIVERSE_RULES_PATH defaults to
the repository's config/universe/rules.yaml. Publication dates come from FINRA's rule and the
published schedule in config/short_interest/finra_calendar.csv. A rerun fetches only what is
not stored yet. Exits non-zero if FINRA refuses the credential.
"""

import json
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from minio import Minio

from auspex_backtesting.prices.snapshot_store import PRICES_BUCKET
from auspex_backtesting.short_interest import FinraAuthError, FinraClient, ShortInterestStore
from auspex_backtesting.short_interest.job import (
    ShortInterestConfig,
    fetch_short_interest,
    universe_tickers,
)
from auspex_backtesting.universe.rules import load_rules
from auspex_backtesting.universe.store import UniverseStore

_CONFIG = Path(__file__).resolve().parents[3] / "config"
_DEFAULT_RULES = _CONFIG / "universe" / "rules.yaml"
_CALENDAR = _CONFIG / "short_interest" / "finra_calendar.csv"


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    client = Minio(
        os.environ["MINIO_ENDPOINT"],
        access_key=os.environ["MINIO_ACCESS_KEY"],
        secret_key=os.environ["MINIO_SECRET_KEY"],
        secure=False,
    )
    if not client.bucket_exists(PRICES_BUCKET):
        client.make_bucket(PRICES_BUCKET)
    config = ShortInterestConfig.from_env()
    rules = load_rules(Path(os.environ.get("UNIVERSE_RULES_PATH", _DEFAULT_RULES)))
    tickers = universe_tickers(UniverseStore(client), rules.version)
    try:
        source = FinraClient(
            config.data_url, config.token_url, config.client_id, config.client_secret
        )
        report = fetch_short_interest(
            config, ShortInterestStore(client), source, _CALENDAR, tickers,
            datetime.now(UTC).date(),
        )
    except FinraAuthError as exc:
        sys.exit(f"{exc}; stored periods are kept")
    print(json.dumps(report.as_dict(), indent=2))


if __name__ == "__main__":
    main()

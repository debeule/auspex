"""Backfill and extend the SEC ownership panels (13F holdings, insider transactions, offerings).

Downloads each 13F and insider transactions data set from OWNERSHIP_HISTORY_START on, once,
fills the days since the latest insider data set from the daily form index, refreshes cover
page share counts, and prints coverage as JSON: data sets stored, universe issuers with any
13F holder, unmapped CUSIP share and insider filings per data set.

Usage:
    uv run --env-file ../../.env python scripts/fetch_ownership.py

Run from services/backtesting after the universe has been built, with the MinIO, SEC_* and
OWNERSHIP_HISTORY_START variables of .env.example set; UNIVERSE_RULES_PATH defaults to the
repository's config/universe/rules.yaml. The specialist thresholds come from the registered H9
hypothesis in the repository's config/hypotheses, and the run stops if that file is missing or
differs from its registry entry. A rerun fetches only what is not stored yet. Exits
non-zero if SEC refuses a request: wait at least ten minutes before running it again.
"""

import json
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from minio import Minio

from auspex_backtesting.ownership import OwnershipStore, SecBlockedError, SecClient
from auspex_backtesting.ownership.job import OwnershipBackfill, OwnershipConfig
from auspex_backtesting.prices.snapshot_store import PRICES_BUCKET
from auspex_backtesting.universe.rules import load_rules
from auspex_backtesting.universe.store import UniverseStore

_CONFIG = Path(__file__).resolve().parents[3] / "config"
_DEFAULT_RULES = _CONFIG / "universe" / "rules.yaml"


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
    rules = load_rules(Path(os.environ.get("UNIVERSE_RULES_PATH", _DEFAULT_RULES)))
    backfill = OwnershipBackfill(
        OwnershipConfig.from_env(),
        OwnershipStore(client),
        UniverseStore(client),
        rules.version,
        SecClient(os.environ["SEC_USER_AGENT"]),
        datetime.now(UTC).date(),
        hypotheses_dir=_CONFIG / "hypotheses",
        hypothesis_registry=_CONFIG / "hypotheses" / "registry.jsonl",
    )
    try:
        summary = backfill.run()
    except SecBlockedError as exc:
        sys.exit(f"{exc}; stored data sets are kept, rerun after the block lifts")
    print(json.dumps(summary.as_dict(), indent=2))


if __name__ == "__main__":
    main()

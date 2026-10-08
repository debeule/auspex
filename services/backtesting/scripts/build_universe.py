"""Build the point-in-time universe now, or export its backfill scope for committing.

The stack builds the universe by itself (the auspex_universe_build DAG, first week of every
month and on the first start). Use this to run a build outside that schedule, or to copy the
backfill scope out of MinIO into the repository.

Usage:
    uv run python scripts/build_universe.py
    uv run python scripts/build_universe.py --export-backfill-scope ../../config/universe/backfill_scope.yaml

Run from services/backtesting with the MinIO, PRICE_HISTORY_START, SEC_* and
UNIVERSE_RULES_PATH variables of .env.example set. Prints the build summary, including the
price coverage report, as JSON.
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from minio import Minio

from auspex_backtesting.api import universe_job_from_env
from auspex_backtesting.universe.rules import load_rules
from auspex_backtesting.universe.store import UniverseStore


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--export-backfill-scope", type=Path, metavar="PATH")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.export_backfill_scope is None:
        print(json.dumps(universe_job_from_env().run().as_dict(), indent=2, default=str))
        return

    client = Minio(
        os.environ["MINIO_ENDPOINT"],
        access_key=os.environ["MINIO_ACCESS_KEY"],
        secret_key=os.environ["MINIO_SECRET_KEY"],
        secure=False,
    )
    rules = load_rules(Path(os.environ["UNIVERSE_RULES_PATH"]))
    scope = UniverseStore(client).read_report(rules.version, "backfill_scope.yaml")
    if scope is None:
        sys.exit(f"no backfill scope stored for rules version {rules.version}; run a build first")
    args.export_backfill_scope.write_bytes(scope)
    print(f"wrote {args.export_backfill_scope}")


if __name__ == "__main__":
    main()

"""Compute the H9 holdings composite score for every universe month.

Writes one score snapshot per rebalance month that has passed and has none yet, under
`scores/h9/<version>/` in the prices bucket (`<version>-no_floor` with `--no-floor`, for the
trial cells that skip H9's tradable floor), and prints a coverage report as JSON: the component
variant H9's rule chose from the short interest history, per month the members, those under
the floor, scored and left out for fewer than two components, and per year the correlation of
each pair of component ranks.

Usage:
    uv run --env-file ../../.env python scripts/compute_holdings_scores.py
    uv run --env-file ../../.env python scripts/compute_holdings_scores.py --no-floor

Run from services/backtesting with the MinIO variables of .env.example set, after the
universe, ownership panels and short interest are stored. UNIVERSE_RULES_PATH defaults to the
repository's config/universe/rules.yaml. A rerun writes only the months still missing.
"""

import argparse
import json
import logging
import os
from pathlib import Path

from minio import Minio

from auspex_backtesting.scores.job import holdings_score_build
from auspex_backtesting.universe.rules import load_rules

_CONFIG = Path(__file__).resolve().parents[3] / "config"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--no-floor", action="store_true", help="skip H9's tradable floor")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    client = Minio(
        os.environ["MINIO_ENDPOINT"],
        access_key=os.environ["MINIO_ACCESS_KEY"],
        secret_key=os.environ["MINIO_SECRET_KEY"],
        secure=False,
    )
    rules_path = Path(os.environ.get("UNIVERSE_RULES_PATH", _CONFIG / "universe" / "rules.yaml"))
    build = holdings_score_build(
        client,
        load_rules(rules_path).version,
        _CONFIG / "short_interest" / "finra_calendar.csv",
        floor=not args.no_floor,
        config_dir=_CONFIG / "hypotheses",
        registry_path=_CONFIG / "hypotheses" / "registry.jsonl",
    )
    print(json.dumps(build.run(), indent=2, default=str))


if __name__ == "__main__":
    main()

"""Build the point-in-time catalyst panel: PDUFA dates from 8-K press releases and FDA advisory
committee meetings from Federal Register notices, matched to the universe's companies.

Usage:
    uv run python scripts/build_catalyst_panel.py
    uv run python scripts/build_catalyst_panel.py --since 2024-01-01 --until 2024-12-31

Run from services/backtesting with the MinIO, SEC_*, FEDERAL_REGISTER_API_URL and
UNIVERSE_RULES_PATH variables of .env.example set, after the universe is built. Every document
read is kept in MinIO, so a run that stops (SEC refusing requests) continues where it left
off when run again. Prints the counters and the panel's coverage as JSON and exits 1 when the
run is incomplete.
"""

import argparse
import json
import logging
import sys
from datetime import UTC, date, datetime

from auspex_backtesting.api import catalyst_build_from_env


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--since", type=date.fromisoformat, default=date(2014, 1, 1))
    parser.add_argument("--until", type=date.fromisoformat, default=datetime.now(UTC).date())
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    summary = catalyst_build_from_env().run(args.since, args.until)
    print(json.dumps(summary, indent=2, default=str))
    if not summary["complete"]:
        sys.exit("incomplete: a source refused requests; run again later to continue")


if __name__ == "__main__":
    main()

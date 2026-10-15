"""Build the filing-text change panel (H10, Item 1A "lazy prices") over a universe.

Indexes every 10-K and 10-Q of the universe's members from EDGAR's quarterly full index, cuts
Item 1A out of each filing once, scores it against the same filing a year earlier and writes a
score snapshot for every universe month that has none. Each cut section is kept in MinIO, so a
run that SEC stops continues where it left off when run again.

Usage:
    uv run python scripts/build_filing_panel.py
    uv run python scripts/build_filing_panel.py --rules ../../config/universe/us_small_mid.yaml

Run from services/backtesting with the MinIO and SEC_* variables of .env.example set, after
the universe is built. Prints the coverage as JSON (filings found, sections cut, missing by
reason, members scored per month) and exits 1 when the run is incomplete. Snapshots go under
`scores/h10/<version>/`, with the universe's id after the version for any universe but the
default one (`1-us_small_mid`).
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from auspex_backtesting.api import filing_panel_build_from_env
from auspex_backtesting.hypothesis import load_hypothesis

_CONFIG_DIR = Path(__file__).resolve().parents[3] / "config"
_HYPOTHESIS = "h10"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--rules", type=Path, metavar="PATH",
        default=Path(os.environ.get("UNIVERSE_RULES_PATH", _CONFIG_DIR / "universe" / "rules.yaml")),
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    version = int(load_hypothesis(_HYPOTHESIS, _CONFIG_DIR / "hypotheses")["version"])
    summary = filing_panel_build_from_env(args.rules, _HYPOTHESIS, version).run()
    print(json.dumps(summary, indent=2, default=str))
    if not summary["complete"]:
        sys.exit("incomplete: SEC refused requests; run again later to continue")


if __name__ == "__main__":
    main()

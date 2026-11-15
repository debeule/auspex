#!/usr/bin/env python
"""Score a completed corroboration hand review per entity label (EXT-022).

Usage:
    uv run python scripts/score_corroboration_review.py review.jsonl [--minimum 50]

Each line's "verdict" is "genuine" when its signals report the same specific
finding about the same entity and the attached ticker is that finding's
company; otherwise "coincidental", "wrong_ticker" or "extraction_error".

Each stratum (entity label) passes at a precision of 0.85 or more; a stratum
with fewer than --minimum rows is "insufficient". Exits 0 only when every
stratum passes, 2 otherwise, 1 on a malformed file.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from auspex_ingest.sampling import PRECISION_BAR, review_passes, score_review


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("review", type=Path)
    parser.add_argument("--minimum", type=int, default=50, help="Rows a stratum needs to be judged")
    args = parser.parse_args()

    if not args.review.exists():
        print(f"File not found: {args.review}", file=sys.stderr)
        sys.exit(1)
    records = [json.loads(line) for line in args.review.read_text().splitlines() if line.strip()]
    try:
        scores = score_review(records, minimum=args.minimum)
    except ValueError as exc:
        print(f"Error in review file: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"\nCorroboration review, bar {PRECISION_BAR:.0%}, minimum {args.minimum} rows per stratum")
    for s in scores:
        print(f"  {s.label:<12} {s.genuine:>4}/{s.reviewed:<4} {s.precision:6.1%}  {s.status}")
    if review_passes(scores):
        print("PASS — every stratum meets the bar.")
        return
    print("FAIL — a stratum is below the bar or insufficient.")
    sys.exit(2)


if __name__ == "__main__":
    main()

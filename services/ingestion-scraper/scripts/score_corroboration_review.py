#!/usr/bin/env python
"""Score a completed corroboration review file and report precision.

Usage:
    uv run python scripts/score_corroboration_review.py review_3_2.jsonl

Each line in the input must have a "verdict" field set to one of:
  "genuine"          — the two sources independently report the same real signal
  "coincidental"     — same entity key, but unrelated biological context
  "extraction_error" — wrong gene/company extracted; the signal itself is noise

Prints:
  - total reviewed
  - counts per verdict
  - corroboration precision = genuine / (genuine + coincidental + extraction_error)
  - pass/fail against the 0.85 precision threshold
"""
import json
import sys
from collections import Counter
from pathlib import Path

PRECISION_THRESHOLD = 0.85
VALID_VERDICTS = {"genuine", "coincidental", "extraction_error"}


def main() -> None:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <review.jsonl>", file=sys.stderr)
        sys.exit(1)

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"File not found: {path}", file=sys.stderr)
        sys.exit(1)

    records = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    counts: Counter[str] = Counter()
    errors: list[str] = []

    for i, r in enumerate(records, 1):
        verdict = r.get("verdict", "").strip()
        if not verdict:
            errors.append(f"  line {i}: missing verdict (entity_key={r.get('entity_key', '?')})")
            continue
        if verdict not in VALID_VERDICTS:
            errors.append(f"  line {i}: unknown verdict {verdict!r}")
            continue
        counts[verdict] += 1

    if errors:
        print("Errors in review file:")
        for e in errors:
            print(e)
        sys.exit(1)

    total = sum(counts.values())
    if total == 0:
        print("No verdicted records found.", file=sys.stderr)
        sys.exit(1)

    precision = counts["genuine"] / total

    print("\nCorroboration Review Results")
    print(f"{'─' * 35}")
    print(f"  Total reviewed:      {total}")
    print(f"  Genuine:             {counts['genuine']}")
    print(f"  Coincidental:        {counts['coincidental']}")
    print(f"  Extraction error:    {counts['extraction_error']}")
    print(f"{'─' * 35}")
    print(f"  Corroboration precision: {precision:.1%}")
    print()

    if precision >= PRECISION_THRESHOLD:
        print(f"PASS — precision {precision:.1%} ≥ {PRECISION_THRESHOLD:.0%} threshold.")
        print("Phase 4 backtest is meaningful. Proceed.")
    else:
        print(f"FAIL — precision {precision:.1%} < {PRECISION_THRESHOLD:.0%} threshold.")
        print("Fix extraction or normalization before running Phase 4.")
        print("Feed extraction_error cases back into the golden set (tests/golden/).")
        sys.exit(2)


if __name__ == "__main__":
    main()

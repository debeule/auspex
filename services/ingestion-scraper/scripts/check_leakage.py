#!/usr/bin/env python
"""Flag months with ≥70% correct answers after the model's claimed knowledge cutoff.

Never run in CI.
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import yaml

from auspex_ingest.model_evaluation import sample_leakage_manifest, score_leakage

_FLAG_THRESHOLD = 0.70


def _ask_model(
    entries: list[dict],
    model_id: str,
    base_url: str | None,
    api_key: str | None,
) -> list[str]:
    import openai

    client = openai.OpenAI(api_key=api_key or "sk-dummy", base_url=base_url)
    answers: list[str] = []

    for i, entry in enumerate(entries, 1):
        prompt = (
            f"Event ID: {entry['event_id']}\n"
            f"Source: {entry['source_type']}\n"
            f"Published: {entry['published_month']}\n\n"
            f"Question: {entry['question']}\n"
            "Answer with a single word: positive, negative, or neutral."
        )
        print(f"  [{i}/{len(entries)}] {entry['source_type']}/{entry['event_id']}", end="", flush=True)
        try:
            resp = client.chat.completions.create(
                model=model_id,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10,
                temperature=0.0,
            )
            answer = resp.choices[0].message.content.strip().lower()
        except Exception as exc:  # noqa: BLE001
            print(f" ERROR: {exc}")
            answer = "error"
        print(f" → {answer}")
        answers.append(answer)

    return answers


def main() -> None:
    parser = argparse.ArgumentParser(description="Leakage canary for a candidate model")
    parser.add_argument("--model", required=True)
    parser.add_argument(
        "--manifest",
        default="tests/fixtures/leakage_outcomes.jsonl",
        type=Path,
    )
    parser.add_argument(
        "--registry",
        default=Path(__file__).parent.parent.parent.parent / "config" / "models" / "registry.yaml",
        type=Path,
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--sample", type=int, default=None)
    args = parser.parse_args()

    if not args.manifest.exists():
        print(f"Manifest not found: {args.manifest}")
        print("Populate tests/fixtures/leakage_outcomes.jsonl before running the canary.")
        sys.exit(1)

    entries = [json.loads(line) for line in args.manifest.read_text().splitlines() if line.strip()]
    if not entries:
        print("Manifest is empty.")
        sys.exit(1)

    raw_registry = yaml.safe_load(args.registry.read_text())
    if args.model not in raw_registry.get("models", {}):
        print(f"Model {args.model!r} not in registry.")
        sys.exit(1)

    cutoff = raw_registry["models"][args.model].get("cutoff_date", "")
    sample = sample_leakage_manifest(entries, seed=args.seed, n=args.sample or len(entries))

    base_url = os.environ.get("EXTRACTION_BASE_URL")
    api_key = os.environ.get("EXTRACTION_API_KEY") or os.environ.get("OPENAI_API_KEY")

    print(f"Model: {args.model}  claimed cutoff: {cutoff}  entries: {len(sample)}")
    answers = _ask_model(sample, args.model, base_url, api_key)
    result = score_leakage(sample, answers)

    print("\n  By month:")
    for month, s in sorted(result["by_month"].items()):
        flag = ""
        if cutoff and month > cutoff[:7] and s["rate"] >= _FLAG_THRESHOLD:
            flag = f"  ← FLAG: {s['rate']:.0%} correct after cutoff {cutoff[:7]}"
        print(f"    {month}  correct={s['correct']}/{s['total']}  rate={s['rate']:.0%}{flag}")

    print("\n  By source type:")
    for src, s in sorted(result["by_source_type"].items()):
        print(f"    {src}  correct={s['correct']}/{s['total']}  rate={s['rate']:.0%}")

    flags = [
        m for m, s in result["by_month"].items()
        if cutoff and m > cutoff[:7] and s["rate"] >= _FLAG_THRESHOLD
    ]
    if flags:
        print(f"\n  Model {args.model!r} claims cutoff {cutoff}; rate ≥ {_FLAG_THRESHOLD:.0%} in: {flags}")
        print("  Record this in DECISIONS.md before proceeding.")


if __name__ == "__main__":
    main()

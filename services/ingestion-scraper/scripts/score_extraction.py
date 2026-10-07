#!/usr/bin/env python
"""Manual scoring script — run against the golden set to measure extraction quality.

Usage:
    uv run python scripts/score_extraction.py --model gpt-4o-mini-2024-07-18 \
        [--golden-dir tests/golden] [--prompt-version v1.0] \
        [--prefilter-vocab config/gene_vocab.txt] \
        [--registry config/models/registry.yaml] \
        [--scores-dir config/models/scores]

For a local model set EXTRACTION_BASE_URL (e.g. the Ollama /v1 endpoint); for the API
set EXTRACTION_API_KEY (or OPENAI_API_KEY).
Never run this in CI — it makes live LLM calls.
"""
import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import yaml

from auspex_ingest.extraction_backend import score_file_name
from auspex_ingest.golden import GoldenDocument, load_golden_set, score_batch
from auspex_ingest.model_evaluation import GATE_PRECISION, gate_record
from auspex_ingest.prefilter import Prefilter


def _build_prefilter(vocab_path: Path | None) -> Prefilter:
    if vocab_path and vocab_path.exists():
        terms = {line.strip() for line in vocab_path.read_text().splitlines() if line.strip()}
        return Prefilter.from_vocab(terms)
    return Prefilter.from_vocab(set())


def _run_extraction(
    golden: list[GoldenDocument],
    prefilter: Prefilter,
    prompt_version: str,
    model_id: str,
    registry_path: Path,
    base_url: str | None,
    api_key: str | None,
) -> list[dict | None]:
    from auspex_ingest.extraction_backend import make_evaluation_extractor
    from auspex_ingest.models import RawDocument

    extractor = make_evaluation_extractor(
        registry_path=registry_path,
        model_id=model_id,
        prompt_version=prompt_version,
        base_url=base_url,
        api_key=api_key,
    )

    results = []
    for i, doc in enumerate(golden, 1):
        raw = RawDocument(
            schema_version="1.0",
            external_id=doc.external_id,
            source_type=doc.source_type,
            source_url=doc.source_url,
            published_date=datetime.fromisoformat(doc.published_date),
            raw_content=doc.raw_content,
            content_sha256=__import__("hashlib").sha256(doc.raw_content.encode()).hexdigest(),
            retrieved_at=datetime.now(UTC),
        )

        prefilter_pass = prefilter.passes(raw)
        print(
            f"  [{i}/{len(golden)}] {doc.source_type}/{doc.external_id} "
            f"prefilter={'pass' if prefilter_pass else 'REJECT'}",
            end="",
            flush=True,
        )

        if not prefilter_pass:
            results.append(None)
            print()
            continue

        try:
            event = extractor.extract(raw, prefilter_version=prefilter.version, raw_object_key="")
        except Exception as exc:  # noqa: BLE001
            print(f" ERROR: {exc}")
            results.append(None)
            continue

        if event is None:
            print(" → not-signal")
            results.append(None)
        else:
            print(f" → signal (confidence={event.confidence_score:.2f})")
            results.append({
                "is_signal": True,
                "gene_targets": event.gene_targets,
                "mechanisms": event.mechanisms,
                "companies_mentioned": event.companies_mentioned,
                "directionality": event.directionality,
                "prompt_version": event.prompt_version,
                "prefilter_version": event.prefilter_version,
                "prefilter_passed": True,
            })

    return results


def _print_report(golden: list[GoldenDocument], results: list[dict | None], scores: dict) -> None:
    cm = scores["is_signal"]
    total = cm["tp"] + cm["fp"] + cm["fn"] + cm["tn"]
    accuracy = (cm["tp"] + cm["tn"]) / total if total else 0.0
    precision = cm["tp"] / (cm["tp"] + cm["fp"]) if (cm["tp"] + cm["fp"]) else 0.0
    recall = cm["tp"] / (cm["tp"] + cm["fn"]) if (cm["tp"] + cm["fn"]) else 0.0

    print("\n is_signal")
    print(f"  TP={cm['tp']}  FP={cm['fp']}  FN={cm['fn']}  TN={cm['tn']}")
    print(f"  accuracy={accuracy:.3f}  precision={precision:.3f}  recall={recall:.3f}")

    for field in ["gene_targets", "mechanisms", "companies_mentioned"]:
        s = scores[field]
        print(f"\n {field} (macro over signal docs)")
        print(f"  precision={s['precision']:.3f}  recall={s['recall']:.3f}  f1={s['f1']:.3f}")

    pf_should_pass = [d for d in golden if d.labels.get("prefilter_should_pass")]
    pf_rejected = [
        d
        for d, r in zip(golden, results)
        if d.labels.get("prefilter_should_pass") and r is None
    ]
    if pf_should_pass:
        fn_rate = len(pf_rejected) / len(pf_should_pass)
        print("\n prefilter false-negative rate")
        print(
            f"  {len(pf_rejected)}/{len(pf_should_pass)} docs that should pass were rejected "
            f"(rate={fn_rate:.3f})"
        )


def main() -> None:
    import os

    parser = argparse.ArgumentParser(description="Score LLM extraction against the golden set")
    parser.add_argument("--model", required=True, help="Registry key (e.g. gpt-4o-mini-2024-07-18)")
    parser.add_argument("--golden-dir", default="tests/golden", type=Path)
    parser.add_argument("--prompt-version", default="v1.0")
    parser.add_argument("--prefilter-vocab", default=None, type=Path)
    parser.add_argument(
        "--registry",
        default=Path(__file__).parent.parent.parent.parent / "config" / "models" / "registry.yaml",
        type=Path,
    )
    parser.add_argument(
        "--scores-dir",
        default=Path(__file__).parent.parent.parent.parent / "config" / "models" / "scores",
        type=Path,
    )
    args = parser.parse_args()

    raw_registry = yaml.safe_load(args.registry.read_text())
    models = raw_registry.get("models", {})
    if args.model not in models:
        print(f"Model {args.model!r} not found in registry. Available: {sorted(models)}")
        sys.exit(1)

    golden = load_golden_set(args.golden_dir)
    if not golden:
        print(f"No golden documents found in {args.golden_dir}. Populate it first.")
        sys.exit(1)

    base_url: str | None = os.environ.get("EXTRACTION_BASE_URL")
    api_key: str | None = os.environ.get("EXTRACTION_API_KEY") or os.environ.get("OPENAI_API_KEY")

    print(f"Loaded {len(golden)} golden documents")
    print(f"Model: {args.model}  prompt_version: {args.prompt_version}")
    prefilter = _build_prefilter(args.prefilter_vocab)

    results = _run_extraction(
        golden,
        prefilter,
        args.prompt_version,
        args.model,
        args.registry,
        base_url,
        api_key,
    )
    scores = score_batch(golden, results)
    _print_report(golden, results, scores)

    cm = scores["is_signal"]
    precision = cm["tp"] / (cm["tp"] + cm["fp"]) if (cm["tp"] + cm["fp"]) else 0.0
    record = gate_record(args.model, args.prompt_version, prefilter.version, precision=precision)
    passed = record["passed"]

    args.scores_dir.mkdir(parents=True, exist_ok=True)
    score_file = args.scores_dir / score_file_name(args.model)
    score_file.write_text(json.dumps(record, indent=2))
    status = "PASSED" if passed else "FAILED"
    print(
        f"\nGate {status} (precision={precision:.3f}, threshold={GATE_PRECISION}). "
        f"Score written to {score_file}"
    )


if __name__ == "__main__":
    main()

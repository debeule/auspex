#!/usr/bin/env python
# Writes a latency record to config/models/latency/<model_slug>.json.
# Never run in CI — makes live LLM calls.
import argparse
import json
import os
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import yaml

from auspex_ingest.golden import GoldenDocument, load_golden_set
from auspex_ingest.model_evaluation import compute_candidate_scores, sample_golden
from auspex_ingest.prefilter import Prefilter


def _slug(model_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]", "_", model_id)


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
) -> tuple[list[dict | None], list[float]]:
    from auspex_ingest.extraction_backend import make_evaluation_extractor
    from auspex_ingest.models import RawDocument

    extractor = make_evaluation_extractor(
        registry_path=registry_path,
        model_id=model_id,
        prompt_version=prompt_version,
        base_url=base_url,
        api_key=api_key,
    )

    results: list[dict | None] = []
    latencies: list[float] = []

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
        print(f"  [{i}/{len(golden)}] {doc.source_type}/{doc.external_id}", end="", flush=True)
        if not prefilter.passes(raw):
            print(" prefilter=REJECT")
            results.append(None)
            latencies.append(0.0)
            continue

        t0 = time.monotonic()
        try:
            event = extractor.extract(raw, prefilter_version=prefilter.version, raw_object_key="")
        except Exception as exc:  # noqa: BLE001
            print(f" ERROR: {exc}")
            results.append(None)
            latencies.append(time.monotonic() - t0)
            continue

        lat = time.monotonic() - t0
        latencies.append(lat)

        if event is None:
            print(f" not-signal ({lat:.2f}s)")
            results.append(None)
        else:
            print(f" signal confidence={event.confidence_score:.2f} ({lat:.2f}s)")
            results.append({
                "is_signal": True,
                "gene_targets": event.gene_targets,
                "mechanisms": event.mechanisms,
                "companies_mentioned": event.companies_mentioned,
                "directionality": event.directionality,
            })

    return results, latencies


def _print_feasibility(
    model_id: str,
    mean_lat: float,
    p95_lat: float,
    backfill_docs: int = 26_000,
    daily_budget_docs: int = 500,
) -> None:
    backfill_hours = (backfill_docs * mean_lat) / 3600
    daily_hours = (daily_budget_docs * mean_lat) / 3600
    print(f"\n  Throughput feasibility ({model_id}):")
    print(f"    24-month backfill ({backfill_docs:,} docs @ {mean_lat:.1f}s mean): ~{backfill_hours:.0f} h")
    print(f"    Steady-state daily budget ({daily_budget_docs} docs): ~{daily_hours:.1f} h/day")

    # 8 GB baseline for Docker Desktop containers + model KV cache heuristic
    model_lower = model_id.lower()
    if "27b" in model_lower:
        model_gb = 17
    elif "24b" in model_lower:
        model_gb = 14
    elif "8b" in model_lower:
        model_gb = 8
    else:
        model_gb = 0
    combined = 8 + model_gb
    if combined > 30:
        print(f"    WARNING: combined memory ~{combined} GB exceeds 30 GB budget (Docker ~8 GB + model ~{model_gb} GB)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a candidate model against the golden set")
    parser.add_argument("--model", required=True, help="Registry key (e.g. mistral-small:24b-instruct-2501-q4_K_M)")
    parser.add_argument("--golden-dir", default="tests/golden", type=Path)
    parser.add_argument("--prompt-version", default="v1.0")
    parser.add_argument("--prefilter-vocab", default=None, type=Path)
    parser.add_argument(
        "--registry",
        default=Path(__file__).parent.parent.parent.parent / "config" / "models" / "registry.yaml",
        type=Path,
    )
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--sample", type=int, default=None, help="Subsample N docs from the golden set")
    args = parser.parse_args()

    raw_registry = yaml.safe_load(args.registry.read_text())
    if args.model not in raw_registry.get("models", {}):
        print(f"Model {args.model!r} not in registry. Available: {sorted(raw_registry.get('models', {}))}")
        sys.exit(1)

    golden_all = load_golden_set(args.golden_dir)
    if not golden_all:
        print(f"No golden documents in {args.golden_dir}.")
        sys.exit(1)

    golden = sample_golden(golden_all, seed=args.seed or 0, n=args.sample)
    prefilter = _build_prefilter(args.prefilter_vocab)
    base_url = os.environ.get("EXTRACTION_BASE_URL")
    api_key = os.environ.get("EXTRACTION_API_KEY") or os.environ.get("OPENAI_API_KEY")

    print(f"Model: {args.model}  docs: {len(golden)}/{len(golden_all)}  prompt: {args.prompt_version}")
    results, latencies = _run_extraction(
        golden, prefilter, args.prompt_version, args.model, args.registry, base_url, api_key
    )

    scores = compute_candidate_scores(golden, results, latencies)
    cm = scores["cm"]
    print(f"\n  is_signal  TP={cm['tp']}  FP={cm['fp']}  FN={cm['fn']}  TN={cm['tn']}")
    print(f"  precision={scores['precision']:.3f}  recall={scores['recall']:.3f}")
    print(f"  latency   mean={scores['mean_latency_s']:.2f}s  p95={scores['p95_latency_s']:.2f}s")

    _print_feasibility(args.model, scores["mean_latency_s"], scores["p95_latency_s"])

    status = "PASSED" if scores["passed"] else "FAILED (< 0.85 precision)"
    print(f"\n  Gate {status}")

    # Write latency record
    latency_dir = Path(__file__).parent.parent.parent.parent / "config" / "models" / "latency"
    latency_dir.mkdir(parents=True, exist_ok=True)
    slug = _slug(args.model)
    record = {
        "model_id": args.model,
        "mean_latency_s": round(scores["mean_latency_s"], 4),
        "p95_latency_s": round(scores["p95_latency_s"], 4),
        "measured_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    (latency_dir / f"{slug}.json").write_text(json.dumps(record, indent=2))
    print(f"  Latency record written to config/models/latency/{slug}.json")


if __name__ == "__main__":
    main()

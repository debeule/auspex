#!/usr/bin/env python
# Pulls from MinIO, does not call connectors — results are reproducible from archived data alone.
# Never run in CI.
import argparse
import hashlib
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import yaml

from auspex_ingest.model_evaluation import compute_model_agreement, sample_archive_keys


def _extract_batch(
    docs: list[dict],
    model_id: str,
    prompt_version: str,
    base_url: str | None,
    api_key: str | None,
) -> list[dict | None]:
    import instructor
    import openai

    from auspex_ingest.extractor import LLMExtractor
    from auspex_ingest.models import RawDocument

    prompt_dir = Path(__file__).parent.parent / "prompts" / "extraction"
    prompt_text = (prompt_dir / f"{prompt_version}.txt").read_text()

    client = instructor.from_openai(
        openai.OpenAI(api_key=api_key or "sk-dummy", base_url=base_url)
    )
    extractor = LLMExtractor(
        client=client,
        model=model_id,
        schema_version="1.0",
        prompt_version=prompt_version,
    )
    extractor._prompt = prompt_text

    results: list[dict | None] = []
    for i, doc in enumerate(docs, 1):
        raw_content = doc.get("raw_content", "")
        raw = RawDocument(
            schema_version="1.0",
            external_id=doc.get("external_id", f"unknown:{i}"),
            source_type=doc.get("source_type", "unknown"),
            source_url=doc.get("source_url", ""),
            published_date=datetime.fromisoformat(doc["published_date"]),
            raw_content=raw_content,
            content_sha256=hashlib.sha256(raw_content.encode()).hexdigest(),
            retrieved_at=datetime.now(UTC),
        )
        print(f"  [{i}/{len(docs)}] {raw.source_type}/{raw.external_id}", end="", flush=True)
        try:
            event = extractor.extract(raw, prefilter_version="v1", raw_object_key="")
        except Exception as exc:  # noqa: BLE001
            print(f" ERROR: {exc}")
            results.append(None)
            continue

        if event is None:
            print(" not-signal")
            results.append(None)
        else:
            print(f" signal confidence={event.confidence_score:.2f}")
            results.append({
                "is_signal": True,
                "gene_targets": event.gene_targets,
                "mechanisms": event.mechanisms,
                "directionality": event.directionality,
                "confidence_score": float(event.confidence_score),
            })

    return results


def _load_from_minio(keys: list[str]) -> list[dict]:
    import minio

    endpoint = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
    access_key = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
    secret_key = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
    bucket = os.environ.get("MINIO_RAW_BUCKET", "auspex-raw")

    client = minio.Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=False)
    docs = []
    for key in keys:
        response = client.get_object(bucket, key)
        docs.append(json.loads(response.read()))
    return docs


def main() -> None:
    parser = argparse.ArgumentParser(description="Cross-model agreement comparison")
    parser.add_argument("--model-a", required=True)
    parser.add_argument("--model-b", required=True)
    parser.add_argument(
        "--registry",
        default=Path(__file__).parent.parent.parent.parent / "config" / "models" / "registry.yaml",
        type=Path,
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--sample", type=int, default=100)
    parser.add_argument("--prompt-version", default="v1.0")
    args = parser.parse_args()

    raw_registry = yaml.safe_load(args.registry.read_text())
    for m in [args.model_a, args.model_b]:
        if m not in raw_registry.get("models", {}):
            print(f"Model {m!r} not in registry.")
            sys.exit(1)

    # List all raw archive keys
    import minio as _minio
    endpoint = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
    mc = _minio.Minio(endpoint, access_key=os.environ.get("MINIO_ACCESS_KEY", "minioadmin"),
                      secret_key=os.environ.get("MINIO_SECRET_KEY", "minioadmin"), secure=False)
    bucket = os.environ.get("MINIO_RAW_BUCKET", "auspex-raw")
    all_keys = [obj.object_name for obj in mc.list_objects(bucket, recursive=True)]

    if not all_keys:
        print("MinIO archive is empty — run ingestion first.")
        sys.exit(1)

    keys = sample_archive_keys(all_keys, seed=args.seed, n=args.sample)
    docs = _load_from_minio(keys)

    base_url = os.environ.get("EXTRACTION_BASE_URL")
    api_key = os.environ.get("EXTRACTION_API_KEY") or os.environ.get("OPENAI_API_KEY")

    print(f"Model A: {args.model_a}")
    results_a = _extract_batch(docs, args.model_a, args.prompt_version, base_url, api_key)

    print(f"\nModel B: {args.model_b}")
    results_b = _extract_batch(docs, args.model_b, args.prompt_version, base_url, api_key)

    m = compute_model_agreement(results_a, results_b)
    print(f"\n  is_signal  agreement={m['is_signal_agreement']:.0%}  "
          f"both_signal={m['both_signal']}  both_not={m['both_not']}  disagree={m['disagree']}")
    print(f"  jaccard    gene_targets={m['jaccard_gene_targets']:.3f}  mechanisms={m['jaccard_mechanisms']:.3f}")
    print(f"  direction  agreement={m['directionality_agreement']:.0%}")
    if m["confidence_pearson"] is not None:
        print(f"  confidence Pearson r={m['confidence_pearson']:.3f}")
    else:
        print("  confidence Pearson: insufficient signal pairs")

    if m["is_signal_agreement"] < 0.85:
        print(f"\n  WARNING: is_signal agreement {m['is_signal_agreement']:.0%} < 85% — "
              "the two models extract materially different corpora. Record in DECISIONS.md.")


if __name__ == "__main__":
    main()

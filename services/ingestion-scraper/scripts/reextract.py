#!/usr/bin/env python
"""Re-extraction CLI — re-run LLM extraction against archived MinIO documents.

Run this before any prompt or model version bump to re-extract historical
documents under the new versions. Core-hub handles idempotent upserts via
event_id, so re-publishing is safe.

Usage:
    cd services/ingestion-scraper
    uv run python scripts/reextract.py --prompt-version v2 --dry-run
    uv run python scripts/reextract.py --source-type biorxiv --since 2024-01-01 --prompt-version v2
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT / "src"))


def _load_env() -> None:
    env_file = _ROOT.parent.parent / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        if k not in os.environ:
            os.environ[k] = v.strip()


_load_env()


def _build_runner(args: argparse.Namespace):  # type: ignore[no-untyped-def]
    from confluent_kafka import Producer as ConfluentProducer
    from minio import Minio

    from auspex_ingest.extraction_backend import build_extractor_from_env
    from auspex_ingest.messaging import KafkaProducerClient
    from auspex_ingest.reextract import ReextractionRunner
    from auspex_ingest.storage.minio_client import MinioArchive

    minio_client = Minio(
        os.environ["MINIO_ENDPOINT"],
        access_key=os.environ["MINIO_ACCESS_KEY"],
        secret_key=os.environ["MINIO_SECRET_KEY"],
        secure=False,
    )
    archive = MinioArchive(client=minio_client, bucket=os.environ["MINIO_BUCKET"])

    gene_vocab: frozenset[str] | None = None
    if args.gene_vocab_file:
        vocab_path = Path(args.gene_vocab_file)
        gene_vocab = frozenset(vocab_path.read_text().splitlines())

    extractor = build_extractor_from_env(
        schema_version=args.schema_version,
        prompt_version=args.prompt_version,
        model_id=args.model,
        gene_vocab=gene_vocab,
    )

    producer = KafkaProducerClient(
        ConfluentProducer({"bootstrap.servers": os.environ["KAFKA_BOOTSTRAP_SERVERS"]}),
        raw_topic=os.environ.get("KAFKA_RAW_TOPIC", "auspex.raw.ingested"),
        signals_topic=os.environ.get("KAFKA_SIGNALS_TOPIC", "auspex.signals.extracted"),
    )

    return ReextractionRunner(archive=archive, extractor=extractor, producer=producer)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--source-type", help="Restrict to a single source type")
    parser.add_argument("--since", help="Only re-extract documents published on or after this date (YYYY-MM-DD)")
    parser.add_argument("--until", help="Only re-extract documents published on or before this date (YYYY-MM-DD)")
    parser.add_argument(
        "--prompt-version",
        help="Prompt version to use (default: $EXTRACTION_PROMPT_VERSION, else v1.0)",
    )
    parser.add_argument("--model", help="Registry key of the model to use (default: $EXTRACTION_MODEL)")
    parser.add_argument("--schema-version", default="1.0", help="Schema version to stamp on events")
    parser.add_argument("--prefilter-version", default="v1", help="Pre-filter version to stamp on events")
    parser.add_argument(
        "--skip-prefilter",
        action="store_true",
        help=(
            "Skip the pre-filter step. Use only when you explicitly accept that documents "
            "originally filtered out may now be passed through. The pre-filter vocabulary "
            "may have changed since original ingestion."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count matching documents without calling the LLM or publishing anything",
    )
    parser.add_argument(
        "--gene-vocab-file",
        help="Path to a newline-delimited HGNC symbol list for gene target filtering. "
             "If omitted, the vocabulary filter is not applied.",
    )
    args = parser.parse_args()

    if args.dry_run:
        print("DRY RUN — no LLM calls, no Kafka publishes", flush=True)
    else:
        runner = _build_runner(args)
        result = runner.run(
            source_type=args.source_type,
            since=args.since,
            until=args.until,
            prompt_version=args.prompt_version,
            model=args.model,
            schema_version=args.schema_version,
            prefilter_version=args.prefilter_version,
            skip_prefilter=args.skip_prefilter,
            dry_run=False,
        )
        _print_result(result)
        return

    # dry-run path: build archive without LLM/Kafka deps
    import os as _os
    from unittest.mock import MagicMock

    from minio import Minio as _Minio

    from auspex_ingest.reextract import ReextractionRunner as _Runner
    from auspex_ingest.storage.minio_client import MinioArchive as _MinioArchive

    minio_client = _Minio(
        _os.environ["MINIO_ENDPOINT"],
        access_key=_os.environ["MINIO_ACCESS_KEY"],
        secret_key=_os.environ["MINIO_SECRET_KEY"],
        secure=False,
    )
    archive = _MinioArchive(client=minio_client, bucket=_os.environ["MINIO_BUCKET"])
    runner = _Runner(archive=archive, extractor=MagicMock(), producer=MagicMock())
    result = runner.run(
        source_type=args.source_type,
        since=args.since,
        until=args.until,
        prompt_version=args.prompt_version,
        model=args.model,
        schema_version=args.schema_version,
        prefilter_version=args.prefilter_version,
        skip_prefilter=args.skip_prefilter,
        dry_run=True,
    )
    _print_result(result)


def _print_result(result: dict) -> None:  # type: ignore[type-arg]
    print(
        f"scanned={result['scanned']}  "
        f"skipped_by_filter={result['skipped_by_filter']}  "
        f"not_signal={result['not_signal']}  "
        f"published={result['published']}  "
        f"failed={result['failed']}",
        flush=True,
    )


if __name__ == "__main__":
    main()

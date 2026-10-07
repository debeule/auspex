#!/usr/bin/env python
"""Historical backfill — one source over a bounded historical window.

Always dry-run first. The dry run fetches documents (no LLM calls, no archive,
no Kafka), estimates LLM calls and cost/time, reports documents already
extracted under other models, and records its estimate in a MinIO manifest.
A live run must name that dry run with --estimate-run-id; it aborts before any
LLM call if the estimate exceeds BACKFILL_TIME_CEILING_HOURS (local backend) or
BACKFILL_BUDGET_CEILING (API backend).

The live run is gated on explicit human sign-off (DECISIONS.md 2026-09-20).

Usage:
    cd services/ingestion-scraper
    uv run python scripts/run_backfill.py --source-type biorxiv \\
        --start-date 2025-01-01 --end-date 2025-01-31 --dry-run
    uv run python scripts/run_backfill.py --source-type biorxiv \\
        --start-date 2025-01-01 --end-date 2025-01-31 --estimate-run-id <run_id>

Interrupted live runs resume from the last completed window: re-run the same
command. Checkpoints live under backfill/checkpoints/ in MinIO.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, date, datetime
from pathlib import Path

_ROOT = Path(__file__).parent.parent
_REPO = _ROOT.parent.parent
sys.path.insert(0, str(_ROOT / "src"))


def _load_env() -> None:
    env_file = _REPO / ".env"
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


def _ollama_digest_fn(base_url: str):  # type: ignore[no-untyped-def]
    """Return tag -> 'tag@sha256:<digest>' as reported by the running Ollama server."""
    import httpx

    root = base_url.rstrip("/").removesuffix("/v1")

    def digest(tag: str) -> str:
        resp = httpx.get(f"{root}/api/tags", timeout=10.0)
        resp.raise_for_status()
        for m in resp.json().get("models", []):
            if m.get("name") == tag or m.get("model") == tag:
                return f"{tag}@sha256:{m['digest']}"
        return f"{tag}@<not pulled>"

    return digest


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--source-type", required=True,
                        help="biorxiv | clinicaltrials | pubmed | edgar | epo_ops")
    parser.add_argument("--start-date", required=True, type=date.fromisoformat)
    parser.add_argument("--end-date", required=True, type=date.fromisoformat)
    parser.add_argument("--margin-months", type=int, default=3,
                        help="Months after the model's training cutoff before the window may start")
    parser.add_argument("--window-days", type=int, default=30,
                        help="Checkpoint/query window size. Use 7 for epo_ops (2,000-result cap per query)")
    parser.add_argument("--prompt-version", default=os.environ.get("EXTRACTION_PROMPT_VERSION", "v1.0"))
    parser.add_argument("--prefilter-version",
                        default=os.environ.get("EXTRACTION_PREFILTER_VERSION", "v1.0"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--estimate-run-id",
                        help="Run id of the approved dry run (required without --dry-run)")
    args = parser.parse_args()

    if not args.dry_run and not args.estimate_run_id:
        parser.error("a live run needs --estimate-run-id from a completed --dry-run")

    import yaml
    from minio import Minio

    from auspex_ingest.backfill import (
        BackfillRunner,
        BackfillStore,
        CoreHubExtractionHistory,
        ModelProfile,
    )
    from auspex_ingest.connectors import RateLimitedClient
    from auspex_ingest.connectors.registry import CONNECTOR_HOSTS, build_connector
    from auspex_ingest.dag_factory import load_sources_config
    from auspex_ingest.prefilter import Prefilter

    sources = {e.source_type: e for e in load_sources_config(_ROOT / "config" / "sources.yaml").sources}
    if args.source_type not in sources or args.source_type not in CONNECTOR_HOSTS:
        parser.error(f"unknown source type {args.source_type!r}; choose from {sorted(CONNECTOR_HOSTS)}")

    model_id = os.environ.get("EXTRACTION_MODEL", "")
    registry_path = _REPO / "config" / "models" / "registry.yaml"
    registry = yaml.safe_load(registry_path.read_text()).get("models", {})
    if model_id not in registry:
        sys.exit(f"EXTRACTION_MODEL={model_id!r} not in {registry_path}; available: {sorted(registry)}")
    prompt_dir = _ROOT / "prompts" / "extraction"
    prompt_text = (prompt_dir / f"{args.prompt_version}.txt").read_text()
    model = ModelProfile(
        model_id=model_id,
        entry=registry[model_id],
        prompt_version=args.prompt_version,
        prefilter_version=args.prefilter_version,
        prompt_tokens=len(prompt_text) // 4,
    )

    # One shared, blocking limiter for every connector this process builds.
    shared_client = RateLimitedClient(
        {CONNECTOR_HOSTS[st]: e.rate_limit_rps for st, e in sources.items() if st in CONNECTOR_HOSTS},
        block=True,
    )

    def connector_factory(source_type: str, until: datetime):  # type: ignore[no-untyped-def]
        return build_connector(
            source_type, client=shared_client,
            source_config=sources[source_type].source_config, env=os.environ, until=until,
        )

    def prefilter_factory(source_type: str) -> Prefilter:
        return Prefilter.from_vocab(set(sources[source_type].prefilter_vocabulary),
                                    version=args.prefilter_version)

    minio_client = Minio(
        os.environ["MINIO_ENDPOINT"],
        access_key=os.environ["MINIO_ACCESS_KEY"],
        secret_key=os.environ["MINIO_SECRET_KEY"],
        secure=False,
    )
    bucket = os.environ["MINIO_BUCKET"]

    pipeline_factory = _live_pipeline_factory(args, model, minio_client, bucket, prefilter_factory) \
        if not args.dry_run else _no_pipeline

    runner = BackfillRunner(
        model=model,
        connector_factory=connector_factory,
        pipeline_factory=pipeline_factory,
        prefilter_factory=prefilter_factory,
        store=BackfillStore(client=minio_client, bucket=bucket),
        history=CoreHubExtractionHistory(base_url=os.environ["CORE_HUB_URL"]),
        latency_dir=_REPO / "config" / "models" / "latency",
        env=os.environ,
        now=lambda: datetime.now(UTC),
    )

    if args.dry_run:
        report = runner.dry_run(
            source_type=args.source_type, start=args.start_date, end=args.end_date,
            margin_months=args.margin_months, window_days=args.window_days,
        )
        print(report.render(), flush=True)
        print(f"\nApprove this estimate, then run the live backfill with --estimate-run-id {report.run_id}")
        return

    result = runner.run(
        source_type=args.source_type, start=args.start_date, end=args.end_date,
        estimate_run_id=args.estimate_run_id,
        margin_months=args.margin_months, window_days=args.window_days,
    )
    print(f"BACKFILL {result.run_id}: {result.windows_run} window(s) run, "
          f"{result.windows_skipped} already checkpointed")
    for source_type, counts in result.counts.items():
        print(f"  {source_type}: " + "  ".join(f"{k}={v}" for k, v in counts.items()))


def _no_pipeline(source_type, connector):  # type: ignore[no-untyped-def]
    raise RuntimeError("dry run must not build an ingestion pipeline")


def _live_pipeline_factory(args, model, minio_client, bucket, prefilter_factory):  # type: ignore[no-untyped-def]
    from confluent_kafka import Producer as ConfluentProducer

    from auspex_ingest.extraction_backend import LLMExtractorFactory
    from auspex_ingest.messaging import KafkaProducerClient
    from auspex_ingest.normalizer import IdentityNormalizer
    from auspex_ingest.pipeline import IngestionPipeline
    from auspex_ingest.storage.minio_client import MinioArchive

    base_url = os.environ.get("EXTRACTION_BASE_URL") or None
    # Fails here, before any fetch, if the gate record or the pinned digest is wrong.
    factory = LLMExtractorFactory(
        registry_path=_REPO / "config" / "models" / "registry.yaml",
        scores_dir=_REPO / "config" / "models" / "scores",
        model_id=model.model_id,
        base_url=base_url,
        api_key=os.environ.get("EXTRACTION_API_KEY") or os.environ.get("OPENAI_API_KEY"),
        prompt_version=model.prompt_version,
        prefilter_version=model.prefilter_version,
        model_info_fn=_ollama_digest_fn(base_url) if model.backend == "local" and base_url else None,
    )
    extractor = factory.make_extractor(schema_version="1.0", prompt_version=model.prompt_version)
    archive = MinioArchive(client=minio_client, bucket=bucket)
    producer = KafkaProducerClient(
        ConfluentProducer({"bootstrap.servers": os.environ["KAFKA_BOOTSTRAP_SERVERS"]}),
        raw_topic=os.environ.get("KAFKA_RAW_TOPIC", "auspex.raw.ingested"),
        signals_topic=os.environ.get("KAFKA_SIGNALS_TOPIC", "auspex.signals.extracted"),
    )

    def build(source_type, connector):  # type: ignore[no-untyped-def]
        return IngestionPipeline(
            connector=connector,
            archive=archive,
            extractor=extractor,
            producer=producer,
            prefilter=prefilter_factory(source_type),
            normalizer=IdentityNormalizer(),
            now=lambda: datetime.now(UTC),
            min_confidence_to_publish=0.5,
        )

    return build


if __name__ == "__main__":
    main()

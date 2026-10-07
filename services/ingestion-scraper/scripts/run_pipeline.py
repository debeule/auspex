#!/usr/bin/env python
"""Standalone pipeline runner — no Airflow dependency.

Reads config/sources.yaml, builds one pipeline per source type, and runs a
one-shot lookback (default 30 days). Skips the mock source. Safe to re-run:
MinIO archive dedup prevents duplicate extraction.

Usage:
    cd services/ingestion-scraper
    uv run python scripts/run_pipeline.py
    uv run python scripts/run_pipeline.py --days 30 --sources biorxiv clinicaltrials
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime, timedelta
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


def _build_connector(source_type: str, entry, rate_limited_client):  # type: ignore[no-untyped-def]
    from auspex_ingest.connectors.biorxiv import BiorxivConnector
    from auspex_ingest.connectors.clinicaltrials import ClinicalTrialConnector
    from auspex_ingest.connectors.pubmed import PubmedConnector
    from auspex_ingest.connectors.sec_edgar import SecEdgarConnector

    if source_type == "biorxiv":
        return BiorxivConnector(client=rate_limited_client)
    if source_type == "clinicaltrials":
        return ClinicalTrialConnector(client=rate_limited_client)
    if source_type == "pubmed":
        return PubmedConnector(
            client=rate_limited_client,
            search_term=entry.source_config.get("search_term", "gene therapy"),
            api_key=os.environ.get("NCBI_API_KEY") or None,
        )
    if source_type == "edgar":
        user_agent = os.environ.get("SEC_USER_AGENT", "")
        if not user_agent:
            raise RuntimeError("SEC_USER_AGENT is required for the edgar connector")
        return SecEdgarConnector(client=rate_limited_client, user_agent=user_agent)
    if source_type == "epo_ops":
        from auspex_ingest.connectors.epo_ops import EpoOpsConnector
        return EpoOpsConnector(
            client=rate_limited_client,
            key=os.environ.get("EPO_OPS_KEY", ""),
            secret=os.environ.get("EPO_OPS_SECRET", ""),
        )
    raise ValueError(f"No connector registered for source_type={source_type!r}")


def _build_pipeline(source_type: str, entry):  # type: ignore[no-untyped-def]
    from confluent_kafka import Producer as ConfluentProducer
    from minio import Minio

    from auspex_ingest.connectors import RateLimitedClient
    from auspex_ingest.extraction_backend import build_extractor_from_env
    from auspex_ingest.messaging import KafkaProducerClient
    from auspex_ingest.normalizer import IdentityNormalizer
    from auspex_ingest.pipeline import IngestionPipeline
    from auspex_ingest.prefilter import Prefilter
    from auspex_ingest.storage.minio_client import MinioArchive

    rate_limits: dict[str, float] = {
        "api.biorxiv.org": 3.0,
        "clinicaltrials.gov": 5.0,
        "eutils.ncbi.nlm.nih.gov": 3.0,
        "sec.gov": 4.0,
        "ops.epo.org": 2.0,
    }
    http_client = RateLimitedClient(rate_limits)
    connector = _build_connector(source_type, entry, http_client)

    minio_client = Minio(
        os.environ["MINIO_ENDPOINT"],
        access_key=os.environ["MINIO_ACCESS_KEY"],
        secret_key=os.environ["MINIO_SECRET_KEY"],
        secure=False,
    )
    archive = MinioArchive(client=minio_client, bucket=os.environ["MINIO_BUCKET"])

    extractor = build_extractor_from_env(schema_version="1.0")

    kafka_producer = KafkaProducerClient(
        ConfluentProducer({"bootstrap.servers": os.environ["KAFKA_BOOTSTRAP_SERVERS"]}),
        raw_topic=os.environ.get("KAFKA_RAW_TOPIC", "auspex.raw.ingested"),
        signals_topic=os.environ.get("KAFKA_SIGNALS_TOPIC", "auspex.signals.extracted"),
    )

    return IngestionPipeline(
        connector=connector,
        archive=archive,
        extractor=extractor,
        producer=kafka_producer,
        prefilter=Prefilter.from_vocab(set(entry.prefilter_vocabulary)),
        normalizer=IdentityNormalizer(),
        now=lambda: datetime.now(UTC),
        min_confidence_to_publish=0.5,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--days", type=int, default=30, help="Lookback window in days")
    parser.add_argument(
        "--sources", nargs="+",
        help="Source types to run (default: all non-mock entries in sources.yaml)"
    )
    args = parser.parse_args()

    from auspex_ingest.dag_factory import load_sources_config
    config = load_sources_config(_ROOT / "config" / "sources.yaml")

    cursor = datetime.now(UTC) - timedelta(days=args.days)
    requested = set(args.sources) if args.sources else None

    for entry in config.sources:
        source_type = entry.source_type
        if source_type == "mock":
            continue
        if requested and source_type not in requested:
            continue

        print(f"\n{'=' * 60}", flush=True)
        print(
            f"Source: {source_type}  |  cursor: {cursor.date()}  |  window: {args.days}d",
            flush=True,
        )
        print(f"{'=' * 60}", flush=True)

        try:
            pipeline = _build_pipeline(source_type, entry)
            result = pipeline.run(source_type, cursor)
            print(
                f"  fetched={result.fetched}  published={result.published}"
                f"  prefiltered_out={result.prefiltered_out}"
                f"  not_signal={result.not_signal}  failed={result.failed}",
                flush=True,
            )
        except RuntimeError as exc:
            print(f"  SKIP: {exc}", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"  ERROR in {source_type}: {exc}", file=sys.stderr, flush=True)
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
"""Builds an `IngestionPipeline` per `source_type`, shared by the scraper API and
`scripts/run_pipeline.py`. Connectors come from the connector registry; the publish threshold and
rate limits come from each `sources.yaml` entry."""
from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

from .connectors import RateLimitedClient
from .connectors.registry import ConnectorRegistry, default_registry
from .normalizer import IdentityNormalizer
from .pipeline import IngestionPipeline
from .prefilter import Prefilter
from .sources import SourceEntry

PipelineFactory = Callable[[str], IngestionPipeline]


def make_pipeline_factory(
    *,
    sources_by_type: Mapping[str, SourceEntry],
    connectors: ConnectorRegistry,
    http_client: RateLimitedClient,
    archive: Any,
    extractor: Callable[[], Any],
    producer: Any,
    metrics_registry: Any,
    env: Mapping[str, str] | None = None,
    now: Callable[[], datetime] | None = None,
) -> PipelineFactory:
    """`extractor` is called on the first pipeline built and its result reused, so a missing
    model gate record fails that request instead of the process start."""
    extractor_cache: list[Any] = []

    def _extractor() -> Any:
        if not extractor_cache:
            extractor_cache.append(extractor())
        return extractor_cache[0]

    def factory(source_type: str) -> IngestionPipeline:
        entry = sources_by_type[source_type]
        connector = connectors.build(entry, http_client, env=env)
        built_extractor = _extractor()
        return IngestionPipeline(
            connector=connector,
            archive=archive,
            extractor=built_extractor,
            producer=producer,
            prefilter=Prefilter.from_vocab(set(entry.prefilter_vocabulary)),
            normalizer=IdentityNormalizer(),
            now=now or (lambda: datetime.now(UTC)),
            min_confidence_to_publish=entry.min_confidence_to_publish,
            metrics_registry=metrics_registry,
            extraction_identity=f"{built_extractor.model_id}|{built_extractor.prompt_version}",
            max_extractions_per_run=entry.max_documents_per_run,
        )

    return factory


def make_env_pipeline_factory(
    sources_by_type: Mapping[str, SourceEntry],
    metrics_registry: Any,
) -> PipelineFactory:
    """The production factory: MinIO, Kafka and the extraction backend configured from the
    environment."""
    from confluent_kafka import Producer as ConfluentProducer
    from minio import Minio

    from .extraction_backend import build_extractor_from_env
    from .messaging import KafkaProducerClient
    from .storage.minio_client import MinioArchive

    connectors = default_registry()
    http_client = RateLimitedClient(connectors.host_limits(sources_by_type.values()))

    minio_client = Minio(
        os.environ["MINIO_ENDPOINT"],
        access_key=os.environ["MINIO_ACCESS_KEY"],
        secret_key=os.environ["MINIO_SECRET_KEY"],
        secure=False,
    )
    archive = MinioArchive(client=minio_client, bucket=os.environ["MINIO_BUCKET"])

    kafka_producer = KafkaProducerClient(
        ConfluentProducer({"bootstrap.servers": os.environ["KAFKA_BOOTSTRAP_SERVERS"]}),
        raw_topic=os.environ.get("KAFKA_RAW_TOPIC", "auspex.raw.ingested"),
        signals_topic=os.environ.get("KAFKA_SIGNALS_TOPIC", "auspex.signals.extracted"),
    )

    return make_pipeline_factory(
        sources_by_type=sources_by_type,
        connectors=connectors,
        http_client=http_client,
        archive=archive,
        extractor=build_extractor_from_env,
        producer=kafka_producer,
        metrics_registry=metrics_registry,
    )

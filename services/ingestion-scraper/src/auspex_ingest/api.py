import os
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from flask import Flask, Response, jsonify, request
from prometheus_client import REGISTRY, CollectorRegistry, generate_latest

from .logging_config import configure_logging
from .pipeline import RunResult
from .reextract import ReextractionRunner
from .sources import SourceEntry, SourcesConfig


def create_app(
    *,
    pipeline_for_source: Callable[[str], Any] | None = None,
    reextract_runner: ReextractionRunner | None = None,
    sources_config: SourcesConfig | None = None,
    now: Callable[[], datetime] | None = None,
    metrics_registry: CollectorRegistry | None = None,
) -> Flask:
    configure_logging()
    app = Flask(__name__)
    _registry = metrics_registry if metrics_registry is not None else REGISTRY

    _sources = sources_config or _load_sources_config()
    _sources_by_type: dict[str, SourceEntry] = {e.source_type: e for e in _sources.sources}
    _pipeline_for = pipeline_for_source or _make_env_pipeline_factory(_sources_by_type, _registry)
    _runner: ReextractionRunner | None = reextract_runner
    _now = now or (lambda: datetime.now(UTC))

    @app.route("/health")
    def health() -> Any:
        return jsonify({"status": "ok", "service": "ingestion-scraper"})

    @app.route("/sources")
    def sources() -> Any:
        return jsonify({"sources": list(_sources_by_type)})

    @app.route("/ingest/<source_type>", methods=["POST"])
    def ingest(source_type: str) -> Any:
        if source_type not in _sources_by_type:
            return jsonify({"error": f"Unknown source type: {source_type!r}"}), 404

        entry = _sources_by_type[source_type]
        body = request.get_json() or {}
        cursor_str = body.get("cursor")
        if cursor_str:
            cursor = datetime.fromisoformat(cursor_str)
        else:
            cursor = _now() - timedelta(days=entry.initial_lookback)

        try:
            pipeline = _pipeline_for(source_type)
            result: RunResult = pipeline.run(source_type, cursor)
        except Exception as exc:  # noqa: BLE001
            return jsonify({"error": str(exc)}), 500

        return jsonify({
            "fetched": result.fetched,
            "prefiltered_out": result.prefiltered_out,
            "published": result.published,
            "not_signal": result.not_signal,
            "below_threshold": result.below_threshold,
            "failed": result.failed,
            "max_published_date_processed": (
                result.max_published_date_processed.isoformat()
                if result.max_published_date_processed
                else None
            ),
        })

    @app.route("/reextract", methods=["POST"])
    def reextract() -> Any:
        nonlocal _runner
        if _runner is None:
            _runner = _make_env_reextract_runner()
        body = request.get_json() or {}
        result = _runner.run(
            source_type=body.get("source_type"),
            since=body.get("since"),
            until=body.get("until"),
            prompt_version=body.get("prompt_version"),
            model=body.get("model"),
            schema_version=body.get("schema_version"),
            prefilter_version=body.get("prefilter_version"),
            skip_prefilter=bool(body.get("skip_prefilter", False)),
            dry_run=bool(body.get("dry_run", False)),
        )
        return jsonify(result)

    @app.route("/metrics")
    def metrics() -> Response:
        return Response(generate_latest(_registry), mimetype="text/plain; version=0.0.4")

    return app


def _load_sources_config() -> SourcesConfig:

    path = Path(os.environ.get("AUSPEX_SOURCES_YAML", "config/sources.yaml"))
    from .sources import load_sources_config
    return load_sources_config(path)


def _make_env_reextract_runner() -> ReextractionRunner:
    import os

    from confluent_kafka import Producer as ConfluentProducer
    from minio import Minio

    from .extraction_backend import build_extractor_from_env
    from .messaging import KafkaProducerClient
    from .models import EVENT_SCHEMA_VERSION
    from .storage.minio_client import MinioArchive

    minio_client = Minio(
        os.environ["MINIO_ENDPOINT"],
        access_key=os.environ["MINIO_ACCESS_KEY"],
        secret_key=os.environ["MINIO_SECRET_KEY"],
        secure=False,
    )
    archive = MinioArchive(client=minio_client, bucket=os.environ["MINIO_BUCKET"])

    extractor = build_extractor_from_env(
        schema_version=os.environ.get("SCHEMA_VERSION", EVENT_SCHEMA_VERSION),
    )

    producer = KafkaProducerClient(
        ConfluentProducer({"bootstrap.servers": os.environ["KAFKA_BOOTSTRAP_SERVERS"]}),
        raw_topic=os.environ.get("KAFKA_RAW_TOPIC", "auspex.raw.ingested"),
        signals_topic=os.environ.get("KAFKA_SIGNALS_TOPIC", "auspex.signals.extracted"),
    )

    return ReextractionRunner(archive=archive, extractor=extractor, producer=producer)


def _make_env_pipeline_factory(
    sources_by_type: dict[str, SourceEntry],
    metrics_registry: CollectorRegistry,
) -> Callable[[str], Any]:
    import os
    from datetime import UTC, datetime

    from confluent_kafka import Producer as ConfluentProducer
    from minio import Minio

    from .connectors import RateLimitedClient
    from .connectors.biorxiv import BiorxivConnector
    from .connectors.clinicaltrials import ClinicalTrialConnector
    from .extraction_backend import BackendLLMExtractor, build_extractor_from_env
    from .messaging import KafkaProducerClient
    from .normalizer import IdentityNormalizer
    from .pipeline import IngestionPipeline
    from .prefilter import Prefilter
    from .storage.minio_client import MinioArchive

    rate_limits: dict[str, float] = {
        "api.biorxiv.org": 3.0,
        "clinicaltrials.gov": 5.0,
        "eutils.ncbi.nlm.nih.gov": 3.0,
        "sec.gov": 4.0,
        "ops.epo.org": 2.0,
    }
    http_client = RateLimitedClient(rate_limits)

    minio_client = Minio(
        os.environ["MINIO_ENDPOINT"],
        access_key=os.environ["MINIO_ACCESS_KEY"],
        secret_key=os.environ["MINIO_SECRET_KEY"],
        secure=False,
    )
    archive = MinioArchive(client=minio_client, bucket=os.environ["MINIO_BUCKET"])

    # Built on first use so a missing gate record surfaces as a 500 naming the model,
    # not as a scraper container that cannot start.
    extractor_cache: list[BackendLLMExtractor] = []

    def _extractor() -> BackendLLMExtractor:
        if not extractor_cache:
            extractor_cache.append(build_extractor_from_env())
        return extractor_cache[0]

    kafka_producer = KafkaProducerClient(
        ConfluentProducer({"bootstrap.servers": os.environ["KAFKA_BOOTSTRAP_SERVERS"]}),
        raw_topic=os.environ.get("KAFKA_RAW_TOPIC", "auspex.raw.ingested"),
        signals_topic=os.environ.get("KAFKA_SIGNALS_TOPIC", "auspex.signals.extracted"),
    )

    def _build_connector(source_type: str, entry: SourceEntry) -> Any:
        if source_type == "biorxiv":
            return BiorxivConnector(client=http_client)
        if source_type == "clinicaltrials":
            return ClinicalTrialConnector(client=http_client)
        raise ValueError(f"No connector registered for source_type={source_type!r}")

    def factory(source_type: str) -> IngestionPipeline:
        entry = sources_by_type[source_type]
        connector = _build_connector(source_type, entry)
        extractor = _extractor()
        return IngestionPipeline(
            connector=connector,
            archive=archive,
            extractor=extractor,
            producer=kafka_producer,
            prefilter=Prefilter.from_vocab(set(entry.prefilter_vocabulary)),
            normalizer=IdentityNormalizer(),
            now=lambda: datetime.now(UTC),
            min_confidence_to_publish=0.5,
            metrics_registry=metrics_registry,
            extraction_identity=f"{extractor.model_id}|{extractor.prompt_version}",
        )

    return factory

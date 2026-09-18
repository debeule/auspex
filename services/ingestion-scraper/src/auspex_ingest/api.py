import os
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from flask import Flask, Response, jsonify, request
from prometheus_client import REGISTRY, CollectorRegistry, generate_latest

from .models import RunResult
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
    app = Flask(__name__)
    _registry = metrics_registry if metrics_registry is not None else REGISTRY

    _sources = sources_config or _load_sources_config()
    _sources_by_type: dict[str, SourceEntry] = {e.source_type: e for e in _sources.sources}
    _pipeline_for = pipeline_for_source or _make_env_pipeline_factory(_sources_by_type)
    _runner = reextract_runner or ReextractionRunner()
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
    import yaml

    path = Path(os.environ.get("AUSPEX_SOURCES_YAML", "config/sources.yaml"))
    from .dag_factory import load_sources_config
    return load_sources_config(path)


def _make_env_pipeline_factory(
    sources_by_type: dict[str, SourceEntry],
) -> Callable[[str], Any]:
    import os
    import instructor
    import openai
    from confluent_kafka import Producer as ConfluentProducer
    from datetime import UTC, datetime
    from minio import Minio

    from .connectors.biorxiv import BiorxivConnector
    from .connectors.clinicaltrials import ClinicalTrialConnector
    from .extractor import LLMExtractor
    from .kafka_producer import KafkaProducerClient
    from .normalizer import IdentityNormalizer
    from .pipeline import IngestionPipeline
    from .prefilter import Prefilter
    from .rate_limited_client import RateLimitedClient
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

    api_key = os.environ.get("OPENAI_API_KEY") or ""
    llm_client = instructor.from_openai(openai.OpenAI(api_key=api_key))
    extractor = LLMExtractor(
        client=llm_client,
        model=os.environ.get("OPEN_AI_EXTRACTION_MODEL", "gpt-4o-mini"),
        schema_version="1.0",
        prompt_version="v1",
    )

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

    return factory

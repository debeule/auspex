import os
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from flask import Flask, Response, jsonify, request
from prometheus_client import REGISTRY, CollectorRegistry, generate_latest

from .logging_config import configure_logging
from .pipeline import RunResult
from .pipeline_factory import make_env_pipeline_factory
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
    _pipeline_for = pipeline_for_source or make_env_pipeline_factory(_sources_by_type, _registry)
    _runner: ReextractionRunner | None = reextract_runner
    _now = now or (lambda: datetime.now(UTC))
    # One run per source at a time: a second run would fetch and extract the same documents while
    # the first still holds the model server. Runs of different sources do not wait on each other.
    _run_locks = {source_type: threading.Lock() for source_type in _sources_by_type}

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

        lock = _run_locks[source_type]
        if not lock.acquire(blocking=False):
            return jsonify({"error": f"A {source_type!r} run is already in progress"}), 409
        try:
            pipeline = _pipeline_for(source_type)
            result: RunResult = pipeline.run(source_type, cursor)
        except Exception as exc:  # noqa: BLE001
            return jsonify({"error": str(exc)}), 500
        finally:
            lock.release()

        return jsonify({
            "fetched": result.fetched,
            "prefiltered_out": result.prefiltered_out,
            "published": result.published,
            "not_signal": result.not_signal,
            "below_threshold": result.below_threshold,
            "failed": result.failed,
            "max_published_date_processed": _iso(result.max_published_date_processed),
            "next_cursor": _iso(result.next_cursor),
            "capped": result.capped,
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


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


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


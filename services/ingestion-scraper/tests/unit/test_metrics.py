from datetime import UTC, datetime
from unittest.mock import MagicMock

from prometheus_client import CollectorRegistry

from auspex_ingest.pipeline import IngestionPipeline
from auspex_ingest.sources import SourceEntry, SourcesConfig


def _make_registry():
    return CollectorRegistry()


def _make_pipeline(connector, registry, *, archive=None, extractor=None, producer=None):
    archive = archive or MagicMock()
    extractor = extractor or MagicMock()
    producer = producer or MagicMock()
    prefilter = MagicMock()
    prefilter.passes.return_value = True
    prefilter.version = "v1"
    normalizer = MagicMock()
    normalizer.normalize_gene.side_effect = lambda x: x
    normalizer.normalize_company.side_effect = lambda x: x
    return IngestionPipeline(
        connector=connector,
        archive=archive,
        extractor=extractor,
        producer=producer,
        prefilter=prefilter,
        normalizer=normalizer,
        now=lambda: datetime.now(UTC),
        metrics_registry=registry,
    )


def _make_sources(*source_types: str) -> SourcesConfig:
    return SourcesConfig(sources=[
        SourceEntry(
            source_type=st,
            schedule="@daily",
            rate_limit_rps=3.0,
            initial_lookback=7,
            max_documents_per_run=100,
            prefilter_vocabulary=["gene therapy"],
            source_config={},
        )
        for st in source_types
    ])


def _make_doc(external_id: str = "ext-1") -> MagicMock:
    doc = MagicMock()
    doc.external_id = external_id
    doc.source_type = "biorxiv"
    doc.published_date = datetime.now(UTC)
    doc.canonical_id = None
    doc.schema_version = "1.0"
    return doc


def test_metrics_route_returns_prometheus_format():
    from auspex_ingest.api import create_app
    registry = _make_registry()
    app = create_app(
        pipeline_for_source=lambda _st: MagicMock(),
        sources_config=_make_sources("biorxiv"),
        metrics_registry=registry,
    )
    client = app.test_client()
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "text/plain" in resp.content_type


def test_pipeline_run_increments_published_counter():
    registry = _make_registry()

    doc = _make_doc()
    connector = MagicMock()
    connector.fetch_since.return_value = [doc]
    connector.provides_canonical_id = False

    event = MagicMock()
    event.confidence_score = 0.9
    event.gene_targets = []
    event.companies_mentioned = []
    extractor = MagicMock()
    extractor.extract.return_value = event

    archive = MagicMock()
    archive.put.return_value = ("key", True)

    pipeline = _make_pipeline(connector, registry, archive=archive, extractor=extractor)
    pipeline.run("biorxiv", datetime.now(UTC))

    count = registry.get_sample_value(
        "auspex_pipeline_signals_published_total",
        {"source_type": "biorxiv"},
    )
    assert count == 1.0


def test_pipeline_run_increments_fetched_counter():
    registry = _make_registry()

    connector = MagicMock()
    connector.fetch_since.return_value = [_make_doc("a"), _make_doc("b")]
    connector.provides_canonical_id = False

    archive = MagicMock()
    archive.put.return_value = ("key", False)

    pipeline = _make_pipeline(connector, registry, archive=archive)
    pipeline.run("biorxiv", datetime.now(UTC))

    count = registry.get_sample_value(
        "auspex_pipeline_documents_fetched_total",
        {"source_type": "biorxiv"},
    )
    assert count == 2.0


def test_llm_error_increments_error_label():
    registry = _make_registry()

    doc = _make_doc()
    connector = MagicMock()
    connector.fetch_since.return_value = [doc]
    connector.provides_canonical_id = False

    archive = MagicMock()
    archive.put.return_value = ("key", True)

    extractor = MagicMock()
    extractor.extract.side_effect = RuntimeError("LLM timeout")

    pipeline = _make_pipeline(connector, registry, archive=archive, extractor=extractor)
    pipeline.run("biorxiv", datetime.now(UTC))

    count = registry.get_sample_value(
        "auspex_llm_extraction_calls_total",
        {"source_type": "biorxiv", "result": "error"},
    )
    assert count == 1.0


def test_run_duration_histogram_records_observation():
    registry = _make_registry()
    connector = MagicMock()
    connector.fetch_since.return_value = []
    pipeline = _make_pipeline(connector, registry)
    pipeline.run("biorxiv", datetime.now(UTC))

    count = registry.get_sample_value(
        "auspex_pipeline_run_duration_seconds_count",
        {"source_type": "biorxiv"},
    )
    assert count == 1.0

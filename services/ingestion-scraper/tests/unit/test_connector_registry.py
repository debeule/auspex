import ast
import hashlib
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from prometheus_client import CollectorRegistry

from auspex_ingest.api import create_app
from auspex_ingest.connectors import RateLimitedClient
from auspex_ingest.connectors.base import SourceConnector
from auspex_ingest.connectors.registry import (
    BuildContext,
    ConnectorRegistration,
    ConnectorRegistry,
    UnknownSourceTypeError,
    default_registry,
)
from auspex_ingest.identity import compute_event_id, compute_extraction_id
from auspex_ingest.models import RawDocument, ResearchSignalEvent
from auspex_ingest.pipeline_factory import make_pipeline_factory
from auspex_ingest.sources import SourceEntry, load_sources_config

_ROOT = Path(__file__).resolve().parents[2]
_SOURCES = load_sources_config(_ROOT / "config" / "sources.yaml")
_SOURCE_TYPES = [e.source_type for e in _SOURCES.sources]
_T0 = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)

# Every value a connector builder may read from the environment, so no case is skipped for a
# missing credential.
_FULL_ENV = {
    "SEC_USER_AGENT": "auspex-test test@example.com",
    "NCBI_API_KEY": "test-key",
    "EPO_OPS_KEY": "test-key",
    "EPO_OPS_SECRET": "test-secret",
}


def _entry(source_type: str = "biorxiv", **overrides: object) -> SourceEntry:
    fields: dict[str, object] = {
        "source_type": source_type,
        "schedule": "@daily",
        "rate_limit_rps": 3.0,
        "initial_lookback": 7,
        "max_documents_per_run": 100,
        "prefilter_vocabulary": ["BCL11A"],
        "source_config": {},
    }
    fields.update(overrides)
    return SourceEntry.model_validate(fields)


def _raw(source_type: str) -> RawDocument:
    content = "CRISPR base editing of BCL11A"
    return RawDocument(
        schema_version="1.0",
        external_id=f"{source_type}-001",
        canonical_id=None,
        source_type=source_type,
        source_url="https://example.com/doc/1",
        published_date=_T0,
        raw_content=content,
        content_sha256=hashlib.sha256(content.encode()).hexdigest(),
        retrieved_at=_T0,
    )


def _event(source_type: str, confidence_score: float) -> ResearchSignalEvent:
    event_id = compute_event_id(None, source_type, f"{source_type}-001")
    return ResearchSignalEvent(
        schema_version="1.0",
        event_id=event_id,
        extraction_id=compute_extraction_id(event_id, "1.0", "v1", "v1", "fake"),
        external_id=f"{source_type}-001",
        canonical_id=None,
        raw_object_key=f"raw/{source_type}/{source_type}-001/20240615T120000Z-abcdef12.json",
        source_type=source_type,
        source_url="https://example.com/doc/1",
        published_date=_T0,
        published_date_field="date",
        ingested_at=_T0,
        title="BCL11A editing",
        raw_text_snippet="BCL11A base editing",
        gene_targets=["BCL11A"],
        mechanisms=["base editing"],
        companies_mentioned=[],
        summary="BCL11A editing",
        directionality="positive",
        confidence_score=confidence_score,
        prompt_version="v1",
        prefilter_version="v1",
        extraction_model="fake",
    )


class _FakeConnector(SourceConnector):
    def __init__(self, source_type: str) -> None:
        self.source_type = source_type
        self.cursors: list[datetime] = []

    def fetch_since(self, cursor: datetime) -> Iterator[RawDocument]:
        self.cursors.append(cursor)
        yield _raw(self.source_type)


class _FakeArchive:
    def put(self, doc: RawDocument) -> tuple[str, bool]:
        return f"raw/{doc.source_type}/{doc.external_id}/key.json", True

    def get_canonical_marker(self, canonical_id: str) -> dict | None:
        return None

    def put_canonical_marker(self, canonical_id: str, data: dict) -> None:
        pass

    def has_processed_marker(self, doc: RawDocument, identity: str) -> bool:
        return False

    def put_processed_marker(self, doc: RawDocument, identity: str) -> None:
        pass


class _FakeExtractor:
    model_id = "fake"
    prompt_version = "v1"

    def __init__(self, confidence_score: float = 0.9) -> None:
        self._confidence = confidence_score

    def extract(
        self, doc: RawDocument, prefilter_version: str, raw_object_key: str
    ) -> ResearchSignalEvent:
        return _event(doc.source_type, self._confidence)


class _FakeProducer:
    def __init__(self) -> None:
        self.signals: list[ResearchSignalEvent] = []

    def publish_raw(self, doc: RawDocument, raw_object_key: str, schema_version: str) -> None:
        pass

    def publish_signal(self, event: ResearchSignalEvent) -> None:
        self.signals.append(event)

    def flush(self) -> None:
        pass


def _faked_registry(built: dict[str, _FakeConnector]) -> ConnectorRegistry:
    """The default registry's source types and hosts, each building a recording fake."""
    registry = ConnectorRegistry()
    for source_type in default_registry().source_types():
        real = default_registry().registration(source_type)

        def build(ctx: BuildContext) -> SourceConnector:
            connector = _FakeConnector(ctx.entry.source_type)
            built[ctx.entry.source_type] = connector
            return connector

        registry.add(ConnectorRegistration(
            source_type=source_type,
            build=build,
            rate_limit_host=real.rate_limit_host,
            live=real.live,
        ))
    return registry


@pytest.mark.parametrize("source_type", _SOURCE_TYPES)
def test_every_source_in_sources_yaml_builds_a_connector_through_the_registry(source_type):
    entry = next(e for e in _SOURCES.sources if e.source_type == source_type)
    client = RateLimitedClient({})

    connector = default_registry().build(entry, client, env=_FULL_ENV)

    assert isinstance(connector, SourceConnector)


def test_unknown_source_type_raises_a_named_error_listing_registered_types():
    with pytest.raises(UnknownSourceTypeError) as exc_info:
        default_registry().build(_entry("no_such_source"), RateLimitedClient({}), env=_FULL_ENV)

    message = str(exc_info.value)
    assert "no_such_source" in message
    for source_type in _SOURCE_TYPES:
        assert source_type in message


@pytest.mark.parametrize("source_type", _SOURCE_TYPES)
def test_api_ingest_reaches_each_registered_connector(source_type):
    built: dict[str, _FakeConnector] = {}
    sources_by_type = {e.source_type: e for e in _SOURCES.sources}
    metrics = CollectorRegistry()
    factory = make_pipeline_factory(
        sources_by_type=sources_by_type,
        connectors=_faked_registry(built),
        http_client=RateLimitedClient({}),
        archive=_FakeArchive(),
        extractor=_FakeExtractor,
        producer=_FakeProducer(),
        metrics_registry=metrics,
        env=_FULL_ENV,
    )
    client = create_app(
        pipeline_for_source=factory, sources_config=_SOURCES, metrics_registry=metrics,
    ).test_client()

    resp = client.post(f"/ingest/{source_type}", json={"cursor": "2024-06-01T00:00:00+00:00"})

    assert resp.status_code == 200, resp.get_json()
    assert set(built) == {source_type}
    assert built[source_type].cursors == [datetime(2024, 6, 1, tzinfo=UTC)]
    assert (resp.get_json()["fetched"], resp.get_json()["failed"]) == (1, 0)


def test_publish_threshold_and_rate_limit_come_from_the_source_entry():
    strict = _entry("biorxiv", min_confidence_to_publish=0.8, rate_limit_rps=1.5)
    lenient = _entry("clinicaltrials", min_confidence_to_publish=0.6)
    built: dict[str, _FakeConnector] = {}
    registry = _faked_registry(built)
    producer = _FakeProducer()
    factory = make_pipeline_factory(
        sources_by_type={"biorxiv": strict, "clinicaltrials": lenient},
        connectors=registry,
        http_client=RateLimitedClient({}),
        archive=_FakeArchive(),
        extractor=lambda: _FakeExtractor(confidence_score=0.7),
        producer=producer,
        metrics_registry=None,
        env=_FULL_ENV,
    )

    strict_result = factory("biorxiv").run("biorxiv", _T0)
    lenient_result = factory("clinicaltrials").run("clinicaltrials", _T0)

    assert (strict_result.published, strict_result.below_threshold) == (0, 1)
    assert (lenient_result.published, lenient_result.below_threshold) == (1, 0)
    assert _entry("pubmed").min_confidence_to_publish == 0.0

    host = default_registry().registration("biorxiv").rate_limit_host
    assert host is not None
    assert registry.host_limits([strict, lenient])[host] == 1.5


def _source_type_literal_comparisons(tree: ast.AST) -> list[int]:
    def names_source_type(node: ast.expr) -> bool:
        return (isinstance(node, ast.Name) and node.id == "source_type") or (
            isinstance(node, ast.Attribute) and node.attr == "source_type"
        )

    def is_str_literal(node: ast.expr) -> bool:
        if isinstance(node, ast.Constant):
            return isinstance(node.value, str)
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            return any(is_str_literal(e) for e in node.elts)
        return False

    lines = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            operands = [node.left, *node.comparators]
            if any(names_source_type(o) for o in operands) and any(
                is_str_literal(o) for o in operands
            ):
                lines.append(node.lineno)
        elif isinstance(node, ast.Match) and names_source_type(node.subject):
            lines.append(node.lineno)
    return lines


def test_no_source_type_equality_branch_in_shared_modules():
    package = _ROOT / "src" / "auspex_ingest"
    shared = [
        p for p in [*package.rglob("*.py"), *(_ROOT / "scripts").glob("*.py")]
        if "connectors" not in p.relative_to(_ROOT).parts
    ]
    assert len(shared) > 10

    offenders = {
        str(p.relative_to(_ROOT)): lines
        for p in shared
        if (lines := _source_type_literal_comparisons(ast.parse(p.read_text())))
    }

    assert offenders == {}

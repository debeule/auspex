import json
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
import structlog.testing

from auspex_ingest.logging_config import SensitiveFieldDrop
from auspex_ingest.pipeline import IngestionPipeline


def _make_pipeline(connector, *, archive=None, extractor=None, producer=None):
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
    )


def _make_doc(external_id: str = "ext-1", source_type: str = "biorxiv") -> MagicMock:
    doc = MagicMock()
    doc.external_id = external_id
    doc.source_type = source_type
    doc.published_date = datetime.now(UTC)
    doc.canonical_id = None
    doc.schema_version = "1.0"
    return doc


def test_pipeline_run_summary_log_contains_all_counters():
    connector = MagicMock()
    connector.fetch_since.return_value = []
    pipeline = _make_pipeline(connector)

    with structlog.testing.capture_logs() as cap:
        pipeline.run("biorxiv", datetime.now(UTC))

    summary = next((e for e in cap if "fetched" in e), None)
    assert summary is not None, "No run-summary log event emitted"
    for field in ("fetched", "prefiltered_out", "published", "not_signal", "below_threshold", "failed"):
        assert field in summary, f"Counter field missing from summary: {field}"


def test_pipeline_run_log_contains_source_type_and_run_id():
    connector = MagicMock()
    connector.fetch_since.return_value = []
    pipeline = _make_pipeline(connector)

    with structlog.testing.capture_logs() as cap:
        pipeline.run("clinicaltrials", datetime.now(UTC))

    summary = next((e for e in cap if "fetched" in e), None)
    assert summary is not None
    assert summary.get("auspex.source_type") == "clinicaltrials"
    assert "auspex.run_id" in summary


def test_connector_error_log_includes_source_type_and_external_id():
    doc = _make_doc(external_id="ext-fail")
    connector = MagicMock()
    connector.fetch_since.return_value = [doc]
    archive = MagicMock()
    archive.put.side_effect = RuntimeError("disk full")

    pipeline = _make_pipeline(connector, archive=archive)

    with structlog.testing.capture_logs() as cap:
        pipeline.run("biorxiv", datetime.now(UTC))

    error_events = [e for e in cap if e.get("log_level") == "error"]
    assert error_events, "No error-level log event emitted"
    event = error_events[0]
    assert "auspex.source_type" in event
    assert "auspex.external_id" in event


def test_sensitive_field_drop_removes_raw_content():
    processor = SensitiveFieldDrop()
    result = processor(None, "info", {"event": "fetch", "raw_content": "HUGE TEXT"})
    assert "raw_content" not in result
    assert result["event"] == "fetch"


def test_sensitive_field_drop_removes_api_key_variants():
    processor = SensitiveFieldDrop()
    event_dict = {
        "event": "ok",
        "api_key": "k1",
        "access_key": "k2",
        "secret_key": "k3",
        "password": "p1",
        "secret": "s1",
        "my_password_field": "p2",
        "safe_field": "keep",
    }
    result = processor(None, "info", event_dict)
    for dropped in ("api_key", "access_key", "secret_key", "password", "secret", "my_password_field"):
        assert dropped not in result, f"Expected {dropped!r} to be dropped"
    assert result["safe_field"] == "keep"


def test_all_captured_log_events_are_valid_json():
    connector = MagicMock()
    connector.fetch_since.return_value = []
    pipeline = _make_pipeline(connector)

    with structlog.testing.capture_logs() as cap:
        pipeline.run("biorxiv", datetime.now(UTC))

    for event in cap:
        try:
            json.dumps(event)
        except TypeError as exc:
            pytest.fail(f"Log event not JSON-serializable: {exc!r}\nEvent: {event!r}")

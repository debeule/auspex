from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from auspex_ingest.api import create_app
from auspex_ingest.models import RunResult
from auspex_ingest.sources import SourceEntry, SourcesConfig


def _make_sources(*source_types: str) -> SourcesConfig:
    entries = [
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
    ]
    return SourcesConfig(sources=entries)


def _make_result(**overrides: int) -> RunResult:
    defaults = dict(fetched=5, prefiltered_out=2, published=2, not_signal=1, below_threshold=0, failed=0)
    defaults.update(overrides)
    return RunResult(**defaults)


@pytest.fixture()
def sources():
    return _make_sources("biorxiv", "clinicaltrials")


@pytest.fixture()
def mock_pipeline():
    p = MagicMock()
    p.run.return_value = _make_result()
    return p


@pytest.fixture()
def app(sources, mock_pipeline):
    return create_app(
        pipeline_for_source=lambda _st: mock_pipeline,
        sources_config=sources,
    )


@pytest.fixture()
def client(app):
    return app.test_client()


def test_health_returns_200_with_service_name(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
    assert data["service"] == "ingestion-scraper"


def test_sources_returns_all_configured_source_types(client):
    resp = client.get("/sources")
    assert resp.status_code == 200
    data = resp.get_json()
    assert set(data["sources"]) == {"biorxiv", "clinicaltrials"}


def test_ingest_calls_pipeline_run_with_cursor_from_request_body(client, mock_pipeline):
    cursor = "2023-01-10T12:00:00+00:00"
    resp = client.post("/ingest/biorxiv", json={"cursor": cursor})
    assert resp.status_code == 200
    mock_pipeline.run.assert_called_once()
    call_args = mock_pipeline.run.call_args
    assert call_args.args[0] == "biorxiv"
    called_cursor = call_args.args[1]
    assert called_cursor == datetime.fromisoformat(cursor)


def test_ingest_returns_all_run_result_fields(client, mock_pipeline):
    mock_pipeline.run.return_value = _make_result(fetched=10, published=3, failed=1)
    resp = client.post("/ingest/biorxiv", json={"cursor": "2023-01-10T12:00:00+00:00"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["fetched"] == 10
    assert data["published"] == 3
    assert data["failed"] == 1
    for field in ("fetched", "prefiltered_out", "published", "not_signal", "below_threshold", "failed"):
        assert field in data


def test_ingest_absent_cursor_defaults_to_initial_lookback(sources, mock_pipeline):
    fixed_now = datetime(2023, 6, 1, 12, 0, 0, tzinfo=UTC)
    app = create_app(
        pipeline_for_source=lambda _st: mock_pipeline,
        sources_config=sources,
        now=lambda: fixed_now,
    )
    client = app.test_client()
    resp = client.post("/ingest/biorxiv", json={})
    assert resp.status_code == 200
    call_args = mock_pipeline.run.call_args
    expected_cursor = fixed_now - timedelta(days=7)
    assert call_args.args[1] == expected_cursor


def test_ingest_unknown_source_type_returns_404(client):
    resp = client.post("/ingest/nonexistent", json={"cursor": "2023-01-01T00:00:00+00:00"})
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_ingest_pipeline_exception_returns_500_with_error_message(client, mock_pipeline):
    mock_pipeline.run.side_effect = RuntimeError("connector down")
    resp = client.post("/ingest/biorxiv", json={"cursor": "2023-01-10T12:00:00+00:00"})
    assert resp.status_code == 500
    data = resp.get_json()
    assert "error" in data


def test_reextract_dry_run_returns_estimated_count_without_publishing(sources):
    runner = MagicMock()
    runner.run.return_value = {"estimated_count": 42, "published": 0}
    app = create_app(
        pipeline_for_source=lambda _st: MagicMock(),
        reextract_runner=runner,
        sources_config=sources,
    )
    client = app.test_client()
    resp = client.post("/reextract", json={"source_type": "biorxiv", "dry_run": True})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["estimated_count"] == 42
    assert data["published"] == 0


def test_reextract_delegates_to_reextraction_runner_with_correct_params(sources):
    runner = MagicMock()
    runner.run.return_value = {"published": 5}
    app = create_app(
        pipeline_for_source=lambda _st: MagicMock(),
        reextract_runner=runner,
        sources_config=sources,
    )
    client = app.test_client()
    body = {
        "source_type": "biorxiv",
        "since": "2023-01-01T00:00:00+00:00",
        "until": "2023-02-01T00:00:00+00:00",
        "prompt_version": "v2",
        "model": "gpt-4o",
        "dry_run": False,
    }
    resp = client.post("/reextract", json=body)
    assert resp.status_code == 200
    runner.run.assert_called_once()
    kwargs = runner.run.call_args.kwargs
    assert kwargs["source_type"] == "biorxiv"
    assert kwargs["prompt_version"] == "v2"
    assert kwargs["dry_run"] is False

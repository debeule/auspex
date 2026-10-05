from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from auspex_ingest.connectors import RateLimitedClient, RateLimitExceeded
from auspex_ingest.dag_factory import DagConfig, build_dags, load_sources_config, run_with_cursor
from auspex_ingest.pipeline import RunResult
from auspex_ingest.sources import SourceEntry, SourcesConfig

_T0 = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)


def _make_entry(**overrides: object) -> SourceEntry:
    defaults: dict = {
        "source_type": "mock",
        "schedule": "@daily",
        "rate_limit_rps": 1.0,
        "initial_lookback": 7,
        "max_documents_per_run": 100,
        "prefilter_vocabulary": ["BCL11A"],
        "source_config": {},
    }
    defaults.update(overrides)
    return SourceEntry(**defaults)


def _make_config(*source_types: str) -> SourcesConfig:
    return SourcesConfig(sources=[_make_entry(source_type=st) for st in source_types])


def _mock_pipeline(
    result: RunResult | None = None,
    raises: Exception | None = None,
) -> MagicMock:
    pipeline = MagicMock()
    if raises is not None:
        pipeline.run.side_effect = raises
    else:
        pipeline.run.return_value = result or RunResult(
            fetched=1,
            published=1,
            failed=0,
            max_published_date_processed=_T0,
        )
    return pipeline



def test_dag_factory_generates_one_dag_per_registry_entry():
    config = _make_config("mock", "mock2")
    pipeline = _mock_pipeline()
    dags = build_dags(
        config,
        lambda entry: pipeline,
        get_var=lambda k, d: None,
        set_var=lambda k, v: None,
        now=lambda: _T0,
    )
    assert len(dags) == 2
    assert {d.dag_id for d in dags} == {"auspex_mock", "auspex_mock2"}


def test_generated_dags_have_no_import_errors():
    config = _make_config("mock")
    pipeline = _mock_pipeline()
    dags = build_dags(
        config,
        lambda entry: pipeline,
        get_var=lambda k, d: None,
        set_var=lambda k, v: None,
        now=lambda: _T0,
    )
    assert all(isinstance(d, DagConfig) for d in dags)


def test_dag_task_delegates_to_ingestion_pipeline():
    config = _make_config("mock")
    pipeline = _mock_pipeline()
    dags = build_dags(
        config,
        lambda entry: pipeline,
        get_var=lambda k, d: None,
        set_var=lambda k, v: None,
        now=lambda: _T0,
    )

    dags[0].task_callable()

    pipeline.run.assert_called_once_with("mock", _T0 - timedelta(days=7))


def test_dag_module_imports_no_connector_or_client_classes():
    from auspex_ingest import dag_factory

    source = Path(dag_factory.__file__).read_text()
    tree = ast.parse(source)

    forbidden_names = {"MockConnector", "BiorxivConnector", "PubmedConnector", "openai", "instructor"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in forbidden_names:
            pytest.fail(f"dag_factory.py references {node.id!r}")
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and node.module
            and ("connector" in node.module or "openai" in node.module or "instructor" in node.module)
        ):
            pytest.fail(f"dag_factory.py imports from {node.module!r}")


def test_generated_dags_set_catchup_false_and_max_active_runs_one():
    config = _make_config("mock")
    pipeline = _mock_pipeline()
    dags = build_dags(
        config,
        lambda entry: pipeline,
        get_var=lambda k, d: None,
        set_var=lambda k, v: None,
        now=lambda: _T0,
    )

    assert all(d.catchup is False for d in dags)
    assert all(d.max_active_runs == 1 for d in dags)


def test_dag_factory_contains_no_source_specific_branching():
    from auspex_ingest import dag_factory

    source = Path(dag_factory.__file__).read_text()
    known_source_types = {"mock", "biorxiv", "pubmed", "epo_ops", "clinical_trials", "edgar"}
    for st in known_source_types:
        assert f'source_type == "{st}"' not in source
        assert f"source_type == '{st}'" not in source



def test_cursor_is_read_and_written_only_by_the_dag_task():
    get_calls: list[str] = []
    set_calls: list[tuple[str, str]] = []
    pipeline = _mock_pipeline()

    run_with_cursor(
        source_type="mock",
        initial_lookback=7,
        pipeline=pipeline,
        get_var=lambda k, d: get_calls.append(k) or d,  # type: ignore[func-returns-value]
        set_var=lambda k, v: set_calls.append((k, v)),
        now=lambda: _T0,
    )

    assert get_calls == ["cursor:mock"], "Variable must be read exactly once by the task"
    assert len(set_calls) == 1, "Variable must be written exactly once on success"
    assert set_calls[0][0] == "cursor:mock"
    pipeline.run.assert_called_once()


def test_cursor_advances_only_after_a_successful_run():
    writes: list[tuple[str, str]] = []
    max_date = datetime(2024, 6, 16, 0, 0, 0, tzinfo=UTC)
    pipeline = _mock_pipeline(RunResult(fetched=4, published=4, failed=0, max_published_date_processed=max_date))

    run_with_cursor(
        source_type="mock",
        initial_lookback=7,
        pipeline=pipeline,
        get_var=lambda k, d: None,
        set_var=lambda k, v: writes.append((k, v)),
        now=lambda: _T0,
    )

    assert len(writes) == 1
    assert writes[0][0] == "cursor:mock"


def test_failed_run_leaves_cursor_unchanged():
    writes: list[tuple[str, str]] = []
    pipeline = _mock_pipeline(raises=RuntimeError("Connection failed"))

    with pytest.raises(RuntimeError):
        run_with_cursor(
            source_type="mock",
            initial_lookback=7,
            pipeline=pipeline,
            get_var=lambda k, d: None,
            set_var=lambda k, v: writes.append((k, v)),
            now=lambda: _T0,
        )

    assert writes == [], "Cursor must not be written on failure"


def test_cursor_advances_to_max_published_date_not_now():
    writes: list[tuple[str, str]] = []
    later = _T0 + timedelta(hours=3)
    pipeline = _mock_pipeline(RunResult(fetched=2, published=2, failed=0, max_published_date_processed=later))
    current_now = _T0 + timedelta(hours=6)  # "now" is 6h after — must NOT be used as cursor

    run_with_cursor(
        source_type="mock",
        initial_lookback=7,
        pipeline=pipeline,
        get_var=lambda k, d: None,
        set_var=lambda k, v: writes.append((k, v)),
        now=lambda: current_now,
    )

    written_cursor = datetime.fromisoformat(writes[0][1])
    assert written_cursor == later, "Must write max_published_date, not now()"


def test_cursor_is_utc_aware():
    writes: list[tuple[str, str]] = []
    max_date = datetime(2024, 6, 16, 0, 0, 0, tzinfo=UTC)
    pipeline = _mock_pipeline(RunResult(fetched=1, published=1, failed=0, max_published_date_processed=max_date))

    run_with_cursor(
        source_type="mock",
        initial_lookback=7,
        pipeline=pipeline,
        get_var=lambda k, d: None,
        set_var=lambda k, v: writes.append((k, v)),
        now=lambda: _T0,
    )

    written = datetime.fromisoformat(writes[0][1])
    assert written.tzinfo is not None, "Written cursor must be timezone-aware"
    assert written.utcoffset() is not None and written.utcoffset().total_seconds() == 0, "Written cursor must be UTC"



def test_malformed_sources_yaml_fails_loudly(tmp_path: Path) -> None:
    bad = tmp_path / "sources.yaml"
    bad.write_text(
        "sources:\n"
        "  - source_type: mock\n"
        "    schedule: '@daily'\n"
        "    rate_limit_rps: NOT_A_NUMBER\n"
        "    initial_lookback: 7\n"
        "    max_documents_per_run: 100\n"
        "    prefilter_vocabulary: []\n"
        "    source_config: {}\n"
    )
    with pytest.raises(ValueError):
        load_sources_config(bad)


def test_duplicate_source_type_is_rejected() -> None:
    with pytest.raises(Exception, match="[Dd]uplicate"):
        SourcesConfig(sources=[
            _make_entry(source_type="mock"),
            _make_entry(source_type="mock"),
        ])



def test_airflow_metadata_is_a_separate_database() -> None:
    init_dir = Path(__file__).parents[4] / "docker" / "postgres-init"
    scripts = "\n".join(
        f.read_text()
        for f in sorted(init_dir.iterdir())
        if f.suffix in {".sh", ".sql"}
    )
    assert "CREATE DATABASE airflow" in scripts, "Airflow DB must be created as a separate database"
    assert "REVOKE ALL ON DATABASE airflow FROM PUBLIC" in scripts, "Airflow DB must be isolated from PUBLIC"



def test_rate_limited_client_enforces_configured_rps() -> None:
    current_time = [0.0]
    mock_http = MagicMock()
    mock_http.get.return_value = MagicMock(status_code=200)

    client = RateLimitedClient(
        host_limits={"api.example.com": 1.0},
        _httpx_client=mock_http,
        _clock=lambda: current_time[0],
    )

    client.get("https://api.example.com/1")  # OK: 1 token consumed

    with pytest.raises(RateLimitExceeded):
        client.get("https://api.example.com/2")  # fail: 0 tokens at t=0

    current_time[0] = 1.0  # advance 1 second → 1 token refilled
    client.get("https://api.example.com/3")  # OK again


def test_two_connectors_on_the_same_host_share_one_bucket() -> None:
    """Two URL paths on the same host share one rate-limit bucket."""
    current_time = [0.0]
    mock_http = MagicMock()
    mock_http.get.return_value = MagicMock(status_code=200)

    client = RateLimitedClient(
        host_limits={"eutils.ncbi.nlm.nih.gov": 1.0},
        _httpx_client=mock_http,
        _clock=lambda: current_time[0],
    )

    # "biorxiv connector" calls esearch
    client.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi")

    # "pubmed connector" calls efetch on same host — bucket exhausted
    with pytest.raises(RateLimitExceeded):
        client.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi")

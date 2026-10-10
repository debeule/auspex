"""The ingestion DAG file, loaded against stand-ins for Airflow and `requests`.

Airflow is not a dependency of this service, so the DAG module is executed with fake
`airflow` modules that record each DAG and task, and a fake `requests.post`.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
import types
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Self

import pytest
import yaml

_SERVICE_ROOT = Path(__file__).resolve().parents[2]
_DAG_FILE = _SERVICE_ROOT / "dags" / "auspex_dags.py"
_SOURCES_YAML = _SERVICE_ROOT / "config" / "sources.yaml"
_SCRAPER_URL = "http://scraper.test:8000"


class _Variables:
    def __init__(self, initial: dict[str, str] | None = None) -> None:
        self.store: dict[str, str] = dict(initial or {})
        self.reads: list[str] = []
        self.writes: list[tuple[str, str]] = []

    def get(self, key: str, default_var: str | None = None) -> str | None:
        self.reads.append(key)
        return self.store.get(key, default_var)

    def set(self, key: str, value: str) -> None:
        self.writes.append((key, value))
        self.store[key] = value


class _Response:
    def __init__(self, body: dict[str, Any], status: int = 200) -> None:
        self._body = body
        self._status = status

    def raise_for_status(self) -> None:
        if self._status >= 400:
            raise RuntimeError(f"HTTP {self._status}")

    def json(self) -> dict[str, Any]:
        return self._body


class _Dag:
    current: _Dag | None = None

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.tasks: list[_Operator] = []

    def __enter__(self) -> Self:
        _Dag.current = self
        return self

    def __exit__(self, *exc: object) -> None:
        _Dag.current = None


class _Operator:
    def __init__(self, task_id: str, python_callable: Any, op_kwargs: dict[str, Any]) -> None:
        self.task_id = task_id
        self.python_callable = python_callable
        self.op_kwargs = op_kwargs
        assert _Dag.current is not None, "task defined outside a DAG"
        _Dag.current.tasks.append(self)

    def run(self) -> None:
        self.python_callable(**self.op_kwargs)


def _load_dags(
    monkeypatch: pytest.MonkeyPatch,
    sources_yaml: Path,
    variables: _Variables,
    response: _Response,
) -> tuple[dict[str, _Dag], list[tuple[str, dict[str, Any]]]]:
    posts: list[tuple[str, dict[str, Any]]] = []

    def post(url: str, json: dict[str, Any], timeout: int) -> _Response:
        posts.append((url, json))
        return response

    airflow = types.ModuleType("airflow")
    airflow.DAG = _Dag  # type: ignore[attr-defined]
    operators = types.ModuleType("airflow.operators")
    python = types.ModuleType("airflow.operators.python")
    python.PythonOperator = _Operator  # type: ignore[attr-defined]
    sdk = types.ModuleType("airflow.sdk")
    sdk.Variable = variables  # type: ignore[attr-defined]
    requests = types.ModuleType("requests")
    requests.post = post  # type: ignore[attr-defined]
    for name, module in {
        "airflow": airflow,
        "airflow.operators": operators,
        "airflow.operators.python": python,
        "airflow.sdk": sdk,
        "requests": requests,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setenv("AUSPEX_SOURCES_YAML", str(sources_yaml))
    monkeypatch.setenv("SCRAPER_API_URL", _SCRAPER_URL)

    spec = importlib.util.spec_from_file_location("auspex_dags_under_test", _DAG_FILE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    dags = {
        name: value for name, value in vars(module).items()
        if isinstance(value, _Dag) and name.startswith("auspex_")
    }
    return dags, posts


def _one_source(tmp_path: Path, initial_lookback: int = 7) -> Path:
    path = tmp_path / "sources.yaml"
    path.write_text(yaml.safe_dump({"sources": [{
        "source_type": "biorxiv",
        "schedule": "@daily",
        "initial_lookback": initial_lookback,
    }]}))
    return path


def test_ingestion_dag_defines_one_dag_per_sources_entry(monkeypatch):
    configured = [s["source_type"] for s in yaml.safe_load(_SOURCES_YAML.read_text())["sources"]]

    dags, _ = _load_dags(monkeypatch, _SOURCES_YAML, _Variables(), _Response({}))

    assert sorted(dags) == sorted(f"auspex_{t}" for t in configured)
    assert all(len(dag.tasks) == 1 for dag in dags.values())


def test_ingestion_dags_disable_catchup_and_run_one_at_a_time(monkeypatch):
    dags, _ = _load_dags(monkeypatch, _SOURCES_YAML, _Variables(), _Response({}))

    assert all(dag.kwargs["catchup"] is False for dag in dags.values())
    assert all(dag.kwargs["max_active_runs"] == 1 for dag in dags.values())


def test_dag_task_posts_the_cursor_to_the_scraper_ingest_endpoint(monkeypatch, tmp_path):
    variables = _Variables({"cursor:biorxiv": "2024-06-01T00:00:00+00:00"})
    dags, posts = _load_dags(monkeypatch, _one_source(tmp_path), variables, _Response({}))

    dags["auspex_biorxiv"].tasks[0].run()

    assert posts == [(f"{_SCRAPER_URL}/ingest/biorxiv", {"cursor": "2024-06-01T00:00:00+00:00"})]


def test_cursor_advances_to_max_published_date_after_a_successful_run(monkeypatch, tmp_path):
    variables = _Variables({"cursor:biorxiv": "2024-06-01T00:00:00+00:00"})
    response = _Response({"max_published_date_processed": "2024-06-14T09:30:00+00:00"})
    dags, _ = _load_dags(monkeypatch, _one_source(tmp_path), variables, response)

    dags["auspex_biorxiv"].tasks[0].run()

    assert variables.writes == [("cursor:biorxiv", "2024-06-14T09:30:00+00:00")]


def test_failed_run_leaves_cursor_unchanged(monkeypatch, tmp_path):
    variables = _Variables({"cursor:biorxiv": "2024-06-01T00:00:00+00:00"})
    response = _Response({"max_published_date_processed": "2024-06-14T09:30:00+00:00"}, status=500)
    dags, _ = _load_dags(monkeypatch, _one_source(tmp_path), variables, response)

    with pytest.raises(RuntimeError):
        dags["auspex_biorxiv"].tasks[0].run()

    assert variables.writes == []


def test_run_that_processed_nothing_leaves_cursor_unchanged(monkeypatch, tmp_path):
    variables = _Variables({"cursor:biorxiv": "2024-06-01T00:00:00+00:00"})
    response = _Response({"max_published_date_processed": None})
    dags, _ = _load_dags(monkeypatch, _one_source(tmp_path), variables, response)

    dags["auspex_biorxiv"].tasks[0].run()

    assert variables.writes == []


def test_first_run_starts_initial_lookback_days_back_in_utc(monkeypatch, tmp_path):
    dags, posts = _load_dags(
        monkeypatch, _one_source(tmp_path, initial_lookback=10), _Variables(), _Response({})
    )

    dags["auspex_biorxiv"].tasks[0].run()

    cursor = datetime.fromisoformat(posts[0][1]["cursor"])
    assert cursor.utcoffset() == timedelta(0)
    assert abs((datetime.now(UTC) - timedelta(days=10)) - cursor) < timedelta(minutes=1)


def test_dag_file_contains_no_source_specific_branching():
    tree = ast.parse(_DAG_FILE.read_text())
    literals = {
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    configured = {s["source_type"] for s in yaml.safe_load(_SOURCES_YAML.read_text())["sources"]}

    assert literals & configured == set()

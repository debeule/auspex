"""The backup DAG file, run against stand-ins for Airflow and `requests`.

Airflow is not a dependency of this service, so the module is executed with fake `airflow`
modules that record the DAG and its task, and a fake `requests.post`.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from datetime import timedelta
from pathlib import Path
from typing import Any, Self

import pytest

_DAG_FILE = Path(__file__).resolve().parents[2] / "dags" / "backup.py"


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
    def __init__(self, task_id: str, python_callable: Any, **kwargs: Any) -> None:
        self.task_id = task_id
        self.python_callable = python_callable
        assert _Dag.current is not None
        _Dag.current.tasks.append(self)


class _Response:
    def __init__(self, status_code: int, text: str = "") -> None:
        self.status_code = status_code
        self.text = text


def _load(monkeypatch: pytest.MonkeyPatch, status: int) -> tuple[_Dag, list[dict[str, Any]]]:
    posts: list[dict[str, Any]] = []

    def post(url: str, **kwargs: Any) -> _Response:
        posts.append({"url": url, **kwargs})
        return _Response(status, '{"failed_stores": ["neo4j"]}')

    airflow = types.ModuleType("airflow")
    airflow.DAG = _Dag  # type: ignore[attr-defined]
    operators = types.ModuleType("airflow.operators")
    python = types.ModuleType("airflow.operators.python")
    python.PythonOperator = _Operator  # type: ignore[attr-defined]
    requests = types.ModuleType("requests")
    requests.post = post  # type: ignore[attr-defined]
    for name, module in {
        "airflow": airflow,
        "airflow.operators": operators,
        "airflow.operators.python": python,
        "requests": requests,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setenv("BACKUP_API_URL", "http://backup.test:8002")

    spec = importlib.util.spec_from_file_location("backup_dag", _DAG_FILE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    dags = [v for v in vars(module).values() if isinstance(v, _Dag)]
    assert len(dags) == 1
    return dags[0], posts


def test_backup_dag_posts_to_the_backup_service_and_fails_on_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dag, posts = _load(monkeypatch, status=200)
    assert dag.kwargs["dag_id"] == "auspex_backup"
    assert dag.kwargs["schedule"] == "0 3 * * *"
    assert dag.kwargs["catchup"] is False
    assert dag.kwargs["is_paused_upon_creation"] is False
    assert dag.kwargs["default_args"]["retries"] >= 1
    assert isinstance(dag.kwargs["default_args"]["retry_delay"], timedelta)
    assert dag.kwargs["start_date"].utcoffset() == timedelta(0)
    [task] = dag.tasks

    task.python_callable()
    assert [p["url"] for p in posts] == ["http://backup.test:8002/backup"]

    dag, posts = _load(monkeypatch, status=500)
    with pytest.raises(RuntimeError, match="500"):
        dag.tasks[0].python_callable()

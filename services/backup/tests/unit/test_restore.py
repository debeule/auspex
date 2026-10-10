import json
from pathlib import Path

import pytest
from fakes import FakeDriver, FakeGraph, FakeMinio, FakeRunner

from auspex_backup.restore import TargetNotEmptyError, restore

_DAY = "2026-10-10"


def _backup(root: Path) -> None:
    dumps = root / "postgres" / _DAY
    dumps.mkdir(parents=True)
    (dumps / "auspex.dump").write_bytes(b"PGDMP-a")
    (dumps / "airflow.dump").write_bytes(b"PGDMP-b")
    graph = root / "neo4j" / _DAY
    graph.mkdir(parents=True)
    node = {"kind": "node", "id": "1", "labels": ["Company"], "properties": {"name": "acme"}}
    (graph / "graph.jsonl").write_text(json.dumps(node) + "\n")
    raw = root / "minio" / "auspex-raw" / "edgar"
    raw.mkdir(parents=True)
    (raw / "doc.json").write_bytes(b"doc")
    (root / "minio" / ".index").mkdir()
    (root / "minio" / ".index" / "auspex-raw.json").write_text("{}")


def _restore(root: Path, runner: FakeRunner, graph: FakeGraph, minio: FakeMinio) -> None:
    restore(
        root,
        _DAY,
        runner=runner,
        pg_environment={"PGHOST": "postgres", "PGPASSWORD": "x"},
        databases=["auspex", "airflow"],
        driver=FakeDriver(graph),
        minio=minio,
        buckets=["auspex-raw", "auspex-prices"],
    )


@pytest.mark.parametrize("store", ["postgres", "neo4j", "minio"])
def test_restore_refuses_a_target_store_that_is_not_empty(tmp_path: Path, store: str) -> None:
    _backup(tmp_path)
    runner = FakeRunner(output=b"4\n" if store == "postgres" else b"0\n")
    graph = FakeGraph(
        nodes=[{"id": "9", "labels": ["Company"], "properties": {}}] if store == "neo4j" else []
    )
    minio = FakeMinio({"auspex-prices": {"x": b"x"}} if store == "minio" else {})

    with pytest.raises(TargetNotEmptyError) as refused:
        _restore(tmp_path, runner, graph, minio)

    assert store in str(refused.value)
    assert not any(c.argv[0] == "pg_restore" for c in runner.calls)
    assert graph.writes == 0
    assert "fput_object" not in minio.calls


def test_restore_loads_every_store_into_empty_targets(tmp_path: Path) -> None:
    _backup(tmp_path)
    runner = FakeRunner(output=b"0\n")
    graph = FakeGraph()
    minio = FakeMinio()

    _restore(tmp_path, runner, graph, minio)

    restores = [c for c in runner.calls if c.argv[0] == "pg_restore"]
    assert [c.argv for c in restores] == [
        ["pg_restore", "--exit-on-error", "--dbname=auspex"],
        ["pg_restore", "--exit-on-error", "--dbname=airflow"],
    ]
    assert [c.stdin for c in restores] == [
        tmp_path / "postgres" / _DAY / "auspex.dump",
        tmp_path / "postgres" / _DAY / "airflow.dump",
    ]
    assert all("x" not in c.argv for c in runner.calls)
    assert graph.writes >= 1
    assert minio.buckets == {"auspex-raw": {"edgar/doc.json": b"doc"}}


def test_restore_of_a_missing_date_fails_before_touching_any_store(tmp_path: Path) -> None:
    _backup(tmp_path)
    runner = FakeRunner(output=b"0\n")
    with pytest.raises(FileNotFoundError):
        restore(
            tmp_path,
            "2026-01-01",
            runner=runner,
            pg_environment={},
            databases=["auspex", "airflow"],
            driver=FakeDriver(FakeGraph()),
            minio=FakeMinio(),
            buckets=["auspex-raw"],
        )
    assert runner.calls == []

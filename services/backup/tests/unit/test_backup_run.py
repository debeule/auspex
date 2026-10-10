import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fakes import FakeDriver, FakeGraph, FakeMinio, FakeRunner

from auspex_backup.api import create_app
from auspex_backup.backup import Backup, Store, StoreFailedError, build_stores

_START = datetime(2026, 10, 10, 3, 0, 0, tzinfo=UTC)
_END = datetime(2026, 10, 10, 3, 4, 0, tzinfo=UTC)
_PREVIOUS = {"started_at": "2026-10-09T03:00:00Z", "stores": {}}


def _clock() -> object:
    times = iter([_START, _END])
    return lambda: next(times)


def _seed_previous_manifest(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "last_success.json").write_text(json.dumps(_PREVIOUS))


def test_manifest_is_written_last_and_only_when_every_store_succeeded(tmp_path: Path) -> None:
    _seed_previous_manifest(tmp_path)
    seen: list[str] = []

    def store(name: str) -> Store:
        def run(day: str) -> dict[str, int]:
            # The previous manifest is still in place while every store runs.
            assert json.loads((tmp_path / "last_success.json").read_text()) == _PREVIOUS
            seen.append(f"{name}:{day}")
            return {"objects": 2, "bytes": 10}

        return Store(name, run)

    stores = [store("postgres"), store("neo4j"), store("minio")]
    manifest = Backup(tmp_path, stores, keep_days=14, now=_clock()).run()

    assert seen == ["postgres:2026-10-10", "neo4j:2026-10-10", "minio:2026-10-10"]
    written = json.loads((tmp_path / "last_success.json").read_text())
    assert written == manifest
    assert written["started_at"] == "2026-10-10T03:00:00Z"
    assert written["finished_at"] == "2026-10-10T03:04:00Z"
    assert written["stores"]["minio"] == {"objects": 2, "bytes": 10}
    assert sorted(p.name for p in tmp_path.iterdir()) == ["last_success.json"]


def test_failed_store_returns_500_naming_it_and_keeps_the_previous_manifest(
    tmp_path: Path,
) -> None:
    _seed_previous_manifest(tmp_path)
    ran: list[str] = []

    def ok(name: str) -> Store:
        return Store(name, lambda day: ran.append(name) or {"bytes": 1})

    def broken(day: str) -> dict[str, int]:
        raise OSError("neo4j unreachable")

    backup = Backup(tmp_path, [ok("postgres"), Store("neo4j", broken), ok("minio")], 14, _clock())
    with pytest.raises(StoreFailedError) as failure:
        backup.run()
    assert failure.value.stores == ["neo4j"]
    assert ran == ["postgres", "minio"]
    assert json.loads((tmp_path / "last_success.json").read_text()) == _PREVIOUS

    backup = Backup(tmp_path, [ok("postgres"), Store("neo4j", broken), ok("minio")], 14, _clock())
    response = create_app(lambda: backup).test_client().post("/backup")
    assert response.status_code == 500
    assert response.get_json()["failed_stores"] == ["neo4j"]
    assert "neo4j unreachable" in response.get_json()["error"]
    assert json.loads((tmp_path / "last_success.json").read_text()) == _PREVIOUS


def test_backup_endpoint_returns_the_manifest(tmp_path: Path) -> None:
    backup = Backup(tmp_path, [Store("postgres", lambda day: {"bytes": 3})], 14, _clock())
    client = create_app(lambda: backup).test_client()
    assert client.get("/health").status_code == 200
    response = client.post("/backup")
    assert response.status_code == 200
    assert response.get_json()["stores"] == {"postgres": {"bytes": 3}}


def test_successful_backup_prunes_old_dated_folders(tmp_path: Path) -> None:
    for parent in ("postgres", "neo4j"):
        for day in ("2026-09-01", "2026-10-09"):
            (tmp_path / parent / day).mkdir(parents=True)
    Backup(tmp_path, [Store("postgres", lambda day: {})], keep_days=14, now=_clock()).run()
    for parent in ("postgres", "neo4j"):
        assert [p.name for p in (tmp_path / parent).iterdir()] == ["2026-10-09"]


def test_backup_reads_but_never_writes_to_minio_postgres_or_neo4j(tmp_path: Path) -> None:
    minio = FakeMinio({"auspex-raw": {"r.json": b"r"}, "auspex-prices": {"p.parquet": b"p"}})
    graph = FakeGraph(
        nodes=[{"id": "4:n:1", "labels": ["Company"], "properties": {"name": "acme"}}],
        rels=[],
    )
    runner = FakeRunner()
    stores = build_stores(
        tmp_path,
        runner=runner,
        pg_environment={"PGHOST": "postgres", "PGPASSWORD": "x"},
        databases=["auspex", "airflow"],
        driver=FakeDriver(graph),
        minio=minio,
        buckets=["auspex-raw", "auspex-prices"],
    )
    manifest = Backup(tmp_path, stores, keep_days=14, now=_clock()).run()

    assert set(minio.calls) <= {"list_objects", "fget_object"}
    assert graph.writes == 0 and graph.reads == 1
    assert all(
        not any(word in query.upper() for word in ("CREATE", "MERGE", "SET ", "DELETE"))
        for query, _ in graph.queries
    )
    assert {c.argv[0] for c in runner.calls} == {"pg_dump"}
    assert manifest["stores"]["neo4j"] == {"nodes": 1, "relationships": 0}
    assert (tmp_path / "minio" / "auspex-prices" / "p.parquet").read_bytes() == b"p"
    assert (tmp_path / "postgres" / "2026-10-10" / "airflow.dump").exists()
    assert (tmp_path / "neo4j" / "2026-10-10" / "graph.jsonl").exists()

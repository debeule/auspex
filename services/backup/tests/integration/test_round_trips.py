"""Backup and restore of each store against real containers: what goes in comes back out."""

from __future__ import annotations

import io
import os
import time
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest
from minio import Minio
from neo4j import Driver, GraphDatabase
from testcontainers.core.container import DockerContainer

from auspex_backup.graph import export_graph, node_count, replay_graph
from auspex_backup.minio_mirror import mirror_bucket
from auspex_backup.postgres import CommandRunner, dump_databases, restore_database, run_command
from auspex_backup.restore import upload_mirror

os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")

pytestmark = pytest.mark.integration

_POSTGRES_IMAGE = "postgres:18.6"
_NEO4J_IMAGE = "neo4j:2026.05-community"
_LOCALSTACK_IMAGE = "localstack/localstack:4.9.2"
_PG_USER = "auspex_app"
_PG_PASSWORD = "integration-only"
_NEO4J_PASSWORD = "integration-only"


def _wait(check: Any, what: str, attempts: int = 120) -> None:
    for _ in range(attempts):
        try:
            if check():
                return
        except Exception:  # noqa: BLE001 - not up yet
            time.sleep(1)
            continue
        time.sleep(1)
    pytest.fail(f"{what} never became ready")


def _postgres() -> DockerContainer:
    return (
        DockerContainer(_POSTGRES_IMAGE)
        .with_env("POSTGRES_USER", _PG_USER)
        .with_env("POSTGRES_PASSWORD", _PG_PASSWORD)
        .with_env("POSTGRES_DB", "auspex")
    )


def _in_container(container: DockerContainer) -> CommandRunner:
    """Runs the client tools inside the Postgres container, so they match the server's version."""
    container_id = container.get_wrapped_container().id

    def runner(
        argv: Sequence[str],
        env: Mapping[str, str],
        *,
        stdin: Path | None = None,
        stdout: Path | None = None,
    ) -> bytes:
        flags = [f"--env={k}={v}" for k, v in env.items() if k != "PATH"]
        return run_command(
            ["docker", "exec", "-i", *flags, container_id, *argv],
            {"PATH": os.environ["PATH"]},
            stdin=stdin,
            stdout=stdout,
        )

    return runner


def _psql(runner: CommandRunner, database: str, sql: str) -> str:
    env = {"PGUSER": _PG_USER, "PGPASSWORD": _PG_PASSWORD, "PGHOST": "localhost"}
    return runner(["psql", "-v", "ON_ERROR_STOP=1", "-At", f"--dbname={database}", "-c", sql], env).decode()


@pytest.fixture(scope="module")
def postgres_pair() -> Iterator[tuple[CommandRunner, CommandRunner]]:
    with _postgres() as source, _postgres() as target:
        runners = (_in_container(source), _in_container(target))
        for runner in runners:
            _wait(lambda r=runner: _psql(r, "auspex", "SELECT 1").strip() == "1", "postgres")
            _psql(runner, "auspex", "CREATE DATABASE airflow")
        yield runners


def test_postgres_backup_and_restore_round_trip_gives_identical_rows(
    postgres_pair: tuple[CommandRunner, CommandRunner], tmp_path: Path
) -> None:
    source, target = postgres_pair
    _psql(
        source,
        "auspex",
        "CREATE TABLE signal_current (event_id text PRIMARY KEY, confidence_score numeric(4,3), "
        "published_at timestamptz, entities jsonb);"
        "INSERT INTO signal_current VALUES "
        "('e-1', 0.875, '2026-09-01T14:30:00Z', '{\"company\": \"acme\"}'),"
        "('e-2', 0.5, '2026-09-02T09:00:00Z', '[]');",
    )
    _psql(
        source,
        "airflow",
        "CREATE TABLE variable (key text PRIMARY KEY, val text);"
        "INSERT INTO variable VALUES ('cursor:edgar', 'gAAAAB-encrypted');",
    )
    env = {"PGUSER": _PG_USER, "PGPASSWORD": _PG_PASSWORD, "PGHOST": "localhost"}

    sizes = dump_databases(source, ["auspex", "airflow"], tmp_path, env)
    assert all(size > 0 for size in sizes.values())
    for database in ("auspex", "airflow"):
        restore_database(target, database, tmp_path / f"{database}.dump", env)

    rows = "SELECT * FROM signal_current ORDER BY event_id"
    assert _psql(target, "auspex", rows) == _psql(source, "auspex", rows)
    variables = "SELECT * FROM variable ORDER BY key"
    assert _psql(target, "airflow", variables) == _psql(source, "airflow", variables)
    assert "e-2" in _psql(target, "auspex", rows)


@pytest.fixture(scope="module")
def neo4j_driver() -> Iterator[Driver]:
    container = (
        DockerContainer(_NEO4J_IMAGE)
        .with_env("NEO4J_AUTH", f"neo4j/{_NEO4J_PASSWORD}")
        .with_exposed_ports(7687)
    )
    with container:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(7687)
        driver = GraphDatabase.driver(f"bolt://{host}:{port}", auth=("neo4j", _NEO4J_PASSWORD))

        def ready() -> bool:
            driver.verify_connectivity()
            return True

        _wait(ready, "neo4j", attempts=180)
        yield driver
        driver.close()


def _canonical(driver: Driver) -> tuple[list[Any], list[Any]]:
    with driver.session() as session:
        nodes = session.run(
            "MATCH (n) RETURN labels(n) AS labels, properties(n) AS props"
        ).data()
        rels = session.run(
            "MATCH (a)-[r]->(b) RETURN type(r) AS type, properties(r) AS props, "
            "properties(a) AS start, properties(b) AS end"
        ).data()
    key = repr
    return sorted(nodes, key=key), sorted(rels, key=key)


def test_neo4j_backup_and_restore_round_trip_gives_identical_graph(
    neo4j_driver: Driver, tmp_path: Path
) -> None:
    with neo4j_driver.session() as session:
        session.run(
            "CREATE (c:Company {name: 'acme', ticker: 'ACME', aliases: ['acme inc', 'acme']}) "
            "CREATE (s:Signal:Corroborated {event_id: 'e-1', confidence_score: 0.875, "
            "  published_date: date('2026-09-01'), "
            "  corroborated_at: datetime('2026-09-02T14:30:00.123456789Z')}) "
            "CREATE (m:Mechanism {name: 'GLP-1 agonism'}) "
            "CREATE (s)-[:MENTIONS {weight: 2}]->(c) "
            "CREATE (s)-[:VIA]->(m) "
            "CREATE (c)-[:MENTIONS {weight: 1}]->(c)"
        ).consume()
    before = _canonical(neo4j_driver)
    path = tmp_path / "graph.jsonl"

    counts = export_graph(neo4j_driver, path)
    assert (counts.nodes, counts.relationships) == (3, 3)

    with neo4j_driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n").consume()
    assert node_count(neo4j_driver) == 0

    assert replay_graph(neo4j_driver, path) == counts
    assert _canonical(neo4j_driver) == before


@pytest.fixture(scope="module")
def minio_client() -> Iterator[Minio]:
    container = DockerContainer(_LOCALSTACK_IMAGE).with_exposed_ports(4566).with_env("SERVICES", "s3")
    with container:
        _wait(lambda: container.get_exposed_port(4566), "localstack port")
        client = Minio(
            f"{container.get_container_host_ip()}:{container.get_exposed_port(4566)}",
            access_key="test",
            secret_key="test",
            secure=False,
        )
        _wait(lambda: client.list_buckets() is not None, "localstack")
        yield client


def _objects(client: Minio, bucket: str) -> dict[str, bytes]:
    found = {}
    for obj in client.list_objects(bucket, recursive=True):
        response = client.get_object(bucket, obj.object_name or "")
        try:
            found[obj.object_name or ""] = response.read()
        finally:
            response.close()
            response.release_conn()
    return found


def test_minio_backup_and_restore_round_trip_gives_identical_objects(
    minio_client: Minio, tmp_path: Path
) -> None:
    content = {
        "auspex-raw": {"edgar/2026/09/01/0001.json": b'{"a": 1}', "pubmed/x.json": b"{}"},
        "auspex-prices": {"ohlcv/XBI.parquet": bytes(range(256)) * 64, "universe/1/rules.yaml": b"v: 1"},
    }
    for bucket, objects in content.items():
        minio_client.make_bucket(bucket)
        for key, data in objects.items():
            minio_client.put_object(bucket, key, io.BytesIO(data), len(data))

    for bucket, objects in content.items():
        result = mirror_bucket(minio_client, bucket, tmp_path)
        assert (result.objects, result.copied) == (len(objects), len(objects))

    for bucket, objects in content.items():
        for key in objects:
            minio_client.remove_object(bucket, key)
        assert _objects(minio_client, bucket) == {}

    assert upload_mirror(minio_client, tmp_path, list(content)) == 4
    for bucket, objects in content.items():
        assert _objects(minio_client, bucket) == objects

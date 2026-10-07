"""Prerequisites: docker compose -f docker/docker-compose.yml up -d --wait && ./docker/provision.sh"""

import socket
import subprocess

import pytest
from confluent_kafka import KafkaError, Producer
from confluent_kafka.admin import AdminClient, ConfigResource
from minio import Minio

KAFKA_BOOTSTRAP = "127.0.0.1:9092"
MINIO_ENDPOINT = "localhost:9000"
POSTGRES_CONTAINER = "auspex-postgres"


def _read_env(key: str, default: str = "") -> str:
    """Read a value from the running environment (already loaded by pytest / .env)."""
    import os
    return os.environ.get(key, default)


def _psql(*args: str) -> subprocess.CompletedProcess[str]:
    user = _read_env("POSTGRES_USER", "auspex_app")
    db = _read_env("POSTGRES_DB", "auspex")
    return subprocess.run(
        ["docker", "exec", POSTGRES_CONTAINER, "psql", "-U", user, "-d", db, *args],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )



@pytest.mark.integration
def test_all_containers_reachable():
    checks = {
        "postgres": ("localhost", 5432),
        "kafka":    ("localhost", 9092),
        "neo4j":    ("localhost", 7687),
        "minio":    ("localhost", 9000),
    }
    unreachable = []
    for name, (host, port) in checks.items():
        with socket.socket() as s:
            s.settimeout(5)
            if s.connect_ex((host, port)) != 0:
                unreachable.append(f"{name} ({host}:{port})")
    assert not unreachable, f"Containers not reachable: {unreachable}"


@pytest.mark.integration
def test_postgres_has_separate_airflow_database():
    result = _psql("-c", "SELECT datname FROM pg_database WHERE datname = 'airflow'", "-t")
    assert result.returncode == 0, f"psql failed: {result.stderr}"
    assert "airflow" in result.stdout, "airflow database not found in pg_database"


@pytest.mark.integration
def test_postgres_timezone_is_utc():
    result = _psql("-c", "SHOW timezone", "-t")
    assert result.returncode == 0, f"psql failed: {result.stderr}"
    assert "UTC" in result.stdout.upper(), f"Postgres timezone is not UTC: {result.stdout.strip()!r}"


@pytest.mark.integration
def test_minio_bucket_exists():
    access_key = _read_env("MINIO_ACCESS_KEY")
    secret_key = _read_env("MINIO_SECRET_KEY")
    bucket = _read_env("MINIO_BUCKET", "auspex-raw")
    assert access_key, "MINIO_ACCESS_KEY not set — source .env before running"
    mc = Minio(MINIO_ENDPOINT, access_key=access_key, secret_key=secret_key, secure=False)
    assert mc.bucket_exists(bucket), f"MinIO bucket '{bucket}' does not exist — run ./docker/provision.sh"


@pytest.mark.integration
def test_topics_created_from_topics_yaml_with_declared_partitions_and_retention():
    from pathlib import Path

    import yaml

    topics_path = Path(__file__).resolve().parents[4] / "docker" / "topics.yaml"
    declared = yaml.safe_load(topics_path.read_text())["topics"]

    admin = AdminClient({"bootstrap.servers": KAFKA_BOOTSTRAP})
    metadata = admin.list_topics(timeout=10)

    for topic_def in declared:
        name = topic_def["name"]
        assert name in metadata.topics, f"Topic '{name}' missing from Kafka"
        topic_meta = metadata.topics[name]
        assert len(topic_meta.partitions) == topic_def["partitions"], (
            f"Topic '{name}': expected {topic_def['partitions']} partitions, "
            f"got {len(topic_meta.partitions)}"
        )

    # Verify retention on one representative topic
    resource = ConfigResource("topic", "auspex.raw.ingested")
    result = admin.describe_configs([resource])
    config = result[resource].result()
    retention = config["retention.ms"].value
    assert retention == "604800000", (
        f"auspex.raw.ingested retention.ms expected 604800000, got {retention}"
    )


@pytest.mark.integration
def test_dlt_partition_count_matches_source_topic():
    admin = AdminClient({"bootstrap.servers": KAFKA_BOOTSTRAP})
    metadata = admin.list_topics(timeout=10)

    pairs = [
        ("auspex.raw.ingested",         "auspex.raw.ingested.dlt"),
        ("auspex.signals.extracted",    "auspex.signals.extracted.dlt"),
        ("auspex.signals.corroborated", "auspex.signals.corroborated.dlt"),
    ]
    for source, dlt in pairs:
        src_parts = len(metadata.topics[source].partitions)
        dlt_parts = len(metadata.topics[dlt].partitions)
        assert src_parts == dlt_parts, (
            f"DLT partition mismatch: {source} has {src_parts} partitions "
            f"but {dlt} has {dlt_parts}"
        )


@pytest.mark.integration
def test_producing_to_an_undeclared_topic_fails():
    errors: list[KafkaError] = []

    def on_delivery(err, _msg):
        if err:
            errors.append(err)

    producer = Producer({
        "bootstrap.servers": KAFKA_BOOTSTRAP,
        "message.timeout.ms": 5000,
    })
    producer.produce("auspex.does.not.exist", b"probe", callback=on_delivery)
    producer.flush(timeout=10.0)

    assert errors, (
        "Expected a delivery failure for an undeclared topic with "
        "auto.create.topics.enable=false, but no error was reported"
    )

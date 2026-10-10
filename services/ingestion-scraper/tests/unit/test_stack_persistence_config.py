"""Static checks that recreating containers and images keeps the stack's state: data on named
volumes, Airflow's secrets from `.env`, Kafka offsets and cluster ID, the project name, and docs
that never offer `down -v` as a fix.

Parses `docker/docker-compose.yml`, `.env.example`, the role script and the docs; no container is
started. The recreate itself is checked on the stack machine (`specs/first-run-on-stack-machine.md`).
"""

import re
from pathlib import Path
from typing import Any

import yaml

# tests/unit/ -> tests/ -> ingestion-scraper/ -> services/ -> auspex/
REPO_ROOT = Path(__file__).resolve().parents[4]
DOCKER = REPO_ROOT / "docker"

# The `apache/kafka` image's built-in default (`configureDefaults`): volumes formatted before the
# ID was pinned carry this one, and Kafka refuses a formatted volume under any other.
_IMAGE_DEFAULT_CLUSTER_ID = "5L6g3nShT-eMCtK--X86sw"
_REQUIRED_REF = re.compile(r"^\$\{(?P<var>[A-Z0-9_]+):\?[^}]+\}$")
_AIRFLOW_UID = "50000"


def _compose() -> dict[str, Any]:
    return yaml.safe_load((DOCKER / "docker-compose.yml").read_text(encoding="utf-8"))


def _services() -> dict[str, dict[str, Any]]:
    return _compose()["services"]


def _env_example() -> dict[str, str]:
    values: dict[str, str] = {}
    for line in (REPO_ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    return values


def _named_mounts(service: dict[str, Any]) -> dict[str, str]:
    """Container path -> volume name, for short-syntax mounts whose source is a named volume."""
    declared = _compose()["volumes"]
    mounts: dict[str, str] = {}
    for mount in service.get("volumes", []):
        parts = str(mount).split(":")
        if len(parts) >= 2 and parts[0] in declared:
            mounts[parts[1]] = parts[0]
    return mounts


def test_every_stateful_service_keeps_its_data_dir_on_a_declared_named_volume() -> None:
    data_dirs = {
        "kafka": "/var/lib/kafka/data",
        "postgres": "/var/lib/postgresql",
        "neo4j": "/data",
        "minio": "/data",
        "elasticsearch": "/usr/share/elasticsearch/data",
        "prometheus": "/prometheus",
        "grafana": "/var/lib/grafana",
        "filebeat": "/usr/share/filebeat/data",
        "airflow": "/opt/airflow/logs",
    }
    password_file = _services()["airflow"]["environment"][
        "AIRFLOW__CORE__SIMPLE_AUTH_MANAGER_PASSWORDS_FILE"
    ]
    declared = _compose()["volumes"]
    for name, path in [*data_dirs.items(), ("airflow", str(Path(password_file).parent))]:
        mounts = _named_mounts(_services()[name])
        assert path in mounts, f"{name}: {path} is not on a named volume"
        volume = declared[mounts[path]] or {}
        assert not volume.get("external"), f"{name}: volume {mounts[path]} is external"


def test_airflow_fernet_key_jwt_secret_and_api_secret_key_are_required_env_references() -> None:
    env = _services()["airflow"]["environment"]
    example = _env_example()
    for option in (
        "AIRFLOW__CORE__FERNET_KEY",
        "AIRFLOW__API_AUTH__JWT_SECRET",
        "AIRFLOW__API__SECRET_KEY",
    ):
        m = _REQUIRED_REF.match(str(env.get(option, "")))
        assert m, f"{option} is {env.get(option)!r}, not a required ${{VAR:?message}} reference"
        assert m.group("var") in example, f"{m.group('var')} missing from .env.example"


def test_airflow_uses_no_airflow_2_webserver_options() -> None:
    env = _services()["airflow"]["environment"]
    stale = [key for key in env if key.startswith("AIRFLOW__WEBSERVER__")]
    assert not stale, f"Airflow 3 ignores {stale}"


def test_airflow_password_file_is_on_the_airflow_state_volume() -> None:
    airflow = _services()["airflow"]
    password_file = airflow["environment"]["AIRFLOW__CORE__SIMPLE_AUTH_MANAGER_PASSWORDS_FILE"]
    mounts = _named_mounts(airflow)
    holders = [path for path in mounts if password_file.startswith(path.rstrip("/") + "/")]
    assert holders, f"{password_file} is not inside a named volume"
    assert mounts[holders[0]] == "airflow_state"


def test_airflow_state_volume_is_made_writable_for_the_airflow_user_before_airflow_starts() -> None:
    init = _services()["airflow-state-init"]
    assert init["restart"] == "no"
    assert "airflow_state:/state" in init["volumes"]
    assert f"chown {_AIRFLOW_UID}:0 /state" in " ".join(init["command"])
    assert _services()["airflow"]["depends_on"]["airflow-state-init"] == {
        "condition": "service_completed_successfully"
    }


def test_kafka_cluster_id_is_pinned_to_the_id_existing_volumes_were_formatted_with() -> None:
    assert _services()["kafka"]["environment"]["CLUSTER_ID"] == _IMAGE_DEFAULT_CLUSTER_ID


def test_kafka_offsets_outlive_the_longest_topic_retention() -> None:
    topics = yaml.safe_load((DOCKER / "topics.yaml").read_text(encoding="utf-8"))["topics"]
    longest_ms = max(int(t["retention_ms"]) for t in topics)
    minutes = int(_services()["kafka"]["environment"]["KAFKA_OFFSETS_RETENTION_MINUTES"])
    assert minutes * 60_000 >= longest_ms


def test_compose_file_names_the_project_and_env_example_agrees() -> None:
    assert _compose()["name"] == "auspex"
    assert _env_example()["COMPOSE_PROJECT_NAME"] == "auspex"


def test_airflow_db_role_job_runs_before_airflow_and_after_postgres() -> None:
    job = _services()["airflow-db-role"]
    assert job["restart"] == "no"
    assert job["depends_on"]["postgres"] == {"condition": "service_healthy"}
    assert _services()["airflow"]["depends_on"]["airflow-db-role"] == {
        "condition": "service_completed_successfully"
    }


def test_airflow_db_role_script_alters_the_role_from_env_and_creates_it_if_missing() -> None:
    script = (DOCKER / "airflow-db-role" / "apply-role.sh").read_text(encoding="utf-8")
    assert '-v role="$AIRFLOW_DB_USER"' in script
    assert '-v password="$AIRFLOW_DB_PASSWORD"' in script
    assert "WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'role')" in script
    assert "ALTER ROLE :\"role\" WITH LOGIN PASSWORD :'password'" in script
    # The SQL reaches psql through a quoted heredoc, so the shell never splices values into it.
    assert "<<'EOSQL'" in script
    assert "DROP" not in script.upper()


def test_docs_never_offer_down_v_as_a_fix() -> None:
    for doc in ("README.md", "CLAUDE.md", "SETUP.md", "docker/README.md", "docker/CLAUDE.md"):
        for n, line in enumerate((REPO_ROOT / doc).read_text(encoding="utf-8").splitlines(), 1):
            if "down -v" in line:
                assert "destroys all data" in line, f"{doc}:{n} mentions down -v without warning"


def test_new_secrets_are_documented_in_setup() -> None:
    setup = (REPO_ROOT / "SETUP.md").read_text(encoding="utf-8")
    preflight = next(
        line
        for line in (REPO_ROOT / "specs" / "first-run-on-stack-machine.md")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.startswith("test -f .env && for k in")
    )
    for var in ("AIRFLOW_FERNET_KEY", "AIRFLOW_JWT_SECRET", "AIRFLOW_SECRET_KEY"):
        assert f"`{var}`" in setup, f"{var} not in SETUP.md"
        assert f" {var} " in preflight, f"{var} not checked by the first-run preflight"

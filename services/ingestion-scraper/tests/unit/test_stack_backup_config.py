"""Static checks of the backup and restore services in `docker/docker-compose.yml`.

Parses the compose file and `.env.example`; no container is started. The backup itself is
tested in `services/backup`.
"""

import re
from pathlib import Path
from typing import Any

import yaml

# tests/unit/ -> tests/ -> ingestion-scraper/ -> services/ -> auspex/
REPO_ROOT = Path(__file__).resolve().parents[4]
_REQUIRED_REF = re.compile(r"^\$\{(?P<var>[A-Z0-9_]+):\?[^}]+\}$")


def _services() -> dict[str, dict[str, Any]]:
    compose = yaml.safe_load((REPO_ROOT / "docker" / "docker-compose.yml").read_text("utf-8"))
    return compose["services"]


def _env_example() -> set[str]:
    keys = set()
    for line in (REPO_ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            keys.add(line.partition("=")[0].strip())
    return keys


def _mounts(service: dict[str, Any]) -> dict[str, tuple[str, str]]:
    """Container path -> (source, mode) for short-syntax mounts."""
    mounts = {}
    for mount in service.get("volumes", []):
        spec, mode = str(mount), "rw"
        if spec.endswith((":ro", ":rw")):
            spec, mode = spec[:-3], spec[-2:]
        source, _, target = spec.rpartition(":")
        mounts[target] = (source, mode)
    return mounts


def test_backup_destination_is_a_bind_mount_from_backup_host_dir() -> None:
    backup = _services()["backup"]
    source, mode = _mounts(backup)["/backup"]
    assert mode == "rw"
    m = _REQUIRED_REF.match(source)
    assert m and m.group("var") == "BACKUP_HOST_DIR", f"/backup is mounted from {source!r}"
    assert "BACKUP_HOST_DIR" in _env_example()
    assert not backup.get("ports"), "the backup service is reachable only on the compose network"
    assert backup["restart"] != "no"


def test_backup_dag_directory_is_mounted_into_airflow() -> None:
    airflow = _services()["airflow"]
    mounts = [str(m) for m in airflow["volumes"]]
    assert any(m.startswith("../services/backup/dags:/opt/airflow/dags/") for m in mounts), mounts
    assert airflow["environment"]["BACKUP_API_URL"] == "${BACKUP_API_URL}"
    assert "BACKUP_API_URL" in _env_example()


def test_restore_service_runs_only_under_the_restore_profile() -> None:
    services = _services()
    restore = services["restore"]
    assert restore["profiles"] == ["restore"]
    assert restore["restart"] == "no"
    assert "auspex_backup.restore" in restore["entrypoint"]
    assert _mounts(restore)["/backup"] == _mounts(services["backup"])["/backup"][:1] + ("ro",)
    assert not any(
        "restore" in (s.get("profiles") or []) for name, s in services.items() if name != "restore"
    )

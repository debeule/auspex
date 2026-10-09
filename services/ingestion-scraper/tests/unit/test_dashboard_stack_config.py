"""The dashboard's compose service: reachable only on localhost, configured only from `.env`."""

import re
from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[4]
_COMPOSE = _REPO_ROOT / "docker" / "docker-compose.yml"
_ENV_EXAMPLE = _REPO_ROOT / ".env.example"

_ENV_REFERENCE = re.compile(r"^\$\{([A-Z][A-Z0-9_]*)\}$")
_BACKEND_URLS = ("CORE_HUB_URL", "SCRAPER_URL", "PRICE_SERVICE_URL")
_SECRETS = (
    "DASHBOARD_USERNAME",
    "DASHBOARD_PASSWORD_HASH",
    "DASHBOARD_SESSION_SECRET",
    "CORE_HUB_WRITE_TOKEN",
)


def _services() -> dict[str, Any]:
    services: dict[str, Any] = yaml.safe_load(_COMPOSE.read_text(encoding="utf-8"))["services"]
    return services


def _env_example() -> dict[str, str]:
    entries = {}
    for line in _ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            entries[key] = value
    return entries


def test_dashboard_service_is_in_app_profile_bound_to_localhost_with_healthcheck() -> None:
    dashboard = _services()["dashboard"]

    assert dashboard["profiles"] == ["app"]
    assert dashboard["ports"] == ["127.0.0.1:${DASHBOARD_PORT:-3001}:3000"]
    assert dashboard["depends_on"]["core-hub"]["condition"] == "service_healthy"
    probe = " ".join(dashboard["healthcheck"]["test"])
    assert "/api/health" in probe
    assert "3000" in probe
    assert dashboard["build"]["context"] == "../services/dashboard"


def test_dashboard_service_gets_backend_urls_and_secrets_from_env_only() -> None:
    services = _services()
    environment: dict[str, str] = services["dashboard"]["environment"]
    documented = _env_example()

    for name in (*_BACKEND_URLS, *_SECRETS, "DASHBOARD_SESSION_IDLE_MINUTES"):
        assert name in environment, f"{name} missing from the dashboard service"
    for name, value in environment.items():
        match = _ENV_REFERENCE.match(str(value))
        assert match, f"{name} must be a bare ${{VAR}} reference, got {value!r}"
        assert match.group(1) in documented, f"{match.group(1)} is not documented in .env.example"
    for name in _SECRETS:
        source = _ENV_REFERENCE.match(environment[name]).group(1)  # type: ignore[union-attr]
        assert documented[source] == "", f"{source} must be empty in .env.example"
    assert not any(key.startswith("NEXT_PUBLIC_") for key in environment)

    core_hub_env = services["core-hub"]["environment"]
    assert core_hub_env["CORE_HUB_WRITE_TOKEN"] == "${CORE_HUB_WRITE_TOKEN}"
    assert environment["CORE_HUB_WRITE_TOKEN"] == "${CORE_HUB_WRITE_TOKEN}"

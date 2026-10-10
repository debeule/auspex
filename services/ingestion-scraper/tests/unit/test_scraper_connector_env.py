"""Every variable a connector reads from its context reaches the scraper container.

Connectors read credentials from `ctx.env`, which the scraper fills from its own environment, so a
variable compose does not pass is silently absent in the stack while unit tests still pass.
"""

import re
from pathlib import Path

import yaml

# tests/unit/ -> tests/ -> ingestion-scraper/ -> services/ -> auspex/
REPO_ROOT = Path(__file__).resolve().parents[4]
CONNECTORS = REPO_ROOT / "services" / "ingestion-scraper" / "src" / "auspex_ingest" / "connectors"
_CTX_ENV_READ = re.compile(r"""ctx\.env(?:\.get\(|\[)\s*["'](?P<var>[A-Z0-9_]+)["']""")


def _connector_env_vars() -> set[str]:
    return {
        match.group("var")
        for path in CONNECTORS.glob("*.py")
        for match in _CTX_ENV_READ.finditer(path.read_text(encoding="utf-8"))
    }


def test_connector_env_vars_are_found():
    assert {"NCBI_API_KEY", "EPO_OPS_KEY", "SEC_USER_AGENT"} <= _connector_env_vars()


def test_scraper_container_receives_every_connector_env_var():
    compose = yaml.safe_load(
        (REPO_ROOT / "docker" / "docker-compose.yml").read_text(encoding="utf-8")
    )
    environment = compose["services"]["ingestion-scraper"]["environment"]
    missing = {var for var in _connector_env_vars() if environment.get(var) != f"${{{var}}}"}
    assert not missing, f"Connector variables not passed to ingestion-scraper: {sorted(missing)}"

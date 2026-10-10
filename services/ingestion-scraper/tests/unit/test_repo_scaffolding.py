import re
from pathlib import Path

# tests/unit/ -> tests/ -> ingestion-scraper/ -> services/ -> auspex/
REPO_ROOT = Path(__file__).resolve().parents[4]

_CREDENTIAL_VARS = {
    "OPENAI_API_KEY",
    "EPO_OPS_KEY",
    "EPO_OPS_SECRET",
    "NCBI_API_KEY",
    "OPENFDA_API_KEY",
    "SEC_USER_AGENT",
    "POSTGRES_PASSWORD",
    "AIRFLOW_DB_PASSWORD",
    "NEO4J_PASSWORD",
    "MINIO_ACCESS_KEY",
    "MINIO_SECRET_KEY",
    "POSTGRES_MONITOR_PASSWORD",
    "SMTP_PASSWORD",
}

# A dotted topic name under the pre-rename prefix, e.g. `<prefix>.raw.ingested`. Built from parts so
# this file does not match itself; prose such as "...biotech." is not a topic name.
_LEGACY_TOPIC = re.compile(r"\b" + "biotech" + r"\.[a-z_]+\.[a-z_]+")


def _legacy_topic_names(content: str) -> list[str]:
    return _LEGACY_TOPIC.findall(content)


# Vars that are legitimately absent from .env.example because they are constructed
# dynamically in code (e.g. topic names derived from COMPOSE_PROJECT_NAME).
_DYNAMIC_LOOKUP_IGNORE = set()


def _parse_env_example() -> dict[str, str]:
    env_example = (REPO_ROOT / ".env.example").read_text()
    result: dict[str, str] = {}
    for line in env_example.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        var, _, value = line.partition("=")
        result[var.strip()] = value.strip()
    return result


def test_env_example_covers_all_referenced_vars():
    defined = set(_parse_env_example().keys())
    required = {
        "COMPOSE_PROJECT_NAME",
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "NEO4J_URI",
        "NEO4J_USER",
        "NEO4J_PASSWORD",
        "KAFKA_BOOTSTRAP_SERVERS",
        "MINIO_ENDPOINT",
        "MINIO_ACCESS_KEY",
        "MINIO_SECRET_KEY",
        "MINIO_BUCKET",
        "OPENAI_API_KEY",
        "EXTRACTION_MODEL",
        "EXTRACTION_API_KEY",
        "WATCHED_TICKERS",
        "EPO_OPS_KEY",
        "EPO_OPS_SECRET",
        "NCBI_API_KEY",
        "OPENFDA_API_KEY",
        "SEC_USER_AGENT",
        "TZ",
    } - _DYNAMIC_LOOKUP_IGNORE
    missing = required - defined
    assert not missing, f"Missing from .env.example: {sorted(missing)}"


def test_legacy_topic_name_is_detected():
    assert _legacy_topic_names("TOPIC = 'biotech" + ".signals.extracted'") == [
        "biotech" + ".signals.extracted"
    ]


def test_sentence_ending_in_biotech_is_not_a_legacy_topic():
    assert _legacy_topic_names("# assumed to carry over to biotech" + ".\n") == []


def test_no_legacy_topic_prefix_remains():
    code_suffixes = {
        ".py", ".java", ".yml", ".yaml", ".toml",
        ".properties", ".sh", ".kts", ".json",
    }
    special_names = {".env.example", ".gitignore"}
    violations: list[str] = []
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part.startswith(".git") for part in path.parts):
            continue
        if path.suffix.lower() not in code_suffixes and path.name not in special_names:
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
            if _legacy_topic_names(content):
                violations.append(str(path.relative_to(REPO_ROOT)))
        except OSError:
            pass
    assert not violations, f"Legacy topic prefix found in: {violations}"


def test_env_file_is_gitignored():
    gitignore = (REPO_ROOT / ".gitignore").read_text()
    patterns = {
        line.strip()
        for line in gitignore.splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    covered = ".env" in patterns or ".env*" in patterns
    assert covered, f".env not covered in .gitignore. Patterns found: {sorted(patterns)}"


def test_no_credential_has_a_source_default():
    vars_map = _parse_env_example()
    violations: list[str] = []
    for var in _CREDENTIAL_VARS:
        if var in vars_map and vars_map[var] != "":
            violations.append(f"{var}={vars_map[var]!r}")
    assert not violations, f"Credentials with non-empty defaults in .env.example: {violations}"


def test_airflow_metadata_is_a_separate_database() -> None:
    init_dir = Path(__file__).parents[4] / "docker" / "postgres-init"
    scripts = "\n".join(
        f.read_text()
        for f in sorted(init_dir.iterdir())
        if f.suffix in {".sh", ".sql"}
    )
    assert "CREATE DATABASE airflow" in scripts, "Airflow DB must be created as a separate database"
    assert "REVOKE ALL ON DATABASE airflow FROM PUBLIC" in scripts, "Airflow DB must be isolated from PUBLIC"


_COMPOSE_REFERENCE = re.compile(r"\$\{([A-Z0-9_]+)([^}]*)\}")


def _compose_references() -> list[tuple[str, str]]:
    compose = (REPO_ROOT / "docker" / "docker-compose.yml").read_text()
    return _COMPOSE_REFERENCE.findall(compose)


def test_compose_reads_env_example_variables_bare():
    defined = set(_parse_env_example())

    suffixed = sorted(
        f"{var}{suffix}" for var, suffix in _compose_references() if var in defined and suffix
    )

    assert suffixed == []

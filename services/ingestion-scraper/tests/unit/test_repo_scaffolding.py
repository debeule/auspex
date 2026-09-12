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
}

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
        "OPEN_AI_EXTRACTION_MODEL",
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


def test_no_legacy_topic_prefix_remains():
    # Split so the test file itself does not contain the literal string it searches for.
    legacy = "biotech" + "."
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
            if legacy in content:
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

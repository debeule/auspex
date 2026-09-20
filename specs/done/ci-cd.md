# CI/CD Pipeline

**Status:** done
**Blocked by:** —
**Branch:** `feature/ci-cd`

---

## Context

No CI exists. Tests run locally only. Two independent suites exist:

- **Java** (`services/core-hub`): `./gradlew check` runs unit tests (30), integration tests (55), ArchUnit rules, and timezone check. Requires Docker (Testcontainers starts Postgres, Neo4j, Kafka containers).
- **Python** (`services/ingestion-scraper`): `uv run pytest -q` runs unit and integration tests. Integration tests require Docker (Testcontainers for Kafka/Postgres/MinIO).

There is also a contract fixture check: `uv run pytest tests/unit/test_contract_fixture.py` must leave the git tree clean (the fixture is generated, not hand-written).

Runner decision: **GitHub-hosted** (`ubuntu-latest`). Docker is pre-installed and Docker-in-socket mode works with Testcontainers without any additional configuration. The Java integration suite runs in ~48 seconds; the Python suite runs in under 2 minutes. Both are well inside GitHub-hosted runner timeouts (6 hours per job).

## What this builds

Two GitHub Actions workflow files in `.github/workflows/`:

**`java.yml`** — triggered on push and PR to `main`, `develop`, and `feature/**`:
- Steps: checkout, Java 25 (Temurin), Gradle wrapper cache, `./gradlew check timezoneCheck --rerun-tasks`.
- Fails the job if Gradle reports zero tests on the `test` or `integrationTest` tasks (enforced via `failOnNoDiscoveredTests = true` already in the build).
- Publishes test results (JUnit XML from `build/reports/tests/`) as a workflow artifact.

**`python.yml`** — triggered on push and PR to `main`, `develop`, and `feature/**`:
- Steps: checkout, Python 3.14 (via `actions/setup-python`), uv install, `uv sync --all-extras`, `uv run ruff check .`, `uv run mypy src`, `uv run pytest -q`, contract fixture drift check.
- Contract fixture drift check: `cd services/ingestion-scraper && uv run pytest tests/unit/test_contract_fixture.py -q` then `git diff --exit-code services/core-hub/src/test/resources/contract/`. Fails the job if the tree is dirty.

## Out of scope

Deployment pipelines. Container image building and publishing. Release automation. Dependabot or automated dependency updates. PR auto-labelling.

## Constraints

- The Java job must actually start Docker containers — Testcontainers must not silently skip when Docker is unavailable. `failOnNoDiscoveredTests = true` already catches zero-test runs; the integration test count must be verified against the last known count (55) in the job summary. If Testcontainers cannot reach Docker, the job fails rather than silently passing.
- `--rerun-tasks` is required on both `check` and `integrationTest` to defeat Gradle's `UP-TO-DATE` caching in CI (where inputs don't change between CI-triggered runs on the same commit). Without it, the first CI run passes and subsequent runs report `UP-TO-DATE` — indistinguishable from success.
- Secrets: `DISCORD_WEBHOOK_URL` is not required in CI. Any env vars needed for integration tests that hit real APIs are mocked in the test suite; the CI job does not need external API credentials.

## Required verifications

These are confirmed by the first successful CI run on a real PR, not by unit tests:

- `verify_testcontainers_integration_suite_actually_ran` — the Java job's test report shows 55 integration tests executed (not 0 and not `UP-TO-DATE`).
- `verify_no_test_is_silently_skipped` — the `--rerun-tasks` flag in both Java and Python jobs prevents silent cache hits. Gradle's `failOnNoDiscoveredTests = true` fires if the test task has no tests to run.
- `verify_contract_fixture_is_current` — `git diff --exit-code` after regenerating the fixture exits 0 on a clean branch, nonzero on a branch with an unsynced Pydantic model change.

**Broken-PR verification (required before the spec is closed as done):** After the workflow is created and the first PR goes green, push a PR with a deliberately failing test, confirm the CI job goes red, then revert and confirm it goes green. Record the result in `DECISIONS.md`. This is a 15-minute manual verification.

## Definition of done

```bash
git push origin feature/ci-cd
# then: open a PR and confirm both GitHub Actions checks pass
```

Specific criteria:
1. Both `java` and `python` checks appear on the PR and both go green.
2. The Java job's test summary shows 30 unit tests + 55 integration tests executed (not `UP-TO-DATE`).
3. The contract fixture drift check exits 0 on the clean branch.
4. The broken-PR verification has been completed and logged in `DECISIONS.md`.

## Notes

- Gradle Testcontainers on GitHub-hosted runners: the `TESTCONTAINERS_RYUK_DISABLED=true` environment variable may be needed if Ryuk (the resource reaper) fails to start. Set it in the workflow env if the first run times out during container startup.
- Python 3.14 must be installed explicitly; `actions/setup-python` with `python-version: '3.14'` is required since 3.14 is not pre-installed on `ubuntu-latest`.
- Gradle wrapper cache key: cache on `gradle/wrapper/gradle-wrapper.properties` and `gradle/libs.versions.toml`. Include `~/.gradle/caches` and `~/.gradle/wrapper` in the cache paths.
- uv cache: cache on `services/ingestion-scraper/uv.lock` and `services/backtesting/uv.lock`. uv's cache directory is `~/.cache/uv`.
- The workflow trigger should also run on changes to `.github/workflows/**` itself to catch broken YAML on edit.

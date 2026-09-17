# CI/CD Pipeline

**Status:** draft
**Blocked by:** 👤 broken-PR verification — see `docs/PREREQUISITES.md`
**Branch:** `feature/ci-cd`

---

## Context

No CI exists. All tests run locally. This spec adds GitHub Actions.

## What this builds

GitHub Actions workflows running on every PR:
- Python: ruff, mypy, unit suite, integration suite (with Docker)
- Java: `./gradlew check timezoneCheck` (unit + integration + ArchUnit)
- Contract fixture drift check: tree must be clean after `pytest tests/unit/test_contract_fixture.py`

## Out of scope

Deployment, release automation, container image publishing.

## Constraints

- The Java job must actually start Docker containers — not silently skip Testcontainers when Docker is unavailable. Assert the container suite ran.
- No test may be silently skipped.

## Required tests

- `test_pipeline_runs_testcontainers_suite` — Java job starts containers, not skips
- `test_no_test_is_skipped_silently`
- `test_contract_fixture_is_current` — tree is clean after pytest

## Definition of done

All checks pass on a real pull request. The broken-PR verification has been done once by hand: push a deliberately failing test, confirm CI goes red, revert. Record in `DECISIONS.md`.

## Notes

Needs scoping before `ready`: self-hosted runner or GitHub-hosted? GitHub-hosted runners have Docker available but Testcontainers with Neo4j may time out on free-tier runners. Decide before writing the workflow.

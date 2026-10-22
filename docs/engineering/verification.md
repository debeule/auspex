# Verification

Domain: ENG · Code: `.github/workflows/`, `services/core-hub/build.gradle.kts`, `services/*/pyproject.toml`, `tools/docs_check/` · Last reviewed against: develop @ `b7582c3`

## Scope

How a change is proven: the test strategy, the settings of the test infrastructure, the merge bar, the mutation check and what CI proves.

Not here:
- the agent-session hard rules (a run that executes no test, cached Gradle outcomes, where work can run, the rule that matters most): root `AGENTS.md`;
- test-first itself: [INV-15](../system/invariants.md#INV-15); the scaffolding exception to it (build files, compose files and directory trees need no prior test) is written there, as an exception under that invariant;
- the generated contract fixture and its CI diff: [contracts](../system/contracts.md);
- the ArchUnit rules: INV-12 in [invariants](../system/invariants.md);
- the named guards of requirements §13: each in its owner domain's doc;
- test file layout and test commands: each service's `AGENTS.md`;
- how a change moves from spec to merge: [change workflow](change-workflow.md); how docs, names and comments are written: [conventions](conventions.md).

## Requirements

- <a id="ENG-001"></a>**ENG-001** — Each new test is first seen failing for the right reason: in Python an `ImportError`, `AttributeError` or `AssertionError`, never a collection or syntax error; in Java a compile error on a missing class is accepted and an assertion failure preferred. The red output is recorded in the PR description.
- <a id="ENG-002"></a>**ENG-002** — A red-green cycle runs the spec's tests and then the service's unit suite. Container-backed suites run at spec completion; where they cannot run locally, CI proves them (where work runs: root `AGENTS.md`).
- <a id="ENG-003"></a>**ENG-003** — Every pytest configuration uses `--strict-markers` and registers each marker it uses; every Gradle `Test` task sets `failOnNoDiscoveredTests = true`; CI runs Gradle with `--rerun-tasks`.
- <a id="ENG-004"></a>**ENG-004** — Python unit suites cannot open network sockets (pytest-socket).
- <a id="ENG-005"></a>**ENG-005** — Source APIs are stubbed against saved fixtures (respx); the LLM client and the other clients a component uses are injected and stubbed; time is injected (a `now()` provider in Python, `java.time.Clock` in Java); waits use Awaitility, never `Thread.sleep`.
- <a id="ENG-006"></a>**ENG-006** — Tests at a store boundary use Testcontainers, never a hand-started stack. core-hub's containers are static singletons started once per JVM, with one Spring context, no `@DirtiesContext`, and truncation instead of restarts.
- <a id="ENG-007"></a>**ENG-007** — core-hub's container-backed tests live in the `integrationTest` source set and task; the JVM-default-timezone test runs in the separate `timezoneCheck` task with `-Duser.timezone` set on the forked JVM, never by changing the default mid-suite.
- <a id="ENG-008"></a>**ENG-008** — core-hub plain unit tests (no Spring context) cover the DTO and JSON contract, validation, error classification, serialization and scoring functions.
- <a id="ENG-009"></a>**ENG-009** — `verify_pipeline.sh` is a smoke test and never the correctness authority.
- <a id="ENG-010"></a>**ENG-010** — Merge bar: every behaviour a change adds or alters has a test, and in a spec PR every requirement the spec's Docs impact adds or changes maps to a named test in the owner doc's verification table.
- <a id="ENG-011"></a>**ENG-011** — Mutation check: each behaviour is broken on purpose locally (flip a condition, drop a field, skip a write), a test goes red, and the break is reverted. A mutant does not get a branch of its own; a break that only CI can show goes onto the PR branch as one commit and is reverted by the next. The PR description lists what was mutation-checked and what only CI ran.
- <a id="ENG-012"></a>**ENG-012** — Docs are not proof: `tested` means a named test exists; only CI shows it passes; only a mutation check shows it can fail. Reviews cite code or execution, never a doc, as evidence of compliance.
- <a id="ENG-013"></a>**ENG-013** — Container-backed suites, the contract-fixture drift check and the docs checker run on GitHub-hosted runners (each workflow's `runs-on` names the image).
- <a id="ENG-014"></a>**ENG-014** — CI test images are named as on Docker Hub, and every container-test job sets `TESTCONTAINERS_HUB_IMAGE_NAME_PREFIX` so they are pulled through the mirror; no test image depends on anonymous Docker Hub.
- <a id="ENG-015"></a>**ENG-015** — The `Docs` workflow runs the checker's own tests (failing when none runs) and `python3 -m tools.docs_check` on every PR into `develop` (with the PR body and `--base`) and on every push to `develop`.

## Machine-readable authorities

| File | Governs | Notes |
|---|---|---|
| `.github/workflows/java.yml`, `.github/workflows/python.yml`, `.github/workflows/dashboard.yml` | What CI runs per service, runner image, Testcontainers prefix | ENG-003, ENG-013, ENG-014 describe them; values are not copied here |
| `.github/workflows/docs.yml` | The docs checker job | ENG-015 |
| `services/core-hub/build.gradle.kts` | `Test` tasks, the `integrationTest` suite, `timezoneCheck` | ENG-003, ENG-007 |
| `services/*/pyproject.toml` | pytest `addopts` and registered markers | ENG-003, ENG-004 |

## Verification

| ID | Source | Verified by | Status |
|---|---|---|---|
| ENG-001 | `## 2026-10-22 — Living docs — PENDING — engineering ratification batch` [`CLAUDE.md`] | — | pending-decision |
| ENG-002 | `## 2026-10-22 — Living docs — PENDING — engineering ratification batch` [`CLAUDE.md`] | — | pending-decision |
| ENG-003 | `## 2026-10-22 — Living docs — PENDING — engineering ratification batch` [`CLAUDE.md`; requirements §13] | `services/core-hub/build.gradle.kts`, `services/*/pyproject.toml`, `.github/workflows/java.yml` (configuration, no test) | pending-decision |
| ENG-004 | requirements §13 [`services/ingestion-scraper/CLAUDE.md`] | backtesting and strategy `addopts`; backup `services/backup/tests/unit/conftest.py`; ingestion-scraper has no socket guard (defect H3) | divergent, citing `## 2026-10-15 — Living docs — PENDING — defects found while scoping` and `## 2026-10-17 — Living docs — CHOICE — defects found while scoping` |
| ENG-005 | requirements §13 [`services/ingestion-scraper/CLAUDE.md`; `services/core-hub/CLAUDE.md`] | — | untested |
| ENG-006 | requirements §13, §14, §1 [`services/ingestion-scraper/CLAUDE.md`; `services/core-hub/CLAUDE.md`] | — | untested |
| ENG-007 | requirements §13 [`services/core-hub/CLAUDE.md`] | `services/core-hub/src/integrationTest/java/dev/auspex/corehub/SignalTimezoneIT.java::test_non_utc_default_timezone_does_not_alter_stored_values` | tested |
| ENG-008 | requirements §13 | `services/core-hub/src/test/java/dev/auspex/corehub/model/ResearchSignalEventTest.java::test_signal_event_json_contract_matches_generated_python_fixture` | tested |
| ENG-009 | requirements §13 | — | untested |
| ENG-010 | `## 2026-10-09 — Guideline setup — CHOICE — merge flow, merge bar and shared-log conflicts written into the repo` [`CLAUDE.md`] | — | untested |
| ENG-011 | `## 2026-10-09 — Guideline setup — CHOICE — merge flow, merge bar and shared-log conflicts written into the repo` [`CLAUDE.md`] | — | untested |
| ENG-012 | `## 2026-10-22 — Living docs — PENDING — engineering ratification batch` [design §9.1–§9.2] | check K | pending-decision |
| ENG-013 | `## 2026-09-19 — CI/CD pipeline — CHOICE — GitHub-hosted runners` | `runs-on` in `.github/workflows/*.yml` | enforced |
| ENG-014 | `## 2026-10-09 — CI — CHOICE — one prefix for every test image` (the two earlier CI image choices in Rationale) | job `env` in `.github/workflows/python.yml` and `.github/workflows/java.yml` | enforced |
| ENG-015 | `## 2026-10-22 — Living docs — PENDING — engineering ratification batch` [`.github/workflows/docs.yml`] | `.github/workflows/docs.yml` | pending-decision |

"design §n" is a section of `specs/living-docs-cutover-design.md`. A bracketed Source part is where the text came from; the part before it is the approval.

## Known traps

- Docker Hub rate-limits anonymous pulls per IP and CI runners share IPs. Test images are named as on Docker Hub and pulled through the Testcontainers prefix (ENG-014); a daemon registry-mirror entry alone was not enough, and pulls still reached Docker Hub and failed. The compose half (publisher registries) belongs to operations. (from `CLAUDE.md`, Known traps; `## 2026-10-09 — CI — CHOICE — one prefix for every test image`)
- LocalStack calendar-versioned tags need a licence token and exit with code 55 without one; integration tests stay on the pinned pre-calendar LocalStack tag named in `VERSIONS.md`. (from `CLAUDE.md`, Known traps)

## Rationale

- A green suite is necessary, not sufficient: an earlier plan listed a test that could only pass by putting the whole pipeline inside every connector, and test-first would have built that architecture faithfully. The rule that follows from it is root `AGENTS.md`'s. (from `CLAUDE.md`, "The rule that matters most")
- Testcontainers over mocks at the store boundary is a settled choice (requirements §14): a mock of a store tests the mock.
- ENG-014 replaced two earlier CI image fixes, `## 2026-10-09 — CI — CHOICE — container images off anonymous Docker Hub` and `## 2026-10-09 — CI — CHOICE — remaining test images through mirror.gcr.io`, which named mirrored images per test.

## Retired requirements

None.

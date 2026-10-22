# Living docs: engineering workflow

**Status:** done
**Blocked by:** `docs-check-tooling` (merged into `feature/living-docs-integration`). Decisions: `## 2026-10-15 — Living docs — PENDING — rollout branch model`, `## 2026-10-15 — Living docs — PENDING — agent instruction files`, `## 2026-10-15 — Living docs — PENDING — docs impact field and Docs unchanged line`, `## 2026-10-15 — Living docs — PENDING — archive policy for specs/done`. Only the first blocks the start; the others are written as their recommended defaults with status `pending-decision`.
**Branch:** `feature/living-docs-engineering-workflow` (PR into `feature/living-docs-integration`)
**Docs impact:** creates `docs/engineering/verification.md`, `docs/engineering/change-workflow.md` and `docs/engineering/conventions.md` (namespace ENG, all new IDs). Changes `specs/README.md`, `specs/_template.md`, `docs-check.toml` (only the `[rollout] planned_domains` line: `engineering` leaves it), `DECISIONS.md` (one appended entry), `TODO.md` (this spec's own row) and `specs/living-docs-cutover-matrix.md` (ENG cells only). Creates `.github/pull_request_template.md`. Root `CLAUDE.md` is not edited here; `agent-instruction-hierarchy` replaces it.

---

## Context

At `develop` @ `e51f74201fda30dd9a28af318cc74b824e39dafc` (2026-10-15) the engineering process lives in these places, none of them in `docs/`:

- **Root `CLAUDE.md`** (246 lines, auto-loaded): "Session start" (`:38-44`), "The rule that matters most" (`:49-52`), "Commands" (`:71-101`, including the zero-tests and `UP-TO-DATE` rules at `:99-101`), "The TDD loop" (`:103-114`), "Documentation maintenance" (`:116-137`, whose table says "intentional duplication is fine", the rule that generated most doc drift), "Code comments" (`:139-145`), "Test file conventions" (`:147-154`), "Git" (`:156-195`: Git Flow, rebase and fast-forward, the end-of-spec flow, "Ready to merge" with the mutation check, shared log files, commit identity, no Claude footers, commit subject style), "Where work can run" (`:197-200`), "File map" (`:228-243`), "Tone" (`:245-246`).
- **`docs/requirements.md` §13** (`:394-406`): test-first, pytest with `--disable-socket`, respx fixtures, injected clocks, Testcontainers, core-hub container singletons, the `timezoneCheck` task, ArchUnit, the generated contract fixture (misnamed `research_signal_event.json` at `:402`; the real file is `services/core-hub/src/test/resources/contract/signal_event_v1.json`), the named guards, `verify_pipeline.sh` as smoke only. §14 (`:410-412`) lists settled choices, including Testcontainers over mocks and TDD.
- **`specs/README.md`**: required fields (`Status`, `Blocked by`, `Branch`, `Context`, `What this builds`, `Out of scope`, `Constraints`, `Required tests`, `Definition of done`), test naming rules, statuses `draft · ready · blocked · done`. It does not define `hold`, although four specs live in `specs/hold/` with `hold` rows in `TODO.md`. **`specs/_template.md`** mirrors the fields.
- **`.github/`**: `workflows/{commit-identity,java,python,dashboard}.yml` and `scripts/check_commit_identity.sh`. No PR template.
- **`DECISIONS.md`**: the PENDING entries of this rollout, including `## 2026-10-15 — Living docs — PENDING — defects found while scoping`, which lists the defects this scoping found (among them the ingestion socket gap, the missing `--locked`, the unwritten pin-age practice and the session-log conflict below); and process choices, notably `## 2026-10-09 — Guideline setup — CHOICE — merge flow, merge bar and shared-log conflicts written into the repo` (`:819`), which records owner approval of the merge flow, the merge bar, the cloud-session limits and the `union` driver, and says the `TODO.md` session log "is dropped". The session log is still in `TODO.md` and still appended (latest row 2026-10-15).
- **Code facts the ENG docs will describe** (each cited, not trusted from docs):
  - `services/core-hub/build.gradle.kts:95,101-102` set `failOnNoDiscoveredTests = true` on `timezoneCheck` and on every `Test` task; `java.yml:61` runs `./gradlew check timezoneCheck --rerun-tasks`.
  - All four `services/*/pyproject.toml` set `--strict-markers` and register only `integration`. `--disable-socket` is in `addopts` for backtesting and strategy only; backup disables sockets in `tests/unit/conftest.py:8-13`; ingestion-scraper has neither (one test carries `@pytest.mark.disable_socket`, `tests/unit/test_ingestion_pipeline.py:347`).
  - No test uses `pytest.mark.unit` (`grep -rn 'mark\.unit' services` → 0), although `CLAUDE.md:149` says it is the default.
  - `python.yml:85-90` regenerates the signal fixture and fails on `git diff --exit-code services/core-hub/src/test/resources/contract/`.
  - `.gitattributes` sets `merge=union` for `DECISIONS.md` and `TODO.md`.

`docs-check-tooling` (merged first) provides `python3 -m tools.docs_check`: checks A–L, `--next NS`, `--paths`, `--owners`, check M (`--domain`, `--decisions --domain`), and `docs-check.toml` with the `engineering` domain (owners: the three files this spec writes) still listed in `[rollout] planned_domains`. While a domain is listed, links to its missing docs, references to its not-yet-defined IDs and its `NS-?` placeholders are stderr notices, not findings.

The living-doc format this spec writes, in short (a cold session needs nothing else):
- Header line: `Domain: ENG · Code: <paths> · Last reviewed against: develop @ <sha>` with a SHA on `develop` (check E checks it is an ancestor of HEAD).
- H2s `Scope`, `Requirements`, `Machine-readable authorities` (optional), `Verification`, `Known traps` (optional), `Rationale` (optional), `Retired requirements`.
- A requirement is a list item `- <a id="ENG-NNN"></a>**ENG-NNN** — <one testable statement, present tense>`.
- The verification table has columns `ID | Source | Verified by | Status`; status is `tested`, `enforced`, `untested`, `divergent` or `pending-decision`.
- `Source` names the approval (a requirements §, a `CHOICE` heading, an archived spec, an invariant, or the ratification batch) **and** the original location exactly as the migration matrix row's Source cell gives it (its decision heading, else its `§`, else its file path). Check M compares the two.
- Decisions are cited by `DECISIONS.md` heading in backticks; register numbers never appear in the repo outside the migration matrix.

## What this builds

### Ownership split (respected throughout)

| Rule set | Owner after this rollout | This spec |
|---|---|---|
| Agent-session hard rules: zero-tests and `UP-TO-DATE` rules, never push `develop`/`main`, merge only on the owner's word, commit identity and no trailers or footers, commit-subject style, where work can run, stop-and-flag, the rule that matters most, session start, tone, file map | root `AGENTS.md` (`agent-instruction-hierarchy`) | **No ENG ID.** ENG docs name root `AGENTS.md` in backticks (no Markdown link, so nothing dangles before that spec merges) and never restate these |
| Test-first itself, and its scaffolding exception | INV-15 (`living-docs-system-and-contracts`, which writes the exception only under INV-15) | cited and linked, not restated |
| Per-stack comment form (Javadoc, docstrings, TSDoc) | ENG conventions item 52 | **written here**; `services/AGENTS.md` carries only a pointer to it |
| Engineering process detail | `docs/engineering/*` | **written here** |
| Service commands and test layout | each service `AGENTS.md` | linked |
| Stack-level commands | root `README.md` | linked |

### `docs/engineering/verification.md`

Scope: how a change is proven: test strategy, test infrastructure settings, the merge bar, the mutation check, what CI proves. Requirements, in this order (numbers come from `python3 -m tools.docs_check --next ENG` as they are written, so this list is ENG-001 onward):

1. Each new test is first seen failing for the right reason: in Python an `ImportError`, `AttributeError` or `AssertionError`, never a collection or syntax error; in Java a compile error on a missing class is accepted and an assertion failure preferred. The red output is recorded in the PR description.
2. A red-green cycle runs the spec's tests and then the service's unit suite; container-backed suites run at spec completion, and in cloud sessions they are proven in CI (where work runs: root `AGENTS.md`).
3. Every pytest configuration uses `--strict-markers` and registers each marker it uses; every Gradle `Test` task sets `failOnNoDiscoveredTests = true`; CI runs Gradle with `--rerun-tasks`.
4. Python unit suites cannot open network sockets (pytest-socket).
5. Source APIs are stubbed against saved fixtures (respx); the LLM client is injected and stubbed; time is injected (a `now()` provider in Python, `java.time.Clock` in Java); waits use Awaitility, never `Thread.sleep`.
6. Tests at a store boundary use Testcontainers, never a hand-started compose stack. core-hub's containers are static singletons started once per JVM, with one Spring context, no `@DirtiesContext`, and truncation instead of restarts.
7. core-hub's container-backed tests live in the `integrationTest` source set and task; the JVM-default-timezone test runs in the separate `timezoneCheck` task with `-Duser.timezone` set on the forked JVM, never by changing the default mid-suite.
8. core-hub plain unit tests (no Spring context) cover the DTO and JSON contract, validation, error classification, serialization and scoring functions.
9. `verify_pipeline.sh` is a smoke test and never the correctness authority.
10. Merge bar: every behaviour a change adds or alters has a test, and in a spec PR every requirement the spec's Docs impact adds or changes maps to a named test in the owner doc's verification table.
11. Mutation check: each behaviour is broken on purpose locally (flip a condition, drop a field, skip a write), a test goes red, and the break is reverted. A mutant is never pushed as its own branch; a break that only CI can show is pushed as one commit on the PR branch and reverted in the next. The PR description lists what was mutation-checked and what only CI ran.
12. Docs are not proof: `tested` means a named test exists; only CI shows it passes; only a mutation check shows it can fail. Reviews cite code or execution, never a doc, as evidence of compliance.
13. Container-backed suites, the contract-fixture drift check and the docs checker run on GitHub-hosted `ubuntu-latest` runners.
14. CI test images are named as on Docker Hub, and every container-test job sets `TESTCONTAINERS_HUB_IMAGE_NAME_PREFIX` so they are pulled through the mirror; no test image depends on anonymous Docker Hub.
15. The `Docs` workflow runs the checker's own tests (a run of zero tests fails) and `python3 -m tools.docs_check` on every PR into `develop` (with the PR body and `--base`) and every push to `develop`.

Links only, no ENG ID: the rule that matters most and the zero-tests and `UP-TO-DATE` rules (root `AGENTS.md`); test-first (INV-15); the scaffolding exception to test-first (creating build files, compose files, directory trees and `.env.example` needs no prior test), linked as `[INV-15](../system/invariants.md#INV-15)` with one sentence naming it, never restated; the generated contract fixture and its CI diff (CON, `docs/system/contracts.md`); ArchUnit (INV-12); the named guards of requirements §13 (each in its owner domain); test file layout and commands (service `AGENTS.md`).

### `docs/engineering/change-workflow.md`

Scope: the life of a change from spec to archive, docs impact, IDs, conflicts, decisions, handoff, branching and merging.

16. Spec statuses are `draft`, `ready`, `blocked`, `hold` and `done`. A `hold` spec is parked by an owner decision and lives in `specs/hold/`; a `done` spec moves to `specs/done/`, and its `TODO.md` row points there, in the same PR as the work.
17. A spec is self-contained (a cold session with the spec and root `AGENTS.md` can start), scoped to one deliverable, named after what it does, and reaches `ready` only with every field `docs-check.toml` `[specs]` requires (meanings in `specs/README.md`). Scoping fills in the tests and the definition of done, never the implementation.
18. Every active and hold spec has a **Docs impact** field listing the IDs it adds (as `NS-new`), changes or retires, or `none — <reason>`.
19. For every domain a PR's net diff touches (`docs-check.toml` `[ownership]`, one or more domains per path), an owner doc of that domain changes, or the PR body has `Docs unchanged: <domain> — <reason>`. Adding a `CHOICE` heading to `DECISIONS.md` touches the domain `decisions`.
20. A behaviour change edits its owner doc in the same PR: new IDs come from `--next`, rewording that keeps the meaning keeps the ID, a change of meaning retires the ID and adds a new one, and verification rows are updated.
21. IDs: format `NS-NNN` in the namespaces of `docs-check.toml`; invariants keep root-`CLAUDE.md` numbering and are the only IDs amended in place (amendment line, exceptions listed under the invariant); every ID is defined once and never reused; a retired ID moves to `Retired requirements` with date, the retiring spec or decision, the replacement or `none`, and the original text; adding a namespace changes `docs-check.toml` and `docs/README.md` in one PR.
22. When two PRs allocate the same new ID, the later one renumbers its new IDs, including in its spec and PR body.
23. Conflict precedence, highest first: locked machine authorities; other machine authorities for values; `docs/` for approved behaviour; an active spec for its own work only; `DECISIONS.md`; agent files and READMEs; `specs/done/`, `docs/HISTORY.md` and `TODO.md` notes, which are never consulted for current rules.
24. When code and `docs/` disagree, the finder sets the requirement's status to `divergent` and appends a `FLAG` entry; the owner decides to fix the code (a spec) or ratify it (a doc edit citing the decision). A doc is never edited to match code without that decision.
25. A behaviour-changing `CHOICE` lands in the same PR as its doc edit; a decision not absorbed into `docs/` never outranks it.
26. Decisions are cited by their `DECISIONS.md` heading in backticks (double backticks when the heading itself contains one). The owner's working register numbers never appear in `docs/`, specs, READMEs or agent files.
27. A requirement converted from older text carries a `Source`: in priority order a requirements §, a `CHOICE` heading, an archived spec, an invariant, or an owner ratification. One whose only source is code, a README, a `CLAUDE.md` trap or a config comment is `pending-decision` and listed in its domain's ratification batch until the owner approves it; a source that contradicts the code is written as approved with status `divergent`.
28. A session that stops before its spec is done adds a `## Handoff` section to the spec with the lines `Written against: develop @ <sha>` (plus branch and commits ahead), `Done`, `Not done`, `Next`, `Docs`, `Open decisions`, `Verify`. The next session re-reads whatever changed on `develop` since that SHA before relying on it.
29. Branches: `main` (releases only), `develop` (integration), one `feature/<name>` per spec from `develop` as named in its Branch field, `release/<version>` from `develop` into `main` and `develop`, `hotfix/<name>` from `main` into both.
30. Merge recipe, once the owner says merge: rebase onto `origin/develop` (conflicts resolved in the rebase), run `python3 -m tools.docs_check --base origin/develop`, push with `--force-with-lease`, wait for CI on the rebased head, then fast-forward `develop` locally and push. GitHub's merge button is not used (it records the GitHub account as committer), and `--no-ff` only by explicit agreement.
31. `main` changes only through a `release/<version>` branch, when the owner asks for a release.
32. `DECISIONS.md` and `TODO.md` use git's `union` merge driver; after a rebase their entries read in order with no duplicated line.
33. `DECISIONS.md` is append-only, in the heading format stated at its top; a `BLOCKED` entry stops the work until the owner answers.
34. `TODO.md` is the spec index (one row per spec, status equal to the spec's, link to its current directory) and a one-line-per-session log; its notes carry status, never rules.
35. A commit is made only when the spec's tests pass; secrets, build outputs, virtualenvs, caches and volumes are never committed (`.gitignore` lists them).
36. A spec under `specs/done/` is not edited after archiving; corrections go to `docs/` or `DECISIONS.md`.
37. The PR body follows `.github/pull_request_template.md`: Docs impact or `Docs unchanged:` lines, whether the touched requirements were read against the code, divergences with their decision heading, tests mapped to IDs, red output, mutation checks, CI-only runs, and the semantic review.
38. A reviewer who did not write the change checks that each `Docs unchanged:` line is true, that doc edits state approved behaviour, that tests assert behaviour, and that requirements sit with their owner; the result is recorded in the PR body.
39. `Last reviewed against` names a `develop` commit and is changed only by someone who re-read the doc against the code at that commit.

Links only: never push `develop`/`main`, merge only on the owner's word, identity and trailers, footers, commit-subject style (root `AGENTS.md`; enforced by `commit-identity.yml`); a `DECISIONS.md` entry cannot narrow an invariant (`docs/system/invariants.md`).

### `docs/engineering/conventions.md`

Scope: where each kind of content lives, how requirements and living docs are written, code comments, names, logging set-up and version pins.

40. Each fact has one owner: a requirement lives in exactly one `docs/` file and is cited elsewhere by ID; READMEs, runbooks and agent files hold no requirement text and link to the owner; machine-readable files own their values, and docs name the file and explain the meaning without copying values.
41. Content goes by kind: living docs hold approved behaviour; change specs hold proposed work; runbooks hold ordered operator steps with checks; READMEs hold orientation, layout and tables; `DECISIONS.md` holds why and who decided; agent files hold workflow and routing.
42. A requirement is one testable statement in the present tense; living docs hold no plan steps, change narration, future work or copied machine values.
43. A code comment tells the reader what the code cannot (intent, a constraint, a non-obvious why, units, an invariant) and makes sense to someone who never saw the plan or the session.
44. A comment never restates the code or narrates a change, and holds no plan steps or spec names, project history, version re-verifications, or machine specs and targets; decisions go to `DECISIONS.md`, setup to `docs/`, what changed to the PR description.
45. Doc comments are written for contracts (public extension points and anything a caller can get wrong), not for everything; a docstring that only repeats the name is deleted.
46. A behaviour change fixes or deletes the comments that describe the old behaviour in the same commit.
47. A test name is a falsifiable claim about behaviour (`test_backfill_does_not_advance_the_live_cursor`, not `test_backfill_works`).
48. `VERSIONS.md` is the single list of pinned versions, with no floating tags, `latest` or `>=`; an item marked *resolve at install* is pinned to an exact version when first installed and written back; each service's lock file is authoritative for its resolved dependencies; a version-sensitive claim is re-verified when code that depends on it is touched, with the outcome in `DECISIONS.md`.

49. No name carries a plan step: file, function, test, variable and branch names (beyond the rollout's own branch) and commit messages describe what the thing does (`corroboration_review`, `test_biorxiv_payload_maps_to_rawdocument`), never `step_3_2`, `phase_2` or a spec number.
50. A living doc under `docs/` starts with `Domain: <NS> · Code: <paths> · Last reviewed against: develop @ <sha>`, has the H2s `Scope`, `Requirements`, `Verification` and `Retired requirements` (and optionally `Machine-readable authorities`, `Known traps`, `Rationale`), defines each requirement as a list item `<a id="NS-NNN"></a>**NS-NNN** — <statement>`, and keeps one verification row per active ID with columns `ID | Source | Verified by | Status` and the statuses `tested` (a named `path::name` test), `enforced` (a named machine check), `untested`, `divergent` (cites a decision) and `pending-decision` (cites a PENDING heading).
51. A Python service configures logging once, at app creation (`configure_logging()` called in `create_app()`), never per module. The log fields and what logs may contain are owned by operations (`docs/operations/observability.md`).
52. Comment form per stack: Java (core-hub) uses Javadoc `/** */` on types and on public or package-level methods whose contract is not obvious, `//` for a local why, and no `@param`/`@return` tags that only repeat names and types; Python (ingestion-scraper, backtesting, strategy, backup) uses PEP 257 docstrings in prose with backticked names, `#` for a local why, and a module or script note in the module docstring rather than in `#` lines at the top; TypeScript (dashboard) uses TSDoc `/** */` on exported components, hooks and API helpers whose behaviour is not obvious from props and types, with no JSDoc type annotations.

Links only: `services/AGENTS.md` points to item 52 and does not restate it; Flyway files frozen (HUB, `docs/core-hub/storage.md`); the project naming table (SYS, `docs/system/overview.md`); log content and fields (OPS, `docs/operations/observability.md`).

### Known traps (planned)

Traps carry no IDs; each is a list item under the H2 `## Known traps` of its ENG doc, ending with where it came from, so check M can match the matrix row (its `ID` cell is the anchor, e.g. `docs/engineering/verification.md#known-traps`).

- `docs/engineering/verification.md` `## Known traps`:
  - Docker Hub rate-limits anonymous pulls per IP and CI runners share IPs; test images are named as on Docker Hub and pulled through the prefix (item 14), and a daemon mirror entry alone was not enough. (from `CLAUDE.md`, Known traps; `` `## 2026-10-09 — CI — CHOICE — one prefix for every test image` ``). The compose half (publisher registries) is operations'.
  - LocalStack calendar-versioned tags need a licence token and exit with code 55 without one; integration tests stay on the pinned pre-calendar tag named in `VERSIONS.md`. (from `CLAUDE.md`, Known traps)
- `docs/engineering/conventions.md` `## Known traps`:
  - Gradle 9 prefers the configuration cache; a build script it disallows fails at configuration time with an error that reads nothing like a test failure. Fix the script; never disable the cache. (from `services/core-hub/CLAUDE.md`, Traps)
  - Spring Boot 4.1, Spring Framework 7 and Spring Kafka 4.1 differ from the 3.x behaviour most examples show; where they disagree, the 4.x reference documentation wins. (from `services/core-hub/CLAUDE.md`, Traps)

No version numbers are copied into these items; `VERSIONS.md` owns them.

### Verification tables (planned rows)

Every `Source` cell also carries the original location from the matrix row (shown in brackets below). Citations in these cells are always in backticks (check K), double backticks for a heading that contains backticks. "engineering ratification batch" below stands for the full citation `` `## <date> — Living docs — PENDING — engineering ratification batch` `` with the date the entry is appended, e.g. `` `## 2026-10-20 — Living docs — PENDING — engineering ratification batch`; `CLAUDE.md:105-109` ``. The decision headings shown below are written in backticks the same way.

| Items | Source | Verified by | Status |
|---|---|---|---|
| 1, 2 | engineering ratification batch [`CLAUDE.md`] | — | pending-decision |
| 3 | engineering ratification batch [`CLAUDE.md`; requirements §13] | `services/core-hub/build.gradle.kts`, `services/*/pyproject.toml`, `java.yml` (configuration, no test) | pending-decision |
| 4 | requirements §13 | ingestion-scraper has no socket guard | **divergent**, citing `## 2026-10-15 — Living docs — PENDING — defects found while scoping` |
| 5–8 | requirements §13, §14 | tests found by the writer (e.g. `SignalTimezoneIT`); else none | `tested` where a `path::name` is found, else `untested` |
| 9 | requirements §13 | — | untested |
| 10, 11 | `## 2026-10-09 — Guideline setup — CHOICE — merge flow, merge bar and shared-log conflicts written into the repo` [`CLAUDE.md`] | — | untested |
| 12 | engineering ratification batch [design §9.2] | check K | pending-decision |
| 13 | `## 2026-09-19 — CI/CD pipeline — CHOICE — GitHub-hosted runners` | `.github/workflows/*.yml` `runs-on` | enforced |
| 14 | `## 2026-10-09 — CI — CHOICE — one prefix for every test image` (the two earlier CI image choices in Rationale) | `python.yml`, `java.yml` job env | enforced |
| 15 | engineering ratification batch [`.github/workflows/docs.yml`] | `docs.yml` | pending-decision |
| 16, 17, 20, 35 | engineering ratification batch [`CLAUDE.md`; `specs/README.md`] | checks J, E, C, C2 where they apply | pending-decision |
| 18, 19 | `## 2026-10-15 — Living docs — PENDING — docs impact field and Docs unchanged line` | checks E, G | pending-decision |
| 21–25, 27, 28, 37–39 | engineering ratification batch [design §5.2, §8, §9, §10.2] | checks C, C2, D, E, K where they apply | pending-decision |
| 26 | engineering ratification batch [`specs/README.md`] | check D | pending-decision |
| 29 | engineering ratification batch [`CLAUDE.md`] | — | pending-decision |
| 30–33 | `## 2026-10-09 — Guideline setup — CHOICE — merge flow, merge bar and shared-log conflicts written into the repo` [`CLAUDE.md`; `DECISIONS.md`] (the `docs_check --base` step from the ratification batch) | `.gitattributes`; check J for duplicate rows | untested (32: enforced by J for `TODO.md` rows) |
| 34 | engineering ratification batch [`TODO.md`] | check J | pending-decision |
| 36 | `## 2026-10-15 — Living docs — PENDING — archive policy for specs/done` | — | pending-decision |
| 40–47, 49 | engineering ratification batch [`CLAUDE.md`; `specs/README.md`] | — | pending-decision |
| 48 | engineering ratification batch [`VERSIONS.md`] | `test_every_new_image_is_pinned_to_an_exact_tag` (`services/ingestion-scraper/tests/unit/test_stack_observability_config.py`) for image tags only | pending-decision |
| 50 | engineering ratification batch [design §5.1] | checks E, K | pending-decision |
| 51 | engineering ratification batch [`services/ingestion-scraper/CLAUDE.md`] | — | pending-decision |
| 52 | engineering ratification batch [`services/CLAUDE.md`, Comment conventions per stack; `CLAUDE.md`, Code comments] | — | pending-decision |

When the owner approves the batch, **the owner** appends `## <date> — Living docs — CHOICE — engineering ratification batch`; once that CHOICE exists, the cutover's decision step flips these rows to their real status and Source (this spec does not wait for it, and neither this spec nor the cutover appends the CHOICE).

"design §n" is a section of `specs/living-docs-cutover-design.md`, the committed rollout design.

### `DECISIONS.md` entry appended by this spec

- `## <date> — Living docs — PENDING — engineering ratification batch`: the items above whose Source is the batch, each with its text and the file:line it came from.

No FLAG is appended. The socket divergence (item 4), the session-log conflict (item 34: the Guideline setup CHOICE says the log is dropped, `TODO.md` still keeps it; item 34 describes the log as practised) and the `--locked` and pin-age observations (Notes) are recorded under `## 2026-10-15 — Living docs — PENDING — defects found while scoping`.

### `specs/README.md`

- Statuses table gains `hold` ("parked by an owner decision; the file lives in `specs/hold/`; it returns to `blocked` or `ready` by a decision").
- Required fields table gains **Docs impact** (between Branch and Context): IDs added (`NS-new`), changed or retired, or `none — <reason>`. A note says the field list is read by check E from `docs-check.toml`.
- "Constraints" now says: which invariants (`docs/system/invariants.md`, `INV-n`) and which owner-doc requirements apply, cited by ID, never restated.
- New section **Citing decisions**: cite `DECISIONS.md` by its full heading in backticks (double backticks when the heading contains one); never by a register number.
- New section **Handoff**: when a session stops before the spec is done, add `## Handoff` with the seven lines of item 28.
- Self-containment sentence names "root `AGENTS.md`" instead of root `CLAUDE.md` (and does not mention `CLAUDE.md` at all).
- Normative sentences carry the ENG ID that owns them (e.g. the status and field rules cite items 16–18); the test naming table stays as explanation of item 47, and the "do not reference plan steps" sentence cites item 49.

### `specs/_template.md`

```markdown
# Feature Name

**Status:** draft
**Blocked by:** —
**Branch:** `feature/descriptive-name`
**Docs impact:** `NS-new` (owner doc) · changed: … · retired: … — or `none — <reason>`

---

## Context
## What this builds
## Out of scope
## Constraints
Which invariants and owner-doc requirements apply, by ID. Specific traps.
## Required tests
## Definition of done
## Compatibility
## Rollback
## Notes
## Handoff
Only when a session stops before the spec is done:
- Written against: develop @ <sha>; branch `…`, N commits ahead
- Done:
- Not done:
- Next:
- Docs:
- Open decisions:
- Verify:
```

(The existing guidance text under each heading stays, updated for IDs.)

### `.github/pull_request_template.md`

```markdown
## Docs
<!-- One line per touched domain whose owner doc did not change, outside this comment, e.g.
Docs unchanged: ingestion — test-only change -->
Docs impact: <IDs added, changed, retired>

Requirements touched were read against the code in this diff: yes / no
Divergences found: none | <ID> — `<DECISIONS heading>`

## Tests
Red before green: <failure lines>
Tests mapped to IDs: <ID> → `path::test`
Mutation-checked: <behaviour> → <test that went red>
CI-only: <tests that could not run locally>

## Review
Reviewed by: <name or separate session>
Checked: Docs unchanged lines true · doc edits state approved behaviour · tests assert behaviour · ownership placement
Findings: none | <list>
```

The example `Docs unchanged:` line sits inside the HTML comment, so it is not parsed as a disposition. The template has no generated-by footer, no session link and no tool attribution.

## Out of scope

- Root and nested `AGENTS.md`/`CLAUDE.md` (`agent-instruction-hierarchy`). Root `CLAUDE.md` keeps its text until that spec.
- Invariants, naming, no-legacy statement and every known trap except the four test and build traps above (`living-docs-system-and-contracts` and the domain specs).
- Changing CI behaviour or any test configuration: the socket divergence and the missing `--locked` in the ingestion job are recorded, not fixed (the rollout changes no application code or test configuration).
- `docs/requirements.md` § index (`legacy-docs-retirement`).
- Check I and archive banners (`living-docs-cutover`).
- Active and hold specs: none belongs to the engineering domain; their Docs impact fields are added by the domain specs.

## Constraints

- **Ownership split** (table above): no ENG ID for an agent-session hard rule; ENG docs name root `AGENTS.md` and never restate it.
- **Invariant 15** is cited, not restated. The CLAUDE.md "scaffolding exemption" (`CLAUDE.md:137`) narrows test-first, so `living-docs-system-and-contracts` writes it as an exception under INV-15; this spec does not.
- **Conversion provenance:** every requirement has a `Source` from the priority list (item 27). Process rules whose only source is `CLAUDE.md` or `specs/README.md` are in the engineering ratification batch with status `pending-decision`.
- **Conflict policy:** where `CLAUDE.md` contradicts code or practice (the `mark.unit` default, the misnamed fixture, the session log), the doc is written as approved and flagged, never silently aligned.
- **No mutants, no pushed scratch branches.** Probes that need a deliberate defect run in a disposable copy under `${TMPDIR:-/tmp}`; nothing is pushed.
- **Frozen paths:** none edited. `CLAUDE.md`, `README.md` and `VERSIONS.md` are read, not changed.
- **ID rules:** numbers from `python3 -m tools.docs_check --next ENG`, in file order verification → change-workflow → conventions; no number reused.
- **No values copied** from `VERSIONS.md`, workflows or `docs-check.toml`: ENG docs name the file.
- **No Claude footer text** in the PR template, and no plan-step names anywhere.

## Dependencies

- **Needs:** `docs-check-tooling` (checker, `docs-check.toml`, `docs.yml`).
- **Cites, defined elsewhere:** INV-12, INV-15 (`living-docs-system-and-contracts`); the CON fixture requirement; the HUB Flyway requirement; root `AGENTS.md` (`agent-instruction-hierarchy`). While `system`, `core-hub` or `operations` is still in `planned_domains`, references to their IDs and docs are notices, so this spec's checks pass whichever merges first. Root `AGENTS.md` is named in backticks only; check B checks a root file name only once it exists.
- **Hands to:** `agent-instruction-hierarchy` (root `AGENTS.md` names `docs/engineering/*` and holds the hard rules ENG links to); every domain spec (the Docs impact field, template and PR template); `legacy-docs-retirement` (root `CLAUDE.md` process sections have an owner); `living-docs-cutover` (merge recipe and conflict policy cited by the cutover PR).

## Affected files

| Path | Action |
|---|---|
| `docs/engineering/verification.md` | create |
| `docs/engineering/change-workflow.md` | create |
| `docs/engineering/conventions.md` | create |
| `specs/README.md` | modify |
| `specs/_template.md` | modify |
| `.github/pull_request_template.md` | create |
| `docs-check.toml` | modify (only the `[rollout] planned_domains` line: remove `engineering`, as the last DoD step) |
| `DECISIONS.md` | modify (append one entry: engineering ratification batch) |
| `TODO.md` | modify (this spec's own row only: status `done`, link to `specs/done/`) |
| `specs/living-docs-engineering-workflow.md` → `specs/done/living-docs-engineering-workflow.md` | move (Status `done`, in this spec's own PR) |
| `specs/living-docs-cutover-matrix.md` | modify (only the `ID` cells of rows whose NS is `ENG`, and the `IDs` cells of binding decisions rows whose fragment rows have `NS` = `ENG`) |
| `CLAUDE.md`, `docs/requirements.md`, `.github/workflows/*.yml`, `.github/scripts/check_commit_identity.sh`, `.gitattributes`, `VERSIONS.md`, `services/core-hub/build.gradle.kts`, `services/*/pyproject.toml` | untouched-but-cited |


## Required tests

Run from the repo root. `PATHS='docs/engineering/**,specs/README.md,specs/_template.md,.github/pull_request_template.md'` (this spec's own files; no other domain's docs or specs are scanned). Each fails as stated.

- `engineering_docs_have_required_structure` — `python3 -m tools.docs_check --only E --paths "$PATHS"` exits 0. Fails on a missing H2, header line, or a `Last reviewed against` SHA not in HEAD's history.
- `engineering_ids_are_unique_and_resolve` — `--only C,D --paths "$PATHS"` exits 0. Fails on a duplicate ENG ID, an unresolved ENG reference, a register number, or an unresolved decision heading. References to IDs of still-planned domains are notices and do not fail it.
- `engineering_verification_rows_are_complete` — `--only K --paths "$PATHS"` exits 0. Fails if an ENG ID has no row, a `tested` row names a missing test, or a `pending-decision` row cites no PENDING heading.
- `engineering_paths_and_links_resolve` — `--only A,B --paths "$PATHS"` exits 0.
- `matrix_rows_for_engineering_all_have_assigned_ids` — `python3 -m tools.docs_check --matrix specs/living-docs-cutover-matrix.md --domain ENG` exits 0. Fails if a move, ratify, divergent or retire row of namespace ENG has no defined ID, or the ID's `Source` lacks the row's source reference.
- `binding_engineering_decisions_carry_ids` — `python3 -m tools.docs_check --matrix specs/living-docs-cutover-matrix.md --decisions --domain ENG` exits 0. Fails if a binding row whose fragment rows have `NS` = `ENG` has no ID, or the ID's `Source` lacks the heading text (the three binding headings: GitHub-hosted runners, Guideline setup, one prefix for every test image).
- `engineering_domain_is_no_longer_planned` — `python3 -m tools.docs_check --only F | grep -c engineering` prints 0, and `grep -E '^planned_domains' docs-check.toml | grep -c engineering` prints 0. Fails if the domain is still listed or one of its owner docs is missing.
- `no_agent_session_hard_rule_is_an_eng_requirement` — `grep -hE '^[0-9]*\.? *- <a id="ENG-|^- <a id="ENG-' docs/engineering/*.md | grep -iE 'Co-Authored-By|Claude-Session|UP-TO-DATE|zero tests|lowercase|force push|never push|cloud session'` prints nothing. Fails if a hard rule was turned into an ENG requirement.
- `no_service_command_restated_in_engineering_docs` — `grep -nE 'uv (run|sync)|gradlew|npm (ci|run)|docker compose' docs/engineering/*.md` prints nothing.
- `plan_step_naming_rule_is_an_eng_convention` — `grep -cE '^- <a id="ENG-[0-9]{3}"></a>\*\*ENG-[0-9]{3}\*\* — No name carries a plan step' docs/engineering/conventions.md` prints 1.
- `scaffolding_exception_is_linked_to_inv_15` — `grep -n 'scaffolding' docs/engineering/verification.md` matches exactly one line, and that line contains `(../system/invariants.md#INV-15)`; `grep -c '\.env\.example' docs/engineering/*.md` prints 0 for every file. Fails if the exception is missing, restated with its file list, or not linked to INV-15. Until `living-docs-system-and-contracts` merges, the link is a notice under check A.
- `comment_form_per_stack_is_an_eng_convention` — `docs/engineering/conventions.md` has one ENG item containing `Javadoc`, `PEP 257` and `TSDoc`. Fails if the per-stack form stays only in an agent file.
- `engineering_traps_are_planned_sections` — `grep -c '^## Known traps$' docs/engineering/verification.md docs/engineering/conventions.md` prints 1 for each; under them, `grep -ciE 'docker hub|localstack'` (verification) and `grep -ciE 'configuration cache|spring kafka 4'` (conventions) each print at least 2 matching lines in total. Fails if one of the four trap rows has no home.
- `living_doc_format_is_an_eng_convention` — `docs/engineering/conventions.md` has one ENG item containing `Last reviewed against: develop @`, `Retired requirements` and `pending-decision`.
- `binding_process_choices_are_cited_as_source` — for each of the three binding headings above, `grep -F` finds it in a `Source` cell of `docs/engineering/*.md`.
- `ratification_batch_is_logged` — `grep -cE '^## [0-9]{4}-[0-9]{2}-[0-9]{2} — Living docs — PENDING — engineering ratification batch$' DECISIONS.md` prints 1, and every ENG `pending-decision` row cites a PENDING heading (check K).
- `specs_readme_defines_hold_status_and_docs_impact_field` — `grep -E '^\| `hold` \|' specs/README.md` and `grep -E '^\| \*\*Docs impact\*\* \|' specs/README.md` each match once.
- `specs_readme_states_decision_citation_rule_and_handoff` — `grep -c '^## Citing decisions$' specs/README.md` and `grep -c '^## Handoff$' specs/README.md` each print 1; `grep -c 'CLAUDE.md' specs/README.md specs/_template.md` prints 0 for both.
- `spec_copied_from_template_passes_structure_check` — in a disposable copy (`D=$(mktemp -d "${TMPDIR:-/tmp}/tmpl.XXXX"); git worktree add --detach "$D"`), copy `specs/_template.md` to `$D/specs/template-probe.md`, run `python3 -m tools.docs_check --root "$D" --only E --paths specs/template-probe.md`, expect exit 0, then `git worktree remove --force "$D"`. Nothing is committed in the repo. Fails if the template lacks a required field or section.
- `template_has_handoff_section_with_required_lines` — each of the seven line labels of item 28 appears under `## Handoff` in `specs/_template.md`.
- `pr_template_example_disposition_is_not_parsed` — in a disposable worktree under `${TMPDIR:-/tmp}` as above, commit a one-line change to `services/ingestion-scraper/pyproject.toml` (domain `ingestion`) on a detached HEAD, run `python3 -m tools.docs_check --root "$D" --only G --base HEAD~1 --pr-body .github/pull_request_template.md`, expect exit 1 with a `G` finding for `ingestion`, then remove the worktree. Nothing is pushed. Fails if the commented example counts as a disposition.
- `pr_template_has_no_generated_footer` — `grep -niE 'generated (with|by)|claude\.ai|claude code|co-authored' .github/pull_request_template.md` prints nothing.
- `pr_template_has_every_review_record_section` — the template has `## Docs`, `## Tests`, `## Review` and the lines `Requirements touched were read against the code`, `Divergences found:`, `Tests mapped to IDs:`, `Mutation-checked:`, `CI-only:`.
- `checker_tests_still_pass` — `python3 -m unittest discover -s tools/docs_check/tests -t .` reports `OK` with the same count as before.

## Definition of done

The last step before the block below is removing `engineering` from `[rollout] planned_domains`, then moving this file to `specs/done/` with Status `done` and updating this spec's own `TODO.md` row.

```bash
PATHS='docs/engineering/**,specs/README.md,specs/_template.md,.github/pull_request_template.md'
python3 -m unittest discover -s tools/docs_check/tests -t . 2>&1 | tail -1
python3 -m tools.docs_check --only A,B,C,D,E,K --paths "$PATHS"; echo "own-files exit=$?"
python3 -m tools.docs_check --only F | grep -c engineering
python3 -m tools.docs_check --matrix specs/living-docs-cutover-matrix.md --domain ENG; echo "M exit=$?"
python3 -m tools.docs_check --matrix specs/living-docs-cutover-matrix.md --decisions --domain ENG; echo "Mdec exit=$?"
ls docs/engineering/*.md | wc -l
grep -hE '^- <a id="ENG-' docs/engineering/*.md | wc -l
grep -hE '^- <a id="ENG-' docs/engineering/*.md | grep -iE 'Co-Authored-By|Claude-Session|UP-TO-DATE|zero tests|never push' | wc -l
grep -niE 'generated (with|by)|claude\.ai|claude code|co-authored' .github/pull_request_template.md | wc -l
test -f specs/done/living-docs-engineering-workflow.md && echo archived
```

Expected:
- `OK`;
- `own-files exit=0` with nothing on stdout (notices on stderr for still-planned domains are allowed);
- `0`;
- `M exit=0`, `Mdec exit=0`;
- `3`;
- `52` (one per item above; differs only if the owner splits or merges items, which the PR states);
- `0`, `0`;
- `archived`.

## Compatibility

- **Nothing reaches `develop`** until the cutover. Sessions on `develop` keep reading root `CLAUDE.md`.
- **On the integration branch**, root `CLAUDE.md` still holds the process text alongside the ENG docs until `agent-instruction-hierarchy` replaces it. ENG is the owner from this merge; on a difference, the ENG doc wins and `CLAUDE.md` is fixed by that spec.
- **Specs.** The new required `Docs impact` field makes check E report every older spec until its domain spec adds the field; report-only mode keeps PRs green meanwhile.
- **PR template** applies to PRs opened after it lands on a branch's base; it changes no workflow.
- **Tests that read docs** (`test_docs_never_offer_down_v_as_a_fix`, `test_new_secrets_are_documented_in_setup`) read none of the files this spec writes.

## Rollback

On the integration branch: one PR off `feature/living-docs-integration` that runs `git revert --no-commit <integration-branch tip before this spec merged>..<tip after>`, restores `DECISIONS.md` to its post-merge content (`git checkout HEAD -- DECISIONS.md`: the appended entry stays, the log is append-only), commits once, and appends `## <date> — Living docs — FLAG — engineering workflow rolled back` recording why. Merged on the owner's word. It removes `docs/engineering/`, the PR template and the README/template edits, moves this spec back to `specs/`, restores its `TODO.md` row and the matrix ENG cells, and puts `engineering` back into `[rollout] planned_domains`. Specs merged later that cite ENG IDs then report under check D until the ENG docs return.

## Notes

- **Scaffolding exemption is an invariant exception.** `CLAUDE.md:137` exempts scaffolding from test-first. Exceptions live only under their invariant, so `living-docs-system-and-contracts` writes it under INV-15 ("`pom.xml`" there is stale; the build is Gradle Kotlin DSL).
- **Ordering with other rollout specs.** This spec depends only on the tooling. Its references to INV-12, INV-15 and to `docs/system/`, `docs/core-hub/`, `docs/operations/` are notices while those domains are planned, and resolve once their specs merge. Root `AGENTS.md` is named in backticks, never linked.
- **`@pytest.mark.unit (default)`** (`CLAUDE.md:149`) is stale: unregistered under `--strict-markers` and unused. It is deleted, not moved.
- **Requirements §13 fixture filename** (`research_signal_event.json`) is stale; the contract fixture requirement goes to CON with the real file name.
- **`--locked` and backtesting lint.** The ingestion CI job runs `uv sync --all-extras` without `--locked` (`python.yml:62`), and the backtesting job runs no ruff or mypy, although `TODO.md` notes say "backtesting ruff and mypy clean". No requirement says either today; both are recorded under `## 2026-10-15 — Living docs — PENDING — defects found while scoping` for a later fix spec.
- **Pin age.** `VERSIONS.md` notes repeatedly skip releases a few days old (pandas-market-calendars 5.5.0, neo4j 6.4.0, blackbox-exporter v0.29.0). It reads like a rule but is written nowhere; it is recorded under the same PENDING heading and is not added as a requirement unless the owner says so.
- **Ratification flip.** The engineering batch may be answered after this spec merges; the owner appends the approving CHOICE and the cutover's decision-application step flips the rows.
- **As built.**
  - **54 IDs, not 52.** ENG-053 covers the core-hub build layout and ENG-054 covers records and constructor injection without Lombok. They cover the system-section matrix rows with NS = ENG and disposition `move` (M-SYS-093/094/095/096/103/153), which no item above covers, and without IDs for them check M fails.
  - **PR template comments.** Each comment opens and closes on one line. Check G otherwise read the `Docs unchanged:` example inside a multi-line comment as a real line.
  - **ENG-033 (append-only `DECISIONS.md`).** It cites the engineering ratification batch rather than the Guideline setup CHOICE, which does not cover append-only, so its status is `pending-decision`.

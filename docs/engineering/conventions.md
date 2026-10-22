# Conventions

Domain: ENG · Code: `docs/`, `specs/`, `services/`, `VERSIONS.md`, `services/core-hub/gradle/libs.versions.toml` · Last reviewed against: develop @ `b7582c3`

## Scope

Where each kind of content lives, how requirements and living docs are written, code comments, names, logging set-up, version pins and the core-hub build layout.

Not here:
- Flyway migrations are frozen: the core-hub [storage](../core-hub/storage.md) doc;
- the project naming table: the system [overview](../system/overview.md);
- what logs contain and their fields: [observability](../operations/observability.md);
- the agent file under `services/` points to ENG-052 for the comment form per stack and does not restate it;
- how a change is proven: [verification](verification.md); how a change moves from spec to merge: [change workflow](change-workflow.md).

## Requirements

- <a id="ENG-040"></a>**ENG-040** — Each fact has one owner: a requirement lives in exactly one `docs/` file and is cited elsewhere by ID; READMEs, runbooks and agent files hold no requirement text and link to the owner; machine-readable files own their values, and docs name the file and explain the meaning without copying values.
- <a id="ENG-041"></a>**ENG-041** — Content goes by kind: living docs hold approved behaviour; change specs hold proposed work; runbooks hold ordered operator steps with checks; READMEs hold orientation, layout and tables; `DECISIONS.md` holds why and who decided; agent files hold workflow and routing.
- <a id="ENG-042"></a>**ENG-042** — A requirement is one testable statement in the present tense; living docs hold no plan steps, change narration, future work or copied machine values.
- <a id="ENG-043"></a>**ENG-043** — A code comment tells the reader what the code cannot (intent, a constraint, a non-obvious why, units, an invariant) and makes sense to someone who never saw the plan or the session.
- <a id="ENG-044"></a>**ENG-044** — A comment never restates the code or narrates a change, and holds no plan steps or spec names, project history, version re-verifications, or machine specs and targets; decisions go to `DECISIONS.md`, setup to `docs/`, what changed to the PR description.
- <a id="ENG-045"></a>**ENG-045** — Doc comments are written for contracts (public extension points and anything a caller can get wrong), not for everything; a docstring that only repeats the name is deleted.
- <a id="ENG-046"></a>**ENG-046** — A behaviour change fixes or deletes the comments that describe the old behaviour in the same commit.
- <a id="ENG-047"></a>**ENG-047** — A test name is a falsifiable claim about behaviour (`test_backfill_does_not_advance_the_live_cursor`, not `test_backfill_works`).
- <a id="ENG-048"></a>**ENG-048** — `VERSIONS.md` is the single list of pinned versions, with no floating tags, `latest` or `>=`; an item marked *resolve at install* is pinned to an exact version when first installed and written back; each service's lock file is committed and authoritative for its resolved dependencies; a version-sensitive claim is re-verified when code that depends on it is touched, with the outcome in `DECISIONS.md`.
- <a id="ENG-049"></a>**ENG-049** — No name carries a plan step: file, function, test, variable and branch names (beyond the rollout's own branch) and commit messages describe what the thing does (`corroboration_review`, `test_biorxiv_payload_maps_to_rawdocument`), never `step_3_2`, `phase_2` or a spec number.
- <a id="ENG-050"></a>**ENG-050** — A living doc under `docs/` starts with `Domain: <NS> · Code: <paths> · Last reviewed against: develop @ <sha>`, has the H2s `Scope`, `Requirements`, `Verification` and `Retired requirements` (and optionally `Machine-readable authorities`, `Known traps`, `Rationale`), defines each requirement as a list item `<a id="NS-NNN"></a>**NS-NNN** — <statement>`, and keeps one verification row per active ID with columns `ID | Source | Verified by | Status` and the statuses `tested` (a named `path::name` test), `enforced` (a named machine check), `untested`, `divergent` (cites a decision) and `pending-decision` (cites a PENDING heading).
- <a id="ENG-051"></a>**ENG-051** — A Python service configures logging once, at app creation (`configure_logging()` called in `create_app()`), never per module. The log fields and what logs may contain are owned by operations ([observability](../operations/observability.md)).
- <a id="ENG-052"></a>**ENG-052** — Comment form per stack: Java (core-hub) uses Javadoc `/** */` on types and on public or package-level methods whose contract is not obvious, `//` for a local why, and no `@param`/`@return` tags that only repeat names and types; Python (ingestion-scraper, backtesting, strategy, backup) uses PEP 257 docstrings in prose with backticked names, `#` for a local why, and a module or script note in the module docstring rather than in `#` lines at the top; TypeScript (dashboard) uses TSDoc `/** */` on exported components, hooks and API helpers whose behaviour is not obvious from props and types, with no JSDoc type annotations.
- <a id="ENG-053"></a>**ENG-053** — core-hub builds with the Gradle Kotlin DSL and a committed wrapper. Every dependency and plugin version is declared once, in `services/core-hub/gradle/libs.versions.toml`, kept equal to `VERSIONS.md`, and never as a literal in `build.gradle.kts`; the Spring Boot plugin supplies the dependency BOM, so `io.spring.dependency-management` is not applied; the Java toolchain is set explicitly to the version `VERSIONS.md` pins.
- <a id="ENG-054"></a>**ENG-054** — core-hub Java code uses records for data carriers and constructor injection, with no Lombok and no field injection.

## Machine-readable authorities

| File | Governs | Notes |
|---|---|---|
| `VERSIONS.md` | Every pinned version | ENG-048; versions are never copied into docs |
| `services/core-hub/gradle/libs.versions.toml` | core-hub dependency and plugin versions | ENG-053 |
| `.gitignore` | What is never committed | ENG-035 in [change workflow](change-workflow.md) |

## Verification

| ID | Source | Verified by | Status |
|---|---|---|---|
| ENG-040 | `## 2026-10-22 — Living docs — PENDING — engineering ratification batch` [design §3, §7.2] | — | pending-decision |
| ENG-041 | `## 2026-10-22 — Living docs — PENDING — engineering ratification batch` [design §3, §7.2] | — | pending-decision |
| ENG-042 | `## 2026-10-22 — Living docs — PENDING — engineering ratification batch` [design §3, §7.2] | — | pending-decision |
| ENG-043 | `## 2026-10-22 — Living docs — PENDING — engineering ratification batch` [`CLAUDE.md`] | — | pending-decision |
| ENG-044 | `## 2026-10-22 — Living docs — PENDING — engineering ratification batch` [`CLAUDE.md`] | — | pending-decision |
| ENG-045 | `## 2026-10-22 — Living docs — PENDING — engineering ratification batch` [`CLAUDE.md`] | — | pending-decision |
| ENG-046 | `## 2026-10-22 — Living docs — PENDING — engineering ratification batch` [`CLAUDE.md`] | — | pending-decision |
| ENG-047 | `## 2026-10-22 — Living docs — PENDING — engineering ratification batch` [`specs/README.md`] | — | pending-decision |
| ENG-048 | requirements §1 (exact pins, committed lock file); the rest: `## 2026-10-22 — Living docs — PENDING — engineering ratification batch` [`VERSIONS.md`] | `services/ingestion-scraper/tests/unit/test_stack_observability_config.py::test_every_new_image_is_pinned_to_an_exact_tag` for image tags only | pending-decision |
| ENG-049 | `## 2026-10-22 — Living docs — PENDING — engineering ratification batch` [`CLAUDE.md`; `specs/README.md`] | — | pending-decision |
| ENG-050 | `## 2026-10-22 — Living docs — PENDING — engineering ratification batch` [design §5.1] | checks E, K | pending-decision |
| ENG-051 | `## 2026-10-22 — Living docs — PENDING — engineering ratification batch` [`services/ingestion-scraper/CLAUDE.md`] | — | pending-decision |
| ENG-052 | `## 2026-10-22 — Living docs — PENDING — engineering ratification batch` [`services/CLAUDE.md`, Comment conventions per stack; `CLAUDE.md`, Code comments] | — | pending-decision |
| ENG-053 | requirements §1 (Kotlin DSL, committed wrapper, version catalog); the plugin and toolchain clauses: `## 2026-10-22 — Living docs — PENDING — engineering ratification batch` [`services/core-hub/CLAUDE.md`] | — | pending-decision |
| ENG-054 | requirements §1 [`services/core-hub/CLAUDE.md`] | — | untested |

"design §n" is a section of `specs/living-docs-cutover-design.md`. A bracketed Source part is where the text came from; the part before it is the approval.

## Known traps

- Gradle 9 prefers the configuration cache; a build script it disallows fails at configuration time with an error that reads nothing like a test failure. Fix the script; never disable the cache. (from `services/core-hub/CLAUDE.md`, Traps)
- Spring Boot 4, Spring Framework 7 and Spring Kafka 4 differ from the 3.x behaviour most examples show; where they disagree, the 4.x reference documentation wins. (from `services/core-hub/CLAUDE.md`, Traps)

## Retired requirements

None.

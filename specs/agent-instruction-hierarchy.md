# Agent instruction hierarchy

**Status:** blocked
**Blocked by:** only the manual load check on the owner's Mac (§8: Claude Code and Codex, 28 cells, the `VERIFIED` entry in `DECISIONS.md`); Claude Code and Codex are not installed in cloud sessions. The cloud part of the definition of done passes on `feature/living-docs-agent-instructions`. Everything else it waited on is in place: the domain docs, check L and check D, `## 2026-10-17 — Living docs — CHOICE — agent instruction files`, `## 2026-10-17 — Living docs — CHOICE — rollout branch model` and `## 2026-10-17 — Living docs — CHOICE — docs impact field and Docs unchanged line`.
**Branch:** `feature/living-docs-agent-instructions` (PR into `feature/living-docs-integration`)
**Docs impact:** no `docs/` requirement added, changed or retired. Creates root `AGENTS.md` and eight nested `AGENTS.md`; reduces the five existing `CLAUDE.md` files to import shims (the `AGENTS.md` chain from the root down to their own directory) and adds four new ones; changes no other file outside this spec's own `TODO.md` row and its move to `specs/done/`. Appends one `VERIFIED` entry to `DECISIONS.md` after the Mac check.

---

## Context

Written against `develop` @ `e51f742`.

**What loads today.**

* Five agent files exist, all `CLAUDE.md`: root (26,132 B, 246 lines), `services/CLAUDE.md` (2,312 B), `services/core-hub/CLAUDE.md` (4,498 B), `services/ingestion-scraper/CLAUDE.md` (2,660 B), `docker/CLAUDE.md` (3,532 B). No `AGENTS.md`, `AGENTS.override.md`, `.claude/` or `.codex/` exists.
* Root `CLAUDE.md:6-7` imports `@TODO.md` (33,484 B) and `@VERSIONS.md` (9,213 B). About 68.8 KB loads in every Claude Code session, whatever the launch directory. Most of `TODO.md` is done rows and the session log.
* `services/backtesting`, `services/strategy`, `services/backup` and `services/dashboard` have no agent file.
* **Codex gets nothing.** With no `AGENTS.md`, Codex loads no project instructions. Renaming the files would not work either: Codex does not expand `@` imports, and the core-hub chain (root + `services` + core-hub = 32,942 B) exceeds Codex's 32 KiB default, which truncates silently at the byte boundary.
* **Duplicated authority.** All 15 invariants restate `docs/requirements.md` §3 with different numbering. At least 11 of the 24 known traps (`CLAUDE.md:203-226`) are also in a nested file or requirements. The commands table (`CLAUDE.md:73-97`) duplicates `README.md:44-64` and has already drifted (no strategy or kill-switch rows). The documentation-maintenance table (`CLAUDE.md:116-135`) mandates duplication ("intentional duplication is fine").
* **Contradictions loaded together.** `services/CLAUDE.md:24` says a DLT partition mismatch "fails silently" because Spring publishes to the same partition; the resolver returns `-1` (`services/core-hub/src/main/java/dev/auspex/corehub/config/KafkaConfig.java:187-188`). `TODO.md:5` says "find the first ready spec" while `CLAUDE.md:16,39` say "the spec you were assigned".
* **What enforces agent rules today:** only `.github/scripts/check_commit_identity.sh` (run by `.github/workflows/commit-identity.yml`), which rejects Claude identities and `Co-Authored-By`/`Claude-Session` trailers. Its comment at line 4 points at "root CLAUDE.md, Git".
* **Doc-reading tests.** `services/ingestion-scraper/tests/unit/test_stack_persistence_config.py::test_docs_never_offer_down_v_as_a_fix` reads `README.md`, `CLAUDE.md`, `SETUP.md`, `docker/README.md` and `docker/CLAUDE.md`: every line mentioning `down -v` must contain "destroys all data". `legacy-docs-retirement` extends the list to `AGENTS.md` files; until then this spec enforces the same rule by its own check.

**Loader behaviour this design relies on.** Labels: VERIFIED-DOCS = read in vendor documentation on 2026-10-15; VERIFIED-SOURCE = read in Codex source at tag `rust-v0.159.2`. Neither CLI was run; the Mac check below is the first execution.

| Fact | Label |
|---|---|
| Claude Code loads `CLAUDE.md` (and `CLAUDE.local.md`) from the launch directory and every ancestor at launch, concatenated root first; nested files below the launch directory load when Claude reads or edits a file there | VERIFIED-DOCS |
| `@path` in a `CLAUDE.md` imports the file relative to the importing file, at launch | VERIFIED-DOCS |
| Claude Code reads `AGENTS.md` natively only from v2.1.277 and only when no `CLAUDE.md`/`CLAUDE.local.md` is on the path; a `CLAUDE.md` containing `@AGENTS.md` never double-loads | VERIFIED-DOCS |
| Codex reads at most one of `AGENTS.override.md`, `AGENTS.md` per directory, from the git root down to the launch directory, never deeper | VERIFIED-SOURCE |
| Codex does not expand `@` imports; it concatenates file text verbatim | VERIFIED-SOURCE |
| Codex's `project_doc_max_bytes` default is 32 KiB combined; a file past the budget is cut at the byte and later files are dropped, with only a log warning | VERIFIED-SOURCE |

## What this builds

When this spec is done, Claude Code and Codex get the same instructions from one canonical file per directory, and a session starts from about 4–6 KB of instructions instead of 68.8 KB.

### 1. Structure (default option of `## 2026-10-15 — Living docs — PENDING — agent instruction files`)

* `AGENTS.md` is canonical at every level. Nothing is imported into it; it names files as plain paths for the agent to open.
* Every `CLAUDE.md` is exactly the import lines of its `AGENTS.md` chain, root first and its own `@AGENTS.md` last (root: `@AGENTS.md`; `services/core-hub/`: `@../../AGENTS.md`, `@../AGENTS.md`, `@AGENTS.md`), at most 512 B, no "must", "never" or "always". Claude Code expands imports only in the launch directory's `CLAUDE.md`, so a nested shim imports its ancestors itself.
* `TODO.md` and `VERSIONS.md` stop auto-loading. Root `AGENTS.md` tells the agent to open `TODO.md` at session start and `VERSIONS.md` only when touching a dependency.
* Pairs (`AGENTS.md` + `CLAUDE.md`) at: repo root, `services/`, `services/core-hub/`, `services/ingestion-scraper/`, `services/backtesting/`, `services/strategy/`, `services/backup/`, `services/dashboard/`, `docker/`.

### 2. Budgets (check L; limits set in `docs-check.toml` `[budgets]` by `docs-check-tooling`)

| File or chain | Limit |
|---|---|
| Root `AGENTS.md` | ≤ 6 KB |
| Each nested `AGENTS.md` | ≤ 3 KB |
| Root → deepest launch chain (`wc -c` sum of every `AGENTS.md` from root to the launch directory) | ≤ 16 KB, half of Codex's default, leaving room for user-level files |
| Each `CLAUDE.md` | ≤ 512 B |

### 3. Ownership split (what goes where)

| Rule set | Owner | Others |
|---|---|---|
| Agent-session hard rules: zero tests is a failure; Gradle `UP-TO-DATE` is not a pass; never push `develop`/`main`; merge only on the owner's word; commit identity and no trailers or footers; commit-subject style; no plan-step names; where work can run; stop and flag; do not report complete without a passing run | **Root `AGENTS.md`** (no ENG ID; test-first itself is INV-15, which `AGENTS.md` cites) | `docs/engineering/*` links to them, never restates |
| Engineering process detail: TDD loop, merge bar, mutation check, branching and merge recipe, conversion provenance, conflict policy, doc ownership, comments rule, naming conventions, handoff format | `docs/engineering/*` (ENG IDs) | Root `AGENTS.md` names the files |
| Service commands | The service's `AGENTS.md` (Codex cannot follow a link, so commands must be in the loaded file) | Service READMEs link to it |
| Stack-level commands (compose up/down, smoke test, restore) | Root `README.md` | Root `AGENTS.md` and `docker/AGENTS.md` name it |
| Requirements, invariants, traps | Their `docs/` owner | Agent files carry IDs and a few words of label only |

### 4. Root `AGENTS.md` (≤ 6 KB)

Opening lines, in this order:

1. `# Auspex — agent instructions` (this exact heading; the load check reads it).
2. "Canonical for every coding agent. Claude Code reads it through `CLAUDE.md`; Codex reads it directly. Nothing is imported into this file: open the paths named below when you need them."
3. **Routing line** (exact text, checked): "Before editing under a directory that has its own `AGENTS.md`, open that file: it lists that directory's commands and the owner docs."

Sections:

* **Authority.** `docs/` is approved current behaviour, one owner per requirement, IDs like `ING-NNN`; `docs/README.md` maps domains to owners. `specs/` holds proposed changes, each governing only its own work until merged; `specs/done/` is history, never authority. Values live in machine-readable files; docs explain them and never copy them. On conflict follow the conflict policy in `docs/engineering/change-workflow.md`; never edit a doc to match code without the owner's decision. A brief, note or memory from outside the repo must name the develop commit it was written against; if HEAD has moved, re-read what it cites.
* **Session start.** (1) The work is the spec you were assigned; with none, open `TODO.md` and take the first `ready` spec; with none ready, scope a `draft` (`specs/README.md`). (2) Read the spec in full, then every `docs/` file its Docs impact names. (3) **The rule that matters most**, kept short and verbatim in meaning from `CLAUDE.md:49-50`: a green suite is necessary, not sufficient; before writing a test, check it against those requirements; if it can only pass by violating one, stop, append to `DECISIONS.md`, and ask; do not write it. (4) If a task seems to need an invariant broken (`docs/system/invariants.md`), stop and flag the same way. (5) Work only that spec; update it as items complete. (6) If you stop before it is done, append a `## Handoff` block (format in `docs/engineering/change-workflow.md`).
* **Hard rules** (the set in §3, each one line). Includes: "A behaviour change updates its owning doc in the same PR; otherwise the PR body says `Docs unchanged: <domain> — <reason>`" (`## 2026-10-15 — Living docs — PENDING — docs impact field and Docs unchanged line`); "Never commit `.env`, `target/`, `.venv/`, `__pycache__/` or Docker volumes"; "Cloud sessions have no Docker, sec.gov or Yahoo: container tests are proven in CI, say so in the PR; work that only the owner's Mac can run goes in a spec the owner runs there; no hand-run setup or data scripts (startup data is a compose one-shot, current data an Airflow DAG calling a service API, a step that cannot be automated goes in `SETUP.md`)."
* **Hard-rule landing phrases.** Every rule moved out of a `CLAUDE.md` into an agent file is written so that it contains the phrase below, verbatim; `every_hard_rule_lands_in_agents_md` greps for each. The wording around it is free.

  | Rule (source) | Phrase | File |
  |---|---|---|
  | Zero tests is a failure (`CLAUDE.md:99`) | `executes zero tests is a failure` | `AGENTS.md` |
  | Gradle up-to-date is not a pass (`CLAUDE.md:101`) | `UP-TO-DATE` | `AGENTS.md` |
  | Never push `develop` or `main` (`CLAUDE.md:172`) | `Never push to \`develop\` or \`main\`` | `AGENTS.md` |
  | Merge only on the owner's word (`CLAUDE.md:174`) | `Merge only when the owner says so` | `AGENTS.md` |
  | Commit identity, no Claude trailers (`CLAUDE.md:193`) | `Co-Authored-By` | `AGENTS.md` |
  | No Claude footers on GitHub (`CLAUDE.md:194`) | `Generated with Claude Code` | `AGENTS.md` |
  | Commit-subject style (`CLAUDE.md:195`) | `subject line only, lowercase` | `AGENTS.md` |
  | Never commit build output or secrets (`CLAUDE.md:192`) | `__pycache__/` | `AGENTS.md` |
  | No plan-step names (`CLAUDE.md:33`) | `plan-step` | `AGENTS.md` |
  | Where work can run (`CLAUDE.md:198-199`) | `Cloud sessions have no Docker` | `AGENTS.md` |
  | No hand-run setup or data scripts (`CLAUDE.md:200`) | `no hand-run setup or data scripts` | `AGENTS.md` |
  | Stop and flag (`CLAUDE.md:49-50`) | `stop, append to \`DECISIONS.md\`, and ask` | `AGENTS.md` |
  | Report complete only after a passing run (`CLAUDE.md:246`) | `unless its tests ran and passed` | `AGENTS.md` |
  | Docs impact or `Docs unchanged:` line | `Docs unchanged:` | `AGENTS.md` |
  | Per-stack comment form (`CLAUDE.md:139-145`, `services/CLAUDE.md:30-35`; the table is owned by the ENG comment-form requirement in `docs/engineering/conventions.md`, written by `living-docs-engineering-workflow`) | `docs/engineering/conventions.md` (a one-line pointer to that requirement, no table) | `services/AGENTS.md` |

  Line numbers are at `e51f742`. A rule in this table that cannot be phrased within the byte budget is a blocker: stop and flag, do not drop it.
* **Where things are** (plain-path table, no imports): work queue `TODO.md`; spec format `specs/README.md`; requirements `docs/README.md`; process detail `docs/engineering/`; pinned versions `VERSIONS.md` (only when touching a dependency); decisions `DECISIONS.md` (read before flagging, append when you flag; heading format named); stack commands `README.md`; service commands the service `AGENTS.md`; manual setup `SETUP.md`; outstanding user actions `docs/PREREQUISITES.md`; restore `docs/backup-restore.md`; local model `docs/local-model-runbook.md`.
* **Tone** (`CLAUDE.md:245-246`): do not report a step complete unless its tests ran and passed; if blocked, say so plainly in `DECISIONS.md` and stop; never work around an invariant to keep moving.

Not in root `AGENTS.md`: invariant text, the naming table, commands, traps, the TDD loop, the merge recipe, the doc-maintenance table (replaced by ENG doc ownership).

### 5. Nested `AGENTS.md` (each ≤ 3 KB)

Rules for every nested file: (1) only what is local to its directory: commands, layout, and requirement IDs with a few words of label; (2) never restates a parent rule; (3) no requirement text; (4) nothing a change must obey lives only here (the routing line and the `docs/` owners carry it). Allowed H2s: `Owners`, `Commands`, `Layout`, `Requirements that bite here`, `Trap pointers`. Each bullet under the last two starts with an ID. First line is `# <directory name>` (`# services`, `# core-hub`, `# ingestion-scraper`, `# backtesting`, `# strategy`, `# backup`, `# dashboard`, `# docker`).

IDs are looked up in the merged `docs/` files (`grep -n '<a id=' docs/**/*.md`), never invented.

| File | Owners line | Commands (sources) | Layout | IDs to cite (subject → owner) |
|---|---|---|---|---|
| `services/AGENTS.md` | `docs/system/contracts.md` for anything on Kafka | none | one-line pointer to the per-stack comment form, which ENG owns in `docs/engineering/conventions.md` (the table from `services/CLAUDE.md:30-35` is not copied here) | INV-1, INV-2 (labels only); CON signal-event fixture requirement; CON DLT naming |
| `services/core-hub/AGENTS.md` | `docs/core-hub/{consumption,storage,corroboration,http-api}.md`, `docs/system/contracts.md` | `./gradlew test` · `integrationTest` · `check` · `test --tests '*X'` · `timezoneCheck` · `--rerun-tasks` (`services/core-hub/CLAUDE.md:7-12`) | unit `src/test/java/**/*Test.java` (no Spring context), container `src/integrationTest/java/**/*IT.java`, versions in `gradle/libs.versions.toml` | COR contract test extended unmodified; HUB Flyway frozen; HUB `ErrorHandlingDeserializer`; CON `.dlt` + partition -1; CON `BigDecimal` `confidence_score`; CON unknown properties ignored; HUB MERGE Company on normalised name; HUB qualified `@Transactional`; ENG Gradle configuration cache; ENG Boot 4.x vs 3.x |
| `services/ingestion-scraper/AGENTS.md` | `docs/ingestion/{connectors,pipeline,extraction}.md`, `docs/system/contracts.md` | `uv sync --all-extras` · `uv run pytest tests/unit -q` · one file · `uv run pytest -q` · `uv run ruff check . && uv run mypy src` · regenerate fixture `uv run pytest tests/unit/test_contract_fixture.py` (`services/ingestion-scraper/CLAUDE.md:7-11`, `CLAUDE.md:97`) | `src/auspex_ingest/`, `tests/unit` (sockets disabled), `tests/integration`, `tests/fixtures`, `scripts/`, `dags/` | INV-1, INV-3, INV-8, INV-9; ING `RateLimitedClient`; ING inject-don't-construct seams; ING `produce()` flush; ING `strftime` on non-UTC; EXT `is_signal` path; OPS single gunicorn process; ENG `pytest-socket`, `respx`, Testcontainers |
| `services/backtesting/AGENTS.md` | `docs/research/*.md`, `docs/research/evaluation-protocol.md` | `uv run pytest tests/unit -q` · `uv run pytest tests/integration -q` (Docker) · `uv run ruff check .` (`services/backtesting/README.md:224-226`) | `src/auspex_backtesting/`, `scripts/`, `dags/`, `config/` | RES/EVA IDs for hash-locked hypotheses, version-locked universe rules, settled bars, as-of rules (the research spec names them) |
| `services/strategy/AGENTS.md` | `docs/strategy/*.md` | `uv run ruff check . && uv run mypy src && uv run pytest tests/unit -q`; kill switch (`services/strategy/README.md:10-12`) | `src/auspex_strategy/` | STR `AsOfContext` (processing time never decides an as-of read), risk check order, deterministic intent ids |
| `services/backup/AGENTS.md` | `docs/operations/backup.md`; restore exception under INV-2 | `uv run ruff check . && uv run mypy src` · `uv run pytest tests/unit -q` · `uv run pytest tests/integration -q` (CI) (`services/backup/README.md:24-26`) | `src/auspex_backup/`, `dags/` | INV-2 (restore exception), INV-12, OPS backup IDs |
| `services/dashboard/AGENTS.md` | `docs/dashboard.md`; `docs/core-hub/http-api.md` for the write token | `npm ci && npm run lint && npx tsc --noEmit && npm run test:ci` · `npm run build && npm run test:bundle` (`CLAUDE.md:94-95`) | `src/app`, `src/proxy.ts`, `scripts/hash-password.mjs` | DSH BFF, single-user login; HUB write token; DSH traps (bcrypt `$`, Next 16 `proxy`) |
| `docker/AGENTS.md` | `docs/operations/{topology,orchestration,observability,backup}.md`; `docker/topics.yaml` via `docs/system/contracts.md` | none: stack commands are in root `README.md` (named, not copied) | `topics.yaml`, `kafka-init/`, `postgres-init/`, `grafana/`, `prometheus/`, ... | OPS one-shots, bare `${VAR}`, `mem_limit` and logging anchor, named volumes, never `down -v` as a fix, Fernet key from `.env`; OPS Grafana `$$`; CON DLT partition parity |

**Commands are copied from the cited lines and then checked by running each one in a cloud session where possible** (Python and npm commands; Gradle where Maven Central is reachable). A command that cannot run in the cloud is marked "(CI)" or "(Mac)" in the file, not left untested silently.

### 6. Where each root `CLAUDE.md` section goes

| Section (`CLAUDE.md` lines) | Destination |
|---|---|
| Always-loaded context, `@TODO.md`/`@VERSIONS.md` (`:5-16`) | Dropped; root `AGENTS.md` "Where things are" lists the paths |
| Naming (`:18-29`), service directories descriptive (`:31`) | `docs/system/overview.md` (SYS) |
| No plan-step references (`:33`) | ENG conventions (owner, written by `living-docs-engineering-workflow`); one-line hard rule in root `AGENTS.md` that names it |
| What this is (`:35-36`) | Root `AGENTS.md` names `README.md` and `docs/system/overview.md` |
| Session start (`:38-44`) | Root `AGENTS.md` Session start; the done-flow detail (`:44`) is ENG change-workflow |
| No legacy system (`:46-47`) | `docs/system/overview.md` (SYS) |
| Rule that matters most (`:49-52`) | Root `AGENTS.md`, short; the `test_dag_task_only_invokes_fetch_since` story is ENG rationale |
| Invariants (`:54-69`) | `docs/system/invariants.md`; root `AGENTS.md` keeps the stop-and-flag rule and the path |
| Commands (`:71-97`) | Service rows → service `AGENTS.md`; stack rows → root `README.md` |
| Zero tests, `UP-TO-DATE` (`:99-101`) | Root `AGENTS.md` hard rules; `failOnNoDiscoveredTests` and `--strict-markers` settings → ENG verification |
| TDD loop (`:103-114`) | ENG verification |
| Documentation maintenance (`:116-135`) | **Replaced** by ENG conventions "Doc ownership"; deleted here |
| Scaffolding exemption (`:137`) | Exception under INV-15 in `docs/system/invariants.md` (written by `living-docs-system-and-contracts`); ENG verification links to it |
| Code comments (`:139-145`) | ENG conventions; Flyway-frozen line → HUB storage |
| Test file conventions (`:147-154`) | Layout rows of the service `AGENTS.md`; contract-test rule → COR |
| Git (`:156-195`) | Hard rules → root `AGENTS.md`; branching, recipe, merge bar, mutation check, union driver → ENG change-workflow |
| Where work can run (`:197-200`) | Root `AGENTS.md` (owner); ENG verification links to it |
| Known traps (`:202-226`) | Each trap → its owner doc's Known traps (destinations in the migration matrix, rows from `CLAUDE.md:203-226`); service `AGENTS.md` lists ID pointers |
| File map (`:228-243`), Tone (`:245-246`) | Root `AGENTS.md` |

Nested `CLAUDE.md` content follows the same split (matrix rows per line). Two known errors are dropped, not carried: `services/CLAUDE.md:24` (DLT "fails silently") and the "re-verify against Spring Kafka 4.1" caveat (`services/core-hub/CLAUDE.md:48`; verified per `## 2026-08-16 — Step 1.3 — VERIFIED — DeadLetterPublishingRecoverer with Spring Kafka 4.1`).

### 7. Edits this spec does not make

This spec edits only agent files, its own `TODO.md` row and its own spec file. Three stale pointers to root `CLAUDE.md` sections are left to their owners, and checked here:

* Residual `CLAUDE.md` section citations in active and hold specs (at `e51f742`: `specs/slow-signal-data-refresh.md:22,61`, `specs/hold/equity-offering-connector.md:24`, `specs/hold/insider-buying-connector.md:18`, `specs/point-in-time-universe.md:123`, `specs/filing-text-change-score.md:16`, `specs/short-interest-snapshots.md:66`) are repointed by the domain spec that adds each spec's Docs impact (`living-docs-research`, `living-docs-ingestion`). `specs/soak-test-run.md` and `specs/first-run-on-stack-machine.md` are not in this list: `living-docs-operations` repoints both itself. `no_spec_cites_a_claude_md_section` fails here if one is left.
* `TODO.md:5` ("find the first `ready` spec") and the comment at `.github/scripts/check_commit_identity.sh:4` ("root CLAUDE.md, Git") are repointed by `living-docs-cutover`, not by this spec. Root `AGENTS.md` Session start states the order that applies; once `CLAUDE.md` is `@AGENTS.md`, "root CLAUDE.md" still resolves to the hard rules through the import.

### 8. Manual load check on the owner's Mac

Neither Claude Code nor Codex is installed in cloud sessions. The owner (or a Claude Code session the owner starts on the Mac) runs this on a checkout of `feature/living-docs-cutover-prep` (which carries this spec's files and every later rollout part), after the cloud part of the definition of done passes and before this spec's PR merges.

**Setup, recorded with the result:** `claude --version`, `codex --version`, `git rev-parse HEAD`. No `AGENTS.override.md` anywhere in the repo; no `CLAUDE.local.md` in the repo; note whether `~/.codex/AGENTS.md` or a user `CLAUDE.md` exists and its byte size; Codex config without `project_doc_max_bytes` or `project_doc_fallback_filenames` overrides. Each cell is a **fresh** session (no resume), launched in the stated directory.

Four cells: Claude Code at the repo root; Claude Code in `services/core-hub/`; Codex at the repo root; Codex in `services/core-hub/`. Ask each prompt verbatim, in order, and record the answer.

| # | Prompt (verbatim) | Expected answer: root launch | Expected answer: `services/core-hub/` launch |
|---|---|---|---|
| P1 | "Without reading any file or running any command, list the first line of every project instruction file already in your context, in the order you received them." | Claude: `@AGENTS.md` and/or `# Auspex — agent instructions` (the import), nothing else. Codex: `# Auspex — agent instructions` only | Both: `# Auspex — agent instructions`, `# services`, `# core-hub`, in that order (Claude may also show each `@AGENTS.md` line) |
| P2 | "Without opening any file: what is the status of the 'Stack backup' row in TODO.md?" | It does not know without opening `TODO.md` (any answer of `done` without a tool call fails: `TODO.md` was auto-loaded) | Same |
| P3 | "Without opening any file: which Spring Boot version does VERSIONS.md pin?" | It does not know without opening `VERSIONS.md` | Same |
| P4 | "Do not edit anything. You are about to change services/core-hub/src/main/java/dev/auspex/corehub/audit/RawAuditService.java. Which instruction file must you open first? Open it and quote its first line and its Commands section." | Names `services/core-hub/AGENTS.md` (citing the routing line); quotes `# core-hub` and the commands exactly as in the file. Codex must reach it by opening the file, since it never loads nested files from the root | Says it is already loaded; quotes the same lines |
| P5 | "Without opening any file, quote the last line of services/core-hub/AGENTS.md exactly." | Codex: says it is not loaded (correct; nested files are not loaded from the root). Claude: not loaded, or quotes it if P4 made it load | Both quote it byte-for-byte equal to `tail -n 1 services/core-hub/AGENTS.md` (proves no truncation) |
| P6 | "May a commit you make carry a Co-Authored-By trailer, and may you push to develop?" | No to both, citing root `AGENTS.md` | Same |
| P7 | "Where are the system invariants defined, and what do you do if a task seems to need one broken?" | `docs/system/invariants.md`; stop, append to `DECISIONS.md`, ask | Same |

Optional, if the CLI offers it: the command that lists loaded instruction files (for Claude Code, `/memory`). Record its output; the prompts remain the check of record.

**Record.** Append to `DECISIONS.md`: `## <date> — Living docs — VERIFIED — agent instruction loading on the stack machine`, with the versions, HEAD, user-level files present, and for each of the 28 cells (4 sessions × 7 prompts) the answer in one line and pass/fail. A failed cell blocks this spec's merge; the fix is a change to the agent files on this spec's branch, then that cell is re-run and re-recorded before the PR merges.

## Out of scope

* Any `docs/` requirement text; any change to the content owned by the system and domain specs.
* Trimming READMEs, the README commands table, `SETUP.md`, `PREREQUISITES.md`, and extending `test_docs_never_offer_down_v_as_a_fix` to `AGENTS.md` files (`legacy-docs-retirement`).
* `specs/README.md` and `specs/_template.md` (repointed from "root `CLAUDE.md`" by `living-docs-engineering-workflow`).
* Moving `TODO.md`'s session log, `TODO.md:5`, or any `TODO.md` row other than this spec's own.
* `.claude/rules/`, `AGENTS.override.md`, Codex or Claude Code configuration files, `CLAUDE.local.md`.
* Any application code or test change.

## Constraints

* **Invariants that apply:** INV-15 (test-first: the checks below are written and seen red on a seeded defect before the files are written); INV-6 (no credential, URL or port in an agent file; commands that need credentials name the env vars, as the kill-switch command does). The agent files must not restate any invariant; they cite `INV-N`.
* **Conversion provenance and conflict policy.** Agent files hold no requirement text, so nothing here needs a `Source`. Every rule removed from a `CLAUDE.md` must already be in its owner (a `docs/` ID or root `AGENTS.md`) before deletion; the migration matrix rows for `CLAUDE.md` sources show where. A rule with no destination is a blocker: stop and flag, do not drop it. Agent files never win a conflict with `docs/`.
* **ID rules.** Agent files reference IDs only as defined in `docs/`, and only active ones. Check D resolves every reference and flags a placeholder or a register number in agent files; it does not flag a reference to a retired ID there, so `agent_file_ids_are_active` checks that.
* **No import in `AGENTS.md`** (check L flags an `@` immediately followed by a path ending in a file extension, at line start or after whitespace). The only import lines in the repo's agent files are the `@AGENTS.md` first lines of the `CLAUDE.md` files.
* **`down -v`.** No agent file needs to mention it (stack commands are in `README.md`). If one does, the line says "destroys all data", like the existing doc test requires.
* **Frozen paths** are not moved: `SETUP.md`, `VERSIONS.md`, `README.md`, `CLAUDE.md` (path kept; content becomes `@AGENTS.md`), `docker/README.md`, `docker/CLAUDE.md`, `docs/backup-restore.md`, `docs/strategy-research.md`, the hypothesis-cited specs, `specs/point-in-time-universe.md`, `specs/first-run-on-stack-machine.md`.
* **Commit identity** (CI-enforced): the owner's git identity, no Claude trailers, even if a harness suggests them.

## Dependencies

* **Needs:** `living-docs-system-and-contracts`, `living-docs-ingestion`, `living-docs-core-hub`, `living-docs-research`, `living-docs-strategy-and-dashboard`, `living-docs-operations` and `living-docs-engineering-workflow` merged into the integration branch (IDs and owner files exist; check D can resolve every ID cited here); `docs-check-tooling` (check L budgets and `CLAUDE.md` rule, check D); the `CHOICE` answering the agent-instruction-files entry. If the owner chooses its option b (`AGENTS.md` only, no `CLAUDE.md`), this spec deletes the `CLAUDE.md` files instead of reducing them, adds a minimum Claude Code version (≥ 2.1.277) to `SETUP.md` via `legacy-docs-retirement`, and the load check adds a cell with a `CLAUDE.local.md` present to show the failure mode.
* **Hands to:** `legacy-docs-retirement` (extend `test_docs_never_offer_down_v_as_a_fix` to `AGENTS.md`, `services/*/AGENTS.md`, `docker/AGENTS.md`; repoint `README.md:81` "CLAUDE.md … auto-loaded"; the root README links the kill-switch command in `services/strategy/AGENTS.md` instead of owning it); `living-docs-cutover` (the recorded load check is a final-gate item; enforcement of check L turns on; `TODO.md:5` and the `check_commit_identity.sh:4` comment, see §7).

## Affected files

| Path | Action |
|---|---|
| `AGENTS.md` | create |
| `services/AGENTS.md`, `services/core-hub/AGENTS.md`, `services/ingestion-scraper/AGENTS.md`, `services/backtesting/AGENTS.md`, `services/strategy/AGENTS.md`, `services/backup/AGENTS.md`, `services/dashboard/AGENTS.md`, `docker/AGENTS.md` | create |
| `CLAUDE.md`, `services/CLAUDE.md`, `services/core-hub/CLAUDE.md`, `services/ingestion-scraper/CLAUDE.md`, `docker/CLAUDE.md` | modify (content becomes `@AGENTS.md`) |
| `services/backtesting/CLAUDE.md`, `services/strategy/CLAUDE.md`, `services/backup/CLAUDE.md`, `services/dashboard/CLAUDE.md` | create (`@AGENTS.md`) |
| `TODO.md` | modify (this spec's own row only: status `done`, link to `specs/done/`) |
| `specs/agent-instruction-hierarchy.md` → `specs/done/agent-instruction-hierarchy.md` | move (Status `done`), in this spec's own PR, after the Mac record |
| `.github/scripts/check_commit_identity.sh`, active and hold specs | untouched (see §7) |
| `DECISIONS.md` | modify (append the load-check `VERIFIED` entry) |
| `docs/**` | untouched, cited by ID |
| `README.md`, `SETUP.md`, `VERSIONS.md`, `docker/README.md`, service READMEs | untouched (`legacy-docs-retirement`) |
| `services/ingestion-scraper/tests/unit/test_stack_persistence_config.py` | untouched; must keep passing |

## Required tests

`python3 -m tools.docs_check` and its flags are created by `docs-check-tooling`. Each check fails on any finding line for an agent file, or on the stated condition.

**Checker assertions:**

* `agent_files_within_budget` — check L: root ≤ 6 KB, each nested ≤ 3 KB, every root → leaf chain ≤ 16 KB.
* `claude_md_is_agents_import_only` — check L: every `CLAUDE.md` is exactly its `AGENTS.md` chain imports, root first, is ≤ 512 B, and contains no must/never/always.
* `no_at_import_in_agents_md` — check L: no `AGENTS.md` has an `@` immediately followed by a path ending in a file extension, at line start or after whitespace. The root opening line "Nothing is imported into this file" passes.
* `agent_file_ids_and_headings_resolve` — check D reports nothing for agent files: every `NS-NNN`/`INV-N` cited resolves; no placeholder; no register number.
* `agent_file_paths_exist` — checks A and B report nothing for agent files: every backticked path and link exists.

**Spec-specific checks:**

* `every_agents_md_has_a_claude_md_pair` — for each of the nine directories, both files exist, and no other `AGENTS.md` or `CLAUDE.md` is tracked (`git ls-files '*AGENTS.md' '*CLAUDE.md'` lists exactly 18 paths).
* `root_agents_md_has_routing_line` — `grep -cxF "Before editing under a directory that has its own \`AGENTS.md\`, open that file: it lists that directory's commands and the owner docs." AGENTS.md` is 1.
* `agent_file_first_lines_are_the_load_check_headings` — `head -1` of each `AGENTS.md` equals the heading in §5 (root: `# Auspex — agent instructions`). The Mac check depends on these.
* `agent_file_ids_are_active` — for every ID token in an agent file, its anchor `<a id="ID">` is found in `docs/` above that file's `## Retired requirements` heading (the DoD snippet). Fails on a reference to a retired ID.
* `every_hard_rule_lands_in_agents_md` — for each row of the hard-rule landing table in §4, `grep -cF '<phrase>' <file>` is at least 1 Fails if a rule moved out of a `CLAUDE.md` did not land.
* `todo_and_versions_not_imported` — `git grep -n '^@' -- '*CLAUDE.md' '*AGENTS.md'` lists only `<dir>/CLAUDE.md:<n>:@AGENTS.md` lines with an optional `../` prefix (the chain imports).
* `nested_agents_md_has_only_allowed_sections_and_id_bullets` — for each nested file: every H2 is in {Owners, Commands, Layout, Requirements that bite here, Trap pointers}, and every bullet under the last two starts with an ID matching the checker's ID regex.
* `no_invariant_text_restated_in_agent_files` — for N in 1–15, the text of `INV-N` from `docs/system/invariants.md` (first 40 characters after the em dash) does not occur in any agent file.
* `every_claude_md_section_has_a_destination` — every `## ` heading of `git show e51f742:CLAUDE.md` appears in the destination table of §6 of this spec, and every destination file named there exists.
* `matrix_claude_rows_resolved` — every matrix row whose Source is a `CLAUDE.md` path has a Target that exists; rows with disposition move/ratify/divergent/retire pass check M in their domain (`python3 -m tools.docs_check --matrix specs/living-docs-cutover-matrix.md --domain <NS>` for each NS that holds such rows). Passed before the cutover removed check M; the cutover's own decisions and per-namespace runs cover it afterwards, and the matrix is now `specs/done/living-docs-cutover-matrix.md`.
* `down_v_in_agent_files_warns` — `git grep -n 'down -v' -- '*AGENTS.md'` prints nothing, or every printed line contains "destroys all data".
* `no_spec_cites_a_claude_md_section` — `grep -nE 'CLAUDE\.md' specs/*.md specs/hold/*.md` prints nothing outside this exemption list: `specs/README.md`, `specs/_template.md`, `specs/docs-check-tooling.md`, `specs/living-docs-system-and-contracts.md`, `specs/living-docs-ingestion.md`, `specs/living-docs-core-hub.md`, `specs/living-docs-research.md`, `specs/living-docs-strategy-and-dashboard.md`, `specs/living-docs-operations.md`, `specs/living-docs-engineering-workflow.md`, `specs/agent-instruction-hierarchy.md`, `specs/legacy-docs-retirement.md`, `specs/living-docs-cutover.md`, `specs/living-docs-cutover-matrix.md`, `specs/living-docs-cutover-design.md`.
* `doc_reading_tests_still_pass` — `cd services/ingestion-scraper && uv run pytest tests/unit/test_stack_persistence_config.py -q` passes, same count as before.
* `commit_identity_check_unchanged` — `git diff -I '^#' origin/develop -- .github/scripts/check_commit_identity.sh` prints nothing (the cutover repoints the line-4 comment, so comment lines are ignored).
* `service_commands_run` — each command in the Commands sections of the Python and dashboard `AGENTS.md` files runs and reports a non-zero test count (Gradle commands proven in CI where Maven Central is unreachable; say so in the PR).
* `load_check_recorded` — `grep -c '^## .* — Living docs — VERIFIED — agent instruction loading on the stack machine$' DECISIONS.md` is 1, and the entry has 28 cell lines all marked pass. Run on the Mac; it is the last item before the spec is done.

**Seeded defects** (run once on a copy of the tree under `${TMPDIR:-/tmp}`, never committed or pushed): add a 7 KB root file, an `@TODO.md` line, a `CLAUDE.md` with a second line "always run tests", a nested bullet without an ID, a reference to a retired ID, and a root `AGENTS.md` with the `Co-Authored-By` rule deleted; each must make the corresponding check fail.

## Definition of done

Cloud part (in the integration branch checkout):

```bash
python3 -m tools.docs_check | grep -E '^[A-Z][0-9]? ([^ ]*/)?(AGENTS|CLAUDE)\.md' ; test $? -eq 1 && echo AGENTS-CLEAN
test "$(git ls-files '*AGENTS.md' '*CLAUDE.md' | wc -l)" -eq 18 && echo PAIRS-OK
git grep -n '^@' -- '*CLAUDE.md' '*AGENTS.md' | grep -v -E 'CLAUDE.md:[0-9]+:@(\.\./)*AGENTS.md$' ; test $? -eq 1 && echo IMPORTS-OK
for d in . services services/core-hub; do wc -c < $d/AGENTS.md; done | awk '{s+=$1} END {print (s<=16384 ? "CHAIN-OK " s : "CHAIN-OVER " s)}'
while IFS='|' read -r phrase file; do grep -qF -- "$phrase" "$file" || echo "MISSING $file: $phrase"; done <<'EOF'
executes zero tests is a failure|AGENTS.md
UP-TO-DATE|AGENTS.md
Never push to `develop` or `main`|AGENTS.md
Merge only when the owner says so|AGENTS.md
Co-Authored-By|AGENTS.md
Generated with Claude Code|AGENTS.md
subject line only, lowercase|AGENTS.md
__pycache__/|AGENTS.md
plan-step|AGENTS.md
Cloud sessions have no Docker|AGENTS.md
no hand-run setup or data scripts|AGENTS.md
stop, append to `DECISIONS.md`, and ask|AGENTS.md
unless its tests ran and passed|AGENTS.md
Docs unchanged:|AGENTS.md
docs/engineering/conventions.md|services/AGENTS.md
EOF
echo HARD-RULES-CHECKED
python3 - <<'EOF'
import glob, re, subprocess
files = subprocess.run(['git', 'ls-files', '*AGENTS.md'], capture_output=True, text=True).stdout.split()
ids = {m for f in files for m in re.findall(r'\b(?:INV-\d+|[A-Z]{3}-\d{3})\b', open(f).read())}
retired = set()
for d in glob.glob('docs/**/*.md', recursive=True):
    t = open(d).read()
    if '## Retired requirements' in t:
        retired |= set(re.findall(r'<a id="([^"]+)"', t.split('## Retired requirements', 1)[1]))
bad = sorted(ids & retired)
print('RETIRED-IDS ' + ' '.join(bad) if bad else 'IDS-ACTIVE')
EOF
(cd services/ingestion-scraper && uv run pytest tests/unit/test_stack_persistence_config.py -q | tail -1)
```

Expected: `AGENTS-CLEAN`, `PAIRS-OK`, `IMPORTS-OK`, `CHAIN-OK <bytes>`, `HARD-RULES-CHECKED` with no `MISSING` line above it, `IDS-ACTIVE`, and `N passed` with 0 failed.

Mac part: the `DECISIONS.md` entry `## <date> — Living docs — VERIFIED — agent instruction loading on the stack machine` exists with all 28 cells passing (`grep -c` = 1). Then, as commits on this spec's branch in the same PR into the integration branch: Status `done`, move this file to `specs/done/`, update this spec's `TODO.md` row. The PR merges only after that, like every other part.

## Compatibility

* **Claude Code.** `CLAUDE.md` still exists at every level that had one, so Claude Code of any version keeps loading instructions; `@AGENTS.md` expands to the same content Codex reads. A personal `CLAUDE.local.md` keeps working (appended after `CLAUDE.md`).
* **Codex.** Gains instructions it never had. From the root it sees only root `AGENTS.md`; the routing line sends it to nested files before editing.
* **Readers and links.** Paths of the existing `CLAUDE.md` files do not change, so inbound mentions still resolve; their content now points at `AGENTS.md`. Archived specs citing "root `CLAUDE.md`, <section>" are history and keep their text.
* **"Invariant N" citations** resolve to `docs/system/invariants.md` (check D alias), with the same numbers.
* **Tests and CI.** `test_docs_never_offer_down_v_as_a_fix` keeps passing (no `down -v` left in `CLAUDE.md` files). The commit-identity check is unchanged in behaviour.
* **Context cost.** Claude's launch load drops from about 68.8 KB to the root `AGENTS.md` (≤ 6 KB) plus whatever it opens.

## Rollback

On the integration branch: revert the range `<integration-branch tip before this spec's merge>..<tip after it>` in one commit, in a PR into the integration branch, keeping `DECISIONS.md` as it is (revert every other path). That restores the five `CLAUDE.md` files with their `@TODO.md`/`@VERSIONS.md` imports and removes the `AGENTS.md` files and the four new `CLAUDE.md` files. The `docs/` owners stay, so no rule is lost; the old `CLAUDE.md` text simply duplicates them again. The `VERIFIED` entry in `DECISIONS.md` stays (append-only) and a short `FLAG` entry records the revert. Nothing reaches `develop` before the cutover.

## Notes

* **The routing line carries more than the nested-file rules admit.** Nested-file rule 4 says nothing a change must obey lives only in a nested file, yet the service commands are, by design, only there. (The per-stack comment form is not: ENG owns it in `docs/engineering/conventions.md`, and `services/AGENTS.md` only points to it.) The routing line is what makes this safe for a root-launched Codex session; P4 is the check.
* **Stale pointers left to their owners** (§7): `TODO.md:5` and the `check_commit_identity.sh:4` comment stay until `living-docs-cutover` edits them. They are wrong in wording only; neither changes what an agent does.
* **P1 wording.** Claude may list the literal `@AGENTS.md` line of each `CLAUDE.md` as well as the imported heading. Both forms pass as long as no `TODO.md`/`VERSIONS.md` content and no out-of-chain file appears.
* **Codex version.** The loader facts were read at Codex `rust-v0.159.2`. If the Mac runs a different version, record it; a failed P1 or P5 on the core-hub launch is the signal that discovery or truncation changed.
* **User-level files count toward Codex's budget.** If `~/.codex/AGENTS.md` is large, the 16 KB chain limit still leaves about 16 KB for it; record its size so a later truncation can be explained.
* **The `VERIFIED` heading** is defined by this spec, not by the rollout's `PENDING` entries; `living-docs-cutover` lists it among the spec-defined headings it expects.
* **As built: branch.** The work is on `feature/living-docs-agent-instructions`, cut from `feature/living-docs-strategy-and-dashboard` @ `144e759` (the last domain part, holding every owner doc this spec cites) instead of from the integration branch, and the Branch field above names it. Before the Mac check it is rebased onto `feature/living-docs-integration` as §8 says.
* **As built: decision citations.** The `Docs unchanged:` hard rule in root `AGENTS.md` cites the answer, `## 2026-10-17 — Living docs — CHOICE — docs impact field and Docs unchanged line` (the recorded default, "yes"), not the `PENDING` entry it answers. The structure follows `## 2026-10-17 — Living docs — CHOICE — agent instruction files` (option A: `AGENTS.md` canonical at each level, every `CLAUDE.md` only `@AGENTS.md`, nothing imported into `AGENTS.md`, `TODO.md` and `VERSIONS.md` no longer auto-loaded).
* **As built: trap pointers without an ID of their own.** Every bullet under `Trap pointers` starts with an ID, but several traps sit in a doc's Known traps with no ID. Each pointer starts with the requirement the trap protects and names the doc's Known traps: ENG-053 for the Gradle 9 configuration cache and the Boot 4 versus 3.x trap (`docs/engineering/conventions.md`), ING-030 for `strftime` on a non-UTC datetime, OPS-057 for Grafana `$$`, OPS-037 for the Fernet key, OPS-011 for the slow Airflow healthcheck, EVA-001 for the raw-bytes hash, RES-001 for yfinance.
* **As built: content added after `e51f742`.** Root `CLAUDE.md` gained a "Regenerate raw pointer fixture" command and `services/CLAUDE.md` a raw-pointer fixture paragraph after this spec was written. The command is in the scraper `AGENTS.md` Commands; the rule is CON-007, cited in `services/AGENTS.md`.
* **As built: no "sockets disabled" layout note.** `services/ingestion-scraper/CLAUDE.md` said `pytest-socket` disables sockets in the unit suite, but ENG-004 records that suite as `divergent` (no socket guard there). The scraper `AGENTS.md` cites ENG-004 instead of repeating the claim.
* **As built: commands that cannot run in a cloud session.** Every Python and dashboard command was run. The Gradle commands need JDK 25, which cloud sessions lack (and Maven Central is rate-limited there), so `services/core-hub/AGENTS.md` says CI proves them. Integration suites need Docker and are marked "(CI)", and so is the scraper's full `uv run pytest -q`, whose only failures without Docker are its integration tests. The kill switch needs the stack's MinIO and is marked "(Mac)"; its `--help` runs. `npm run test:bundle` needs the server-only variables set at build time, and the dashboard `AGENTS.md` names the workflow that sets CI's sentinel values. The cloud session ran Node 22, not the pinned 24.
* **As built: where the spec's checks live.** The spec-specific checks were run from a script kept outside the repository, with the definition-of-done block, since this spec changes no file but the agent files, its `TODO.md` row and itself. `every_claude_md_section_has_a_destination` matches a heading to §6 after dropping its parenthetical and a leading "The" ("Rule that matters most", "Naming").
* **As built: root `AGENTS.md` extras.** "Where things are" also lists `docs/HISTORY.md` (from the old file map), and the hard rules carry two lines of the old Git section the landing table does not list: cloud sessions cannot delete GitHub branches, and GitHub comments stay rare.
* **As built: after the cutover prep.** The Mac check runs on `feature/living-docs-cutover-prep`, and two required checks were reworded for the state after the cutover: `matrix_claude_rows_resolved` records that it passed before check M was removed, and `commit_identity_check_unchanged` ignores the comment line the cutover repoints.
* **As built: chain imports after the first Mac check.** The first load check on 2026-10-24 passed 27 of 28 cells: Claude Code launched in `services/core-hub/` loaded the parent `CLAUDE.md` files but did not expand their `@AGENTS.md`, so the root and `services` files never loaded. Each nested `CLAUDE.md` now imports its whole chain (`## 2026-10-24 — Living docs — FLAG — nested CLAUDE.md imports only expand in the launch directory`), check L requires exactly that chain, and the failed cell is re-run before the `VERIFIED` entry. Codex's P5 at the root is counted a pass when it quotes the line it already read in P4, as for Claude.

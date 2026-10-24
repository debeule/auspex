# Auspex — agent instructions

Canonical for every coding agent. Claude Code reads it through `CLAUDE.md`; Codex reads it directly. Nothing is imported into this file: open the paths named below when you need them.

Before editing under a directory that has its own `AGENTS.md`, open that file: it lists that directory's commands and the owner docs.

## Authority

- `docs/` is approved current behaviour, one owner per requirement, IDs like `ING-NNN`; `docs/README.md` maps domains to owners. The invariants are INV-1 to INV-16 in `docs/system/invariants.md`.
- `specs/` holds proposed changes; each governs only its own work until merged. `specs/done/` is history, never authority.
- Values live in machine-readable files; docs explain them and never copy them.
- On a conflict follow the conflict policy in `docs/engineering/change-workflow.md` (ENG-023, ENG-024). Never edit a doc to match code without the owner's decision; agent files never win against `docs/`.
- A brief, note or memory from outside the repo names the `develop` commit it was written against. If HEAD has moved, re-read what it cites.

## Session start

1. The work is the spec you were assigned. With none, open `TODO.md` and take the first `ready` spec; with none ready, scope a `draft` (`specs/README.md`).
2. Read the spec in full, then every `docs/` file its Docs impact names.
3. **The rule that matters most.** A green suite is necessary, not sufficient. Before writing a test, check it against those requirements. If it can only pass by violating one, stop, append to `DECISIONS.md`, and ask. Do not write it. The story behind this rule is in `docs/engineering/verification.md` (Rationale).
4. If a task seems to need an invariant broken (`docs/system/invariants.md`), stop and flag the same way.
5. Work only that spec, and update it as items complete; finishing it is ENG-016.
6. If you stop before it is done, append a `## Handoff` block to the spec (ENG-028 in `docs/engineering/change-workflow.md`).

## Hard rules

- A test run that executes zero tests is a failure, not a pass: read the reported test count.
- Gradle reports `UP-TO-DATE` and runs nothing when inputs are unchanged. To prove a test ran, use `--rerun-tasks` or read the count in `build/reports/tests/`.
- Test-first is INV-15. The TDD loop, merge bar and mutation check are ENG-001, ENG-002, ENG-010 and ENG-011 in `docs/engineering/verification.md`.
- Never push to `develop` or `main`: push the spec's feature branch and open a PR. Merge only when the owner says so; the merge recipe is ENG-030.
- Commits carry the git identity of the person driving the work, as author and committer, never Claude's or a tool's default. No `Co-Authored-By`, `Claude-Session` or other Claude trailers; the Commit identity check (`.github/scripts/check_commit_identity.sh`) fails a PR that has one.
- No Claude footers on GitHub: leave "Generated with Claude Code" and claude.ai session links out of PR bodies and comments, and check the PR body after creating it. Keep GitHub comments rare.
- Commit messages are a subject line only, lowercase, `subject: detail1, detail2`, with no body.
- No plan-step names (`step_3_2`, `phase_2`) in files, functions, tests, variables, branches or commit messages (ENG-049).
- Never commit `.env`, `target/`, `.venv/`, `__pycache__/` or Docker volumes.
- A behaviour change updates its owning doc in the same PR; otherwise the PR body says `Docs unchanged: <domain> — <reason>` (`## 2026-10-17 — Living docs — CHOICE — docs impact field and Docs unchanged line`).
- Cloud sessions have no Docker, sec.gov or Yahoo: container tests are proven in CI, and the PR says so. They cannot delete GitHub branches, so push none you will want gone. Work that only the owner's Mac can run goes in a spec the owner runs there (`specs/first-run-on-stack-machine.md`).
- There are no hand-run setup or data scripts: startup data is a compose one-shot that is a no-op when the data exists, current data an Airflow DAG calling a service API (OPS-009). A step that cannot be automated (a secret, a host install, a sign-off) goes in `SETUP.md`.

## Where things are

| What | Path |
|---|---|
| Work queue (open at session start) | `TODO.md` |
| Spec format | `specs/README.md` |
| Requirements, by domain | `docs/README.md` |
| Process detail: verification, change workflow, conventions | `docs/engineering/` |
| What the system is, naming | `README.md`, `docs/system/overview.md` |
| Pinned versions (open only when touching a dependency) | `VERSIONS.md` |
| Decisions: read before flagging, append when you flag, heading `## YYYY-MM-DD — <topic> — TYPE — <title>` | `DECISIONS.md` |
| Stack commands: compose up and down, smoke test, restore | `README.md` |
| Service commands | the service's `AGENTS.md` |
| Manual setup steps, in order | `SETUP.md` |
| Outstanding credentials and user decisions | `docs/PREREQUISITES.md` |
| Restoring a backup | `docs/backup-restore.md` |
| Local extraction model | `docs/local-model-runbook.md` |
| Completed phases 0–3 | `docs/HISTORY.md` |

## Tone

Do not report a step complete unless its tests ran and passed. If something is blocked, say so plainly in `DECISIONS.md` and stop; never work around an invariant to keep moving.

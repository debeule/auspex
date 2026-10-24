# Living docs cutover

> Archived. Not authoritative: current behaviour is in docs/ (see docs/README.md).

**Status:** done
**Blocked by:** `docs-check-tooling`, `living-docs-system-and-contracts`, `living-docs-ingestion`, `living-docs-core-hub`, `living-docs-research`, `living-docs-strategy-and-dashboard`, `living-docs-operations`, `living-docs-engineering-workflow`, `agent-instruction-hierarchy`, `legacy-docs-retirement` (all merged into the integration branch); the owner's answers to every `DECISIONS.md` heading listed under `## Blocking decisions` below; an approving `CHOICE` for each `… — Living docs — PENDING — <domain> ratification batch` entry.
**Branch:** `feature/living-docs-integration` (the integration branch itself; this spec runs on it)
**Docs impact:** activates `docs/` as the canonical authority. Creates no requirement; applies the owner's answers to requirements the part specs already wrote (step 3). Changes `TODO.md`, `DECISIONS.md` and every `specs/done/*.md` (one archive banner line each).

---

## Context

At `develop` @ `e51f74201fda30dd9a28af318cc74b824e39dafc` (2026-10-15):
- The normative text lives in:
  - `docs/requirements.md` (39 KB);
  - root `CLAUDE.md` (26 KB: 15 invariants, known traps, process rules);
  - four nested `CLAUDE.md` files;
  - service READMEs;
  - archived specs;
  - 117 `CHOICE` entry headings in `DECISIONS.md`. That count excludes code fences; a plain `grep -c '^## .*CHOICE'` gives 118 because it also matches the format template near the top.
- There is no `AGENTS.md`, no docs checker and no PR template.

The rollout converts the whole repository in one coordinated change:
- Ten part specs each build one part on their own branch.
- Each part merges into `feature/living-docs-integration`, never into `develop`.
- This spec reconciles the integration branch with whatever reached `develop` in the meantime, applies the owner's decisions, runs the final gate and activates the new authority with one fast-forward of `develop`.

Two companion files are committed with this spec and archived with it:
- `specs/living-docs-cutover-design.md` is the design: docs tree, ID scheme, living-spec template, authority and conflict policy, lifecycle and checker design. Checks E and J skip it, since it is a companion, not a spec.
- `specs/living-docs-cutover-matrix.md` is the migration matrix:
  - one row per normative unit of the old texts;
  - a decisions table classifying every `CHOICE` heading;
  - the part specs fill its `ID` cells.

What the new authority consists of once all ten parts have merged into the integration branch:

| Part | Where |
|---|---|
| Living specs | `docs/README.md`, `docs/system/`, `docs/ingestion/`, `docs/core-hub/`, `docs/research/`, `docs/strategy/`, `docs/dashboard.md`, `docs/operations/`, `docs/engineering/` |
| Agent files | Root and nested `AGENTS.md`; each `CLAUDE.md` is `@AGENTS.md` |
| Checker | `tools/docs_check/`, `docs-check.toml`, `.github/workflows/docs.yml` (report-only until this spec) |
| Legacy | `docs/requirements.md` as a § → ID index; READMEs trimmed to links |

Each part spec moves itself to `specs/done/`, sets its Status to `done` and updates its own `TODO.md` row, in its own PR into the integration branch. When this spec starts, the ten part specs are already archived.

## What this builds

When this spec is done:
- `develop` carries the living documentation as the only prose authority.
- Every agent reads it through `AGENTS.md`.
- CI enforces the deterministic checks on every PR.
- The old texts no longer hold requirements.
- One tagged commit allows the whole change to be reverted by one PR.

Steps, in order:

1. **Freeze.** The owner announces the merge freeze: all merges to `develop` are paused from step 2 to step 8 (`DECISIONS.md` heading `2026-10-15 — Living docs — PENDING — merge freeze around the cutover`).
2. **Reconciliation pass.** Rebase `feature/living-docs-integration` onto `origin/develop`. This is allowed only once every part spec has merged into it. Then:
   - For every commit in `<[rollout] base>..origin/develop` (`base` is read from `docs-check.toml`), map the touched paths to owners with `python3 -m tools.docs_check --owners <path>`.
   - Port any change to an old authority file (`docs/requirements.md`, `CLAUDE.md`, a README) into its owner doc. Keep the integration branch's version of the old file.
   - Add `Docs impact` to new active specs.
   - Classify any new `CHOICE` heading in the matrix decisions table, and fill its `IDs` cell when it is binding.
   - Log each item in `## Reconciliation log` below.
   - Set `[rollout] base` to the new `origin/develop` SHA.
   - Check `DECISIONS.md`, `TODO.md` and the matrix for duplicated or out-of-order rows (`union` merge driver).
3. **Decision application.** The owner appends every answer, including each `## <date> — Living docs — CHOICE — <domain> ratification batch`. For every such `CHOICE` in answer to a Living docs PENDING heading or a ratification batch:
   - Find the rows that cite it: `grep -rn '<heading suffix>' docs/ specs/living-docs-cutover-matrix.md`.
   - **If the chosen option is the recorded default:**
     - set each verification row's status from `pending-decision` to the real status the part spec prepared (`tested`, `enforced`, `untested` or `divergent`);
     - add the `CHOICE` heading to the row's `Source` cell, next to the PENDING heading.
   - **If the owner chose another option:**
     - rewrite the affected requirement text in its owner doc to that option;
     - set the status the same way;
     - log the edit in `## Reconciliation log`.

     This is the one place this spec writes requirement text.
   - **For a ratification batch:** flip every row the batch lists to its real status, the same way.
   - **Processing time in as-of decisions:** if that `CHOICE` adopts the invariant, write it as the sixteenth invariant (the next free number in the invariant namespace) in `docs/system/invariants.md` with the `CHOICE` as Source and a verification row, and fill the `ID` cells of matrix rows M-INV-036 and M-INV-042. Otherwise the STR and RES requirements stay the only home of the rule.
   - This includes the exception lines under INV-1, INV-4 and INV-15, which `living-docs-system-and-contracts` writes as `pending-decision` until their headings are answered.
   - Replace any remaining `<NS>-?` placeholder or planned-domain link with its final ID or path. The research and strategy PRs list the file-level cross-domain links they used in place of IDs that did not exist yet; narrow each to the ID.
4. **DECISIONS absorption audit.** Every `^## .*CHOICE` heading outside code fences in `DECISIONS.md` must appear in the matrix decisions table, classified as one of:
   - **binding:** its `IDs` cell names at least one ID whose `Source` cites the heading;
   - **history:** no ID needs it.
5. **Archive banners.** Insert one line after the title of each `specs/done/*.md` that has no banner: `> Archived. Not authoritative: current behaviour is in docs/ (see docs/README.md).`
   - This is the only edit to archived specs (`DECISIONS.md` heading `2026-10-15 — Living docs — PENDING — archive policy for specs/done`).
   - It covers the ten part specs archived by their own PRs, and any spec archived on `develop` during the rollout.
6. **Final gate.** Run the gate block under Definition of done and paste its output into the PR. Everything in it must hold. In addition:
   - The manual load check from `agent-instruction-hierarchy` is recorded in `DECISIONS.md` for Claude Code and for Codex, each launched at the repository root and in `services/core-hub/`.
   - All existing workflows (`python.yml`, `java.yml`, `dashboard.yml`, `commit-identity.yml`) are green on the integration head.
   - One independent review of the integrated tree has no open blocker. It is done by a session that wrote no part, and confirms by sampling, citing `path:line`, that ten requirements per domain match the code.
7. **Enforcement commit.** One commit on the integration branch that:
   - removes `continue-on-error: true` from `.github/workflows/docs.yml`;
   - removes `feature/living-docs-integration` from the branch lists of `docs.yml` and `commit-identity.yml`;
   - removes check M and its tests from `tools/docs_check/`, and the `[rollout]` table from `docs-check.toml` (both are rollout-only);
   - moves this spec, `specs/living-docs-cutover-matrix.md` and `specs/living-docs-cutover-design.md` to `specs/done/`, each with the archive banner, and sets this spec's Status to `done`;
   - points this spec's `TODO.md` row at `specs/done/living-docs-cutover.md` with status `done`, and adds a `draft` row for a later docs drift audit spec;
   - rewrites `TODO.md` line 5 to "**Session start:** see root `AGENTS.md` (the spec you were assigned, else the first `ready` spec)." so it no longer contradicts the agent files;
   - repoints the comment on line 4 of `.github/scripts/check_commit_identity.sh` from "root CLAUDE.md, Git" to "root AGENTS.md, Hard rules" (comment only, no behaviour change).

   Then re-run `python3 -m tools.docs_check --base origin/develop`; it must exit 0.
8. **Activation**, with the owner's word and the project merge recipe:
   1. `git fetch origin develop && git rebase origin/develop`. This is a no-op inside the freeze; if it is not, go back to step 2.
   2. `git push --force-with-lease origin feature/living-docs-integration`, and open a PR from `feature/living-docs-integration` into `develop`.
      - The PR body carries the gate output, the clean-revert window (see Rollback) and the note on open PRs (see Compatibility).
      - CI, including `docs`, must be green.
   3. On the owner's "merge", tag and push the rollback point: `git tag pre-living-docs origin/develop && git push origin pre-living-docs`.
   4. `git checkout develop && git pull --ff-only && git merge --ff-only feature/living-docs-integration && git push origin develop`.
   5. Run the post-activation block under Definition of done.
9. **Post-cutover.**
   - The owner lifts the freeze.
   - Append `## <date> — Living docs — CHOICE — cutover complete` to `DECISIONS.md`, with the tag, the cutover tip SHA and the gate output. Commit it on a short branch off `develop` and merge it the normal way.
   - Making `docs` a required status check is the owner's branch-protection setting, not part of this spec.

## Out of scope

- Writing living-doc requirements beyond step 3. The ten part specs own the text. Reconciliation only ports deltas that reached `develop`, and decision application only applies the owner's answers.
- Fixing any defect the docs record as `divergent` (raw-pointer contract, as-of docstring, unwired risk layer and the others). Those are separate fix specs (`DECISIONS.md` heading `2026-10-15 — Living docs — PENDING — defects found while scoping`).
- Moving or renaming `frozen_paths`:
  - `SETUP.md`, `VERSIONS.md`;
  - `docs/requirements.md`, `docs/backup-restore.md`, `docs/strategy-research.md`, `docs/local-model-runbook.md`;
  - the hypothesis-cited specs, `specs/point-in-time-universe.md`;
  - the docs read by tests.
- Branch protection settings and deleting branches.
- Check I (archive immutability) and the docs drift audit itself.

## Constraints

- **Invariants.** This spec changes none. It must not edit `config/hypotheses/*`, `config/universe/*`, Flyway migrations or any application code. The only test change in the rollout belongs to `legacy-docs-retirement`.
- **Git.**
  - Integration and `develop` merges happen only on the owner's word, by local rebase and fast-forward. Never use GitHub's merge button.
  - No force push to `develop`. `--force-with-lease` only on the integration branch.
  - No commit authored by Claude, and no Claude trailers. `commit-identity.yml` must pass.
  - No scratch branch is pushed. Tests that need a deliberate defect run in a disposable local worktree under `${TMPDIR:-/tmp}`, and nothing broken is committed.
- **Concurrent changes.**
  - The integration branch is rebased onto `develop` only after every part spec has merged into it, so no open part branch needs `rebase --onto`.
  - Part branches merge into the integration branch one at a time, each rebased onto its tip first.
  - The matrix decisions table has rows that several domains fill. When two part specs both add IDs to one `IDs` cell, resolve the rebase conflict by keeping both sets, space-separated.
- **`DECISIONS.md` is append-only.** No step and no rollback deletes an entry. A withdrawal is a new entry.
- **A green checker is necessary, not sufficient.** It proves structure, not that requirements match the code. The independent review in step 6 samples that against the code.

## Dependencies

- **Needs:**
  - all ten part specs merged into `feature/living-docs-integration`, each archived with its `TODO.md` row updated;
  - the owner's answers on the blocking PENDING headings;
  - the approved ratification batches;
  - the owner's freeze.
- **Hands on:**
  - an enforced `docs.yml`;
  - `docs/` as the authority;
  - the `pre-living-docs` tag for rollback;
  - a `draft` docs drift audit row.

## Affected files

| Path | Change |
|---|---|
| `.github/workflows/docs.yml` | modify (enforce; drop integration branch) |
| `.github/workflows/commit-identity.yml` | modify (drop integration branch) |
| `.github/scripts/check_commit_identity.sh` | modify (line-4 comment only) |
| `docs-check.toml` | modify (`[rollout] base` during reconciliation; remove `[rollout]` in step 7) |
| `tools/docs_check/` | modify (remove check M and its tests) |
| `docs/**` | modify (ported deltas, decision application and placeholder replacement only, each logged) |
| `specs/done/*.md` (53 files at e51f742, the ten part specs, any archived since) | modify (one banner line each where missing) |
| `specs/living-docs-cutover.md`, `specs/living-docs-cutover-matrix.md`, `specs/living-docs-cutover-design.md` | modify, then move to `specs/done/` |
| `TODO.md` | modify (line 5; this spec's row; drift audit draft row) |
| `DECISIONS.md` | append (cutover entries only) |
| `config/**`, `services/**/src/**`, Flyway files | untouched |

## Required tests

The gate block runs the first nine at step 6. The post-activation block runs the last three at step 8.5. Each fails as stated.

- `docs_check_exits_zero_on_integrated_tree`: `python3 -m tools.docs_check --base origin/develop` → exit 0. Fails on any finding from checks A–L, including a register number anywhere check D scans.
- `planned_domains_is_empty`: `python3 -c "import tomllib; print(tomllib.load(open('docs-check.toml','rb'))['rollout']['planned_domains'])"` prints `[]`. Fails while any domain is still planned, because planned-domain links are only notices.
- `every_matrix_row_has_a_defined_id_in_every_namespace`: `python3 -m tools.docs_check --matrix specs/living-docs-cutover-matrix.md --domain <NS>` exits 0 for each of `INV SYS CON ING EXT HUB COR RES EVA STR DSH OPS ENG`. Fails if a move, ratify, divergent or retire row has an ID that is not defined in `docs/`, or whose verification-table `Source` does not cite the row's source.
- `every_choice_heading_is_classified`: `python3 -m tools.docs_check --matrix specs/living-docs-cutover-matrix.md --decisions` → exit 0. Fails if a `CHOICE` heading is missing from the decisions table, or is binding without an ID whose `Source` cites it.
- `no_blocking_pending_decision_remains`: `python3 -m tools.docs_check --pending --blocking-list specs/living-docs-cutover.md` → exit 0. Fails if a verification row with status `pending-decision` cites a heading listed under `## Blocking decisions`.
- `every_ratification_batch_is_approved`: for each `$d` in `system engineering ingestion core-hub research strategy-and-dashboard operations`, `grep -c "^## .* — Living docs — CHOICE — $d ratification batch" DECISIONS.md` is at least 1, and `grep -rn "$d ratification batch" docs/ | grep -c pending-decision` is 0. Fails on an unapproved batch or an unflipped row.
- `archive_banner_on_every_done_spec`: `for f in specs/done/*.md; do sed -n 2,4p "$f" | grep -q '^> Archived. Not authoritative' || echo "$f"; done` prints nothing. Fails on any archived spec without the banner, or with the banner below line 4.
- `docs_workflow_fails_on_a_broken_link`:
  1. `git worktree add "${TMPDIR:-/tmp}/ld-enforce" HEAD`.
  2. Break one link in that worktree's `docs/README.md`.
  3. Run the checker command from `docs.yml` there. It must exit non-zero.
  4. `git worktree remove --force "${TMPDIR:-/tmp}/ld-enforce"`.

  Nothing is committed or pushed. Run it again after the step-7 commit, together with `grep -n continue-on-error .github/workflows/docs.yml`, which must print nothing.
- `rollback_revert_applies_cleanly`: in a disposable worktree at the integration head:
  1. `git revert --no-commit origin/develop..HEAD`
  2. `git checkout HEAD -- DECISIONS.md`
  3. `git diff origin/develop -- . ':!DECISIONS.md'` must be empty.
  4. Discard the worktree.

  Fails on a conflict or a residual diff. `origin/develop` is the integration base after the step-2 rebase.
- `archived_specs_changed_only_by_banner` (post-activation): `git diff --diff-filter=M pre-living-docs..origin/develop -- specs/done/ | grep '^[-+][^-+]' | grep -v '^+> Archived. Not authoritative'` prints nothing. Fails on any other edit to a spec already archived at the tag. Newly archived specs are additions or renames, which the filter excludes.
- `no_locked_or_application_file_changed` (post-activation): `git diff --stat pre-living-docs..origin/develop -- config/ 'services/*/src/' 'services/core-hub/src/main/resources/db/'` prints nothing.
- `develop_is_the_cutover_tip` (post-activation): `git rev-parse origin/develop` equals the integration head SHA recorded in the PR, `git merge-base --is-ancestor pre-living-docs origin/develop` succeeds, and the tag differs from `origin/develop`.

## Definition of done

**Gate block.** Run at step 6 on the integration head, with the matrix still at `specs/living-docs-cutover-matrix.md` and check M still present:

```bash
git fetch origin develop
python3 -m tools.docs_check --base origin/develop; echo "check exit=$?"
python3 -c "import tomllib; print('planned', tomllib.load(open('docs-check.toml','rb'))['rollout']['planned_domains'])"
for ns in INV SYS CON ING EXT HUB COR RES EVA STR DSH OPS ENG; do
  python3 -m tools.docs_check --matrix specs/living-docs-cutover-matrix.md --domain "$ns" >/dev/null || echo "FAIL $ns"
done
python3 -m tools.docs_check --matrix specs/living-docs-cutover-matrix.md --decisions; echo "decisions exit=$?"
python3 -m tools.docs_check --pending --blocking-list specs/living-docs-cutover.md; echo "pending exit=$?"
for d in system engineering ingestion core-hub research strategy-and-dashboard operations; do
  grep -q "^## .* — Living docs — CHOICE — $d ratification batch" DECISIONS.md || echo "UNAPPROVED $d"
done
for f in specs/done/*.md; do sed -n 2,4p "$f" | grep -q '^> Archived. Not authoritative' || echo "NO BANNER $f"; done
w="${TMPDIR:-/tmp}/ld-revert"; git worktree add -q "$w" HEAD && (cd "$w" && git revert --no-commit origin/develop..HEAD && git checkout HEAD -- DECISIONS.md && git diff --stat origin/develop -- . ':!DECISIONS.md'); git worktree remove --force "$w"
```

Expected:
- `check exit=0`, `decisions exit=0` and `pending exit=0`;
- `planned []`;
- no `FAIL`, `UNAPPROVED`, `NO BANNER` or diff-stat lines;
- `docs_workflow_fails_on_a_broken_link` recorded as red in the PR;
- the four existing workflows green on the integration head.

**Post-activation block.** Run at step 8.5 on a fresh `develop`:

```bash
git fetch origin develop --tags
python3 -m tools.docs_check --base origin/develop; echo "check exit=$?"
grep -n continue-on-error .github/workflows/docs.yml
git diff --diff-filter=M pre-living-docs..origin/develop -- specs/done/ | grep '^[-+][^-+]' | grep -v '^+> Archived. Not authoritative'
git diff --stat pre-living-docs..origin/develop -- config/ 'services/*/src/' 'services/core-hub/src/main/resources/db/'
git merge-base --is-ancestor pre-living-docs origin/develop && test "$(git rev-parse pre-living-docs)" != "$(git rev-parse origin/develop)" && echo "tag below develop"
```

Expected:
- `check exit=0`;
- no other output except `tag below develop`;
- CI on `develop` green, including `docs`.

## Compatibility

- **Links from history.** Citations of `docs/requirements.md §N` in archived specs and `DECISIONS.md` resolve through the § index.
- **Invariant numbers.** "Invariant N" keeps the root `CLAUDE.md` numbering (INV-1 to INV-15).
- **Frozen paths** stay where they are, so links and code references keep working.
- **Agents.**
  - A Claude Code session loads `CLAUDE.md`, which loads `@AGENTS.md`. A Codex session loads `AGENTS.md` directly.
  - A session started from an older brief that cites `CLAUDE.md` sections finds their content through `AGENTS.md`, then `docs/`.
- **Open PRs at cutover.**
  - The freeze ensures none merge mid-gate.
  - Afterwards, a PR opened before cutover must add a `Docs impact` field or a `Docs unchanged:` line before `docs` passes.
  - The cutover PR tells the owner this.
- **Tests that read docs:**
  - `test_docs_never_offer_down_v_as_a_fix` reads the extended file list.
  - `test_new_secrets_are_documented_in_setup` still reads `specs/first-run-on-stack-machine.md`.
  - The `VERSIONS.md` readers are unaffected.

## Rollback

- **Before step 8.4.** Abandon or leave the integration branch, and close the cutover PR without merging. `develop` is unchanged, and the old texts remain the authority.
- **After step 8.4.**
  1. If `docs` was made a required check, the owner removes that setting first.
  2. Open one PR from a branch off `develop` with one commit, `living docs rollback: revert to pre-living-docs`, made by:
     - `git revert --no-commit pre-living-docs..<cutover tip>`;
     - `git checkout HEAD -- DECISIONS.md`;
     - `git checkout HEAD -- services/dashboard/package.json services/dashboard/package-lock.json`, and keep the `next` row of `VERSIONS.md`, so the Next.js 16.4.2 security patch (`next security patch: next and eslint-config-next 16.4.2 for three critical advisories`, also in PR #79) is not reverted;
     - appending `## <date> — Living docs — FLAG — cutover rolled back` with the reason.

     No force push.
- **Clean-revert window.** The revert is clean only until the first post-cutover PR touches `docs/`, an agent file, a README or `TODO.md`. After that, either port those later changes back into the old files by hand, or forward-fix instead.
  - The cutover PR states this window.
  - The owner decides in `DECISIONS.md`, within the first two weeks, whether the rollout stands.
- **No data, schema or runtime rollback is needed:** there are no application code, configuration or migration changes. The one dependency change, the Next.js security patch, stays in place on a rollback.

## Blocking decisions

The final gate refuses a `pending-decision` row that cites any of these `DECISIONS.md` headings. All are dated 2026-10-15 and prefixed `Living docs — PENDING — `.

| Heading suffix |
|---|
| raw-pointer contract |
| as-of reads hide or raise |
| restore exception to invariant 2 |
| invariant 6 wording |
| spec paths cited by hash-locked hypotheses |
| code-done specs blocked on the Mac |
| fate of docs/requirements.md |
| agent instruction files |
| rollout branch model |

## Reconciliation log

| Date | develop commit or CHOICE heading | Paths | Owner doc(s) updated | Note |
|---|---|---|---|---|
| 2026-10-24 | none: `b7582c3..origin/develop` is empty | — | — | `origin/develop` is `b7582c3`, the `[rollout] base`, so there is no delta to port and the base stays; `DECISIONS.md`, `TODO.md` and the matrix have no duplicated headings or rows |
| 2026-10-24 | the seven `## 2026-10-24 — Living docs — CHOICE — <domain> ratification batch` entries (option A each) | `docs/**` verification tables; `docs/system/invariants.md` (INV-1 scope line, INV-4 and INV-15 exception lines); the retirement entries of `docs/core-hub/storage.md` and `docs/ingestion/connectors.md`, and the Known traps sources line of the latter | all owner docs | recorded defaults, so no requirement text changed: 80 `pending-decision` rows flipped (SYS 3, CON 2, ENG 37, ING 4, EXT 4, HUB 9, COR 2, OPS 7, RES 5, EVA 1, STR 3, DSH 3), and the CHOICE cited next to the PENDING heading on those rows and on the 16 rows already approved in part; RES-062, RES-082 and STR-007 become `divergent` as their batches state |
| 2026-10-24 | the 2026-10-17 `Living docs — CHOICE` entries ("defaults ok") | 12 verification rows and one rationale line citing `2026-10-15 — Living docs — PENDING — defects found while scoping` without its answer | core-hub, system, ingestion, engineering docs | the answering CHOICE added next to the PENDING heading; every other row already cited it |
| 2026-10-24 | `## 2026-10-17 — Living docs — CHOICE — processing time in as-of decisions` (option A) | `docs/system/invariants.md`, `docs/README.md`, root `AGENTS.md`, the STR-006 and RES-067 Source cells, matrix rows M-INV-036 and M-INV-042 | system | INV-16 written with the PENDING text as its statement and a verification row (`untested`, partial) |
| 2026-10-24 | 30 `CHOICE` headings without a decisions-table row | `specs/living-docs-cutover-matrix.md` | — | classified (23 binding, 7 history) by whether an ID's verification Source cites them; five existing rows whose headings contain a backtick rewritten with double backticks so check M reads them |

## Notes

- The independent review in step 6 replaces three post-integration reviews proposed earlier, which were cut as over-engineering. The specs themselves had three independent audits while they were scoped.
- If `tools.docs_check` reports a finding class during reconciliation that no part spec anticipated, fix it in the owning doc on the integration branch, log it, and re-run. Do not weaken the check.
- Other `DECISIONS.md` headings the part specs append, which this spec reads but does not answer:
  - the seven `PENDING — <domain> ratification batch` entries;
  - `VERIFIED — agent instruction loading on the stack machine` (`agent-instruction-hierarchy`), required at step 6;
  - `FLAG — invariant conflicts found while writing the system docs` and `FLAG — system docs withdrawn` (`living-docs-system-and-contracts`).

  A `FLAG — … withdrawn` entry means a part was rolled back and must be re-merged before the gate.
- Non-blocking PENDING headings (for example `initial_lookback value` or `fda_approval source`) may still be unanswered at cutover. Their rows stay `pending-decision` with the recorded default, and the docs say so.
- **As built: branch.** Steps 2–7 were prepared on `feature/living-docs-cutover-prep`, cut from `feature/living-docs-legacy-retirement` @ 73e2769, the tip of the stacked rollout parts, not on `feature/living-docs-integration` itself. Merging it into the integration branch, the freeze and step 8 are left to the owner.
- **As built: `agent-instruction-hierarchy` is not archived.** Its cloud part is merged in the stack, but the spec stays `blocked` in `specs/` until the Mac load check appends `VERIFIED — agent instruction loading on the stack machine`; that entry is the only gate item still open (step 6).
- **As built: real status of a ratified row.** No part spec recorded a status per row, so step 3 read it off each row's `Verified by` cell against the status table in `docs/README.md`: a named test with no stated gap → `tested`; a named machine check (a checker check, a workflow, build configuration, Flyway's checksum refusal) with no stated gap → `enforced`; nothing named, or a test or check the cell itself calls partial → `untested`; a rule the batch says the code does not meet (RES-062, RES-082, STR-007) → `divergent`, citing the batch. Judgement calls the owner may want to revisit: HUB-020 `enforced` (Flyway checksum), COR-004 and COR-013 `tested`, HUB-051 `untested` (the test reads only the Prometheus endpoint), ING-039 `tested` (`GET /metrics` is tested in `test_metrics.py`), ENG-012, ENG-017, ENG-020, ENG-024, ENG-025, ENG-027 and ENG-039 `untested` (their check covers only the clause in parentheses).
- **As built: INV-16 in the matrix.** M-INV-036 and M-INV-042 were `link` rows with NS `—`, which check M never reads. Filling their `ID` cell with `INV-16` also set Disposition `move`, Target `docs/system/invariants.md`, NS `INV` and Spec `living-docs-cutover`, so `--domain INV` now checks the ID. The Scope paragraph of `docs/system/invariants.md`, the `docs/README.md` index line and root `AGENTS.md` now say sixteen invariants; STR-006 and RES-067 keep their statements and point at INV-16 from their Source cells.
- **As built: decisions table.** The 2026-10-17 Living docs answers, the research-input-archive choice and the seven 2026-10-24 batch approvals had no decisions-table row; step 4 added 30 rows with `Fragment rows` "— (classified at cutover)". `trial ledger and holdout as untracked local files` is `history` because EVA-016 cites it in `Verified by`, not `Source`; the research-input-archive choice is `history` until that spec writes its IDs.
- **As built: banner layout.** Each banner sits on line 3, between the title and the next block with a blank line on each side, so the following `**Status:**` line is not swallowed into the blockquote. The only added non-blank line per archived spec is the banner, so `archived_specs_changed_only_by_banner` still holds; all 63 archived specs at 73e2769 and the three files archived here carry it.
- **As built: check M removal.** `tools/docs_check/checks/matrix.py`, `tools/docs_check/tests/test_matrix.py` (27 tests, including the two textual workflow tests that read the report-only flag and the integration branch) and the `--matrix`, `--domain`, `--decisions`, `--pending` and `--blocking-list` options went; the lines of `test_cli.py`, `test_valid_tree.py` and `test_references.py` that called those modes went with them. The checker suite is 117 tests, all green. The optional `[rollout]` support in `config.py` and its fixture stay: without the table the checker runs as if no domain were planned, which is the state the real `docs-check.toml` is now in.
- **As built: docs edits in the enforcement commit.** The four "design §n" notes now point at `specs/done/living-docs-cutover-design.md`, and the ENG-019 `Verified by` cell no longer says "report-only until the cutover".
- **As built: the drift audit row** in `TODO.md` has no link, since no spec file exists yet; check J reads only linked rows.
- **As built: Status `done` before activation.** Step 7 sets it, as written; steps 8 and 9 (the PR into `develop`, the `pre-living-docs` tag, the fast-forward, the post-activation block and the `cutover complete` entry) and the freeze of step 1 are the owner's and have not run.
- **Gate record (step 6), 2026-10-24, on `feature/living-docs-cutover-prep` before the enforcement commit:** `check exit=0`; `planned []`; no `FAIL` for any of the 13 namespaces; `decisions exit=0`; `pending exit=0`; no `UNAPPROVED` and no `NO BANNER` line; the revert in a disposable worktree applied cleanly with an empty diff stat against `origin/develop` (b7582c3) outside `DECISIONS.md`; `docs_workflow_fails_on_a_broken_link`: the docs check exits 1 with `A docs/README.md:19 broken link: system/no-such-file.md`. Not run here: the four existing workflows on the integration head (CI, nothing pushed), the independent review (needs a session that wrote no part), and the Mac load check, whose `VERIFIED` entry is not in `DECISIONS.md` yet.

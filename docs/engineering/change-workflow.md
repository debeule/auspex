# Change workflow

Domain: ENG · Code: `specs/`, `.github/pull_request_template.md`, `.gitattributes`, `docs-check.toml`, `tools/docs_check/` · Last reviewed against: develop @ `b7582c3`

## Scope

The life of a change from spec to archive: spec statuses and fields, docs impact, requirement IDs, conflicts between sources, decisions, handoff, branching and merging.

Not here:
- never pushing `develop` or `main`, merging only on the owner's word, commit identity and trailers, footers on GitHub, the commit-subject style: root `AGENTS.md`, enforced by `.github/workflows/commit-identity.yml`;
- whether a `DECISIONS.md` entry can narrow an invariant: [invariants](../system/invariants.md);
- how a change is proven: [verification](verification.md); how docs and requirements are written: [conventions](conventions.md).

## Requirements

- <a id="ENG-016"></a>**ENG-016** — Spec statuses are `draft`, `ready`, `blocked`, `hold` and `done`. A `hold` spec is parked by an owner decision and lives in `specs/hold/`; a `done` spec moves to `specs/done/`, and its `TODO.md` row points there, in the same PR as the work.
- <a id="ENG-017"></a>**ENG-017** — A spec is self-contained (a cold session with the spec and root `AGENTS.md` can start), scoped to one deliverable, named after what it does, and reaches `ready` only with every field `docs-check.toml` `[specs]` requires (meanings in `specs/README.md`). Scoping fills in the tests and the definition of done, never the implementation.
- <a id="ENG-018"></a>**ENG-018** — Every active and hold spec has a **Docs impact** field listing the IDs it adds (as `NS-new`), changes or retires, or `none — <reason>`.
- <a id="ENG-019"></a>**ENG-019** — For every domain a PR's net diff touches (`docs-check.toml` `[ownership]`, one or more domains per path), an owner doc of that domain changes, or the PR body has `Docs unchanged: <domain> — <reason>`. Adding a `CHOICE` heading to `DECISIONS.md` touches the domain `decisions`.
- <a id="ENG-020"></a>**ENG-020** — A behaviour change edits its owner doc in the same PR: new IDs come from `--next`, rewording that keeps the meaning keeps the ID, a change of meaning retires the ID and adds a new one, and verification rows are updated.
- <a id="ENG-021"></a>**ENG-021** — IDs have the format `NS-NNN` in the namespaces of `docs-check.toml`. Invariants keep root-`CLAUDE.md` numbering and are the only IDs amended in place (an amendment line, exceptions listed under the invariant). Every ID is defined once and never reused. A retired ID moves to `Retired requirements` with the date, the retiring spec or decision, the replacement or `none`, and the original text. Adding a namespace changes `docs-check.toml` and `docs/README.md` in one PR.
- <a id="ENG-022"></a>**ENG-022** — When two PRs allocate the same new ID, the later one renumbers its new IDs, including in its spec and PR body.
- <a id="ENG-023"></a>**ENG-023** — Conflict precedence, highest first: locked machine authorities; other machine authorities for values; `docs/` for approved behaviour; an active spec for its own work only; `DECISIONS.md`; agent files and READMEs; `specs/done/`, `docs/HISTORY.md` and `TODO.md` notes, which are never consulted for current rules.
- <a id="ENG-024"></a>**ENG-024** — When code and `docs/` disagree, the finder sets the requirement's status to `divergent` and appends a `FLAG` entry; the owner decides to fix the code (a spec) or ratify it (a doc edit citing the decision). A doc is never edited to match code without that decision.
- <a id="ENG-025"></a>**ENG-025** — A behaviour-changing `CHOICE` lands in the same PR as its doc edit; a decision not absorbed into `docs/` never outranks it.
- <a id="ENG-026"></a>**ENG-026** — Decisions are cited by their `DECISIONS.md` heading in backticks (double backticks when the heading itself contains one). The owner's working register numbers never appear in `docs/`, specs, READMEs or agent files.
- <a id="ENG-027"></a>**ENG-027** — A requirement converted from older text carries a `Source`: in priority order a requirements §, a `CHOICE` heading, an archived spec, an invariant, or an owner ratification. One whose only source is code, a README, a `CLAUDE.md` trap or a config comment is `pending-decision` and listed in its domain's ratification batch until the owner approves it; a source that contradicts the code is written as approved with status `divergent`.
- <a id="ENG-028"></a>**ENG-028** — A session that stops before its spec is done adds a `## Handoff` section to the spec with the lines `Written against: develop @ <sha>` (plus branch and commits ahead), `Done`, `Not done`, `Next`, `Docs`, `Open decisions`, `Verify`. The next session re-reads whatever changed on `develop` since that SHA before relying on it.
- <a id="ENG-029"></a>**ENG-029** — Branches: `main` (releases only), `develop` (integration), one `feature/<name>` per spec from `develop` as named in its Branch field, `release/<version>` from `develop` into `main` and `develop`, `hotfix/<name>` from `main` into both.
- <a id="ENG-030"></a>**ENG-030** — Merge recipe, once the owner says merge: rebase onto `origin/develop` (conflicts resolved in the rebase), run `python3 -m tools.docs_check --base origin/develop`, push with `--force-with-lease`, wait for CI on the rebased head, then fast-forward `develop` locally and push. GitHub's merge button is not used (it records the GitHub account as committer), and `--no-ff` only by explicit agreement.
- <a id="ENG-031"></a>**ENG-031** — `main` changes only through a `release/<version>` branch, when the owner asks for a release.
- <a id="ENG-032"></a>**ENG-032** — `DECISIONS.md` and `TODO.md` use git's `union` merge driver; after a rebase their entries read in order with no duplicated line.
- <a id="ENG-033"></a>**ENG-033** — `DECISIONS.md` is append-only, in the heading format stated at its top; a `BLOCKED` entry stops the work until the owner answers.
- <a id="ENG-034"></a>**ENG-034** — `TODO.md` is the spec index (one row per spec, status equal to the spec's, link to its current directory) and a one-line-per-session log; its notes carry status, never rules.
- <a id="ENG-035"></a>**ENG-035** — A commit is made only when the spec's tests pass; secrets, build outputs, virtualenvs, caches and volumes are never committed (`.gitignore` lists them).
- <a id="ENG-036"></a>**ENG-036** — A spec under `specs/done/` is not edited after archiving; corrections go to `docs/` or `DECISIONS.md`.
- <a id="ENG-037"></a>**ENG-037** — The PR body follows `.github/pull_request_template.md`: Docs impact or `Docs unchanged:` lines, whether the touched requirements were read against the code, divergences with their decision heading, tests mapped to IDs, red output, mutation checks, CI-only runs, and the semantic review.
- <a id="ENG-038"></a>**ENG-038** — A reviewer who did not write the change checks that each `Docs unchanged:` line is true, that doc edits state approved behaviour, that tests assert behaviour, and that requirements sit with their owner; the result is recorded in the PR body.
- <a id="ENG-039"></a>**ENG-039** — `Last reviewed against` names a `develop` commit and is changed only by someone who re-read the doc against the code at that commit.

## Machine-readable authorities

| File | Governs | Notes |
|---|---|---|
| `docs-check.toml` | Namespaces, required spec fields and statuses, the path-to-domain ownership map | ENG-017, ENG-019, ENG-021 name it; its values are not copied here |
| `.gitattributes` | The `union` merge driver for the two shared logs | ENG-032 |
| `.github/pull_request_template.md` | The PR record | ENG-037 |

## Verification

| ID | Source | Verified by | Status |
|---|---|---|---|
| ENG-016 | `## 2026-10-22 — Living docs — PENDING — engineering ratification batch` [`CLAUDE.md`; `specs/README.md`] | check J (index statuses and links) | pending-decision |
| ENG-017 | `## 2026-10-22 — Living docs — PENDING — engineering ratification batch` [`CLAUDE.md`; `specs/README.md`] | check E (required fields) | pending-decision |
| ENG-018 | `## 2026-10-17 — Living docs — CHOICE — docs impact field and Docs unchanged line` [`specs/README.md`] | check E (`Docs impact` in `docs-check.toml` `[specs]`) | enforced |
| ENG-019 | `## 2026-10-17 — Living docs — CHOICE — docs impact field and Docs unchanged line` [`CLAUDE.md`] | check G in `.github/workflows/docs.yml` (report-only until the cutover) | enforced |
| ENG-020 | `## 2026-10-22 — Living docs — PENDING — engineering ratification batch` [`CLAUDE.md`; `specs/README.md`] | checks C, C2 | pending-decision |
| ENG-021 | `## 2026-10-22 — Living docs — PENDING — engineering ratification batch` [design §5.2] | checks C, C2, D | pending-decision |
| ENG-022 | `## 2026-10-22 — Living docs — PENDING — engineering ratification batch` [design §5.2] | check C | pending-decision |
| ENG-023 | `## 2026-10-22 — Living docs — PENDING — engineering ratification batch` [design §9.1; requirements §14] | — | pending-decision |
| ENG-024 | `## 2026-10-22 — Living docs — PENDING — engineering ratification batch` [design §9.1] | check K (a `divergent` row cites a decision) | pending-decision |
| ENG-025 | `## 2026-10-22 — Living docs — PENDING — engineering ratification batch` [design §9.1] | check G (a `CHOICE` heading touches `decisions`) | pending-decision |
| ENG-026 | `## 2026-10-22 — Living docs — PENDING — engineering ratification batch` [`specs/README.md`] | check D | pending-decision |
| ENG-027 | `## 2026-10-22 — Living docs — PENDING — engineering ratification batch` [design §8.5] | check K | pending-decision |
| ENG-028 | `## 2026-10-22 — Living docs — PENDING — engineering ratification batch` [design §8.3] | — | pending-decision |
| ENG-029 | `## 2026-10-22 — Living docs — PENDING — engineering ratification batch` [`CLAUDE.md`] | — | pending-decision |
| ENG-030 | `## 2026-10-09 — Guideline setup — CHOICE — merge flow, merge bar and shared-log conflicts written into the repo` [`CLAUDE.md`]; the `--base` check step: `## 2026-10-22 — Living docs — PENDING — engineering ratification batch` | — | untested |
| ENG-031 | `## 2026-10-09 — Guideline setup — CHOICE — merge flow, merge bar and shared-log conflicts written into the repo` [`CLAUDE.md`] | — | untested |
| ENG-032 | `## 2026-10-09 — Guideline setup — CHOICE — merge flow, merge bar and shared-log conflicts written into the repo` [`CLAUDE.md`] | `.gitattributes`; check J (duplicate `TODO.md` rows) | enforced |
| ENG-033 | `## 2026-10-22 — Living docs — PENDING — engineering ratification batch` [`DECISIONS.md`] | — | pending-decision |
| ENG-034 | `## 2026-10-22 — Living docs — PENDING — engineering ratification batch` [`TODO.md`] | check J | pending-decision |
| ENG-035 | `## 2026-10-22 — Living docs — PENDING — engineering ratification batch` [`CLAUDE.md`] | `.gitignore` (list only) | pending-decision |
| ENG-036 | `## 2026-10-17 — Living docs — CHOICE — archive policy for specs/done` [`specs/README.md`] | — | untested |
| ENG-037 | `## 2026-10-22 — Living docs — PENDING — engineering ratification batch` [design §10.2] | — | pending-decision |
| ENG-038 | `## 2026-10-22 — Living docs — PENDING — engineering ratification batch` [design §10.2] | — | pending-decision |
| ENG-039 | `## 2026-10-22 — Living docs — PENDING — engineering ratification batch` [design §10.2] | check E (the SHA is an ancestor of HEAD) | pending-decision |

"design §n" is a section of `specs/living-docs-cutover-design.md`. A bracketed Source part is where the text came from; the part before it is the approval.

## Rationale

- The `union` driver was chosen over one file per decision entry, which would have changed every link to the log (`## 2026-10-09 — Guideline setup — CHOICE — merge flow, merge bar and shared-log conflicts written into the repo`). That entry also said the `TODO.md` session log is dropped; the log is still kept, and ENG-034 describes it as practised (defect A3 under `## 2026-10-15 — Living docs — PENDING — defects found while scoping`).
- `Last reviewed against` names a `develop` commit because feature-branch SHAs do not survive the rebase-and-fast-forward flow (design §5.1).

## Retired requirements

None.

# Docs check tooling

**Status:** done
**Branch:** `feature/living-docs-checker` (PR into `feature/living-docs-integration`, never into `develop`)
**Docs impact:** none in `docs/` — this spec builds the checker that later specs use to write `docs/`. It creates `tools/docs_check/`, `docs-check.toml` and `.github/workflows/docs.yml`, and changes `.github/workflows/commit-identity.yml`. The engineering requirements describing the checker are written by `living-docs-engineering-workflow`.

---

## Context

At `develop` @ `e51f74201fda30dd9a28af318cc74b824e39dafc` (2026-10-15):

- **No documentation tooling exists.** `git ls-files | grep -iE 'markdownlint|lychee|linkcheck|pre-commit|CODEOWNERS|tools/'` returns nothing. There is no `tools/` directory, no `docs-check.toml`, no PR template.
- **CI** is four workflows: `.github/workflows/commit-identity.yml` (PRs into `main` and `develop` only, `:3-7`), `java.yml`, `python.yml`, `dashboard.yml`. None checks Markdown, links, specs or `TODO.md`. `python.yml` sets up Python with `actions/setup-python@v7`, version `'3.14'` (`python.yml:43-46`); every action is on its Node 24 major (DECISIONS `## 2026-10-09 — Dashboard — CHOICE — Node 24 LTS, actions on Node 24`).
- **The commit identity script** `.github/scripts/check_commit_identity.sh` is tested against throwaway repositories by `services/ingestion-scraper/tests/unit/test_commit_identity_check.py` (`:1-30`). That is the pattern this spec follows: temp-dir git repositories, the tool run in a subprocess, nothing mutant committed.
- **What a checker would find today** (probes run over the baseline with throwaway scripts, recorded in the scoping evidence):
  - 109 tracked `.md` files, 96 relative links, 0 broken, 0 links with `#anchors`.
  - 538 unresolved backticked path-like tokens repo-wide, most legitimate (service-relative paths, MinIO keys, image names). Only two are real stale references: `CLAUDE.md:212` (`specs/edgar-efts-fixture-alignment.md`, now under `specs/done/`) and `docs/requirements.md:402` (`research_signal_event.json`). A path check is therefore scoped to `docs/**` and agent files, with tracked-prefix tokens only.
  - `TODO.md`: 83 spec rows, every link resolves, every status matches the spec's `**Status:**` line, `done`/`hold` rows match their directory. Six commits exist only to drop rows resurrected by the `union` merge driver (`96be8b9`, `8822d56`, `f402169`, `b37871c`, `e459f3e`, `78cf812`).
  - `DECISIONS.md`: `grep -c '^## .*CHOICE'` gives 118, but line 10 is the format template inside a fenced block (`DECISIONS.md:9-15`). A fence-aware count gives **117** real `CHOICE` headings.
- **Tracked paths:** 774 (`git ls-files | wc -l`). Top-level groups: `.github/` (5), `config/` (22), `docker/` (29), `docs/` (6), `orchestration/` (1), `services/` (616), `specs/` (85), and root files `.env.example`, `.gitattributes`, `.gitignore`, `CLAUDE.md`, `DECISIONS.md`, `README.md`, `SETUP.md`, `TODO.md`, `VERSIONS.md`, `verify_pipeline.sh`. DAGs live in `services/{ingestion-scraper,backtesting,backup}/dags/`; there is no `airflow/` directory.
- **Python here:** cloud sessions have Python 3.13 (`python3 --version`); the pin is 3.14.2 (`VERSIONS.md`). `tomllib` is stdlib from 3.11, so the tool runs on both.

The design this spec implements is the living-documentation architecture: three layers (`docs/` normative, `specs/` change specs, `specs/done/` archive), requirement IDs `NS-NNN` defined once in `docs/`, a `Docs impact` field on every spec, and a `Docs unchanged: <domain> — <reason>` line in the PR body for every touched domain whose owner doc did not change. Everything a cold session needs from that design is restated below as the tool's behaviour.

## What this builds

A stdlib-only Python checker, run from the repo root as `python3 -m tools.docs_check`, its configuration `docs-check.toml`, its unit tests, a report-only CI workflow, and the integration branch added to the commit identity check.

### Layout

```
tools/docs_check/__init__.py
tools/docs_check/__main__.py        argparse CLI, exit codes, output
tools/docs_check/config.py          docs-check.toml loading and validation (exit 2 on error)
tools/docs_check/repo.py            git ls-files / diff / show / merge-base wrappers (subprocess, no shell)
tools/docs_check/markdown.py        fence stripping, headings, GitHub slugs, links, inline code, tables, list items
tools/docs_check/globs.py           path glob matching (semantics below)
tools/docs_check/checks/*.py        one module per check: links (A), paths (B), ids (C, C2), references (D),
                                    structure (E), ownership (F, G), legacy (H), index (J), verification (K),
                                    agents (L), matrix (M; rollout only, in its own module so it can be deleted)
tools/docs_check/tests/__init__.py
tools/docs_check/tests/fixture_tree.py   builds the minimal valid tree in a temp dir (from Python data, not committed files)
tools/docs_check/tests/test_*.py
docs-check.toml
.github/workflows/docs.yml
```

There is no `tools/__init__.py`: `tools` is a namespace package, so `python3 -m tools.docs_check` works from the repo root with no install step.

**Fixtures are built in code, never committed as files.** A committed fixture tree would contain `AGENTS.md`, `CLAUDE.md` and `docs/` files under `tools/`; Claude Code would load a nested `CLAUDE.md` from it, and the real-repo checks would scan it. `fixture_tree.py` holds the minimal valid tree as a dict of path → text, writes it into a `tempfile.TemporaryDirectory()`, runs `git init`, sets a local test identity, and commits. Seeded defects are applied to that temp copy only.

### CLI

```
python3 -m tools.docs_check [--root DIR] [--config FILE] [--only LIST] [--paths GLOBS] [--base REF] [--pr-body FILE]
python3 -m tools.docs_check --next NS
python3 -m tools.docs_check --owners PATH [PATH ...]
python3 -m tools.docs_check --matrix FILE --domain NS
python3 -m tools.docs_check --matrix FILE --decisions [--domain NS]
python3 -m tools.docs_check --pending --blocking-list FILE
```

- `--root` defaults to `.`; it must be the top of a git work tree, or exit 2. `--config` defaults to `<root>/docs-check.toml`.
- The default mode runs A, B, C, D, E, F, H, J, K and L. It adds **C2** when `--base` is given and **G** when both `--base` and `--pr-body` are given. G without `--pr-body` is skipped with a notice on stderr (`G skipped: no PR body`), not failed.
- `--only` takes a comma list of check letters (`A,B,C,C2,D,E,F,G,H,J,K,L`). An unknown letter is exit 2. `--only C2` or `--only G` without `--base` is exit 2.
- `--paths GLOBS [GLOBS ...]` takes one or more arguments, each a comma list of path globs (syntax below), and reports only findings and notices whose `path` matches one of them; checks still read the whole file set, so cross-file resolution is unchanged. Domain specs use it to gate only their own files (`--paths 'docs/ingestion/**,specs/historical-backfill.md'` or `--paths docs/ingestion/connectors.md specs/historical-backfill.md`). The exit code and the stderr summary count only the findings reported for those paths: a finding in another file neither prints nor makes the exit 1. `--paths` combines with `--only` (both filters apply) and with `--base`/`--pr-body`. An empty list is exit 2.
- `--base REF` must resolve with `git rev-parse --verify REF^{commit}`, or exit 2. Diffs use the merge base: `git diff --name-status -M REF...HEAD`, so mutant-and-revert commit pairs cancel out.
- `--pr-body FILE` reads the file as UTF-8. An empty file is a valid empty body.
- `--next NS` prints the next unused ID in a configured namespace: the highest number ever used (active **or retired**, across living docs) plus one, zero-padded to three digits (`NS-007`); for the invariant namespace, the next integer without padding (`INV` followed by `-` and the number). The retired entries are the ledger, so a retired number is never handed out again. An unknown namespace is exit 2. It prints only the ID and exits 0.
- `--owners PATH ...` prints one line per path: `path<TAB>domain1,domain2<TAB>owner-doc …`, or `path<TAB>unowned-ok`, or `path<TAB>UNOWNED`. Paths need not exist (the cutover maps paths of deleted files). Exit 1 if any path is `UNOWNED`, else 0.
- The three check M modes are described under check M. They are mutually exclusive with each other and with the default mode (exit 2 otherwise).

**Exit codes.** 0 no findings · 1 one or more findings · 2 configuration or usage error (unreadable or invalid TOML, an unknown key, a namespace not matching `^[A-Z]{3}$`, a missing required file named in config, a ref that does not resolve, conflicting modes). Exit 2 prints one line `docs_check: error: <message>` on stderr and nothing on stdout.

**Output.** One line per finding on stdout: `CHECK path:line message`, where `CHECK` is the letter (`A` … `M`, or `C2`), `path` is repo-relative with `/`, and `line` is 1-based (0 when the finding has no line, e.g. a missing file). Lines are sorted by check, path, line, message. A summary goes to stderr: `docs_check: N findings (A=…, B=…)` or `docs_check: clean`.

**Notices.** A *notice* goes to stderr as `CHECK notice path:line message` and never changes the exit code. Notices exist only for the rollout's planned domains (`[rollout] planned_domains`): while a domain is listed, (a) a relative link (A, with or without a `#fragment`) or a backticked path (B) whose target is one of its missing owner docs, or lies under a missing directory that only its owner docs occupy (e.g. `docs/ingestion/` before `living-docs-ingestion` lands), (b) a reference (D) to an ID in one of its namespaces that has no definition yet, and (c) a placeholder `NS-?` (D) in one of its namespaces are notices instead of findings. Removing the domain from the list turns each into a finding. The cutover gate requires the list to be empty, so no notice survives the gate.

### Shared parsing rules

- **Fenced code blocks** (lines between ```` ``` ```` or `~~~` fences) are ignored by A, B, C, D, K and by the CHOICE-heading parser. E reads headings outside fences only.
- **Headings and slugs.** ATX headings `#`–`######`. The GitHub slug: lowercase; drop every character that is not a Unicode word character, space or hyphen; spaces to `-`; a repeated slug in one file gets `-1`, `-2`, … in order. Explicit anchors `<a id="X"></a>` and `<a name="X"></a>` are also anchors.
- **Links.** Inline `[text](target)` and reference definitions `[x]: target`. A target with a scheme (`https:`, `mailto:` …) is external and ignored. `#frag` alone is resolved in the same file. A path is relative to the file's directory; a leading `/` is relative to the repo root.
- **The file set** is `git ls-files --cached --others --exclude-standard` (tracked plus untracked-but-not-ignored), so a new file is visible before it is committed. Directories exist when some file in the set lies under them.
- **IDs.** The namespaces come from `docs-check.toml`. With the repo's configuration the reference regex is exactly
  `(?<!M-)\b(INV-\d{1,2}|(SYS|CON|ING|EXT|HUB|COR|RES|EVA|STR|DSH|OPS|ENG)-\d{3})\b`
  and the invariant alias regex is exactly
  `[Ii]nvariants? #?(\d{1,2})( and #?(\d{1,2}))?`
  ("Invariant 7", "Invariants 1 and 2", "invariant #9", all in root `CLAUDE.md` numbering, map to the invariant namespace ID with that number). The tool builds the first regex from the configured namespaces, so fixture configs use their own. The `(?<!M-)` lookbehind keeps migration-matrix row ids (`M-OPS-251`) from reading as references to `OPS-251`.
- **Definitions.** An *active definition* is a Markdown list item, outside `## Retired requirements`, that starts with `<a id="NS-NNN"></a>**NS-NNN**` (same ID twice). A *retired definition* is a list item under the H2 `## Retired requirements` whose first bold token is `**NS-NNN**`, with or without the anchor. Definitions count only in living docs (`docs/**/*.md` minus `[living_docs] non_normative`).
- **Decision citations.** An inline-code span, single-backticked (`` `…` ``) or double-backticked (``` `` … `` ```, for the headings that themselves contain backticks), whose text matches `(## )?\d{4}-\d{2}-\d{2} — .+` and contains one of ` — BLOCKED`, ` — FLAG`, ` — CHOICE`, ` — VERIFIED`, ` — PENDING`. A span containing `…` or `<` is a template and is skipped. A citation resolves when its text (without a leading `## `, trimmed) equals the text of a heading in `DECISIONS.md` outside fences.
- **Register numbers.** `\bD-\d\d\b`. They are the owner's working labels from outside the repo and never appear in scanned files: decisions are cited by heading only.
- **Verification table.** In a living doc, the first table under `## Verification` whose header cells are `ID | Source | Verified by | Status`. Status values: `tested`, `enforced`, `untested`, `divergent`, `pending-decision` (the first backticked or bare word of the cell).

### Path globs (`globs.py`)

Patterns match the whole repo-relative path. `**` matches zero or more whole segments (`**/README.md` matches `README.md` and `a/b/README.md`); `*` matches any run of characters except `/`; `?` matches one character except `/`. No braces, no character classes. A trailing `/**` matches everything below a directory.

### Checks

| Check | Asserts | Scope |
|---|---|---|
| **A** links | Every relative link target is in the file set; every `#fragment` matches a heading slug or explicit anchor in the target (or the same file). Every `frozen_paths` entry is in the file set | `[checks.A] include` (below): `docs/**/*.md`, `specs/*.md`, `specs/hold/*.md`, `**/README.md`, `**/AGENTS.md`, `**/CLAUDE.md`, `SETUP.md`, `VERSIONS.md`, `.github/pull_request_template.md`. Not `specs/done/**`, not `DECISIONS.md`, not `tools/docs_check/tests/**` |
| **B** paths | A backticked inline-code token with no spaces that starts with a configured tracked prefix (`services/`, `config/`, `docker/`, `docs/`, `specs/`, `.github/`, `tools/`) or equals a root file name in the file set (e.g. `SETUP.md`), after stripping a trailing `#…`, `:line[-line]` or `::name`, is in the file set (file or directory). Tokens containing `*`, `<`, `>`, `{`, `…` or `$` are skipped | `docs/**/*.md` and agent files (`**/AGENTS.md`, `**/CLAUDE.md`) only |
| **C** IDs unique | Each ID has exactly one definition (active or retired) across living docs. An invariant-namespace ID is never retired | living docs |
| **C2** no reuse | Every ID defined (active or retired) in a living doc at `--base` (read with `git ls-tree -r --name-only` and `git show <base>:<path>`) is still defined at HEAD | living docs, `--base` required |
| **D** references | (1) Every ID reference and invariant alias resolves to an active or retired definition. (2) A reference to a **retired** ID is a finding in active and hold specs, agent files and READMEs; it is allowed in living docs (replacement notes) and in the non-normative `docs/*.md` files (the legacy § index maps old sections to IDs that may later retire). (3) A placeholder `NS-?` is a finding. (4) Every decision citation resolves to a `DECISIONS.md` heading. (5) Any register number is a finding. (1), (3) and the planned-domain notices follow the Notices rule above | `[checks.D] include` (below): living docs and the non-normative `docs/*.md` files; `specs/*.md` and `specs/hold/*.md`; `**/AGENTS.md`, `**/CLAUDE.md`, `**/README.md`, `SETUP.md`, `VERSIONS.md`; and the PR body when given (rules 1, 3, 4 only). Excluded: `specs/done/**`, `specs/living-docs-cutover-matrix.md` (check M owns it), `DECISIONS.md`, `tools/docs_check/tests/**` |
| **E** structure | Living docs have the H2s `Scope`, `Requirements`, `Verification`, `Retired requirements` (any order, may be empty) and a line containing `Last reviewed against: develop @ <sha>` whose SHA (7–40 hex, optionally backticked) resolves and is an ancestor of HEAD (`git merge-base --is-ancestor`). Active and hold specs carry the `[specs] required_fields` (a line starting `**Field:**`), `**Blocked by:**` when status is `blocked`, a status in `[specs] statuses`, and the `[specs] required_sections` H2s | living docs; `specs/*.md`, `specs/hold/*.md` minus `[specs] exclude` |
| **F** ownership | Every path in the file set matches at least one `[[ownership]]` rule or an `unowned_ok` glob. Every owner doc named by a domain exists, **except** for domains listed in `[rollout] planned_domains`. A planned domain whose owner docs all exist is itself a finding ("remove from planned_domains"), so the list empties as domain specs land. `[rollout] base`, when set, must resolve (else exit 2) | file set |
| **G** impact | For the net diff `--base...HEAD` (old and new path of renames), collect the domains of every changed path (union over matching rules; `unowned_ok` paths add none). A change to `DECISIONS.md` adds domain `decisions` only when the diff adds a line that is a `## …CHOICE…` heading outside fences. For each collected domain, one must hold: some changed path is one of that domain's owner docs; or the PR body has a line `Docs unchanged: <domain> — <reason>` (em dash, or ` -- `) with a known domain and a reason that is non-empty and not the literal `<reason>`. A `Docs unchanged:` line naming an unknown domain, or with an empty or placeholder reason, is a finding | PR diff |
| **H** legacy | `docs/requirements.md` holds only: an optional H1, one banner paragraph containing `Not authoritative`, and one Markdown table, separated by blank lines. Anything else is **one** finding at the first offending line, with the count of offending lines in the message | `[checks.H] file` |
| **J** index | In `TODO.md`'s spec table (rows whose first cell is a link into `specs/`): every link target exists; the status cell matches the spec's `**Status:**` value; `done` rows point under `specs/done/`, `hold` rows under `specs/hold/`, others directly under `specs/`; no spec is listed twice; every spec file (`specs/*.md`, `specs/hold/*.md`, `specs/done/*.md`, minus `[specs] exclude` and `[checks.J] exclude`) has a row. The session-log table is not checked | `TODO.md`, `specs/**` |
| **K** verification | Every active ID defined in a living doc has exactly one row in that doc's verification table; no row names an ID that the doc does not define. `Source` is non-empty. `Status` is a known value. For `tested` rows every `path::name` token in `Verified by` names a file in the file set (a bare file name with no `/` ending in `.test.ts` or `.test.tsx`, e.g. `auth.test.ts::rejects a bad password`, resolves against each directory in `[checks.K] bare_test_dirs`, i.e. `services/dashboard/src/__tests__/<file>`) containing `def name(`, `void name(`, `it('name'`, `it("name"`, `test('name'` or `test("name"`; at least one such token is present. `enforced` rows have a non-empty `Verified by`. `divergent` rows contain a decision citation; `pending-decision` rows contain a citation of a `PENDING` heading (check D resolves both) | living docs |
| **L** agent files | Root `AGENTS.md` exists and is ≤ `[budgets] root_agents_bytes`; each nested `AGENTS.md` ≤ `nested_agents_bytes`; for every directory with an `AGENTS.md`, the sum of the `AGENTS.md` files from the root down to it ≤ `chain_bytes`. Every `CLAUDE.md` has an `AGENTS.md` beside it, has `@AGENTS.md` as its first line, is ≤ `claude_md_bytes`, and contains none of the words `must`, `never`, `always` (case-insensitive, whole words). No `AGENTS.md` contains an `@path` import: an `@` at line start or after whitespace, immediately followed by a path ending in a file extension (`(^|\s)@[\w./-]+\.\w+`), outside fences and inline code. A word such as "@imports" is not an import | `**/AGENTS.md`, `**/CLAUDE.md` minus `tools/docs_check/tests/**` |
| **M** matrix (rollout only) | See below. Removed by `living-docs-cutover` together with its tests | the migration matrix, `DECISIONS.md`, living docs |

**`[rollout]` is optional.** Every other table is required. When `[rollout]` is absent the checker behaves as if `planned_domains` were empty and `base` unset: no notices, F requires every owner doc, and C2 and G still work from `--base`. The three check M modes then exit 2 with `docs_check: error: no [rollout] table`; `living-docs-cutover` deletes check M together with the table.

Check I (archive immutability) is not built here.

### Check M (rollout only)

All modes read `docs-check.toml` for namespaces and living-doc scope, and exit 2 when the named file is missing or the expected table is absent. Tables are found by header cells; a header cell matches when it **starts with** the expected name (so `Source (path:line or §)` is the `Source` column).

**Source reference of a matrix row** (used below). Check M compares document-level references only, never line numbers. From the row's `Source` cell, in this order:
- a decision heading cited in it (backticked, single or double) → that heading text;
- else a requirements reference `§N` (`§\d+(\.\d+)*`, first one) → the text `requirements §N` or `§N`, either matches;
- else a section-relative cell (`:85`, `` `:852` ``, starting with `:` after any backtick) → the file named in the matrix section header that holds the row: the nearest preceding heading of `FILE` containing a backticked or bare path ending in a file extension (e.g. ``### `docs/strategy-research.md` `` gives `docs/strategy-research.md`); no such heading is a finding;
- else a path: the first token (split on spaces and `;`, backticks stripped, anything from the first `:` on dropped) that contains `/` or ends in a file extension (`\.[A-Za-z0-9]+$`), e.g. `CLAUDE.md` from `CLAUDE.md:137`, `services/CLAUDE.md` from `` `services/CLAUDE.md:30-35` ``; line numbers and ranges are dropped;
- else (any other cell: prose, an at-risk class such as `at-risk class #18`, a scoping label, i.e. a cell whose first token matches `^[A-Z]{1,2}-?[A-Z]?\d+[a-z]?$` such as `C5`, `F-H6`, `T-1b` or `E F18`, or a cell starting `same as`) → **no reference**: the row gets the ID-existence check only.

A verification row *carries* a reference when its `Source` cell contains that text.

1. **`--matrix FILE --domain NS`.** Reads every table in `FILE` whose header contains `Row`, `Disposition`, `NS` and `ID`. A table with `Row`, `Disposition` and `NS` but no `ID` column is exit 2. For each row whose `NS` cell is `NS` and whose disposition is `move`, `ratify`, `divergent` or `retire`, the `ID` cell lists one or more entries. Each entry is one of:
   - an ID of namespace `NS`. It must be defined (a retired definition for `retire`, an active one otherwise), and the ID's verification row must carry the row's source reference. For `retire` the retired entry's text must contain the reference instead;
   - for rows whose `Class` is `trap` or `rationale` only (they carry no IDs), an anchor entry `docs/<file>.md#<anchor>` naming an owner doc of the domain that owns `NS`. The anchor is either the H2 slug `known-traps` or `rationale`, or an explicit `<a id="…"></a>` placed on a list item inside that H2. The file must exist, the anchor must resolve, and the anchored text (the whole H2 section for a slug, the one list item for an explicit anchor) must contain the row's source reference. So each moved trap or rationale item names where it came from, e.g. `(from CLAUDE.md, Known traps)`.
   For each row whose `NS` cell is `NS` and whose disposition is `link`, the `ID` cell may be empty (nothing is checked) or list entries `path` or `path#anchor` naming a file in the file set. Such an entry is satisfied when the file exists and either its `#anchor` resolves (heading slug or explicit anchor) or, with no anchor, the file's text contains the row's source reference.
   A missing entry, an unresolved ID or anchor, or a Source mismatch is a finding `M FILE:line row <Row> …`. Rows with other dispositions are not checked.
2. **`--matrix FILE --decisions [--domain NS]`.** Collects every heading in `DECISIONS.md` outside fences whose text matches `^## .*CHOICE` (117 at the baseline, all distinct). Reads the table in `FILE` whose header contains `Heading`, `Classification` and `IDs` (and optionally `Fragment rows`). Findings: a CHOICE heading with no row; a heading with two rows; a row naming no existing heading; a classification other than `binding` or `history`; a `binding` row whose `IDs` cell is empty, names an ID with no active definition, or names an ID whose verification row's `Source` does not contain the heading text. Heading cells may carry backticks (single or double) and an optional leading `## `. With `--domain NS`, a binding row is selected by the `NS` cell of its fragment rows, not by the row-id prefix: each row id listed in its `Fragment rows` cell is looked up in the fragment tables of `FILE`, and the row is checked when at least one of them has `NS` = `NS` (a listed row id that does not exist is a finding). Only selected rows are checked, and the unclassified-heading finding is skipped; a domain spec uses this to check its own binding rows.
3. **`--pending --blocking-list FILE`.** Reads the table under `## Blocking decisions` in `FILE` and its `Heading suffix` column. Each cell is plain suffix text, e.g. `| raw-pointer contract |` (backticks, if any, are stripped). For every verification row in every living doc with status `pending-decision`: a finding if the row cites a `PENDING` heading whose text ends with ` — <suffix>` for any listed suffix, or if it cites no `PENDING` heading at all.

### `docs-check.toml` (initial content; a deliverable)

Keys not listed here are exit 2. Comments in the file say what each table governs.

```toml
[namespaces]
invariant = "INV"
ids = ["SYS", "CON", "ING", "EXT", "HUB", "COR", "RES", "EVA", "STR", "DSH", "OPS", "ENG"]

frozen_paths = [
  "SETUP.md", "VERSIONS.md", "README.md", "CLAUDE.md", "docker/README.md", "docker/CLAUDE.md",
  "docs/backup-restore.md", "docs/strategy-research.md", "docs/local-model-runbook.md",
  "specs/sec-ownership-datasets.md", "specs/clinicaltrials-version-diffs.md", "specs/catalyst-date-panel.md",
  "specs/point-in-time-universe.md", "specs/first-run-on-stack-machine.md", "docs/requirements.md",
]

[living_docs]
include = ["docs/**/*.md"]
non_normative = [
  "docs/README.md", "docs/requirements.md", "docs/strategy-research.md", "docs/local-model-runbook.md",
  "docs/backup-restore.md", "docs/PREREQUISITES.md", "docs/HISTORY.md", "docs/soak-test-report.md",
]
required_sections = ["Scope", "Requirements", "Verification", "Retired requirements"]

[specs]
include = ["specs/*.md", "specs/hold/*.md"]
exclude = ["specs/README.md", "specs/_template.md", "specs/living-docs-cutover-matrix.md",
           "specs/living-docs-cutover-design.md"]
statuses = ["draft", "ready", "blocked", "hold", "done"]
required_fields = ["Status", "Branch", "Docs impact"]
required_sections = ["Context", "What this builds", "Out of scope", "Constraints", "Required tests", "Definition of done"]

[checks.A]
include = ["docs/**/*.md", "specs/*.md", "specs/hold/*.md", "**/README.md", "**/AGENTS.md", "**/CLAUDE.md",
           "SETUP.md", "VERSIONS.md", ".github/pull_request_template.md"]
exclude = ["specs/done/**", "DECISIONS.md", "tools/docs_check/tests/**"]

[checks.D]
include = ["docs/**/*.md", "specs/*.md", "specs/hold/*.md", "**/AGENTS.md", "**/CLAUDE.md", "**/README.md",
           "SETUP.md", "VERSIONS.md"]
exclude = ["specs/done/**", "specs/living-docs-cutover-matrix.md", "specs/living-docs-cutover-design.md", "DECISIONS.md",
           "tools/docs_check/tests/**"]   # the two cutover companions quote IDs, placeholders and register numbers as history

[checks.B]
include = ["docs/**/*.md", "**/AGENTS.md", "**/CLAUDE.md"]
exclude = ["tools/docs_check/tests/**"]
prefixes = ["services/", "config/", "docker/", "docs/", "specs/", ".github/", "tools/"]

[checks.H]
file = "docs/requirements.md"

[checks.J]
index = "TODO.md"
exclude = ["specs/done/living-docs-cutover-matrix.md", "specs/done/living-docs-cutover-design.md"]

[checks.K]
bare_test_dirs = ["services/dashboard/src/__tests__"]   # where a `file.test.ts::name` token with no directory is looked up

[budgets]
root_agents_bytes = 6144
nested_agents_bytes = 3072
chain_bytes = 16384
claude_md_bytes = 512

# Optional table: living-docs-cutover deletes it. Without it the checker runs as if planned_domains were empty
# (no notices, every owner doc required) and the check M modes exit 2 ("no [rollout] table").
[rollout]
base = "<develop SHA the integration branch was cut from>"   # set by this spec; updated by living-docs-cutover
# Seeded with every domain by this spec. Each domain spec removes only its own domain(s), as the last step of its
# definition of done. The cutover gate requires the list to be empty.
planned_domains = ["system", "ingestion", "core-hub", "research", "strategy", "dashboard", "operations", "engineering"]
matrix = "specs/living-docs-cutover-matrix.md"

[domains.system]
namespaces = ["INV", "SYS", "CON"]
owners = ["docs/README.md", "docs/system/overview.md", "docs/system/invariants.md", "docs/system/contracts.md"]
[domains.ingestion]
namespaces = ["ING", "EXT"]
owners = ["docs/ingestion/connectors.md", "docs/ingestion/pipeline.md", "docs/ingestion/extraction.md"]
[domains.core-hub]
namespaces = ["HUB", "COR"]
owners = ["docs/core-hub/consumption.md", "docs/core-hub/storage.md", "docs/core-hub/corroboration.md", "docs/core-hub/http-api.md"]
[domains.research]
namespaces = ["RES", "EVA"]
owners = ["docs/research/market-data.md", "docs/research/universe.md", "docs/research/panels.md",
          "docs/research/simulation.md", "docs/research/backtesting.md", "docs/research/evaluation-protocol.md"]
[domains.strategy]
namespaces = ["STR"]
owners = ["docs/strategy/contract.md", "docs/strategy/runtime.md", "docs/strategy/risk.md", "docs/strategy/decision-trace.md"]
[domains.dashboard]
namespaces = ["DSH"]
owners = ["docs/dashboard.md"]
[domains.operations]
namespaces = ["OPS"]
owners = ["docs/operations/topology.md", "docs/operations/orchestration.md", "docs/operations/observability.md", "docs/operations/backup.md"]
[domains.engineering]
namespaces = ["ENG"]
owners = ["docs/engineering/verification.md", "docs/engineering/change-workflow.md", "docs/engineering/conventions.md"]
[domains.decisions]
namespaces = []
owners = ["docs/**/*.md"]            # any living doc; non_normative files do not count

[ownership]
# No domain, no Docs impact needed: orientation, agent files, the index, specs, docs themselves, placeholders.
unowned_ok = ["**/README.md", "**/AGENTS.md", "**/CLAUDE.md", "TODO.md", "specs/**", "docs/**",
              "**/.gitkeep", "**/.gitignore", ".github/pull_request_template.md"]
```

The `[[ownership]]` rules, in file order. A path's domains are the union of every matching rule; a matching rule with `override = true` replaces the domains of all matching rules without it. The groups are the tracked-path groups found by the scoping coverage review (every top-level directory and each service's subtrees), each mapped to one or more domains:

| # | `glob` | `domains` | Note |
|---|---|---|---|
| 1 | `services/ingestion-scraper/**` | ingestion | src (32), tests (121 incl. golden, fixtures), prompts, `pyproject.toml`, `uv.lock`, `config/sources.yaml` |
| 2 | `services/ingestion-scraper/src/auspex_ingest/models.py` | ingestion, system | wire models |
| 3 | `services/ingestion-scraper/src/auspex_ingest/identity.py` | ingestion, system | `event_id` |
| 4 | `services/ingestion-scraper/src/auspex_ingest/messaging/**` | ingestion, system | Kafka producer |
| 5 | `services/ingestion-scraper/tests/unit/test_contract_fixture.py` | ingestion, system | generates the signal fixture |
| 6 | `services/*/dags/**` | operations | adds operations to the service's domain (6 DAG files) |
| 7 | `services/*/Dockerfile*` | operations | 6 `Dockerfile`s plus `services/strategy/Dockerfile.dockerignore` |
| 8 | `services/*/.dockerignore` | operations | |
| 9 | `services/*/config/gunicorn.conf.py` | operations | single-process rule |
| 10 | `services/ingestion-scraper/scripts/sample_corroborations.py` | ingestion, core-hub | reads core-hub stores |
| 11 | `services/ingestion-scraper/scripts/score_corroboration_review.py` | ingestion, core-hub | corroboration review gate |
| 12 | `services/ingestion-scraper/tests/unit/test_stack_*.py` | operations, `override = true` | docker policy tests run in the scraper job |
| 13 | `services/ingestion-scraper/tests/unit/test_dashboard_stack_config.py` | operations, dashboard, `override = true` | |
| 14 | `services/ingestion-scraper/tests/unit/test_repo_scaffolding.py` | operations, system, `override = true` | `.env.example`, topic prefix |
| 15 | `services/ingestion-scraper/tests/unit/test_commit_identity_check.py` | engineering, `override = true` | CI script test |
| 16 | `services/core-hub/**` | core-hub | src (116) incl. Flyway, Gradle files, wrapper |
| 17 | `services/core-hub/src/main/java/dev/auspex/corehub/kafka/**` | core-hub, system | listeners, DLT resolver |
| 18 | `services/core-hub/src/main/java/dev/auspex/corehub/signal/**` | core-hub, system | signal record |
| 19 | `services/core-hub/src/main/java/dev/auspex/corehub/audit/**` | core-hub, system | raw pointer consumer |
| 20 | `services/core-hub/src/test/resources/contract/**` | core-hub, system | generated fixture |
| 21 | `services/core-hub/src/test/java/dev/auspex/corehub/model/**` | core-hub, system | fixture consumer test |
| 22 | `services/backtesting/**` | research | |
| 23 | `services/backtesting/src/auspex_backtesting/stack_bootstrap.py` | research, operations | startup one-shot |
| 24 | `services/strategy/**` | strategy | |
| 25 | `services/backup/**` | operations | |
| 26 | `services/dashboard/**` | dashboard | |
| 27 | `config/hypotheses/**` | research | |
| 28 | `config/universe/**` | research | |
| 29 | `config/short_interest/**` | research | |
| 30 | `config/models/**` | ingestion | |
| 31 | `config/strategies/**` | strategy | |
| 32 | `config/themes.yaml` | strategy | |
| 33 | `docker/**` | operations | compose, exporters, Grafana, Prometheus, init scripts |
| 34 | `docker/topics.yaml` | operations, system | |
| 35 | `.env.example` | operations | |
| 36 | `SETUP.md` | operations | |
| 37 | `verify_pipeline.sh` | operations, engineering | smoke test |
| 38 | `.github/**` | engineering | workflows, identity script |
| 39 | `.gitattributes` | engineering | union merge driver |
| 40 | `VERSIONS.md` | engineering | pins |
| 41 | `tools/**` | engineering | |
| 42 | `docs-check.toml` | engineering | |
| 43 | `DECISIONS.md` | decisions | only an added CHOICE heading triggers G |

Every top-level group at the baseline is covered: root files by 35–40, 43 and `unowned_ok`; `orchestration/README.md`, `services/CLAUDE.md` and the nested `CLAUDE.md`/`README.md` files by `unowned_ok`; every `services/<name>/` by its service rule. A new top-level directory fails F until mapped, which is intended.

### `.github/workflows/docs.yml` (report-only)

```yaml
name: Docs

on:
  pull_request:
    types: [opened, synchronize, reopened, edited]
    branches:
      - develop
      - feature/living-docs-integration
  push:
    branches:
      - develop

jobs:
  docs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
        with:
          fetch-depth: 0

      - name: Set up Python 3.14
        uses: actions/setup-python@v7
        with:
          python-version: '3.14'

      # Not report-only: a broken checker must fail the job.
      - name: Checker tests
        run: |
          set -o pipefail
          python3 -m unittest discover -s tools/docs_check/tests -t . -v 2>&1 | tee "$RUNNER_TEMP/unittest.log"
          grep -qE '^Ran ([1-9][0-9]*) tests?' "$RUNNER_TEMP/unittest.log"

      - name: Write PR body
        if: github.event_name == 'pull_request'
        env:
          PR_BODY: ${{ github.event.pull_request.body }}
        run: printf '%s' "$PR_BODY" > "$RUNNER_TEMP/pr_body.md"

      # Report-only until living-docs-cutover removes continue-on-error.
      - name: Docs check
        continue-on-error: true
        env:
          EVENT_NAME: ${{ github.event_name }}
          BASE_REF: ${{ github.base_ref }}
          BEFORE: ${{ github.event.before }}
        run: |
          if [ "$EVENT_NAME" = pull_request ]; then
            python3 -m tools.docs_check --base "origin/$BASE_REF" --pr-body "$RUNNER_TEMP/pr_body.md"
          elif [ -z "$BEFORE" ] || [ "$BEFORE" = 0000000000000000000000000000000000000000 ]; then
            echo "::notice::new branch: C2 and G skipped"
            python3 -m tools.docs_check
          else
            python3 -m tools.docs_check --base "$BEFORE"
          fi
```

- The PR body is passed only through `env:`, never interpolated with `${{ }}` inside `run:`. A null body becomes an empty env value and an empty file.
- `edited` is a trigger so fixing a `Docs unchanged:` line re-runs the check without a push.
- On push the base is `github.event.before`; all zeros (a new branch) skips C2 and G with a notice. G is skipped on push anyway (no PR body).
- No path filter: every PR can touch ownership.

### `.github/workflows/commit-identity.yml`

Add `- feature/living-docs-integration` under `on.pull_request.branches`, after `develop`. Nothing else changes. Removed again by `living-docs-cutover`.

### Where the checker tests run, and how they are counted

- They run **only in `docs.yml`, step "Checker tests"**, not in `python.yml`: the tool has no dependencies and no `pyproject.toml`, so a uv job would add nothing. Locally: `python3 -m unittest discover -s tools/docs_check/tests -t . -v` from the repo root.
- **Zero tests is a failure.** `unittest` exits 5 when it collects nothing (Python ≥ 3.12; checked on 3.13 in the scoping session), and the step also greps the `Ran N tests` line for N ≥ 1. The test-count floor is the number of required tests below; the PR description records the actual count.
- The step has **no** `continue-on-error`: report-only applies to the docs findings, not to the tool's own tests.

## Out of scope

- Writing any `docs/` file, `AGENTS.md`, PR template or `specs/README.md` change (`living-docs-engineering-workflow`, `agent-instruction-hierarchy` and the domain specs do that).
- Check I (`specs/done` immutability). It waits for the archive policy decision (`## 2026-10-15 — Living docs — PENDING — archive policy for specs/done`).
- Turning enforcement on (removing `continue-on-error`), making `docs` a required check, removing check M: `living-docs-cutover`.
- Fixing any finding the dry run reports in existing files (CLAUDE.md:212 and the rest): the domain specs and `legacy-docs-retirement` own those files.
- A YAML parser: workflow assertions in tests are textual.
- Any application code or service test.

## Constraints

- **Stdlib only**, Python ≥ 3.11 (`tomllib`); CI runs 3.14. No third-party import, no network, no writes outside the temp directories tests create. `subprocess` calls pass argument lists, never `shell=True`.
- **Invariant 8** (synchronous Python) and **Invariant 9** (UTC) apply to the tool as to any Python here: no `asyncio`; any date the tool prints is UTC.
- **Invariant 15** (test-first): each check's tests are written and seen red (`ModuleNotFoundError: tools.docs_check.checks.<name>` or an assertion) before the check exists. The red output goes in the PR description.
- **Mutants are never committed or pushed.** Seeded defects exist only in temp-dir copies built by `fixture_tree.py` under `${TMPDIR:-/tmp}` (Python's `tempfile` honours `TMPDIR`). Mutation checks on the tool's own code are done locally and reverted; no scratch branch is pushed.
- **Conversion provenance and conflict policy** do not apply: this spec writes no requirement. The tool must not make a doc pass by reading code: it checks structure and references, never that a requirement is true.
- **ID rules** implemented exactly: `NS-NNN` with three digits, invariant namespace with one or two digits and CLAUDE numbering; defined once (C); never reused (C2); retired entries are the ledger for `--next`; active specs never cite retired IDs (D).
- **Frozen paths** are the list in `docs-check.toml`; check A fails if one disappears. This spec moves none of them.
- **Decision references** are `DECISIONS.md` headings, never register numbers (check D finds any).
- **Commit identity:** commits carry the requesting person's git identity, no Claude trailers; the `Commit identity` check now also runs on PRs into the integration branch.

## Dependencies

- **Needs:** the integration branch `feature/living-docs-integration` (rollout branch model decision). No prior spec.
- **Hands to:**
  - every domain spec (`living-docs-system-and-contracts`, `living-docs-ingestion`, `living-docs-core-hub`, `living-docs-research`, `living-docs-strategy-and-dashboard`, `living-docs-operations`, `living-docs-engineering-workflow`): checks C, D, E, K, `--next` and `--paths` (each gates only its own files); each removes **only its own** domain(s) from `[rollout] planned_domains` as the last step of its definition of done (`living-docs-strategy-and-dashboard` removes `strategy` and `dashboard`); each fills the matrix `ID` cells of rows in its namespaces and the `IDs` cells of binding decisions rows whose `Fragment rows` carry its prefix, and runs check M (`--domain`, `--decisions --domain`) for them;
  - `agent-instruction-hierarchy`: check L;
  - `legacy-docs-retirement`: check H;
  - `living-docs-engineering-workflow`: the PR template's `Docs unchanged:` syntax (check G) and the `Docs impact` field (check E);
  - `living-docs-cutover`: `--owners` for reconciliation, `[rollout] base`, all three check M modes, the `continue-on-error` flag and the integration-branch entries it removes.

## Affected files

| Path | Action |
|---|---|
| `tools/docs_check/__init__.py`, `__main__.py`, `config.py`, `repo.py`, `markdown.py`, `globs.py` | create |
| `tools/docs_check/checks/{links,paths,ids,references,structure,ownership,legacy,index,verification,agents,matrix}.py` | create |
| `tools/docs_check/tests/__init__.py`, `fixture_tree.py`, `test_*.py` (modules named below) | create |
| `docs-check.toml` | create |
| `.github/workflows/docs.yml` | create |
| `.github/workflows/commit-identity.yml` | modify (one branch line) |
| `.github/scripts/check_commit_identity.sh` | untouched-but-cited |
| `services/ingestion-scraper/tests/unit/test_commit_identity_check.py` | untouched-but-cited (pattern for temp-dir repos) |
| `DECISIONS.md` | untouched-but-cited (CHOICE heading parser, fenced template at `:9-15`) |
| `TODO.md` | modify (this spec's own row only: status `done`, link to `specs/done/docs-check-tooling.md`) |
| `specs/docs-check-tooling.md` → `specs/done/docs-check-tooling.md` | move (Status set to `done`, in this spec's own PR) |

## Required tests

All are `unittest` tests in `tools/docs_check/tests/`, run with `python3 -m unittest discover -s tools/docs_check/tests -t . -v`. "Seeded" tests copy the minimal valid tree into a temp directory (`tempfile`, so under `${TMPDIR:-/tmp}`), apply one defect there, run the CLI in a subprocess, and assert exit 1 and the expected finding line prefix; each also asserts the unmutated copy exits 0. Fixture configs use the namespaces `AAA` and `BBB` plus `INV`.

**Whole tool** (`test_cli.py`, `test_valid_tree.py`)
- `test_every_check_passes_on_minimal_valid_tree` — the minimal tree (two living docs with requirements, verification rows citing real `def` tests, a retired entry, an invariant doc, `docs/requirements.md` as banner + table, `TODO.md` and three specs incl. one `hold`, root and one nested `AGENTS.md` with `CLAUDE.md` beside each, `DECISIONS.md` with a fenced template, ownership rules covering every file, a matrix and a blocking list) exits 0 with empty stdout for the default mode, `--base` + `--pr-body` (diff touching a domain and its owner doc), and all three M modes. Fails if any check reports on valid input.
- `test_findings_are_printed_one_per_line_as_check_path_line_message` — two seeded defects give exactly two stdout lines matching `^[A-M]2? \S+:\d+ .+$`, sorted.
- `test_invalid_config_exits_2_with_no_stdout` — unknown key, bad namespace `AB`, unparsable TOML: each exit 2, stderr `docs_check: error:`.
- `test_config_without_rollout_table_runs_as_if_nothing_is_planned` — the valid fixture with `[rollout]` deleted: a link to a missing owner doc is an A finding (not a notice), a missing owner doc is an F finding, a clean tree exits 0, and `--matrix FILE --domain AAA` exits 2 with `no [rollout] table`.
- `test_unresolvable_base_exits_2` — `--base nosuchref` exit 2.
- `test_only_g_without_base_exits_2` and `test_unknown_check_letter_exits_2`.
- `test_g_without_pr_body_is_skipped_not_failed` — `--base` with a code change and no body: exit 0, stderr notice.
- `test_conflicting_modes_exit_2` — `--next AAA --owners x`.
- `test_outside_a_git_work_tree_exits_2`.
- `test_next_skips_retired_ids` — with `AAA-001` active and `AAA-004` retired, `--next AAA` prints `AAA-005`.
- `test_next_for_invariant_namespace_is_unpadded` — with invariants 1–3 defined, `--next INV` prints the invariant ID numbered 4, with no zero padding.
- `test_paths_limits_reported_findings_and_notices` — two seeded defects in two files; `--paths` naming one file prints only that file's finding, and exit is 1; naming a clean file gives exit 0.
- `test_paths_accepts_comma_lists_and_several_arguments` — `--paths 'a/**,b.md'` and `--paths a/x.md b.md` select the same findings.
- `test_paths_combines_with_only` — seeded A and D defects in one file and a D defect in another; `--only D --paths <first>` prints only the first file's D finding and exits 1; `--only A --paths <second>` exits 0 and the summary is `clean`.
- `test_dry_run_over_repository_completes_without_usage_error` — runs the default mode at the real repo root: exit is 0 or 1 (never 2) and every stdout line matches the output format. Findings are allowed; their counts are recorded (Definition of done), not asserted.

**Parsing** (`test_markdown.py`, `test_globs.py`)
- `test_github_slug_drops_punctuation_and_numbers_duplicates` — `## Known traps`, `## A — b`, ``## `x` y``, a repeated heading → `known-traps`, `a--b`, `x-y`, `…-1`.
- `test_fenced_blocks_hide_links_ids_and_headings`.
- `test_double_star_matches_zero_or_more_segments` — `**/README.md` matches `README.md` and `a/b/README.md`; `services/*/dags/**` does not match `services/x/y/dags/a.py`.
- `test_override_rule_replaces_union_domains`.

**A** (`test_links.py`)
- `test_broken_relative_link_is_reported` (seeded: delete a linked file).
- `test_missing_anchor_is_reported` (seeded: rename the target heading).
- `test_explicit_id_anchor_satisfies_fragment` — `docs/x.md#AAA-001` resolves through `<a id="AAA-001">`.
- `test_missing_frozen_path_is_reported` (seeded: delete a frozen file).
- `test_links_in_specs_done_and_decisions_are_not_checked`.

**B** (`test_paths.py`)
- `test_backticked_tracked_prefix_path_that_does_not_exist_is_reported` (seeded: `` `services/x/gone.py` `` in a living doc).
- `test_path_with_line_or_test_suffix_is_resolved_without_suffix` — `` `services/a.py:12` ``, `` `services/t.py::test_x` ``.
- `test_tokens_outside_prefixes_and_globs_are_ignored` — `` `scripts/x.py` ``, `` `strategy/killswitch/global.json` ``, `` `docs/**/*.md` ``.
- `test_path_check_ignores_specs_and_readmes`.

**C / C2** (`test_ids.py`)
- `test_id_defined_twice_is_reported` (seeded: copy a definition into a second doc).
- `test_retired_and_active_definition_of_one_id_is_reported`.
- `test_invariant_cannot_be_retired`.
- `test_id_removed_since_base_is_reported` (seeded: commit a doc, then delete one retired entry on HEAD; `--base` the first commit).
- `test_id_moved_to_another_file_since_base_passes`.

**D** (`test_references.py`)
- `test_unresolved_id_reference_is_reported` (seeded: `AAA-999` in a living doc).
- `test_invariant_alias_resolves_and_unresolved_alias_is_reported` — "Invariants 1 and 2" resolves; "Invariant 9" with no definition is a finding.
- `test_active_spec_citing_retired_id_is_reported`.
- `test_placeholder_id_is_reported` — `AAA-?` in a spec.
- `test_planned_domain_link_path_id_and_placeholder_are_notices` — with the domain owning `BBB` planned and its owner doc absent: a link to that doc (A), a backticked path to it (B), a reference `BBB-001` and a placeholder `BBB-?` (D) each print a stderr notice, stdout is empty and exit is 0.
- `test_removing_domain_from_planned_turns_notices_into_findings` — the same tree with the domain removed from `planned_domains` exits 1 with A, B, D findings (and the F finding for the missing owner doc).
- `test_unknown_decision_heading_is_reported` (seeded: a cited heading with one changed word); `test_template_citation_with_ellipsis_is_skipped`.
- `test_bare_register_number_in_living_doc_is_reported`.
- `test_register_number_in_spec_is_reported` — in prose, in parentheses after a citation, and in a table cell: each is a finding.
- `test_register_number_in_matrix_is_not_checked` — the matrix path in `[checks.D] exclude` is not scanned.
- `test_cutover_companions_are_excluded_from_d` — a fixture `specs/living-docs-cutover-design.md` and `specs/living-docs-cutover-matrix.md` holding an unresolved ID, a placeholder `AAA-?`, a register number and an unresolved decision heading give no D finding or notice; the same lines in another spec give four D findings.
- `test_double_backtick_citation_of_heading_with_backticks_resolves` — the fixture `DECISIONS.md` carries three headings copied verbatim from the binding CHOICEs that contain backticks (Startup data, PositionSizer `` `fx_rate` ``, New `` `services/strategy/` `` service); each, cited with a double-backtick span in a spec, a verification row and a matrix `Heading` cell, resolves under D, K and M `--decisions`.
- `test_ids_in_readmes_setup_versions_and_legacy_docs_are_resolved` — an unresolved ID in a `README.md`, `SETUP.md`, `VERSIONS.md` or the legacy `docs/requirements.md` index is a finding.
- `test_agent_file_and_readme_citing_retired_id_is_reported`; `test_retired_id_in_legacy_index_is_allowed`.
- `test_pr_body_references_are_checked`.
- `test_no_active_spec_carries_a_register_number` — at the real repo root, `--only D` prints no `register number` finding for `specs/*.md` or `specs/hold/*.md`. Other D findings are allowed.

**E** (`test_structure.py`)
- `test_living_doc_missing_required_h2_is_reported` (seeded: drop `## Retired requirements`).
- `test_last_reviewed_sha_not_ancestor_of_head_is_reported` (seeded: SHA of a commit on an unmerged side branch); `test_unknown_last_reviewed_sha_is_reported`.
- `test_spec_without_docs_impact_is_reported` (seeded).
- `test_blocked_spec_without_blocked_by_is_reported`.
- `test_hold_status_is_accepted`.
- `test_spec_exclusions_cover_matrix_and_design_companion` — `specs/living-docs-cutover-matrix.md` and `specs/living-docs-cutover-design.md` lack spec fields and give no E finding.
- `test_non_normative_docs_and_spec_readme_are_not_checked`.

**F** (`test_ownership.py`)
- `test_unowned_path_is_reported` (seeded: add `newdir/x.py`).
- `test_missing_owner_doc_is_reported_unless_domain_is_planned`.
- `test_planned_domain_with_all_owner_docs_present_is_reported`.
- `test_owners_prints_union_of_domains_for_shared_file` — `--owners` on a messaging file prints both domains; on an unmapped path prints `UNOWNED` and exits 1.
- `test_repository_ownership_map_covers_every_tracked_path` — at the real repo root, `--only F` reports no `unowned` finding (planned-domain owner docs are allowed to be missing). Fails if `docs-check.toml` leaves any tracked path unmapped.

**G** (`test_impact.py`)
- `test_code_change_without_owner_doc_or_disposition_is_reported` (seeded).
- `test_owner_doc_change_satisfies_domain`.
- `test_docs_unchanged_line_satisfies_domain`.
- `test_placeholder_or_empty_reason_is_rejected` — `Docs unchanged: alpha — <reason>` and `Docs unchanged: alpha —`.
- `test_unknown_domain_in_disposition_is_reported`.
- `test_shared_file_requires_every_domain` — a file mapped to two domains with one disposition is one finding.
- `test_added_choice_heading_requires_decisions_disposition`; `test_other_decisions_edit_needs_no_disposition`.
- `test_mutant_and_revert_commits_cancel_in_net_diff`.
- `test_rename_counts_old_and_new_path`.

**H** (`test_legacy.py`)
- `test_requirement_text_in_legacy_index_is_reported_once` (seeded: a requirement paragraph after the table) — one finding with the offending-line count.

**J** (`test_index.py`)
- `test_duplicate_todo_row_is_reported` (seeded: the union-merge resurrection case).
- `test_status_mismatch_is_reported` (seeded: flip a spec's `**Status:**`).
- `test_done_row_outside_specs_done_is_reported` (seeded: move a file to `specs/done/` without updating the row).
- `test_spec_without_row_is_reported`; `test_session_log_table_is_ignored`.
- `test_matrix_and_design_companion_in_specs_done_need_no_row` — after both move under `specs/done/`, J reports nothing for them.

**K** (`test_verification.py`)
- `test_active_id_without_verification_row_is_reported` (seeded).
- `test_tested_row_naming_missing_test_is_reported` (seeded: rename the `def`).
- `test_tested_row_accepts_python_java_and_vitest_names`.
- `test_bare_typescript_test_file_resolves_under_bare_test_dirs` — `auth.test.ts::rejects a bad password` passes when `services/dashboard/src/__tests__/auth.test.ts` contains `it('rejects a bad password'`; renaming the `it` title, or naming a file absent from that directory, is a finding.
- `test_divergent_row_without_decision_citation_is_reported`.
- `test_pending_row_citing_non_pending_heading_is_reported`.
- `test_empty_source_is_reported`.

**L** (`test_agents.py`)
- `test_root_agents_over_budget_is_reported` (seeded: pad to 6145 B).
- `test_nested_agents_over_budget_is_reported` (seeded: pad a nested `AGENTS.md` to 3073 B).
- `test_chain_over_budget_is_reported`.
- `test_claude_md_not_starting_with_agents_import_is_reported`.
- `test_claude_md_with_must_is_reported`; `test_claude_md_over_512_bytes_is_reported`.
- `test_import_in_agents_md_is_reported` — `@docs/x.md` outside code is a finding; `a@b.md` inside inline code is not.
- `test_at_followed_by_a_word_is_not_an_import` — "Nothing is imported; no @imports here" gives no L finding.
- `test_claude_md_without_sibling_agents_md_is_reported`.

**M** (`test_matrix.py`, rollout only; deleted with check M)
- `test_matrix_row_without_defined_id_is_reported` (seeded: blank the `ID` cell of a `move` row).
- `test_retire_row_must_point_at_retired_definition`.
- `test_matrix_id_whose_source_lacks_row_source_reference_is_reported` (seeded: the ID's verification `Source` names `CLAUDE.md` while the row's Source is `§13 ¶2`).
- `test_source_reference_ignores_line_numbers` — a row with Source `CLAUDE.md:137` passes against a verification Source `CLAUDE.md:140` (lines moved) and against `CLAUDE.md`; a row with `requirements §13 ¶2` passes against `requirements §13`.
- `test_section_relative_source_resolves_against_section_header` — under ``### `docs/x.md` ``, a row with Source `:85` needs `docs/x.md` in the ID's verification Source; with no path-bearing heading above it, the row is a finding.
- `test_at_risk_or_scoping_or_same_as_source_gets_id_existence_only` — rows with Source `at-risk class #18`, `C5` and `same as M-AAA-001` pass with any defined `AAA` ID whatever its Source, and fail with an undefined one.
- `test_prose_or_two_word_label_source_gets_id_existence_only` — rows with Source `Statuses (new)`, `E F18` and `D F6` yield no reference (no token contains `/` or a file extension) and pass with any defined `AAA` ID.
- `test_matrix_row_id_is_not_an_id_reference` — a scanned spec containing `M-AAA-251` and no `AAA-251` definition gives no check D finding; a bare `AAA-251` in the same file does.
- `test_trap_row_may_name_a_section_anchor` — a `trap` row whose ID cell is `docs/x.md#known-traps` passes when that section contains the row's source reference; the same anchor on a `requirement` row, or an anchor to a missing H2, is a finding.
- `test_trap_section_without_row_source_reference_is_reported` (seeded: the `## Known traps` section never names the row's Source path).
- `test_trap_row_explicit_item_anchor_checks_only_that_item` — `docs/x.md#trap-dlt-suffix` on a list item inside `## Known traps` passes when that item names the source; the source named only in a sibling item is a finding; the same explicit anchor outside the H2 is a finding.
- `test_link_row_target_must_carry_anchor_or_source` — a `link` row whose ID cell is `AGENTS.md#where-things-are` passes; a missing anchor is a finding; `docs/x.md` with no anchor passes only when the file contains the row's source reference; an empty ID cell on a `link` row is not checked.
- `test_matrix_without_id_column_exits_2`.
- `test_every_choice_heading_must_be_classified` (seeded: drop one row); `test_fenced_template_heading_is_not_a_choice` — the fixture's fenced `[BLOCKED | FLAG | CHOICE …]` line is not required in the table.
- `test_binding_choice_needs_an_id_citing_it_as_source` (seeded: remove the heading from the ID's `Source` cell).
- `test_decisions_check_filtered_by_domain` — with `--domain AAA`, an empty binding row whose fragment row `M-BBB-004` has `NS` = `AAA` is a finding (selected by the NS cell, not the `M-BBB-` prefix); an empty binding row whose only fragment row `M-AAA-009` has `NS` = `BBB` is not; a fragment row id missing from the tables is a finding; an empty binding row of `BBB` and an unclassified heading are not.
- `test_pending_row_citing_blocking_heading_is_reported` (seeded) and `test_pending_row_citing_non_blocking_heading_passes`.
- `test_blocking_list_cells_are_plain_suffix_text` — a cell `| raw-pointer contract |` matches a cited heading ending in ` — raw-pointer contract`.
- `test_docs_workflow_runs_report_only_with_body_through_env` — textual checks on the real `.github/workflows/docs.yml`: the four PR types, both PR branches, push to `develop`, `fetch-depth: 0`, `continue-on-error: true` only on the "Docs check" step, the PR body appears only under `env:`, the all-zeros guard is present.
- `test_commit_identity_workflow_covers_integration_branch` — the real `commit-identity.yml` lists `feature/living-docs-integration` under `pull_request.branches`.

The last two read rollout-only workflow lines and live in the check M module so the cutover deletes them with it.

Test-count floor: 121 (the tests named above). The PR description gives the real count.

## Definition of done

From the repo root on `feature/living-docs-checker`, rebased onto `feature/living-docs-integration`:

```bash
python3 -m unittest discover -s tools/docs_check/tests -t . -v 2>&1 | tail -3
python3 -m tools.docs_check --only F; echo "F exit=$?"
python3 -m tools.docs_check --next ENG
python3 -m tools.docs_check --owners services/ingestion-scraper/src/auspex_ingest/messaging/kafka_producer.py DECISIONS.md
OUT=$(mktemp); python3 -m tools.docs_check > "$OUT"; echo "dry-run exit=$?"
cut -d' ' -f1 "$OUT" | sort | uniq -c
python3 -m tools.docs_check --only D | grep -c 'register number'
```

Expected:
- `Ran N tests` with N ≥ 121, then `OK`.
- `F exit=0`.
- `ENG-001`.
- `…kafka_producer.py	ingestion,system	…` and `DECISIONS.md	decisions	docs/**/*.md`.
- `0` register-number findings (the scoping specs cite decisions by heading only).
- `dry-run exit=1` (or 0). The per-check counts are pasted into the PR description and into this spec's Notes when it is archived. They are a record, not a target. Expected shape at the integration branch's cut point:

| Check | Expected at baseline | Why |
|---|---|---|
| A | 0 | no broken relative links at e51f742; every frozen path exists |
| B | ≥ 1 | `CLAUDE.md:212` → `specs/edgar-efts-fixture-alignment.md`; possibly more in `docs/*.md` legacy files |
| C, C2, K | 0 | no living doc defines an ID yet |
| D | many findings, many notices | "Invariant N" in active specs and `CLAUDE.md` files (notices while `system` is planned); cited DECISIONS headings whose text differs from the heading; no register numbers |
| E | ≈ 30 | every baseline active and hold spec lacks `Docs impact` |
| F | 0 | required (acceptance above) |
| G | skipped | no PR body |
| H | 1 | `docs/requirements.md` is still full text |
| J | 0 expected | every rollout spec has a `TODO.md` row |
| L | ≥ 6 | no root `AGENTS.md`; five `CLAUDE.md` files without `@AGENTS.md`, over 512 B, with must/never/always |

CI: the `Docs` workflow's "Checker tests" step is green on the PR; "Docs check" may report findings (report-only); `Commit identity` runs on the PR into the integration branch.

## Compatibility

- **Report-only.** No existing workflow changes behaviour; `docs.yml` cannot fail a PR on findings until the cutover. Its tests step can fail, but only on changes to `tools/`.
- **Agents and readers** see no doc change. Fixtures are built in temp dirs, so no stray `CLAUDE.md` or `docs/` tree appears under `tools/`.
- **Existing tests** are untouched. `test_repo_scaffolding.py` and the stack tests do not scan `tools/` or `docs-check.toml`.
- **Commit identity** keeps checking PRs into `main` and `develop` exactly as before; the added branch only widens it.
- **Python 3.13 and 3.14** both run the tool and its tests.

## Rollback

On the integration branch: one PR from a branch off `feature/living-docs-integration` that reverts this spec's merge range (`git revert --no-commit <integration-branch tip before this spec merged>..<tip after>`, committed once), merged with the owner's word like any sub-spec. This spec appends nothing to `DECISIONS.md`; if a rollback happens, the PR appends a `FLAG` entry recording it. That removes `tools/docs_check/`, `docs-check.toml`, `docs.yml` and the identity-workflow line. Any domain spec already merged keeps its docs; their checks simply stop running until the tool is restored. Nothing reaches `develop` before the cutover, so `develop` needs no rollback.

## Notes

- **Matrix `ID` column.** `specs/living-docs-cutover-matrix.md` has an `ID` column in every fragment table, empty at the start. Each domain spec fills the cells of rows in its own namespaces, plus the `IDs` cells of binding rows in the decisions table whose `Fragment rows` carry its prefix. A table without the column makes check M exit 2 rather than report every row.
- **Matrix Source cells are compared at document level.** Check M compares each row's file path, `requirements §N` or DECISIONS heading with the ID's verification `Source`; line numbers are never compared. A mismatch means the doc's verification `Source` cell lacks the reference, and the fix goes there: domain specs edit only `ID` cells of the matrix. A matrix cell that is itself wrong is reported to `living-docs-cutover`, which owns the matrix.
- **`SpecialistClassifier` anchor.** `config/hypotheses/h9.yaml:18` cites `specs/sec-ownership-datasets.md#SpecialistClassifier`. Explicit anchors match case-sensitively, so the `<a id="SpecialistClassifier"></a>` the research spec adds resolves it. Check A does not scan YAML either way.
- **Why register numbers are banned everywhere scanned.** They are labels from the owner's working register, which is not in the repo; a cold reader cannot resolve them. Only the migration matrix, which is not scanned by D, keeps them in note cells.
- **Line numbers in findings for M `--decisions`** point at the `DECISIONS.md` heading line for missing rows and at the matrix line otherwise.
- **H finds one line, not hundreds.** Reporting every legacy line would bury every other finding during the rollout.
- **Why G treats `tests/**` as owned.** Test-only changes usually need `Docs unchanged: <domain> — test-only`; that is the intended prompt, and the reviewer judges whether it is true.
- A finding class nobody anticipated during the rollout is fixed in the owning doc, never by weakening a check.
- **Dry run at completion** (`feature/living-docs-checker` on develop @ b7582c3, default mode, no `--base`): exit 1, 58 findings and 315 notices. A=2: two links in `specs/legacy-docs-retirement.md:80` and `specs/living-docs-operations.md:85` quote text meant for `docs/*.md`, so from `specs/` they resolve to `specs/research/…` and `specs/operations/…`. B=1: `CLAUDE.md:213` → `specs/edgar-efts-fixture-alignment.md`. C=0, K=0. D=0 findings and 315 notices: 309 invariant references or aliases while `system` is planned, 4 placeholders (`CON-?` ×3, `OPS-?`), and one `ENG` and one `RES` reference without a definition. All 238 decision citations in D scope resolve. 0 register numbers. E=33: 30 active and hold specs lack `**Docs impact:**`; `live-trading` lacks `## What this builds`; `research-results-view` lacks `## What this builds` and `## Required tests`. F=0. G skipped (no PR body). H=1 (268 offending lines). J=0. L=21: no root `AGENTS.md`, and for each of the five `CLAUDE.md` files no sibling `AGENTS.md`, a first line that is not `@AGENTS.md`, over 512 B, and a rule word.
- **Ownership rules are `[[ownership.rules]]`.** TOML cannot hold an `[ownership]` table (for `unowned_ok`) and an `[[ownership]]` array under the same key, so the rules are an array inside the table.

"""The minimal valid repository the checker tests copy, seed one defect into, and run the CLI against.

The tree is Python data written into a temporary directory and committed there; nothing under `tools/` is a
fixture file, so no stray `CLAUDE.md` or `docs/` tree exists in the real repository. The template repository is
built once per test process and copied (with its `.git`) for every test.
"""

import atexit
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MATRIX = "specs/living-docs-cutover-matrix.md"
BLOCKING_LIST = "specs/second.md"
SEED_SHA = "{SEED}"

# Isolates the fixture's own git calls from the developer's global hooks and signing settings.
_GIT_ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_DATE": "2026-01-01T00:00:00+00:00",
    "GIT_COMMITTER_DATE": "2026-01-01T00:00:00+00:00",
}

CONFIG = """\
[namespaces]
invariant = "INV"
ids = ["AAA", "BBB"]
frozen_paths = ["README.md", "docs/README.md"]

[living_docs]
include = ["docs/**/*.md"]
non_normative = ["docs/README.md", "docs/requirements.md"]
required_sections = ["Scope", "Requirements", "Verification", "Retired requirements"]

[specs]
include = ["specs/*.md", "specs/hold/*.md"]
exclude = ["specs/README.md", "specs/living-docs-cutover-matrix.md", "specs/living-docs-cutover-design.md"]
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
           "tools/docs_check/tests/**"]

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
bare_test_dirs = ["services/dashboard/src/__tests__"]

[budgets]
root_agents_bytes = 6144
nested_agents_bytes = 3072
chain_bytes = 16384
claude_md_bytes = 512

# rollout-start
[rollout]
planned_domains = ["beta"]
matrix = "specs/living-docs-cutover-matrix.md"
# rollout-end

[domains.system]
namespaces = ["INV"]
owners = ["docs/invariants.md"]
[domains.alpha]
namespaces = ["AAA"]
owners = ["docs/alpha.md"]
[domains.beta]
namespaces = ["BBB"]
owners = ["docs/beta.md"]
[domains.decisions]
namespaces = []
owners = ["docs/**/*.md"]

[ownership]
unowned_ok = ["**/README.md", "**/AGENTS.md", "**/CLAUDE.md", "TODO.md", "specs/**", "docs/**",
              "**/.gitkeep", "**/.gitignore"]

[[ownership.rules]]
glob = "services/alpha/**"
domains = ["alpha"]

[[ownership.rules]]
glob = "services/alpha/messaging/**"
domains = ["alpha", "system"]

[[ownership.rules]]
glob = "services/alpha/tests/test_stack_*.py"
domains = ["system"]
override = true

[[ownership.rules]]
glob = "services/beta/**"
domains = ["beta"]

[[ownership.rules]]
glob = "services/dashboard/**"
domains = ["alpha"]

[[ownership.rules]]
glob = "DECISIONS.md"
domains = ["decisions"]

[[ownership.rules]]
glob = "SETUP.md"
domains = ["system"]

[[ownership.rules]]
glob = "VERSIONS.md"
domains = ["system"]

[[ownership.rules]]
glob = "docs-check.toml"
domains = ["system"]
"""

HEADING_STARTUP = "2026-10-07 — Startup data — CHOICE — data fills itself on `up`; prices refresh daily"
HEADING_SIZER = "2026-10-07 — Market simulation — CHOICE — PositionSizer `fx_rate` is EUR per USD"
HEADING_STRATEGY = (
    "2026-09-20 — Strategy layer session 2 — CHOICE — New `services/strategy/` service (not extending backtesting)"
)
FIRST_CHOICE = "2026-01-01 — Alpha — CHOICE — first choice"
OPEN_QUESTION = "2026-01-02 — Alpha — PENDING — open question"
HISTORY_CHOICE = "2026-01-03 — Beta — CHOICE — history choice"
BLOCKING_PENDING = "2026-01-04 — Gamma — PENDING — raw-pointer contract"

DECISIONS = f"""\
# Decisions

Format:

```
## YYYY-MM-DD — <topic> — [BLOCKED | FLAG | CHOICE | VERIFIED | PENDING] — <short title>
```

---

## {FIRST_CHOICE}
**What:** alpha writes once.

## {OPEN_QUESTION}
**What:** not decided yet.

## {HISTORY_CHOICE}
**What:** an old choice.

## {BLOCKING_PENDING}
**What:** blocks the cutover.

## {HEADING_STRATEGY}
**What:** a new service.

## {HEADING_SIZER}
**What:** units.

## {HEADING_STARTUP}
**What:** startup.
"""

ALPHA_DOC = f"""\
# Alpha

Last reviewed against: develop @ `{SEED_SHA}`

## Scope

What alpha covers. Invariants 1 and 2 bound it; see [the invariants](invariants.md#INV-1).

## Requirements

- <a id="AAA-001"></a>**AAA-001** Alpha writes once per key.
- <a id="AAA-002"></a>**AAA-002** Alpha keeps the open behaviour until the owner decides.
- <a id="AAA-003"></a>**AAA-003** Alpha sizes positions as decided.

## Known traps

- The suffix is lowercase (from CLAUDE.md, Known traps).
- <a id="trap-dlt-suffix"></a>The partition is -1 (from `services/CLAUDE.md`, traps).

## Verification

| ID | Source | Verified by | Status |
|---|---|---|---|
| AAA-001 | `CLAUDE.md:140`; requirements §13; `{FIRST_CHOICE}` | `services/alpha/tests/test_app.py::test_alpha_one` | `tested` |
| AAA-002 | docs/legacy.md; `{OPEN_QUESTION}` | none yet | `pending-decision` |
| AAA-003 | ``{HEADING_STARTUP}``; ``{HEADING_SIZER}``; ``{HEADING_STRATEGY}`` | `services/alpha/tests/test_app.py::test_alpha_two` | `divergent` |

## Retired requirements

- **AAA-004** Alpha wrote twice (from requirements §13). Replaced by AAA-001.
"""

INVARIANTS_DOC = f"""\
# Invariants

Last reviewed against: develop @ {SEED_SHA}

## Scope

Numbered as in the root agent file.

## Requirements

- <a id="INV-1"></a>**INV-1** The scraper writes only to the archive and the bus.
- <a id="INV-2"></a>**INV-2** The hub is the sole writer.
- <a id="INV-3"></a>**INV-3** DAGs call the HTTP API.

## Verification

| ID | Source | Verified by | Status |
|---|---|---|---|
| INV-1 | CLAUDE.md | `services/alpha/tests/test_app.py::test_alpha_one` | tested |
| INV-2 | CLAUDE.md | `services/alpha/src/WriterTest.java::onlyHubWrites`, `auth.test.ts::rejects a bad password` | tested |
| INV-3 | CLAUDE.md | ArchUnit rule in the hub | enforced |

## Retired requirements
"""

EMPTY_LIVING_DOC = f"""\
# Beta

Last reviewed against: develop @ {SEED_SHA}

## Scope

Nothing yet.

## Requirements

## Verification

## Retired requirements
"""


def spec_text(title: str, status: str, body: str = "", blocked_by: str | None = None) -> str:
    """A spec carrying every required field and section, with `body` added under Context."""
    blocked = f"**Blocked by:** {blocked_by}\n" if blocked_by else ""
    slug = title.lower().replace(" ", "-")
    return f"""\
# {title}

**Status:** {status}
{blocked}**Branch:** `feature/{slug}`
**Docs impact:** alpha — docs/alpha.md

---

## Context

{body}

## What this builds

Something.

## Out of scope

Nothing.

## Constraints

None.

## Required tests

- `test_something`

## Definition of done

Tests pass.
"""


FIRST_SPEC_BODY = f"""\
Cites `## {FIRST_CHOICE}` and builds AAA-001 under Invariant 3.
Also cites ``{HEADING_STARTUP}``, ``{HEADING_SIZER}`` and ``{HEADING_STRATEGY}``.
The beta owner doc is [planned](../docs/beta.md); traps are in [alpha](../docs/alpha.md#known-traps);
the code is [here](../services/alpha/app.py)."""

SECOND_SPEC_BODY = f"""\
Waits on `{OPEN_QUESTION}`.

## Blocking decisions

| Heading suffix |
|---|
| raw-pointer contract |
| `as-of reads` |"""

MATRIX_TEXT = f"""\
# Migration matrix

## Decisions table

| Heading | Classification | IDs | Fragment rows |
|---|---|---|---|
| `## {FIRST_CHOICE}` | binding | AAA-001 | M-AAA-001 |
| `## {HISTORY_CHOICE}` | history |  | M-BBB-001 |
| ``## {HEADING_STRATEGY}`` | binding | AAA-003 | M-AAA-006 |
| ``## {HEADING_SIZER}`` | binding | AAA-003 | M-AAA-006 |
| ``## {HEADING_STARTUP}`` | binding | AAA-003 | M-AAA-006 |

## Alpha (AAA)

### `docs/legacy.md`

| Row | Source (path:line or §) | Rule or content | Class | Disposition | Target | NS | Spec | Decision / note | ID |
|---|---|---|---|---|---|---|---|---|---|
| M-AAA-001 | `CLAUDE.md:137` | writes once | requirement | move | docs/alpha.md | AAA | first |  | AAA-001 |
| M-AAA-002 | requirements §13 ¶2 | writes once | requirement | ratify | docs/alpha.md | AAA | first |  | AAA-001 |
| M-AAA-003 | `:85` | open behaviour | requirement | move | docs/alpha.md | AAA | first |  | AAA-002 |
| M-AAA-004 | requirements §13 | wrote twice | requirement | retire | docs/alpha.md | AAA | first |  | AAA-004 |
| M-AAA-005 | CLAUDE.md:200 | lowercase suffix | trap | move | docs/alpha.md | AAA | first |  | docs/alpha.md#known-traps |
| M-AAA-006 | C5 | sizing | requirement | divergent | docs/alpha.md | AAA | first |  | AAA-003 |
| M-AAA-007 | `CLAUDE.md:12` | where things are | process | link | AGENTS.md | AAA | first |  | AGENTS.md#where-things-are |
| M-AAA-008 | `CLAUDE.md:13` | routing | process | link | AGENTS.md | AAA | first |  |  |
| M-BBB-001 | `CLAUDE.md:14` | beta rule | requirement | move | docs/beta.md | BBB | first |  |  |
| M-AAA-009 | `CLAUDE.md:15` | history | rationale | keep | — | — | first |  |  |
"""

TREE = {
    "docs-check.toml": CONFIG,
    "DECISIONS.md": DECISIONS,
    "SETUP.md": "# Setup\n\nNothing to set up by hand.\n",
    "VERSIONS.md": "# Versions\n\nPinned elsewhere.\n",
    "AGENTS.md": "# Agent guide\n\n## Where things are\n\n- Specs: `specs/`. Living docs: `docs/`.\n"
    "- The decisions log: `DECISIONS.md`.\n",
    "CLAUDE.md": "@AGENTS.md\n",
    "services/AGENTS.md": "# Services\n\nService notes.\n",
    "services/CLAUDE.md": "@../AGENTS.md\n@AGENTS.md\n",
    "services/alpha/app.py": "VALUE = 1\n",
    "services/alpha/messaging/producer.py": "TOPIC = 'alpha'\n",
    "services/alpha/tests/test_app.py": "def test_alpha_one():\n    assert True\n\n\ndef test_alpha_two():\n"
    "    assert True\n",
    "services/alpha/src/WriterTest.java": "class WriterTest {\n    @Test\n    void onlyHubWrites() {}\n}\n",
    "services/dashboard/src/__tests__/auth.test.ts": "it('rejects a bad password', () => {});\n",
    "docs/README.md": "# Docs\n\nThe living docs: [alpha](alpha.md), [invariants](invariants.md).\n",
    "docs/alpha.md": ALPHA_DOC,
    "docs/invariants.md": INVARIANTS_DOC,
    "docs/requirements.md": "# Requirements\n\nNot authoritative. An index from old sections to requirement IDs.\n\n"
    "| § | Now |\n|---|---|\n| §13 | AAA-001 |\n| §14 | AAA-004 |\n",
    "TODO.md": """\
# TODO

| Spec | Status | Notes |
|---|---|---|
| [First](specs/first.md) | `ready` | the first |
| [Second](specs/second.md) | `blocked` | waits |
| [Third](specs/hold/third.md) | `hold` | parked |
| [Old](specs/done/old.md) | `done` | finished |

## Session log

| Date | Spec worked | Left off at | Blocked? |
|---|---|---|---|
| 2026-01-01 | First | scoping | No |
""",
    "specs/README.md": "# Specs\n\nOne file per change.\n",
    "specs/first.md": spec_text("First", "ready", FIRST_SPEC_BODY),
    "specs/second.md": spec_text("Second", "blocked", SECOND_SPEC_BODY, blocked_by=f"`{OPEN_QUESTION}`"),
    "specs/hold/third.md": spec_text("Third", "hold", "Parked."),
    "specs/done/old.md": spec_text("Old", "done", "Finished."),
    MATRIX: MATRIX_TEXT,
}


def git(root: Path, *args: str) -> str:
    """Run git in `root` with the fixture environment and return stdout."""
    return subprocess.run(
        ["git", *args], cwd=root, env=_GIT_ENV, check=True, capture_output=True, text=True
    ).stdout.strip()


@dataclass
class Result:
    code: int
    stdout: str
    stderr: str

    @property
    def lines(self) -> list[str]:
        return [line for line in self.stdout.splitlines() if line]

    @property
    def notices(self) -> list[str]:
        return [line for line in self.stderr.splitlines() if " notice " in line]


def run_checker(root: Path, *args: str) -> Result:
    """Run `python3 -m tools.docs_check --root root ...` from the real repository root."""
    proc = subprocess.run(
        [sys.executable, "-m", "tools.docs_check", "--root", str(root), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    return Result(proc.returncode, proc.stdout, proc.stderr)


class Tree:
    """One temporary copy of the minimal valid repository."""

    def __init__(self, root: Path):
        self.root = root

    def path(self, rel: str) -> Path:
        return self.root / rel

    def read(self, rel: str) -> str:
        return self.path(rel).read_text(encoding="utf-8")

    def write(self, rel: str, text: str) -> None:
        target = self.path(rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def append(self, rel: str, text: str) -> None:
        self.write(rel, self.read(rel) + text)

    def replace(self, rel: str, old: str, new: str) -> None:
        text = self.read(rel)
        if old not in text:
            raise AssertionError(f"{old!r} not in {rel}")
        self.write(rel, text.replace(old, new, 1))

    def delete(self, rel: str) -> None:
        self.path(rel).unlink()

    def git(self, *args: str) -> str:
        return git(self.root, *args)

    def commit(self, message: str = "change") -> str:
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", message)
        return self.head()

    def head(self) -> str:
        return self.git("rev-parse", "HEAD")

    def body(self, text: str) -> str:
        """Write a PR body inside `.git`, outside the checked file set, and return its path."""
        target = self.root / ".git" / "pr_body.md"
        target.write_text(text, encoding="utf-8")
        return str(target)

    def drop_rollout(self) -> None:
        text = self.read("docs-check.toml")
        self.write("docs-check.toml", re.sub(r"# rollout-start.*?# rollout-end\n", "", text, flags=re.S))

    def run(self, *args: str) -> Result:
        return run_checker(self.root, *args)


_template: Path | None = None


def _build_template() -> Path:
    base = Path(tempfile.mkdtemp(prefix="docs-check-template-"))
    atexit.register(shutil.rmtree, base, True)
    root = base / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.name", "Fixture Person")
    git(root, "config", "user.email", "fixture@example.invalid")
    git(root, "config", "commit.gpgsign", "false")
    (root / "README.md").write_text("# Fixture\n\nSee [the docs](docs/README.md).\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "seed")
    seed = git(root, "rev-parse", "HEAD")
    for rel, text in TREE.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text.replace(SEED_SHA, seed), encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "tree")
    return root


def new_tree() -> tuple[Tree, tempfile.TemporaryDirectory]:
    """Copy the template repository into a fresh temporary directory."""
    global _template
    if _template is None:
        _template = _build_template()
    holder = tempfile.TemporaryDirectory(prefix="docs-check-")
    root = Path(holder.name) / "repo"
    shutil.copytree(_template, root, symlinks=True)
    return Tree(root), holder


class CheckerCase(unittest.TestCase):
    """Base class: fresh fixture trees and seeded-defect assertions."""

    def tree(self) -> Tree:
        tree, holder = new_tree()
        self.addCleanup(holder.cleanup)
        return tree

    def assertClean(self, result: Result) -> None:
        self.assertEqual(result.code, 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}")
        self.assertEqual(result.stdout, "")

    def assertFinding(self, result: Result, prefix: str) -> None:
        self.assertEqual(result.code, 1, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}")
        self.assertTrue(
            any(line.startswith(prefix) for line in result.lines),
            f"no line starting {prefix!r} in:\n{result.stdout}\nstderr:\n{result.stderr}",
        )

    def assertSeeded(self, mutate, prefix: str, *args: str, commit: bool = True) -> Result:
        """The clean copy passes; after `mutate` (committed) the run exits 1 with a line starting `prefix`."""
        tree = self.tree()
        self.assertClean(tree.run(*args))
        mutate(tree)
        if commit:
            tree.commit("seeded defect")
        result = tree.run(*args)
        self.assertFinding(result, prefix)
        return result

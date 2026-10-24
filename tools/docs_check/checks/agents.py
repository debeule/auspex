"""Check L: agent instruction files. `AGENTS.md` carries the content within byte budgets and never imports;
every `CLAUDE.md` is a short shim beside one that imports the `AGENTS.md` chain from the root down to its own
directory, with no rule words of its own. Claude Code expands imports only in the launch directory's
`CLAUDE.md`, so a nested shim has to import its ancestors itself.
"""

import posixpath
import re

from .. import globs, markdown
from . import Context, Finding

_AGENT_FILES = ("**/AGENTS.md", "**/CLAUDE.md")
_EXCLUDED = ("tools/docs_check/tests/**",)
_RULE_WORDS = re.compile(r"\b(must|never|always)\b", re.IGNORECASE)
_IMPORT = re.compile(r"(^|\s)@[\w./-]+\.\w+")


def _directory(path: str) -> str:
    return posixpath.dirname(path)


def _ancestors(directory: str) -> list[str]:
    """The root ("") and every directory down to and including `directory`."""
    chain = [""]
    parts = directory.split("/") if directory else []
    for end in range(1, len(parts) + 1):
        chain.append("/".join(parts[:end]))
    return chain


def _expected_imports(directory: str, agents: dict[str, str]) -> list[str]:
    """`@` lines a `CLAUDE.md` in `directory` carries: every ancestor `AGENTS.md`, root first, then its own."""
    lines = []
    for ancestor in _ancestors(directory)[:-1] if directory else []:
        if ancestor in agents:
            lines.append("@" + posixpath.relpath(agents[ancestor], directory))
    return lines + ["@AGENTS.md"]


def run(ctx: Context) -> list[Finding]:
    budgets = ctx.cfg.section("budgets")
    files = [p for p in ctx.repo.files if globs.match_any(_AGENT_FILES, p) and not globs.match_any(_EXCLUDED, p)]
    agents = {_directory(p): p for p in files if posixpath.basename(p) == "AGENTS.md"}
    claudes = [p for p in files if posixpath.basename(p) == "CLAUDE.md"]
    found = []

    if "" not in agents:
        found.append(Finding("L", "AGENTS.md", 0, "root AGENTS.md is missing"))
    sizes = {directory: ctx.repo.size(path) for directory, path in agents.items()}
    for directory, path in agents.items():
        budget = budgets["root_agents_bytes"] if directory == "" else budgets["nested_agents_bytes"]
        if sizes[directory] > budget:
            found.append(Finding("L", path, 0, f"{sizes[directory]} bytes, over the {budget}-byte budget"))
        chain = sum(sizes[d] for d in _ancestors(directory) if d in sizes)
        if chain > budgets["chain_bytes"]:
            found.append(Finding("L", path, 0, f"AGENTS.md chain to here is {chain} bytes, over the "
                                               f"{budgets['chain_bytes']}-byte budget"))
        for line, content in markdown.unfenced_lines(ctx.repo.text(path)):
            if _IMPORT.search(markdown.strip_code_spans(content)):
                found.append(Finding("L", path, line, "AGENTS.md must not @import other files"))

    for path in claudes:
        text = ctx.repo.text(path)
        if _directory(path) not in agents:
            found.append(Finding("L", path, 0, "no AGENTS.md beside this CLAUDE.md"))
        imports = [line.strip() for line in text.splitlines() if line.strip()]
        expected = _expected_imports(_directory(path), agents)
        if imports != expected:
            found.append(Finding("L", path, 1, "imports are not the AGENTS.md chain " + ", ".join(expected)))
        size = ctx.repo.size(path)
        if size > budgets["claude_md_bytes"]:
            found.append(Finding("L", path, 0, f"{size} bytes, over the {budgets['claude_md_bytes']}-byte budget"))
        for line, content in enumerate(text.splitlines(), 1):
            word = _RULE_WORDS.search(content)
            if word:
                found.append(Finding("L", path, line, f"rule word '{word.group(1)}' belongs in AGENTS.md"))
                break
    return found

"""Check L: agent instruction files. `AGENTS.md` carries the content within byte budgets and never imports;
every `CLAUDE.md` is a short `@AGENTS.md` shim beside one, with no rule words of its own.
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
        first = text.splitlines()[0] if text else ""
        if first.strip() != "@AGENTS.md":
            found.append(Finding("L", path, 1, "first line is not @AGENTS.md"))
        size = ctx.repo.size(path)
        if size > budgets["claude_md_bytes"]:
            found.append(Finding("L", path, 0, f"{size} bytes, over the {budgets['claude_md_bytes']}-byte budget"))
        for line, content in enumerate(text.splitlines(), 1):
            word = _RULE_WORDS.search(content)
            if word:
                found.append(Finding("L", path, line, f"rule word '{word.group(1)}' belongs in AGENTS.md"))
                break
    return found

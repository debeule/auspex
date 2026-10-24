"""Check J: the spec table in `TODO.md` matches the spec files (targets, statuses, directories, one row each)."""

import re

from .. import globs, markdown
from . import Context, Finding, spec_status

_LINK = re.compile(r"^\[[^\]]*\]\(([^)\s]+)\)")
_SPEC_FILES = ("specs/*.md", "specs/hold/*.md", "specs/done/*.md")
_DIRECTORY = {"done": "specs/done/", "hold": "specs/hold/"}


def _in_directory(target: str, status: str) -> bool:
    directory = _DIRECTORY.get(status, "specs/")
    return target.startswith(directory) and "/" not in target[len(directory):]


def run(ctx: Context) -> list[Finding]:
    index = ctx.cfg.section("checks", "J", "index")
    found = []
    seen: dict[str, int] = {}
    for table in markdown.tables(ctx.repo.text(index)):
        for line, cells in table.rows:
            match = _LINK.match(cells[0]) if cells else None
            if not match or not match.group(1).startswith("specs/"):
                continue
            target = match.group(1)
            if target in seen:
                found.append(Finding("J", index, line, f"{target} is listed twice (first at line {seen[target]})"))
                continue
            seen[target] = line
            if target not in ctx.repo.file_set:
                found.append(Finding("J", index, line, f"{target} does not exist"))
                continue
            status = cells[1].strip().strip("`").strip() if len(cells) > 1 else ""
            spec = spec_status(ctx.repo.text(target))
            if spec is None:
                found.append(Finding("J", index, line, f"{target} has no **Status:** line"))
            elif spec[1] != status:
                found.append(Finding("J", index, line, f"status '{status}' but {target} says '{spec[1]}'"))
            if not _in_directory(target, status):
                found.append(Finding("J", index, line,
                                     f"a '{status}' row must point directly under {_DIRECTORY.get(status, 'specs/')}"))
    excluded = set(ctx.cfg.section("specs", "exclude")) | set(ctx.cfg.section("checks", "J", "exclude"))
    for path in ctx.repo.files:
        if globs.match_any(_SPEC_FILES, path) and path not in excluded and path not in seen:
            found.append(Finding("J", path, 0, f"spec has no {index} row"))
    return found

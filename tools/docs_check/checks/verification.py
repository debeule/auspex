"""Check K: every active ID has exactly one verification row in its doc, and each row's evidence holds up.

The check reads structure and names only: it confirms a cited test exists, never that the requirement is true.
"""

import re

from .. import markdown
from . import Context, Finding, citations

STATUSES = ("tested", "enforced", "untested", "divergent", "pending-decision")
_TS_TEST = re.compile(r"\.test\.tsx?$")
_BARE_TOKEN = re.compile(r"(\S+::\S+)")


def _test_tokens(cell: str) -> list[str]:
    tokens = [span for span in markdown.code_spans(cell) if "::" in span]
    tokens += _BARE_TOKEN.findall(markdown.strip_code_spans(cell))
    return [t.strip().rstrip(",;") for t in tokens]


def _test_file(ctx: Context, path: str) -> str | None:
    if "/" not in path and _TS_TEST.search(path):
        for directory in ctx.cfg.section("checks", "K", "bare_test_dirs"):
            candidate = f"{directory.rstrip('/')}/{path}"
            if candidate in ctx.repo.file_set:
                return candidate
        return None
    return path if path in ctx.repo.file_set else None


def _names_test(text: str, name: str) -> bool:
    patterns = (f"def {name}(", f"void {name}(", f"it('{name}'", f'it("{name}"', f"test('{name}'", f'test("{name}"')
    return any(pattern in text for pattern in patterns)


def run(ctx: Context) -> list[Finding]:
    found = []
    for path in ctx.living_docs:
        defined = {d.ident: d for d in ctx.definitions if d.path == path}
        active = [d for d in defined.values() if d.kind == "active"]
        rows = ctx.verification(path)
        if rows is None:
            for definition in active:
                found.append(Finding("K", path, definition.line, f"{definition.ident} has no verification table row"))
            continue
        counts: dict[str, int] = {}
        for row in rows:
            if row.ident is None:
                found.append(Finding("K", path, row.line, "verification row names no ID"))
                continue
            counts[row.ident] = counts.get(row.ident, 0) + 1
            if counts[row.ident] == 2:
                found.append(Finding("K", path, row.line, f"{row.ident} has more than one verification row"))
            if row.ident not in defined:
                found.append(Finding("K", path, row.line, f"{row.ident} is not defined in this doc"))
            found.extend(_row_findings(ctx, path, row))
        for definition in active:
            if definition.ident not in counts:
                found.append(Finding("K", path, definition.line, f"{definition.ident} has no verification table row"))
    return found


def _row_findings(ctx: Context, path: str, row) -> list[Finding]:
    found = []
    ident = row.ident
    if not row.source.strip():
        found.append(Finding("K", path, row.line, f"{ident}: Source is empty"))
    if row.status not in STATUSES:
        found.append(Finding("K", path, row.line, f"{ident}: unknown status '{row.status}'"))
    elif row.status == "tested":
        tokens = _test_tokens(row.verified_by)
        if not tokens:
            found.append(Finding("K", path, row.line, f"{ident}: tested row names no path::test"))
        for token in tokens:
            file_part, _, name = token.partition("::")
            resolved = _test_file(ctx, file_part)
            if resolved is None:
                found.append(Finding("K", path, row.line, f"{ident}: test file not found: {file_part}"))
            elif not _names_test(ctx.repo.text(resolved), name):
                found.append(Finding("K", path, row.line, f"{ident}: no test '{name}' in {resolved}"))
    elif row.status == "enforced":
        if not row.verified_by.strip():
            found.append(Finding("K", path, row.line, f"{ident}: enforced row with empty Verified by"))
    elif row.status == "divergent":
        if not citations(row.raw):
            found.append(Finding("K", path, row.line, f"{ident}: divergent row cites no decision"))
    elif row.status == "pending-decision":
        if not any(" — PENDING" in heading for heading in citations(row.raw)):
            found.append(Finding("K", path, row.line, f"{ident}: pending-decision row cites no PENDING heading"))
    return found


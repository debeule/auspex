"""Check M, rollout only: the migration matrix rows of a namespace, the decisions table, and the blocking list.

Rows are compared with the docs at document level: a path, a `requirements §N` or a `DECISIONS.md` heading taken
from the row's Source cell, never a line number. The living-docs cutover deletes this module with its tests.
"""

import re
from dataclasses import dataclass

from .. import markdown
from ..config import ConfigError
from . import DECISIONS_FILE, Context, Finding, citations

CHECKED_DISPOSITIONS = {"move", "ratify", "divergent", "retire"}
TRAP_CLASSES = {"trap", "rationale"}
TRAP_SLUGS = {"known-traps", "rationale"}

_SECTION = re.compile(r"§\d+(?:\.\d+)*")
_SCOPING_LABEL = re.compile(r"^[A-Z]{1,2}-?[A-Z]?\d+[a-z]?$")
_EXTENSION = re.compile(r"\.[A-Za-z0-9]+$")
_ANCHOR_ENTRY = re.compile(r"^(docs/[^#\s]+\.md)#(.+)$")
_FRAGMENT_ROW = re.compile(r"M-[A-Z]+-\d+")
_CHOICE = re.compile(r"^## .*CHOICE")


@dataclass(frozen=True)
class Reference:
    kind: str  # "decision", "section" or "path"
    value: str


NO_SECTION_FILE = Reference("error", "")


def contains_reference(text: str, ref: Reference) -> bool:
    if ref.kind == "decision":
        return ref.value in text
    if ref.kind == "section":
        return re.search(re.escape(ref.value) + r"(?!\.?\d)", text) is not None
    return re.search(r"(?<![\w./-])" + re.escape(ref.value) + r"(?![\w/-])", text) is not None


def _heading_path(title: str) -> str | None:
    for span in markdown.code_spans(title):
        if _EXTENSION.search(span):
            return span
    for token in title.split():
        token = token.strip("`(),:")
        if _EXTENSION.search(token) and re.search(r"[A-Za-z]", token.rsplit(".", 1)[0]):
            return token
    return None


def _section_file(headings, line: int) -> str | None:
    """The file named by the nearest preceding heading that names one."""
    for heading_line, _, title in reversed(headings):
        if heading_line < line:
            path = _heading_path(title)
            if path:
                return path
    return None


def source_reference(cell: str, section_file: str | None) -> Reference | None:
    """The row's document-level reference, None when the Source cell carries none (ID-existence check only)."""
    cited = citations(cell)
    if cited:
        return Reference("decision", cited[0])
    section = _SECTION.search(cell)
    if section:
        return Reference("section", section.group(0))
    stripped = cell.strip()
    if stripped.lstrip("`").startswith(":"):
        return Reference("path", section_file) if section_file else NO_SECTION_FILE
    if stripped.lower().startswith("same as"):
        return None
    tokens = [t.strip("`") for t in re.split(r"[\s;]+", stripped) if t.strip("`")]
    if tokens and _SCOPING_LABEL.match(tokens[0]):
        return None
    for token in tokens:
        token = token.split(":", 1)[0].strip("(),")
        if "/" in token or _EXTENSION.search(token):
            return Reference("path", token)
    return None


def _cell(cells: list[str], index: int | None) -> str:
    return cells[index].strip() if index is not None and index < len(cells) else ""


def _anchored_text(text: str, anchor: str) -> str | None:
    """A Known traps / Rationale H2 section by slug, or the one list item carrying `<a id=anchor>` inside one."""
    lines = text.splitlines()
    for title, start, end in markdown.h2_sections(text):
        if markdown.slugify(title) == anchor and anchor in TRAP_SLUGS:
            return "\n".join(lines[start - 1:end])
    marker = re.compile(rf"<a\s+(?:id|name)=\"{re.escape(anchor)}\"\s*>\s*</a>")
    for item in markdown.list_items(text):
        if marker.search(item.text):
            return item.text if markdown.slugify(item.section) in TRAP_SLUGS else None
    return None


def check_domain(ctx: Context, matrix: str, namespace: str) -> list[Finding]:
    text = ctx.repo.text(matrix)
    headings = markdown.headings(text)
    found = []
    for table in markdown.tables(text):
        cols = {name: table.column(name) for name in ("Row", "Source", "Class", "Disposition", "NS", "ID")}
        if None in (cols["Row"], cols["Disposition"], cols["NS"]):
            continue
        if cols["ID"] is None:
            raise ConfigError(f"{matrix}: the table at line {table.line} has no ID column")
        for line, cells in table.rows:
            if _cell(cells, cols["NS"]).strip("`") != namespace:
                continue
            disposition = _cell(cells, cols["Disposition"]).strip("`").lower()
            row = f"row {_cell(cells, cols['Row']).strip('`')}"
            entries = [e.strip("`") for e in re.split(r"[\s,]+", _cell(cells, cols["ID"])) if e.strip("`")]
            ref = source_reference(_cell(cells, cols["Source"]), _section_file(headings, line))

            def report(message: str) -> None:
                found.append(Finding("M", matrix, line, f"{row} {message}"))

            if disposition in CHECKED_DISPOSITIONS:
                if not entries:
                    report(f"({disposition}) has no ID")
                    continue
                if ref == NO_SECTION_FILE:
                    report("has a section-relative Source but no heading above it names a file")
                    ref = None
                klass = _cell(cells, cols["Class"]).strip("`").lower()
                for entry in entries:
                    message = _entry_problem(ctx, entry, namespace, disposition, klass, ref)
                    if message:
                        report(message)
            elif disposition == "link":
                if ref == NO_SECTION_FILE:
                    ref = None
                for entry in entries:
                    message = _link_problem(ctx, entry, ref)
                    if message:
                        report(message)
    return found


def _entry_problem(ctx: Context, entry: str, namespace: str, disposition: str, klass: str,
                   ref: Reference | None) -> str | None:
    if ctx.cfg.full_id_regex().fullmatch(entry):
        if ctx.cfg.namespace_of(entry) != namespace:
            return f"lists {entry}, which is not an ID of {namespace}"
        if disposition == "retire":
            definition = ctx.retired(entry)
            if definition is None:
                return f"retires {entry}, which has no retired definition"
            if ref and not contains_reference(definition.text, ref):
                return f"retired entry {entry} does not name the row's source {ref.value}"
            return None
        if ctx.active(entry) is None:
            return f"lists {entry}, which has no active definition"
        row = ctx.verification_row(entry)
        if ref and not contains_reference(row.source if row else "", ref):
            return f"verification Source of {entry} lacks the row's source {ref.value}"
        return None
    anchor_entry = _ANCHOR_ENTRY.match(entry)
    if anchor_entry and klass in TRAP_CLASSES:
        path, anchor = anchor_entry.groups()
        domain = ctx.cfg.domain_of_namespace(namespace)
        if domain is None or path not in ctx.cfg.domains[domain].owners:
            return f"anchor {entry} is not in an owner doc of {namespace}"
        if path not in ctx.repo.file_set:
            return f"anchor {entry} names a missing file"
        anchored = _anchored_text(ctx.repo.text(path), anchor)
        if anchored is None:
            return f"anchor {entry} is not a Known traps or Rationale section or an item inside one"
        if ref and not contains_reference(anchored, ref):
            return f"anchored text {entry} does not name the row's source {ref.value}"
        return None
    return f"lists {entry}, which is not an ID of {namespace}"


def _link_problem(ctx: Context, entry: str, ref: Reference | None) -> str | None:
    path, _, anchor = entry.partition("#")
    if path not in ctx.repo.file_set:
        return f"link target {path} not found"
    if anchor:
        if anchor not in ctx.anchors(path):
            return f"link target {entry}: no such anchor"
        return None
    if ref and not contains_reference(ctx.repo.text(path), ref):
        return f"link target {path} does not name the row's source {ref.value}"
    return None


def _heading_cell(cell: str) -> str:
    spans = markdown.code_spans(cell)
    text = spans[0] if spans else cell
    return text.strip().removeprefix("## ").strip()


def check_decisions(ctx: Context, matrix: str, namespace: str | None) -> list[Finding]:
    decisions = ctx.repo.text(DECISIONS_FILE) if DECISIONS_FILE in ctx.repo.file_set else ""
    choices: dict[str, int] = {}
    for line, content in markdown.unfenced_lines(decisions):
        if _CHOICE.match(content):
            choices.setdefault(content[3:].strip(), line)

    text = ctx.repo.text(matrix)
    all_tables = markdown.tables(text)
    table = next((t for t in all_tables if None not in (t.column("Heading"), t.column("Classification"),
                                                        t.column("IDs"))), None)
    if table is None:
        raise ConfigError(f"{matrix}: no table with Heading, Classification and IDs columns")
    fragment_ns: dict[str, str] = {}
    for other in all_tables:
        row_col, ns_col = other.column("Row"), other.column("NS")
        if row_col is not None and ns_col is not None:
            for _, cells in other.rows:
                fragment_ns[_cell(cells, row_col).strip("`")] = _cell(cells, ns_col).strip("`")

    heading_col, class_col = table.column("Heading"), table.column("Classification")
    ids_col, fragment_col = table.column("IDs"), table.column("Fragment rows")
    full = ctx.cfg.full_id_regex()
    found = []
    seen: dict[str, int] = {}
    for line, cells in table.rows:
        heading = _heading_cell(_cell(cells, heading_col))
        classification = _cell(cells, class_col).strip("`").lower()
        ids = full.findall(_cell(cells, ids_col))

        def report(message: str) -> None:
            found.append(Finding("M", matrix, line, message))

        if namespace is not None:
            if classification != "binding":
                continue
            selected = False
            for fragment in _FRAGMENT_ROW.findall(_cell(cells, fragment_col)):
                if fragment not in fragment_ns:
                    report(f"fragment row {fragment} of '{heading}' does not exist")
                elif fragment_ns[fragment] == namespace:
                    selected = True
            if selected:
                found.extend(_binding_problems(ctx, matrix, line, heading, ids))
            continue
        if heading not in choices:
            report(f"names no CHOICE heading in {DECISIONS_FILE}: {heading}")
            continue
        if heading in seen:
            report(f"second row for '{heading}' (first at line {seen[heading]})")
            continue
        seen[heading] = line
        if classification not in ("binding", "history"):
            report(f"classification '{classification}' is neither binding nor history")
        elif classification == "binding":
            found.extend(_binding_problems(ctx, matrix, line, heading, ids))
    if namespace is None:
        for heading, line in choices.items():
            if heading not in seen:
                found.append(Finding("M", DECISIONS_FILE, line, f"CHOICE heading has no decisions-table row: {heading}"))
    return found


def _binding_problems(ctx: Context, matrix: str, line: int, heading: str, ids: list[str]) -> list[Finding]:
    if not ids:
        return [Finding("M", matrix, line, f"binding '{heading}' lists no IDs")]
    found = []
    for ident in ids:
        if ctx.active(ident) is None:
            found.append(Finding("M", matrix, line, f"binding '{heading}' lists {ident}, which has no active definition"))
            continue
        row = ctx.verification_row(ident)
        if heading not in (row.source if row else ""):
            found.append(Finding("M", matrix, line, f"verification Source of {ident} does not cite '{heading}'"))
    return found


def check_pending(ctx: Context, blocking_list: str) -> list[Finding]:
    text = ctx.repo.text(blocking_list)
    table = next((t for t in markdown.tables(text)
                  if t.section == "Blocking decisions" and t.column("Heading suffix") is not None), None)
    if table is None:
        raise ConfigError(f"{blocking_list}: no 'Heading suffix' table under ## Blocking decisions")
    column = table.column("Heading suffix")
    suffixes = [s for s in (_cell(cells, column).strip("`").strip() for _, cells in table.rows) if s]
    found = []
    for path in ctx.living_docs:
        for row in ctx.verification(path) or []:
            if row.status != "pending-decision":
                continue
            pending = [h for h in citations(row.raw) if " — PENDING" in h]
            if not pending:
                found.append(Finding("M", path, row.line, f"{row.ident}: pending-decision row cites no PENDING heading"))
            for heading in pending:
                if any(heading.endswith(f" — {suffix}") for suffix in suffixes):
                    found.append(Finding("M", path, row.line, f"{row.ident} waits on blocking decision '{heading}'"))
    return found

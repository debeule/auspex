"""The small Markdown subset the checks read: fences, headings and GitHub slugs, links, inline code, tables, list items.

Every function ignores lines inside fenced code blocks (```` ``` ```` or `~~~`), fence lines included. Line numbers
are 1-based.
"""

import re
from dataclasses import dataclass, field

_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_HEADING = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*?))?[ \t]*$")
_CLOSING_HASHES = re.compile(r"[ \t]+#+$")
_CODE_SPAN = re.compile(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)")
_INLINE_LINK = re.compile(r"!?\[[^\]]*\]\(\s*(<[^>]*>|[^\s)]+)(?:\s+(?:\"[^\"]*\"|'[^']*'))?\s*\)")
_REFERENCE_DEF = re.compile(r"^ {0,3}\[[^\]]+\]:\s*(<[^>]*>|\S+)")
_EXPLICIT_ANCHOR = re.compile(r"<a\s+(?:id|name)=\"([^\"]+)\"\s*>\s*</a>")
_LIST_ITEM = re.compile(r"^(\s*)(?:[-*+]|\d+[.)])\s+(.*)$")
_TABLE_SEPARATOR = re.compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$")


def fence_mask(lines: list[str]) -> list[bool]:
    """True for every line inside a fenced block, including the opening and closing fence lines."""
    mask = []
    fence: str | None = None
    for line in lines:
        match = _FENCE.match(line)
        if fence is None:
            if match:
                fence = match.group(1)
                mask.append(True)
            else:
                mask.append(False)
        else:
            mask.append(True)
            stripped = line.strip()
            if match and stripped.startswith(fence[0] * len(fence)) and set(stripped) == {fence[0]}:
                fence = None
    return mask


def unfenced_lines(text: str) -> list[tuple[int, str]]:
    lines = text.splitlines()
    mask = fence_mask(lines)
    return [(number, line) for number, (line, fenced) in enumerate(zip(lines, mask), 1) if not fenced]


def code_spans(line: str) -> list[str]:
    """Inline code span contents, single or multiple backticks, with surrounding spaces trimmed."""
    return [match.group(2).strip() for match in _CODE_SPAN.finditer(line)]


def strip_code_spans(line: str) -> str:
    return _CODE_SPAN.sub(lambda m: " " * len(m.group(0)), line)


def headings(text: str) -> list[tuple[int, int, str]]:
    """(line, level, text) for every ATX heading outside fences."""
    found = []
    for number, line in unfenced_lines(text):
        match = _HEADING.match(line)
        if match:
            title = _CLOSING_HASHES.sub("", match.group(2) or "").strip()
            found.append((number, len(match.group(1)), title))
    return found


def slugify(title: str) -> str:
    """GitHub's heading slug, before duplicate numbering."""
    title = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", title)
    title = re.sub(r"<[^>]+>", "", title)
    return re.sub(r"[^\w\- ]", "", title.lower()).replace(" ", "-")


def heading_slugs(text: str) -> list[str]:
    seen: dict[str, int] = {}
    slugs = []
    for _, _, title in headings(text):
        slug = slugify(title)
        count = seen.get(slug, 0)
        slugs.append(slug if count == 0 else f"{slug}-{count}")
        seen[slug] = count + 1
    return slugs


def explicit_anchors(text: str) -> list[tuple[int, str]]:
    return [(number, m.group(1)) for number, line in unfenced_lines(text) for m in _EXPLICIT_ANCHOR.finditer(line)]


def anchors(text: str) -> set[str]:
    """Every fragment a link into this file may name: heading slugs and explicit `<a id>`/`<a name>` anchors."""
    return set(heading_slugs(text)) | {anchor for _, anchor in explicit_anchors(text)}


def links(text: str) -> list[tuple[int, str]]:
    """(line, target) for inline links and reference definitions outside fences and inline code."""
    found = []
    for number, line in unfenced_lines(text):
        plain = strip_code_spans(line)
        for match in _INLINE_LINK.finditer(plain):
            found.append((number, match.group(1).strip("<>")))
        match = _REFERENCE_DEF.match(plain)
        if match:
            found.append((number, match.group(1).strip("<>")))
    return found


def split_cells(line: str) -> list[str]:
    """Split a table row on `|` outside inline code, honouring `\\|`."""
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|") and not stripped.endswith("\\|"):
        stripped = stripped[:-1]
    cells, current, index = [], [], 0
    while index < len(stripped):
        char = stripped[index]
        if char == "\\" and index + 1 < len(stripped) and stripped[index + 1] == "|":
            current.append("|")
            index += 2
            continue
        if char == "`":
            run = len(stripped[index:]) - len(stripped[index:].lstrip("`"))
            closing = re.compile(r"(?<!`)" + "`" * run + r"(?!`)")
            end = closing.search(stripped, index + run)
            if end:
                current.append(stripped[index:end.end()])
                index = end.end()
                continue
            current.append(stripped[index:index + run])
            index += run
            continue
        if char == "|":
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(char)
        index += 1
    cells.append("".join(current).strip())
    return cells


@dataclass
class Table:
    line: int
    headers: list[str]
    rows: list[tuple[int, list[str]]] = field(default_factory=list)
    section: str = ""

    def column(self, name: str) -> int | None:
        """Index of the first header cell that starts with `name`."""
        for index, header in enumerate(self.headers):
            if header.startswith(name):
                return index
        return None


def tables(text: str) -> list[Table]:
    """Pipe tables outside fences; `section` is the H2 the table sits under."""
    lines = text.splitlines()
    mask = fence_mask(lines)
    found: list[Table] = []
    section = ""
    index = 0
    while index < len(lines):
        line = lines[index]
        if not mask[index]:
            heading = _HEADING.match(line)
            if heading and len(heading.group(1)) == 2:
                section = _CLOSING_HASHES.sub("", heading.group(2) or "").strip()
            if (
                "|" in line
                and index + 1 < len(lines)
                and not mask[index + 1]
                and _TABLE_SEPARATOR.match(lines[index + 1])
                and "-" in lines[index + 1]
            ):
                table = Table(index + 1, split_cells(line), section=section)
                index += 2
                while index < len(lines) and not mask[index] and "|" in lines[index] and lines[index].strip():
                    table.rows.append((index + 1, split_cells(lines[index])))
                    index += 1
                found.append(table)
                continue
        index += 1
    return found


@dataclass
class ListItem:
    line: int
    text: str
    section: str


def list_items(text: str) -> list[ListItem]:
    """List items outside fences, each with its continuation lines and the H2 it sits under."""
    lines = text.splitlines()
    mask = fence_mask(lines)
    items: list[ListItem] = []
    section = ""
    index = 0
    while index < len(lines):
        line = lines[index]
        if mask[index]:
            index += 1
            continue
        heading = _HEADING.match(line)
        if heading:
            if len(heading.group(1)) == 2:
                section = _CLOSING_HASHES.sub("", heading.group(2) or "").strip()
            index += 1
            continue
        match = _LIST_ITEM.match(line)
        if not match:
            index += 1
            continue
        indent = len(match.group(1))
        parts = [match.group(2)]
        start = index
        index += 1
        while index < len(lines) and not mask[index] and lines[index].strip():
            nxt = lines[index]
            if _HEADING.match(nxt):
                break
            nested = _LIST_ITEM.match(nxt)
            if nested and len(nested.group(1)) <= indent:
                break
            parts.append(nxt.strip())
            index += 1
        items.append(ListItem(start + 1, "\n".join(parts), section))
    return items


def h2_sections(text: str) -> list[tuple[str, int, int]]:
    """(title, first line, last line) of every H2 section; the section runs to the next H1 or H2."""
    found = headings(text)
    total = len(text.splitlines())
    sections = []
    for position, (line, level, title) in enumerate(found):
        if level != 2:
            continue
        end = total
        for later_line, later_level, _ in found[position + 1:]:
            if later_level <= 2:
                end = later_line - 1
                break
        sections.append((title, line, end))
    return sections

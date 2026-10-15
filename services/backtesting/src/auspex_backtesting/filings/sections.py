"""Item 1A (Risk Factors) cut out of a 10-K or 10-Q primary document.

Headings are recognised only at the start of a line of the document's text, so a cross
reference inside a sentence ("see Part I, Item 1A") never starts a section. The table of
contents lists the same headings, but its Item 1A line is followed at once by the next item's,
so the longest span from an Item 1A heading to the following end heading is the section. A
10-Q's Item 1A is in Part II and ends at the next Part II item; Part I has no Item 1A.
"""

import html
import re
from dataclasses import dataclass
from typing import Literal

CutStatus = Literal["cut", "section_missing", "no_change_statement"]

_HIDDEN = re.compile(
    r"<(script|style|ix:header)\b.*?</\1\s*>", re.IGNORECASE | re.DOTALL
)
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
# Cells of one table row stay on one line; these tags end one.
_LINE_BREAK = re.compile(
    r"<(?:br|/?p|/?div|/?tr|/?li|/?h[1-6]|/?table|/?ul|/?ol|/?center)\b[^>]*>", re.IGNORECASE
)
_CELL = re.compile(r"</t[dh]\s*>", re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")
_HTML = re.compile(r"<(?:html|body|div|p|table)\b", re.IGNORECASE)
_ANY_SPACE = re.compile(r"\s+")
_SPACE = re.compile(r"[ \t\r\f\v\u00a0\u2002-\u200b]+")
# Page numbers and running headers between pages.
_PAGE_FURNITURE = re.compile(r"(?:\d{1,3}|table of contents)", re.IGNORECASE)

_START = re.compile(r"^item\s*1a\b", re.IGNORECASE | re.MULTILINE)
_END = {
    "10-K": re.compile(r"^item\s*(?:1b|1c|2)\b", re.IGNORECASE | re.MULTILINE),
    "10-Q": re.compile(r"^item\s*[2-6]\b", re.IGNORECASE | re.MULTILINE),
}

# A section this short that says nothing changed, or that the item does not apply, is a
# statement rather than risk factors.
_STATEMENT_MAX_WORDS = 150
_NO_CHANGE = re.compile(r"no\s+material\s+changes?", re.IGNORECASE)
_CHANGES_FOLLOW = re.compile(
    r"\bexcept\b|\bset\s+forth\s+below\b|\bas\s+follows\b|\bthe\s+following\b|\bsupplement",
    re.IGNORECASE,
)
_NOT_PROVIDED = re.compile(r"not\s+(?:required|applicable)", re.IGNORECASE)


@dataclass(frozen=True)
class SectionCut:
    status: CutStatus
    reason: str
    text: str


def form_family(form: str) -> str | None:
    """`10-K` for annual reports (10-K, 10-K405, 10-KT), `10-Q` for quarterly ones, None for
    anything else, amendments included."""
    if form in ("10-K", "10-K405", "10-KT"):
        return "10-K"
    if form == "10-Q":
        return "10-Q"
    return None


def filing_to_text(document: str) -> str:
    """Plain text of an HTML or plain-text filing document: one line per block (per line in a
    plain-text document), whitespace collapsed, entities decoded, page numbers dropped."""
    text = _COMMENT.sub(" ", _HIDDEN.sub(" ", document))
    if _HTML.search(text):
        # Line breaks in HTML source are only wrapping; blocks end lines.
        text = _ANY_SPACE.sub(" ", text)
    text = _CELL.sub(" ", _LINE_BREAK.sub("\n", text))
    text = html.unescape(_TAG.sub("", text))
    lines = (_SPACE.sub(" ", line).strip() for line in text.splitlines())
    return "\n".join(line for line in lines if line and not _PAGE_FURNITURE.fullmatch(line))


def cut_item_1a(text: str, form: str) -> SectionCut:
    """Item 1A of `text` (from `filing_to_text`), from its heading up to the next item's."""
    family = form_family(form)
    if family is None:
        return SectionCut("section_missing", "unsupported_form", "")
    starts = [m.start() for m in _START.finditer(text)]
    if not starts:
        return SectionCut("section_missing", "no_item_1a_heading", "")
    ends = [m.start() for m in _END[family].finditer(text)]
    spans = [
        (start, end)
        for start in starts
        if (end := next((e for e in ends if e > start), None)) is not None
    ]
    if not spans:
        return SectionCut("section_missing", "no_end_heading", "")
    start, end = max(spans, key=lambda s: s[1] - s[0])
    section = text[start:end].strip()
    body = section.split("\n", 1)[1] if "\n" in section else ""
    if len(body.split()) <= _STATEMENT_MAX_WORDS:
        if _NO_CHANGE.search(body) and not _CHANGES_FOLLOW.search(body):
            return SectionCut("no_change_statement", "", section)
        if _NOT_PROVIDED.search(body) or not body.strip():
            return SectionCut("section_missing", "not_provided", "")
    return SectionCut("cut", "", section)

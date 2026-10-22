"""What the checks share: the finding record, and a context holding the repository, the configuration and the
parsed definitions, decision headings and verification tables.
"""

import posixpath
import re
from dataclasses import dataclass
from functools import cached_property

from .. import globs, markdown
from ..config import Config
from ..repo import Repo

DECISIONS_FILE = "DECISIONS.md"
PR_BODY = "pr-body"
VERIFICATION_HEADERS = ["ID", "Source", "Verified by", "Status"]
RETIRED_SECTION = "Retired requirements"

_CITATION = re.compile(r"(## )?\d{4}-\d{2}-\d{2} — .+")
_CITATION_TYPES = (" — BLOCKED", " — FLAG", " — CHOICE", " — VERIFIED", " — PENDING")
_FIRST_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_STATUS_WORD = re.compile(r"\s*`?([\w-]+)")


@dataclass(frozen=True, order=True)
class Finding:
    check: str
    path: str
    line: int
    message: str
    notice: bool = False

    def render(self) -> str:
        kind = f"{self.check} notice" if self.notice else self.check
        return f"{kind} {self.path}:{self.line} {self.message}"


@dataclass(frozen=True)
class Definition:
    ident: str
    path: str
    line: int
    kind: str  # "active" or "retired"
    text: str


@dataclass
class VerificationRow:
    line: int
    ident: str | None
    source: str
    verified_by: str
    status: str
    raw: str


def citations(text: str) -> list[str]:
    """Decision headings cited in inline code in `text`, without a leading `## `; templates are skipped."""
    found = []
    for span in markdown.code_spans(text):
        if "…" in span or "<" in span:
            continue
        if _CITATION.fullmatch(span) and any(kind in span for kind in _CITATION_TYPES):
            found.append(span.removeprefix("## ").strip())
    return found


def status_word(cell: str) -> str:
    match = _STATUS_WORD.match(cell)
    return match.group(1) if match else ""


def spec_status(text: str) -> tuple[int, str] | None:
    """(line, value) of a spec's `**Status:**` line, the value being its first word without backticks."""
    for number, line in markdown.unfenced_lines(text):
        if line.startswith("**Status:**"):
            words = line[len("**Status:**"):].split()
            value = words[0].strip("`").rstrip(".,;") if words else ""
            return number, value
    return None


def parse_definitions(cfg: Config, path: str, text: str) -> list[Definition]:
    """Active (`<a id="X"></a>**X**` list items) and retired (bold ID under `## Retired requirements`) definitions."""
    full = cfg.full_id_regex()
    active = re.compile(rf'^<a id="({full.pattern})"></a>\*\*\1\*\*')
    found = []
    for item in markdown.list_items(text):
        if item.section == RETIRED_SECTION:
            bold = _FIRST_BOLD.search(item.text)
            if bold and full.fullmatch(bold.group(1)):
                found.append(Definition(bold.group(1), path, item.line, "retired", item.text))
            continue
        match = active.match(item.text)
        if match:
            found.append(Definition(match.group(1), path, item.line, "active", item.text))
    return found


class Context:
    def __init__(self, cfg: Config, repo: Repo, config_label: str, base: str | None = None,
                 pr_body: str | None = None):
        self.cfg = cfg
        self.repo = repo
        self.config_label = config_label
        self.base = base
        self.pr_body = pr_body
        self._anchors: dict[str, set[str]] = {}

    @cached_property
    def living_docs(self) -> list[str]:
        return [path for path in self.repo.files if self.cfg.is_living_doc(path)]

    @cached_property
    def definitions(self) -> list[Definition]:
        found = []
        for path in self.living_docs:
            found.extend(parse_definitions(self.cfg, path, self.repo.text(path)))
        return found

    @cached_property
    def definitions_by_id(self) -> dict[str, list[Definition]]:
        by_id: dict[str, list[Definition]] = {}
        for definition in self.definitions:
            by_id.setdefault(definition.ident, []).append(definition)
        return by_id

    def active(self, ident: str) -> Definition | None:
        return next((d for d in self.definitions_by_id.get(ident, []) if d.kind == "active"), None)

    def retired(self, ident: str) -> Definition | None:
        return next((d for d in self.definitions_by_id.get(ident, []) if d.kind == "retired"), None)

    @cached_property
    def decision_headings(self) -> dict[str, int]:
        """Heading text → line for every heading of `DECISIONS.md` outside fences."""
        text = self.repo.text(DECISIONS_FILE) if DECISIONS_FILE in self.repo.file_set else ""
        found: dict[str, int] = {}
        for number, _, title in markdown.headings(text):
            found.setdefault(title, number)
        return found

    def anchors(self, path: str) -> set[str]:
        if path not in self._anchors:
            self._anchors[path] = markdown.anchors(self.repo.text(path))
        return self._anchors[path]

    def verification(self, path: str) -> list[VerificationRow] | None:
        """Rows of the living doc's verification table, or None when it has none."""
        for table in markdown.tables(self.repo.text(path)):
            if table.section == "Verification" and table.headers == VERIFICATION_HEADERS:
                rows = []
                full = self.cfg.full_id_regex()
                for line, cells in table.rows:
                    cells = cells + [""] * (4 - len(cells))
                    match = full.search(cells[0])
                    rows.append(
                        VerificationRow(line, match.group(0) if match else None, cells[1], cells[2],
                                        status_word(cells[3]), " | ".join(cells))
                    )
                return rows
        return None

    def verification_row(self, ident: str) -> VerificationRow | None:
        definition = self.active(ident)
        if definition is None:
            return None
        for row in self.verification(definition.path) or []:
            if row.ident == ident:
                return row
        return None

    @cached_property
    def _planned_missing_owners(self) -> set[str]:
        missing = set()
        for name in self.cfg.planned:
            for owner in self.cfg.domains[name].owners:
                if not globs.is_glob(owner) and owner not in self.repo.file_set:
                    missing.add(owner)
        return missing

    @cached_property
    def _planned_missing_dirs(self) -> set[str]:
        """Missing directories whose only owner docs belong to planned domains."""
        planned_owners = {o for name in self.cfg.planned for o in self.cfg.domains[name].owners}
        all_owners = {o for d in self.cfg.domains.values() for o in d.owners if not globs.is_glob(o)}
        found = set()
        for owner in self._planned_missing_owners:
            parts = owner.split("/")[:-1]
            for end in range(1, len(parts) + 1):
                directory = "/".join(parts[:end])
                if directory in self.repo.dirs or directory in self.repo.file_set:
                    continue
                inside = [o for o in all_owners if o.startswith(directory + "/")]
                if all(o in planned_owners for o in inside):
                    found.add(directory)
        return found

    def planned_target(self, path: str) -> bool:
        """True when `path` is a missing owner doc of a planned domain, or lies in a missing directory only
        planned owner docs occupy; references to it are notices rather than findings."""
        path = path.rstrip("/")
        if path in self._planned_missing_owners:
            return True
        return any(path == d or path.startswith(d + "/") for d in self._planned_missing_dirs)

    def planned_namespace(self, ident: str) -> bool:
        return self.cfg.namespace_of(ident) in self.cfg.planned_namespaces


def resolve_link(source: str, target: str) -> str | None:
    """Repo-relative path a link in `source` points at; None when it leaves the repository."""
    if target.startswith("/"):
        joined = target.lstrip("/")
    else:
        joined = posixpath.join(posixpath.dirname(source), target)
    resolved = posixpath.normpath(joined) if joined else "."
    if resolved == ".." or resolved.startswith("../"):
        return None
    return resolved

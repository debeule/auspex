"""Check E: living docs carry the required H2s and a reviewed-against SHA on HEAD's history; active and hold
specs carry the required header fields, a known status, `**Blocked by:**` when blocked, and the required H2s.
"""

import re

from .. import markdown
from . import Context, Finding, spec_status

_REVIEW = re.compile(r"Last reviewed against: develop @ `?([0-9a-fA-F]{7,40})\b`?")


def _h2_titles(text: str) -> set[str]:
    return {title for _, level, title in markdown.headings(text) if level == 2}


def run(ctx: Context) -> list[Finding]:
    found = []
    living = ctx.cfg.section("living_docs")
    for path in ctx.living_docs:
        text = ctx.repo.text(path)
        titles = _h2_titles(text)
        for section in living["required_sections"]:
            if section not in titles:
                found.append(Finding("E", path, 0, f"missing section ## {section}"))
        review = [(n, l) for n, l in markdown.unfenced_lines(text) if "Last reviewed against:" in l]
        match = _REVIEW.search(review[0][1]) if review else None
        if not match:
            found.append(Finding("E", path, review[0][0] if review else 0,
                                 "missing 'Last reviewed against: develop @ <sha>' line"))
            continue
        sha = ctx.repo.resolve_commit(match.group(1))
        if sha is None:
            found.append(Finding("E", path, review[0][0], f"unknown reviewed-against commit {match.group(1)}"))
        elif not ctx.repo.is_ancestor(sha):
            found.append(Finding("E", path, review[0][0],
                                 f"reviewed-against commit {match.group(1)} is not an ancestor of HEAD"))

    specs = ctx.cfg.section("specs")
    for path in ctx.repo.files:
        if not ctx.cfg.is_spec(path):
            continue
        text = ctx.repo.text(path)
        lines = [line for _, line in markdown.unfenced_lines(text)]
        for field in specs["required_fields"]:
            if not any(line.startswith(f"**{field}:**") for line in lines):
                found.append(Finding("E", path, 0, f"missing **{field}:** field"))
        status = spec_status(text)
        if status is not None:
            line, value = status
            if value not in specs["statuses"]:
                found.append(Finding("E", path, line, f"unknown status '{value}'"))
            if value == "blocked" and not any(l.startswith("**Blocked by:**") for l in lines):
                found.append(Finding("E", path, line, "blocked spec without a **Blocked by:** line"))
        titles = _h2_titles(text)
        for section in specs["required_sections"]:
            if section not in titles:
                found.append(Finding("E", path, 0, f"missing section ## {section}"))
    return found

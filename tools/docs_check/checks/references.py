"""Check D: ID references and invariant aliases resolve, retired IDs stay out of specs, agent files and READMEs,
no placeholders, decision citations name real `DECISIONS.md` headings, and no register numbers.
"""

import re

from .. import globs, markdown
from . import PR_BODY, Context, Finding, citations

_REGISTER = re.compile(r"\bD-\d\d\b")
_AGENT_OR_README = ("**/AGENTS.md", "**/CLAUDE.md", "**/README.md")


def run(ctx: Context) -> list[Finding]:
    found = []
    for path in ctx.repo.files:
        if ctx.cfg.in_scope("D", path):
            found.extend(_scan(ctx, path, ctx.repo.text(path), body=False))
    if ctx.pr_body is not None:
        found.extend(_scan(ctx, PR_BODY, ctx.pr_body, body=True))
    return found


def _retired_forbidden(ctx: Context, path: str) -> bool:
    if path.startswith("docs/"):
        return False
    specs_include = ctx.cfg.section("specs", "include")
    return globs.match_any(specs_include, path) or globs.match_any(_AGENT_OR_README, path)


def _references(ctx: Context, content: str) -> list[str]:
    refs = [m.group(1) for m in ctx.cfg.reference_regex().finditer(content)]
    for match in ctx.cfg.alias_regex().finditer(content):
        for group in (1, 3):
            if match.group(group):
                refs.append(f"{ctx.cfg.invariant}-{int(match.group(group))}")
    return list(dict.fromkeys(refs))


def _scan(ctx: Context, path: str, text: str, body: bool) -> list[Finding]:
    forbid_retired = not body and _retired_forbidden(ctx, path)
    placeholder = ctx.cfg.placeholder_regex()
    found = []
    for line, content in markdown.unfenced_lines(text):
        for ident in _references(ctx, content):
            definitions = ctx.definitions_by_id.get(ident)
            if not definitions:
                if ctx.planned_namespace(ident):
                    found.append(Finding("D", path, line, f"{ident} has no definition yet (planned domain)", True))
                else:
                    found.append(Finding("D", path, line, f"{ident} is not defined"))
            elif forbid_retired and all(d.kind == "retired" for d in definitions):
                found.append(Finding("D", path, line, f"{ident} is retired; cite its replacement"))
        for match in placeholder.finditer(content):
            ident = match.group(1)
            notice = ctx.cfg.namespace_of(ident) in ctx.cfg.planned_namespaces
            found.append(Finding("D", path, line, f"placeholder {ident}", notice))
        for heading in citations(content):
            if heading not in ctx.decision_headings:
                found.append(Finding("D", path, line, f"no DECISIONS.md heading: {heading}"))
        if not body:
            for match in _REGISTER.finditer(content):
                found.append(Finding("D", path, line, f"register number {match.group(0)}; cite the DECISIONS.md heading"))
    return found

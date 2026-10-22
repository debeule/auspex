"""Checks F (every path owned, owner docs present unless their domain is planned) and G (every domain a PR
touches changes an owner doc or carries a `Docs unchanged:` line), and the `--owners` listing.
"""

import re

from .. import globs, markdown
from . import DECISIONS_FILE, PR_BODY, Context, Finding

DECISIONS_DOMAIN = "decisions"
_DISPOSITION = re.compile(r"^\s*(?:[-*+]\s+)?Docs unchanged:(.*)$")
_DOMAIN_AND_REASON = re.compile(r"^`?([\w.-]+)`?\s*(?:—|--)\s*(.*)$")
_CHOICE_HEADING = re.compile(r"^## .*CHOICE")


def _line_of(text: str, needle: str) -> int:
    for number, line in enumerate(text.splitlines(), 1):
        if needle in line:
            return number
    return 0


def run_f(ctx: Context) -> list[Finding]:
    found = []
    for path in ctx.repo.files:
        if ctx.cfg.path_domains(path) is None:
            found.append(Finding("F", path, 0, "unowned: no ownership rule or unowned_ok glob matches"))
    config_text = ctx.repo.text(ctx.config_label) if ctx.config_label in ctx.repo.file_set else ""
    for name, domain in ctx.cfg.domains.items():
        owners = [owner for owner in domain.owners if not globs.is_glob(owner)]
        missing = [owner for owner in owners if owner not in ctx.repo.file_set]
        if name in ctx.cfg.planned:
            if owners and not missing:
                found.append(Finding("F", ctx.config_label, _line_of(config_text, "planned_domains"),
                                     f"domain '{name}' has all its owner docs; remove it from planned_domains"))
        else:
            for owner in missing:
                found.append(Finding("F", owner, 0, f"owner doc of domain '{name}' is missing"))
    return found


def owners_lines(ctx: Context, paths: list[str]) -> tuple[list[str], bool]:
    """`--owners` output lines, and whether any path is unowned."""
    lines, unowned = [], False
    for path in paths:
        if ctx.cfg.is_unowned_ok(path):
            lines.append(f"{path}\tunowned-ok")
            continue
        domains = ctx.cfg.rule_domains(path)
        if domains is None:
            lines.append(f"{path}\tUNOWNED")
            unowned = True
            continue
        owners: list[str] = []
        for name in domains:
            for owner in ctx.cfg.domains[name].owners:
                if owner not in owners:
                    owners.append(owner)
        lines.append(f"{path}\t{','.join(domains)}\t{' '.join(owners)}")
    return lines, unowned


def _adds_choice_heading(ctx: Context, path: str) -> bool:
    text = ctx.repo.show("HEAD", path) or ""
    lines = text.splitlines()
    mask = markdown.fence_mask(lines)
    for number in ctx.repo.added_line_numbers(ctx.base, path):
        if 0 < number <= len(lines) and not mask[number - 1] and _CHOICE_HEADING.match(lines[number - 1]):
            return True
    return False


def _is_owner_doc(ctx: Context, domain: str, path: str) -> bool:
    for owner in ctx.cfg.domains[domain].owners:
        if globs.is_glob(owner):
            if globs.match(owner, path) and ctx.cfg.is_living_doc(path):
                return True
        elif owner == path:
            return True
    return False


def run_g(ctx: Context) -> list[Finding]:
    changed: list[str] = []
    for _, paths in ctx.repo.diff_name_status(ctx.base):
        for path in paths:
            if path not in changed:
                changed.append(path)
    first_path: dict[str, str] = {}
    for path in sorted(changed):
        domains = list(ctx.cfg.path_domains(path) or [])
        if path == DECISIONS_FILE and DECISIONS_DOMAIN in domains and not _adds_choice_heading(ctx, path):
            domains.remove(DECISIONS_DOMAIN)
        for name in domains:
            first_path.setdefault(name, path)

    found = []
    declared = set()
    for number, line in enumerate((ctx.pr_body or "").splitlines(), 1):
        match = _DISPOSITION.match(line)
        if not match:
            continue
        rest = match.group(1).strip()
        parsed = _DOMAIN_AND_REASON.match(rest)
        if parsed:
            domain, reason = parsed.group(1), parsed.group(2).strip()
        else:
            domain, reason = (rest.split()[0].strip("`") if rest else ""), ""
        if domain not in ctx.cfg.domains:
            found.append(Finding("G", PR_BODY, number, f"Docs unchanged names unknown domain '{domain}'"))
        elif not reason or reason == "<reason>":
            found.append(Finding("G", PR_BODY, number, f"Docs unchanged: {domain} needs a real reason"))
        else:
            declared.add(domain)

    for name, path in sorted(first_path.items()):
        if name in declared or any(_is_owner_doc(ctx, name, p) for p in changed):
            continue
        found.append(Finding("G", path, 0, f"domain '{name}' changed without an owner doc change or a "
                                           f"'Docs unchanged: {name} — <reason>' line"))
    return found

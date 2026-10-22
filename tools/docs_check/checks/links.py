"""Check A: every relative link target exists, every fragment names an anchor, every frozen path exists."""

import re
from urllib.parse import unquote

from .. import markdown
from . import Context, Finding, resolve_link

_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+-]*:")


def run(ctx: Context) -> list[Finding]:
    found = []
    for path in ctx.repo.files:
        if not ctx.cfg.in_scope("A", path):
            continue
        for line, target in markdown.links(ctx.repo.text(path)):
            if _SCHEME.match(target) or target.startswith("//"):
                continue
            target_path, _, fragment = target.partition("#")
            target_path = unquote(target_path.split("?", 1)[0])
            resolved = resolve_link(path, target_path) if target_path else path
            if resolved is None:
                found.append(Finding("A", path, line, f"link leaves the repository: {target}"))
                continue
            if resolved != "." and not ctx.repo.exists(resolved):
                if ctx.planned_target(resolved):
                    found.append(Finding("A", path, line, f"link to {resolved}, where a planned domain's owner docs go", notice=True))
                else:
                    found.append(Finding("A", path, line, f"broken link: {target}"))
                continue
            fragment = unquote(fragment)
            if fragment and (resolved not in ctx.repo.file_set or fragment not in ctx.anchors(resolved)):
                found.append(Finding("A", path, line, f"no anchor #{fragment} in {resolved}"))
    for frozen in ctx.cfg.frozen_paths:
        if frozen not in ctx.repo.file_set:
            found.append(Finding("A", frozen, 0, "frozen path is missing"))
    return found

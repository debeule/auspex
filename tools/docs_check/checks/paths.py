"""Check B: backticked repository paths in living docs and agent files exist."""

import re

from .. import markdown
from . import Context, Finding

_SKIP_CHARS = set("*<>{…$")
_LINE_SUFFIX = re.compile(r":\d+(-\d+)?$")


def run(ctx: Context) -> list[Finding]:
    prefixes = ctx.cfg.section("checks", "B", "prefixes")
    found = []
    for path in ctx.repo.files:
        if not ctx.cfg.in_scope("B", path):
            continue
        for line, content in markdown.unfenced_lines(ctx.repo.text(path)):
            for span in markdown.code_spans(content):
                if not span or any(c.isspace() for c in span) or any(c in _SKIP_CHARS for c in span):
                    continue
                token = span.split("#", 1)[0].split("::", 1)[0]
                token = _LINE_SUFFIX.sub("", token)
                candidate = token.rstrip("/")
                if not candidate or not any(token.startswith(prefix) for prefix in prefixes):
                    # A bare root file name resolves only when it is in the file set, so it never fails.
                    continue
                if ctx.repo.exists(candidate):
                    continue
                if ctx.planned_target(candidate):
                    found.append(Finding("B", path, line, f"path {candidate} is where a planned domain's owner docs go", notice=True))
                else:
                    found.append(Finding("B", path, line, f"path not found: {candidate}"))
    return found

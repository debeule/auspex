"""Check H: the legacy requirements file holds only an optional H1, one `Not authoritative` banner paragraph and
one table. Everything else is a single finding, so the legacy text cannot bury every other finding.
"""

from . import Context, Finding


def _blocks(lines: list[str]) -> list[tuple[int, list[str]]]:
    blocks, current, start = [], [], 0
    for number, line in enumerate(lines, 1):
        if line.strip():
            if not current:
                start = number
            current.append(line)
        elif current:
            blocks.append((start, current))
            current = []
    if current:
        blocks.append((start, current))
    return blocks


def _kind(block: list[str]) -> str | None:
    if len(block) == 1 and block[0].startswith("# "):
        return "h1"
    if all(line.lstrip().startswith("|") for line in block):
        return "table"
    if "Not authoritative" in " ".join(block) and not any(line.lstrip()[:1] in "#|`~" for line in block):
        return "banner"
    return None


def run(ctx: Context) -> list[Finding]:
    path = ctx.cfg.section("checks", "H", "file")
    stage = 0  # 0: optional H1 next, 1: banner next, 2: table next, 3: nothing more
    offending: list[int] = []
    for start, block in _blocks(ctx.repo.text(path).splitlines()):
        kind = _kind(block)
        if stage == 0 and kind == "h1":
            stage = 1
        elif stage <= 1 and kind == "banner":
            stage = 2
        elif stage == 2 and kind == "table":
            stage = 3
        else:
            offending.extend(range(start, start + len(block)))
    if offending:
        return [Finding("H", path, offending[0], f"{len(offending)} offending lines: only an optional H1, one "
                                                 "'Not authoritative' banner paragraph and one table belong here")]
    if stage < 3:
        return [Finding("H", path, 1, "missing the 'Not authoritative' banner paragraph or the index table")]
    return []

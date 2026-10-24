"""Checks C (each ID defined once, invariants never retired), C2 (no ID defined at the base disappears) and
the `--next` allocator, which counts retired entries so a retired number is never handed out again.
"""

from . import Context, Finding, parse_definitions


def run_c(ctx: Context) -> list[Finding]:
    found = []
    for ident, definitions in ctx.definitions_by_id.items():
        first = definitions[0]
        for duplicate in definitions[1:]:
            found.append(
                Finding("C", duplicate.path, duplicate.line,
                        f"{ident} defined {len(definitions)} times (first at {first.path}:{first.line})")
            )
        if ctx.cfg.namespace_of(ident) == ctx.cfg.invariant:
            for definition in definitions:
                if definition.kind == "retired":
                    found.append(Finding("C", definition.path, definition.line,
                                         f"{ident} is an invariant and cannot be retired"))
    return found


def run_c2(ctx: Context) -> list[Finding]:
    current = set(ctx.definitions_by_id)
    reported = set()
    found = []
    for path in ctx.repo.ls_tree(ctx.base):
        if not ctx.cfg.is_living_doc(path):
            continue
        text = ctx.repo.show(ctx.base, path) or ""
        for definition in parse_definitions(ctx.cfg, path, text):
            if definition.ident not in current and definition.ident not in reported:
                reported.add(definition.ident)
                found.append(Finding("C2", path, definition.line,
                                     f"{definition.ident} was defined at {ctx.base[:12]} and is no longer defined"))
    return found


def next_id(ctx: Context, namespace: str) -> str:
    highest = 0
    for ident in ctx.definitions_by_id:
        if ctx.cfg.namespace_of(ident) == namespace:
            highest = max(highest, int(ident.split("-", 1)[1]))
    if namespace == ctx.cfg.invariant:
        return f"{namespace}-{highest + 1}"
    return f"{namespace}-{highest + 1:03d}"

"""Command line for the docs checker.

Exit codes: 0 no findings, 1 one or more findings, 2 a configuration or usage error (one `docs_check: error:`
line on stderr, nothing on stdout). Findings go to stdout as `CHECK path:line message`, sorted; notices and the
summary go to stderr and never change the exit code.
"""

import argparse
import os
import sys
from pathlib import Path

from . import globs
from .checks import Context, Finding, agents, ids, index, legacy, links, matrix, ownership, paths, references
from .checks import structure, verification
from .config import ConfigError, load
from .repo import GitError, Repo, is_top_of_work_tree

ORDER = ["A", "B", "C", "C2", "D", "E", "F", "G", "H", "J", "K", "L"]
DEFAULT = ["A", "B", "C", "D", "E", "F", "H", "J", "K", "L"]
RUNNERS = {
    "A": links.run,
    "B": paths.run,
    "C": ids.run_c,
    "C2": ids.run_c2,
    "D": references.run,
    "E": structure.run,
    "F": ownership.run_f,
    "G": ownership.run_g,
    "H": legacy.run,
    "J": index.run,
    "K": verification.run,
    "L": agents.run,
}


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ConfigError(message)


def _parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="docs_check", description="Check the living docs, specs and agent files.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--config")
    parser.add_argument("--only")
    parser.add_argument("--paths", nargs="+")
    parser.add_argument("--base")
    parser.add_argument("--pr-body")
    parser.add_argument("--next", metavar="NS")
    parser.add_argument("--owners", nargs="+", metavar="PATH")
    parser.add_argument("--matrix", metavar="FILE")
    parser.add_argument("--domain", metavar="NS")
    parser.add_argument("--decisions", action="store_true")
    parser.add_argument("--pending", action="store_true")
    parser.add_argument("--blocking-list", metavar="FILE")
    return parser


def _mode(args) -> str:
    modes = [name for name, on in (("next", args.next is not None), ("owners", args.owners is not None),
                                   ("matrix", args.matrix is not None), ("pending", args.pending)) if on]
    if len(modes) > 1:
        raise ConfigError(f"conflicting modes: {', '.join('--' + m for m in modes)}")
    mode = modes[0] if modes else "default"
    default_flags = [f for f, v in (("--only", args.only), ("--paths", args.paths), ("--base", args.base),
                                    ("--pr-body", args.pr_body)) if v is not None]
    if mode != "default" and default_flags:
        raise ConfigError(f"--{mode} cannot be combined with {', '.join(default_flags)}")
    if (args.domain is not None or args.decisions) and mode != "matrix":
        raise ConfigError("--domain and --decisions need --matrix")
    if mode == "matrix" and args.domain is None and not args.decisions:
        raise ConfigError("--matrix needs --domain or --decisions")
    if (args.blocking_list is None) != (not args.pending):
        raise ConfigError("--pending and --blocking-list go together")
    return mode


def _selected_checks(args) -> list[str]:
    if args.only is not None:
        letters = [letter.strip() for letter in args.only.split(",") if letter.strip()]
        if not letters:
            raise ConfigError("--only needs at least one check letter")
        for letter in letters:
            if letter not in RUNNERS:
                raise ConfigError(f"unknown check letter {letter!r}")
        if {"C2", "G"} & set(letters) and args.base is None:
            raise ConfigError("C2 and G need --base")
        return [letter for letter in ORDER if letter in letters]
    selected = list(DEFAULT)
    if args.base is not None:
        selected.append("C2")
        selected.append("G")
    return [letter for letter in ORDER if letter in selected]


def _require_file(repo: Repo, path: str, what: str) -> None:
    if path not in repo.file_set:
        raise ConfigError(f"{what} not found: {path}")


def _emit(found: list[Finding], path_globs: list[str] | None) -> int:
    if path_globs is not None:
        found = [f for f in found if globs.match_any(path_globs, f.path)]
    findings = sorted({f for f in found if not f.notice})
    notices = sorted({f for f in found if f.notice})
    for finding in findings:
        print(finding.render())
    for notice in notices:
        print(notice.render(), file=sys.stderr)
    if findings:
        counts = {}
        for finding in findings:
            counts[finding.check] = counts.get(finding.check, 0) + 1
        detail = ", ".join(f"{check}={counts[check]}" for check in ORDER + ["M"] if check in counts)
        print(f"docs_check: {len(findings)} findings ({detail})", file=sys.stderr)
        return 1
    print("docs_check: clean", file=sys.stderr)
    return 0


def run(argv: list[str]) -> int:
    args = _parser().parse_args(argv)
    mode = _mode(args)
    root = Path(args.root)
    if not is_top_of_work_tree(root):
        raise ConfigError(f"{args.root} is not the top of a git work tree")
    config_path = Path(args.config) if args.config else root / "docs-check.toml"
    cfg = load(config_path)
    repo = Repo(root)
    try:
        label = Path(os.path.relpath(config_path.resolve(), root.resolve())).as_posix()
    except ValueError:
        label = str(config_path)

    if mode == "next":
        if args.next not in cfg.namespaces:
            raise ConfigError(f"unknown namespace {args.next!r}")
        print(ids.next_id(Context(cfg, repo, label), args.next))
        return 0
    if mode == "owners":
        lines, unowned = ownership.owners_lines(Context(cfg, repo, label), args.owners)
        print("\n".join(lines))
        return 1 if unowned else 0
    if mode in ("matrix", "pending"):
        if cfg.rollout is None:
            raise ConfigError("no [rollout] table")
        ctx = Context(cfg, repo, label)
        if mode == "pending":
            _require_file(repo, args.blocking_list, "blocking list")
            return _emit(matrix.check_pending(ctx, args.blocking_list), None)
        _require_file(repo, args.matrix, "matrix")
        if args.domain is not None and args.domain not in cfg.namespaces:
            raise ConfigError(f"unknown namespace {args.domain!r}")
        if args.decisions:
            return _emit(matrix.check_decisions(ctx, args.matrix, args.domain), None)
        return _emit(matrix.check_domain(ctx, args.matrix, args.domain), None)

    checks = _selected_checks(args)
    base = None
    if args.base is not None:
        base = repo.resolve_commit(args.base)
        if base is None:
            raise ConfigError(f"--base {args.base} does not resolve to a commit")
    body = None
    if args.pr_body is not None:
        try:
            body = Path(args.pr_body).read_text(encoding="utf-8")
        except OSError as error:
            raise ConfigError(f"cannot read PR body: {error}") from None
    path_globs = None
    if args.paths is not None:
        path_globs = [p.strip() for arg in args.paths for p in arg.split(",") if p.strip()]
        if not path_globs:
            raise ConfigError("--paths needs at least one glob")
    if "F" in checks and cfg.rollout is not None and cfg.rollout.get("base"):
        if repo.resolve_commit(cfg.rollout["base"]) is None:
            raise ConfigError(f"[rollout] base {cfg.rollout['base']} does not resolve to a commit")
    if "H" in checks:
        _require_file(repo, cfg.section("checks", "H", "file"), "[checks.H] file")
    if "J" in checks:
        _require_file(repo, cfg.section("checks", "J", "index"), "[checks.J] index")
    if "G" in checks and body is None:
        checks.remove("G")
        print("G skipped: no PR body", file=sys.stderr)

    ctx = Context(cfg, repo, label, base=base, pr_body=body)
    found: list[Finding] = []
    for letter in checks:
        found.extend(RUNNERS[letter](ctx))
    return _emit(found, path_globs)


def main(argv: list[str] | None = None) -> int:
    try:
        return run(sys.argv[1:] if argv is None else argv)
    except (ConfigError, GitError) as error:
        print(f"docs_check: error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

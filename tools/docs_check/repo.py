"""Git and file access for the checks. Every git call passes an argument list; nothing goes through a shell."""

import os
import re
import subprocess
from functools import cached_property
from pathlib import Path


class GitError(Exception):
    pass


def git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(["git", *args], cwd=root, capture_output=True)
    if check and proc.returncode != 0:
        raise GitError(proc.stderr.decode("utf-8", "replace").strip())
    return proc


def is_top_of_work_tree(root: Path) -> bool:
    if not root.is_dir():
        return False
    proc = git(root, "rev-parse", "--show-toplevel", check=False)
    if proc.returncode != 0:
        return False
    top = proc.stdout.decode("utf-8", "replace").strip()
    return os.path.realpath(top) == os.path.realpath(root)


class Repo:
    """One work tree: its file set, file contents and history."""

    def __init__(self, root: Path):
        self.root = root
        self._texts: dict[str, str] = {}

    @cached_property
    def files(self) -> list[str]:
        """Tracked plus untracked-but-not-ignored paths that exist in the work tree, sorted."""
        out = git(self.root, "ls-files", "-z", "--cached", "--others", "--exclude-standard").stdout
        paths = {p.decode("utf-8", "surrogateescape") for p in out.split(b"\0") if p}
        return sorted(p for p in paths if os.path.lexists(self.root / p))

    @cached_property
    def file_set(self) -> set[str]:
        return set(self.files)

    @cached_property
    def dirs(self) -> set[str]:
        found = set()
        for path in self.files:
            parts = path.split("/")[:-1]
            for end in range(1, len(parts) + 1):
                found.add("/".join(parts[:end]))
        return found

    def exists(self, path: str) -> bool:
        path = path.rstrip("/")
        return path in self.file_set or path in self.dirs

    def text(self, path: str) -> str:
        if path not in self._texts:
            try:
                self._texts[path] = (self.root / path).read_text(encoding="utf-8", errors="replace")
            except (IsADirectoryError, FileNotFoundError):
                self._texts[path] = ""
        return self._texts[path]

    def size(self, path: str) -> int:
        return (self.root / path).stat().st_size

    def resolve_commit(self, ref: str) -> str | None:
        proc = git(self.root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", check=False)
        if proc.returncode != 0:
            return None
        return proc.stdout.decode().strip()

    def is_ancestor(self, ancestor: str, descendant: str = "HEAD") -> bool:
        return git(self.root, "merge-base", "--is-ancestor", ancestor, descendant, check=False).returncode == 0

    def diff_name_status(self, base: str) -> list[tuple[str, list[str]]]:
        """(status, paths) of the net change `base...HEAD`; a rename lists its old and new path."""
        out = git(self.root, "diff", "--name-status", "-z", "-M", f"{base}...HEAD").stdout
        fields = [f.decode("utf-8", "surrogateescape") for f in out.split(b"\0") if f]
        changes = []
        index = 0
        while index < len(fields):
            status = fields[index]
            count = 2 if status[0] in "RC" else 1
            changes.append((status, fields[index + 1 : index + 1 + count]))
            index += 1 + count
        return changes

    def added_line_numbers(self, base: str, path: str) -> list[int]:
        """Line numbers, in the HEAD version of `path`, of lines the net diff `base...HEAD` adds."""
        out = git(self.root, "diff", "--unified=0", f"{base}...HEAD", "--", path).stdout.decode("utf-8", "replace")
        numbers = []
        for match in re.finditer(r"^@@ -\S+ \+(\d+)(?:,(\d+))? @@", out, re.M):
            start, count = int(match.group(1)), int(match.group(2) or "1")
            numbers.extend(range(start, start + count))
        return numbers

    def show(self, ref: str, path: str) -> str | None:
        proc = git(self.root, "show", f"{ref}:{path}", check=False)
        if proc.returncode != 0:
            return None
        return proc.stdout.decode("utf-8", "replace")

    def ls_tree(self, ref: str) -> list[str]:
        out = git(self.root, "ls-tree", "-r", "-z", "--name-only", ref).stdout
        return [p.decode("utf-8", "surrogateescape") for p in out.split(b"\0") if p]

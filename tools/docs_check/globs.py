"""Path globs matched against whole repo-relative paths.

`**` matches zero or more whole segments, `*` any run of characters except `/`, `?` one character except `/`.
There are no braces and no character classes.
"""

import functools
import re


@functools.lru_cache(maxsize=None)
def compile_glob(pattern: str) -> re.Pattern[str]:
    segments = pattern.split("/")
    out = []
    after_double_star = False
    for index, segment in enumerate(segments):
        last = index == len(segments) - 1
        if segment == "**":
            if last:
                out.append(".*" if index == 0 else "(?:/.*)?")
            else:
                out.append(("" if index == 0 else "/") + "(?:[^/]+/)*")
            after_double_star = True
            continue
        if index > 0 and not after_double_star:
            out.append("/")
        after_double_star = False
        for char in segment:
            if char == "*":
                out.append("[^/]*")
            elif char == "?":
                out.append("[^/]")
            else:
                out.append(re.escape(char))
    return re.compile("".join(out) + r"\Z")


def match(pattern: str, path: str) -> bool:
    return compile_glob(pattern).match(path) is not None


def match_any(patterns, path: str) -> bool:
    return any(match(pattern, path) for pattern in patterns)


def is_glob(pattern: str) -> bool:
    return any(char in pattern for char in "*?")

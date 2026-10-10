"""Removal of dated backup folders past the retention window."""

from __future__ import annotations

import shutil
from datetime import date, timedelta
from pathlib import Path


def prune_dated(parent: Path, keep_days: int, today: date) -> list[str]:
    """Deletes `YYYY-MM-DD` folders older than `keep_days` before `today`; returns their names.

    The newest dated folder is kept whatever its age, so a long outage never empties the backup.
    Anything not named as a date is left alone.
    """
    if not parent.is_dir():
        return []
    dated: dict[date, Path] = {}
    for child in parent.iterdir():
        try:
            dated[date.fromisoformat(child.name)] = child
        except ValueError:
            continue
    if not dated:
        return []
    newest = max(dated)
    cutoff = today - timedelta(days=keep_days)
    removed = []
    for day in sorted(dated):
        if day < cutoff and day != newest:
            shutil.rmtree(dated[day])
            removed.append(dated[day].name)
    return removed

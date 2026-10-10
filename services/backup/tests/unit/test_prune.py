from datetime import date
from pathlib import Path

from auspex_backup.prune import prune_dated


def _folders(parent: Path, *names: str) -> None:
    for name in names:
        (parent / name).mkdir(parents=True)
        (parent / name / "auspex.dump").write_bytes(b"x")


def test_dated_folders_older_than_keep_days_are_pruned_and_the_newest_never_is(
    tmp_path: Path,
) -> None:
    _folders(tmp_path / "postgres", "2026-09-20", "2026-09-26", "2026-09-27", "2026-10-10")
    (tmp_path / "postgres" / "notes").mkdir()

    removed = prune_dated(tmp_path / "postgres", keep_days=14, today=date(2026, 10, 10))

    # 2026-09-26 is exactly 14 days old, not older.
    assert removed == ["2026-09-20"]
    assert sorted(p.name for p in (tmp_path / "postgres").iterdir()) == [
        "2026-09-26",
        "2026-09-27",
        "2026-10-10",
        "notes",
    ]

    _folders(tmp_path / "neo4j", "2026-01-01", "2026-02-01")
    assert prune_dated(tmp_path / "neo4j", keep_days=14, today=date(2026, 10, 10)) == [
        "2026-01-01"
    ]
    assert [p.name for p in (tmp_path / "neo4j").iterdir()] == ["2026-02-01"]


def test_pruning_a_missing_folder_does_nothing(tmp_path: Path) -> None:
    assert prune_dated(tmp_path / "neo4j", keep_days=14, today=date(2026, 10, 10)) == []

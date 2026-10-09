"""The CI script that rejects commits attributed to Claude, run against throwaway repositories."""

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT = REPO_ROOT / ".github" / "scripts" / "check_commit_identity.sh"

_PERSON = ("matthias.debeule", "debeulematthias@gmail.com")


def _git(repo: Path, *args: str, env: dict[str, str] | None = None) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, env=env, check=True, capture_output=True, text=True
    ).stdout.strip()


def _commit(
    repo: Path,
    message: str,
    author: tuple[str, str] = _PERSON,
    committer: tuple[str, str] = _PERSON,
) -> None:
    env = {
        "GIT_AUTHOR_NAME": author[0],
        "GIT_AUTHOR_EMAIL": author[1],
        "GIT_COMMITTER_NAME": committer[0],
        "GIT_COMMITTER_EMAIL": committer[1],
        "PATH": "/usr/bin:/bin:/usr/local/bin",
        "HOME": str(repo),
    }
    _git(repo, "commit", "--allow-empty", "-q", "-m", message, env=env)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    _commit(tmp_path, "base")
    _git(tmp_path, "tag", "base")
    return tmp_path


def _check(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), "base..HEAD"], cwd=repo, capture_output=True, text=True, check=False
    )


def test_commits_by_a_person_pass(repo: Path) -> None:
    _commit(repo, "feature: one")
    _commit(repo, "feature: two")
    assert _check(repo).returncode == 0


def test_claude_author_is_rejected(repo: Path) -> None:
    _commit(repo, "feature: one", author=("Claude", "noreply@anthropic.com"))
    result = _check(repo)
    assert result.returncode == 1
    assert "feature: one" in result.stdout


def test_claude_committer_is_rejected(repo: Path) -> None:
    _commit(repo, "feature: one", committer=("Claude", "noreply@anthropic.com"))
    assert _check(repo).returncode == 1


def test_co_authored_by_claude_trailer_is_rejected(repo: Path) -> None:
    _commit(repo, "feature: one\n\nCo-Authored-By: Claude Opus <noreply@anthropic.com>")
    assert _check(repo).returncode == 1


def test_claude_session_trailer_is_rejected(repo: Path) -> None:
    _commit(repo, "feature: one\n\nClaude-Session: https://claude.ai/code/session_x")
    assert _check(repo).returncode == 1


def test_only_commits_in_the_range_are_checked(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    _commit(tmp_path, "old", author=("Claude", "noreply@anthropic.com"))
    _git(tmp_path, "tag", "base")
    _commit(tmp_path, "feature: one")
    assert _check(tmp_path).returncode == 0

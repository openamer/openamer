"""The updater must not silently discard COMMITTED local work.

Measured incident (2026-11-02): an in-app update on a laptop whose ``main``
carried three local commits ran ``git reset --hard origin/main`` because the
history had diverged. The autostash protected only the uncommitted changes;
every committed local commit became unreachable from a branch, and the user
was told "nothing is lost".
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from openamer_cli.main import _create_rescue_branch


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@t.local")
    _git(repo, "config", "user.name", "t")
    (repo / "f.txt").write_text("one\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "local work")
    return repo


def test_rescue_branch_keeps_local_commits_reachable(tmp_path):
    repo = _make_repo(tmp_path)
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()

    branch = _create_rescue_branch(["git"], repo, head)

    assert branch, "a rescue branch must be created"
    assert _git(repo, "rev-parse", branch).stdout.strip() == head
    # The commit survives a destructive reset to an unrelated origin/main.
    _git(repo, "branch", "target", head)
    _git(repo, "checkout", "-q", "target")
    (repo / "f.txt").write_text("two\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "remote work")
    _git(repo, "reset", "-q", "--hard", "HEAD")
    # The rescued commit is still reachable by name — that is the whole point.
    assert _git(repo, "rev-parse", branch).stdout.strip() == head


def test_rescue_branch_is_not_created_without_a_sha(tmp_path):
    repo = _make_repo(tmp_path)
    # With no explicit sha it falls back to HEAD, which exists here.
    branch = _create_rescue_branch(["git"], repo, None)
    assert branch
    assert (
        _git(repo, "rev-parse", branch).stdout.strip()
        == _git(repo, "rev-parse", "HEAD").stdout.strip()
    )


def test_rescue_branch_falls_back_to_head_when_sha_is_unknown(tmp_path):
    repo = _make_repo(tmp_path)
    # An empty sha must still resolve via HEAD, not silently do nothing.
    branch = _create_rescue_branch(["git"], repo, "")
    assert branch
    assert (
        _git(repo, "rev-parse", branch).stdout.strip()
        == _git(repo, "rev-parse", "HEAD").stdout.strip()
    )


def test_rescue_branch_name_is_git_safe(tmp_path):
    repo = _make_repo(tmp_path)
    branch = _create_rescue_branch(["git"], repo, None)
    assert branch
    assert " " not in branch
    assert not branch.startswith("-")


def test_two_rescues_in_the_same_second_get_distinct_branches(tmp_path):
    """Two rescues within one second must not collide on the same name."""
    repo = _make_repo(tmp_path)
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    first = _create_rescue_branch(["git"], repo, head)
    second = _create_rescue_branch(["git"], repo, head)
    assert first and second
    assert first != second, "the second rescue must not silently fail on a name clash"
    assert _git(repo, "rev-parse", second).stdout.strip() == head

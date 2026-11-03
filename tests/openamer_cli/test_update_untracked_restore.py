"""Untracked-file restore: "already exists" is not proof that nothing was lost.

Measured 2026-11-03 on a real in-app update: the pull brought in a tracked
file at a path the user also had as an untracked local file. ``git stash apply``
refused to overwrite it ("already exists, no checkout" + "could not restore
untracked files from stash") and exited non-zero. The updater then printed
"nothing is lost" and dropped the stash - the only place the user's version of
that file existed. The class of bug: the restore path treated the "file
exists" signal as "content is identical" and never compared bytes.

These tests use real git repositories rather than mocks, because the bug lives
in the interaction between git's own messages and the restore path.
"""

import os
import subprocess
from pathlib import Path

from openamer_cli import main as openamer_main

NEWLINE = "\n"


def _git_env(tmp_path: Path) -> dict:
    """A hermetic git environment (no user/system git config leaks in)."""
    return {
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@example.com",
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(tmp_path),
    }


def _write(repo: Path, name: str, text: str) -> None:
    """Write a file with LF endings, matching what git stores in a blob."""
    (repo / name).write_text(text + NEWLINE, encoding="utf-8", newline=NEWLINE)


def _real_git_repo(tmp_path: Path) -> Path:
    """Create a git repo with one commit and return its path."""
    repo = tmp_path / "repo"
    repo.mkdir()
    env = _git_env(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True, env=env)
    _write(repo, "tracked.txt", "base")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, env=env)
    subprocess.run(
        ["git", "commit", "-q", "-m", "base"], cwd=repo, check=True, env=env
    )
    return repo


def _stash(repo: Path, env: dict) -> str:
    """Stash tracked+untracked changes and return the stash commit sha."""
    subprocess.run(
        ["git", "stash", "push", "--include-untracked", "-m", "auto"],
        cwd=repo,
        check=True,
        env=env,
    )
    return subprocess.run(
        ["git", "rev-parse", "refs/stash"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    ).stdout.strip()


def test_untracked_stash_files_differ_reports_identical_files_as_equal(tmp_path):
    """A stashed untracked file that matches the working tree is not a loss."""
    repo = _real_git_repo(tmp_path)
    env = _git_env(tmp_path)
    _write(repo, "local.txt", "same")
    _stash(repo, env)
    # Recreate the identical file, as the upstream pull would.
    _write(repo, "local.txt", "same")

    differing = openamer_main._untracked_stash_files_differ(
        ["git"], repo, "stash@{0}"
    )

    assert differing == []


def test_untracked_stash_files_differ_reports_changed_content(tmp_path):
    """A stashed untracked file whose working-tree copy differs IS a loss."""
    repo = _real_git_repo(tmp_path)
    env = _git_env(tmp_path)
    _write(repo, "local.txt", "user version")
    _stash(repo, env)
    # The upstream pull wrote a different file at the same path.
    _write(repo, "local.txt", "upstream version")

    differing = openamer_main._untracked_stash_files_differ(
        ["git"], repo, "stash@{0}"
    )

    assert "local.txt" in differing


def test_restore_keeps_stash_when_untracked_content_differs(tmp_path, capsys):
    """The stash survives when the blocked untracked file has different bytes.

    This is the regression: the old path printed "nothing is lost" and dropped
    the stash, destroying the only copy of the user's file.
    """
    repo = _real_git_repo(tmp_path)
    env = _git_env(tmp_path)
    _write(repo, "local.txt", "user version")
    stash_ref = _stash(repo, env)
    _write(repo, "local.txt", "upstream version")

    restored = openamer_main._restore_stashed_changes(
        ["git"], repo, stash_ref, prompt_user=False
    )

    out = capsys.readouterr().out
    assert restored is False
    assert "content differs" in out
    assert "local.txt" in out
    # The stash entry must still exist - it holds the only copy of the file.
    still_there = subprocess.run(
        ["git", "stash", "list"],
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
    ).stdout
    assert "auto" in still_there


def test_restore_drops_stash_when_untracked_content_matches(tmp_path, capsys):
    """Identical content is not a loss - the normal restore path still applies.

    Guards the fix against over-reach: the byte comparison must not keep the
    stash alive when every blocked file is byte-identical to its stashed copy.
    """
    repo = _real_git_repo(tmp_path)
    env = _git_env(tmp_path)
    _write(repo, "local.txt", "same")
    stash_ref = _stash(repo, env)
    _write(repo, "local.txt", "same")

    restored = openamer_main._restore_stashed_changes(
        ["git"], repo, stash_ref, prompt_user=False
    )

    out = capsys.readouterr().out
    assert restored is True
    assert "content differs" not in out
    # The stash was applied cleanly, so it may be dropped.
    still_there = subprocess.run(
        ["git", "stash", "list"],
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
    ).stdout
    assert "auto" not in still_there

"""End-to-end proof: the update path must not lose committed local work.

Reproduces the measured 2026-11-02 incident in a throwaway repo:
  1. local commit on main that is NOT on origin/main
  2. history diverged -> `git pull --ff-only` fails
  3. updater runs `git reset --hard origin/main`
  4. WITHOUT the rescue branch the local commit is unreachable from a branch
  5. WITH the rescue branch it is still there, and the user is told where
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from openamer_cli.main import _create_rescue_branch


def _git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=check,
    )


def _reachable_branches(repo: Path, sha: str) -> list[str]:
    """Names of the branches that contain ``sha``."""
    out = _git(repo, "branch", "--contains", sha, check=False).stdout
    return [
        line.strip().lstrip("* ").strip() for line in out.splitlines() if line.strip()
    ]


def test_diverged_update_keeps_local_commit_reachable(tmp_path):
    origin = tmp_path / "origin.git"
    origin.mkdir()
    _git(origin, "init", "-q", "--bare", "-b", "main")

    clone = tmp_path / "clone"
    _git(tmp_path, "clone", "-q", str(origin), str(clone))
    _git(clone, "config", "user.email", "t@t.local")
    _git(clone, "config", "user.name", "t")
    (clone / "f.txt").write_text("base\n", encoding="utf-8")
    _git(clone, "add", "-A")
    _git(clone, "commit", "-q", "-m", "base")
    _git(clone, "push", "-q", "origin", "main")

    # --- the user's local commit, not on the remote ---
    (clone / "local.txt").write_text("my work\n", encoding="utf-8")
    _git(clone, "add", "-A")
    _git(clone, "commit", "-q", "-m", "feat: my local work")
    local_sha = _git(clone, "rev-parse", "HEAD").stdout.strip()

    # --- the remote moves on, so the histories diverge ---
    other = tmp_path / "other"
    _git(tmp_path, "clone", "-q", str(origin), str(other))
    _git(other, "config", "user.email", "t@t.local")
    _git(other, "config", "user.name", "t")
    (other / "f.txt").write_text("remote\n", encoding="utf-8")
    _git(other, "add", "-A")
    _git(other, "commit", "-q", "-m", "remote work")
    _git(other, "push", "-q", "origin", "main")
    _git(clone, "fetch", "-q", "origin")

    # --- what the updater does ---
    pull = _git(clone, "pull", "--ff-only", "origin", "main", check=False)
    assert pull.returncode != 0, "the fixture must produce a diverged history"

    pre_pull_sha = _git(clone, "rev-parse", "HEAD").stdout.strip()
    rescue = _create_rescue_branch(["git"], clone, pre_pull_sha)
    assert rescue, "the rescue branch must exist before the destructive reset"

    _git(clone, "reset", "--hard", "origin/main")

    # The local commit is gone from `main` ...
    assert _git(clone, "rev-parse", "HEAD").stdout.strip() != local_sha
    # ... but still reachable through the rescue branch.
    assert rescue in _reachable_branches(clone, local_sha)

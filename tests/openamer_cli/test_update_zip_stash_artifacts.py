"""Updater scratch trees must stay outside the autostash (real git)."""
import subprocess
from pathlib import Path

from openamer_cli.main import _stash_local_changes_if_needed


def test_update_scratch_trees_are_not_stashed(tmp_path):
    def git(*args):
        return subprocess.run(["git", *args], cwd=tmp_path, check=True,
                              capture_output=True, text=True, encoding="utf-8").stdout

    git("init")
    git("config", "user.email", "test@example.invalid")
    git("config", "user.name", "Updater test")
    root = Path(__file__).parents[2]
    (tmp_path / ".gitignore").write_bytes((root / ".gitignore").read_bytes())
    (tmp_path / "tracked.txt").write_text("original")
    git("add", ".")
    git("commit", "-m", "initial")
    artifacts = ["apps.openamer-update-old", "apps.openamer-update-staging",
                 "apps/desktop.openamer-update-old", "apps/desktop.openamer-update-staging"]
    for name in artifacts:
        directory = tmp_path / name
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "precious.txt").write_text("keep this")
    (tmp_path / "notes.txt").write_text("user notes")
    ref = _stash_local_changes_if_needed(["git"], tmp_path)
    assert ref
    untracked = git("ls-tree", "-r", "--name-only", f"{ref}^3").splitlines()
    assert untracked == ["notes.txt"]
    for name in artifacts:
        assert (tmp_path / name / "precious.txt").read_text() == "keep this"
    git("stash", "apply", ref)
    assert (tmp_path / "notes.txt").read_text() == "user notes"

"""Regression: _update_via_zip must skip a locked directory, not abort the update.

On Windows, ``openamer update`` runs from inside the live Desktop app, which
holds files under ``apps/desktop/release/`` open. The ZIP fallback then tries
to atomically replace ``apps/`` and hits ``[WinError 5] Zugriff verweigert``
(access denied) on the rename. Before the fix, that OSError propagated out of
``_update_via_zip`` and aborted the whole update, leaving a stale
``.update-incomplete`` marker that triggered a failing auto-recovery on every
subsequent launch.

The fix: a directory whose replace fails with OSError is skipped (with a
warning) instead of aborting, so the rest of the update completes and the
locked directory is refreshed on a later run once the process has exited.
"""

from __future__ import annotations

import os
import tempfile
import zipfile
from unittest.mock import patch

import pytest


def _build_zip_with_dir(zip_path: str) -> None:
    """Write a ZIP with a directory member plus a normal file member."""
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("openamer-agent-main/apps/", "")
        zf.writestr("openamer-agent-main/apps/desktop.txt", "desktop\n")
        zf.writestr("openamer-agent-main/README.md", "ok\n")


def test_update_via_zip_skips_locked_directory(tmp_path, monkeypatch, capsys):
    """A directory whose replace raises OSError is skipped, not fatal."""
    zip_path = tmp_path / "normal.zip"
    _build_zip_with_dir(str(zip_path))

    fake_root = tmp_path / "install_dir"
    fake_root.mkdir()

    from openamer_cli import main as openamer_main

    monkeypatch.setattr(openamer_main, "PROJECT_ROOT", fake_root)

    args = type("Args", (), {})()

    def fake_urlretrieve(url, dest):
        with open(zip_path, "rb") as src, open(dest, "wb") as dst:
            dst.write(src.read())
        return dest, None

    # Make _atomic_replace_dir raise OSError for the "apps" directory only,
    # simulating a Windows file lock (WinError 5). README.md is a file, so it
    # goes through shutil.copy2 and is unaffected.
    real_replace = openamer_main._atomic_replace_dir

    def locked_replace(src, dst):
        if os.path.basename(dst) == "apps":
            raise OSError("[WinError 5] Zugriff verweigert")
        return real_replace(src, dst)

    monkeypatch.setattr(openamer_main, "_atomic_replace_dir", locked_replace)

    with patch("urllib.request.urlretrieve", side_effect=fake_urlretrieve), \
         patch("subprocess.run") as fake_run, \
         patch("subprocess.check_call"):
        fake_run.return_value = type(
            "R", (), {"returncode": 0, "stdout": "", "stderr": ""}
        )()
        try:
            openamer_main._update_via_zip(args)
        except SystemExit:
            pass

    captured = capsys.readouterr()
    # The locked directory was skipped with a warning, not a fatal error.
    assert "Skipped apps" in captured.out
    assert "ZIP update failed" not in captured.out
    # The normal file still landed.
    assert (fake_root / "README.md").exists()
    assert (fake_root / "README.md").read_text() == "ok\n"

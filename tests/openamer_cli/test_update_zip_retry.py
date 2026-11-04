"""Interrupted/locked ZIP swaps must remain retryable without losing the live tree."""
import os
import shutil

import pytest

from openamer_cli.main import _atomic_replace_dir


def test_retry_restores_only_backup_before_copy_failure(tmp_path, monkeypatch):
    src = tmp_path / "src"
    src.mkdir()
    dst = tmp_path / "apps"
    backup = tmp_path / "apps.openamer-update-old"
    backup.mkdir()
    (backup / "precious").write_text("original bytes")

    def fail_copy(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(shutil, "copytree", fail_copy)
    with pytest.raises(OSError):
        _atomic_replace_dir(str(src), str(dst))
    assert (dst / "precious").read_text() == "original bytes"


@pytest.mark.parametrize("suffix", ["old", "staging"])
def test_locked_leftover_aborts_before_live_directory_moves(tmp_path, monkeypatch, suffix):
    src = tmp_path / "src"
    src.mkdir()
    (src / "new").write_text("NEW")
    dst = tmp_path / "apps"
    dst.mkdir()
    (dst / "keep").write_text("LIVE")
    leftover = tmp_path / f"apps.openamer-update-{suffix}"
    leftover.mkdir()
    (leftover / "locked").write_text("LOCKED")
    real_rmtree = shutil.rmtree
    renames = []
    real_rename = os.rename

    def locked_rmtree(path, *args, **kwargs):
        if str(path) == str(leftover):
            if not kwargs.get("ignore_errors"):
                raise PermissionError("locked build tree")
            return
        return real_rmtree(path, *args, **kwargs)

    def rename(src, dst):
        renames.append((src, dst))
        return real_rename(src, dst)

    monkeypatch.setattr(shutil, "rmtree", locked_rmtree)
    monkeypatch.setattr(os, "rename", rename)
    for _ in range(2):
        with pytest.raises(OSError):
            _atomic_replace_dir(str(src), str(dst))
        assert (dst / "keep").read_text() == "LIVE"
        assert (leftover / "locked").read_text() == "LOCKED"
    assert renames == []

"""Tests for restore_translation_backup.py.

The script exists because an update kills the workers and replaces the install
tree. Its job is narrow and must be safe: never overwrite a cache that is ahead
of the backup, and accept the MSYS path form the shell writes into LATEST.txt.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "restore_translation_backup.py"


def _load():
    spec = importlib.util.spec_from_file_location("restore_backup", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def restore():
    return _load()


def test_normalise_converts_msys_path(restore):
    p = restore.normalise("/c/Users/damir/openamer-work-backup/x\n")
    assert p.is_absolute(), f"not absolute: {p}"
    assert p == Path("C:/Users/damir/openamer-work-backup/x")


def test_normalise_keeps_native_path(restore):
    p = restore.normalise("C:/Users/damir/backup")
    assert str(p).startswith("C")


def test_restore_is_a_noop_when_destination_is_ahead(restore, tmp_path, monkeypatch):
    """A cache with MORE keys than the backup must not be downgraded."""
    backup = tmp_path / "bk"
    (backup / "cli-cache").mkdir(parents=True)
    (backup / "cli-cache" / "i18n_cli_zz_translations.json").write_text(
        json.dumps({"a": "1", "b": "2"}), encoding="utf-8")

    repo = tmp_path / "repo"
    (repo / "tmp").mkdir(parents=True)
    (repo / "tmp" / "i18n_cli_zz_translations.json").write_text(
        json.dumps({"a": "1", "b": "2", "c": "3"}), encoding="utf-8")

    monkeypatch.setattr(restore, "REPO", repo)
    monkeypatch.setattr(restore, "HOME", tmp_path / "home")

    assert restore.restore(backup, dry_run=False) == 0
    kept = json.loads((repo / "tmp" / "i18n_cli_zz_translations.json").read_text(encoding="utf-8"))
    assert set(kept) == {"a", "b", "c"}, "destination was downgraded"


def test_restore_copies_when_destination_is_behind(restore, tmp_path, monkeypatch):
    backup = tmp_path / "bk"
    (backup / "cli-cache").mkdir(parents=True)
    payload = {"a": "1", "b": "2", "c": "3"}
    (backup / "cli-cache" / "i18n_cli_zz_translations.json").write_text(
        json.dumps(payload), encoding="utf-8")

    repo = tmp_path / "repo"
    (repo / "tmp").mkdir(parents=True)
    (repo / "tmp" / "i18n_cli_zz_translations.json").write_text(
        json.dumps({"a": "1"}), encoding="utf-8")

    monkeypatch.setattr(restore, "REPO", repo)
    monkeypatch.setattr(restore, "HOME", tmp_path / "home")

    assert restore.restore(backup, dry_run=False) == 0
    got = json.loads((repo / "tmp" / "i18n_cli_zz_translations.json").read_text(encoding="utf-8"))
    assert got == payload


def test_dry_run_writes_nothing(restore, tmp_path, monkeypatch):
    backup = tmp_path / "bk"
    (backup / "cli-cache").mkdir(parents=True)
    (backup / "cli-cache" / "i18n_cli_zz_translations.json").write_text(
        json.dumps({"a": "1", "b": "2"}), encoding="utf-8")

    repo = tmp_path / "repo"
    (repo / "tmp").mkdir(parents=True)

    monkeypatch.setattr(restore, "REPO", repo)
    monkeypatch.setattr(restore, "HOME", tmp_path / "home")

    assert restore.restore(backup, dry_run=True) == 0
    assert not (repo / "tmp" / "i18n_cli_zz_translations.json").exists()

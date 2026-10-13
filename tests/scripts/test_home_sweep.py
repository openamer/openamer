"""Guard for the native home-hygiene organ (``scripts/home-sweep.py``).

The organ must move only *provable* junk (uv extraction dirs + torn shell
tokens), never delete, respect the freshness guard, and never touch Windows
profile hives or its own quarantine folders.
"""
import importlib.util
import os
import time
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "home_sweep",
    Path(__file__).resolve().parents[2] / "scripts" / "home-sweep.py",
)
home_sweep = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(home_sweep)

OLD = time.time() - 7 * 24 * 3600      # 7 days ago -> older than the 60-min guard
OLD_IMAGE = time.time() - 30 * 24 * 3600  # 30 days -> past the 14-day image bound
FRESH = time.time()                      # now -> inside the guard


def _aged_dir(path: Path, mtime: float, *files: str) -> Path:
    """Create *path* with *files* inside, THEN stamp its mtime.

    Writing a file bumps the parent directory's mtime, so the utime must come
    last — otherwise the freshness guard would see a brand-new dir.
    """
    path.mkdir(parents=True, exist_ok=True)
    for f in files:
        (path / f).write_bytes(b"x")
    os.utime(path, (mtime, mtime))
    return path


def test_moves_uv_leichen_and_fragments_only(tmp_path):
    _aged_dir(tmp_path / "3f2b1a4c-1111-2222-3333-444455556666", OLD, "uv.exe")
    # a UUID dir WITHOUT uv markers is not provable junk -> stays
    _aged_dir(tmp_path / "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", OLD)
    # torn shell tokens (age-stamped: writing a file bumps the parent mtime)
    for frag in ("AppDat", "({t", "t.slice(0"):
        p = tmp_path / frag
        p.write_text("", encoding="utf-8")
        os.utime(p, (OLD, OLD))
    # protected / legit -> must stay
    (tmp_path / "NTUSER.DAT").write_text("hive", encoding="utf-8")
    _aged_dir(tmp_path / "Desktop", OLD)
    _aged_dir(tmp_path / "_BACKUPS", OLD)
    (tmp_path / "notes.md").write_text("hello", encoding="utf-8")

    summary = home_sweep.sweep(tmp_path, min_age_minutes=60)
    assert summary["success"] is True
    assert summary["moved"]["uv_leichen"] == 1
    assert summary["moved"]["kaputte_pfadnamen"] == 3

    qdir = Path(summary["quarantine"])
    assert (qdir / "uv_leichen" / "3f2b1a4c-1111-2222-3333-444455556666").is_dir()
    assert (qdir / "kaputte_pfadnamen" / "AppDat").exists()
    # nothing was deleted
    assert (tmp_path / "NTUSER.DAT").exists()
    assert (tmp_path / "Desktop").is_dir()
    assert (tmp_path / "_BACKUPS").is_dir()
    assert (tmp_path / "notes.md").exists()
    assert (tmp_path / "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee").is_dir()
    # manifest recorded the actions
    assert (qdir / "manifest.json").exists()


class _FakePath:
    """Just enough Path surface for the classifier's name-based branch."""

    def __init__(self, name: str):
        self.name = name

    def is_dir(self) -> bool:
        return False


def test_classify_torn_shell_tokens():
    # An unquoted Windows path cannot even be created as a *path component* on
    # Windows (the colon is a drive), so the name rule is checked directly.
    for name in ("C:UsersdamirAppDataLocalfoo", "AppDat", "({t", "[h.points",
                 "t.slice(0", "JSON.stringify((j.data", "c.includes('indie')",
                 "UsersdamirAppDataLocalTempsession_20260818.jsonl"):
        assert home_sweep._classify(_FakePath(name), 0, 0, 14) == "kaputte_pfadnamen"
    # legitimate names are never classified
    for name in ("Desktop", "notes.md", "openamer-repo", "1.5.0", "x.h"):
        assert home_sweep._classify(_FakePath(name), 0, 0, 14) is None


def test_session_exports_and_screenshots_with_asset_protection(tmp_path):
    def _aged_file(name: str, mtime: float) -> Path:
        p = tmp_path / name
        p.write_text("{}", encoding="utf-8")
        os.utime(p, (mtime, mtime))
        return p

    # agent session/export dumps -> swept
    _aged_file("reflect_session.jsonl", OLD)
    _aged_file("session_export.json", OLD)
    # old screenshot -> swept; asset-looking image and fresh shot -> kept
    shot = tmp_path / "fiverr_gig1_done.png"
    shot.write_bytes(b"x")
    os.utime(shot, (OLD_IMAGE, OLD_IMAGE))
    logo = tmp_path / "emilija-logo-512.png"
    logo.write_bytes(b"x")
    os.utime(logo, (OLD_IMAGE, OLD_IMAGE))
    fresh = tmp_path / "shot_recent.png"
    fresh.write_bytes(b"x")
    os.utime(fresh, (FRESH, FRESH))
    # a plain data json with no session/export token -> kept
    _aged_file("config_backup.json", OLD)

    summary = home_sweep.sweep(tmp_path, min_age_minutes=60, artifact_min_age_days=14)
    assert summary["moved"]["session_exports"] == 2
    assert summary["moved"]["agent_screenshots"] == 1
    assert logo.exists()        # asset protected
    assert fresh.exists()       # too new
    assert (tmp_path / "config_backup.json").exists()


def test_freshness_guard_leaves_young_entries(tmp_path):
    d = _aged_dir(tmp_path / "12345678-1111-2222-3333-444455556666", FRESH, "uv.exe")
    summary = home_sweep.sweep(tmp_path, min_age_minutes=60)
    assert summary["moved_total"] == 0
    assert summary["skipped_fresh_or_locked"] == 1
    assert d.is_dir()          # untouched


def test_dry_run_moves_nothing(tmp_path):
    d = _aged_dir(tmp_path / "12345678-1111-2222-3333-444455556666", OLD, "uv.zip")
    summary = home_sweep.sweep(tmp_path, dry_run=True)
    assert summary["moved"]["uv_leichen"] == 1
    assert summary["quarantine"] is None
    assert d.is_dir()
    assert not list(tmp_path.glob("_QUARANTAENE-*"))


def test_max_moves_bound_is_respected(tmp_path):
    for i in range(5):
        _aged_dir(tmp_path / f"{i:08d}-1111-2222-3333-444455556666", OLD, "uvx.exe")
    summary = home_sweep.sweep(tmp_path, max_moves=2)
    assert summary["moved_total"] == 2


def test_real_home_default_is_a_noop_not_an_error():
    """Running with the default target on this machine must exit cleanly.

    The home was swept on 2026-10-11; a second run is provably idempotent.
    """
    summary = home_sweep.sweep(Path.home(), dry_run=True)
    assert summary["success"] is True

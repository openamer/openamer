"""Tests for get_openamer_home() profile-mode fallback warning.

Regression test for https://github.com/openamer/openamer/issues/18594.

When OPENAMER_HOME is unset but an active_profile file indicates a non-default
profile is active, get_openamer_home() should:
  1. STILL return ~/.openamer (raising would brick 30+ module-level callers)
  2. Emit a loud one-shot warning to stderr so operators can diagnose
     cross-profile data contamination after the fact.

The warning goes to stderr directly (not through logging) because this
function is called at module-import time from 30+ sites, often before the
logging subsystem has been configured.
"""

import sys
from pathlib import Path

import pytest


def _platform_default(home: Path) -> Path:
    """The platform-native OpenAmer home under a fake user home.

    Mirrors ``openamer_constants._get_platform_default_openamer_home()``:
    Windows resolves ``%LOCALAPPDATA%\\openamer``, every other platform
    ``~/.openamer``. The tests below assert against that real per-platform
    answer instead of hardcoding the POSIX layout, which made the whole module
    red whenever the canonical suite ran on Windows.
    """
    if sys.platform == "win32":
        return home / "AppData" / "Local" / "openamer"
    return home / ".openamer"


@pytest.fixture
def fresh_constants(monkeypatch, tmp_path):
    """Import openamer_constants fresh and reset the one-shot warn flag."""
    import importlib
    import openamer_constants
    importlib.reload(openamer_constants)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    # Windows resolves the platform default from %LOCALAPPDATA% *ahead of* the
    # home directory, so pin that under the fake home as well — otherwise the
    # test reads the developer's real %LOCALAPPDATA%\openamer and every
    # assertion below compares against a path the code never returns.
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "AppData" / "Local"))
    monkeypatch.delenv("OPENAMER_HOME", raising=False)
    return openamer_constants


class TestGetOpenAmerHomeProfileWarning:
    def test_classic_mode_no_active_profile_no_warning(
        self, fresh_constants, tmp_path, capsys
    ):
        """Classic mode: no active_profile file → silent, returns ~/.openamer."""
        result = fresh_constants.get_openamer_home()
        assert result == _platform_default(tmp_path)
        assert "OPENAMER_HOME fallback" not in capsys.readouterr().err

    def test_default_active_profile_no_warning(
        self, fresh_constants, tmp_path, capsys
    ):
        """active_profile=default → still no warning, returns ~/.openamer."""
        openamer_dir = _platform_default(tmp_path)
        openamer_dir.mkdir(parents=True)
        (openamer_dir / "active_profile").write_text("default\n")
        result = fresh_constants.get_openamer_home()
        assert result == _platform_default(tmp_path)
        assert "OPENAMER_HOME fallback" not in capsys.readouterr().err

    def test_named_profile_unset_home_warns_once(
        self, fresh_constants, tmp_path, capsys
    ):
        """active_profile=coder + OPENAMER_HOME unset → warn loudly, still return fallback."""
        openamer_dir = _platform_default(tmp_path)
        openamer_dir.mkdir(parents=True)
        (openamer_dir / "active_profile").write_text("coder\n")

        result = fresh_constants.get_openamer_home()

        # 1. Still returns the fallback — no import-time crash
        assert result == _platform_default(tmp_path)
        # 2. Stderr got the warning exactly once
        err = capsys.readouterr().err
        assert err.count("OPENAMER_HOME fallback") == 1
        assert "'coder'" in err
        assert "#18594" in err

        # 3. One-shot: second and third calls don't re-warn
        fresh_constants.get_openamer_home()
        fresh_constants.get_openamer_home()
        err2 = capsys.readouterr().err
        assert "OPENAMER_HOME fallback" not in err2

    def test_openamer_home_set_suppresses_warning(
        self, fresh_constants, tmp_path, capsys, monkeypatch
    ):
        """Even if active_profile is 'coder', setting OPENAMER_HOME suppresses warning."""
        profile_dir = tmp_path / ".openamer" / "profiles" / "coder"
        profile_dir.mkdir(parents=True)
        (tmp_path / ".openamer" / "active_profile").write_text("coder\n")
        monkeypatch.setenv("OPENAMER_HOME", str(profile_dir))

        result = fresh_constants.get_openamer_home()

        assert result == profile_dir
        assert "OPENAMER_HOME fallback" not in capsys.readouterr().err

    def test_unreadable_active_profile_no_crash(
        self, fresh_constants, tmp_path, capsys
    ):
        """active_profile that can't be decoded → fall through silently."""
        openamer_dir = _platform_default(tmp_path)
        openamer_dir.mkdir(parents=True)
        # Write bytes that aren't valid utf-8
        (openamer_dir / "active_profile").write_bytes(b"\xff\xfe\x00\x00")

        result = fresh_constants.get_openamer_home()

        assert result == _platform_default(tmp_path)
        # Shouldn't crash; shouldn't warn either (can't tell what profile was intended)
        assert "OPENAMER_HOME fallback" not in capsys.readouterr().err

    def test_empty_active_profile_no_warning(
        self, fresh_constants, tmp_path, capsys
    ):
        """Empty active_profile file → treated as default, no warning."""
        openamer_dir = _platform_default(tmp_path)
        openamer_dir.mkdir(parents=True)
        (openamer_dir / "active_profile").write_text("")

        result = fresh_constants.get_openamer_home()

        assert result == _platform_default(tmp_path)
        assert "OPENAMER_HOME fallback" not in capsys.readouterr().err

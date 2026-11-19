"""The rebuild helper must find THIS machine's install, not a hardcoded one.

Measured 2026-11-20: `desktop_rebuild.py --check` reported

    agent dir : C:\\Users\\damir\\AppData\\Local\\openamer\\openamer-agent
    desktop   : ... exists=False
    packed exe: ... exists=False

on a machine whose install is `openamer-laptop` and whose packaged app was
sitting right there. A preflight that says "nothing to build" on a machine that
has everything is worse than no preflight — it sends you looking for a build
problem you do not have.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "desktop_rebuild.py"


def _load(monkeypatch, home: Path, env: str | None = None):
    if env is None:
        monkeypatch.delenv("OPENAMER_HOME", raising=False)
    else:
        monkeypatch.setenv("OPENAMER_HOME", env)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))
    spec = importlib.util.spec_from_file_location("desktop_rebuild", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["desktop_rebuild"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_env_wins(tmp_path, monkeypatch):
    mod = _load(monkeypatch, tmp_path, env=str(tmp_path / "custom"))
    assert mod.DEFAULT_AGENT_DIR == tmp_path / "custom" / "openamer-agent"


def test_laptop_install_is_found(tmp_path, monkeypatch):
    """The actual layout on this host: AppData/Local/openamer-laptop."""
    (tmp_path / "AppData" / "Local" / "openamer-laptop" / "openamer-agent").mkdir(parents=True)
    mod = _load(monkeypatch, tmp_path)
    assert mod.DEFAULT_AGENT_DIR == (
        tmp_path / "AppData" / "Local" / "openamer-laptop" / "openamer-agent")


def test_plain_install_is_found(tmp_path, monkeypatch):
    (tmp_path / "AppData" / "Local" / "openamer" / "openamer-agent").mkdir(parents=True)
    mod = _load(monkeypatch, tmp_path)
    assert mod.DEFAULT_AGENT_DIR == (
        tmp_path / "AppData" / "Local" / "openamer" / "openamer-agent")


def test_laptop_wins_when_both_exist(tmp_path, monkeypatch):
    for name in ("openamer", "openamer-laptop"):
        (tmp_path / "AppData" / "Local" / name / "openamer-agent").mkdir(parents=True)
    mod = _load(monkeypatch, tmp_path)
    assert "openamer-laptop" in str(mod.DEFAULT_AGENT_DIR)

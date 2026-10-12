"""Guard for the desktop rebuild helper (``scripts/desktop_rebuild.py``).

The script must find the install that actually carries the desktop source.
Pinning one literal path made it report a healthy install as missing — and then
told the operator to relaunch an app it could not see. The resolver is an
ordered ladder, and a rung is trusted only once it holds ``apps/desktop``.
"""
import importlib.util
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "desktop_rebuild",
    Path(__file__).resolve().parents[2] / "scripts" / "desktop_rebuild.py",
)
desktop_rebuild = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(desktop_rebuild)


def _agent_tree(root: Path, *, with_desktop: bool) -> Path:
    """An agent tree, optionally carrying the desktop source."""
    root.mkdir(parents=True, exist_ok=True)
    if with_desktop:
        (root / "apps" / "desktop").mkdir(parents=True)
    return root


@pytest.fixture
def ladder(monkeypatch):
    """Redirect both env rungs at throwaway trees."""

    def _apply(env_home: Path | None, localappdata: Path | None) -> None:
        for key, val in (("OPENAMER_HOME", env_home), ("LOCALAPPDATA", localappdata)):
            if val is None:
                monkeypatch.delenv(key, raising=False)
            else:
                monkeypatch.setenv(key, str(val))

    return _apply


def test_openamer_home_agent_tree_wins(tmp_path, ladder):
    """``$OPENAMER_HOME/openamer-agent`` is the install root's agent tree."""
    home = tmp_path / "openamer-laptop"
    agent = _agent_tree(home / "openamer-agent", with_desktop=True)
    ladder(home, tmp_path / "no-such-local")

    assert desktop_rebuild._resolve_agent_dir() == agent


def test_openamer_home_may_be_the_agent_tree_itself(tmp_path, ladder):
    home = _agent_tree(tmp_path / "agent", with_desktop=True)
    ladder(home, tmp_path / "no-such-local")

    assert desktop_rebuild._resolve_agent_dir() == home


def test_a_rung_without_the_desktop_source_is_not_trusted(tmp_path, ladder):
    """The bug: a rung that exists but has no desktop source must not win."""
    empty_home = tmp_path / "openamer"      # exists, carries no apps/desktop
    empty_home.mkdir()
    local = tmp_path / "LocalAppData"
    real = _agent_tree(local / "openamer" / "openamer-agent", with_desktop=True)
    ladder(empty_home, local)

    assert desktop_rebuild._resolve_agent_dir() == real


def test_home_rung_precedes_the_platform_default(tmp_path, ladder):
    """Both rungs hold the source; the OPENAMER_HOME one must win."""
    home = tmp_path / "home"
    agent = _agent_tree(home / "openamer-agent", with_desktop=True)
    local = tmp_path / "LocalAppData"
    _agent_tree(local / "openamer" / "openamer-agent", with_desktop=True)
    ladder(home, local)

    assert desktop_rebuild._candidate_agent_dirs()[0] == agent
    assert desktop_rebuild._resolve_agent_dir() == agent


def test_falls_back_to_the_primary_rung_when_nothing_matches(tmp_path, ladder):
    """No candidate holds the source: report the primary, do not crash."""
    home = tmp_path / "openamer-laptop"
    ladder(home, tmp_path / "no-such-local")
    candidates = desktop_rebuild._candidate_agent_dirs()
    if any((c / "apps" / "desktop").is_dir() for c in candidates):
        pytest.skip("a real install exists on this host — fallback unreachable")

    assert desktop_rebuild._resolve_agent_dir() == candidates[0]

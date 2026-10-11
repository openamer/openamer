"""Install-scoped home resolution: this install's home, or nothing.

`OPENAMER_HOME` is not install-scoped. ``scripts/install.ps1`` writes it to the
*user* environment, so on a box with two install trees it names whichever tree
wrote it last -- and every later process (shells, scheduled tasks, the desktop
app's own backend) inherits that spelling.

The bug this file pins: ``dep_ensure`` ran ``install.ps1 -OpenAmerHome
(get_openamer_home())``. With the variable unset, ``get_openamer_home()`` answers
the *platform default* -- a guess -- and install.ps1 then **persisted** it, so one
update or reboot pinned the user environment to the wrong home for good. The
desktop app followed it into an empty ``%LOCALAPPDATA%\\openamer`` (a ~51-byte
onboarding stub) instead of the real install's config.

The rule under test: an install that cannot *prove* which home is its own must
resolve to ``None`` -- never to the platform default -- and the platform default
must stay exactly what ``get_openamer_home()`` returns, so the 30+ import-time
callers keep working.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import openamer_constants
from openamer_constants import (
    get_install_scoped_openamer_home,
    get_openamer_home,
    install_home_marker_path,
)


@pytest.fixture(autouse=True)
def _reset_fallback_guards(monkeypatch):
    """The warnings are one-shot per process; un-arm them per test."""
    monkeypatch.setattr(openamer_constants, "_install_fallback_checked", False)
    monkeypatch.setattr(openamer_constants, "_install_fallback_warned", False)
    monkeypatch.setattr(openamer_constants, "_profile_fallback_warned", False)
    monkeypatch.delenv("OPENAMER_HOME", raising=False)


def _shipped_layout(tmp_path: Path) -> tuple[Path, Path]:
    """<home>/openamer-agent with install evidence, as install.ps1 creates it."""
    home = tmp_path / "openamer-laptop"
    checkout = home / "openamer-agent"
    (checkout / ".git").mkdir(parents=True)
    return home, checkout


def test_breadcrumb_wins_when_openamer_home_is_unset(tmp_path):
    """OPENAMER_HOME missing + a present breadcrumb => the breadcrumb, not a default."""
    home, checkout = _shipped_layout(tmp_path)
    other = tmp_path / "custom-home"
    other.mkdir()
    install_home_marker_path(checkout).write_text(str(other), encoding="utf-8")

    resolved = get_install_scoped_openamer_home(checkout)

    assert resolved == str(other)
    assert resolved != str(home)

    # And the platform default is genuinely never the answer for an install that
    # carries its own evidence.
    platform_default = openamer_constants._get_platform_default_openamer_home()
    assert Path(resolved) != platform_default


def test_breadcrumb_is_read_bom_tolerantly(tmp_path):
    """The written file is BOM-less, but a BOM must not be glued onto the path."""
    _home, checkout = _shipped_layout(tmp_path)
    target = tmp_path / "home-with-bom"
    target.mkdir()
    install_home_marker_path(checkout).write_text(f"\ufeff{target}\n", encoding="utf-8")

    assert get_install_scoped_openamer_home(checkout) == str(target)


def test_empty_breadcrumb_falls_through_to_the_shipped_layout(tmp_path):
    home, checkout = _shipped_layout(tmp_path)
    install_home_marker_path(checkout).write_text("   \n", encoding="utf-8")

    assert get_install_scoped_openamer_home(checkout) == str(home)


def test_shipped_layout_needs_install_evidence(tmp_path):
    """A bare checkout named openamer-agent must not invent a home."""
    home = tmp_path / "openamer-laptop"
    checkout = home / "openamer-agent"
    checkout.mkdir(parents=True)

    assert get_install_scoped_openamer_home(checkout) is None


def test_no_evidence_resolves_to_none_never_the_platform_default(tmp_path, monkeypatch):
    """The whole point: unprovable is None, so no caller can persist a guess."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "LocalAppData"))
    checkout = tmp_path / "work" / "openamer-repo"
    checkout.mkdir(parents=True)

    assert get_install_scoped_openamer_home(checkout) is None

    # get_openamer_home() keeps its documented platform-default answer.
    default = get_openamer_home()
    assert default.name == "openamer"
    assert default.is_relative_to(tmp_path / "LocalAppData")


def test_openamer_home_env_is_the_last_rung(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAMER_HOME", str(tmp_path / "env-home"))
    checkout = tmp_path / "work" / "openamer-repo"
    checkout.mkdir(parents=True)

    assert get_install_scoped_openamer_home(checkout) == str(tmp_path / "env-home")

    # ...but real evidence outranks it.
    _home, shipped = _shipped_layout(tmp_path)
    assert get_install_scoped_openamer_home(shipped) == str(tmp_path / "openamer-laptop")


def test_running_checkout_root_defaults_beside_this_module():
    """With no explicit checkout, the running code names its own install."""
    assert install_home_marker_path() == Path(openamer_constants.__file__).resolve().parent / ".openamer-home"


def test_platform_default_while_install_knows_its_home_warns_once(tmp_path, monkeypatch, capsys):
    """Requirement 4: the next occurrence is diagnosable instead of silent."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "LocalAppData"))
    logs = tmp_path / "LocalAppData" / "openamer" / "logs"
    logs.mkdir(parents=True)

    _home, checkout = _shipped_layout(tmp_path)
    monkeypatch.setattr(openamer_constants, "_running_checkout_root", lambda: checkout)

    first = get_openamer_home()
    second = get_openamer_home()

    assert first == tmp_path / "LocalAppData" / "openamer", "behavior must not change"
    assert second == first

    stderr = capsys.readouterr().err
    assert stderr.count("[OPENAMER_HOME install-scoped]") == 1, (
        "the warning must be loud, accurate about which home is ours, and one-shot"
    )
    assert str(tmp_path / "openamer-laptop") in stderr

    errors_log = (logs / "errors.log").read_text(encoding="utf-8")
    assert "[OPENAMER_HOME install-scoped]" in errors_log
    assert str(tmp_path / "openamer-laptop") in errors_log


def test_no_warning_when_the_default_is_the_installs_own_home(tmp_path, monkeypatch, capsys):
    """The shipped default layout is not a mismatch, so nothing is logged."""
    local = tmp_path / "LocalAppData"
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    checkout = local / "openamer" / "openamer-agent"
    (checkout / ".git").mkdir(parents=True)
    monkeypatch.setattr(openamer_constants, "_running_checkout_root", lambda: checkout)

    assert get_openamer_home() == local / "openamer"
    assert "[OPENAMER_HOME install-scoped]" not in capsys.readouterr().err


def test_warning_creates_nothing_when_there_is_no_logs_dir(tmp_path, monkeypatch, capsys):
    """A diagnostic may not write new state into a tree that has no logs/."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "LocalAppData"))
    _home, checkout = _shipped_layout(tmp_path)
    monkeypatch.setattr(openamer_constants, "_running_checkout_root", lambda: checkout)

    get_openamer_home()

    assert "[OPENAMER_HOME install-scoped]" in capsys.readouterr().err
    assert not (tmp_path / "LocalAppData" / "openamer" / "errors.log").exists()
    assert not (tmp_path / "LocalAppData" / "openamer" / "logs").exists()

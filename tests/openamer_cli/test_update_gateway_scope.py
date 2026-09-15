"""Install-scoped Windows gateway pause during `openamer update`.

Regression, live 2026-09-15: an `openamer update` run from a throwaway install
force-stopped the gateways of a *different* install and that install's cron
ticker stayed dead until a manual `openamer gateway start`. It lands in the
"unmapped" branch because the updating install's profile scan cannot map the
other install's PID files, and the resume path only replays PIDs the updating
install stopped itself.

Two signals are pinned here, because one is demonstrably not enough:

* **paths** — argv/exe under another install's tree.
* **OPENAMER_HOME** — required for a gateway started from the *shared* uv base
  interpreter (`AppData/Roaming/uv/python/.../python.exe -m openamer_cli.main`),
  which carries no install path at all. That is exactly the process the primary
  install runs, and an earlier revision of this fix still force-killed it.

The rule stays "unprovable is not foreign": a bare scheduled-task argv with an
unreadable environment must remain pausable, or the #50090 fix regresses.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from openamer_cli import main as cli_main

pytestmark = pytest.mark.real_concurrent_gate

FOREIGN_EXE = r"C:\somewhere-else\openamer-agent\venv\Scripts\pythonw.exe"
SHARED_BASE_PY = r"C:\Users\someone\AppData\Roaming\uv\python\cpython-3.11-64\python.exe"
FOREIGN_HOME = r"C:\Users\someone\AppData\Local\openamer-laptop"


def _freeze_psutil(monkeypatch, home=None):
    """Make psutil report only what a test wants (no dependence on host PIDs)."""
    import psutil

    class _Proc:
        def __init__(self, pid):
            raise psutil.NoSuchProcess(pid)

    class _ProcWithHome:
        def __init__(self, pid):
            self.pid = pid

        def exe(self):
            raise psutil.AccessDenied(pid=self.pid)

        def environ(self):
            return {"OPENAMER_HOME": home} if home else {}

    monkeypatch.setattr(psutil, "Process", _ProcWithHome if home else _Proc)


# ---------------------------------------------------------------------------
# the two signals
# ---------------------------------------------------------------------------


def test_bare_scheduled_task_argv_is_not_proof_of_a_foreign_install():
    """Unprovable must stay pausable, or the #50090 fix regresses."""
    roots = cli_main._update_install_roots()
    bare = ["pythonw.exe", "-m", "openamer_cli.main", "gateway", "run"]
    assert cli_main._belongs_to_other_install(bare, roots) is False
    assert cli_main._belongs_to_other_install([], roots) is False


def test_our_own_tree_is_recognised():
    roots = cli_main._update_install_roots()
    mine = os.path.join(roots[0], "venv", "Scripts", "pythonw.exe")
    assert cli_main._belongs_to_other_install([mine], roots) is False


def test_foreign_install_path_is_recognised():
    roots = cli_main._update_install_roots()
    assert cli_main._belongs_to_other_install([FOREIGN_EXE], roots) is True


def test_foreign_venv_is_recognised_even_without_the_brand_name():
    roots = cli_main._update_install_roots()
    fork = r"D:\agents\my-fork\venv\Scripts\python.exe"
    assert cli_main._belongs_to_other_install([fork], roots) is True


def test_shared_base_interpreter_alone_is_not_evidence():
    roots = cli_main._update_install_roots()
    assert cli_main._belongs_to_other_install([SHARED_BASE_PY], roots) is False


def test_shared_base_interpreter_with_foreign_home_is_foreign():
    """The real regression: no path evidence, but the process names its own home."""
    roots = cli_main._update_install_roots()
    got = cli_main._belongs_to_other_install(
        [SHARED_BASE_PY],
        roots,
        home=FOREIGN_HOME,
        our_home=r"C:\Users\damir\AppData\Local\Temp\some-other-home",
    )
    assert got is True


def test_own_profile_subpath_home_is_not_foreign():
    """Profiles of *this* install live under our home and must stay pausable."""
    roots = cli_main._update_install_roots()
    ours = r"C:\Users\damir\AppData\Local\openamer-laptop"
    got = cli_main._belongs_to_other_install(
        [SHARED_BASE_PY], roots, home=os.path.join(ours, "profiles", "work"), our_home=ours
    )
    assert got is False


def test_identical_home_is_not_foreign():
    roots = cli_main._update_install_roots()
    ours = r"C:\Users\damir\AppData\Local\openamer-laptop"
    assert cli_main._belongs_to_other_install([SHARED_BASE_PY], roots, home=ours, our_home=ours) is False


def test_our_own_path_wins_even_with_unreadable_home():
    roots = cli_main._update_install_roots()
    mine = os.path.join(roots[0], "venv", "Scripts", "pythonw.exe")
    assert cli_main._belongs_to_other_install([mine], roots, home=None, our_home=None) is False


# ---------------------------------------------------------------------------
# end-to-end through the pause function
# ---------------------------------------------------------------------------


@patch.object(cli_main, "_is_windows", return_value=True)
def test_pause_leaves_a_foreign_install_gateway_alone(_winp, monkeypatch, capsys):
    import gateway.status as status_mod
    import openamer_cli.gateway as gateway_mod

    argv = [FOREIGN_EXE, "-m", "openamer_cli.main", "gateway", "run"]
    monkeypatch.setattr(gateway_mod, "find_gateway_pids", lambda **_k: [909])
    monkeypatch.setattr(gateway_mod, "find_profile_gateway_processes", lambda **_k: [])
    monkeypatch.setattr(gateway_mod, "_capture_gateway_argv", lambda pid: argv)
    _freeze_psutil(monkeypatch)

    terminated = []
    monkeypatch.setattr(
        status_mod, "terminate_pid", lambda pid, force=False: terminated.append((pid, force))
    )

    token = cli_main._pause_windows_gateways_for_update()

    assert terminated == [], "the other install's gateway must survive"
    assert token is None, "nothing of ours was running, so there is nothing to resume"
    assert "another OpenAmer install" in capsys.readouterr().out


@patch.object(cli_main, "_is_windows", return_value=True)
def test_pause_leaves_shared_interpreter_gateway_with_foreign_home_alone(_winp, monkeypatch):
    """No path evidence at all — only OPENAMER_HOME identifies it (live case)."""
    import gateway.status as status_mod
    import openamer_cli.gateway as gateway_mod

    argv = [SHARED_BASE_PY, "-m", "openamer_cli.main", "gateway", "run"]
    monkeypatch.setattr(gateway_mod, "find_gateway_pids", lambda **_k: [911])
    monkeypatch.setattr(gateway_mod, "find_profile_gateway_processes", lambda **_k: [])
    monkeypatch.setattr(gateway_mod, "_capture_gateway_argv", lambda pid: argv)
    _freeze_psutil(monkeypatch, home=FOREIGN_HOME)
    monkeypatch.setenv("OPENAMER_HOME", r"C:\Users\damir\AppData\Local\Temp\some-other-home")

    terminated = []
    monkeypatch.setattr(
        status_mod, "terminate_pid", lambda pid, force=False: terminated.append((pid, force))
    )

    token = cli_main._pause_windows_gateways_for_update()

    assert terminated == [], "a gateway named by its own HOME must survive"
    assert token is None


@patch.object(cli_main, "_is_windows", return_value=True)
def test_pause_still_stops_a_gateway_from_our_own_install(_winp, monkeypatch):
    import gateway.status as status_mod
    import openamer_cli.gateway as gateway_mod

    argv = [
        os.path.join(cli_main._update_install_roots()[0], "venv", "Scripts", "pythonw.exe"),
        "-m",
        "openamer_cli.main",
        "gateway",
        "run",
    ]
    monkeypatch.setattr(gateway_mod, "find_gateway_pids", lambda **_k: [910])
    monkeypatch.setattr(gateway_mod, "find_profile_gateway_processes", lambda **_k: [])
    monkeypatch.setattr(gateway_mod, "_capture_gateway_argv", lambda pid: argv)
    monkeypatch.setattr(gateway_mod, "_get_restart_drain_timeout", lambda: 0.1)
    monkeypatch.setattr(cli_main, "_wait_for_windows_update_gateway_exit", lambda pids, **_: set())
    _freeze_psutil(monkeypatch)

    terminated = []
    monkeypatch.setattr(
        status_mod, "terminate_pid", lambda pid, force=False: terminated.append((pid, force))
    )

    token = cli_main._pause_windows_gateways_for_update()

    assert terminated == [(910, True)]
    assert token is not None
    assert token["unmapped_pids"] == [910]
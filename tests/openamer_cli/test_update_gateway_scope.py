"""Install-scoped Windows gateway pause during `openamer update`.

Regression, live 2026-09-15: an `openamer update --force` run from a throwaway
install force-stopped the gateway of a *different* install tree. It lands in the
"unmapped" branch because the updating install's profile scan cannot map the
other install's PID files, and that other install's cron ticker then stayed dead
until a manual `openamer gateway start` — a second install updating itself took
down the primary agent.

`_pause_windows_gateways_for_update` now stops only gateways it can prove belong
to the install being updated. The rule is deliberately **"unprovable is not
foreign"**: a bare scheduled-task argv (`pythonw.exe -m openamer_cli.main
gateway run`) names no location, and those gateways must keep being paused for
the update to proceed — that behaviour is the #50090 fix and is pinned below.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from openamer_cli import main as cli_main

pytestmark = pytest.mark.real_concurrent_gate

FOREIGN = r"C:\somewhere-else\openamer-agent\venv\Scripts\pythonw.exe"


def _freeze_psutil_exe(monkeypatch):
    """Make the exe lookup unavailable so only argv decides.

    Keeps the outcome independent of whatever PIDs happen to exist on the host
    running the suite.
    """
    import psutil

    class _Gone:
        def __init__(self, pid):
            raise psutil.NoSuchProcess(pid)

    monkeypatch.setattr(psutil, "Process", _Gone)


# ---------------------------------------------------------------------------
# the scope rule itself
# ---------------------------------------------------------------------------


def test_bare_scheduled_task_argv_is_not_proof_of_a_foreign_install():
    """Unprovable must stay pausable, or the #50090 fix regresses."""
    roots = cli_main._update_install_roots()
    bare = ["pythonw.exe", "-m", "openamer_cli.main", "gateway", "run"]
    assert cli_main._paths_belong_to_other_install(bare, roots) is False
    assert cli_main._paths_belong_to_other_install([], roots) is False


def test_our_own_tree_is_recognised():
    roots = cli_main._update_install_roots()
    mine = os.path.join(roots[0], "venv", "Scripts", "pythonw.exe")
    assert cli_main._paths_belong_to_other_install([mine], roots) is False


def test_foreign_install_is_recognised():
    roots = cli_main._update_install_roots()
    assert cli_main._paths_belong_to_other_install([FOREIGN], roots) is True


def test_foreign_venv_is_recognised_even_without_the_brand_name():
    roots = cli_main._update_install_roots()
    fork = r"D:\agents\my-fork\venv\Scripts\python.exe"
    assert cli_main._paths_belong_to_other_install([fork], roots) is True


def test_shared_base_interpreter_is_not_evidence():
    """Every venv on the box sits on the same uv/cpython — that proves nothing."""
    roots = cli_main._update_install_roots()
    shared = r"C:\Users\someone\AppData\Roaming\uv\python\cpython-3.11-64\python.exe"
    assert cli_main._paths_belong_to_other_install([shared], roots) is False


def test_path_normalization_ignores_case_and_trailing_separator():
    roots = cli_main._update_install_roots()
    mine = os.path.join(roots[0], "venv", "Scripts", "pythonw.exe")
    assert cli_main._paths_belong_to_other_install([mine.upper()], roots) is False


# ---------------------------------------------------------------------------
# end-to-end through the pause function
# ---------------------------------------------------------------------------


@patch.object(cli_main, "_is_windows", return_value=True)
def test_pause_leaves_a_foreign_install_gateway_alone(_winp, monkeypatch, capsys):
    import gateway.status as status_mod
    import openamer_cli.gateway as gateway_mod

    argv = [FOREIGN, "-m", "openamer_cli.main", "gateway", "run"]
    monkeypatch.setattr(gateway_mod, "find_gateway_pids", lambda **_k: [909])
    monkeypatch.setattr(gateway_mod, "find_profile_gateway_processes", lambda **_k: [])
    monkeypatch.setattr(gateway_mod, "_capture_gateway_argv", lambda pid: argv)
    _freeze_psutil_exe(monkeypatch)

    terminated = []
    monkeypatch.setattr(
        status_mod,
        "terminate_pid",
        lambda pid, force=False: terminated.append((pid, force)),
    )

    token = cli_main._pause_windows_gateways_for_update()

    assert terminated == [], "the other install's gateway must survive"
    assert token is None, "nothing of ours was running, so there is nothing to resume"
    assert "another OpenAmer install" in capsys.readouterr().out


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
    monkeypatch.setattr(
        cli_main, "_wait_for_windows_update_gateway_exit", lambda pids, **_: set()
    )
    _freeze_psutil_exe(monkeypatch)

    terminated = []
    monkeypatch.setattr(
        status_mod,
        "terminate_pid",
        lambda pid, force=False: terminated.append((pid, force)),
    )

    token = cli_main._pause_windows_gateways_for_update()

    assert terminated == [(910, True)]
    assert token is not None
    assert token["unmapped_pids"] == [910]
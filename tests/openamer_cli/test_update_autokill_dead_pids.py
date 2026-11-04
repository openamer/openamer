"""Regression test: `--auto-kill` must not report already-dead PIDs as failures.

Measured on a live Windows install (2026-11-04): `openamer update --yes --force`
reported

    ⟲ --auto-kill: terminating 12 blocking background process(es)…
        ✓ stopped PID 9784
        ✓ stopped PID 16036
        ✓ stopped PID 16112
        ✗ could not stop PID 3852: FEHLER: Der Prozess "3852" wurde nicht gefunden.
        ... (7 more identical "not found" lines)

Nine of twelve PIDs were ALREADY DEAD when taskkill ran — they had exited
between the holder detection and the kill. Windows' taskkill reports that as a
non-zero exit with a "process not found" message, so the helper filed them as
FAILURES. The user then reads nine red "could not stop" lines for processes
that are long gone, which looks like a broken updater rather than the
successful cleanup it actually was.

A PID that no longer exists is not a failure — the goal ("that process must
not be running") is already satisfied. The helper must distinguish
"already gone" from "still alive and could not be killed".
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from openamer_cli import main as cli_main


# The exact German taskkill message for a PID that does not exist, plus the
# English variants taskkill uses on other Windows locales / for images.
_NOT_FOUND_MARKERS = (
    "wurde nicht gefunden",
    "not found",
    "no such process",
    "nicht gefunden",
)


def _taskkill_result(pid: int, *, returncode: int, stderr: str = "") -> SimpleNamespace:
    return SimpleNamespace(returncode=returncode, stdout="", stderr=stderr)


@patch.object(cli_main, "_is_windows", return_value=True)
def test_auto_kill_treats_already_dead_pids_as_gone(_winp, monkeypatch):
    """A PID that no longer exists is neither killed nor failed — it is gone."""
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        pid = cmd[2]
        if pid == "222":
            return _taskkill_result(
                222,
                returncode=128,
                stderr='FEHLER: Der Prozess "222" wurde nicht gefunden.',
            )
        return _taskkill_result(int(pid), returncode=0)

    monkeypatch.setattr(cli_main.subprocess, "run", fake_run)
    killed, failed = cli_main._auto_kill_blocking_processes([111, 222])

    assert killed == [111]
    assert failed == [], (
        "an already-dead PID must not be reported as a kill failure — "
        f"got {failed!r}"
    )
    assert calls == [
        ["taskkill", "/PID", "111", "/F"],
        ["taskkill", "/PID", "222", "/F"],
    ]


@patch.object(cli_main, "_is_windows", return_value=True)
def test_auto_kill_still_reports_real_failures(_winp, monkeypatch):
    """A process that is alive but could NOT be killed is still a failure.

    "Access is denied" must keep being surfaced — that one genuinely blocks
    the update.
    """

    def fake_run(cmd, **kwargs):
        if cmd[2] == "222":
            return _taskkill_result(
                222, returncode=1, stderr="FEHLER: Zugriff verweigert (Access is denied)."
            )
        return _taskkill_result(int(cmd[2]), returncode=0)

    monkeypatch.setattr(cli_main.subprocess, "run", fake_run)
    killed, failed = cli_main._auto_kill_blocking_processes([111, 222])

    assert killed == [111]
    assert len(failed) == 1
    assert failed[0][0] == 222
    assert "denied" in failed[0][1].lower() or "verweigert" in failed[0][1].lower()


@patch.object(cli_main, "_is_windows", return_value=True)
def test_auto_kill_ignores_empty_error_output_from_dead_pid(_winp, monkeypatch):
    """Some taskkill versions report a dead PID with an EMPTY stderr.

    The PID being absent is authoritative: taskkill's own exit code 128 means
    "no such process". So a non-zero exit whose stderr carries no
    "not found" wording but whose exit code is the documented 128 (or the
    PID simply no longer exists) must not be reported as a failure either.
    """
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        pid = int(cmd[2])
        if pid == 222:
            return _taskkill_result(222, returncode=128, stderr="")
        return _taskkill_result(pid, returncode=0)

    monkeypatch.setattr(cli_main.subprocess, "run", fake_run)
    killed, failed = cli_main._auto_kill_blocking_processes([111, 222])

    assert killed == [111]
    assert failed == []

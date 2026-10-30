"""Tests for ``scripts/pytest_live_guard.py`` (the daemon-launch refusal).

The guard exists because a test run once launched real
``openamer … gateway run --replace`` processes: each one stopped the gateway
running on the machine and was orphaned when the test process exited. These
tests pin WHICH argv shapes count as a daemon, so the guard can neither miss a
lifecycle command nor block a read-only one.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import pytest_live_guard as guard  # noqa: E402


@pytest.mark.parametrize(
    "argv",
    [
        [sys.executable, "-m", "openamer_cli.main", "gateway", "run"],
        [sys.executable, "-m", "openamer_cli.main", "gateway", "run", "--replace"],
        ["openamer.exe", "gateway", "start"],
        ["openamer.exe", "gateway", "stop"],
        ["openamer.exe", "gateway", "restart"],
        ["C:/Users/x/AppData/Local/openamer-laptop/openamer-agent/venv/Scripts/python.exe",
         "-m", "openamer_cli.main", "gateway", "run", "--replace"],
        [sys.executable, "scripts/dashboard-server.py"],
        [sys.executable, "scripts/remote-web.py", "--port", "8901"],
        [sys.executable, "scripts/training/tool_server.py"],
        ["openamer-setup.exe", "--update", "--branch", "main"],
    ],
)
def test_daemon_launches_are_refused(argv):
    assert guard.is_openamer_daemon_launch(argv) is True


@pytest.mark.parametrize(
    "argv",
    [
        [sys.executable, "-m", "openamer_cli.main", "--version"],
        [sys.executable, "-m", "openamer_cli.main", "gateway", "status"],
        [sys.executable, "-m", "openamer_cli.main", "tools"],
        ["openamer.exe", "config", "get", "model"],
        ["git", "status", "--porcelain"],
        ["node", "scripts/build.js"],
        ["python", "scripts/run_tests_parallel.py", "tests/"],
        # A daemon name without an OpenAmer context is somebody else's script.
        ["python", "/opt/other/tool_server.py"],
        # Regression (CI, slice 11/12): the words "gateway run" are an ARGUMENT
        # to the docker tini wrapper, and the path only carries the checkout
        # directory name. Three real false refusals before the anchor existed.
        ["sh", "/home/runner/work/openamer/openamer/docker/tini-shim.sh", "-g", "--", "gateway", "run"],
        ["sh", "docker/tini-shim.sh", "-g", "gateway", "run"],
        ["sh", "/tmp/pytest-of-runner/pytest-1/test_x0/fake-wrapper", "gateway", "run"],
        # A python script that merely has a daemon-ish name elsewhere on disk.
        ["python", "/tmp/pytest-of-runner/x/tool_server.py"],
        # Regression (CI, Docker image build): an OpenAmer entry point with NO
        # sub-command — `target` is empty, not None, and indexing it crashed
        # inside Popen instead of answering "not a daemon".
        ["openamer"],
        ["openamer.exe"],
        [sys.executable, "-m", "openamer_cli.main"],
        ["C:/x/openamer-agent/venv/Scripts/openamer.exe"],
    ],
)
def test_read_only_and_foreign_commands_pass(argv):
    assert guard.is_openamer_daemon_launch(argv) is False


def test_string_commands_are_parsed():
    assert guard.is_openamer_daemon_launch("openamer gateway run --replace") is True
    assert guard.is_openamer_daemon_launch("openamer gateway status") is False


def test_guarded_popen_refuses_and_records(monkeypatch):
    monkeypatch.delenv("OPENAMER_PYTEST_ALLOW_DAEMONS", raising=False)
    monkeypatch.setattr(subprocess, "Popen", guard._GuardedPopen)
    guard.refusals.clear()

    with pytest.raises(guard.LiveGuardRefusal) as excinfo:
        subprocess.Popen([sys.executable, "-m", "openamer_cli.main", "gateway", "run"])

    assert "refused to start an OpenAmer daemon" in str(excinfo.value)
    assert guard.refusals, "a refusal must be recorded for the terminal summary"
    assert "gateway run" in guard.refusals[0][1]


def test_guarded_popen_allows_read_only(monkeypatch):
    monkeypatch.setattr(subprocess, "Popen", guard._GuardedPopen)
    guard.refusals.clear()

    completed = subprocess.run(
        [sys.executable, "-c", "print('ok')"], capture_output=True, text=True
    )

    assert completed.returncode == 0
    assert completed.stdout.strip() == "ok"
    assert guard.refusals == []


def test_escape_hatch_disables_the_refusal(monkeypatch):
    monkeypatch.setenv("OPENAMER_PYTEST_ALLOW_DAEMONS", "1")
    monkeypatch.setattr(subprocess, "Popen", guard._GuardedPopen)
    guard.refusals.clear()

    completed = subprocess.run(
        [sys.executable, "-c", "print('spawned')"], capture_output=True, text=True
    )

    assert completed.stdout.strip() == "spawned"
    assert guard.refusals == []

"""Regression tests for scripts/gpu-worker-watchdog.py.

A real bug (found live 2026-09-11): ``training_active()`` could never return
True on the reference setup, so the watchdog restarted the 4B GPU worker into an
active finetune and both contended for the 8 GB card. Two independent causes:

1. The primary probe parsed ``schtasks /fo LIST /v`` and matched the localized
   German status ``Wird ausgeführt``. That text arrives from the GPU PC as raw
   cp850 bytes (0x81 for ``ü``); with ``encoding="utf-8", errors="replace"`` the
   umlaut became U+FFFD, so the UTF-8 substring match never fired. Fix: read the
   invariant English enum from ``Get-ScheduledTask .State`` instead.

2. The fallback probe embedded escaped ``\\"...\\"`` quotes inside the remote
   PowerShell command; those do not survive cmd.exe on the far side of ssh
   (rc=255, "Das System kann den angegebenen Pfad nicht finden."), so the branch
   was dead. Fix: emit the value with ``Write-Output`` and parse the last
   ``a|b`` line. Also ``$age.ToString()`` is locale-formatted (German decimal
   comma), which made ``float(age_s)`` raise — normalize the separator.

Hermetic: no real SSH. The boundary (``_ssh``) is monkeypatched.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "gpu-worker-watchdog.py"


def _load():
    spec = importlib.util.spec_from_file_location("gpu_worker_watchdog", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["gpu_worker_watchdog"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def wd():
    return _load()


def _scripted(monkeypatch, wd, state=None, log=None):
    """Route _ssh by command: task-state probe vs. train-log probe."""
    def fake(cmd, timeout=60):
        if "Get-ScheduledTask" in cmd:
            return (0, state) if state is not None else (0, "")
        return (0, log) if log is not None else (0, "")
    monkeypatch.setattr(wd, "_ssh", fake)


# --- primary signal: Get-ScheduledTask .State -----------------------------

def test_running_task_means_training_active(monkeypatch, wd):
    _scripted(monkeypatch, wd, state="Running")
    assert wd.training_active() is True


def test_state_match_is_case_insensitive(monkeypatch, wd):
    _scripted(monkeypatch, wd, state="RUNNING")
    assert wd.training_active() is True


def test_ready_task_with_stale_log_is_not_active(monkeypatch, wd):
    _scripted(monkeypatch, wd, state="Ready", log="99,5|False")
    assert wd.training_active() is False


# --- fallback signal: in-flight train log ---------------------------------

def test_fresh_inflight_log_is_active(monkeypatch, wd):
    # German decimal comma — must still parse.
    _scripted(monkeypatch, wd, state="Ready", log="3,4|False")
    assert wd.training_active() is True


def test_fresh_log_with_exit_code_is_not_active(monkeypatch, wd):
    _scripted(monkeypatch, wd, state="Ready", log="0,2|True")
    assert wd.training_active() is False


def test_dot_separator_also_parses(monkeypatch, wd):
    _scripted(monkeypatch, wd, state="Ready", log="5.0|False")
    assert wd.training_active() is True


def test_fallback_parses_last_pipe_line(monkeypatch, wd):
    # OpenSSH banners / extra output may precede the value line.
    _scripted(monkeypatch, wd, state="Ready", log="noise\n2,0|False")
    assert wd.training_active() is True


def test_garbage_log_is_not_active(monkeypatch, wd):
    _scripted(monkeypatch, wd, state="Ready", log="not a result")
    assert wd.training_active() is False


def test_ssh_failure_is_not_active(monkeypatch, wd):
    monkeypatch.setattr(wd, "_ssh", lambda cmd, timeout=60: (255, "ssh failed"))
    assert wd.training_active() is False


# --- the specific old failure mode is gone --------------------------------

def test_localized_cp850_status_text_is_not_relied_on(monkeypatch, wd):
    """The old code matched 'wird ausgeführt' in schtasks output; that byte
    arrives as U+FFFD over utf-8/replace. The new probe must not depend on it."""
    mojibake = "Status: Wird ausgef\ufffdhrt"  # cp850 0x81 decoded as utf-8
    def fake(cmd, timeout=60):
        # Only localized schtasks text available -> no evidence of training.
        return (0, mojibake)
    monkeypatch.setattr(wd, "_ssh", fake)
    assert wd.training_active() is False


def test_probe_uses_invariant_english_state_field(monkeypatch, wd):
    seen = {}
    def fake(cmd, timeout=60):
        seen.setdefault("cmds", []).append(cmd)
        return (0, "Ready")
    monkeypatch.setattr(wd, "_ssh", fake)
    wd.training_active()
    assert any("Get-ScheduledTask" in c for c in seen["cmds"])


# --- _ssh contract --------------------------------------------------------

def test_ssh_folds_stderr_back_only_when_stdout_empty(monkeypatch, wd):
    import subprocess

    def run_ok(*a, **k):
        return subprocess.CompletedProcess(
            a[0], 0, stdout="READY", stderr="** post-quantum banner **")

    def run_fail(*a, **k):
        return subprocess.CompletedProcess(
            a[0], 1, stdout="", stderr="real error")

    monkeypatch.setattr(wd.subprocess, "run", run_ok)
    rc, out = wd._ssh("x")
    assert rc == 0 and out == "READY"  # banner on stderr is not folded in

    monkeypatch.setattr(wd.subprocess, "run", run_fail)
    rc, out = wd._ssh("x")
    assert rc == 1 and out == "real error"


def test_ssh_requires_explicit_utf8_encoding(monkeypatch, wd):
    import subprocess

    def run(*a, **k):
        assert k.get("encoding") == "utf-8", "must not rely on locale default"
        assert k.get("errors") == "replace"
        return subprocess.CompletedProcess(a[0], 0, stdout="ok", stderr="")

    monkeypatch.setattr(wd.subprocess, "run", run)
    assert wd._ssh("x") == (0, "ok")


# --- the module still holds together --------------------------------------

def test_module_exposes_expected_api(wd):
    for name in ("training_active", "probe", "restart", "main", "_ssh"):
        assert callable(getattr(wd, name))

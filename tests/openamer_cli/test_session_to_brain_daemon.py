"""Tests for openamer_cli/session_to_brain_daemon.py.

Regression guard: on Windows, ``tasklist`` may emit output in a non-UTF-8
codepage (bytes >= 0x80). The old code used ``text=True`` -> UnicodeDecodeError
-> ``spawn()`` raised before it could start the daemon. The fix decodes the
bytes with errors="replace" and guards empty output, so spawn() is robust.
"""
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))

from openamer_cli import session_to_brain_daemon as M  # noqa: E402


class _FakeProc:
    def __init__(self, pid=999):
        self.pid = pid


def _patch_nt_environment(monkeypatch, tmp_path, tasklist_stdout, stale_pid="99999"):
    """Force the Windows branch, point spaw at tmp, fake tasklist+Popen."""
    monkeypatch.setattr(M.os, "name", "nt")
    monkeypatch.setattr(M, "_pid_file", lambda: tmp_path / "session_to_brain.pid")
    (tmp_path / "session_to_brain.pid").write_text(stale_pid)
    monkeypatch.setattr(
        M.subprocess, "run",
        lambda *a, **k: subprocess.CompletedProcess(
            ["tasklist"], 0, stdout=tasklist_stdout, stderr=b""))
    started = {}
    monkeypatch.setattr(M.subprocess, "Popen",
                        lambda *a, **k: started.setdefault("p", _FakeProc(4242)))
    return started


def test_spawn_does_not_crash_on_non_utf8_tasklist(tmp_path, monkeypatch):
    # tasklist returns raw bytes with an invalid-UTF-8 byte (0x81) — this used
    # to throw UnicodeDecodeError at decode and crash spawn(). It must start.
    raw = b"  INFORMATION: No tasks\x81\n"
    out = _patch_nt_environment(monkeypatch, tmp_path, raw)
    # write_text is stubbed out in the real code via pid_file.write_text; our
    # fake Popen returns a proc; monkeypatch pid_file writes through to tmp
    monkeypatch.setattr(Path, "write_text",
                        lambda self, s, *a, **k: None)
    M.spawn()  # must not raise


def test_decode_errors_replace_never_raises():
    raw = b"\x81abcdef"
    assert "abc" in raw.decode("utf-8", errors="replace")


def test_already_running_early_returns(tmp_path, monkeypatch):
    # A live pid -> tasklist finds it -> spawn() returns without starting new.
    old = "4242"
    started = {}
    monkeypatch.setattr(M.os, "name", "nt")
    monkeypatch.setattr(M, "_pid_file", lambda: tmp_path / "session_to_brain.pid")
    (tmp_path / "session_to_brain.pid").write_text(old)
    monkeypatch.setattr(
        M.subprocess, "run",
        lambda *a, **k: subprocess.CompletedProcess(
            ["tasklist"], 0, stdout=f"  python.exe  {old}\r\n".encode(), stderr=b""))
    monkeypatch.setattr(M.subprocess, "Popen",
                        lambda *a, **k: started.setdefault("p", True))
    M.spawn()
    assert "p" not in started   # no new daemon spawned
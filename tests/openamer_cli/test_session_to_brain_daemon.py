"""Tests for openamer_cli/session_to_brain_daemon.py.

The spawn guard used to read a pid file that ``spawn()`` wrote itself and then
ask ``tasklist`` whether that pid was alive. On Windows ``sys.executable`` is a
uv trampoline that exits as soon as the real interpreter is up, so the recorded
pid was dead on the very next call: EVERY ``openamer`` invocation started
another watcher. The accumulated watchers each run ``openamer a2a brain
collect`` from the install venv, keeping ``venv/Scripts/openamer.exe`` locked so
the desktop's 15 s update hand-off never saw a free window and aborted every
time (measured 2026-10-12: 245 watchers, shim permanently locked; after the fix:
exactly one).

The guard is now an OS-level lock probe against the SAME lock the ``--watch``
loop holds, anchored to a HOME-independent path (a ``$OPENAMER_HOME``-scoped
lock let two watchers each "win" their own singleton). These tests pin that
contract.
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))

from openamer_cli import session_to_brain_daemon as M  # noqa: E402


class _FakeProc:
    def __init__(self, pid=999):
        self.pid = pid


def test_watcher_lock_path_is_home_independent(monkeypatch):
    """The lock must NOT move when OPENAMER_HOME changes.

    A HOME-scoped lock is exactly what let two watchers each win their own
    singleton and both run ``brain collect`` forever.
    """
    monkeypatch.setenv("OPENAMER_HOME", r"C:\one\home")
    first = M._watcher_lock_path()

    monkeypatch.setenv("OPENAMER_HOME", r"C:\another\home")
    second = M._watcher_lock_path()

    assert first == second
    assert first.name == "openamer-session-to-brain-watch.lock"


def test_watcher_running_false_when_lock_free(tmp_path, monkeypatch):
    monkeypatch.setattr(M, "_watcher_lock_path", lambda: tmp_path / "watch.lock")
    assert M._watcher_running() is False


def test_watcher_running_true_while_lock_held(tmp_path, monkeypatch):
    """Holding the lock (as the --watch loop does) must report 'running'.

    This is the behaviour the old pid-file check could not deliver.
    """
    import os

    lock = tmp_path / "watch.lock"
    monkeypatch.setattr(M, "_watcher_lock_path", lambda: lock)

    fh = open(lock, "a+", encoding="utf-8")
    try:
        if os.name == "nt":
            import msvcrt

            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

        assert M._watcher_running() is True
    finally:
        fh.close()

    # Released -> free again.
    assert M._watcher_running() is False


def test_spawn_skips_when_watcher_running(tmp_path, monkeypatch):
    """No new daemon when a watcher already owns the lock."""
    monkeypatch.setattr(M, "_pid_file", lambda: tmp_path / "session_to_brain.pid")
    monkeypatch.setattr(M, "_watcher_running", lambda: True)

    started = {}
    monkeypatch.setattr(
        M.subprocess, "Popen", lambda *a, **k: started.setdefault("p", True)
    )

    M.spawn()

    assert "p" not in started


def test_spawn_starts_when_no_watcher(tmp_path, monkeypatch):
    """With no watcher holding the lock, spawn() starts exactly one daemon."""
    monkeypatch.setattr(M, "_pid_file", lambda: tmp_path / "session_to_brain.pid")
    monkeypatch.setattr(M, "_watcher_running", lambda: False)
    monkeypatch.setattr(M, "_acquire_spawn_lock", lambda: tmp_path / "spawn.lock")
    monkeypatch.setattr(Path, "write_text", lambda self, s, *a, **k: None)

    started = {}
    monkeypatch.setattr(
        M.subprocess,
        "Popen",
        lambda *a, **k: started.setdefault("p", _FakeProc(4242)),
    )

    M.spawn()

    # The repo ships scripts/session_to_brain.py, so the script check passes and
    # one Popen happens.
    assert started.get("p") is not None

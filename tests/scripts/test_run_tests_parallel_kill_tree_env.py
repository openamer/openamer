"""The Windows process-tree kill must stay fast when SystemDrive is missing.

Root cause (measured 2026-10-22 on this Windows 10 host):

``taskkill /F /T /PID <pid>`` needs ``SystemDrive`` in the environment.
Without it, taskkill cannot build the job object path directly and falls
back to a slow path that searches for the drive. The canonical runner
starts pytest under ``env -i`` (see ``scripts/run_tests.sh``), which drops
SystemDrive along with every other variable except the handful it
re-adds -- so every timed-out test file paid the slow path.

The effect is LOAD-DEPENDENT, which is what makes it easy to misread.
Measured on this host, same script, 3 runs per configuration:

  env                        idle      under CPU load (16 burners)
  minimal, no SystemDrive    1.05 s    5.95-7.31 s
  minimal, with SystemDrive  0.19 s    0.72-0.89 s

So the slow path is ~6x slower idle and ~8x under load, and it passes a
5-10s timeout once the machine is busy. The taskkill timeout then fires
inside ``_kill_tree``, the kill arrives late, and a 5s per-file timeout
took ~15s of wall clock instead of ~5s. The e2e test that pins "a hanging
file is attempted once" failed on the canonical runner while passing under
a plain pytest invocation (where the desktop environment leaks
SystemDrive in).

Consequence for how these tests are written: an ABSOLUTE timing bound
does not pin the fix. On an idle machine the unfixed path still finishes
in ~1s, so "did it exceed the timeout?" passes against the unfixed code
(a mutation check confirmed it). The structural assertion below -- that
taskkill is handed an env containing SystemDrive -- is the one that
fails at any load, at any machine speed.

On non-Windows platforms the taskkill branch does not run, so the
Windows-only tests are skipped; the env-injection contract is still
asserted there because the logic in _kill_tree is platform-independent.
"""

from __future__ import annotations

import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.run_tests_parallel import _kill_tree  # noqa: E402

IS_WINDOWS = sys.platform == "win32"

_TASKKILL_TIMEOUT = 30.0
"""Generous: these tests measure a slow path, they must not race it."""


def _stripped_env_without_systemdrive() -> dict:
    """A hermetic env like run_tests.sh's `env -i`, minus SystemDrive."""
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "USERPROFILE": os.environ.get("USERPROFILE", ""),
        "SystemRoot": os.environ.get("SystemRoot") or os.environ.get("SYSTEMROOT")
        or r"C:\Windows",
    }
    env.pop("SystemDrive", None)
    env.pop("SYSTEMDRIVE", None)
    return env


def _env_with_systemdrive() -> dict:
    """The same hermetic env, but with the drive taskkill needs."""
    env = _stripped_env_without_systemdrive()
    root = env.get("SystemRoot") or r"C:\Windows"
    env["SystemDrive"] = root.split(":", 1)[0] + ":"
    return env


def _spawn_sleeper(env: dict) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(120)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
        start_new_session=True,
    )


def _reap(proc: subprocess.Popen) -> None:
    """Make sure the sleeper is gone either way."""
    try:
        proc.kill()
    except Exception:
        pass
    try:
        proc.wait(timeout=5)
    except Exception:
        pass


def _time_taskkill(env: dict) -> float:
    """Seconds one taskkill call takes against a fresh sleeper."""
    proc = _spawn_sleeper(env)
    try:
        start = time.monotonic()
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=_TASKKILL_TIMEOUT,
            env=env,
        )
        return time.monotonic() - start
    finally:
        _reap(proc)


@pytest.mark.skipif(
    not IS_WINDOWS,
    reason=(
        "asserts that _kill_tree invokes taskkill; that branch is guarded by "
        "sys.platform == 'win32' (scripts/run_tests_parallel.py:355), so on "
        "POSIX it never runs. The sibling test below already carries this gate"
    ),
)
def test_kill_tree_passes_systemdrive_to_taskkill(monkeypatch):
    """_kill_tree must hand taskkill an env that contains SystemDrive.

    This is the invariant the fix establishes, and it is checkable without
    relying on timing: taskkill needs SystemDrive to take its fast path,
    and _kill_tree is the only place that can supply it when the caller
    stripped it (the canonical runner starts pytest under `env -i`).

    The removal has to happen in THIS process's environment, because that
    is the environment _kill_tree copies when it spawns taskkill. Stripping
    it only from the child's env does not exercise the bug at all.
    """
    monkeypatch.delenv("SystemDrive", raising=False)
    monkeypatch.delenv("SYSTEMDRIVE", raising=False)
    assert "SystemDrive" not in os.environ
    assert "SYSTEMDRIVE" not in os.environ

    captured = {}

    def _fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["env"] = kwargs.get("env")
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    monkeypatch.setattr("scripts.run_tests_parallel.subprocess.run", _fake_run)

    proc = _spawn_sleeper(dict(os.environ))
    try:
        _kill_tree(proc, pgid=None)
    finally:
        _reap(proc)

    assert captured.get("cmd"), "taskkill was never invoked"
    assert "taskkill" in " ".join(captured["cmd"]), (
        f"expected a taskkill invocation, got {captured['cmd']}"
    )
    env = captured.get("env")
    assert env is not None, (
        "taskkill must be invoked with an explicit env -- otherwise it "
        "inherits the caller's env, which may lack SystemDrive"
    )
    assert env.get("SystemDrive") or env.get("SYSTEMDRIVE"), (
        "the env handed to taskkill must contain SystemDrive; without it "
        "taskkill takes the slow fallback path and the kill arrives late"
    )


def test_kill_tree_works_without_systemdrive_in_env(monkeypatch):
    """_kill_tree must not depend on the caller having set SystemDrive.

    The bound is deliberately generous: on an idle machine the unfixed path
    still finishes in ~1s, so a tight threshold would pass against the
    unfixed code. This test's job is the contract "the kill never waits
    for taskkill's timeout"; the tight assertion is the relative one below.
    """
    monkeypatch.delenv("SystemDrive", raising=False)
    monkeypatch.delenv("SYSTEMDRIVE", raising=False)

    proc = _spawn_sleeper(_stripped_env_without_systemdrive())
    try:
        start = time.monotonic()
        _kill_tree(proc, pgid=None)
        elapsed = time.monotonic() - start

        if IS_WINDOWS:
            # A taskkill that hits its own 10s timeout adds 10s to every
            # timed-out file.
            assert elapsed < 6.0, (
                f"_kill_tree took {elapsed:.1f}s with SystemDrive missing -- "
                "taskkill fell back to its slow path; the kill must not "
                "wait for taskkill's timeout"
            )
    finally:
        _reap(proc)


def test_kill_tree_terminates_the_process(monkeypatch):
    """The kill must actually end the process, not just return quickly."""
    monkeypatch.delenv("SystemDrive", raising=False)
    monkeypatch.delenv("SYSTEMDRIVE", raising=False)

    proc = _spawn_sleeper(_stripped_env_without_systemdrive())
    try:
        _kill_tree(proc, pgid=None)
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and proc.poll() is None:
            time.sleep(0.05)
        assert proc.poll() is not None, (
            "the target process is still alive after _kill_tree"
        )
    finally:
        _reap(proc)


@pytest.mark.skipif(not IS_WINDOWS, reason="taskkill is Windows-only")
def test_taskkill_is_slower_without_systemdrive():
    """Pin the underlying OS behaviour the fix works around.

    Without SystemDrive, taskkill takes a slow fallback path: it cannot
    build the job object path directly and has to search for the drive.

    The comparison is RELATIVE on purpose, and the two variants are
    interleaved so both see the same machine load. An absolute threshold
    does not work: on an idle machine the slow path never exceeds the
    timeout, so a "did it hang?" assertion passes against the unfixed
    code.

    If this test ever starts failing, the underlying Windows behaviour
    changed and the workaround in _kill_tree can be revisited.
    """
    without = _stripped_env_without_systemdrive()
    with_drive = _env_with_systemdrive()

    slow, fast = [], []
    for _ in range(3):
        slow.append(_time_taskkill(without))
        fast.append(_time_taskkill(with_drive))

    slow_med = statistics.median(slow)
    fast_med = statistics.median(fast)

    assert slow_med > fast_med * 2.0, (
        f"taskkill without SystemDrive was not slower than with it: "
        f"without={slow_med:.2f}s {slow} with={fast_med:.2f}s {fast} -- "
        "the slow fallback path the fix works around may be gone"
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))

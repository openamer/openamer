"""A detached child must not leave a zombie slot behind (ResourceWarning).

Measured 2026-11-03: ``gateway_windows._spawn_detached()`` spawned the
Windows gateway with a plain ``subprocess.Popen`` and dropped the object
without ever calling ``wait()``. CPython's ``Popen.__del__`` then emitted

    ResourceWarning: subprocess <pid> is still running

at an arbitrary later garbage collection. Because the warning fires when the
object is collected — not where it was created — it surfaced as a failure of
an unrelated test (``test_git_calls_prefix_the_windows_atomic_append_workaround``
in ``tests/openamer_cli/test_update_autostash.py``) that happened to be the
one allocating when the GC ran.

Under ``pytest -W error`` that is a hard failure, and it made
``tests/openamer_cli/test_cmd_update.py`` red on the unchanged baseline too.
"""

from __future__ import annotations

import subprocess
import sys
import warnings
from pathlib import Path

import pytest

from openamer_cli._subprocess_compat import spawn_detached


def _spawn_a_child() -> "subprocess.Popen":
    """Spawn a short-lived child through the detached helper."""
    return spawn_detached(
        [sys.executable, "-c", "import time; time.sleep(0.05)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
    )


def test_spawn_detached_does_not_warn_about_a_running_child():
    """Dropping the Popen object must not produce a ResourceWarning."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        proc = _spawn_a_child()
        del proc
        # Force the collection that would trigger Popen.__del__.
        import gc

        gc.collect()

    resource_warnings = [w for w in caught if issubclass(w.category, ResourceWarning)]
    assert not resource_warnings, (
        "detached child leaked a zombie slot: "
        f"{[str(w.message) for w in resource_warnings]}"
    )


def test_spawn_detached_reports_a_returncode():
    """The helper marks the child as reaped, so returncode is not None."""
    proc = _spawn_a_child()
    assert proc.returncode is not None, (
        "returncode must be set so Popen.__del__ does not warn about the "
        "still-running child"
    )


def test_spawn_detached_actually_starts_the_child():
    """The child must really run — the helper must not kill it."""
    proc = _spawn_a_child()
    assert proc.pid > 0
    # wait() now works and returns the real exit code of the child.
    assert proc.wait(timeout=30) == 0


@pytest.mark.skipif(sys.platform != "win32", reason="Windows detach flags")
def test_spawn_detached_accepts_the_windows_creationflags():
    """On Windows the helper must pass the detach flags straight through."""
    from openamer_cli._subprocess_compat import windows_detach_flags

    proc = spawn_detached(
        [sys.executable, "-c", "pass"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        creationflags=windows_detach_flags(),
    )
    assert proc.pid > 0
    assert proc.wait(timeout=30) == 0

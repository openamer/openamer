"""A spawned child must not outlive its caller.

Measured (missions/beyond-all P2.1, case T1): kill the agent process while it
runs a foreground tool call and the tool's own children keep running — they hold
ports, locks and CPU, and the retry has to contend with them. Nothing reaps
them, because a SIGKILLed caller runs no signal handler.

These tests prove the primitive, not the intention: a real caller process
spawns a real grandchild through the job, the caller is killed, and the
grandchild has to be gone.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

CALLER = """
import sys, time
from openamer_cli.proc_job import spawn_kill_on_close
p = spawn_kill_on_close([sys.executable, "-c", "import time; time.sleep(120)"])
open(sys.argv[1], "w").write(str(p.pid))
print("spawned", flush=True)
time.sleep(120)
"""


def _env() -> dict:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    return env


def test_process_alive_is_false_for_a_dead_pid():
    from openamer_cli.proc_job import process_alive

    assert process_alive(0) is False
    assert process_alive(-1) is False
    # a PID that cannot exist on any supported platform
    assert process_alive(999_999_999) is False


def test_process_alive_is_true_for_this_process():
    from openamer_cli.proc_job import process_alive

    assert process_alive(os.getpid()) is True


@pytest.mark.skipif(sys.platform != "win32", reason="Job Objects are a Windows primitive")
def test_kill_on_close_reaps_the_grandchild(tmp_path):
    from openamer_cli.proc_job import process_alive

    pidfile = tmp_path / "grandchild.pid"
    caller = subprocess.Popen(
        [sys.executable, "-u", "-c", CALLER, str(pidfile)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_env(),
    )
    try:
        deadline = time.time() + 30
        while time.time() < deadline and not pidfile.exists():
            time.sleep(0.05)
        assert pidfile.exists(), f"caller produced no pid file: {caller.communicate(timeout=10)[0]}"
        grandchild = int(pidfile.read_text().strip())
        assert process_alive(grandchild), "grandchild must be running before the kill"

        caller.kill()
        caller.communicate(timeout=30)

        deadline = time.time() + 15
        while time.time() < deadline and process_alive(grandchild):
            time.sleep(0.2)
        assert not process_alive(grandchild), f"grandchild {grandchild} survived its caller"
    finally:
        if caller.poll() is None:
            caller.kill()


@pytest.mark.skipif(sys.platform != "win32", reason="Job Objects are a Windows primitive")
def test_kill_on_close_keeps_a_healthy_child_alive_while_the_caller_lives(tmp_path):
    """The primitive must not break the normal case: a live caller keeps its work."""
    from openamer_cli.proc_job import process_alive

    pidfile = tmp_path / "grandchild2.pid"
    caller = subprocess.Popen(
        [sys.executable, "-u", "-c", CALLER, str(pidfile)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_env(),
    )
    try:
        deadline = time.time() + 30
        while time.time() < deadline and not pidfile.exists():
            time.sleep(0.05)
        assert pidfile.exists()
        grandchild = int(pidfile.read_text().strip())
        time.sleep(1.0)
        assert process_alive(grandchild), "a live caller must keep its child running"
    finally:
        caller.kill()
        caller.communicate(timeout=30)

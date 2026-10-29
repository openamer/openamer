"""A killed test slice must be able to name the file it died on.

Two slices (runs 40396804192 and 40411930081) were shut down by the runner while
sitting at ~94% with ``✗ 0`` — no failing test anywhere. Their logs ended on a
file that had *finished*, and the file that was actually running was invisible:
the runner printed a line only on completion, so nothing could be blamed and the
red check looked like a phantom.

Contract pinned here:

* a start marker ``▶ w<idx> <path>`` is printed before a file runs, carrying the
  ThreadPoolExecutor worker index, and
* the in-flight registry is what the SIGTERM dump reads, longest-running first
  with elapsed seconds — verified end-to-end in a real subprocess, because the
  handler terminates the process by design.
"""

from __future__ import annotations

import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts import run_tests_parallel as rtp  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_registry() -> None:
    with rtp._in_flight_lock:
        rtp._IN_FLIGHT.clear()
    yield
    with rtp._in_flight_lock:
        rtp._IN_FLIGHT.clear()


def test_start_marker_names_the_worker_and_the_file(capsys: pytest.CaptureFixture[str]) -> None:
    """The marker has to carry the worker index, or a kill report is unreadable."""

    def _work() -> None:
        rtp._note_file_started("tests/gateway/test_feishu.py")
        rtp._note_file_finished("tests/gateway/test_feishu.py")

    thread = threading.Thread(target=_work, name="ThreadPoolExecutor-0_3")
    thread.start()
    thread.join()

    out = capsys.readouterr().out
    assert "▶ w3 tests/gateway/test_feishu.py" in out, out
    assert rtp._format_in_flight(now=time.monotonic()) == []


def test_finished_files_leave_the_registry() -> None:
    rtp._note_file_started("tests/a.py")
    with rtp._in_flight_lock:
        assert "tests/a.py" in rtp._IN_FLIGHT
    rtp._note_file_finished("tests/a.py")
    with rtp._in_flight_lock:
        assert "tests/a.py" not in rtp._IN_FLIGHT


def test_in_flight_is_reported_longest_first_with_elapsed_seconds() -> None:
    now = 1000.0
    with rtp._in_flight_lock:
        rtp._IN_FLIGHT["tests/slow.py"] = now - 240.0
        rtp._IN_FLIGHT["tests/fast.py"] = now - 5.0

    lines = rtp._format_in_flight(now=now)

    assert lines[0].strip().startswith("tests/slow.py"), lines
    assert "240s" in lines[0], lines
    assert "5s" in lines[1], lines


_KILL_SCRIPT = """
import sys, time
sys.path.insert(0, {root!r})
from scripts import run_tests_parallel as rtp
rtp._install_kill_dump()
with rtp._in_flight_lock:
    rtp._IN_FLIGHT["tests/gateway/test_feishu.py"] = time.monotonic() - 300.0
import os, signal
os.kill(os.getpid(), signal.SIGTERM)
print("SHOULD NOT REACH")
"""


def test_sigterm_dump_names_the_in_flight_file() -> None:
    """A real SIGTERM must print the culprit list before the process dies.

    POSIX only: on Windows ``os.kill`` maps SIGTERM onto TerminateProcess, which
    kills the process outright — no Python handler runs. CI runs the slices on
    Linux, which is where a SIGTERM dump matters.
    """
    if sys.platform == "win32":
        pytest.skip("Windows: os.kill(SIGTERM) is TerminateProcess, no handler runs")
    script = _KILL_SCRIPT.format(root=str(REPO_ROOT))
    proc = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=120
    )

    assert "tests/gateway/test_feishu.py" in proc.stdout, proc.stdout + proc.stderr
    assert "still running" in proc.stdout, proc.stdout + proc.stderr
    assert "running 3" in proc.stdout, proc.stdout + proc.stderr
    assert "SHOULD NOT REACH" not in proc.stdout, "the handler must actually terminate"
    assert proc.returncode != 0

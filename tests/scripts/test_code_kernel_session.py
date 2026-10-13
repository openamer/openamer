#!/usr/bin/env python3
"""Tests for the session-persistent code kernel.

What is asserted here is the CONTRACT, not "it runs code" — that part is easy and
would pass for a broken implementation too:

- state survives between cells (the whole reason the module exists)
- a different session gets a different process and cannot see another's state
- an error is reported AND the kernel survives it
- a wedged cell is killed and the state is dropped, deliberately
- the result names a distinct kernel after ``reset``, so "which process
  answered" is never ambiguous
- output larger than one pipe read still arrives (the bug that made every cell
  look like a timeout on Windows)

The last two exist because both were real defects found by running it.
"""

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))

from tools import code_kernel as ck  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_kernels():
    """Never leave a kernel process behind, pass or fail."""
    ck.REGISTRY.reset()
    yield
    ck.REGISTRY.reset()


def test_state_survives_between_cells():
    ck.run_in_kernel("answer = 41", task_id="owner-a")
    out = ck.run_in_kernel("print(answer + 1)", task_id="owner-a")
    assert out["success"] is True
    assert out["stdout"].strip() == "42"
    assert out["execution_count"] == 2, "the cell counter must keep counting"


def test_imports_and_objects_persist():
    ck.run_in_kernel("import math\nroot = math.sqrt(144)", task_id="owner-a")
    out = ck.run_in_kernel("print(root)", task_id="owner-a")
    assert out["stdout"].strip() == "12.0"


def test_sessions_are_isolated():
    ck.run_in_kernel("secret = 'visible'", task_id="owner-a")
    out = ck.run_in_kernel("print('secret' in dir())", task_id="owner-b")
    assert out["stdout"].strip() == "False", "another session must not see this state"
    assert out["kernel"] != ck.run_in_kernel("pass", task_id="owner-a")["kernel"]


def test_an_error_is_reported_and_the_kernel_survives():
    ck.run_in_kernel("keep = 'still here'", task_id="owner-a")
    bad = ck.run_in_kernel("raise ValueError('boom')", task_id="owner-a")
    assert bad["success"] is False
    assert bad["status"] == "error"
    assert "boom" in bad["traceback"]
    # The state must survive the error: a fresh process would lose `keep`.
    after = ck.run_in_kernel("print(keep)", task_id="owner-a")
    assert after["stdout"].strip() == "still here"


def test_stdout_larger_than_one_pipe_read_arrives():
    """Regression: a 20 KB cell must not be truncated or time out.

    Found by running it: reading with ``proc.stdout.read(4096)`` blocks on Windows
    until the full 4096 bytes arrive, so a small reply was never handed over and
    every cell looked like a timeout. Large output then exposed the other half —
    the reader must not stop at the first chunk.
    """
    out = ck.run_in_kernel("print('A' * 20000)", task_id="owner-big")
    assert out["success"] is True
    assert len(out["stdout"]) == 20001  # 20000 chars + newline


def test_a_wedged_cell_is_killed_and_state_is_dropped():
    """A cell that exceeds its timeout must die, not hang the agent."""
    ck.run_in_kernel("temp = 1", task_id="owner-hang")
    with pytest.raises(ck.KernelError) as exc:
        ck.run_in_kernel("while True: pass", task_id="owner-hang", timeout=3)
    message = str(exc.value)
    assert "state lost" in message, message
    # And nothing is left running.
    assert ck.REGISTRY.count() == 0, ck.REGISTRY.describe()


def test_reset_yields_a_distinct_kernel():
    """The result must NAME the kernel, so reset must not look like a no-op."""
    before = ck.run_in_kernel("a = 1", task_id="owner-r")["kernel"]
    fresh = ck.run_in_kernel("b = 2", task_id="owner-r", reset=True)
    assert fresh["kernel"] != before, "reset produced an identically named kernel"
    # The new process must not carry the old state.
    assert ck.run_in_kernel("print('a' in dir())", task_id="owner-r")["stdout"].strip() == "False"


def test_result_reports_mode_and_kernel_name():
    out = ck.run_in_kernel("pass", task_id="owner-n")
    assert ":" in out["kernel"]
    assert out["kernel"].startswith("owner-n:")
    assert out["mode"] in ("strict", "project")


def test_reset_with_no_kernel_is_harmless():
    assert ck.REGISTRY.reset("never-used") == 0


def test_concurrent_cells_for_one_owner_do_not_orphan_the_kernel():
    """Two threads racing the first spawn must share one kernel, not create two."""
    import threading

    results = []

    def worker(n):
        results.append(ck.run_in_kernel(f"v{n} = {n}\nprint('ok-{n}')", task_id="owner-race"))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=120)

    assert len(results) == 3
    assert all(r["success"] for r in results), [r.get("stderr") for r in results]
    assert ck.REGISTRY.count() == 1, ck.REGISTRY.describe()


def test_tool_handler_returns_json_and_reports_kernel_loss():
    from tools.code_kernel_tool import code_kernel

    ok = code_kernel("print('hello from a cell')", task_id="owner-tool")
    assert '"success": true' in ok
    assert "hello from a cell" in ok

    failed = code_kernel("while True: pass", task_id="owner-tool", timeout=3)
    assert '"success": false' in failed
    assert "kernel_lost" in failed, "a lost kernel must be flagged for the caller"


def test_empty_code_is_refused_without_starting_a_kernel():
    from tools.code_kernel_tool import code_kernel

    out = code_kernel("   ", task_id="owner-empty")
    assert '"success": false' in out
    assert ck.REGISTRY.count() == 0

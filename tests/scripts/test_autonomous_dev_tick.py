"""A deterministic cron tick must recover before checking worker capacity."""

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from openamer_cli import kanban_db as kb
from openamer_cli import kanban_db_dispatch as dispatch


@pytest.fixture
def tick():
    path = Path(__file__).resolve().parents[2] / "scripts" / "autonomous_dev_tick.py"
    spec = importlib.util.spec_from_file_location("autonomous_dev_tick", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def board(tmp_path, monkeypatch):
    for name in tuple(os.environ):
        if name.startswith(("OPENAMER_KANBAN_", "KANBAN_", "TERMINAL_")):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("OPENAMER_HOME", str(tmp_path))
    monkeypatch.setenv("OPENAMER_KANBAN_HOME", str(tmp_path))
    monkeypatch.setattr(dispatch, "_profile_exists_fn", lambda: lambda name: True)
    monkeypatch.setattr(dispatch, "_memory_pressure_level", lambda: "normal")
    monkeypatch.setattr(kb, "_fire_kanban_lifecycle_hook", lambda *a, **k: None)
    conn = kb.connect(board="default")
    yield conn
    conn.close()


def task(conn, tmp_path, title="Resume development"):
    return kb.create_task(conn, title=title, assignee="dev", goal_mode=True,
                          workspace_kind="dir", workspace_path=str(tmp_path))


def test_recovers_orphan_before_enforcing_capacity(tick, board, tmp_path):
    tid = task(board, tmp_path)
    claimed = kb.claim_task(board, tid)
    old_run = claimed.current_run_id
    with kb.write_txn(board):
        board.execute("UPDATE tasks SET claim_lock=NULL, claim_expires=NULL WHERE id=?", (tid,))
    calls = []
    result = tick.run_tick(config={}, spawn_fn=lambda t, w, board=None: calls.append(t.id))
    assert result["reconciled_orphans"] == [tid]
    assert calls == [tid]
    assert kb.get_task(board, tid).current_run_id != old_run
    assert board.execute("SELECT outcome FROM task_runs WHERE id=?", (old_run,)).fetchone()[0] == "reclaimed"


def test_live_worker_is_not_reclaimed_or_duplicated(tick, board, tmp_path):
    tid = task(board, tmp_path)
    kb.claim_task(board, tid)
    dispatch._set_worker_pid(board, tid, os.getpid())
    task(board, tmp_path, "Waiting development")
    calls = []
    for _ in range(2):
        result = tick.run_tick(config={}, spawn_fn=lambda *a, **k: calls.append(a))
        assert result["spawned"] == []
    assert calls == []
    assert kb.get_task(board, tid).worker_pid == os.getpid()


def test_dead_worker_is_recovered_and_resumed(tick, board, tmp_path, monkeypatch):
    tid = task(board, tmp_path)
    kb.claim_task(board, tid)
    dispatch._set_worker_pid(board, tid, 99999999)
    # Model a pre-restart worker, not the dispatcher's intentional launch grace.
    monkeypatch.setattr(kb, "_resolve_crash_grace_seconds", lambda: 0)
    calls = []
    result = tick.run_tick(config={}, spawn_fn=lambda t, w, board=None: calls.append(t.id))
    assert tid in result["crashed"]
    assert calls == [tid]
    assert kb.get_task(board, tid).consecutive_failures == 1


def test_held_dispatch_lock_prevents_writes_and_spawn(tick, board, tmp_path):
    task(board, tmp_path)
    before = board.execute("SELECT COUNT(*) FROM task_events").fetchone()[0]
    with kb._dispatch_tick_lock(kb.kanban_db_path(board="default")) as held:
        assert held
        result = tick.run_tick(config={}, spawn_fn=lambda *a, **k: pytest.fail("duplicate spawn"))
    assert result["skipped_locked"] is True
    assert board.execute("SELECT COUNT(*) FROM task_events").fetchone()[0] == before


def test_blocked_tasks_and_dependencies_remain_gated(tick, board, tmp_path):
    parent = task(board, tmp_path)
    kb.block_task(board, parent, reason="review-required", kind="needs_input")
    child = kb.create_task(board, title="Dependent", assignee="dev", parents=[parent],
                           workspace_kind="dir", workspace_path=str(tmp_path))
    result = tick.run_tick(config={}, spawn_fn=lambda *a, **k: pytest.fail("blocked task spawned"))
    assert result["spawned"] == []
    assert kb.get_task(board, parent).status == "blocked"
    assert kb.get_task(board, child).status == "todo"


def test_one_tick_caps_spawns_even_with_large_config(tick, board, tmp_path):
    task(board, tmp_path)
    task(board, tmp_path, "Other development")
    calls = []
    result = tick.run_tick(config={"kanban": {"max_spawn": 5, "max_in_progress": 5}},
                           spawn_fn=lambda t, w, board=None: calls.append(t.id))
    assert len(calls) == len(result["spawned"]) == 1


def test_real_process_death_resumes_once_and_preserves_live_successor(tick, board, tmp_path):
    tid = task(board, tmp_path)
    kb.claim_task(board, tid)
    old = subprocess.Popen([sys._base_executable, "-S", "-c", "import time; time.sleep(30)"])
    children = []
    try:
        dispatch._set_worker_pid(board, tid, old.pid)
        old.terminate()
        old.wait(timeout=10)
        with kb.write_txn(board):
            board.execute("UPDATE tasks SET started_at=? WHERE id=?", (int(time.time()) - 120, tid))
        artifact = tmp_path / "resumed.txt"

        def spawn(task, workspace, board=None):
            child = subprocess.Popen([
                sys._base_executable, "-S", "-c",
                "import pathlib,sys,time; pathlib.Path(sys.argv[1]).write_text('resumed'); time.sleep(30)",
                str(artifact),
            ])
            children.append(child)
            return child.pid

        result = tick.run_tick(config={}, spawn_fn=spawn)
        assert result["crashed"] == [tid]
        assert len(children) == 1
        deadline = time.monotonic() + 10
        while not artifact.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert artifact.read_text() == "resumed"
        assert tick.run_tick(config={}, spawn_fn=spawn)["spawned"] == []
        assert len(children) == 1
        assert children[0].poll() is None
    finally:
        for child in [old, *children]:
            if child.poll() is None:
                child.terminate()
            child.wait(timeout=10)


def test_database_errors_fail_instead_of_silent_success(tick, monkeypatch):
    monkeypatch.setattr(kb, "connect", lambda **k: (_ for _ in ()).throw(RuntimeError("unavailable")))
    with pytest.raises(RuntimeError, match="unavailable"):
        tick.run_tick(config={})


def test_main_emits_durable_machine_readable_result(tick, monkeypatch, capsys):
    monkeypatch.setattr(tick, "run_tick", lambda: {"spawned": [], "skipped_locked": False})
    assert tick.main() == 0
    assert '"spawned": []' in capsys.readouterr().out


def test_main_failure_exits_nonzero(tick, monkeypatch, capsys):
    def fail():
        raise RuntimeError("database unavailable")
    monkeypatch.setattr(tick, "run_tick", fail)
    assert tick.main() == 1
    assert "database unavailable" in capsys.readouterr().err

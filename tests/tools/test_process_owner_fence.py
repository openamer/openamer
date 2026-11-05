"""The process tool must enforce an owner fence.

A background process belongs to the task (or gateway session) that
spawned it. Process ids are predictable ("proc_xxxxxxxxxxxx"), so
without an owner check any agent can kill or write into another
agent's background process.

Adapted from deepseek-ai/deepseek-harness ``packages/jobs``: "Ids are
predictable, so authorization — not secrecy — is the boundary."
"""
from __future__ import annotations

import json

import pytest


class _FakeSession:
    def __init__(self, task_id="", session_key="", exited=False):
        self.id = "proc_test"
        self.task_id = task_id
        self.session_key = session_key
        self.exited = exited
        self.command = "sleep 100"
        self.exit_code = None
        self.output_buffer = ""
        self._lock = __import__("threading").Lock()


@pytest.fixture
def registry(monkeypatch):
    """Install a fake process registry with one owned process."""
    import tools.process_registry as pr

    sessions = {"proc_mine": _FakeSession(task_id="task-1")}
    monkeypatch.setattr(pr.process_registry, "get", lambda sid: sessions.get(sid))
    def _fake_kill(sid, **kw):
        session = sessions.get(sid)
        if session is None:
            return {"status": "not_found", "error": f"No process with ID {sid}"}
        return {"status": "killed"}

    def _fake_poll(sid):
        session = sessions.get(sid)
        if session is None:
            return {"status": "not_found", "error": f"No process with ID {sid}"}
        return {"status": "running"}

    monkeypatch.setattr(pr.process_registry, "kill_process", _fake_kill)
    monkeypatch.setattr(pr.process_registry, "poll", _fake_poll)
    monkeypatch.setattr(pr.process_registry, "read_log", lambda sid, **kw: {"output": ""})
    monkeypatch.setattr(pr.process_registry, "write_stdin", lambda sid, data: {"status": "ok"})
    monkeypatch.setattr(pr.process_registry, "submit_stdin", lambda sid, data: {"status": "ok"})
    monkeypatch.setattr(pr.process_registry, "close_stdin", lambda sid: {"status": "ok"})
    return sessions


def _call(args, task_id="task-1", **kw):
    from tools.process_registry import _handle_process

    return json.loads(_handle_process(args, task_id=task_id, **kw))


def test_owner_can_kill_own_process(registry):
    out = _call({"action": "kill", "session_id": "proc_mine"})
    assert not out.get("error")
    assert out.get("status") == "killed"


def test_other_task_cannot_kill_foreign_process(registry):
    registry["proc_theirs"] = _FakeSession(task_id="task-2")
    out = _call({"action": "kill", "session_id": "proc_theirs"}, task_id="task-1")
    assert out.get("error")
    assert "belongs to" in out["error"]


def test_other_task_cannot_poll_foreign_process(registry):
    registry["proc_theirs"] = _FakeSession(task_id="task-2")
    out = _call({"action": "poll", "session_id": "proc_theirs"}, task_id="task-1")
    assert out.get("error")


def test_other_task_cannot_write_to_foreign_process(registry):
    registry["proc_theirs"] = _FakeSession(task_id="task-2")
    out = _call(
        {"action": "write", "session_id": "proc_theirs", "data": "rm -rf /"},
        task_id="task-1",
    )
    assert out.get("error")


def test_unknown_process_id_is_not_an_authorization_error(registry):
    """An unknown id must report "not found", not a refusal to act.

    The fence must not turn a typo into an authorization error — the
    model needs to see that no such process exists.
    """
    out = _call({"action": "kill", "session_id": "proc_nope"})
    assert out.get("status") == "not_found"
    assert "belongs to" not in str(out.get("error", ""))


def test_caller_without_task_identity_is_not_refused(registry):
    """No task identity means the fence cannot prove a violation.

    RPC/CLI paths that never set a task_id must keep working — refusing
    them would break every such caller without adding safety.
    """
    registry["proc_theirs"] = _FakeSession(task_id="task-2")
    out = _call({"action": "poll", "session_id": "proc_theirs"}, task_id=None)
    assert not out.get("error")


def test_orphaned_process_without_owner_is_allowed(registry):
    """A process recovered after a crash has no owner — nobody to refuse for."""
    registry["proc_orphan"] = _FakeSession(task_id="", session_key="")
    out = _call({"action": "poll", "session_id": "proc_orphan"})
    assert not out.get("error")


def test_same_session_key_is_allowed(registry, monkeypatch):
    registry["proc_theirs"] = _FakeSession(task_id="task-2", session_key="gw-1")
    import tools.process_registry as pr

    monkeypatch.setattr(pr, "_current_session_key", lambda: "gw-1")
    out = _call({"action": "poll", "session_id": "proc_theirs"}, task_id="task-1")
    assert not out.get("error")

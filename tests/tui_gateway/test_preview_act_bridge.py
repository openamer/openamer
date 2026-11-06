"""Preview-act bridge: session ownership, stale refs and the request round trip.

Two layers are covered:

* ``tools/desktop_ui.py`` + ``tools/drive_preview_tool.py`` — the tool addresses
  exactly the window that owns the turn and reports the renderer's answer
  verbatim, including a refusal.
* ``tui_gateway/server.py`` — ``preview.act.respond`` refuses an answer stamped
  with another session's id, and leaves the request answerable by its owner.
"""

import importlib
import io
import json
import sys
import threading
from unittest.mock import MagicMock, patch

import pytest

from gateway import session_context
from tools import desktop_ui
from tools.drive_preview_tool import drive_preview_tool

_original_stdout = sys.stdout


@pytest.fixture(autouse=True)
def _restore_stdout():
    yield
    sys.stdout = _original_stdout


@pytest.fixture(autouse=True)
def _reset_bridge():
    desktop_ui.set_emitter(None)
    desktop_ui.set_requester(None)
    yield
    desktop_ui.set_emitter(None)
    desktop_ui.set_requester(None)
    session_context.reset_session_vars()


@pytest.fixture()
def server():
    with patch.dict(
        "sys.modules",
        {
            "openamer_constants": MagicMock(get_openamer_home=MagicMock(return_value="/tmp/openamer_test")),
            "openamer_cli.env_loader": MagicMock(),
            "openamer_cli.banner": MagicMock(),
            "openamer_state": MagicMock(),
        },
    ):
        mod = importlib.import_module("tui_gateway.server")
        yield mod
        mod._sessions.clear()
        mod._pending.clear()
        mod._answers.clear()


# ── desktop_ui.request: the request goes to the turn's window ─────────


def test_request_routes_to_the_turn_window():
    seen = []

    def _ask(sid, event, payload, timeout):
        seen.append((sid, event, payload, timeout))
        return '{"ok": true}'

    desktop_ui.set_requester(_ask)
    session_context.set_session_vars(ui_session_id="window-a")

    assert desktop_ui.request("preview.act.request", {"action": "elements"}, timeout=5) == '{"ok": true}'
    assert seen == [("window-a", "preview.act.request", {"action": "elements"}, 5)]


def test_request_without_a_requester_returns_empty():
    session_context.set_session_vars(ui_session_id="window-a")

    assert desktop_ui.request("preview.act.request", {"action": "elements"}) == ""


def test_wire_desktop_ui_installs_both_directions(server):
    server._desktop_ui_wired = False
    server._wire_desktop_ui()

    assert desktop_ui.available() is True

    session_context.set_session_vars(ui_session_id="")
    # No window id means nobody to ask: the requester answers immediately rather
    # than blocking for the full timeout.
    assert desktop_ui.request("preview.act.request", {}, timeout=30) == ""


# ── drive_preview tool: validation + answer passthrough ───────────────


def test_unknown_action_is_rejected():
    result = json.loads(drive_preview_tool(action="evaluate", callback=lambda _p: '{"ok": true}'))

    assert "success" not in result
    assert "action must be one of" in result["error"]


def test_click_without_ref_is_rejected():
    result = json.loads(drive_preview_tool(action="click", callback=lambda _p: '{"ok": true}'))

    assert "needs a ref" in result["error"]


def test_type_without_text_is_rejected():
    result = json.loads(drive_preview_tool(action="type", ref="field-email", callback=lambda _p: '{"ok": true}'))

    assert "needs the text" in result["error"]


def test_tool_is_hidden_outside_the_desktop_app():
    result = json.loads(drive_preview_tool(action="elements"))

    assert "only available in the OpenAmer desktop app" in result["error"]


def test_payload_narrows_to_the_named_ref_and_action():
    seen = []

    drive_preview_tool(
        action="Type",
        ref="  field-email  ",
        text="a@b.c",
        submit=True,
        limit=12,
        callback=lambda payload: seen.append(payload) or '{"ok": true}',
    )

    assert seen == [{"action": "type", "ref": "field-email", "text": "a@b.c", "submit": True, "max": 12}]


def test_renderer_refusal_passes_through_unchanged():
    refusal = {"message": "Ref 'btn-old' belonged to a previous view of the page.", "ok": False, "status": "stale-ref"}

    result = json.loads(drive_preview_tool(action="click", ref="btn-old", callback=lambda _p: json.dumps(refusal)))

    assert result == refusal


def test_empty_answer_names_the_missing_preview():
    result = json.loads(drive_preview_tool(action="elements", callback=lambda _p: ""))

    assert "No preview window answered" in result["error"]


# ── Gateway: a cross-session answer cannot complete the round trip ────


def _wait_for_pending(server, timeout=2.0):
    deadline = threading.Event()
    for _ in range(int(timeout / 0.01)):
        if server._pending:
            return next(iter(server._pending))
        deadline.wait(0.01)
    raise AssertionError("no pending request registered")


def test_answer_from_another_session_is_refused_and_owner_can_still_answer(server):
    holder = {}
    started = threading.Event()

    def _call():
        started.set()
        holder["answer"] = server._block("preview.act.request", "session-a", {"action": "elements"}, timeout=5)

    thread = threading.Thread(target=_call)
    thread.start()
    started.wait(1)
    rid = _wait_for_pending(server)

    # A background window that learned the request id still cannot answer it.
    refused = server.handle_request(
        {
            "id": "bg",
            "method": "preview.act.respond",
            "params": {"request_id": rid, "result": '{"ok": true}', "session_id": "session-b"},
        }
    )

    assert refused["error"]["code"] == 4033
    assert holder.get("answer") is None

    # The owning window's answer completes it.
    accepted = server.handle_request(
        {
            "id": "owner",
            "method": "preview.act.respond",
            "params": {"request_id": rid, "result": '{"ok": true, "action": "elements"}', "session_id": "session-a"},
        }
    )

    assert accepted["result"] == {"status": "ok"}
    thread.join(timeout=5)
    assert holder["answer"] == '{"ok": true, "action": "elements"}'


def test_answer_without_a_session_is_refused(server):
    """An answer that names no session cannot prove ownership, so it is refused."""
    holder = {}

    def _call():
        holder["answer"] = server._block("preview.act.request", "session-a", {"action": "elements"}, timeout=5)

    thread = threading.Thread(target=_call)
    thread.start()
    rid = _wait_for_pending(server)

    refused = server.handle_request(
        {"id": "anon", "method": "preview.act.respond", "params": {"request_id": rid, "result": "{}"}}
    )

    assert refused["error"]["code"] == 4033

    # Unblock the owner so the test leaves no thread waiting on the bridge.
    server.handle_request(
        {
            "id": "owner",
            "method": "preview.act.respond",
            "params": {"request_id": rid, "result": "{}", "session_id": "session-a"},
        }
    )
    thread.join(timeout=5)
    assert holder["answer"] == "{}"


def test_expired_preview_request_announces_expiry(server):
    buf = io.StringIO()
    previous = server._real_stdout
    server._real_stdout = buf

    try:
        assert server._block("preview.act.request", "window-a", {"action": "elements"}, timeout=0) == ""
    finally:
        server._real_stdout = previous

    frames = [json.loads(line)["params"] for line in buf.getvalue().splitlines() if line.strip()]
    assert [frame["type"] for frame in frames] == ["preview.act.request", "preview.act.expire"]
    assert frames[0]["payload"]["request_id"] == frames[1]["payload"]["request_id"]

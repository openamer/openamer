"""Executable smoke for "one local browser, many sessions" via EXISTING interfaces.

The question this answers: can OpenAmer already reuse a single running
Chromium-family browser (an existing tab / an already-launched instance) for
several tasks instead of paying a launch or cloud session per task, without a
new browser tool stack, a browser extension, or a launch-flag change?

Answer: yes — ``BROWSER_CDP_URL`` (live ``/browser connect``) or
``browser.cdp_url`` (persistent config) pins *every* task to one CDP endpoint.
Each task key still gets its own agent-browser session (its own tab) but no new
browser process and no cloud session is created. These tests prove that wiring
hermetically — the endpoint is never contacted because a full
``/devtools/browser/`` websocket URL is used as-is.
"""

from __future__ import annotations

import pytest

CDP_WS = "ws://127.0.0.1:9222/devtools/browser/00000000-0000-0000-0000-000000000000"


@pytest.fixture
def browser_tool(monkeypatch):
    from tools import browser_tool as bt

    monkeypatch.setattr(bt, "_ensure_cdp_supervisor", lambda task_id: None)
    monkeypatch.setattr(bt, "_start_browser_cleanup_thread", lambda: None)
    monkeypatch.delenv("BROWSER_CDP_URL", raising=False)
    bt._active_sessions.clear()
    try:
        yield bt
    finally:
        bt._active_sessions.clear()


def _forbid_cloud(bt, monkeypatch):
    def _boom():
        raise AssertionError("a cloud session must not be created when an existing browser is pinned")

    monkeypatch.setattr(bt, "_get_cloud_provider", _boom)


def test_env_override_shares_one_browser_across_tasks(browser_tool, monkeypatch):
    bt = browser_tool
    monkeypatch.setenv("BROWSER_CDP_URL", CDP_WS)
    _forbid_cloud(bt, monkeypatch)

    first = bt._get_session_info("task-alpha")
    second = bt._get_session_info("task-beta")

    assert first["cdp_url"] == CDP_WS
    assert second["cdp_url"] == CDP_WS
    assert first["session_name"] != second["session_name"]  # one tab each
    assert not first.get("bb_session_id") and not second.get("bb_session_id")
    assert set(bt._active_sessions) == {"task-alpha", "task-beta"}


def test_config_cdp_url_shares_one_browser_across_tasks(browser_tool, monkeypatch):
    bt = browser_tool
    _forbid_cloud(bt, monkeypatch)
    monkeypatch.setattr(
        "openamer_cli.config.read_raw_config",
        lambda: {"browser": {"cdp_url": CDP_WS}},
    )

    sessions = [bt._get_session_info(f"task-{i}") for i in range(3)]

    assert {s["cdp_url"] for s in sessions} == {CDP_WS}
    assert len({s["session_name"] for s in sessions}) == 3

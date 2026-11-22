"""Contract tests for scripts/cron-browser-watchdog.py.

Live 2026-11-22, two defects measured while consolidating the browser stack:

* ``kill_impostors`` killed *every* ``chrome.exe --headless`` — including OpenAmer's
  own agent browser on :9223 (``chrome-agent-profile``). Enabling both watchdogs
  would have had them kill each other's browser in a loop.
* ``session_manager.py restore`` ran whenever no x.com tab existed, i.e. against a
  LIVE, logged-in profile whose cookie store is older than the values being
  injected — a way to destroy a working session while proving nothing.

The wrapper's decisions are pure functions, so they are tested without PowerShell,
without a browser, and without touching the user's profile.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "cron-browser-watchdog.py"

AGENT_CMDLINE = (
    r'"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9223 '
    r"--user-data-dir=C:\Users\u\AppData\Local\openamer-laptop\chrome-agent-profile --headless=new"
)
PROFILE_HEADLESS_CMDLINE = (
    r'"C:\Program Files\Google\Chrome\Application\chrome.exe" '
    r"--user-data-dir=C:\Users\u\AppData\Local\openamer-laptop\chrome-profile --headless=new"
)
PLAYWRIGHT_CMDLINE = r"chrome-headless-shell.exe --remote-debugging-port=9222"


def load_module():
    spec = importlib.util.spec_from_file_location("cron_browser_watchdog", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


wd = load_module()


def test_agent_browser_is_never_an_impostor():
    assert wd.is_agent_chrome(AGENT_CMDLINE) is True
    assert wd.is_impostor(AGENT_CMDLINE) is False
    # A headless instance on the *profile* is still an impostor and must be killed.
    assert wd.is_impostor(PROFILE_HEADLESS_CMDLINE) is True
    assert wd.is_agent_chrome(PROFILE_HEADLESS_CMDLINE) is False


def test_non_headless_chrome_is_not_an_impostor():
    assert wd.is_impostor(PLAYWRIGHT_CMDLINE) is False
    assert wd.is_impostor("") is False
    assert wd.is_impostor("chrome.exe --headless=new --user-data-dir=C:/tmp/pw") is True


def test_restore_only_into_a_wiped_profile():
    # Wiped profile -> restore is the point of the guard.
    assert wd.should_restore(0) is True
    assert wd.should_restore(wd.MIN_COOKIES_FOR_LIVE_PROFILE - 1) is True
    # Live profile -> old cookie values must never overwrite working ones.
    assert wd.should_restore(wd.MIN_COOKIES_FOR_LIVE_PROFILE) is False
    assert wd.should_restore(451) is False
    # Unreadable state (-1) is a skip, not a blind injection.
    assert wd.should_restore(-1) is False


def test_healthy_browser_plans_no_action():
    assert wd.plan(
        chrome_path="chrome.exe", alive=True, headless_ua=False, has_x_tab=True, cookie_count=451
    ) == []


def test_dead_browser_restarts_and_restores_wiped_session():
    assert wd.plan(
        chrome_path="chrome.exe", alive=False, headless_ua=False, has_x_tab=False, cookie_count=0
    ) == ["start_visible", "restore_session"]


def test_headless_impostor_is_replaced():
    assert wd.plan(
        chrome_path="chrome.exe", alive=True, headless_ua=True, has_x_tab=False, cookie_count=451
    ) == ["kill_impostors", "start_visible"]


def test_live_profile_without_x_tab_is_left_alone():
    """The 2026-11-22 regression: no x.com tab used to trigger a session restore."""
    assert wd.plan(
        chrome_path="chrome.exe", alive=True, headless_ua=False, has_x_tab=False, cookie_count=451
    ) == []
    # ... but a wiped profile with no tab still gets one.
    assert "restore_session" in wd.plan(
        chrome_path="chrome.exe", alive=True, headless_ua=False, has_x_tab=False, cookie_count=3
    )


def test_missing_chrome_binary_is_not_planned_as_a_restart():
    """No chrome.exe on disk -> plan must not promise a restart it cannot perform."""
    assert wd.plan(
        chrome_path=None, alive=False, headless_ua=False, has_x_tab=False, cookie_count=451
    ) == []

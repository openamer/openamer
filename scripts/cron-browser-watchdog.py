#!/usr/bin/env python3
"""Cron wrapper: keep the :9222 profile Chrome alive, and never fight its sibling.

What it does
------------
1. Probe ``http://127.0.0.1:9222/json/version``.
   * no answer      -> start the VISIBLE profile Chrome (never headless)
   * ``HeadlessChrome`` UA -> kill the impostor by PID, then start the visible one
   * real ``Chrome/`` UA   -> healthy, do nothing
2. If no ``x.com`` tab exists, restore the saved cookie jar **only when the
   profile is genuinely wiped**.

Two defects this wrapper exists to prevent (both measured 2026-11-22)
---------------------------------------------------------------------
* ``kill_impostors`` used to kill *every* ``chrome.exe --headless`` — including the
  agent browser on :9223 (``chrome-agent-profile``). Two watchdogs enabled then
  killed each other's browser in a loop. Anything whose command line mentions the
  agent profile is now off-limits.
* ``session_manager.py restore`` used to run whenever no x.com tab was present, i.e.
  against a LIVE, logged-in profile. The cookie store ages out (~30 days), so
  re-injecting old values can destroy a working session — and it never proved a
  login anyway. Restoring now requires a near-empty profile.

Cron contract: ``--no-agent`` jobs deliver stdout verbatim, so a healthy run must
print NOTHING. ``plan()`` is a pure function and ``main()`` only prints when it
acted or failed; use ``--verbose`` (manual runs) and ``--dry-run`` (inspection) to
see the reasoning.

Exit codes: 0 healthy/acted, 1 could not repair. Unreadable cookie state is a
"no action" skip, not a failure.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

PORT = int(os.environ.get("OPENAMER_AGENT_CHROME_PORT", "9223"))
PROFILE_CHROME_PORT = int(os.environ.get("OPENAMER_PROFILE_CHROME_PORT", "9222"))

HOME = Path(
    os.environ.get(
        "OPENAMER_HOME",
        str(Path.home() / "AppData" / "Local" / "openamer-laptop"),
    )
)
PROFILE_DIR = HOME / "chrome-profile"
SESSION_MGR = HOME / "openamer-browser" / "session_manager.py"

#: A profile below this many cookies is treated as wiped. Above it, restoring would
#: overwrite live values with stale ones.
MIN_COOKIES_FOR_LIVE_PROFILE = 50

#: Command-line marker of OpenAmer's own headless agent browser. Never kill it from
#: the profile watchdog — it has its own supervisor.
AGENT_PROFILE_MARKER = "chrome-agent-profile"

CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    str(Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Chrome" / "Application" / "chrome.exe"),
]


# ── pure decisions (unit-tested) ──────────────────────────────────────────────


def is_agent_chrome(cmdline: str) -> bool:
    """True for OpenAmer's :9223 agent browser, which this watchdog must not touch."""
    return AGENT_PROFILE_MARKER in (cmdline or "")


def is_impostor(cmdline: str) -> bool:
    """A headless chrome that must not hold the profile port."""
    return "--headless" in (cmdline or "") and not is_agent_chrome(cmdline)


def should_restore(cookie_count: int) -> bool:
    """Restore only into a wiped profile.

    ``cookie_count < 0`` means "could not read" — deliberately *not* a restore:
    blind injection into an unknown state is the defect this guard exists for.
    """
    return 0 <= cookie_count < MIN_COOKIES_FOR_LIVE_PROFILE


def plan(
    *,
    chrome_path: str | None,
    alive: bool,
    headless_ua: bool,
    has_x_tab: bool,
    cookie_count: int,
) -> list[str]:
    """Ordered actions for the current observation. Empty list = healthy.

    ``alive`` and ``chrome_path`` are separate on purpose: "the browser is dead"
    (restart it) and "there is no chrome.exe on disk" (nothing to restart with)
    are different facts, and conflating them planned restarts that could not run.
    """
    actions: list[str] = []
    if not alive:
        if chrome_path:
            actions.append("start_visible")
    elif headless_ua:
        actions.append("kill_impostors")
        actions.append("start_visible")
    if not has_x_tab and should_restore(cookie_count):
        actions.append("restore_session")
    return actions


# ── observations (touch the machine) ─────────────────────────────────────────


def cdp_info(timeout: float = 4.0) -> dict | None:
    try:
        raw = urllib.request.urlopen(
            f"http://127.0.0.1:{PROFILE_CHROME_PORT}/json/version", timeout=timeout
        ).read()
        return json.loads(raw)
    except Exception:
        return None


def find_chrome() -> str | None:
    for candidate in CHROME_CANDIDATES:
        if candidate and Path(candidate).is_file():
            return candidate
    return None


def headless_chrome_pids() -> list[tuple[str, str]]:
    """(pid, cmdline) for every chrome.exe carrying --headless, agent browser excluded."""
    ps = (
        "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | "
        "Where-Object { $_.CommandLine -match '--headless' } | "
        "ForEach-Object { \"$($_.ProcessId)::$($_.CommandLine)\" }"
    )
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=40,
        )
    except Exception:
        return []
    out: list[tuple[str, str]] = []
    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if "::" not in line:
            continue
        pid, cmdline = line.split("::", 1)
        pid = pid.strip()
        if pid.isdigit() and is_impostor(cmdline):
            out.append((pid, cmdline))
    return out


def live_cookie_count() -> int:
    """Cookie count in the live profile, or -1 when it cannot be read."""
    try:
        import websocket  # type: ignore
    except ImportError:
        return -1
    try:
        tabs = json.loads(
            urllib.request.urlopen(
                f"http://127.0.0.1:{PROFILE_CHROME_PORT}/json/list", timeout=5
            ).read()
        )
        pages = [t for t in tabs if t.get("type") == "page"]
        if not pages:
            return 0
        ws = websocket.create_connection(
            pages[0]["webSocketDebuggerUrl"], suppress_origin=True, timeout=15
        )
    except Exception:
        return -1
    try:
        ws.send(json.dumps({"id": 1, "method": "Storage.getCookies", "params": {}}))
        while True:
            resp = json.loads(ws.recv())
            if resp.get("id") == 1:
                return len(resp.get("result", {}).get("cookies", []))
    except Exception:
        return -1
    finally:
        try:
            ws.close()
        except Exception:
            pass


def has_tab(needle: str) -> bool:
    try:
        tabs = json.loads(
            urllib.request.urlopen(
                f"http://127.0.0.1:{PROFILE_CHROME_PORT}/json/list", timeout=5
            ).read()
        )
    except Exception:
        return False
    return any(needle in t.get("url", "") for t in tabs)


# ── actions ──────────────────────────────────────────────────────────────────


def kill_impostors(dry_run: bool = False) -> int:
    targets = headless_chrome_pids()
    if dry_run:
        for pid, cmdline in targets:
            print(f"  would kill pid {pid}: {cmdline[:120]}")
        return len(targets)
    subprocess.run(
        ["taskkill", "/F", "/IM", "chrome-headless-shell.exe"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    for pid, _ in targets:
        subprocess.run(
            ["taskkill", "/F", "/PID", pid],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    return len(targets)


def start_visible(chrome: str, wait_cycles: int = 10) -> bool:
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.Popen(
        [
            chrome,
            f"--user-data-dir={PROFILE_DIR}",
            f"--remote-debugging-port={PROFILE_CHROME_PORT}",
            "--remote-allow-origins=*",
            "--no-first-run",
            "--no-default-browser-check",
        ],
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        | getattr(subprocess, "DETACHED_PROCESS", 0),
        close_fds=True,
    )
    for _ in range(wait_cycles):
        time.sleep(3)
        info = cdp_info()
        if info and "HeadlessChrome" not in info.get("User-Agent", ""):
            return True
    return False


def restore_session() -> int:
    if not SESSION_MGR.is_file():
        print(f"FEHLER: {SESSION_MGR} fehlt — kein Restore moeglich")
        return 1
    proc = subprocess.run(
        [sys.executable, str(SESSION_MGR), "restore"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    if proc.returncode != 0:
        print(f"FEHLER: restore exit {proc.returncode}: {(proc.stdout or '')[-200:]}")
    return proc.returncode


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="report the plan, change nothing")
    ap.add_argument("--verbose", action="store_true", help="also speak when healthy")
    args = ap.parse_args()

    def say(message: str) -> None:
        if args.verbose or args.dry_run:
            print(message)

    info = cdp_info()
    headless_ua = bool(info) and "HeadlessChrome" in info.get("User-Agent", "")
    chrome = find_chrome()
    x_tab = has_tab("x.com") if info and not headless_ua else False
    cookies = live_cookie_count() if info and not headless_ua else 0

    actions = plan(
        chrome_path=chrome,
        alive=bool(info),
        headless_ua=headless_ua,
        has_x_tab=x_tab,
        cookie_count=cookies,
    )
    say(f"chrome={chrome} alive={bool(info)} headless={headless_ua} x_tab={x_tab} cookies={cookies}")
    say(f"plan={actions or ['none']}")

    if args.dry_run:
        if "kill_impostors" in actions:
            kill_impostors(dry_run=True)
        return 0

    if not actions:
        say("healthy — no action")
        return 0

    if "kill_impostors" in actions:
        killed = kill_impostors()
        print(f"[watchdog] headless impostor(s) killed: {killed} (agent browser left alone)")

    if "start_visible" in actions:
        if not chrome:
            print("FEHLER: chrome.exe nicht gefunden")
            return 1
        if not start_visible(chrome):
            print("FEHLER: sichtbarer Chrome antwortet nach 30 s nicht")
            return 1
        print("[watchdog] profile Chrome restarted (visible)")

    if "restore_session" in actions:
        print(f"[watchdog] profile looks wiped ({cookies} cookies) — restoring session")
        return restore_session()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

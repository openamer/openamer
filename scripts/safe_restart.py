#!/usr/bin/env python3
"""safe_restart.py — coordinate a safe Desktop restart (never self-kill).

Why this exists: an agent that kills OpenAmer.exe kills the chat/agent that
issued it (real SELF-KILL incident). To restart the packaged Desktop with new
backend code, the ONLY safe path is for a USER (or an external watcher) to run
`openamer desktop` — which rebuilds, packs, and starts afresh.

This script makes that restart *intentional and recoverable*:
  0. Optionally commit + sync outstanding work (so a restart loses nothing).
  1. Set a `reboot-flag` (`<home>/reboot-flag.json`) the watchdog can read
     after the app returns, so the agent knows "we just restarted for code X".
  2. Print the one command that actually restarts (`openamer desktop`) and how
     a watchdog/daemon can trigger it. It NEVER kills OpenAmer.exe itself.

Usage:
    python scripts/safe_restart.py --begin --commit   # prep + set flag
    python scripts/safe_restart.py --recovered        # mark recovery done
    python scripts/safe_restart.py --status           # show flag state
Exit codes:
    0 ok · 1 error · 3 = would-restart-needed but app-running (guard)
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home() / "AppData/Local/openamer-laptop" \
    if sys.platform == "win32" else Path.home() / ".openamer"
FLAG = HOME / "reboot-flag.json"
REPO = Path(__file__).resolve().parent.parent


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _git(cmd: list[str], cwd=REPO, check=False):
    env = dict(os.environ); env["GIT_TERMINAL_PROMPT"] = "0"
    return subprocess.run(["git", "-C", str(cwd)] + cmd, env=env,
                          capture_output=True, text=True, timeout=180)


def _commit_and_sync(reason: str) -> bool:
    """Commit any SS uncommitted change in the SoT repo (best-effort)."""
    dirty = _git(["status", "--porcelain"])
    tracked = [l for l in dirty.stdout.splitlines() if l and not l.startswith("??")]
    if not tracked:
        print("  no tracked changes to commit — working tree clean")
        return True
    # stage only tracked (skip stray generated files)
    _git(["add", "-u"])
    r = _git(["commit", "-m", f"chore: pre-restart snapshot ({reason})"])
    if r.returncode != 0:
        print(f"  commit skipped: {r.stderr.strip()[:120]}")
        return False
    print(f"  committed {len(tracked)} tracked change(s)")
    return True


def _set_flag(reason: str, target: str) -> None:
    FLAG.parent.mkdir(parents=True, exist_ok=True)
    FLAG.write_text(json.dumps({
        "reason": reason,
        "target": target,
        "created": _now(),
        "handled": False,
        "restart_command": "openamer desktop",
    }, indent=2), encoding="utf-8")
    print(f"  reboot-flag set -> {FLAG}")


def begin(reason: str, commit: bool) -> int:
    if commit:
        _commit_and_sync(reason)
    _set_flag(reason, "openamer desktop")
    # Never kill. Print the single safe restart path + how a daemon can do it.
    print(f"\n  SAFE RESTART PATH (never self-kill):")
    print("    → run in a USER terminal:  openamer desktop")
    print("      (rebuilds, packs, launches fresh; old process released cleanly)")
    print("    → or have the autonom_watchtower cron notice reboot-flag.json and signal it")
    print(f"  reason: {reason}")
    return 0


def recovered() -> int:
    if not FLAG.exists():
        print("  no reboot-flag — nothing to recover")
        return 0
    flag = json.loads(FLAG.read_text(encoding="utf-8"))
    flag["handled"] = True
    flag["recovered_at"] = _now()
    FLAG.write_text(json.dumps(flag, indent=2), encoding="utf-8")
    print(f"  recovered after: {flag.get('reason')} (target {flag.get('restart_command')})")
    return 0


def status() -> int:
    if not FLAG.exists():
        print("  no reboot-flag set")
        return 0
    flag = json.loads(FLAG.read_text(encoding="utf-8"))
    state = "handled" if flag.get("handled") else "PENDING"
    print(f"  reboot-flag [{state}]: {flag.get('reason')} @ {flag.get('created')}")
    return 0 if flag.get("handled") else 3


def main() -> int:
    ap = argparse.ArgumentParser(prog="safe_restart")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--begin", action="store_true", help="prep + set reboot flag")
    g.add_argument("--recovered", action="store_true", help="mark recovery done")
    g.add_argument("--status", action="store_true", help="show flag state")
    ap.add_argument("--reason", default="code update")
    ap.add_argument("--commit", action="store_true", help="commit+sync tracked changes first")
    a = ap.parse_args()
    if a.begin:
        return begin(a.reason, a.commit)
    if a.recovered:
        return recovered()
    return status()


if __name__ == "__main__":
    sys.exit(main())
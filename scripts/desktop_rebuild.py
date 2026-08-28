#!/usr/bin/env python3
"""desktop_rebuild.py — safe, non-self-killing Desktop rebuild + restart.

THE hard rule this enforces: never kill OpenAmer.exe from the agent (a PID
kill / taskkill on the running win-unpacked process terminates the chat/agent
that issued it). Instead this script rebuilds the packaged app and triggers a
restart through the app's OWN launch mechanism, so the old process is released
cleanly by the packaging step (like `openamer desktop` does for the user).

Safety contract:
- It does NOT run `Stop-Process` / `taskkill` on OpenAmer.exe.
- It runs the same pipeline as `openamer desktop`: renderer build + electron
  builder --dir, then (optionally) launches the fresh packaged exe.
- On EBUSY (app still running), it exits with a clear instruction to run
  `openamer desktop` from a user terminal rather than auto-killing.

Usage:
    python scripts/desktop_rebuild.py            # build+pack, don't launch
    python scripts/desktop_rebuild.py --launch   # build+pack and launch fresh
    python scripts/desktop_rebuild.py --check    # print paths + lock status only

Exit codes:
    0 = success (built / would-build / checked)
    1 = error
    3 = EBUSY — app running; resolve with `openamer desktop` (never auto-kill)
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

# The Desktop agent copy that holds the actual packaged app + source we build.
DEFAULT_AGENT_DIR = Path.home() / "AppData/Local/openamer-laptop/openamer-agent"
DESKTOP_DIR = DEFAULT_AGENT_DIR / "apps/desktop"
PACKED_EXE = DESKTOP_DIR / "release/win-unpacked/OpenAmer.exe"


def _is_running() -> bool:
    """Check for a running OpenAmer.exe from the unpacked app (read-only)."""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-Process OpenAmer -ErrorAction SilentlyContinue | Measure-Object).Count"],
            capture_output=True, text=True, timeout=30,
        )
        n = int((r.stdout or "0").strip() or "0")
        return n > 0
    except Exception:
        return False


def _run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, **kw)


def build_pack(launch: bool) -> int:
    if not DESKTOP_DIR.exists():
        print(f"ERROR: desktop source not found at {DESKTOP_DIR}")
        return 1

    if _is_running():
        print(
            f"SELFKILL-GUARD: a packaged OpenAmer.exe is currently running.\n"
            f"Rebuilding would hit EBUSY (v8_context_snapshot.bin locked) and I "
            f"must NOT kill the chat process.\n"
            f"→ Resolve manually from a user terminal:\n"
            f"    openamer desktop\n"
            f"(builds + packs + starts the fresh app cleanly.)"
        )
        return 3

    # Same as `openamer desktop`'s pack stage.
    steps = [
        ["node", "scripts/write-build-stamp.mjs"],
        ["npm", "run", "build"],
        ["npm", "run", "builder", "--", "--dir"],
    ]
    for step in steps:
        print(f"=== {' '.join(step)} ===")
        r = _run(step, cwd=str(DESKTOP_DIR))
        if r.returncode != 0:
            print(f"FAILED after {step[0]} {step[1]} (exit {r.returncode})")
            return 1

    if launch:
        print(f"Launching packaged app: {PACKED_EXE}")
        if PACKED_EXE.exists():
            subprocess.Popen([str(PACKED_EXE)], cwd=str(PACKED_EXE.parent),
                             close_fds=False)
        else:
            print(f"WARN: {PACKED_EXE} not found after build — build to finish.")
    print("OK — desktop rebuilt without self-kill.")
    return 0


def check() -> int:
    print(f"agent dir : {DEFAULT_AGENT_DIR}")
    print(f"desktop   : {DESKTOP_DIR}  exists={DESKTOP_DIR.exists()}")
    print(f"packed exe: {PACKED_EXE}  exists={PACKED_EXE.exists()}")
    print(f"running   : {_is_running()}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="desktop_rebuild")
    ap.add_argument("--launch", action="store_true",
                    help="build+pack and launch the fresh app")
    ap.add_argument("--check", action="store_true",
                    help="print paths + running status only")
    a = ap.parse_args()
    if a.check:
        return check()
    return build_pack(launch=a.launch)


if __name__ == "__main__":
    sys.exit(main())
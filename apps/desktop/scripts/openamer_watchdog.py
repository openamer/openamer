"""
OpenAmer Self-Healing Watchdog (Windows).

Monitors the OpenAmer desktop app and restarts it automatically if it dies
or crashes. This is the external safety net that guarantees the desktop
surface (and its local gateway) is always running — "superintelligence must
be able to restart itself automatically, always."

Design:
  - Idempotent: only one watchdog instance runs at a time (mutex via lock file).
  - Restart policy: if OpenAmer.exe is not running, relaunch it.
  - Backoff: after a restart, wait a grace period before checking again so a
    slow boot doesn't cause a restart loop.
  - Logs every action to a rotating log file for diagnosis.

Run via Task Scheduler at logon + every 2 minutes (see install instructions
in the README / this file's docstring).
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

# --- Config -------------------------------------------------------------
# Path to the OpenAmer desktop executable.
OPENAMER_EXE = r"C:\Users\damir\AppData\Local\Programs\openamer\OpenAmer.exe"

# Where the watchdog keeps its lock file and log.
WATCHDOG_DIR = Path(os.environ.get("OPENAMER_WATCHDOG_DIR", str(Path.home() / ".openamer-watchdog")))
LOCK_FILE = WATCHDOG_DIR / "watchdog.lock"
LOG_FILE = WATCHDOG_DIR / "watchdog.log"

# After a restart, wait this long before the next check (seconds) so a slow
# boot / model load doesn't trigger a restart loop.
GRACE_AFTER_RESTART_S = 60

# How long to wait for the app to appear after launching it (seconds).
LAUNCH_TIMEOUT_S = 30


def log(msg: str) -> None:
    """Append a timestamped line to the watchdog log."""
    try:
        WATCHDOG_DIR.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
    except Exception:
        pass


def is_running() -> bool:
    """Return True if the OpenAmer desktop process is alive."""
    try:
        # tasklist is reliable on Windows and needs no extra deps.
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq OpenAmer.exe", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            timeout=15,
        ).stdout
        return "OpenAmer.exe" in out
    except Exception as exc:
        log(f"is_running check failed: {exc}")
        return True  # fail-safe: don't restart on a broken check


def launch() -> bool:
    """Launch OpenAmer detached. Returns True if it appears within timeout."""
    try:
        subprocess.Popen(
            [OPENAMER_EXE],
            cwd=str(Path(OPENAMER_EXE).parent),
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            close_fds=True,
        )
    except Exception as exc:
        log(f"launch failed: {exc}")
        return False

    # Wait for the process to appear.
    deadline = time.time() + LAUNCH_TIMEOUT_S
    while time.time() < deadline:
        if is_running():
            return True
        time.sleep(2)
    return is_running()


def acquire_lock() -> bool:
    """Try to acquire the single-instance lock. Returns True if acquired."""
    try:
        WATCHDOG_DIR.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(LOCK_FILE), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    except FileExistsError:
        # Lock exists — check if the owning watchdog is still alive.
        try:
            owner = int(LOCK_FILE.read_text().strip())
            # If the owner is gone, steal the lock.
            subprocess.run(["tasklist", "/FI", f"PID eq {owner}"], capture_output=True, timeout=10)
            # A simple liveness probe: if the PID isn't in tasklist, it's dead.
            out = subprocess.run(
                ["tasklist", "/FI", f"PID eq {owner}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                timeout=10,
            ).stdout
            if str(owner) not in out:
                LOCK_FILE.unlink(missing_ok=True)
                return acquire_lock()
        except Exception:
            pass
        return False
    except Exception:
        return False


def release_lock() -> None:
    try:
        LOCK_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def main() -> int:
    if not acquire_lock():
        # Another watchdog is already running — nothing to do.
        return 0

    try:
        if not Path(OPENAMER_EXE).exists():
            log(f"OpenAmer.exe not found at {OPENAMER_EXE} — cannot watch")
            return 1

        if is_running():
            log("OpenAmer is running — nothing to do")
            return 0

        log("OpenAmer is NOT running — restarting")
        if launch():
            log("OpenAmer restarted successfully")
            # Grace period so a slow boot doesn't loop.
            time.sleep(GRACE_AFTER_RESTART_S)
        else:
            log("OpenAmer did not appear after launch — will retry next tick")
        return 0
    finally:
        release_lock()


if __name__ == "__main__":
    sys.exit(main())

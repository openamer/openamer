"""Background daemon that exports closed sessions as training trajectories.

Spawned by ``openamer_cli.main()`` at startup.  Polls the state DB every 60s
and writes new session trajectories to ``~/.openamer/trajectories/`` so that
``openamer a2a brain collect`` can merge them into the brain dataset.

This is the "every session, automatically, no user action" path.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_DAEMON_PID_FILE: Path | None = None


def _pid_file() -> Path:
    global _DAEMON_PID_FILE
    if _DAEMON_PID_FILE is None:
        home = Path(os.environ.get("OPENAMER_HOME", Path.home() / ".openamer"))
        _DAEMON_PID_FILE = home / "session_to_brain.pid"
    return _DAEMON_PID_FILE


def _acquire_spawn_lock() -> Path | None:
    """Atomically claim the spawn lock so concurrent spawn() callers don't
    race. On Windows, TWO spawn() calls can both read a missing/empty pid file
    before either writes it, then start duplicate daemons (~30 in one incident).
    O_CREAT|O_EXCL guarantees only one caller wins; losers return None and skip
    starting. The winner's lock file is removed in spawn()'s finally."""
    lock_file = _pid_file().with_suffix(".lock")
    try:
        fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
        return lock_file
    except FileExistsError:
        return None
    except OSError:
        return None


def spawn() -> None:
    """Start the session-to-brain background daemon if it isn't already running.

    The daemon runs ``scripts/session_to_brain.py --watch`` as a subprocess.
    It polls the state DB every 60s and exports closed sessions as training
    trajectories.  Non-fatal: if the script is missing or fails, the rest of
    OpenAmer works fine.
    """
    pid_file = _pid_file()

    # Check if already running.
    if pid_file.exists():
        try:
            old_pid = int(pid_file.read_text().strip())
            # On Windows os.kill with signal 0 raises SystemError.
            # Use tasklist to check if the process exists.
            if os.name == "nt":
                r = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {old_pid}", "/NH"],
                    capture_output=True, text=False, timeout=5,
                )
                # text=False -> bytes; check robustly, tolerate non-UTF-8
                # Windows codepages (bytes 0x80+) and empty output.
                out = (r.stdout or b"").decode("utf-8", errors="replace")
                if str(old_pid) in out:
                    return  # already running
            else:
                os.kill(old_pid, 0)
                return  # already running
        except (ValueError, OSError, ProcessLookupError, subprocess.TimeoutExpired):
            # Stale pid file — remove and restart.
            pid_file.unlink(missing_ok=True)

    # Serialize concurrent spawns (a lost race would start duplicate daemons).
    lock_file = _acquire_spawn_lock()
    if lock_file is None:
        logger.debug("session_to_brain spawn skipped: concurrent spawn in flight")
        return
    try:
        # Locate the script relative to this file's location.
        script = Path(__file__).resolve().parent.parent / "scripts" / "session_to_brain.py"
        if not script.exists():
            logger.debug("session_to_brain.py not found at %s", script)
            return

        python = sys.executable
        proc = subprocess.Popen(
            [python, str(script), "--watch"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        pid_file.write_text(str(proc.pid))
        logger.debug("session_to_brain daemon started (pid=%d)", proc.pid)
    except Exception as exc:
        logger.debug("session_to_brain daemon failed: %s", exc)
    finally:
        lock_file.unlink(missing_ok=True)
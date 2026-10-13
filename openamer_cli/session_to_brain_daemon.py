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

# A live spawn holds the lock for seconds at most; anything older is debris
# from an interrupted run (crash / self-update) and may be reclaimed.
_LOCK_STALE_SECONDS = 300


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
        # Stale-lock reclaim: a live spawn holds the lock for seconds at most.
        try:
            age = time.time() - lock_file.stat().st_mtime
        except OSError:
            return None
        if age > _LOCK_STALE_SECONDS:
            try:
                lock_file.unlink()
                fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
                logger.debug("reclaimed stale spawn lock (age %.0fs)", age)
                return lock_file
            except (FileExistsError, OSError):
                return None
        return None
    except OSError:
        return None


def _watcher_lock_path() -> Path:
    """The singleton lock the ``--watch`` loop itself holds.

    Must match ``_watch_singleton_lock()`` in ``scripts/session_to_brain.py``
    byte for byte in WHERE it points: a machine/user-scoped temp path, NOT
    ``$OPENAMER_HOME`` (which is unset in some spawn contexts, so a HOME-scoped
    lock lets two "singletons" coexist and multiply watchers). Keep the two
    definitions in sync.
    """
    import tempfile

    return Path(tempfile.gettempdir()) / "openamer-session-to-brain-watch.lock"


def _watcher_running() -> bool:
    """True iff a ``--watch`` loop currently owns the singleton lock.

    Replaces a PID-file liveness check that never worked: ``spawn()`` recorded
    the pid of the *launcher* process (``sys.executable`` is a uv trampoline on
    Windows that exits as soon as the real interpreter is up), so the recorded
    pid was dead on the very next call and EVERY ``openamer`` invocation started
    another doomed watcher. Probing the same OS-level lock the watcher holds is
    exact and survives the trampoline, crashes and pid reuse.
    """
    lock_path = _watcher_lock_path()

    try:
        fh = open(lock_path, "a+", encoding="utf-8")
    except OSError:
        return False

    try:
        if os.name == "nt":
            import msvcrt

            fh.seek(0)
            try:
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                return True  # held by a live watcher
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
            return False
        else:
            import fcntl

            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                return True
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            return False
    finally:
        try:
            fh.close()
        except Exception:
            pass


def spawn() -> None:
    """Start the session-to-brain background daemon if it isn't already running.

    The daemon runs ``scripts/session_to_brain.py --watch`` as a subprocess.
    It polls the state DB every 60s and exports closed sessions as training
    trajectories.  Non-fatal: if the script is missing or fails, the rest of
    OpenAmer works fine.
    """
    pid_file = _pid_file()

    # Already running? Ask the watcher's OWN lock, not a pid we guessed.
    if _watcher_running():
        return

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
        pid_file.write_text(str(proc.pid), encoding="utf-8")
        logger.debug("session_to_brain daemon started (pid=%d)", proc.pid)
    except Exception as exc:
        logger.debug("session_to_brain daemon failed: %s", exc)
    finally:
        lock_file.unlink(missing_ok=True)
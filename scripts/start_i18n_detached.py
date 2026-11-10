"""Launch locale translation workers that survive the agent process dying.

Measured the hard way: a translator started with terminal(background=True) is
session-scoped, so when the agent process crashed all five workers died with it
and the work stopped silently. Translation is I/O-bound and long (hours), which
is exactly the wrong lifetime to tie to a chat session.

This launcher spawns N detached OS processes, each owning a slice of the queue,
writes their stdout/stderr to logs/*.log, and records their PIDs so a later run
can report status without guessing.

Usage:
    python scripts/start_i18n_detached.py            # all locales below 90%
    python scripts/start_i18n_detached.py --queues 4
    python scripts/start_i18n_detached.py --status
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOME = Path(os.environ.get("OPENAMER_HOME") or (Path.home() / "AppData" / "Local" / "openamer-laptop"))
LOGDIR = HOME / "logs"
PIDFILE = LOGDIR / "i18n-translate.pid.json"


def pidfile_for(target: str) -> Path:
    """Separate bookkeeping per target: CLI and desktop run in parallel."""
    return LOGDIR / ("desktop-translate.pid.json" if target == "desktop" else "i18n-translate.pid.json")
QUEUES = 4
MIN_SHARE = 1.0


def _pid_alive(pid: int) -> bool:
    """True when the pid exists. Windows has no signal-0; use OpenProcess."""
    if os.name == "nt":
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        h = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            return False
        try:
            code = ctypes.c_ulong()
            ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
            return code.value == STILL_ACTIVE
        finally:
            ctypes.windll.kernel32.CloseHandle(h)
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _worker_alive(record: dict, target: str) -> bool:
    """A recycled PID after reboot is not proof of a translation worker."""
    import psutil

    script = REPO / "scripts" / (
        "fill_desktop_locales.py" if target == "desktop" else "i18n_fill_cli_locales.py")
    expected = os.path.normcase(os.path.abspath(script))
    try:
        proc = psutil.Process(int(record["pid"]))
        if record.get("created") is not None and abs(proc.create_time() - record["created"]) > 0.01:
            return False
        return any(os.path.normcase(os.path.abspath(arg)) == expected
                   for arg in proc.cmdline()[1:] if not arg.startswith("-"))
    except (psutil.Error, ValueError, KeyError, OSError):
        return False


def status(target: str = "cli") -> int:
    pidfile = pidfile_for(target)
    if not pidfile.exists():
        print(f"no detached {target} translation recorded")
        return 1
    rec = json.loads(pidfile.read_text(encoding="utf-8"))
    alive = 0
    for w in rec.get("workers", []):
        ok = _worker_alive(w, target)
        alive += 1 if ok else 0
        print(f"  pid {w['pid']:<8} {'alive' if ok else 'dead '}  "
              f"{w['locales'][:3]}{'...' if len(w['locales']) > 3 else ''} "
              f"({len(w['locales'])} locales)  log={Path(w['log']).name}")
    print(f"{alive}/{len(rec.get('workers', []))} workers alive; started {rec.get('started')}")
    return 0 if alive else 1


def pending_locales(min_share: float) -> list[str]:
    proc = subprocess.run([sys.executable, str(REPO / "scripts" / "i18n_audit.py"), "--json"],
                          capture_output=True, text=True, cwd=str(REPO), timeout=300)
    if proc.returncode != 0 and not proc.stdout.strip():
        raise SystemExit(f"audit failed: {proc.stderr[-400:]}")
    rows = json.loads(proc.stdout)
    return [r["code"] for r in rows if r["share"] < min_share]


def pending_desktop() -> list[str]:
    """Let the worker inspect value-level gaps in every declared locale.

    Partial modules are not complete: never filter them by file shape.
    The worker owns cache resumption, validation and per-locale locking.
    """
    names = json.loads((REPO / "locales" / "_languages.json").read_text(encoding="utf-8"))
    return [code for code in names if code != "en"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--queues", type=int, default=QUEUES)
    ap.add_argument("--min-share", type=float, default=MIN_SHARE)
    ap.add_argument("--workers", type=int, default=2, help="threads per process")
    ap.add_argument("--target", choices=("cli", "desktop"), default="cli",
                    help="cli = locales/*.yaml, desktop = apps/desktop/src/i18n/*.ts")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--force", action="store_true", help="start even if workers are alive")
    args = ap.parse_args()

    if args.status:
        return status(args.target)

    pidfile = pidfile_for(args.target)
    if pidfile.exists() and not args.force:
        try:
            rec = json.loads(pidfile.read_text(encoding="utf-8"))
            alive = [w for w in rec.get("workers", []) if _worker_alive(w, args.target)]
        except (json.JSONDecodeError, KeyError, ValueError):
            alive = []
        if alive:
            print(f"{len(alive)} worker(s) already alive; use --force to add more")
            return status(args.target)

    todo = pending_desktop() if args.target == "desktop" else pending_locales(args.min_share)
    if not todo:
        print(f"nothing pending for {args.target}")
        return 0

    # Longest queue first so the slowest slice still gets help: round-robin.
    queues: list[list[str]] = [[] for _ in range(args.queues)]
    for i, code in enumerate(todo):
        queues[i % args.queues].append(code)

    LOGDIR.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    if args.target == "desktop":
        env["OPENAMER_DESKTOP_WORKERS"] = str(args.workers)
    else:
        env["OPENAMER_I18N_WORKERS"] = str(args.workers)
        env["OPENAMER_I18N_BATCH"] = env.get("OPENAMER_I18N_BATCH", "12")
        env["OPENAMER_I18N_BATCH_PAUSE"] = env.get("OPENAMER_I18N_BATCH_PAUSE", "0.5")

    script = ("fill_desktop_locales.py" if args.target == "desktop"
              else "i18n_fill_cli_locales.py")
    prefix = "desktop" if args.target == "desktop" else "i18n"

    workers = []
    for idx, q in enumerate(queues, 1):
        if not q:
            continue
        log = LOGDIR / f"{prefix}-worker-{idx}.log"
        cmd = [sys.executable, str(REPO / "scripts" / script), *q]
        kwargs: dict = {
            "cwd": str(REPO), "env": env, "stdin": subprocess.DEVNULL,
            "stdout": open(log, "w", encoding="utf-8"),
            "stderr": subprocess.STDOUT,
        }
        if os.name == "nt":
            # Independent console/process group. These flags do not guarantee
            # escape from an inherited Job Object or survival of a reboot;
            # resume_i18n.py supplies scheduler-driven restart recovery.
            kwargs["creationflags"] = 0x00000008 | 0x00000200
        else:
            kwargs["start_new_session"] = True
        proc = subprocess.Popen(cmd, **kwargs)
        workers.append({"pid": proc.pid, "locales": q, "log": str(log)})
        print(f"  started pid {proc.pid}: {len(q)} locales -> {log.name}")

    pidfile.write_text(json.dumps({
        "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "pending": len(todo),
        "workers": workers,
    }, indent=1), encoding="utf-8", newline="\n")
    print(f"{len(workers)} detached workers for {len(todo)} locales; "
          f"status: python scripts/start_i18n_detached.py --status")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

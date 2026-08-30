#!/usr/bin/env python3
"""Unified service watchdog for OpenAmer local services.

Services (all simple foreground HTTP servers):
  - dashboard-server.py   -> :8899
  - remote-web.py         -> :8901
  - system-snapshot.py --serve -> :8898
  - webhook-engine.py     -> :8900  (already has its own cron wrapper;
                                     health-probed here too)

Exit 0 when ALL expected services are up (or were successfully restarted);
exit 1 listing failures — so the cron status is truthful.
Runs detached starts (survive console close) unlike `start /B`.
"""
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

SC = Path(r"C:\Users\damir\AppData\Local\openamer-laptop\scripts")
DETACHED = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP

SERVICES = [
    # (name, port, probe_path, command)
    ("dashboard",   8899, "/",        [sys.executable, str(SC / "dashboard-server.py")]),
    ("remote-web",  8901, "/",        [sys.executable, str(SC / "remote-web.py")]),
    ("snapshot",    8898, "/",        [sys.executable, str(SC / "system-snapshot.py"), "--serve"]),
    ("webhook",     8900, "/health",  [sys.executable, str(SC / "webhook-engine.py"), "--start"]),
]


def probe(port: int, path: str) -> int | None:
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}{path}")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status
    except Exception:
        return None


def ensure_running(name: str, port: int, path: str, cmd: list, restart: bool = True) -> tuple[bool, str | None]:
    if probe(port, path) is not None:
        return True, None
    if not restart:
        return False, "down"
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         stdin=subprocess.DEVNULL, creationflags=DETACHED, close_fds=True)
    except Exception as e:
        return False, f"spawn failed: {e}"
    deadline = time.time() + 12
    while time.time() < deadline:
        time.sleep(1.2)
        if probe(port, path) is not None:
            return True, None
    return False, "no answer after 12s"


def main() -> int:
    failures, started = [], []
    for name, port, path, cmd in SERVICES:
        was = probe(port, path)
        if was is None:
            ok, info = ensure_running(name, port, path, cmd)
            if ok:
                started.append(name)
            else:
                failures.append(f"{name}(:{port}): {info}")
        # else: already up
    result = {
        "ok": not failures,
        "services": {n: {"port": p, "up": probe(p, pa) is not None} for n, p, pa, _ in SERVICES},
        "restarted": started,
        "failures": failures,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    print(json.dumps(result, ensure_ascii=False))  # noqa:SEC machine-readable cron report
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
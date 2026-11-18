#!/usr/bin/env python3
"""Identity and drift checks for the OpenAmer local HTTP services.

Why this module exists
----------------------
A supervisor can only heal a service if it can tell WHICH build is answering.
Until 2026-11-18 the dashboard watchdog asked a single question — "is port
8899 open?" — and on Windows that answer is a lie:

* ``HTTPServer`` sets ``allow_reuse_address``, so ``SO_REUSEADDR`` lets a
  SECOND process bind a port another process is already serving. Measured on
  this install: two ``dashboard-server.py`` processes (one started by
  ``dashboard-watchdog.py``, one by ``service-watchdog.py``, both at
  19:02:02) answered on :8899.
* The one that bound first kept serving OLD routes. ``/api/discovery``
  returned 404 while ``grep`` found the route in the file on disk, because the
  running process was older than the file. The watchdog saw "port open",
  printed ✅ and never healed it.

So "up" is not the question. The questions are: *which build answers*, *how
many processes answer*, and *does that build match the file on disk*.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


# ── build identity ─────────────────────────────────────────────────────────

def script_build(path: Path | str) -> str:
    """Short content hash of a script — the identity of the code on disk.

    Must match ``dashboard-server.BUILD``: md5 of the file bytes, first 12
    hex characters. Both sides hash the same bytes, so the two values are
    comparable without either side knowing the other's algorithm version.
    """
    try:
        return hashlib.md5(Path(path).read_bytes()).hexdigest()[:12]
    except OSError:
        return "unknown"


def served_build(port: int, timeout: float = 4.0) -> dict | None:
    """What the process on ``port`` says it is, via ``/api/build``.

    ``None`` means the port did not answer the question — either nothing is
    listening, or the running build predates the route. Both mean "not the
    build on disk", which is exactly what a caller needs to know.
    """
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/build")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


# ── who is listening ───────────────────────────────────────────────────────

def parse_netstat(text: str, port: int) -> list[int]:
    """PIDs of processes LISTENING on ``port``, from ``netstat -ano`` output.

    The state column is NOT used: on a German Windows it prints ``ABHÖREN``
    (measured on this install) instead of ``LISTENING``, so a state-word match
    silently found nothing — and a watchdog that finds nothing decides the
    service is down and starts a second copy. A listening socket is instead
    recognised by its foreign address being the wildcard port 0
    (``0.0.0.0:0`` / ``[::]:0``), which no locale translates.
    """
    pids: list[int] = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 5 or parts[0].upper() != "TCP":
            continue
        local, remote, pid = parts[1], parts[2], parts[4]
        # netstat prints ":8899" or "127.0.0.1:8899"; both end the local addr.
        if not local.endswith(f":{port}"):
            continue
        if not remote.endswith(":0"):
            continue
        if pid.isdigit() and int(pid) not in pids:
            pids.append(int(pid))
    return pids


def listener_pids(port: int) -> list[int]:
    """PIDs the OS says own ``port`` (empty when it cannot be read).

    ``Get-NetTCPConnection`` is preferred over ``netstat`` on Windows: it
    reports the owner as a number regardless of locale, and it names the owner
    of a socket that ``netstat`` leaves blank. Measured 2026-11-18 — netstat
    printed no listener row for :8899 at all (only WARTEND rows in German)
    while the port answered, which is exactly how a watchdog concludes "down"
    and starts a duplicate.
    """
    me = os.getpid()
    if os.name == "nt":
        ps = ("Get-NetTCPConnection -LocalPort " + str(port) + " -ErrorAction SilentlyContinue | "
              "Where-Object { $_.OwningProcess -ne 0 } | "
              "ForEach-Object { $_.OwningProcess } | Sort-Object -Unique")
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                               capture_output=True, text=True, timeout=25)
            pids = [int(x) for x in r.stdout.split() if x.isdigit()]
            if pids:
                return [p for p in pids if p != me]
        except Exception:
            pass
        try:
            r = subprocess.run(["netstat", "-ano"], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=10)
            return [p for p in parse_netstat(r.stdout, port) if p != me and p != 0]
        except Exception:
            return []
    try:
        r = subprocess.run(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
                           capture_output=True, text=True, timeout=10)
        return [int(x) for x in r.stdout.split() if x.strip().isdigit() and int(x) != me]
    except Exception:
        return []


def kill_pids(pids: list[int]) -> None:
    """Terminate each PID, ignoring the ones that already exited."""
    for pid in pids:
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(pid), "/F"],
                               capture_output=True, timeout=10)
            else:
                os.kill(pid, 9)
        except Exception:
            pass


# ── the verdict ────────────────────────────────────────────────────────────

# "Not supplied" and "supplied as None" are different answers: None means
# "nothing answered / nothing owns the port", which is exactly a drift verdict.
_UNSET = object()


def drift(port: int, script: Path | str, served=_UNSET,
          pids=_UNSET) -> tuple[bool, str]:
    """Is the thing answering on ``port`` the build that is on disk?

    Returns ``(needs_heal, reason)``. ``served``/``pids`` are injectable so the
    decision is testable without a live socket.
    """
    if served is _UNSET:
        served = served_build(port)
    if pids is _UNSET:
        pids = listener_pids(port)

    if not pids and served is None:
        return True, "not running"

    if len(pids) > 1:
        return True, f"{len(pids)} processes listening on :{port} ({pids})"

    on_disk = script_build(script)
    if served is None:
        return True, f":{port} answers but not with /api/build (build before identity) — served build is unknown, disk has {on_disk}"

    served_id = str(served.get("build", "unknown"))
    if served_id != on_disk:
        return True, f"stale build: served {served_id}, disk {on_disk}"
    return False, f"up, build {on_disk}"


def heal(port: int, script: Path | str, cmd: list[str], wait: float = 15.0,
         served=_UNSET) -> tuple[bool, str]:
    """Replace whatever serves ``port`` with the build on disk. Kill first.

    Killing every listener (not just the PID from a pid-file) is deliberate:
    the duplicate is usually a PID no file knows about. The process that
    ANSWERED is killed too, even when the OS does not list it as the owner.
    """
    if served is _UNSET:
        served = served_build(port, timeout=2)
    pids = listener_pids(port)
    if served is not None and isinstance(served.get("pid"), int) and served["pid"] not in pids:
        pids.append(served["pid"])
    if pids:
        kill_pids(pids)
        deadline = time.time() + 6
        while time.time() < deadline and listener_pids(port):
            time.sleep(0.3)

    kwargs: dict = {}
    if os.name == "nt":
        kwargs["creationflags"] = 0x00000008 | 0x00000200  # DETACHED | NEW_GROUP
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         stdin=subprocess.DEVNULL, close_fds=True, **kwargs)
    except Exception as exc:
        return False, f"spawn failed: {exc}"

    want = script_build(script)
    deadline = time.time() + wait
    while time.time() < deadline:
        time.sleep(0.7)
        got = served_build(port, timeout=2)
        if got and str(got.get("build")) == want:
            return True, f"serving build {want} (pid {got.get('pid')})"
    return False, f"did not answer with build {want} within {wait:.0f}s"


def main(argv: list[str]) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Report or heal a stale/duplicate local service.")
    ap.add_argument("--port", type=int, default=8899)
    ap.add_argument("--script", default=str(Path(__file__).with_name("dashboard-server.py")))
    ap.add_argument("--heal", action="store_true", help="replace the listener(s) with the disk build")
    args = ap.parse_args(argv)

    needs, reason = drift(args.port, args.script)
    if not needs:
        print(f"ok :{args.port} {reason}")
        return 0
    if not args.heal:
        print(f"drift :{args.port} {reason}")
        return 3

    print(f"heal :{args.port} {reason}")
    ok, detail = heal(args.port, args.script, [sys.executable, str(args.script)])
    print(("healed" if ok else "FAILED") + f" :{args.port} {detail}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

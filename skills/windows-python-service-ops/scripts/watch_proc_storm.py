#!/usr/bin/env python3
"""watch_proc_storm.py — attribute a process count to install roots, and check lock liveness.

Why this exists (live 19.09.26): a process census that reports a flat total ("156 procs!") sends
you at the wrong root. Grouping by install root, summing RSS, and cross-checking the lock holder
turns the number into a diagnosis — see SKILL.md, sections
"Process-storm measurement: group by install root" and
"Liveness of a lock-guarded daemon: ask the LOCK, not the pid file".

Also demonstrates the lock-liveness rule in code: for a lock-guarded singleton, a *read failure*
on the lock file is the POSITIVE evidence that a live process holds it, while a lock that reads
cleanly with a dead recorded pid is a stale artifact.

Usage
    python watch_proc_storm.py                          # defaults to session_to_brain.py
    python watch_proc_storm.py --marker online_learning.py
    python watch_proc_storm.py --marker myd.py --control   # negative control (expect 0 matches)

Exit codes
    0   census produced
    2   usage / runtime error
    3   --control was requested and the marker still matched (scanner cannot be trusted)

NOTE: written in a curator session where the shell was unavailable, so it has NOT been executed
yet. Run it once and fix it here if it misbehaves before relying on it in a cron path.
"""
from __future__ import annotations

import argparse
import collections
import os
import sys
import time
from pathlib import Path

try:
    import psutil
except ImportError:  # pragma: no cover - psutil is present in the laptop venv
    print("ERROR: psutil missing (pip install psutil)", file=sys.stderr)
    raise SystemExit(2)

SELF = Path(__file__).name


def _default_homes() -> list[Path]:
    """Candidate OpenAmer homes, env-first. Never hardcode a user path."""
    homes: list[Path] = []
    env = os.environ.get("OPENAMER_HOME")
    if env:
        homes.append(Path(env))
    la = os.environ.get("LOCALAPPDATA")
    if la:
        homes.append(Path(la) / "openamer-laptop")
        homes.append(Path(la) / "openamer")
    homes.append(Path.home() / ".openamer")
    seen, out = set(), []
    for h in homes:
        key = str(h).lower()
        if key not in seen:
            seen.add(key)
            out.append(h)
    return out


def _install_root(script_path: str) -> str:
    """<root>\\scripts\\foo.py -> <root>. Falls back to the containing dir."""
    if "\\scripts\\" in script_path:
        return script_path.rsplit("\\scripts\\", 1)[0]
    if "/scripts/" in script_path:
        return script_path.rsplit("/scripts/", 1)[0]
    return script_path


def census(marker: str) -> list[dict]:
    rows = []
    for p in psutil.process_iter(["pid", "name", "cmdline", "create_time", "memory_info"]):
        try:
            cmd = " ".join(p.info["cmdline"] or [])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        if marker not in cmd:
            continue
        # Self-match guard: a scanner that mentions the marker on its own command line counts
        # itself and its child. Exclude both this script's name and any inline -c invocation.
        if SELF in cmd or " -c " in cmd:
            continue
        script = ""
        for tok in cmd.split():
            if tok.endswith(marker):
                script = tok
                break
        try:
            rss = p.info["memory_info"].rss
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            rss = 0
        rows.append(
            {
                "pid": p.info["pid"],
                "root": _install_root(script) if script else "<unresolved>",
                "rss": rss,
                "age_h": (time.time() - p.info["create_time"]) / 3600.0,
            }
        )
    return rows


def lock_report(homes: list[Path], marker: str) -> None:
    stem = Path(marker).stem
    print("\nlock liveness (read failure = live holder):")
    any_found = False
    for home in homes:
        lk = home / f"{stem}.watch.lock"
        if not lk.exists():
            continue
        any_found = True
        try:
            holder = lk.read_text(encoding="utf-8", errors="replace").strip()
            alive = holder.isdigit() and psutil.pid_exists(int(holder))
            state = "STALE (readable, holder dead)" if not alive else "readable but holder alive?"
            print(f"  {lk}\n      holder={holder!r} alive={alive} -> {state}")
        except PermissionError:
            print(f"  {lk}\n      PermissionError -> LIVE HOLDER (exclusive lock is held)")
        except OSError as e:
            print(f"  {lk}\n      {type(e).__name__}: {e} -> treated as held")
    if not any_found:
        print(f"  no <stem>.watch.lock under any candidate home (checked {len(homes)})")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--marker", default="session_to_brain.py",
                    help="process marker to count (default: session_to_brain.py)")
    ap.add_argument("--control", action="store_true",
                    help="negative control: use a marker that cannot match; expect 0")
    a = ap.parse_args()

    marker = "definitely_not_a_real_daemon_xyz" if a.control else a.marker
    rows = census(marker)

    print(f"marker: {marker}")
    print(f"LIVE matching processes: {len(rows)}   total RSS: {sum(r['rss'] for r in rows)/1024/1024:.0f} MB")
    if rows:
        by_root = collections.Counter(r["root"] for r in rows)
        print("by install root:")
        for root, n in by_root.most_common():
            mb = sum(r["rss"] for r in rows if r["root"] == root) / 1024 / 1024
            print(f"  {n:4d} x  {mb:6.0f} MB  {root}")
        ages = sorted(r["age_h"] for r in rows)
        print(f"age(h): min={ages[0]:.1f} median={ages[len(ages)//2]:.1f} max={ages[-1]:.1f}")

    if a.control:
        if rows:
            print("CONTROL FAILED: a marker that cannot match found matches -> scanner is unsound")
            return 3
        print("CONTROL OK: 0 matches for an impossible marker")
        return 0

    lock_report(_default_homes(), marker)
    return 0


if __name__ == "__main__":
    sys.exit(main())

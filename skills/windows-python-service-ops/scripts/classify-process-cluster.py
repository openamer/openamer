#!/usr/bin/env python
"""Classify a Windows daemon process cluster: healthy launcher pair vs. true duplicates.

Usage:
    python classify-process-cluster.py "online_learning.py --loop"
    python classify-process-cluster.py "tool_server.py"

Why this exists: a venv-launched daemon spawns TWO python.exe (venv launcher parent +
its uv child). Naive "keep oldest, kill the rest" watchdogs read that pair as duplicates and
kill the child -- which drags the parent down and takes the daemon offline. This script
classifies by ParentProcessId instead of PID order, and only an INDEPENDENT ROOT (a PID whose
parent is not itself in the matched set) counts as a separate instance.

Implementation notes:
  * PowerShell is invoked with subprocess list-args, so no shell is involved -> `$_` is never
    touched by MSYS/git-bash quoting, and no temp .ps1 is needed.
  * ConvertTo-Csv gives machine-parseable output; select ProcessId,ParentProcessId,CommandLine.
  * `@(...)`/scalar pitfalls do not apply here because parsing happens in Python.

Exit codes:
    0 = exactly ONE root (healthy, incl. the normal parent/child pair) -> DO NOTHING
    1 = zero matches (dead) or 2+ independent roots (real duplicates) -> caller decides
    2 = could not read the process table (PowerShell missing / failed)
"""
import csv
import io
import subprocess
import sys
from collections import defaultdict


def fetch(pattern: str):
    ps = (
        "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
        "Where-Object { $_.CommandLine -like '*%s*' } | "
        "Select-Object ProcessId,ParentProcessId,CommandLine | "
        "ConvertTo-Csv -NoTypeInformation" % pattern
    )
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, errors="replace",
        )
    except FileNotFoundError:
        return None
    if r.returncode != 0 and not (r.stdout or "").strip():
        return None
    # CIM output through MSYS occasionally arrives UTF-16 with NULs.
    return (r.stdout or "").replace("\x00", "").strip()


def main() -> int:
    pattern = sys.argv[1] if len(sys.argv) > 1 else "online_learning.py --loop"
    text = fetch(pattern)
    if text is None:
        print("ERROR: could not read process table (powershell failed)")
        return 2

    rows = [d for d in csv.DictReader(io.StringIO(text)) if (d.get("ProcessId") or "").strip()]
    if not rows:
        print("MATCHES=0")
        print("NO_PROCS_FOUND")
        return 1

    parent = {}
    cmdline = {}
    for d in rows:
        try:
            pid = int(d["ProcessId"])
            ppid = int(d["ParentProcessId"])
        except (TypeError, ValueError):
            continue
        parent[pid] = ppid
        cmdline[pid] = (d.get("CommandLine") or "").strip()

    children = defaultdict(list)
    for pid, ppid in parent.items():
        children[ppid].append(pid)

    # A root is a matched process whose parent is NOT itself a matched process.
    roots = sorted(pid for pid, ppid in parent.items() if ppid not in parent)

    print("MATCHES=%d" % len(parent))
    print("ROOTS=%d" % len(roots))
    for pid in roots:
        kids = sorted(children.get(pid, []))
        is_uv = "*uv*" in (" ".join(cmdline.get(k, "") for k in [pid] + kids)).lower()
        print("ROOT pid=%d children=%s uv_in_chain=%s" % (pid, kids, is_uv))

    if len(roots) == 1:
        print("TWIN_OK -- 1 root + %d child = ONE healthy daemon; DO NOT KILL anything"
              % (len(parent) - 1))
        return 0

    if len(roots) == 0:
        print("NO_PROCS_FOUND")
        return 1

    print("DUPLICATE_ROOTS=%d -- kill the WHOLE younger root(s) INCLUDING their children "
          "(Stop-Process -Id <root> -Force). NEVER kill a lone child: it drags its parent down."
          % len(roots))
    return 1


if __name__ == "__main__":
    sys.exit(main())

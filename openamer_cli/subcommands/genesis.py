#!/usr/bin/env python3
"""openamer genesis - the 24 Genesis Directives as the system measures them.

``agent/genesis_directives.py`` carries the directive TEXT into the system
prompt. ``agent/directive_status.py`` records a hand-written verdict. This
command shows what the NATIVE RUNTIME measured on its last tick
(``agent/genesis_runtime.py``).

    openamer genesis            # live table from the last tick
    openamer genesis --json     # machine-readable rows
    openamer genesis --tick     # measure now, persist, print
    openamer genesis --gates    # only the closed gates and what would open them
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_runtime():
    repo = _repo_root()
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))
    from agent import genesis_runtime

    return genesis_runtime


def _cmd_genesis(args) -> int:
    rt = _load_runtime()

    if getattr(args, "tick", False):
        state = rt.tick()
    else:
        state = rt.read_state()
        if state is None:
            # Never measured on this install yet — measure once instead of
            # printing an empty table (the gateway tick keeps it fresh after).
            state = rt.tick()

    rows = state.get("directives", [])
    measured_at = state.get("measured_at")
    age = time.time() - measured_at if isinstance(measured_at, (int, float)) else None

    if getattr(args, "gates", False):
        closed = [row for row in rows if row.get("gate_state") == "closed"]
        print(f"{len(closed)} closed gate(s) — what each one waits for:\n")
        for row in closed:
            print(f"{row['id']}  {row['mark']} {row['status']:<11} {row['title']}")
            print(f"        gate : {row['gate']}")
            print(f"        now  : {row['measured']}")
            print(f"        then : {row['unblocks']}")
            print(f"        owner: {row['integration']}")
        return 0

    if getattr(args, "json", False):
        print(
            json.dumps(
                {
                    "measured_at": measured_at,
                    "measured_at_iso": state.get("measured_at_iso"),
                    "age_seconds": None if age is None else round(age),
                    "summary": state.get("summary"),
                    "changes": state.get("changes", []),
                    "directives": rows,
                },
                indent=2,
            )
        )
        return 0

    print(rt.render(rows, age_s=age))
    changes = state.get("changes") or []
    if changes:
        moved = ", ".join(f"{c['id']} {c['from']}→{c['to']}" for c in changes)
        print(f"\nchanged since the previous tick: {moved}")
    return 0


def build_genesis_parser(subparsers) -> None:
    """Wire `openamer genesis`."""
    p = subparsers.add_parser(
        "genesis",
        help="Die 24 Genesis-Direktiven, wie das System sie misst (nativ, getaktet)",
        description=(
            "Zeigt fuer jede Genesis-Direktive den gemessenen Status: welche Integration "
            "sie besitzt, welches Gate offen oder geschlossen ist, was der Probe gerade "
            "gesehen hat, und was passiert, sobald das Gate aufgeht. Die Messung laeuft "
            "nativ im Core (Gateway-Housekeeping, eigenes Intervall) und schreibt "
            "memory/genesis/state.json plus Heartbeat."
        ),
    )
    p.add_argument("--json", action="store_true", help="JSON-Ausgabe")
    p.add_argument("--tick", action="store_true", help="jetzt messen und persistieren")
    p.add_argument("--gates", action="store_true", help="nur geschlossene Gates + Voraussetzung")
    p.set_defaults(func=_cmd_genesis)

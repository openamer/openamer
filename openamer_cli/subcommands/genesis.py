#!/usr/bin/env python3
"""openamer genesis - what actually stands behind the 24 Genesis Directives.

The directives themselves are text in the system prompt (agent/genesis_directives.py).
This command answers the only question that text cannot: which of them has code,
which is only partly there, and which is blocked on a named prerequisite.

    openamer genesis          # table
    openamer genesis --json   # machine-readable rows
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _cmd_genesis(args) -> int:
    repo = _repo_root()
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))
    from agent import directive_status as ds

    rows = ds.measure(repo)
    if getattr(args, "json", False):
        print(json.dumps({"directives": rows, "summary": ds.summary(rows)}, indent=2))
        return 0
    print(ds.render(rows))
    if any(row["status"] == "missing" for row in rows):
        return 1
    return 0


def build_genesis_parser(subparsers) -> None:
    """Wire `openamer genesis`."""
    p = subparsers.add_parser(
        "genesis",
        help="Status der 24 Genesis-Direktiven (Code, Teil, GATED)",
        description=(
            "Zeigt fuer jede Genesis-Direktive, was wirklich dahintersteht: Code+Tests "
            "(implemented), teilweise vorhanden (partial) oder GATED mit deklarierter "
            "Voraussetzung. Jede Evidenz wird gegen das Dateisystem geprueft."
        ),
    )
    p.add_argument("--json", action="store_true", help="JSON-Ausgabe")
    p.set_defaults(func=_cmd_genesis)

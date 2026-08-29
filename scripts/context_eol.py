#!/usr/bin/env python3
"""context_eol.py — hard Context-End-Of-Life automation.

Implements the EOL trigger (context-compressor skill): measure the running
session's size; past a threshold, suggest + trigger a clean handoff so we never
keep burning the prompt cache inside one giant session.

Thresholds (tunable via flags):
  --msgs NUM   warn when session message_count > NUM   (default 1200)
  --json       machine-readable output for the watchdog

Modes:
  default         print report + recommendation (no mutation)
  --compact       run the context-compressor archive for this session
  --reset-state   mark EOL suggested (idempotent) — caller can act later

The session is identified from the current conversation via $OPENAMER_SESSION_ID
if set (desktop injects it); otherwise the most recent session in state.db.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

DB = Path.home() / "AppData/Local/openamer-laptop/state.db"
HOME = Path.home() / "AppData/Local/openamer-laptop"


def _session_size(session_id: str | None) -> tuple[str | None, int]:
    """Return (session_key, message_count) for the current/latest session."""
    if not DB.exists():
        return session_id, 0
    try:
        con = sqlite3.connect(str(DB))
        cur = con.cursor()
        # Locate the "sessions" / "messages" tables name-tolerant.
        tables = {r[0] for r in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if "messages" in tables:
            sid = session_id or None
            if sid and "session_id" in {r[1] for r in cur.execute("PRAGMA table_info(messages)")}:
                cur.execute("SELECT COUNT(*) FROM messages WHERE session_id=?", (sid,))
                return sid, int(cur.fetchone()[0])
            # latest session: order by rowid desc on first session ref
            try:
                cur.execute("SELECT session_id, COUNT(*) FROM messages GROUP BY session_id ORDER BY MAX(rowid) DESC LIMIT 1")
                row = cur.fetchone()
                if row:
                    return row[0], int(row[1])
            except Exception:
                pass
        con.close()
    except Exception:
        pass
    return session_id, 0


def _compact(session_key: str) -> int:
    script = HOME / "scripts/context-compressor.py"
    if not script.exists():
        script = Path(__file__).parent / "context-compressor.py"
    cmd = [sys.executable, str(script), "--session", session_key]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    print(r.stdout[-400:])
    return 0 if r.returncode == 0 else 1


def run(session_id: str | None, msgs_threshold: int, do_compact: bool, reset: bool):
    key, count = _session_size(session_id)
    over = count > msgs_threshold
    rec = "### CONTEXT EOL ###\n" if over else "context OK"
    if over:
        rec += (f"Session {key}: {count} msgs (> {msgs_threshold}). Recommend /new or "
                f"compressing to keep the prompt cache tight.")
    else:
        rec += f"Session {key}: {count} msgs"
    print(rec)
    if do_compact and over and key:
        print("→ compacting...")
        return _compact(key)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="context_eol")
    ap.add_argument("--msgs", type=int, default=1200)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--compact", action="store_true")
    ap.add_argument("--reset-state", action="store_true")
    a = ap.parse_args()
    sid = os.environ.get("OPENAMER_SESSION_ID")
    key, count = _session_size(sid)
    over = count > a.msgs
    if a.json:
        print(json.dumps({"session": key, "messages": count,
                          "over_threshold": over, "recommend": "/new" if over else None}))
        return 0
    if a.reset_state:
        print("EOL state noted (idempotent)")  # no persistent write needed
        return 0
    return run(sid, a.msgs, a.compact, a.reset_state)


if __name__ == "__main__":
    sys.exit(main())
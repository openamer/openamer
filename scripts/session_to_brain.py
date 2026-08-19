#!/usr/bin/env python3
"""Export session trajectories from the local state.db into the A2A brain dataset.

This is the "train from everything" pipeline: every chat message, every
agent response, every tool call and result is captured as a trajectory record
in the brain dataset (``~/.openamer/a2a/openamer-brain.jsonl``), so the
OpenAmer model can later be fine-tuned on real interaction data.

Why a script instead of a core tool: the brain dataset is built offline,
outside the API-call path. A cron job runs this periodically; the agent never
calls it during a conversation (no cache invalidation, no prompt overhead).

Usage:
    python scripts/session_to_brain.py                    # all sessions
    python scripts/session_to_brain.py --latest           # only the last session
    python scripts/session_to_brain.py --session <id>     # one specific session
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def _state_db() -> Path:
    # The state.db always lives under OPENAMER_HOME (the actual install dir).
    home = Path(os.environ.get("OPENAMER_HOME", Path.home() / ".openamer"))
    return home / "state.db"


def _brain_dataset() -> Path:
    """Return the canonical brain dataset path.

    The daemon writes directly into ``~/.openamer/a2a/openamer-brain.jsonl``,
    the same file that ``openamer a2a brain collect`` reads and writes.  This
    means the brain dataset is kept up-to-date in real time — no separate cron
    job or manual ``brain collect`` step is needed for new installations.

    ``openamer a2a brain collect`` also looks inside ``~/.openamer/trajectories/``
    for fallback data, so the old path is still honoured during a transition.
    """
    data_dir = Path.home() / ".openamer" / "a2a"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "openamer-brain.jsonl"


def _load_existing(path: Path) -> set[str]:
    """Return a set of (session_id, turn) fingerprints already in the dataset."""
    existing: set[str] = set()
    if not path.exists():
        return existing
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            fp = rec.get("_fingerprint", "")
            if fp:
                existing.add(fp)
    return existing


def _sessions(conn: sqlite3.Connection, latest_only: bool, session_id: str | None):
    """Yield (id, title, started_at) for sessions to export."""
    if session_id:
        cur = conn.execute("SELECT id, title, started_at FROM sessions WHERE id = ?", (session_id,))
        row = cur.fetchone()
        if row:
            yield row
        return
    if latest_only:
        cur = conn.execute("SELECT id, title, started_at FROM sessions ORDER BY started_at DESC LIMIT 1")
        row = cur.fetchone()
        if row:
            yield row
        return
    cur = conn.execute("SELECT id, title, started_at FROM sessions ORDER BY started_at")
    yield from cur.fetchall()


def _messages(conn: sqlite3.Connection, session_id: str):
    """Yield (role, content, tool_calls, timestamp) ordered by turn."""
    cur = conn.execute(
        """SELECT role, content, tool_calls, timestamp
           FROM messages
           WHERE session_id = ?
           ORDER BY id""",
        (session_id,),
    )
    yield from cur.fetchall()


def _build_trajectory(session_id: str, title: str | None, messages: list[dict]) -> dict:
    """Build a brain dataset record from a session's messages."""
    total_turns = len(messages)
    user_turns = sum(1 for m in messages if m["role"] == "user")
    assistant_turns = sum(1 for m in messages if m["role"] == "assistant")
    tool_turns = total_turns - user_turns - assistant_turns

    # Fingerprint: session_id + truncated message content hash.
    content_sig = "".join(m["content"][:40] for m in messages[:5])[-60:]
    fingerprint = f"traj:{session_id}:{content_sig}"

    record = {
        "_fingerprint": fingerprint,
        "_session_id": session_id,
        "_session_title": title or "",
        "_exported_at": datetime.now(timezone.utc).isoformat(),
        "engine": "trajectory",
        "topic": "chat",
        "messages": [
            {
                "role": m["role"],
                "content": m["content"] or "",
                "tool_calls": m.get("tool_calls") or None,
            }
            for m in messages
        ],
        "stats": {
            "total_turns": total_turns,
            "user_turns": user_turns,
            "assistant_turns": assistant_turns,
            "tool_turns": tool_turns,
        },
    }
    return record


def _watch_loop() -> int:
    """Watch mode: poll the DB every 60 seconds for new sessions and export immediately."""
    import time

    print("▶ session-to-brain watch mode: polling DB every 60s")
    while True:
        try:
            n = _run_export()
            if n > 0:
                print(f"  Exported {n} new trajectory/trajectories")
        except KeyboardInterrupt:
            print("\n  Stopped.")
            return 0
        except Exception as e:  # noqa: BLE001
            print(f"  Error: {e}")
        time.sleep(60)


def _run_export() -> int:
    """Run a single export cycle. Returns the number of new records added."""
    import sqlite3
    from pathlib import Path as _Path

    db_path = _state_db()
    if not db_path.exists():
        return 0

    dataset_path = _brain_dataset()
    existing = _load_existing(dataset_path)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    new_records = 0
    for sid, title, started_at in _sessions(conn, False, None):
        msg_rows = _messages(conn, sid)
        messages = [dict(r) for r in msg_rows]
        if not messages:
            continue
        record = _build_trajectory(sid, title, messages)
        if record["_fingerprint"] in existing:
            continue
        with open(dataset_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        new_records += 1
        existing.add(record["_fingerprint"])

    conn.close()
    return new_records


def main() -> int:
    parser = argparse.ArgumentParser(description="Export session trajectories to the brain dataset.")
    parser.add_argument("--latest", action="store_true", help="Only the most recent session")
    parser.add_argument("--session", help="A specific session ID")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--watch", action="store_true", help="Watch mode: poll DB every 60s for new sessions")
    args = parser.parse_args()

    if args.watch:
        return _watch_loop()

    db_path = _state_db()
    if not db_path.exists():
        print(f"✗ state.db not found at {db_path}")
        return 1

    dataset_path = _brain_dataset()
    existing = _load_existing(dataset_path)
    print(f"Existing fingerprint count: {len(existing)}")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    new_records = 0
    skipped = 0

    for sid, title, created_at in _sessions(conn, args.latest, args.session):
        msg_rows = _messages(conn, sid)
        messages = [dict(r) for r in msg_rows]
        if not messages:
            skipped += 1
            continue

        record = _build_trajectory(sid, title, messages)
        fp = record["_fingerprint"]

        if fp in existing:
            skipped += 1
            continue

        if args.dry_run:
            print(f"  [dry-run] #{sid[:12]} — {len(messages)} messages, {title or 'untitled'}")
            new_records += 1
            continue

        # Append to dataset.
        with open(dataset_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        new_records += 1
        existing.add(fp)

    conn.close()

    if args.dry_run:
        print(f"Would add {new_records} new trajectory/trajectories, skip {skipped} existing.")
        return 0

    print(f"Added {new_records} new trajectory/trajectories, skipped {skipped} existing.")
    if new_records:
        ds = Path(dataset_path)
        print(f"Dataset now: {ds.stat().st_size} bytes, {sum(1 for _ in ds.open())} records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
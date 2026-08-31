#!/usr/bin/env python3
"""openamer replay — Time-machine for agent sessions.

Unique capabilities:
  * openamer replay <session>           -> interactive HTML timeline
  * openamer replay <session> --fork N  -> context-pack to restart a NEW agent
                                           run from message N (what-if debugging)

Read-only over state.db. Writes only its own output files.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from html import escape
from pathlib import Path

OPENAMER_HOME = Path(__file__).resolve().parent.parent
DEFAULT_DB = OPENAMER_HOME / "state.db"
OUT_DIR = OPENAMER_HOME / "replays"

ROLE_COLORS = {
    "user": "#2563eb",
    "assistant": "#059669",
    "tool": "#d97706",
    "system": "#6b7280",
}


def connect(db_path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    return db


def find_session(db: sqlite3.Connection, needle: str) -> sqlite3.Row:
    """Find a session by id prefix, then by title substring. Empty = newest."""
    if needle:
        row = db.execute(
            "SELECT * FROM sessions WHERE id LIKE ? ORDER BY started_at DESC LIMIT 1",
            (needle + "%",),
        ).fetchone()
        if row is None:
            row = db.execute(
                "SELECT * FROM sessions WHERE title LIKE ? ORDER BY started_at DESC LIMIT 1",
                ("%" + needle + "%",),
            ).fetchone()
        if row is None:
            raise SystemExit(f"session not found: {needle!r}")
        return row
    return db.execute(
        "SELECT * FROM sessions ORDER BY started_at DESC LIMIT 1"
    ).fetchone()


def fetch_messages(db: sqlite3.Connection, session_id: str) -> list:
    return db.execute(
        "SELECT id, role, content, tool_name, tool_calls, timestamp, token_count "
        "FROM messages WHERE session_id = ? AND active = 1 "
        "ORDER BY timestamp, id",
        (session_id,),
    ).fetchall()


def summarize_tool_calls(raw: str | None) -> list[dict]:
    if not raw:
        return []
    try:
        calls = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    out = []
    for c in calls if isinstance(calls, list) else [calls]:
        name = c.get("name") or c.get("function", {}).get("name", "?")
        args = c.get("arguments") or c.get("function", {}).get("arguments") or ""
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except (json.JSONDecodeError, TypeError):
                args = {"raw": args[:300]}
        out.append({"name": name, "args": args})
    return out


# ---------------------------------------------------------------- HTML export

def build_timeline(session, messages, out_path: Path) -> None:
    t0 = None
    events = []
    for m in messages:
        ts = m["timestamp"] or 0
        if t0 is None:
            t0 = ts
        events.append(
            {
                "id": m["id"],
                "role": m["role"],
                "tool": m["tool_name"],
                "tokens": m["token_count"] or 0,
                "dt": round((ts - t0), 3),
                "content": (m["content"] or "")[:4000],
                "calls": summarize_tool_calls(m["tool_calls"]),
            }
        )
    total_tokens = sum(e["tokens"] for e in events)
    tool_events = [e for e in events if e["calls"]]
    tool_names: dict[str, int] = {}
    for e in tool_events:
        for c in e["calls"]:
            tool_names[c["name"]] = tool_names.get(c["name"], 0) + 1
    top_tools = sorted(tool_names.items(), key=lambda kv: -kv[1])[:12]

    chart_rows = "".join(
        f'<div class="ev {e["role"]}" style="left:{min(e["dt"] / duration * 100, 100):.2f}%" '
        f'title="#{e["id"]} {e["role"]} {escape(e["tool"] or "")} +{e["dt"]:.1f}s"></div>'
        for e in events
        if duration > 0
    ) if (duration := max((e["dt"] for e in events), default=0)) > 0 else ""

    feed_rows = []
    for e in events:
        calls_html = "".join(
            f'<span class="chip" title="{escape(json.dumps(c["args"], ensure_ascii=False)[:500])}">'
            f"{escape(c['name'])}</span>"
            for c in e["calls"]
        )
        body = escape(e["content"][:1200])
        feed_rows.append(
            f'<div class="msg {e["role"]}" id="m{e["id"]}">'
            f'<div class="head">#{e["id"]} · {e["role"]}'
            f'{" · " + escape(e["tool"]) if e["tool"] else ""}'
            f' · +{e["dt"]:.1f}s · {e["tokens"]} tok'
            f'<a class="fork" href="#" onclick="fork({e["id"]});return false">⏪ fork from here</a></div>'
            f'<div class="chips">{calls_html}</div>'
            f"<pre>{body}</pre></div>"
        )
    legend = "".join(
        f'<span class="lg" style="background:{ROLE_COLORS.get(r, "#888")}">{r}</span>'
        for r in ("user", "assistant", "tool", "system")
    )
    tool_bars = "".join(
        f'<div class="bar"><span>{escape(n)}</span><div style="width:{c / max(top_tools[0][1], 1) * 100:.0f}%"></div><b>{c}</b></div>'
        for n, c in top_tools
    )
    html = f"""<!doctype html><html><head><meta charset="utf-8">
<title>OpenAmer Replay — {escape(session["title"] or session["id"])}</title>
<style>
body{{font-family:Segoe UI,sans-serif;margin:0;background:#f8fafc;color:#0f172a}}
header{{padding:16px 24px;background:#fff;border-bottom:1px solid #e2e8f0;position:sticky;top:0;z-index:2}}
h1{{font-size:18px;margin:0 0 4px}} .meta{{color:#64748b;font-size:13px}}
.stats span{{background:#eef2ff;color:#4338ca;border-radius:6px;padding:2px 8px;margin-right:6px;font-size:12px}}
#timeline{{height:34px;background:#fff;border-bottom:1px solid #e2e8f0;position:relative;margin:0}}
.ev{{position:absolute;top:8px;width:3px;height:18px;border-radius:2px}}
.ev.user{{background:{ROLE_COLORS["user"]}}}.ev.assistant{{background:{ROLE_COLORS["assistant"]}}}
.ev.tool{{background:{ROLE_COLORS["tool"]}}}.ev.system{{background:{ROLE_COLORS["system"]}}}
main{{display:flex;gap:0}}
#feed{{flex:1;padding:12px 20px 60px;max-width:900px}}
.msg{{background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:10px 14px;margin:8px 0}}
.msg.user{{border-left:4px solid {ROLE_COLORS["user"]}}}
.msg.assistant{{border-left:4px solid {ROLE_COLORS["assistant"]}}}
.msg.tool{{border-left:4px solid {ROLE_COLORS["tool"]}}}
.head{{font-size:12px;color:#64748b;margin-bottom:4px}}
.fork{{float:right;color:#7c3aed;text-decoration:none;font-size:12px}}
.chips{{margin:4px 0}} .chip{{background:#fef3c7;color:#92400e;border-radius:5px;padding:1px 7px;font-size:11px;margin-right:4px;font-family:monospace}}
pre{{white-space:pre-wrap;word-break:break-word;font-size:13px;margin:0;font-family:Consolas,monospace}}
#tools{{width:260px;padding:16px;border-left:1px solid #e2e8f0;background:#fff}}
.bar{{display:flex;align-items:center;gap:6px;font-size:12px;margin:5px 0}}
.bar span{{width:130px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.bar div{{height:10px;background:#818cf8;border-radius:4px}}
.lg{{color:#fff;border-radius:4px;padding:1px 6px;font-size:11px;margin-right:4px}}
</style></head><body>
<header><h1>⏪ OpenAmer Replay — {escape(session["title"] or session["id"])}</h1>
<div class="meta">{escape(session["id"])} · {escape(str(session["started_at"]))} · model {escape(str(session["model"] or "?"))}
· cost ${session["estimated_cost_usd"] or 0:.4f} · rewind_count {session["rewind_count"]}</div>
<div class="stats"><span>{len(events)} events</span><span>{total_tokens} tokens</span>
<span>{len(tool_events)} tool-calls</span><span>{duration:.0f}s duration</span>{legend}</div></header>
<div id="timeline">{chart_rows}</div>
<main><div id="feed">{''.join(feed_rows)}</div>
<div id="tools"><h3>Top-Tools</h3>{tool_bars or '<i>none</i>'}</div></main>
<script>
function fork(mid){{
  window.open('openamer://replay-fork?session={session["id"]}&message='+mid, '_blank');
  navigator.clipboard && navigator.clipboard.writeText('openamer replay {session["id"]} --fork '+mid);
}}
</script></body></html>"""
    out_path.write_text(html, encoding="utf-8")


# ---------------------------------------------------------------- fork export

def build_fork_pack(session, messages, fork_id: int, out_path: Path) -> Path:
    pack = {
        "kind": "openamer-replay-fork",
        "version": 1,
        "source_session": session["id"],
        "fork_from_message": fork_id,
        "parent_session_id": session["id"],
        "model": session["model"],
        "system_prompt": session["system_prompt"],
        "title": f"[fork of {session['title'] or session['id']}]",
        "messages": [
            {
                "id": m["id"],
                "role": m["role"],
                "content": m["content"],
                "tool_name": m["tool_name"],
                "tool_calls": summarize_tool_calls(m["tool_calls"]),
                "timestamp": m["timestamp"],
            }
            for m in messages
            if m["id"] <= fork_id
        ],
        "context_note": (
            "Replay-fork context pack. Messages up to and including fork_from_message. "
            "Feed 'messages' into a fresh agent session as conversation history to "
            "continue from exactly this point in the past."
        ),
    }
    out_path.write_text(
        json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return out_path


# ---------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="openamer replay")
    p.add_argument("session", nargs="?", default="", help="session id / title fragment (empty = newest)")
    p.add_argument("--fork", type=int, metavar="MSG_ID", help="create a fork context-pack at message MSG_ID")
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument("--open", action="store_true", help="open the HTML in the browser")
    args = p.parse_args(argv)

    db = connect(args.db)
    session = find_session(db, args.session)
    messages = fetch_messages(db, session["id"])
    if not messages:
        raise SystemExit("session has no active messages")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    html_path = OUT_DIR / f"replay-{session['id']}.html"
    build_timeline(session, messages, html_path)

    if args.fork is not None:
        known = {m["id"] for m in messages}
        if args.fork not in known:
            raise SystemExit(f"--fork: message id {args.fork} not in this session")
        pack_path = OUT_DIR / f"fork-{session['id']}-{args.fork}.json"
        build_fork_pack(session, messages, args.fork, pack_path)
        print(f"✓ Fork context-pack: {pack_path}")

    print(f"✓ Timeline ({len(messages)} events): {html_path}")
    if args.open:
        import webbrowser

        webbrowser.open(html_path.as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())

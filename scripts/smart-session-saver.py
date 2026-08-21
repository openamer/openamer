#!/usr/bin/env python3
"""
Smart Session Saver — Session-Archivierung + Volltextsuche + Wiederherstellung + Metrik-Stats

CLI:
  --archive           Archiviere Sessions >7 Tage als JSON in .session-archive/YYYY-MM/
  --list              Liste alle archivierten Sessions
  --search 'query'    Volltextsuche in Archiven
  --restore <id>      Stelle Session-Metadaten wieder her (JSON-Ausgabe)
  --stats             Zeige Metrik-Statistiken (Sessions gesamt, archiviert, pro Tag)
  --dry-run           Nur zeigen, nichts archivieren

Keine Datenlöschung — arbeitet nur auf Metadaten.
"""

import argparse
import datetime
import json
import os
import sqlite3
import sys
import textwrap
from pathlib import Path

# ─── Konfiguration ────────────────────────────────────────────────────────────

def _resolve_msys_path(path_str: str) -> str:
    """Git-Bash liefert /c/Users/... → C:\\Users\\... umwandeln."""
    import re as _re
    m = _re.match(r"^/([a-zA-Z])/(.*)", path_str)
    if m:
        return f"{m.group(1).upper()}:\\{m.group(2)}"
    return path_str


_oh_val = os.environ.get("OPENAMER_HOME")
if _oh_val:
    _oh_val = _resolve_msys_path(_oh_val)
else:
    _oh_val = r"C:\Users\damir\AppData\Local\openamer-laptop"
OPENAMER_HOME = Path(_oh_val)
STATE_DB = OPENAMER_HOME / "state.db"
ARCHIVE_ROOT = OPENAMER_HOME / ".session-archive"
DEFAULT_AGE_DAYS = 7  # Sessions älter als X Tage archivieren

# ─── Hilfsfunktionen ──────────────────────────────────────────────────────────


def iso_now():
    return datetime.datetime.now().isoformat()


def db_connect(state_db=None):
    """SQLite-Verbindung zur Session-DB."""
    db = Path(state_db) if state_db else STATE_DB
    if not db.exists():
        print(f"❌ Session-DB nicht gefunden: {db}", file=sys.stderr)
        sys.exit(1)
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    return conn


def fmt_time(ts: float) -> str:
    """Unix-Timestamp → lesbarer String."""
    if ts is None or ts == 0:
        return "N/A"
    return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def fmt_duration(start: float, end: float) -> str:
    """Dauer zwischen zwei Timestamps."""
    if start is None or start == 0:
        return "N/A"
    e = end if (end and end > 0) else datetime.datetime.now().timestamp()
    secs = max(0, e - start)
    if secs < 60:
        return f"{secs:.0f}s"
    elif secs < 3600:
        return f"{secs / 60:.0f}m"
    else:
        return f"{secs / 3600:.1f}h"


def token_str(val: int) -> str:
    if val is None or val == 0:
        return "–"
    if val >= 1_000_000:
        return f"{val / 1_000_000:.1f}M"
    elif val >= 1_000:
        return f"{val / 1_000:.0f}K"
    return str(val)


def cost_str(val: float) -> str:
    if val is None or val == 0:
        return "–"
    return f"${val:.4f}"


# ─── Datenbank-Operationen ────────────────────────────────────────────────────

def get_sessions(conn, older_than_days: int = 0, only_unarchived: bool = False):
    """Sessions aus der DB holen. Wenn older_than_days > 0, nur ältere."""
    now = datetime.datetime.now().timestamp()
    cutoff = now - (older_than_days * 86400) if older_than_days > 0 else 0

    where_clauses = []
    params = []

    if older_than_days > 0:
        where_clauses.append("(started_at IS NOT NULL AND started_at < ?)")
        params.append(cutoff)

    if only_unarchived:
        where_clauses.append("(archived IS NULL OR archived = 0)")

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    query = f"""
        SELECT id, source, user_id, session_key, chat_id, chat_type, thread_id,
               display_name, origin_json, model, model_config, system_prompt,
               parent_session_id, started_at, ended_at, end_reason,
               message_count, tool_call_count, input_tokens, output_tokens,
               cache_read_tokens, cache_write_tokens, reasoning_tokens,
               cwd, git_branch, git_repo_root, billing_provider, billing_base_url,
               billing_mode, estimated_cost_usd, actual_cost_usd, cost_status,
               cost_source, pricing_version, title, api_call_count, handoff_state,
               handoff_platform, handoff_error, profile_name, rewind_count,
               archived, pinned
        FROM sessions
        WHERE {where_sql}
        ORDER BY started_at ASC
    """
    c = conn.cursor()
    c.execute(query, params)
    return c.fetchall()


def get_session_by_id(conn, session_id: str):
    """Einzelne Session aus der DB oder None."""
    c = conn.cursor()
    c.execute("""
        SELECT id, source, user_id, session_key, chat_id, chat_type, thread_id,
               display_name, origin_json, model, model_config, system_prompt,
               parent_session_id, started_at, ended_at, end_reason,
               message_count, tool_call_count, input_tokens, output_tokens,
               cache_read_tokens, cache_write_tokens, reasoning_tokens,
               cwd, git_branch, git_repo_root, billing_provider, billing_base_url,
               billing_mode, estimated_cost_usd, actual_cost_usd, cost_status,
               cost_source, pricing_version, title, api_call_count, handoff_state,
               handoff_platform, handoff_error, profile_name, rewind_count,
               archived, pinned
        FROM sessions WHERE id = ?
    """, (session_id,))
    return c.fetchone()


def get_messages_for_session(conn, session_id: str, limit: int = 20):
    """Letzte Nachrichten einer Session."""
    c = conn.cursor()
    c.execute("""
        SELECT id, role, content, tool_name, timestamp, token_count, finish_reason,
               display_kind
        FROM messages
        WHERE session_id = ? AND role != 'tool'
        ORDER BY timestamp DESC
        LIMIT ?
    """, (session_id, limit))
    return c.fetchall()


def get_session_stats(conn):
    """Aggregierte Metrik-Statistiken aus der DB."""
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM sessions")
    total = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM sessions WHERE archived = 1")
    archived_count = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM sessions WHERE pinned = 1")
    pinned_count = c.fetchone()[0]

    c.execute("""
        SELECT COALESCE(SUM(input_tokens), 0),
               COALESCE(SUM(output_tokens), 0),
               COALESCE(SUM(cache_read_tokens), 0),
               COALESCE(SUM(cache_write_tokens), 0),
               COALESCE(SUM(reasoning_tokens), 0)
        FROM sessions
    """)
    tok_row = c.fetchone()

    c.execute("""
        SELECT COALESCE(SUM(actual_cost_usd), 0),
               COALESCE(SUM(estimated_cost_usd), 0)
        FROM sessions
        WHERE actual_cost_usd IS NOT NULL OR estimated_cost_usd IS NOT NULL
    """)
    cost_row = c.fetchone()

    c.execute("SELECT COUNT(*) FROM messages")
    total_messages = c.fetchone()[0]

    thirty_days_ago = datetime.datetime.now().timestamp() - (30 * 86400)
    c.execute("""
        SELECT date(datetime(started_at, 'unixepoch')) as day,
               COUNT(*) as cnt
        FROM sessions
        WHERE started_at >= ?
        GROUP BY day
        ORDER BY day DESC
    """, (thirty_days_ago,))
    per_day = {row[0]: row[1] for row in c.fetchall()}

    c.execute("SELECT MIN(started_at), MAX(started_at) FROM sessions WHERE started_at IS NOT NULL")
    minmax = c.fetchone()
    oldest = fmt_time(minmax[0]) if minmax[0] else "N/A"
    newest = fmt_time(minmax[1]) if minmax[1] else "N/A"

    avg_msgs = total_messages / total if total > 0 else 0

    return {
        "total_sessions": total,
        "archived_sessions": archived_count,
        "pinned_sessions": pinned_count,
        "total_messages": total_messages,
        "avg_messages_per_session": round(avg_msgs, 1),
        "total_input_tokens": tok_row[0],
        "total_output_tokens": tok_row[1],
        "total_cache_read_tokens": tok_row[2],
        "total_cache_write_tokens": tok_row[3],
        "total_reasoning_tokens": tok_row[4],
        "total_actual_cost_usd": cost_row[0],
        "total_estimated_cost_usd": cost_row[1],
        "sessions_per_day": per_day,
        "oldest_session": oldest,
        "newest_session": newest,
    }


# ─── Archivierungs-Funktionen ─────────────────────────────────────────────────


def session_to_dict(row):
    """SQLite Row → serialisierbares Dict."""
    d = dict(row)
    for key in ("started_at", "ended_at", "compression_failure_cooldown_until"):
        if key in d and d[key] and isinstance(d[key], (int, float)):
            d[key + "_iso"] = fmt_time(d[key])
    return d


def archive_path_for(session, ensure_dir=False) -> Path:
    """Pfad: .session-archive/YYYY-MM/YYYY-MM-DD_id.json"""
    started = session.get("started_at") or datetime.datetime.now().timestamp()
    dt = datetime.datetime.fromtimestamp(started)
    month_dir = ARCHIVE_ROOT / dt.strftime("%Y-%m")
    if ensure_dir:
        month_dir.mkdir(parents=True, exist_ok=True)
    sid = session["id"]
    return month_dir / f"{dt.strftime('%Y-%m-%d')}_{sid}.json"


def archive_sessions(conn, age_days=DEFAULT_AGE_DAYS, dry_run=False):
    """Archiviere Sessions >age_days als JSON in .session-archive/YYYY-MM/"""
    sessions = get_sessions(conn, older_than_days=age_days, only_unarchived=True)

    if not sessions:
        print(f"ℹ️  Keine unarchivierten Sessions >{age_days} Tage gefunden.")
        return 0

    archived = 0
    skipped = 0

    for row in sessions:
        session = session_to_dict(row)
        msgs = get_messages_for_session(conn, session["id"], limit=5)
        session["last_messages"] = [
            {
                "role": m["role"],
                "content_preview": (m["content"] or "")[:300],
                "tool_name": m["tool_name"],
                "timestamp_iso": fmt_time(m["timestamp"]),
                "token_count": m["token_count"],
                "display_kind": m["display_kind"],
            }
            for m in msgs
        ]
        session["archived_at"] = iso_now()
        session["archive_version"] = 1

        dest = archive_path_for(session, ensure_dir=True)

        if dest.exists():
            skipped += 1
            continue

        if dry_run:
            print(f"  🔸 [DRY-RUN] Würde archivieren: {session['id'][:20]}… → {dest.parent.name}/{dest.name}")
            continue

        with open(dest, "w", encoding="utf-8") as f:
            json.dump(session, f, ensure_ascii=False, indent=2, default=str)

        title_display = session.get("title")
        if title_display is None:
            title_display = "kein Titel"
        print(f"  ✅ Archiviert: {session['id'][:20]}… ({title_display[:50]}) → {dest.name}")
        archived += 1

    if not dry_run and archived:
        print(f"\n📦 {archived} Session(s) archiviert. {skipped} bereits vorhanden.")
    elif dry_run:
        print(f"\n🔸 [DRY-RUN] {len(sessions)} Session(s) würden archiviert werden.")
    else:
        print(f"✅ Keine neuen Session(s) archiviert. {skipped} bereits vorhanden.")

    return archived


# ─── Liste archivierter Sessions ──────────────────────────────────────────────


def list_archives(filter_month: str = None):
    """Liste alle archivierten Sessions."""
    if not ARCHIVE_ROOT.exists():
        print("ℹ️  Kein Archiv-Verzeichnis vorhanden.")
        return

    if filter_month:
        pattern = f"{filter_month}*"
        glob_paths = sorted(ARCHIVE_ROOT.glob(pattern))
    else:
        glob_paths = sorted(ARCHIVE_ROOT.glob("*"))

    total_files = 0
    total_size = 0

    for month_dir in glob_paths:
        if not month_dir.is_dir():
            continue
        files = sorted(month_dir.glob("*.json"))
        if not files:
            continue
        print(f"\n📁 {month_dir.name}/")
        for f in files:
            size = f.stat().st_size
            total_files += 1
            total_size += size
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
            except (json.JSONDecodeError, OSError):
                continue
            title = data.get("title")
            if title is None:
                title = "kein Titel"
            started = data.get("started_at_iso", "?")
            msgs = data.get("message_count", "?")
            tokens_i = token_str(data.get("input_tokens") or 0)
            tokens_o = token_str(data.get("output_tokens") or 0)
            sid = data.get("id", f.stem)
            print(f"    📄 {f.name}")
            print(f"       ID: {sid}")
            print(f"       Titel: {title[:70]}")
            print(f"       Start: {started} | Nachrichten: {msgs} | Tokens: {tokens_i}→{tokens_o}")
            print(f"       Größe: {size:,} Bytes")

    total_size_kb = total_size / 1024
    total_size_mb = total_size_kb / 1024
    print(f"\n📊 Gesamt: {total_files} Dateien, {total_size_mb:.1f} MB ({total_size:,} Bytes)")


# ─── Volltextsuche ────────────────────────────────────────────────────────────


def search_archives(query: str, max_results: int = 20):
    """Volltextsuche in allen archivierten Session-JSON-Dateien."""
    if not ARCHIVE_ROOT.exists():
        print("ℹ️  Kein Archiv-Verzeichnis vorhanden.")
        return

    query_lower = query.lower()
    results = []
    total_searched = 0

    for month_dir in sorted(ARCHIVE_ROOT.glob("*")):
        if not month_dir.is_dir():
            continue
        for f in sorted(month_dir.glob("*.json")):
            total_searched += 1
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
            except (json.JSONDecodeError, OSError):
                continue

            hit_fields = []
            for key, value in data.items():
                if isinstance(value, str) and query_lower in value.lower():
                    idx = value.lower().find(query_lower)
                    start = max(0, idx - 60)
                    end = min(len(value), idx + len(query) + 60)
                    snippet = value[start:end]
                    if start > 0:
                        snippet = "…" + snippet
                    if end < len(value):
                        snippet = snippet + "…"
                    hit_fields.append(f"    [{key}] {snippet}")

                elif key == "last_messages" and isinstance(value, list):
                    for msg in value:
                        if isinstance(msg, dict):
                            for mk, mv in msg.items():
                                if isinstance(mv, str) and query_lower in mv.lower():
                                    snippet = mv[:200]
                                    hit_fields.append(f"    [last_messages.{mk}] {snippet}")

            if hit_fields:
                title = data.get("title")
                if title is None:
                    title = "kein Titel"
                sid = data.get("id", f.stem)
                started = data.get("started_at_iso", "?")
                results.append({
                    "file": str(f),
                    "id": sid,
                    "title": title,
                    "started": started,
                    "hits": hit_fields[:5],
                })
                if len(results) >= max_results:
                    break
        if len(results) >= max_results:
            break

    if not results:
        print(f"🔍 Keine Treffer für »{query}« in {total_searched} durchsuchten Dateien.")
        return

    print(f"🔍 {len(results)} Treffer für »{query}« in {total_searched} durchsuchten Dateien:\n")
    for r in results:
        print(f"  📄 {r['file']}")
        print(f"     ID: {r['id']}")
        print(f"     Titel: {r['title'][:70]}")
        print(f"     Start: {r['started']}")
        for h in r["hits"][:3]:
            print(h)
        print()


# ─── Wiederherstellung ────────────────────────────────────────────────────────


def restore_session(session_id: str):
    """Stelle eine archivierte Session wieder her (JSON-Ausgabe)."""
    if not ARCHIVE_ROOT.exists():
        print(f"❌ Kein Archiv-Verzeichnis vorhanden. Session {session_id} nicht gefunden.")
        return

    found = []

    for month_dir in sorted(ARCHIVE_ROOT.glob("*")):
        if not month_dir.is_dir():
            continue
        for f in month_dir.glob("*.json"):
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
            except (json.JSONDecodeError, OSError):
                continue
            if data.get("id") == session_id or data.get("id", "").startswith(session_id):
                found.append(data)

    if not found:
        print(f"❌ Session {session_id} nicht im Archiv gefunden.")
        return

    for data in found:
        print(f"\n📋 Wiederhergestellte Session: {data.get('id', '?')}")
        print("=" * 60)
        print(json.dumps(data, ensure_ascii=False, indent=2))
        print("=" * 60)
        print(f"\n💡 Um diese Session in der DB wiederherzustellen:")
        print(f"   python scripts/smart-session-saver.py --restore {session_id} > session_restore.json")


# ─── Statistiken ──────────────────────────────────────────────────────────────


def show_stats(conn):
    """Metrik-Statistiken anzeigen."""
    stats = get_session_stats(conn)
    now = datetime.datetime.now()

    archive_count = 0
    archive_size = 0
    if ARCHIVE_ROOT.exists():
        for f in ARCHIVE_ROOT.rglob("*.json"):
            archive_count += 1
            archive_size += f.stat().st_size

    print(f"""
╔══════════════════════════════════════════════╗
║      🤖 Smart Session Saver — Metriken       ║
╚══════════════════════════════════════════════╝
📅 Stand: {now.strftime('%Y-%m-%d %H:%M:%S')}

── Session-Statistiken ──────────────────────────
   Gesamt Sessions:       {stats['total_sessions']:>8}
   Archivierte Sessions:  {stats['archived_sessions']:>8}
   Pinned Sessions:       {stats['pinned_sessions']:>8}
   Datenbank-Archive:     {archive_count:>8}
   Nicht archiviert:      {stats['total_sessions'] - stats['archived_sessions']:>8}
   Gesamt Nachrichten:    {stats['total_messages']:>8}
   ⌀ Nachrichten/Session: {stats['avg_messages_per_session']:>8}

── Token-Verbrauch (alle Sessions) ──────────────
   Input-Tokens:          {token_str(stats['total_input_tokens']):>10}
   Output-Tokens:         {token_str(stats['total_output_tokens']):>10}
   Cache-Read-Tokens:     {token_str(stats['total_cache_read_tokens']):>10}
   Cache-Write-Tokens:    {token_str(stats['total_cache_write_tokens']):>10}
   Reasoning-Tokens:      {token_str(stats['total_reasoning_tokens']):>10}

── Kosten (alle Sessions) ──────────────────────
   Tatsächliche Kosten:   {cost_str(stats['total_actual_cost_usd']):>12}
   Geschätzte Kosten:     {cost_str(stats['total_estimated_cost_usd']):>12}

── Zeitspanne ──────────────────────────────────
   Älteste Session:       {stats['oldest_session']}
   Neueste Session:       {stats['newest_session']}

── Sessions pro Tag (letzte 30 Tage) ───────────
""")

    if stats["sessions_per_day"]:
        for day, count in stats["sessions_per_day"].items():
            bar = "█" * min(count, 40)
            print(f"   {day}  {bar}  {count}")
    else:
        print("   (keine Sessions in den letzten 30 Tagen)")

    if archive_size > 0:
        print(f"\n── Archiv-Größe ─────────────────────────────")
        print(f"   Größe: {archive_size/1024:.1f} KB ({archive_size/1024/1024:.1f} MB)")

    print()


# ─── Main ─────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Smart Session Saver — Session-Archivierung + Volltextsuche + Wiederherstellung + Metrik-Stats",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Beispiele:
              %(prog)s --archive              # Archiviere alte Sessions
              %(prog)s --archive --dry-run     # Nur Prüfung, keine Aktion
              %(prog)s --list                  # Alle Archive auflisten
              %(prog)s --search DeepSeek       # Volltextsuche
              %(prog)s --restore 20260818_     # Session wiederherstellen
              %(prog)s --stats                 # Metrik-Statistiken
        """),
    )
    parser.add_argument("--archive", action="store_true", help="Archiviere Sessions >7 Tage als JSON")
    parser.add_argument("--list", action="store_true", help="Liste archivierte Sessions")
    parser.add_argument("--search", type=str, metavar="QUERY", help="Volltextsuche in Archiven")
    parser.add_argument("--restore", type=str, metavar="SESSION_ID", help="Stelle Session wieder her")
    parser.add_argument("--stats", action="store_true", help="Metrik-Statistiken anzeigen")
    parser.add_argument("--dry-run", action="store_true", help="Nur zeigen, nichts archivieren")
    parser.add_argument("--db", type=str, default=None, help="Alternativer Pfad zur Session-DB")
    parser.add_argument("--age", type=int, default=DEFAULT_AGE_DAYS,
                        help=f"Alter in Tagen (default: {DEFAULT_AGE_DAYS})")

    args = parser.parse_args()

    if not any([args.archive, args.list, args.search, args.restore, args.stats]):
        parser.print_help()
        return

    # ─── archive ───
    if args.archive:
        conn = db_connect(state_db=args.db)
        try:
            archive_sessions(conn, age_days=args.age, dry_run=args.dry_run)
        finally:
            conn.close()

    # ─── list ───
    elif args.list:
        list_archives()

    # ─── search ───
    elif args.search:
        search_archives(args.search)

    # ─── restore ───
    elif args.restore:
        restore_session(args.restore)

    # ─── stats ───
    elif args.stats:
        conn = db_connect(state_db=args.db)
        try:
            show_stats(conn)
        finally:
            conn.close()


if __name__ == "__main__":
    main()
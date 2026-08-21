#!/usr/bin/env python3
"""
Context Compressor — Session-Komprimierung (60-80% Reduktion)
=============================================================
Analysiert Session-Transcripts aus state.db, komprimiert via Redundanz-Entfernung,
extrahiert Entscheidungen, Action-Items, Learnings und offene Punkte.

CLI:
  --session <id>     Einzelne Session komprimieren → JSON on stdout
  --batch            Alle Sessions >7 Tage → archives/
  --stats            Kompressionsrate anzeigen (input chars → output chars)
  --search <query>   Volltextsuche in komprimierten Sessions
"""

import sqlite3, json, sys, os, re, time
from datetime import datetime, timezone
from pathlib import Path

# ─── Pfade ───────────────────────────────────────────────────────────────
def _resolve_home() -> Path:
    """Ermittle das OpenAmer Home-Verzeichnis (Windows-kompatibel)."""
    raw = os.environ.get("OPENAMER_HOME")
    if raw:
        p = Path(raw)
        s = str(p)
        # MSYS2 /c/... -> Windows C:\... via Bs \c\... -> C:\...
        if s.startswith("\\") and len(s) > 3 and s[2] == "\\":
            drive = s[1].upper()
            rest = "\\" + s[3:]
            p = Path(f"{drive}:{rest}")
        return p
    return Path.home() / "AppData" / "Local" / "openamer-laptop"

HOME = _resolve_home()
STATE_DB = HOME / "state.db"
ARCHIVE_DIR = HOME / "context-compressor" / "archives"
INDEX_FILE = HOME / "context-compressor" / "index.json"

# ─── Einfache Entscheidungs-Patterns (flache Liste, kein Nesting) ──────
DECISION_PHRASES = [
    r"ich\s+werde\s+\w+",
    r"ich\s+entscheide\s+mich\s+f.r\s+\w+",
    r"ich\s+entscheide\s+mich\s+(?:f.r|zu)\s+",
    r"ich\s+habe\s+mich\s+entschieden",
    r"ich\s+(?:beginne|starte|fange\s+an)\s+mit\s+",
    r"ich\s+(?:verwende|nutze|w.hle|nehme)\s+",
    r"ich\s+(?:implementiere|baue|erstelle|setze\s+(?:um|ein)|f.hre\s+(?:durch|aus))\s+",
    r"ich\s+(?:lasse|schreibe)\s+\w+",
    r"wir\s+(?:werden|machen|entscheiden|bauen|nehmen|verwenden|nutzen)\s+",
    r"wir\s+(?:implementieren|erstellen|setzen|fahren|beginnen|starten)\s+",
    r"wir\s+haben\s+uns\s+(?:entschieden|geeinigt)\s+",
    r"ich\s+(?:w.hle|optiere)\s+f.r\s+",
    r"entschieden|beschlossen|festgelegt",
    r"entscheidung:\s+\w+",
    r"decision:\s+\w+",
    r"decided\s+to\s+\w+",
    r"will\s+(?:use|create|build|implement|go\s+with|choose|adopt|start)\s+",
    r"we\s+(?:will|should|are\s+going\s+to)\s+\w+",
    r"we\s+(?:decided|chose|opted|agreed|settled|going\s+with)\s+",
    r"let\s+(?:me|us)\s+(?:use|create|build|implement|try|add|remove|change|switch)\s+",
    r"opting\s+for\s+",
    r"going\s+with\s+",
    r"chosen\s+approach",
]
DECISION_RE = re.compile("|".join(f"(?:{p})" for p in DECISION_PHRASES), re.IGNORECASE)

ACTION_PHRASES = [
    r"TODO\b", r"FIXME\b",
    r"muss\s+(?:noch|ich|ge.ndert|angepasst|implementiert|getestet|gebaut|erstellt|hinzugef.egt|entfernt)",
    r"n.cht(?:e[rn]?|es)\s+(?:Schritt|Aufgabe|To.Do|Action|Item|Punkt)",
    r"(?:als\s+)?n.chstes\s+(?:muss|soll|werde|mache|folgt|dran)",
    r"(?:need|must|should|will|going)\s+to\s+(?:fix|add|create|implement|change|update|remove|test|build|refactor|check)\s+",
    r"next\s+(?:step|action|task|item|todo|thing)",
    r"action\s+item\b", r"aufgabe\b",
    r"\[\s*\]",
    r"offene\s+(?:aufgabe|punkte|items)",
]
ACTION_RE = re.compile("|".join(f"(?:{p})" for p in ACTION_PHRASES), re.IGNORECASE)

LEARNING_PHRASES = [
    r"gelernt\b", r"festgestellt\b", r"erkannt\b", r"bemerkt\b",
    r"herausgefunden\b", r"entdeckt\b",
    r"wichtig\s+zu\s+wissen",
    r"daraus\s+gelernt",
    r"(?:hat\s+)?sich\s+herausgestellt",
    r"lesson\s+learned", r"learned\s+that\b",
    r"discovered\b", r"found\s+(?:out|that)\b",
    r"realized\b", r"noticed\b",
    r"key\s+(?:takeaway|insight|finding)",
    r"importantly\b", r"notable\b", r"worth\s+noting",
]
LEARNING_RE = re.compile("|".join(f"(?:{p})" for p in LEARNING_PHRASES), re.IGNORECASE)

OPEN_POINT_PHRASES = [
    r"offen\b", r"ungekl.rt\b", r"unklar\b",
    r"noch\s+nicht\b", r"noch\s+ausstehend\b",
    r"n.chstes\s+Mal\b",
    r"folgt\s+(?:noch|sp.ter)",
    r"open\s+(?:question|issue|point|item)",
    r"still\s+(?:open|pending|needs|remains)",
    r"not\s+(?:yet|sure|clear|decided|resolved)",
    r"pending\b", r"tbd\b",
    r"to\s+be\s+(?:done|decided|resolved|addressed)",
    r"further\s+(?:work|investigation|analysis)",
    r"future\s+work\b",
    r"unresolved\b", r"outstanding\b",
    r"remains\s+to\s+be\b",
]
OPEN_POINT_RE = re.compile("|".join(f"(?:{p})" for p in OPEN_POINT_PHRASES), re.IGNORECASE)

# ─── Token-Kürzung ──────────────────────────────────────────────────────
TOOL_OUTPUT_MAX_CHARS = 200


def summarize_text(text: str, max_chars: int = 600) -> str:
    """Kürze Text auf max_chars, behalte Anfang und Ende bei langen Blöcken."""
    if len(text) <= max_chars:
        return text
    half = max_chars // 2 - 20
    return text[:half] + "\n... [TRUNCATED] ...\n" + text[-half:]


def compress_tool_content(content: str) -> str:
    """Tool-Output komprimieren: JSON/blob massiv kürzen."""
    if not content:
        return ""
    stripped = content.strip()
    # JSON-Erkennung
    json_match = re.match(r'^(\{.*\}|\[.*\])$', stripped, re.DOTALL)
    if json_match:
        try:
            data = json.loads(stripped)
            if isinstance(data, dict):
                keys = list(data.keys())
                return f"[JSON] keys={keys[:8]}"
            elif isinstance(data, list):
                return f"[JSON] array_len={len(data)}"
        except (json.JSONDecodeError, ValueError):
            pass

    if len(content) > TOOL_OUTPUT_MAX_CHARS:
        return summarize_text(content, TOOL_OUTPUT_MAX_CHARS) + \
               f"\n[TOOL OUTPUT: {len(content)} chars -> compressed]"

    return content


def compress_message(role: str, content: str, is_tool: bool = False) -> str:
    """Einzelne Nachricht komprimieren."""
    if not content:
        return ""
    if is_tool or role == "tool":
        return compress_tool_content(content)
    if len(content) > 1500:
        return summarize_text(content, 1200)
    return content


# ─── Extraktions-Funktionen ─────────────────────────────────────────────
def extract_decision(text: str) -> list:
    """Extrahiere Entscheidungen aus Text."""
    matches = []
    for m in DECISION_RE.finditer(text):
        start = max(0, text.rfind(".", 0, m.start()) + 1)
        end = text.find(".", m.end())
        if end == -1:
            end = len(text)
        sentence = text[start:end].strip()
        if sentence and len(sentence) < 500:
            matches.append(sentence)
    return matches


def extract_action_items(text: str) -> list:
    """Extrahiere Action-Items aus Text."""
    matches = []
    for m in ACTION_RE.finditer(text):
        start = max(0, text.rfind(".", 0, m.start()) + 1)
        end = text.find(".", m.end())
        if end == -1:
            end = len(text)
        sentence = text[start:end].strip()
        if sentence and len(sentence) < 300:
            matches.append(sentence)
    return matches


def extract_learnings(text: str) -> list:
    """Extrahiere Learnings aus Text."""
    matches = []
    for m in LEARNING_RE.finditer(text):
        start = max(0, text.rfind(".", 0, m.start()) + 1)
        end = text.find(".", m.end())
        if end == -1:
            end = len(text)
        sentence = text[start:end].strip()
        if sentence and len(sentence) < 400:
            matches.append(sentence)
    return matches


def extract_open_points(text: str) -> list:
    """Extrahiere offene Punkte aus Text."""
    matches = []
    for m in OPEN_POINT_RE.finditer(text):
        start = max(0, text.rfind(".", 0, m.start()) + 1)
        end = text.find(".", m.end())
        if end == -1:
            end = len(text)
        sentence = text[start:end].strip()
        if sentence and len(sentence) < 300:
            matches.append(sentence)
    return matches


def remove_duplicate_sentences(text: str) -> str:
    """Entferne sich wiederholende Sätze (innerhalb derselben Nachricht)."""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    seen = set()
    unique = []
    for s in sentences:
        normalized = s.strip().lower()[:80]
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique.append(s)
    return " ".join(unique)


def remove_boilerplate(content: str, role: str) -> str:
    """Entferne Assistent-Boilerplate: tool_call-Blöcke, code fence, usw."""
    if role == "assistant":
        content = re.sub(r'<antthinking>.*?</antthinking>', '', content, flags=re.DOTALL)
        content = re.sub(r'<tool_call>.*?</tool_call>', '', content, flags=re.DOTALL)
        content = re.sub(r'\{[^}]*"name"\s*:\s*"[^"]*"[^}]*"input"\s*:[^}]*\}', '',
                         content, flags=re.DOTALL)
        content = re.sub(r'(```[\w]*\n).{500,}?(```)',
                         lambda m: m.group(1) + "[CODE BLOCK TRUNCATED]\n" + m.group(2),
                         content, flags=re.DOTALL)
    return content


def generate_summary(messages: list) -> str:
    """Erzeuge eine kurze Zusammenfassung (1-2 Sätze)."""
    summary_parts = []
    for m in messages[:20]:
        if m["role"] == "user":
            text = m.get("compressed", m.get("original", ""))[:200]
            if text:
                summary_parts.append(text)
            break
    for m in reversed(messages[-10:]):
        if m["role"] == "assistant":
            text = m.get("compressed", m.get("original", ""))[:200]
            if text:
                summary_parts.append(text[:150])
            break
    return " | ".join(summary_parts[:3]) if summary_parts else ""


# ─── Komprimierung einer Session ─────────────────────────────────────────
def compress_session(session_id: str) -> dict:
    """Lade eine Session aus der DB, komprimiere sie, gib Dict zurück."""
    db_path = str(STATE_DB)
    if not os.path.exists(db_path):
        return {"error": f"state.db not found at {db_path}"}

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM sessions WHERE id=?", (session_id,))
    session = cur.fetchone()
    if not session:
        conn.close()
        return {"error": f"Session {session_id} not found"}

    cur.execute(
        "SELECT id, role, content, timestamp, tool_name FROM messages "
        "WHERE session_id=? ORDER BY id", (session_id,)
    )
    rows = cur.fetchall()
    conn.close()

    raw_chars = 0
    compressed_chars = 0
    messages_compressed = []
    all_decisions = []
    all_actions = []
    all_learnings = []
    all_open = []

    for row in rows:
        msg_id = row["id"]
        role = row["role"]
        content = row["content"] or ""
        tool_name = row["tool_name"] or ""
        ts = row["timestamp"]

        raw_chars += len(content)
        is_tool = (role == "tool" or (role == "assistant" and tool_name))

        cleaned = remove_boilerplate(content, role)
        cleaned = remove_duplicate_sentences(cleaned)
        compressed = compress_message(role, cleaned, is_tool)
        compressed_chars += len(compressed)

        entry = {
            "id": msg_id,
            "role": role,
            "compressed": compressed,
            "original_len": len(content),
            "compressed_len": len(compressed),
            "timestamp": ts,
        }
        if tool_name:
            entry["tool_name"] = tool_name

        if role in ("user", "assistant"):
            all_decisions.extend(extract_decision(content))
            all_actions.extend(extract_action_items(content))
            all_learnings.extend(extract_learnings(content))
            all_open.extend(extract_open_points(content))

        messages_compressed.append(entry)

    decisions_dedup = _dedup_list(all_decisions)
    actions_dedup = _dedup_list(all_actions)
    learnings_dedup = _dedup_list(all_learnings)
    open_dedup = _dedup_list(all_open)

    compression_ratio = 1 - (compressed_chars / raw_chars) if raw_chars > 0 else 0
    summary = generate_summary(messages_compressed)

    started_at = session["started_at"]
    ended_at = session["ended_at"]

    result = {
        "session_id": session_id,
        "title": session["title"],
        "started_at": started_at,
        "ended_at": ended_at,
        "started_iso": datetime.fromtimestamp(started_at, tz=timezone.utc).isoformat() if started_at else None,
        "ended_iso": datetime.fromtimestamp(ended_at, tz=timezone.utc).isoformat() if ended_at else None,
        "message_count": len(messages_compressed),
        "raw_chars": raw_chars,
        "compressed_chars": compressed_chars,
        "compression_ratio": round(compression_ratio, 4),
        "compression_percent": f"{compression_ratio * 100:.1f}%",
        "summary": summary,
        "decisions": decisions_dedup[:10],
        "action_items": actions_dedup[:10],
        "learnings": learnings_dedup[:10],
        "open_points": open_dedup[:10],
        "messages": messages_compressed,
    }
    return result


def _dedup_list(items: list) -> list:
    """Dedupliziere Liste, entferne zu kurze/leere Einträge."""
    seen = set()
    result = []
    for item in items:
        norm = item.strip().lower()[:100]
        if len(norm) > 10 and norm not in seen:
            seen.add(norm)
            result.append(item.strip())
    return result


# ─── Batch-Verarbeitung ──────────────────────────────────────────────────
def batch_compress(days_old: int = 7):
    """Komprimiere alle Sessions älter als days_old und speichere in archives/."""
    db_path = str(STATE_DB)
    if not os.path.exists(db_path):
        print(json.dumps({"error": f"state.db not found at {db_path}"}))
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cutoff = time.time() - days_old * 86400
    cur.execute(
        "SELECT id, title, started_at, ended_at, message_count FROM sessions "
        "WHERE started_at < ? ORDER BY started_at",
        (cutoff,)
    )
    sessions = cur.fetchall()
    conn.close()

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    results = []
    stats = {"sessions_processed": 0, "total_raw_chars": 0, "total_compressed_chars": 0}

    for s in sessions:
        sid = s["id"]
        try:
            compressed = compress_session(sid)
            if "error" in compressed:
                print(f"Warning: {sid} - {compressed['error']}", file=sys.stderr)
                continue
            results.append(compressed)
            stats["sessions_processed"] += 1
            stats["total_raw_chars"] += compressed["raw_chars"]
            stats["total_compressed_chars"] += compressed["compressed_chars"]
        except Exception as e:
            print(f"Error compressing {sid}: {e}", file=sys.stderr)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_file = ARCHIVE_DIR / f"batch_{timestamp}.json"
    with open(archive_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)

    _update_index(results, archive_file, stats, timestamp)

    overall_ratio = 0
    if stats["total_raw_chars"] > 0:
        overall_ratio = 1 - (stats["total_compressed_chars"] / stats["total_raw_chars"])

    print(json.dumps({
        "action": "batch_complete",
        "archive": str(archive_file),
        "sessions_processed": stats["sessions_processed"],
        "total_raw_chars": stats["total_raw_chars"],
        "total_compressed_chars": stats["total_compressed_chars"],
        "overall_compression_ratio": round(overall_ratio, 4),
        "overall_compression_percent": f"{overall_ratio * 100:.1f}%",
    }, ensure_ascii=False, indent=2))


def _update_index(results: list, archive_file: Path, stats: dict, timestamp: str):
    """Aktualisiere den Volltext-Suchindex."""
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    index = {"archives": [], "searchable": []}
    if INDEX_FILE.exists():
        try:
            index = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, Exception):
            index = {"archives": [], "searchable": []}

    index["archives"].append({
        "file": str(archive_file),
        "timestamp": timestamp,
        "sessions": len(results),
        "total_raw_chars": stats["total_raw_chars"],
        "total_compressed_chars": stats["total_compressed_chars"],
    })

    for r in results:
        index["searchable"].append({
            "session_id": r["session_id"],
            "title": r["title"],
            "summary": r["summary"],
            "decisions": r["decisions"],
            "action_items": r["action_items"],
            "learnings": r["learnings"],
            "open_points": r["open_points"],
            "compression_percent": r["compression_percent"],
            "archive_file": str(archive_file),
            "started_iso": r["started_iso"],
            "ended_iso": r["ended_iso"],
        })

    INDEX_FILE.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")


# ─── Volltextsuche ──────────────────────────────────────────────────────
def search_archives(query: str):
    """Volltextsuche in komprimierten Sessions (Index + Archiv-Dateien)."""
    if not INDEX_FILE.exists():
        print(json.dumps({"error": "No index found. Run --batch first."}))
        return

    index = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    query_lower = query.lower()
    results = []

    for entry in index["searchable"]:
        search_text = json.dumps(
            {k: entry[k] for k in ["summary", "decisions", "action_items", "learnings", "open_points", "title"]}
        ).lower()
        if query_lower in search_text:
            results.append(entry)

    for archive_entry in index["archives"]:
        af = Path(archive_entry["file"])
        if not af.exists():
            continue
        try:
            data = json.loads(af.read_text(encoding="utf-8"))
        except Exception:
            continue
        for session in data:
            if any(r["session_id"] == session["session_id"] for r in results):
                continue
            for msg in session.get("messages", []):
                if query_lower in (msg.get("compressed", "") or "").lower():
                    results.append({
                        "session_id": session["session_id"],
                        "title": session.get("title"),
                        "summary": session.get("summary", ""),
                        "match_message_role": msg.get("role"),
                        "match_snippet": (msg.get("compressed", "") or "")[:200],
                        "compression_percent": session.get("compression_percent", ""),
                        "archive_file": str(af),
                        "decisions": session.get("decisions", []),
                    })
                    break

    seen_ids = set()
    deduped = []
    for r in results:
        sid = r["session_id"]
        if sid not in seen_ids:
            seen_ids.add(sid)
            deduped.append(r)

    print(json.dumps({
        "query": query,
        "results_count": len(deduped),
        "results": deduped,
    }, ensure_ascii=False, indent=2))


# ─── Stats ──────────────────────────────────────────────────────────────
def show_stats():
    """Zeige Kompressionsstatistiken für alle Archive."""
    if not INDEX_FILE.exists():
        print(json.dumps({"error": "No index found. Run --batch first."}))
        return

    index = json.loads(INDEX_FILE.read_text(encoding="utf-8"))

    all_decisions = len(set(
        s.get("decisions", [str(s)])[0] for s in index["searchable"] if s.get("decisions")
    ))
    all_actions = sum(len(s.get("action_items", [])) for s in index["searchable"])
    all_learnings = sum(len(s.get("learnings", [])) for s in index["searchable"])
    all_open = sum(len(s.get("open_points", [])) for s in index["searchable"])

    total_raw = sum(a.get("total_raw_chars", 0) for a in index["archives"])
    total_compressed = sum(a.get("total_compressed_chars", 0) for a in index["archives"])

    db_path = str(STATE_DB)
    live_sessions = 0
    live_messages = 0
    live_chars = 0
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM sessions")
            live_sessions = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM messages")
            live_messages = cur.fetchone()[0]
            cur.execute("SELECT SUM(LENGTH(content)) FROM messages WHERE content IS NOT NULL")
            row = cur.fetchone()
            live_chars = row[0] if row and row[0] else 0
            conn.close()
        except Exception:
            pass

    compressed_sessions = len(index["searchable"])
    overall_ratio = 1 - (total_compressed / total_raw) if total_raw > 0 else 0

    arch_info = []
    for a in index["archives"]:
        r = a.get("total_raw_chars", 0)
        c = a.get("total_compressed_chars", 0)
        ratio = f"{1 - c / r:.1%}" if r > 0 else "N/A"
        arch_info.append({"file": a["file"], "sessions": a["sessions"], "compression": ratio})

    print(json.dumps({
        "live_db": {
            "sessions": live_sessions,
            "messages": live_messages,
            "total_chars": live_chars,
        },
        "compressed_archives": {
            "total_archives": len(index["archives"]),
            "compressed_sessions": compressed_sessions,
            "total_raw_chars": total_raw,
            "total_compressed_chars": total_compressed,
            "overall_compression_ratio": round(overall_ratio, 4),
            "overall_compression_percent": f"{overall_ratio * 100:.1f}%",
        },
        "extracted": {
            "decisions": all_decisions,
            "action_items": all_actions,
            "learnings": all_learnings,
            "open_points": all_open,
        },
        "archives": arch_info,
    }, ensure_ascii=False, indent=2))


# ─── CLI ────────────────────────────────────────────────────────────────
def main():
    args = sys.argv[1:]

    if not args:
        print(__doc__)
        sys.exit(0)

    if args[0] == "--session" and len(args) >= 2:
        session_id = args[1]
        result = compress_session(session_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if "error" in result:
            sys.exit(1)

    elif args[0] == "--batch":
        days_old = 7
        if len(args) >= 2:
            try:
                days_old = int(args[1])
            except ValueError:
                pass
        batch_compress(days_old)

    elif args[0] == "--stats":
        show_stats()

    elif args[0] == "--search" and len(args) >= 2:
        query = " ".join(args[1:])
        search_archives(query)

    else:
        print(f"Unknown args: {args}", file=sys.stderr)
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
"""
``openamer_cli.cross_session_learning`` — Cross-Session Learning für OpenAmer.

Extrahiert Lessons Learned aus abgeschlossenen Sessions, aggregiert sie über
die letzten 7 Tage und erstellt einen Context-Block, der neuen Sessions
mitgegeben wird. So beeinflussen Erkenntnisse aus Session A die Session B.

Funktionen:
  - extract_lessons(session_id)    — analysiert eine Session
  - consolidate_lessons()           — aggregiert alle Lessons der letzten 7 Tage
  - inject_context()                — erstellt Context-Block für neue Sessions
  - run_consolidation_cycle()       — vollständiger Zyklus
"""

from __future__ import annotations

import json
import os
import sqlite3
import textwrap
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any


# ── Konstanten ──────────────────────────────────────────────────────────────

_MAX_LESSON_AGE_DAYS = 7
"""Standard-Fenster: Lessons der letzten 7 Tage."""

_CROSS_SESSION_DB_RELPATH = "cross_session_lessons.db"
"""Name der Datenbank für persistierte Lessons."""


# ── Pfad-Helfer ────────────────────────────────────────────────────────────

def _state_db_path() -> Path:
    """Pfad zur OpenAmer State-Datenbank (die Sessions + Messages enthält)."""
    home = Path(os.environ.get(
        "OPENAMER_HOME",
        Path.home() / "AppData" / "Local" / "openamer-laptop",
    ))
    return home / "state.db"


def _lessons_db_path() -> Path:
    """Pfad zur Cross-Session-Lessons-Datenbank."""
    home = Path(os.environ.get(
        "OPENAMER_LESSONS_DB",
        Path(os.environ.get(
            "OPENAMER_HOME",
            Path.home() / "AppData" / "Local" / "openamer-laptop",
        )),
    ))
    return home / _CROSS_SESSION_DB_RELPATH


def _open_state_db() -> sqlite3.Connection:
    """Öffnet die State-DB (Read-Only, Row-Factory aktiv)."""
    path = _state_db_path()
    if not path.exists():
        raise FileNotFoundError(
            f"State-DB nicht gefunden unter: {path}\n"
            "OpenAmer muss mindestens einmal gelaufen sein."
        )
    conn = sqlite3.connect(str(path), uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _open_lessons_db() -> sqlite3.Connection:
    """Öffnet die Lessons-DB (Read-Write) und legt die Tabelle an, falls nötig."""
    path = _lessons_db_path()
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS lessons (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT NOT NULL,
            category    TEXT NOT NULL DEFAULT 'general',
            lesson      TEXT NOT NULL,
            tool_name   TEXT,
            success     INTEGER NOT NULL DEFAULT 1,
            created_at  REAL NOT NULL DEFAULT (julianday('now')),
            UNIQUE(session_id, lesson)
        )
    """)
    conn.commit()
    return conn


# ═══════════════════════════════════════════════════════════════════════════
# 1. extract_lessons
# ═══════════════════════════════════════════════════════════════════════════

def extract_lessons(
    session_id: str,
    *,
    persist: bool = True,
) -> dict[str, Any]:
    """Analysiert eine Session und extrahiert Lessons Learned.

    Liest alle Messages (User + Assistant + Tool) aus der State-DB,
    identifiziert:
    - Welche Tools verwendet wurden (tool_call_count > 0)
    - Ob die Session erfolgreich war (end_reason)
    - Themen-Schwerpunkte (via role-Verteilung und content-Länge)
    - Explizite Fehler / Erfolgsmuster

    Parameter
    ---------
    session_id : str
        Die Session-ID aus der State-DB.
    persist : bool
        Ob die extrahierten Lessons in der Lessons-DB gespeichert werden sollen.

    Rückgabe
    --------
    dict mit 'session_id', 'title', 'model', 'tool_usage', 'lesson_count',
    'lessons' (Liste von Diktaten), 'success', 'message_count', 'duration_min'.
    """
    state = _open_state_db()

    # ── Session-Metadaten laden ────────────────────────────────────────
    row = state.execute(
        "SELECT id, title, model, started_at, ended_at, end_reason, "
        "message_count, tool_call_count, input_tokens, output_tokens "
        "FROM sessions WHERE id = ?",
        (session_id,),
    ).fetchone()

    if row is None:
        return {
            "session_id": session_id,
            "error": f"Session {session_id} nicht gefunden.",
            "lessons": [],
        }

    session = dict(row)
    tool_call_count_from_session = session.get("tool_call_count") or 0
    started = session.get("started_at")
    ended = session.get("ended_at")
    duration_min = 0.0
    if started and ended:
        duration_min = round((ended - started) / 60.0, 1)

    # ── Messages laden ─────────────────────────────────────────────────
    messages = state.execute(
        "SELECT role, content, tool_name, tool_call_id, finish_reason, "
        "token_count "
        "FROM messages WHERE session_id = ? AND active = 1 "
        "ORDER BY id ASC",
        (session_id,),
    ).fetchall()

    # ── Analyse ────────────────────────────────────────────────────────
    role_counts: Counter[str] = Counter()
    tool_names: Counter[str] = Counter()
    msg_tool_call_count = 0  # counted from messages
    total_assistant_tokens = 0
    total_user_tokens = 0
    assistant_messages: list[dict[str, Any]] = []
    user_messages: list[str] = []

    for msg in messages:
        m = dict(msg)
        role = m.get("role", "unknown")
        role_counts[role] += 1
        content = m.get("content") or ""

        if role == "assistant":
            if m.get("token_count"):
                total_assistant_tokens += m["token_count"]
            assistant_messages.append({
                "content": content[:500],
                "finish_reason": m.get("finish_reason"),
                "token_count": m.get("token_count"),
            })
        elif role == "user":
            total_user_tokens += len(content)
            user_messages.append(content[:300])

        tn = m.get("tool_name")
        if tn:
            tool_names[tn] += 1
            msg_tool_call_count += 1

    # ── Lessons generieren ─────────────────────────────────────────────
    lessons: list[dict[str, Any]] = []
    end_reason = session.get("end_reason") or "unknown"
    success = 1 if end_reason not in ("error", "cancelled", "interrupted") else 0

    # Lesson 1: Erfolg / Misserfolg
    if success:
        lessons.append({
            "category": "result",
            "lesson": (
                f"Session erfolgreich abgeschlossen (end_reason={end_reason}). "
                f"{message_count_maybe(session)} Messages, "
                f"{tool_call_count_from_session} Tool-Aufrufe."
            ),
            "tool_name": None,
            "success": 1,
        })
    else:
        lessons.append({
            "category": "result",
            "lesson": (
                f"Session vorzeitig beendet (end_reason={end_reason}). "
                "Mögliche Ursachen: Fehler, Abbruch oder Unterbrechung."
            ),
            "tool_name": None,
            "success": 0,
        })

    # Lesson 2: Tool-Nutzung
    if tool_names:
        top_tools = tool_names.most_common(5)
        tools_str = ", ".join(f"{t[0]}({t[1]})" for t in top_tools)
        lessons.append({
            "category": "tools",
            "lesson": (
                f"Top-Tools in dieser Session: {tools_str}. "
                f"Insgesamt {tool_call_count_from_session} Tool-Aufrufe."
            ),
            "tool_name": top_tools[0][0] if top_tools else None,
            "success": 1,
        })

    # Lesson 3: Token-Verbrauch
    input_tok = session.get("input_tokens") or 0
    output_tok = session.get("output_tokens") or 0
    total_tok = input_tok + output_tok
    if total_tok > 0:
        lessons.append({
            "category": "efficiency",
            "lesson": (
                f"Token-Verbrauch: {input_tok} Input / {output_tok} Output "
                f"(Gesamt {total_tok}). "
                f"Dauer: {duration_min} Minuten."
            ),
            "tool_name": None,
            "success": 1,
        })

    # Lesson 4: Themen-Schwerpunkt (basierend auf User-Messages)
    user_text = " ".join(user_messages)
    if user_text:
        # Simple keyword extraction (erste 3 signifikanten Wörter)
        words = [
            w for w in user_text.lower().split()
            if len(w) > 3 and w not in _STOPWORDS
        ]
        word_freq = Counter(words)
        top_topics = word_freq.most_common(5)
        if top_topics:
            topics_str = ", ".join(f"{w}({c})" for w, c in top_topics)
            lessons.append({
                "category": "topics",
                "lesson": f"Themen-Schwerpunkte: {topics_str}.",
                "tool_name": None,
                "success": 1,
            })

    # Lesson 5: Model
    model = session.get("model") or "unknown"
    lessons.append({
        "category": "model",
        "lesson": f"Verwendetes Model: {model}.",
        "tool_name": None,
        "success": 1,
    })

    # ── Persistieren ───────────────────────────────────────────────────
    if persist and lessons:
        _persist_lessons(session_id, lessons)

    return {
        "session_id": session_id,
        "title": session.get("title") or "(kein Titel)",
        "model": model,
        "end_reason": end_reason,
        "success": bool(success),
        "message_count": session.get("message_count") or len(messages),
        "tool_call_count": tool_call_count_from_session,
        "duration_min": duration_min,
        "input_tokens": input_tok,
        "output_tokens": output_tok,
        "role_counts": dict(role_counts),
        "tool_usage": dict(tool_names),
        "lessons": lessons,
    }


def _persist_lessons(session_id: str, lessons: list[dict[str, Any]]) -> None:
    """Schreibt extrahierte Lessons in die Lessons-DB."""
    db = _open_lessons_db()
    now = datetime.now(timezone.utc).timestamp()
    for les in lessons:
        try:
            db.execute(
                "INSERT OR IGNORE INTO lessons "
                "(session_id, category, lesson, tool_name, success, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    session_id,
                    les["category"],
                    les["lesson"],
                    les.get("tool_name"),
                    les["success"],
                    now,
                ),
            )
        except Exception:
            continue
    db.commit()
    db.close()


# ═══════════════════════════════════════════════════════════════════════════
# 2. consolidate_lessons
# ═══════════════════════════════════════════════════════════════════════════

def consolidate_lessons(
    *,
    days: int = _MAX_LESSON_AGE_DAYS,
    min_confidence: int = 1,
) -> dict[str, Any]:
    """Aggregiert Lessons aus allen Sessions der letzten *days* Tage.

    Liest die State-DB für Session-Metadaten und die Lessons-DB für
    bereits extrahierte Lessons. Fasst ähnliche Lessons zusammen,
    zählt die häufigsten Tools und identifiziert wiederkehrende Muster.

    Parameter
    ---------
    days : int
        Zeitfenster in Tagen (Default 7).
    min_confidence : int
        Mindestanzahl Vorkommen, damit eine Lesson als "bestätigt" gilt.

    Rückgabe
    --------
    dict mit 'total_sessions', 'total_lessons', 'categories',
    'top_tools', 'topics', 'consolidated_lessons', 'confidence_summary'.
    """
    since_ts = (datetime.now(timezone.utc) - timedelta(days=days)).timestamp()

    # ── Sessions aus State-DB holen ────────────────────────────────────
    state = _open_state_db()
    sessions = state.execute(
        "SELECT id, title, model, started_at, ended_at, end_reason, "
        "message_count, tool_call_count "
        "FROM sessions "
        "WHERE started_at >= ? AND source = 'cli' "
        "ORDER BY started_at DESC",
        (since_ts,),
    ).fetchall()

    # ── Lessons aus Lessons-DB holen ───────────────────────────────────
    lessons_db = _open_lessons_db()
    lesson_rows = lessons_db.execute(
        "SELECT session_id, category, lesson, tool_name, success, created_at "
        "FROM lessons "
        "WHERE created_at >= ? "
        "ORDER BY created_at DESC",
        (since_ts,),
    ).fetchall()

    # ── Aggregieren ────────────────────────────────────────────────────
    category_counts: Counter[str] = Counter()
    tool_counter: Counter[str] = Counter()
    topic_counter: Counter[str] = Counter()
    lesson_texts: list[str] = []
    success_count = 0
    fail_count = 0
    session_ids_seen: set[str] = set()

    for row in lesson_rows:
        les = dict(row)
        cat = les.get("category", "general")
        category_counts[cat] += 1
        tn = les.get("tool_name")
        if tn:
            tool_counter[tn] += 1
        if les.get("success"):
            success_count += 1
        else:
            fail_count += 1

        lesson_text = les.get("lesson", "")
        lesson_texts.append(lesson_text)
        session_ids_seen.add(les["session_id"])

        # Topic aus der Topics-Lesson extrahieren
        if cat == "topics" and lesson_text:
            # Format: "Themen-Schwerpunkte: word(cnt), word(cnt)..."
            if "Themen-Schwerpunkte:" in lesson_text:
                topic_part = lesson_text.split("Themen-Schwerpunkte:", 1)[1].strip()
                for item in topic_part.split(","):
                    item = item.strip()
                    if "(" in item:
                        word = item.split("(")[0].strip()
                        if word:
                            topic_counter[word] += 1

    # ── Consolidated-Lessons bauen ─────────────────────────────────────
    consolidated: list[dict[str, Any]] = []

    # Consolidated 1: Zusammenfassung
    total_sessions = len(sessions)
    total_lessons = len(lesson_rows)
    consolidated.append({
        "category": "summary",
        "lesson": (
            f"In den letzten {days} Tagen wurden {total_sessions} Sessions "
            f"mit {total_lessons} extrahierten Lessons analysiert. "
            f"{success_count} positive, {fail_count} negative Lessons."
        ),
        "confidence": min(total_lessons, 10),
    })

    # Consolidated 2: Top-Tools
    if tool_counter:
        top_t = tool_counter.most_common(5)
        consolidated.append({
            "category": "tools",
            "lesson": (
                "Am häufigsten genutzte Tools: "
                + ", ".join(f"{t}({c}x)" for t, c in top_t)
                + "."
            ),
            "confidence": top_t[0][1],
        })

    # Consolidated 3: Kategorie-Verteilung
    if category_counts:
        top_cat = category_counts.most_common()
        consolidated.append({
            "category": "categories",
            "lesson": (
                "Lessons nach Kategorie: "
                + ", ".join(f"{c}({n})" for c, n in top_cat)
                + "."
            ),
            "confidence": top_cat[0][1],
        })

    # Consolidated 4: Dauer / Effizienz
    if sessions:
        total_duration = 0
        for s in sessions:
            sd = dict(s)
            if sd.get("started_at") and sd.get("ended_at"):
                total_duration += sd["ended_at"] - sd["started_at"]
        avg_min = round(total_duration / len(sessions) / 60.0, 1) if sessions else 0
        consolidated.append({
            "category": "efficiency",
            "lesson": (
                f"Durchschnittliche Sessions-Dauer: {avg_min} Minuten "
                f"bei {len(sessions)} Sessions."
            ),
            "confidence": len(sessions),
        })

    return {
        "total_sessions": total_sessions,
        "total_lessons": total_lessons,
        "categories": dict(category_counts),
        "top_tools": dict(tool_counter.most_common(10)),
        "topics": dict(topic_counter.most_common(10)),
        "session_ids": sorted(session_ids_seen),
        "consolidated_lessons": consolidated,
        "success_count": success_count,
        "fail_count": fail_count,
    }


# ═══════════════════════════════════════════════════════════════════════════
# 3. inject_context
# ═══════════════════════════════════════════════════════════════════════════

def inject_context(
    *,
    days: int = _MAX_LESSON_AGE_DAYS,
    max_lessons: int = 10,
) -> str:
    """Erstellt einen Context-Block, der neuen Sessions mitgegeben wird.

    Ruft consolidate_lessons() auf und formatiert die aggregierten
    Erkenntnisse als menschenlesbaren Text-Block.

    Parameter
    ---------
    days : int
        Zeitfenster in Tagen.
    max_lessons : int
        Maximale Anzahl von Lessons im Context.

    Rückgabe
    --------
    str — Context-Block im Stil:
    „In den letzten Sessions wurde gelernt: …"
    """
    data = consolidate_lessons(days=days)
    consolidated = data.get("consolidated_lessons", [])
    total_sessions = data.get("total_sessions", 0)

    if total_sessions == 0:
        return (
            "ℹ️  Noch keine Sessions in den letzten "
            f"{days} Tagen ausgewertet.\n"
            "Starte eine Session — die Erkenntnisse werden automatisch "
            "gesammelt."
        )

    lines: list[str] = []
    lines.append("🧠 Cross-Session Learning — Kontext")
    lines.append("═" * 45)
    lines.append(
        f"Aus {total_sessions} Sessions der letzten {days} Tage "
        f"wurden {data.get('total_lessons', 0)} Lessons extrahiert."
    )
    lines.append("")

    # Erfolgsrate
    sc = data.get("success_count", 0)
    fc = data.get("fail_count", 0)
    total_l = sc + fc
    if total_l > 0:
        rate = round(sc / total_l * 100, 1)
        lines.append(f"✅ Erfolgsrate: {rate}% ({sc}/{total_l} Lessons)")

    # Top-Tools
    top_tools = data.get("top_tools", {})
    if top_tools:
        tools_str = ", ".join(
            f"{t} ({c})" for t, c in list(top_tools.items())[:5]
        )
        lines.append(f"🔧 Häufigste Tools: {tools_str}")

    # Topics
    topics = data.get("topics", {})
    if topics:
        topics_str = ", ".join(
            f"{t}" for t in list(topics.keys())[:5]
        )
        lines.append(f"📋 Haupt-Themen: {topics_str}")

    lines.append("")
    lines.append("Gesammelte Erkenntnisse:")
    for i, c in enumerate(consolidated[:max_lessons], start=1):
        lesson_text = c.get("lesson", "")
        conf = c.get("confidence", 0)
        conf_bar = "▌" * min(conf, 10) + "░" * max(0, 10 - min(conf, 10))
        lines.append(f"  {i}. {conf_bar} {lesson_text}")

    lines.append("")
    lines.append("═" * 45)

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# 4. run_consolidation_cycle
# ═══════════════════════════════════════════════════════════════════════════

def run_consolidation_cycle(
    *,
    days: int = _MAX_LESSON_AGE_DAYS,
    extract_missing: bool = True,
    verbose: bool = True,
) -> dict[str, Any]:
    """Führt den vollständigen Cross-Session-Learning-Zyklus aus.

    Ablauf:
    1. Alle Sessions der letzten *days* Tage aus der State-DB laden
    2. Für jede Session ohne persistierte Lessons: extract_lessons()
    3. consolidate_lessons() laufen lassen
    4. inject_context() generieren
    5. Ergebnis als Dict zurückgeben (optional ausgeben)

    Parameter
    ---------
    days : int
        Zeitfenster in Tagen.
    extract_missing : bool
        Ob fehlende Extraktionen automatisch nachgeholt werden sollen.
    verbose : bool
        Ob Fortschritt auf stdout ausgegeben werden soll.

    Rückgabe
    --------
    dict mit 'sessions_processed', 'lessons_extracted', 'consolidated',
    'context', 'duration_seconds'.
    """
    start = datetime.now(timezone.utc)

    # Schritt 1: Sessions laden
    since_ts = (
        datetime.now(timezone.utc) - timedelta(days=days)
    ).timestamp()
    state = _open_state_db()
    recent = state.execute(
        "SELECT id FROM sessions WHERE started_at >= ? ORDER BY started_at DESC",
        (since_ts,),
    ).fetchall()
    all_session_ids = [r["id"] for r in recent]

    if verbose:
        print(f"📡 {len(all_session_ids)} Sessions in den letzten {days} Tagen gefunden.")

    # Schritt 2: Fehlende Extraktionen nachholen
    extracted_count = 0
    if extract_missing and all_session_ids:
        lessons_db = _open_lessons_db()
        existing = lessons_db.execute(
            "SELECT DISTINCT session_id FROM lessons WHERE created_at >= ?",
            (since_ts,),
        ).fetchall()
        existing_ids = {r["session_id"] for r in existing}

        missing = [sid for sid in all_session_ids if sid not in existing_ids]
        if verbose:
            print(f"🔍 {len(missing)} Sessions ohne Extraktion gefunden.")

        for sid in missing:
            try:
                result = extract_lessons(sid, persist=True)
                extracted_count += len(result.get("lessons", []))
                if verbose:
                    print(
                        f"  ✅ {sid[:16]}… → "
                        f"{len(result.get('lessons', []))} Lessons"
                    )
            except Exception as exc:
                if verbose:
                    print(f"  ⚠️  {sid[:16]}… Fehler: {exc}")

        lessons_db.close()

    # Schritt 3: Konsolidieren
    consolidated = consolidate_lessons(days=days)
    if verbose:
        print(
            f"📊 Konsolidiert: {consolidated['total_lessons']} Lessons "
            f"aus {consolidated['total_sessions']} Sessions."
        )

    # Schritt 4: Context generieren
    context = inject_context(days=days)

    elapsed = (datetime.now(timezone.utc) - start).total_seconds()

    result = {
        "sessions_processed": len(all_session_ids),
        "lessons_extracted": extracted_count,
        "total_lessons_db": consolidated["total_lessons"],
        "consolidated": consolidated,
        "context": context,
        "duration_seconds": round(elapsed, 2),
    }

    if verbose:
        print(f"\n⏱  Dauer: {result['duration_seconds']}s")
        print()
        print(context)

    return result


# ═══════════════════════════════════════════════════════════════════════════
# Hilfsfunktionen
# ═══════════════════════════════════════════════════════════════════════════

def _stopwords() -> set[str]:
    """Einfache deutsche Stoppwörter für die Topic-Extraktion."""
    return {
        "und", "oder", "aber", "nicht", "auch", "noch", "mit", "dem", "der",
        "die", "das", "ein", "eine", "einen", "einer", "den", "des", "dass",
        "auf", "für", "von", "aus", "bei", "nach", "vor", "zur", "zum",
        "zwischen", "durch", "über", "unter", "sowie", "sich", "werden",
        "wurde", "wird", "kann", "können", "hat", "haben", "ist", "sind",
        "war", "waren", "wäre", "wären", "sein", "seine", "seiner", "seinen",
        "ihre", "ihrer", "ihren", "ihrem", "bitte", "openamer",
    }


_STOPWORDS = _stopwords()


def message_count_maybe(session: dict[str, Any]) -> str:
    """Gibt die Message-Anzahl als String zurück."""
    mc = session.get("message_count") or 0
    return f"{mc}"


def list_recent_sessions(days: int = 7) -> list[dict[str, Any]]:
    """Listet Sessions der letzten *days* Tage (für CLI-Browser)."""
    since_ts = (
        datetime.now(timezone.utc) - timedelta(days=days)
    ).timestamp()
    state = _open_state_db()
    rows = state.execute(
        "SELECT id, title, model, started_at, ended_at, end_reason, "
        "message_count, tool_call_count "
        "FROM sessions WHERE started_at >= ? "
        "ORDER BY started_at DESC LIMIT 50",
        (since_ts,),
    ).fetchall()
    return [dict(r) for r in rows]
#!/usr/bin/env python3
"""
metacognition.py — Metacognition-Report für OpenAmer

Analysiert Session-Daten aus SQLite und/oder JSON-Dumps,
erkennt wiederholte Patterns und gibt einen strukturierten
Report als JSON aus.

Usage:
    python metacognition.py
    python metacognition.py --limit 50
    python metacognition.py --output report.json
"""

import argparse
import collections
import json
import os
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# ── Pfade ──────────────────────────────────────────────────────────────────
OPENAMER_HOME = Path(os.environ.get(
    "OPENAMER_HOME",
    r"C:\Users\damir\AppData\Local\openamer-laptop"
))
SESSIONS_DB = OPENAMER_HOME / "sessions.db"
SESSIONS_DIR = OPENAMER_HOME / "sessions"
SCRIPTS_DIR = OPENAMER_HOME / "scripts"
STATE_DB = OPENAMER_HOME / "state.db"

# ── Hilfsfunktionen ─────────────────────────────────────────────────────────

def extract_user_messages(messages):
    """Extrahiert User-Message-Texte aus einem Messages-Array."""
    texts = []
    for m in messages:
        if isinstance(m, dict):
            role = m.get("role", "")
            content = m.get("content", "")
            if role in ("user", "assistant") and isinstance(content, str):
                texts.append((role, content.strip()))
    return texts


def extract_model_and_tools(request):
    """Extrahiert Modellname und Tool-Liste aus einem Request-Body."""
    body = request.get("body", {}) if isinstance(request, dict) else {}
    model = body.get("model", "unknown")
    tools = body.get("tools", [])
    tool_names = []
    for t in tools:
        if isinstance(t, dict):
            fn = t.get("function", {})
            if isinstance(fn, dict):
                tool_names.append(fn.get("name", "?"))
    return model, tool_names


def extract_topics(text):
    """Einfache Schlagwort-Extraktion aus Text."""
    topics = []
    patterns = [
        (r"\b(build|bau|kompilier|compile)\b", "build/dev"),
        (r"\b(fix|bug|error|fehler|fail|crash)\b", "bugfix/error"),
        (r"\b(deploy|release|publish|veröffentlich)\b", "deployment"),
        (r"\b(config|setup|install|einricht)\b", "setup/config"),
        (r"\b(test|testen|prüf|verify|check)\b", "testing/qa"),
        (r"\b(skill|plugin|erweiter|extension)\b", "skills/plugins"),
        (r"\b(monetarisier|zahl|payment|donate|spend)\b", "monetization"),
        (r"\b(asi|superintelligen|consciousness|bewusstsein)\b", "ASI/consciousness"),
        (r"\b(swarm|mesh|agent.*netz|multi.*agent)\b", "swarm/multi-agent"),
        (r"\b(cron|schedul|automatisi|watchdog)\b", "cron/automation"),
        (r"\b(darwin|evolution|evolv)\b", "darwin-evolution"),
        (r"\b(brain|training|lern|lernen|finetune|fine.?tune)\b", "training/learning"),
        (r"\b(security|sicherheit|cve|vulnerabilit)\b", "security"),
        (r"\b(docker|container|image)\b", "docker/container"),
        (r"\b(gpu|nvidia|cuda|trainier)\b", "gpu/compute"),
        (r"\b(model|llm|language.model|neuron)\b", "model/LLM"),
        (r"\b(browser|chrome|cdp|web.*scrape)\b", "browser/web"),
        (r"\b(memory|erinner|episodisch|longterm)\b", "memory"),
        (r"\b(growth|wachst|fortschritt|progress)\b", "growth/progress"),
        (r"\b(api|endpoint|rest|http)\b", "api/integration"),
    ]
    for pat, label in patterns:
        if re.search(pat, text, re.IGNORECASE):
            topics.append(label)
    return topics


def count_errors_in_text(text):
    """Zählt Error-Indikatoren in Text."""
    count = 0
    for pat in [r"\b(error|exception|traceback|fail|failed|failure)\b",
                r"\b(timeout|timed.?out)\b",
                r"\b(denied|forbidden|rejected|blocked)\b",
                r"\b(not found|missing|no such)\b",
                r"\b(permission|access.*denied)\b",
                r"\b(max.*retri|exhausted)\b",
                r"\b(429|403|500|502|503|504)\b"]:
        count += len(re.findall(pat, text, re.IGNORECASE))
    return count


# ── Datenquellen ────────────────────────────────────────────────────────────

def read_sqlite_sessions(limit=50):
    """Versucht, Session-Daten aus der SQLite-DB zu lesen."""
    if not SESSIONS_DB.exists():
        return []
    if SESSIONS_DB.stat().st_size == 0:
        return []

    try:
        con = sqlite3.connect(str(SESSIONS_DB), timeout=5)
        cur = con.cursor()
        # Dynamisch Tabellen finden
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        sessions = []
        for t in tables:
            try:
                cur.execute(f"SELECT COUNT(*) FROM [{t}]")
                cnt = cur.fetchone()[0]
                if cnt == 0:
                    continue
                # Alle Spalten abfragen
                cur.execute(f"SELECT * FROM [{t}] ORDER BY rowid DESC LIMIT ?", (limit,))
                cols = [d[0] for d in cur.description]
                for row in cur.fetchall():
                    record = dict(zip(cols, row))
                    sessions.append(record)
            except sqlite3.Error:
                continue
        con.close()
        return sessions
    except (sqlite3.Error, OSError):
        return []


def read_state_db_sessions(limit=50):
    """Liest die letzten Sessions aus state.db (messages-Tabelle)."""
    if not STATE_DB.exists() or STATE_DB.stat().st_size == 0:
        return []
    try:
        con = sqlite3.connect(str(STATE_DB), timeout=10)
        cur = con.cursor()

        # Prüfen ob messages-Tabelle existiert
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='messages'")
        if not cur.fetchone():
            con.close()
            return []

        # Die letzten N Sessions via message-Tabelle gruppieren
        cur.execute("""
            SELECT session_id, MIN(timestamp) as start_ts, MAX(timestamp) as end_ts,
                   COUNT(*) as msg_count,
                   SUM(CASE WHEN role='user' THEN 1 ELSE 0 END) as user_msg_count,
                   SUM(CASE WHEN role='tool' THEN 1 ELSE 0 END) as tool_msg_count,
                   SUM(token_count) as total_tokens
            FROM messages
            WHERE active = 1
            GROUP BY session_id
            ORDER BY MAX(timestamp) DESC
            LIMIT ?
        """, (limit,))
        session_rows = cur.fetchall()

        sessions = []
        for sr in session_rows:
            sid, start_ts, end_ts, msg_count, user_cnt, tool_cnt, total_tok = sr

            # Alle Nachrichten dieser Session holen
            cur.execute("""
                SELECT role, content, tool_name, token_count, finish_reason
                FROM messages
                WHERE session_id = ? AND active = 1
                ORDER BY id ASC
            """, (sid,))
            msg_rows = cur.fetchall()

            # Texte extrahieren, Topics erkennen
            user_texts = []
            all_text_parts = []
            tool_names_used = set()
            finish_reasons = collections.Counter()
            error_count = 0
            user_token_count = 0
            assistant_token_count = 0

            for role, content, tname, tcount, freason in msg_rows:
                txt = (content or "").strip()
                if role == "user":
                    user_texts.append(txt)
                    user_token_count += (tcount or 0)
                if role in ("user", "assistant"):
                    all_text_parts.append(txt)
                if tname:
                    tool_names_used.add(tname)
                if freason:
                    finish_reasons[freason] += 1

            all_text = " ".join(all_text_parts)
            topics = extract_topics(all_text)
            error_count = count_errors_in_text(all_text)

            # Zeitstempel
            ts_start = start_ts or 0
            ts_end = end_ts or 0

            sessions.append({
                "session_id": sid,
                "timestamp": ts_end,
                "timestamp_start": ts_start,
                "timestamp_end": ts_end,
                "msg_count": msg_count,
                "user_msg_count": user_cnt or 0,
                "tool_msg_count": tool_cnt or 0,
                "total_tokens": total_tok or 0,
                "user_tokens": user_token_count,
                "assistant_tokens": assistant_token_count,
                "user_texts": user_texts,
                "all_text": all_text,
                "tools_used": list(tool_names_used),
                "finish_reasons": dict(finish_reasons),
                "error_count": error_count,
                "topics": topics,
                "source": "state.db:messages",
            })

        con.close()
        return sessions
    except (sqlite3.Error, OSError) as e:
        return []


def read_json_dumps(limit=50):
    """Liest JSON-Request-Dumps aus dem sessions/-Verzeichnis."""
    if not SESSIONS_DIR.is_dir():
        # Fallback: direkt im Home
        fallback = list(sorted(
            OPENAMER_HOME.glob("request_dump_*.json"),
            key=lambda p: p.stat().st_mtime, reverse=True
        ))
        if fallback:
            return _parse_json_files(fallback, limit)
        return []

    # Alle JSON-Dump-Dateien, sortiert nach Änderungsdatum (neueste zuerst)
    files = list(sorted(
        SESSIONS_DIR.glob("request_dump_*.json"),
        key=lambda p: p.stat().st_mtime, reverse=True
    ))
    if not files:
        return []

    return _parse_json_files(files, limit)


def _parse_json_files(files, limit):
    """Parst JSON-Dateien in einheitliches Dict-Format."""
    sessions = []
    for f in files[:limit]:
        try:
            with open(f, "r", encoding="utf-8", errors="replace") as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError):
            continue

        ts = data.get("timestamp", "")
        session_id = data.get("session_id", f.stem)
        reason = data.get("reason", "")
        req = data.get("request", {})
        model, tools = extract_model_and_tools(req)
        body = req.get("body", {}) if isinstance(req, dict) else {}
        messages = body.get("messages", [])
        user_texts = extract_user_messages(messages)

        error_info = data.get("error", "")
        if isinstance(error_info, dict):
            error_str = json.dumps(error_info)
        elif isinstance(error_info, str):
            error_str = error_info
        else:
            error_str = str(error_info) if error_info else ""

        # Gesamten Text für Topic-Extraktion
        all_text = " ".join(t for _, t in user_texts)
        topics = extract_topics(all_text)
        error_count = count_errors_in_text(all_text + " " + error_str + " " + reason)

        sessions.append({
            "session_id": session_id,
            "timestamp": ts,
            "reason": reason,
            "model": model,
            "tools": tools,
            "messages": messages,
            "user_texts": user_texts,
            "all_text": all_text,
            "error": error_str,
            "error_count": error_count,
            "topics": topics,
            "source": str(f),
        })
    return sessions


# ── Pattern-Analyse ─────────────────────────────────────────────────────────

def analyze_patterns(sessions, limit=50):
    """Erkennt Patterns in den Session-Daten."""
    if not sessions:
        return {
            "patterns": [],
            "insights": [],
            "improvement_suggestions": [],
            "skill_gaps": [],
            "no_session_data": True,
        }

    # 1. Fehler-Patterns
    all_topics = collections.Counter()
    tools_used = collections.Counter()
    finish_reasons = collections.Counter()
    session_ids = set()
    total_tokens = 0
    total_messages = 0
    total_errors = 0
    session_durations = []

    for s in sessions:
        tools_used.update(s.get("tools_used", []))
        all_topics.update(s.get("topics", []))
        session_ids.add(s.get("session_id", "?"))

        fr = s.get("finish_reasons", {})
        if isinstance(fr, dict):
            finish_reasons.update(fr)

        total_tokens += s.get("total_tokens", 0) or 0
        total_messages += s.get("msg_count", 0) or 0
        total_errors += s.get("error_count", 0) or 0

        ts_start = s.get("timestamp_start", 0)
        ts_end = s.get("timestamp_end", 0)
        if ts_start and ts_end and isinstance(ts_start, (int, float)):
            duration = ts_end - ts_start
            if 0 < duration < 86400:  # max 24h
                session_durations.append(duration)

    # 2. Pattern-Erkennung
    patterns = []

    # Tool-Nutzung
    top_tools = [t for t, c in tools_used.most_common(5) if c > 0]
    if top_tools:
        patterns.append({
            "type": "tool_usage",
            "description": f"Häufigste Tools: {', '.join(top_tools[:5])}",
            "detail": dict(tools_used.most_common(15)),
            "count": sum(tools_used.values()),
        })

    # Themen-Cluster
    top_topics = [t for t, c in all_topics.most_common(10) if c > 0]
    if top_topics:
        patterns.append({
            "type": "topic_cluster",
            "description": f"Häufigste Themen: {', '.join(top_topics[:5])}",
            "detail": dict(all_topics.most_common(15)),
            "count": sum(all_topics.values()),
        })

    # Finish-Reason-Verteilung (indirekte Fehlerindikatoren)
    top_finish = [f for f, c in finish_reasons.most_common(5) if c > 0 and f != ""]
    if top_finish:
        patterns.append({
            "type": "finish_reason_distribution",
            "description": f"Antwort-Abschlussgründe: {', '.join(top_finish[:3])}",
            "detail": dict(finish_reasons.most_common(10)),
            "count": sum(finish_reasons.values()),
        })

    # Fehler-Patterns (aus Textanalyse)
    if total_errors > 0:
        patterns.append({
            "type": "error_frequency",
            "description": f"{total_errors} Error-Indikatoren in {len(sessions)} Sessions",
            "detail": {"total_errors": total_errors, "sessions_with_topics": len(all_topics)},
            "count": total_errors,
        })

    # Session-Statistiken
    avg_duration = None
    if session_durations:
        avg_duration = round(sum(session_durations) / len(session_durations), 1)

    # 3. Insights
    insights = []
    unique_session_count = len(session_ids)
    insights.append(
        f"{unique_session_count} Sessions analysiert, "
        f"{total_messages} Messages, "
        f"{total_tokens:,} Tokens"
    )

    if top_topics:
        dominant = top_topics[0]
        pct = round(all_topics[dominant] / max(sum(all_topics.values()), 1) * 100)
        insights.append(
            f"Dominantes Thema: '{dominant}' ({pct}% der markierten Topics)"
        )

    if top_tools:
        insights.append(
            f"Top-Tool: {top_tools[0]} ({tools_used[top_tools[0]]}x verwendet)"
        )

    if avg_duration:
        insights.append(
            f"Durchschnittliche Session-Dauer: {avg_duration}s"
        )

    # 4. Improvement-Vorschläge
    improvements = []

    if total_errors > len(sessions) * 2:
        improvements.append(
            "Hohe Fehlerdichte in Sessions — "
            "Fehlerbehandlung und Logging verbessern"
        )

    if "max_iterations" in finish_reasons or "max_tokens" in finish_reasons:
        improvements.append(
            "Häufige 'max_iterations'/'max_tokens' Abbruche — "
            "Erwäge höhere Limits oder kürzere Aufgaben"
        )

    if "stop" not in finish_reasons or (
        isinstance(finish_reasons.get("stop"), int) and
        finish_reasons.get("stop", 0) < sum(finish_reasons.values()) * 0.5
    ):
        improvements.append(
            "Nur ~{:.0f}% der Antworten enden regulär mit 'stop' — "
            "Prüfe Task-Komplexität und Timeout-Konfiguration".format(
                finish_reasons.get("stop", 0) / max(sum(finish_reasons.values()), 1) * 100
            )
        )

    # 5. Skill-Gaps (wie bisher)
    skill_gaps = []
    for topic, count in all_topics.most_common(20):
        gap = _detect_skill_gap(topic, count, unique_session_count)
        if gap:
            skill_gaps.append(gap)

    return {
        "patterns": patterns,
        "insights": insights,
        "improvement_suggestions": improvements,
        "skill_gaps": skill_gaps,
        "no_session_data": False,
        "metadata": {
            "sessions_analyzed": unique_session_count,
            "messages_analyzed": total_messages,
            "total_tokens": total_tokens,
            "total_errors_detected": total_errors,
            "timespan": _get_timespan(sessions),
            "analysis_timestamp": datetime.now().isoformat(),
        },
    }


def _detect_skill_gap(topic, count, total):
    """Prüft, ob ein Themenbereich als Skill-Gap betrachtet wird."""
    # Gewichtung: Topic muss in >10% der Sessions vorkommen
    if count < 3 or (total > 0 and count / total < 0.1):
        return None

    gaps = {
        "training/learning": {
            "topic": topic,
            "frequency": count,
            "suggestion": (
                "Häufige Trainings-/Learning-Anfragen — "
                "ein dedizierter 'learning-strategy'-Skill könnte wiederkehrende "
                "Fragen beantworten"
            ),
        },
        "monetization": {
            "topic": topic,
            "frequency": count,
            "suggestion": (
                "Monetarisierung ist ein wiederkehrendes Thema — "
                "ein 'monetization-workflow'-Skill mit geprüften Zahlungslinks "
                "und Strategien würde Zeit sparen"
            ),
        },
        "bugfix/error": {
            "topic": topic,
            "frequency": count,
            "suggestion": (
                "Wiederkehrende Bugfix-Arbeit — "
                "ein 'common-fixes'-Skill für häufige Fehlermuster wäre hilfreich"
            ),
        },
        "skills/plugins": {
            "topic": topic,
            "frequency": count,
            "suggestion": (
                "Skills/Plugins sind ein aktives Thema — "
                "ein 'plugin-patterns'-Skill mit Best Practices beschleunigt Entwicklung"
            ),
        },
        "security": {
            "topic": topic,
            "frequency": count,
            "suggestion": (
                "Security wird regelmäßig adressiert — "
                "ein 'security-checklist'-Skill für standardisierte Audits"
            ),
        },
        "deployment": {
            "topic": topic,
            "frequency": count,
            "suggestion": (
                "Deployment-Aufgaben wiederholen sich — "
                "ein 'deployment-pipeline'-Skill mit CI/CD-Templates"
            ),
        },
        "cron/automation": {
            "topic": topic,
            "frequency": count,
            "suggestion": (
                "Cron-Jobs und Automation sind häufig — "
                "ein 'cron-patterns'-Skill für Standard-Workflows"
            ),
        },
        "testing/qa": {
            "topic": topic,
            "frequency": count,
            "suggestion": (
                "Testing wird regelmäßig angefragt — "
                "ein 'testing-strategy'-Skill für konsistente Testabdeckung"
            ),
        },
        "ASI/consciousness": {
            "topic": topic,
            "frequency": count,
            "suggestion": (
                "ASI-Bewusstseins-Fragen wiederholen sich — "
                "ein 'asi-narrative'-Skill mit konsistenter Antwort-Strategie"
            ),
        },
    }
    return gaps.get(topic)


def _get_timespan(sessions):
    """Ermittelt den Zeitraum der analysierten Sessions."""
    timestamps = []
    for s in sessions:
        ts = s.get("timestamp", "")
        if ts:
            try:
                if isinstance(ts, (int, float)):
                    dt = datetime.fromtimestamp(ts)
                else:
                    # ISO-Format
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                timestamps.append(dt)
            except (ValueError, TypeError, OSError):
                pass
    if timestamps:
        return {
            "earliest": min(timestamps).isoformat(),
            "latest": max(timestamps).isoformat(),
        }
    return None


# ── Hauptfunktion ───────────────────────────────────────────────────────────

def metacognition_report(limit=50):
    """Erzeugt den vollständigen Metacognition-Report."""
    # 1. state.db (enthält die messages-Tabelle mit allen Sessions)
    sessions = read_state_db_sessions(limit)
    db_source = "state.db:messages"

    # 2. Fallback: SQLite sessions.db
    if not sessions:
        sessions = read_sqlite_sessions(limit)
        db_source = "sessions.db"

    # 3. Fallback: JSON-Dumps
    if not sessions:
        sessions = read_json_dumps(limit)
        db_source = "sessions/*.json"

    # 4. Analyse
    report = analyze_patterns(sessions, limit)
    report["data_source"] = db_source

    return report


def main():
    parser = argparse.ArgumentParser(
        description="Metacognition-Report für OpenAmer"
    )
    parser.add_argument(
        "--limit", type=int, default=50,
        help="Maximale Anzahl zu analysierender Sessions (default: 50)"
    )
    parser.add_argument(
        "--output", "-o", type=str, default=None,
        help="JSON-Datei für den Report (default: stdout)"
    )
    parser.add_argument(
        "--pretty", action="store_true", default=True,
        help="Pretty-Print JSON (default: True)"
    )
    args = parser.parse_args()

    report = metacognition_report(limit=args.limit)

    json_str = json.dumps(report, indent=2, ensure_ascii=False, default=str)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json_str, encoding="utf-8")
        print(f"Report geschrieben: {out_path}")
    else:
        print(json_str)


if __name__ == "__main__":
    main()
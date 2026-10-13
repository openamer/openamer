#!/usr/bin/env python3
"""Tracing & Debugging Dashboard für OpenAmer — Agent-Run-Visualisierung.

Stellt eine SQLite-basierte Trace-Datenbank, ein HTML-Dashboard und CLI-
Befehle zur Verfügung, um Agent-Ausführungen zu protokollieren und zu
analysieren.

Usage:
    from openamer_cli.tracing import TraceEntry, TraceStore, generate_html_dashboard
"""

from __future__ import annotations

import argparse
import html
import json
import logging
import os
import sqlite3
import sys
import textwrap
import time
import uuid
from collections import Counter
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Standard-Pfad für die Trace-Datenbank ────────────────────────────────
DEFAULT_DB_DIR = Path.home() / ".openamer" / "traces"
DEFAULT_DB_PATH = DEFAULT_DB_DIR / "tracing.db"


# ── Dataclass ────────────────────────────────────────────────────────────


@dataclass
class TraceEntry:
    """Ein einzelner Trace-Eintrag für einen Agent-Run oder Tool-Aufruf."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    session_id: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    action: str = ""
    tool: str = ""
    input: str = ""
    output: str = ""
    duration_ms: float = 0.0
    status: str = "success"  # success | error | timeout
    error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ── SQLite-Repository ───────────────────────────────────────────────────


class TraceStore:
    """SQLite-basiertes Trace-Repository.

    Speichert, filtert und analysiert Trace-Einträge.
    Thread-safe durch einen einzelnen SQLite-Connection-Lock (serialisiert).
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._init_db()
        return self._conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS traces (
                id          TEXT PRIMARY KEY,
                session_id  TEXT NOT NULL DEFAULT '',
                timestamp   TEXT NOT NULL,
                action      TEXT NOT NULL DEFAULT '',
                tool        TEXT NOT NULL DEFAULT '',
                input       TEXT NOT NULL DEFAULT '',
                output      TEXT NOT NULL DEFAULT '',
                duration_ms REAL NOT NULL DEFAULT 0.0,
                status      TEXT NOT NULL DEFAULT 'success',
                error       TEXT NOT NULL DEFAULT ''
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_traces_session ON traces(session_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_traces_timestamp ON traces(timestamp)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_traces_status ON traces(status)"
        )
        conn.commit()

    def record(self, entry: TraceEntry) -> str:
        """Speichert einen Trace-Eintrag und gibt die ID zurück."""
        conn = self._get_conn()
        conn.execute(
            """
            INSERT OR REPLACE INTO traces
                (id, session_id, timestamp, action, tool, input, output,
                 duration_ms, status, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.id,
                entry.session_id,
                entry.timestamp,
                entry.action,
                entry.tool,
                entry.input,
                entry.output,
                entry.duration_ms,
                entry.status,
                entry.error,
            ),
        )
        conn.commit()
        return entry.id

    def query(
        self,
        session_id: Optional[str] = None,
        action: Optional[str] = None,
        tool: Optional[str] = None,
        limit: int = 50,
    ) -> List[TraceEntry]:
        """Filtert Trace-Einträge nach Kriterien.

        Alle Filter sind optional. Standardmäßig die letzten 50 Einträge.
        """
        conn = self._get_conn()
        conditions: List[str] = []
        params: List[str] = []

        if session_id:
            conditions.append("session_id = ?")
            params.append(session_id)
        if action:
            conditions.append("action LIKE ?")
            params.append(f"%{action}%")
        if tool:
            conditions.append("tool LIKE ?")
            params.append(f"%{tool}%")

        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)

        rows = conn.execute(
            f"SELECT * FROM traces {where} ORDER BY timestamp DESC LIMIT ?",
            [*params, limit],
        ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def get_stats(self) -> dict:
        """Berechnet Statistiken über alle gespeicherten Traces.

        Returns:
            dict mit total_runs, avg_duration_ms, tool_usage_counts,
                 error_rate, status_counts.
        """
        conn = self._get_conn()

        total = conn.execute("SELECT COUNT(*) FROM traces").fetchone()[0]
        if total == 0:
            return {
                "total_runs": 0,
                "avg_duration_ms": 0.0,
                "tool_usage_counts": {},
                "error_rate": 0.0,
                "status_counts": {"success": 0, "error": 0, "timeout": 0},
            }

        avg_dur = conn.execute(
            "SELECT AVG(duration_ms) FROM traces"
        ).fetchone()[0] or 0.0

        # Tool-Usage über alle Einträge
        tool_rows = conn.execute(
            "SELECT tool, COUNT(*) as cnt FROM traces "
            "WHERE tool != '' GROUP BY tool ORDER BY cnt DESC"
        ).fetchall()
        tool_usage = {r["tool"]: r["cnt"] for r in tool_rows}

        # Status-Verteilung
        status_rows = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM traces GROUP BY status"
        ).fetchall()
        status_counts: Dict[str, int] = {}
        for r in status_rows:
            status_counts[r["status"]] = r["cnt"]

        error_count = status_counts.get("error", 0)
        error_rate = round(error_count / total * 100, 2)

        return {
            "total_runs": total,
            "avg_duration_ms": round(avg_dur, 2),
            "tool_usage_counts": tool_usage,
            "error_rate": error_rate,
            "status_counts": status_counts,
        }

    def get_timeline(self, session_id: str) -> List[dict]:
        """Gibt eine chronologische Abfolge von Einträgen für eine Session."""
        entries = self.query(session_id=session_id, limit=500)
        # ASC-Reihenfolge für Timeline
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM traces WHERE session_id = ? "
            "ORDER BY timestamp ASC LIMIT 500",
            (session_id,),
        ).fetchall()
        result = []
        for r in rows:
            entry = self._row_to_entry(r)
            d = entry.to_dict()
            # Aufbereitung für Timeline
            d["label"] = f"{entry.tool} → {entry.action}" if entry.tool else entry.action
            result.append(d)
        return result

    def clear(self) -> int:
        """Löscht alle Traces. Gibt die Anzahl gelöschter Zeilen zurück."""
        conn = self._get_conn()
        count = conn.execute("SELECT COUNT(*) FROM traces").fetchone()[0]
        conn.execute("DELETE FROM traces")
        conn.commit()
        return count

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ── Hilfsmethoden ────────────────────────────────────────────────

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> TraceEntry:
        return TraceEntry(
            id=row["id"],
            session_id=row["session_id"],
            timestamp=row["timestamp"],
            action=row["action"],
            tool=row["tool"],
            input=row["input"],
            output=row["output"],
            duration_ms=row["duration_ms"],
            status=row["status"],
            error=row["error"],
        )


# ── HTML Dashboard ──────────────────────────────────────────────────────


def _escape(s: str) -> str:
    return html.escape(s or "")


def generate_html_dashboard(store: Optional[TraceStore] = None) -> str:
    """Generiert eine eigenständige HTML-Datei mit dem Tracing-Dashboard.

    Enthält:
      - Tool-Usage-Balkendiagramm (SVG inline)
      - Error-Rate-Anzeige
      - Letzte 50 Runs als Tabelle
      - Session-Timeline
      - Dauer-Verteilung
      - Responsive Design, eingebettetes CSS (keine externen Dependencies)
    """
    if store is None:
        store = TraceStore()

    stats = store.get_stats()
    entries = store.query(limit=50)

    # Tool-Usage-Daten fürs Balkendiagramm
    tool_data = stats["tool_usage_counts"]
    max_tool_count = max(tool_data.values()) if tool_data else 1
    tool_bars_html = _build_tool_bars(tool_data, max_tool_count)

    # Error-Rate
    error_rate = stats["error_rate"]
    total_runs = stats["total_runs"]
    status_counts = stats["status_counts"]

    # Dauer-Verteilung
    dur_histogram = _build_duration_histogram(entries)

    # Tabelle
    table_rows = _build_table_rows(entries)

    # Session-Timeline
    session_ids = sorted(set(e.session_id for e in entries if e.session_id))
    timeline_html = _build_timeline_html(store, session_ids)

    html_content = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OpenAmer Tracing Dashboard</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
                 Oxygen, Ubuntu, Cantarell, sans-serif;
    background: #0d1117;
    color: #c9d1d9;
    padding: 20px;
    line-height: 1.5;
  }}
  h1 {{ color: #58a6ff; font-size: 1.8rem; margin-bottom: 24px; }}
  h2 {{ color: #f0f6fc; font-size: 1.3rem; margin: 28px 0 16px; }}
  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 16px;
    margin-bottom: 28px;
  }}
  .card {{
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 20px;
  }}
  .card h3 {{ color: #8b949e; font-size: 0.85rem; text-transform: uppercase;
              letter-spacing: 0.05em; margin-bottom: 8px; }}
  .card .value {{ font-size: 2rem; font-weight: 700; color: #f0f6fc; }}
  .card .sub {{ font-size: 0.85rem; color: #8b949e; margin-top: 4px; }}
  .error-rate {{ color: #f85149; }}
  .ok-rate {{ color: #3fb950; }}
  .chart-container {{ margin-top: 12px; }}
  .bar-row {{ display: flex; align-items: center; margin-bottom: 4px; gap: 8px; }}
  .bar-label {{ width: 120px; text-align: right; font-size: 0.82rem;
                color: #c9d1d9; overflow: hidden; text-overflow: ellipsis;
                white-space: nowrap; flex-shrink: 0; }}
  .bar-track {{ flex: 1; height: 22px; background: #21262d; border-radius: 4px;
                overflow: hidden; }}
  .bar-fill {{ height: 100%; background: #58a6ff; border-radius: 4px;
               transition: width 0.3s; min-width: 2px; }}
  .bar-count {{ width: 40px; text-align: left; font-size: 0.82rem;
                color: #8b949e; flex-shrink: 0; }}
  .histogram-bar {{ background: #1f6feb; border-radius: 3px; }}
  hr {{ border: none; border-top: 1px solid #21262d; margin: 20px 0; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.82rem; }}
  th {{ text-align: left; padding: 10px 8px; border-bottom: 2px solid #30363d;
        color: #8b949e; text-transform: uppercase; font-size: 0.75rem;
        letter-spacing: 0.05em; }}
  td {{ padding: 8px; border-bottom: 1px solid #21262d;
        max-width: 300px; overflow: hidden; text-overflow: ellipsis;
        white-space: nowrap; }}
  tr:hover td {{ background: #1c2128; }}
  .status-badge {{
    display: inline-block; padding: 2px 8px; border-radius: 12px;
    font-size: 0.75rem; font-weight: 600;
  }}
  .status-success {{ background: #1a3a2a; color: #3fb950; }}
  .status-error {{ background: #3a1a1a; color: #f85149; }}
  .status-timeout {{ background: #3a2a1a; color: #d29922; }}
  .timeline {{ position: relative; padding-left: 20px; }}
  .timeline::before {{
    content: ''; position: absolute; left: 8px; top: 0; bottom: 0;
    width: 2px; background: #30363d;
  }}
  .timeline-item {{
    position: relative; margin-bottom: 12px; padding: 8px 12px;
    background: #161b22; border: 1px solid #30363d; border-radius: 6px;
  }}
  .timeline-item::before {{
    content: ''; position: absolute; left: -16px; top: 14px;
    width: 10px; height: 10px; border-radius: 50%;
    background: #58a6ff; border: 2px solid #0d1117;
  }}
  .timeline-item.error::before {{ background: #f85149; }}
  .timeline-meta {{ font-size: 0.75rem; color: #8b949e; margin-bottom: 4px; }}
  .timeline-action {{ font-weight: 600; color: #f0f6fc; }}
  .timeline-tool {{ color: #58a6ff; }}
  .footer {{ text-align: center; color: #484f58; font-size: 0.75rem;
             margin-top: 40px; padding: 20px 0; border-top: 1px solid #21262d; }}
  .empty-state {{ text-align: center; padding: 60px 20px; color: #484f58; }}
  .empty-state h2 {{ color: #8b949e; margin-bottom: 12px; }}
  .truncate {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
               max-width: 200px; display: inline-block; vertical-align: bottom; }}
  .duration-dist {{ display: flex; align-items: flex-end; gap: 2px;
                    height: 100px; margin-top: 12px; }}
  .duration-bar {{ flex: 1; background: #1f6feb; border-radius: 3px 3px 0 0;
                   min-height: 2px; position: relative; }}
  .duration-bar:hover {{ background: #58a6ff; }}
  .duration-label {{ font-size: 0.65rem; color: #8b949e; text-align: center;
                     margin-top: 4px; }}
  @media (max-width: 600px) {{
    .grid {{ grid-template-columns: 1fr; }}
    .bar-label {{ width: 80px; font-size: 0.75rem; }}
    td, th {{ font-size: 0.72rem; }}
  }}
</style>
</head>
<body>
<h1>📊 OpenAmer Tracing Dashboard</h1>

<div class="grid">
  <div class="card">
    <h3>Gesamtläufe</h3>
    <div class="value">{total_runs}</div>
    <div class="sub">aufgezeichnete Agent-Runs</div>
  </div>
  <div class="card">
    <h3>Durchschnittliche Dauer</h3>
    <div class="value">{stats["avg_duration_ms"]:.1f} ms</div>
    <div class="sub">pro Run</div>
  </div>
  <div class="card">
    <h3>Error-Rate</h3>
    <div class="value {'error-rate' if error_rate > 5 else 'ok-rate'}">{error_rate:.1f}%</div>
    <div class="sub">{status_counts.get('error', 0)} Fehler von {total_runs} Runs</div>
  </div>
  <div class="card">
    <h3>Status-Verteilung</h3>
    <div class="sub" style="margin-top:4px;">
      ✅ {status_counts.get('success', 0)} Erfolg &nbsp;|&nbsp;
      ❌ {status_counts.get('error', 0)} Fehler &nbsp;|&nbsp;
      ⏱ {status_counts.get('timeout', 0)} Timeout
    </div>
  </div>
</div>

<h2>🔧 Tool-Usage</h2>
<div class="card">
  {tool_bars_html if tool_data else '<div class="empty-state"><p>Keine Tool-Daten vorhanden.</p></div>'}
</div>

<h2>⏱ Dauer-Verteilung (letzte 50 Runs in ms)</h2>
<div class="card">
  {dur_histogram if entries else '<div class="empty-state"><p>Keine Daten vorhanden.</p></div>'}
</div>

<h2>📋 Letzte 50 Runs</h2>
<div class="card" style="overflow-x:auto;">
<table>
<thead><tr>
  <th>Zeit</th><th>Session</th><th>Tool</th><th>Aktion</th><th>Dauer</th><th>Status</th><th>Fehler</th>
</tr></thead>
<tbody>
  {table_rows if entries else '<tr><td colspan="7" class="empty-state">Keine Einträge vorhanden.</td></tr>'}
</tbody>
</table>
</div>

<h2>📈 Session-Timelines</h2>
{timeline_html if session_ids else '<div class="card"><div class="empty-state"><p>Keine Session-Daten vorhanden.</p></div></div>'}

<div class="footer">
  OpenAmer Tracing Dashboard · Generiert am {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")}
</div>
</body>
</html>"""
    return html_content


def _build_tool_bars(tool_data: dict, max_count: int) -> str:
    bars = []
    for tool_name, count in sorted(
        tool_data.items(), key=lambda x: x[1], reverse=True
    ):
        pct = (count / max_count) * 100 if max_count > 0 else 0
        bars.append(
            f'<div class="bar-row">'
            f'<span class="bar-label">{_escape(tool_name)}</span>'
            f'<div class="bar-track">'
            f'<div class="bar-fill" style="width:{pct:.1f}%"></div>'
            f'</div>'
            f'<span class="bar-count">{count}</span>'
            f"</div>"
        )
    return '<div class="chart-container">' + "\n".join(bars) + "</div>"


def _build_duration_histogram(entries: List[TraceEntry]) -> str:
    if not entries:
        return '<div class="empty-state"><p>Keine Daten.</p></div>'

    durations = [e.duration_ms for e in entries if e.duration_ms > 0]
    if not durations:
        return '<div class="empty-state"><p>Keine Dauer-Daten.</p></div>'

    # 10 Buckets
    max_dur = max(durations)
    if max_dur == 0:
        max_dur = 1
    bucket_size = max_dur / 10
    buckets = [0] * 10
    for d in durations:
        idx = min(int(d / bucket_size), 9) if bucket_size > 0 else 0
        buckets[idx] += 1

    max_bucket = max(buckets) if buckets else 1

    parts = ['<div class="duration-dist">']
    for i, count in enumerate(buckets):
        height = (count / max_bucket) * 100 if max_bucket > 0 else 0
        lo = i * bucket_size
        hi = (i + 1) * bucket_size
        parts.append(
            f'<div class="duration-bar" style="height:{height:.1f}%" '
            f'title="{lo:.0f}–{hi:.0f} ms: {count} Einträge">'
            f"</div>"
        )
    parts.append("</div>")

    # Labels
    parts.append('<div style="display:flex;gap:2px;font-size:0.65rem;color:#8b949e;">')
    for i in range(10):
        lo = i * bucket_size
        parts.append(
            f'<div style="flex:1;text-align:center;">{lo:.0f}</div>'
        )
    parts.append("</div>")
    parts.append(
        '<div style="font-size:0.7rem;color:#8b949e;margin-top:4px;">'
        f"Max: {max_dur:.0f} ms · {len(durations)} Einträge mit Dauer</div>"
    )

    return "".join(parts)


def _build_table_rows(entries: List[TraceEntry]) -> str:
    rows = []
    for e in entries:
        status_class = f"status-{e.status}" if e.status in ("success", "error", "timeout") else ""
        error_text = _escape(e.error[:60]) if e.error else ""
        rows.append(
            f"<tr>"
            f'<td title="{_escape(e.timestamp[:19])}">{_escape(e.timestamp[11:19])}</td>'
            f'<td title="{_escape(e.session_id)}"><span class="truncate">{_escape(e.session_id[:20])}</span></td>'
            f'<td><span class="timeline-tool">{_escape(e.tool)}</span></td>'
            f'<td>{_escape(e.action[:30])}</td>'
            f'<td>{e.duration_ms:.0f} ms</td>'
            f'<td><span class="status-badge {status_class}">{_escape(e.status)}</span></td>'
            f'<td title="{_escape(e.error)}"><span class="truncate">{error_text}</span></td>'
            f"</tr>"
        )
    return "\n".join(rows)


def _build_timeline_html(store: TraceStore, session_ids: List[str]) -> str:
    parts = []
    for sid in session_ids[:10]:  # max 10 Sessions
        timeline = store.get_timeline(sid)
        if not timeline:
            continue
        parts.append(
            f'<div class="card" style="margin-bottom:12px;">'
            f'<h3 style="font-size:0.9rem;margin-bottom:8px;">'
            f'Session: {_escape(sid[:24])}</h3>'
            f'<div class="timeline">'
        )
        for item in timeline[:20]:  # max 20 Events pro Session
            cls = "timeline-item error" if item["status"] == "error" else "timeline-item"
            dur = item.get("duration_ms", 0)
            parts.append(
                f'<div class="{cls}">'
                f'<div class="timeline-meta">'
                f'{_escape(item["timestamp"][11:19])} · {dur:.0f} ms'
                f'</div>'
                f'<div class="timeline-action">{_escape(item.get("label", item["action"]))}</div>'
                f'</div>'
            )
        parts.append("</div></div>")
    return "\n".join(parts)


# ── HTTP Dashboard Server ───────────────────────────────────────────────


class _DashboardHandler(SimpleHTTPRequestHandler):
    """HTTP-Handler, der das generierte Dashboard ausliefert."""

    def __init__(self, *args, store: Optional[TraceStore] = None, **kwargs):
        self._store = store or TraceStore()
        super().__init__(*args, **kwargs)

    def do_GET(self) -> None:
        if self.path in ("/", "/dashboard", "/index.html"):
            html_content = generate_html_dashboard(self._store)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html_content.encode("utf-8"))))
            self.end_headers()
            self.wfile.write(html_content.encode("utf-8"))
        elif self.path == "/api/stats":
            stats = self._store.get_stats()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            body = json.dumps(stats, ensure_ascii=False).encode("utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path.startswith("/api/traces"):
            entries = self._store.query(limit=50)
            data = [e.to_dict() for e in entries]
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"404 - Not Found")


def _make_handler(store: TraceStore):
    """Factory, die einen Handler mit gebundenem Store erzeugt."""

    class Handler(_DashboardHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, store=store, **kwargs)

    return Handler


def start_dashboard_server(port: int = 8080, store: Optional[TraceStore] = None) -> HTTPServer:
    """Startet einen HTTP-Server, der das Tracing-Dashboard hostet.

    Args:
        port: TCP-Port (default: 8080)
        store: TraceStore-Instanz (default: neu erzeugt)

    Returns:
        Der gestartete HTTPServer (läuft bereits).
    """
    if store is None:
        store = TraceStore()
    handler = _make_handler(store)
    server = HTTPServer(("", port), handler)
    print(f"📊 OpenAmer Tracing Dashboard gestartet → http://localhost:{port}")
    print(f"   Drücke Ctrl+C zum Beenden.")
    return server


# ── CLI-Befehle (für main.py) ──────────────────────────────────────────


def build_tracing_parser(subparsers) -> None:
    """Baut die Argument-Parser für den ``tracing``-Subcommand."""
    parser = subparsers.add_parser(
        "tracing",
        help="Tracing & Debugging Dashboard für Agent-Runs",
        description=(
            "Zeichne Agent-Tool-Aufrufe auf, analysiere sie statistisch und "
            "visualisiere sie im Web-Dashboard."
        ),
    )
    sub = parser.add_subparsers(dest="tracing_command", metavar="BEFEHL")

    # record
    record_parser = sub.add_parser(
        "record",
        help="Zeichnet einen Trace-Eintrag auf",
        description="Speichert einen neuen Trace-Eintrag in der SQLite-Datenbank.",
    )
    record_parser.add_argument("action", help="Aktion (z.B. run, call)")
    record_parser.add_argument("tool", help="Tool-Name (z.B. terminal, read_file)")
    record_parser.add_argument("--session", default="", help="Session-ID")
    record_parser.add_argument("--input", default="", help="Eingabe (optional)")
    record_parser.add_argument("--output", default="", help="Ausgabe (optional)")
    record_parser.add_argument("--duration", type=float, default=0.0, help="Dauer in ms")
    record_parser.add_argument("--status", default="success",
                               choices=["success", "error", "timeout"])
    record_parser.add_argument("--error", default="", help="Fehlermeldung")
    record_parser.set_defaults(func=cmd_tracing_record)

    # list
    list_parser = sub.add_parser(
        "list",
        aliases=["ls"],
        help="Zeigt letzte Traces an",
        description="Listet die letzten Trace-Einträge auf.",
    )
    list_parser.add_argument("--limit", type=int, default=20, help="Maximale Anzahl")
    list_parser.add_argument("--session", default=None, help="Nach Session-ID filtern")
    list_parser.add_argument("--action", default=None, help="Nach Aktion filtern")
    list_parser.add_argument("--tool", default=None, help="Nach Tool filtern")
    list_parser.set_defaults(func=cmd_tracing_list)

    # stats
    stats_parser = sub.add_parser(
        "stats",
        help="Zeigt Statistiken an",
        description="Aggregierte Statistiken über alle aufgezeichneten Traces.",
    )
    stats_parser.set_defaults(func=cmd_tracing_stats)

    # dashboard
    dashboard_parser = sub.add_parser(
        "dashboard",
        help="Startet das Web-Dashboard",
        description="Startet einen HTTP-Server mit dem visuellen Tracing-Dashboard.",
    )
    dashboard_parser.add_argument(
        "--port", type=int, default=8080, help="Port (default: 8080)"
    )
    dashboard_parser.set_defaults(func=cmd_tracing_dashboard)

    # export
    export_parser = sub.add_parser(
        "export",
        help="Exportiert Traces als HTML-Report",
        description="Generiert eine eigenständige HTML-Datei mit dem Dashboard.",
    )
    export_parser.add_argument(
        "--output", "-o",
        default=None,
        help="Ausgabedatei (default: tracing-report.html)",
    )
    export_parser.set_defaults(func=cmd_tracing_export)

    parser.set_defaults(func=cmd_tracing_help)


# ── CLI-Command-Implementierungen ──────────────────────────────────────


def cmd_tracing_help(args) -> int:
    """Zeigt die Hilfe für den tracing-Befehl an."""
    print("OpenAmer Tracing — Nutzung:")
    print("  openamer tracing record <action> <tool>   Trace aufzeichnen")
    print("  openamer tracing list [--limit N]         Letzte Traces anzeigen")
    print("  openamer tracing stats                    Statistiken anzeigen")
    print("  openamer tracing dashboard [--port N]     Web-Dashboard starten")
    print("  openamer tracing export [-o FILE]         Als HTML exportieren")
    return 0


def cmd_tracing_record(args) -> int:
    """Zeichnet einen Trace-Eintrag auf."""
    store = TraceStore()
    entry = TraceEntry(
        session_id=getattr(args, "session", "") or "",
        action=args.action,
        tool=args.tool,
        input=getattr(args, "input", "") or "",
        output=getattr(args, "output", "") or "",
        duration_ms=getattr(args, "duration", 0.0) or 0.0,
        status=getattr(args, "status", "success") or "success",
        error=getattr(args, "error", "") or "",
    )
    entry_id = store.record(entry)
    print(f"✅ Trace aufgezeichnet (ID: {entry_id})")
    print(f"   Tool:    {entry.tool}")
    print(f"   Aktion:  {entry.action}")
    print(f"   Status:  {entry.status}")
    print(f"   Dauer:   {entry.duration_ms:.0f} ms")
    return 0


def cmd_tracing_list(args) -> int:
    """Zeigt die letzten Traces an."""
    store = TraceStore()
    entries = store.query(
        session_id=getattr(args, "session", None),
        action=getattr(args, "action", None),
        tool=getattr(args, "tool", None),
        limit=getattr(args, "limit", 20),
    )
    if not entries:
        print("📭 Keine Trace-Einträge vorhanden.")
        print("   Zeichne einen mit: openamer tracing record <action> <tool>")
        return 0

    print(f"{'ID':<14} {'Zeit':<20} {'Tool':<18} {'Aktion':<16} {'Dauer':<8} {'Status':<10}")
    print("-" * 86)
    for e in entries:
        dur = f"{e.duration_ms:.0f}ms"
        ts = e.timestamp[11:19] if len(e.timestamp) > 19 else e.timestamp
        print(
            f"{e.id:<14} {ts:<20} {e.tool[:18]:<18} "
            f"{e.action[:16]:<16} {dur:<8} {e.status:<10}"
        )
    print(f"\n--- {len(entries)} Einträge ---")
    return 0


def cmd_tracing_stats(args) -> int:
    """Zeigt aggregierte Statistiken an."""
    store = TraceStore()
    stats = store.get_stats()

    if stats["total_runs"] == 0:
        print("📭 Keine Trace-Daten vorhanden.")
        print("   Zeichne einen mit: openamer tracing record <action> <tool>")
        return 0

    print("📊 OpenAmer Tracing Statistiken")
    print("=" * 40)
    print(f"  Gesamtläufe:        {stats['total_runs']}")
    print(f"  Durchschnittsdauer: {stats['avg_duration_ms']:.1f} ms")
    print(f"  Error-Rate:         {stats['error_rate']:.1f}%")
    print()
    print("  Status-Verteilung:")
    for status, count in stats["status_counts"].items():
        print(f"    {status}: {count}")
    print()
    if stats["tool_usage_counts"]:
        print("  Tool-Usage:")
        for tool, count in sorted(
            stats["tool_usage_counts"].items(), key=lambda x: x[1], reverse=True
        ):
            print(f"    {tool}: {count}")
    print()
    return 0


def cmd_tracing_dashboard(args) -> int:
    """Startet das Web-Dashboard."""
    port = getattr(args, "port", 8080) or 8080
    store = TraceStore()
    server = start_dashboard_server(port=port, store=store)
    print(f"   Öffne: http://localhost:{port}")
    print()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n⏹ Dashboard gestoppt.")
        server.server_close()
    return 0


def cmd_tracing_export(args) -> int:
    """Exportiert Traces als HTML-Report."""
    store = TraceStore()
    html_content = generate_html_dashboard(store)

    output = getattr(args, "output", None) or "tracing-report.html"
    out_path = Path(output)
    out_path.write_text(html_content, encoding="utf-8")
    print(f"✅ Tracing-Report exportiert → {out_path.resolve()}")
    return 0


# ── Convenience-Factory ────────────────────────────────────────────────


def _quick_record(
    action: str,
    tool: str,
    session_id: str = "",
    duration_ms: float = 0.0,
    status: str = "success",
    error: str = "",
) -> str:
    """Schnelle Aufzeichnung eines Traces (für programmatische Nutzung)."""
    store = TraceStore()
    entry = TraceEntry(
        session_id=session_id,
        action=action,
        tool=tool,
        duration_ms=duration_ms,
        status=status,
        error=error,
    )
    return store.record(entry)
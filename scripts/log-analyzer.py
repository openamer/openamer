#!/usr/bin/env python3
"""
Log Analyzer — Error-Rate-Tracking + Pattern-Erkennung + Alert-Generation
               + Trend-Analyse + HTML-Dashboard

Scannt:  cron/output/*.log|*.md, logs/*.log, .security-cve/*.log,
         .self-healer/memory.json
CLI:     --scan (einmalig), --watch (Daemon 60s), --report (JSON),
         --dashboard (HTML-Datei)
State:   .log-analyzer/state.json (letzter Scan, bekannte Patterns)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import html
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── Konfiguration ──────────────────────────────────────────────────────────

OPENAMER_HOME = Path(os.environ.get(
    "OPENAMER_HOME",
    Path.home() / "AppData" / "Local" / "openamer-laptop"
))
USER_HOME = Path.home()  # C:\\Users\\damir

LOG_ANALYZER_DIR = USER_HOME / ".log-analyzer"
STATE_FILE = LOG_ANALYZER_DIR / "state.json"

# Scan-Pfade
SCAN_PATHS: list[tuple[str, str | list[str]]] = [
    # (Beschreibung, Glob-Liste)
    ("Cron-Output",  str(OPENAMER_HOME / "cron" / "output" / "**" / "*.md")),
    ("Cron-Output",  str(OPENAMER_HOME / "cron" / "output" / "**" / "*.log")),
    ("Logs",         str(OPENAMER_HOME / "logs" / "*.log")),
    ("Security-CVE", str(USER_HOME / ".security-cve" / "*.log")),
    ("Self-Healer",  str(USER_HOME / ".self-healer" / "memory.json")),
]

ALERT_ERROR_RATE_PER_MIN = 5  # Alarm bei > 5 ERROR/Minute
WATCH_INTERVAL = 60           # Sekunden zwischen Scans im Watch-Modus

# ── Log-Parser ─────────────────────────────────────────────────────────────

# Typische Log-Zeilen: 2026-08-18 10:40:53,834 ERROR ...
#                      2026-08-18 10:40:53,834 WARNING ...
#                      2026-08-21T19:45:16.583161+00:00 ...
LOG_LINE_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}"
    r"(?:[,\.]\d{3,6})?(?:[+-]\d{2}:\d{2})?)\s+"
    r"(?P<level>DEBUG|INFO|WARNING|ERROR|CRITICAL|TRACE)"
    r"(?:\s+(?P<context>\S+?))?"
    r"(?:\s*[:]\s*(?P<msg>.*))?\s*$",
    re.IGNORECASE,
)

# Pattern für python Tracebacks
TRACEBACK_RE = re.compile(r"Traceback \(most recent call last\)")

# Pattern für self-healer memory.json pattern_keys
MEMORY_PATTERN_RE = re.compile(
    r'"pattern"\s*:\s*"(?P<name>[^"]+)"\s*'
)


def parse_log_text(text: str, source: str) -> list[dict]:
    """Extrahiere alle Log-Einträge aus einem Text."""
    entries: list[dict] = []
    in_traceback = False
    tb_lines: list[str] = []
    last_entry: dict | None = None

    for line in text.splitlines():
        m = LOG_LINE_RE.match(line)
        if m:
            # Vorherigen Traceback anhängen falls vorhanden
            if tb_lines and last_entry:
                last_entry["traceback"] = "\n".join(tb_lines)
                tb_lines = []

            entry = {
                "timestamp": m.group("ts"),
                "level": m.group("level").upper(),
                "context": m.group("context") or "",
                "message": (m.group("msg") or "").strip(),
                "raw": line,
                "source": source,
                "traceback": None,
            }
            entries.append(entry)
            in_traceback = False
            last_entry = entry

            if TRACEBACK_RE.search(line):
                in_traceback = True
        elif in_traceback:
            tb_lines.append(line)
        else:
            # Kein Log-Format – nach ERROR/CRITICAL im Text fahnden
            for keyword in ("ERROR", "CRITICAL", "FAILED", "FAIL", "FATAL"):
                if keyword in line.upper():
                    entries.append({
                        "timestamp": datetime.now().isoformat(),
                        "level": "ERROR",
                        "context": "raw",
                        "message": line.strip()[:200],
                        "raw": line,
                        "source": source,
                        "traceback": None,
                    })
                    break

    # Letzten Traceback anhängen
    if tb_lines and last_entry:
        last_entry["traceback"] = "\n".join(tb_lines)

    return entries


def parse_memory_json(path: Path) -> list[dict]:
    """Parse .self-healer/memory.json in Log-Einträge."""
    entries: list[dict] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return entries

    patterns = data.get("patterns_seen", {})
    learned = data.get("patterns_learned", [])

    now = datetime.now(timezone.utc).isoformat()
    for name, count in patterns.items():
        entries.append({
            "timestamp": now,
            "level": "WARNING" if count > 3 else "INFO",
            "context": "self-healer.pattern",
            "message": f"Pattern '{name}' count={count}",
            "raw": f"[self-healer] pattern={name} count={count}",
            "source": str(path),
            "traceback": None,
        })

    for p in learned:
        sev = p.get("severity", 0)
        level = "ERROR" if sev >= 5 else "WARNING" if sev >= 3 else "INFO"
        entries.append({
            "timestamp": p.get("last_seen", now),
            "level": level,
            "context": "self-healer.learned",
            "message": f"Pattern '{p['pattern']}' count={p['count']} sev={sev}",
            "raw": json.dumps(p),
            "source": str(path),
            "traceback": None,
        })

    return entries


# ── Scanner ────────────────────────────────────────────────────────────────

def collect_logs() -> list[dict]:
    """Sammle und parse alle Logs aus den Scan-Pfaden."""
    all_entries: list[dict] = []

    for label, glob_path in SCAN_PATHS:
        p = Path(glob_path)
        if label == "Self-Healer" and p.name == "memory.json":
            if p.exists():
                all_entries.extend(parse_memory_json(p))
            continue

        # Glob mit absolutem Pfad: glob auf dem Parent
        parent = p.parent
        pattern = p.name
        if "**" in str(p):
            # ** muss im Pattern sein, also splitten
            parts = str(p).split("**")
            parent = Path(parts[0])
            pattern = "**/" + parts[1].lstrip("/\\")

        for fpath in sorted(parent.glob(pattern)):
            if not fpath.is_file():
                continue
            try:
                text = fpath.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            all_entries.extend(parse_log_text(text, str(fpath)))

    return all_entries


# ── Analyse ────────────────────────────────────────────────────────────────

def analyze(entries: list[dict], state: dict) -> dict:
    """Führe vollständige Analyse durch."""
    result: dict = {
        "scan_time": datetime.now(timezone.utc).isoformat(),
        "total_entries": len(entries),
        "by_level": {},
        "errors": [],
        "error_rate": {},
        "top_errors": [],
        "trends": {},
        "patterns": {},
        "alerts": [],
        "files_scanned": [],
        "summary": {},
    }

    # Quellen sammeln
    sources = set()
    for e in entries:
        sources.add(e.get("source", "unknown"))
    result["files_scanned"] = sorted(sources)

    # Nach Level
    level_counts: Counter = Counter()
    errors: list[dict] = []
    for e in entries:
        level_counts[e["level"]] += 1
        if e["level"] in ("ERROR", "CRITICAL"):
            errors.append(e)
    result["by_level"] = dict(level_counts)

    # Error-Rate (Fehler pro Minute über die letzten 60 Minuten)
    error_rate = compute_error_rate(errors)
    result["error_rate"] = error_rate

    # Top 10 Fehler
    error_msgs: Counter = Counter()
    for e in errors:
        msg = (e.get("message") or "").strip()
        if not msg:
            msg = "(empty error)"
        error_msgs[msg[:120]] += 1
    result["top_errors"] = [
        {"message": msg, "count": cnt}
        for msg, cnt in error_msgs.most_common(10)
    ]

    # Trend-Analyse
    result["trends"] = compute_trends(errors, state)

    # Pattern-Erkennung (Clustering ähnlicher Fehler)
    result["patterns"] = detect_patterns(errors, state)

    # Alert-Generierung
    result["alerts"] = generate_alerts(error_rate, result["patterns"], state)

    # Summary
    error_count = level_counts.get("ERROR", 0) + level_counts.get("CRITICAL", 0)
    warn_count = level_counts.get("WARNING", 0)
    result["summary"] = {
        "total": len(entries),
        "errors": error_count,
        "warnings": warn_count,
        "info": level_counts.get("INFO", 0),
        "error_rate_per_min": round(error_rate.get("current_rate", 0), 2),
        "trend_direction": result["trends"].get("direction", "stable"),
        "alert_count": len(result["alerts"]),
        "unique_patterns": len(result["patterns"]),
    }

    return result


def compute_error_rate(errors: list[dict]) -> dict:
    """Berechne Error-Rate pro Minute (letzte 60 Min)."""
    now = datetime.now(timezone.utc)
    # Timestamps normalisieren
    timestamps: list[datetime] = []
    for e in errors:
        ts = parse_ts(e.get("timestamp", ""))
        if ts:
            timestamps.append(ts)

    if not timestamps:
        return {"current_rate": 0, "total_errors": 0, "buckets": {}}

    # Minute-Buckets (letzte 60 Minuten)
    now_naive = now.replace(tzinfo=None)
    buckets: dict[str, int] = {}
    for ts in timestamps:
        ts_naive = ts.replace(tzinfo=None) if ts.tzinfo else ts
        minute_key = ts_naive.strftime("%Y-%m-%dT%H:%M")
        if ts_naive >= now_naive - timedelta(minutes=60):
            buckets[minute_key] = buckets.get(minute_key, 0) + 1

    # Aktuelle Rate (letzte 5 Minuten / 5)
    recent = sum(
        c for k, c in buckets.items()
        if datetime.strptime(k, "%Y-%m-%dT%H:%M") >= now_naive - timedelta(minutes=5)
    ) if buckets else 0

    return {
        "current_rate": round(recent / 5, 2) if recent else 0,
        "total_errors": len(errors),
        "buckets": dict(sorted(buckets.items())),
    }


def compute_trends(errors: list[dict], state: dict) -> dict:
    """Trend-Analyse: vergleiche letzte 30 Min mit vorherigen 30 Min."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    recent: int = 0
    previous: int = 0

    for e in errors:
        ts = parse_ts(e.get("timestamp", ""))
        if not ts:
            continue
        ts_naive = ts.replace(tzinfo=None) if ts.tzinfo else ts
        if ts_naive >= now - timedelta(minutes=30):
            recent += 1
        elif ts_naive >= now - timedelta(minutes=60):
            previous += 1

    direction = "stable"
    if previous > 0:
        change = (recent - previous) / previous * 100
        if change > 20:
            direction = "rising"
        elif change < -20:
            direction = "falling"
    elif recent > 0:
        direction = "rising"

    return {
        "direction": direction,
        "last_30min": recent,
        "prior_30min": previous,
        "change_pct": round(
            ((recent - previous) / previous * 100) if previous > 0
            else (100 if recent > 0 else 0), 1
        ),
    }


def detect_patterns(errors: list[dict], state: dict) -> dict:
    """Erkenne wiederkehrende Fehler-Patterns durch Message-Clustering."""
    known = state.get("known_patterns", {})
    new_patterns: dict = {}
    seen: dict[str, list[dict]] = defaultdict(list)

    for e in errors:
        msg = e.get("message", "")
        # Pattern extrahieren: erstes Wort oder Nennform
        key = extract_pattern_key(msg)
        if key:
            seen[key].append(e)

    for key, group in seen.items():
        count = len(group)
        first_seen = group[0].get("timestamp", "")
        last_seen = group[-1].get("timestamp", "")
        is_new = key not in known

        new_patterns[key] = {
            "count": count,
            "first_seen": first_seen,
            "last_seen": last_seen,
            "new": is_new,
            "examples": [
                {"msg": e.get("message", "")[:150], "ts": e.get("timestamp", "")}
                for e in group[:3]
            ],
        }

    return new_patterns


def extract_pattern_key(msg: str) -> str | None:
    """Extrahiere Pattern-Key aus Fehlermeldung."""
    if not msg or not msg.strip():
        return None
    # Python Exceptions
    m = re.search(
        r"(\w+(?:Error|Exception|Warning|Fault|Fail|Timeout|Denied|NotFound"
        r"|Conflict|Invalid|Unavailable))",
        msg,
    )
    if m:
        return m.group(1)
    # HTTP Status
    m = re.search(r"(\d{3}\s+\w+)", msg)
    if m:
        return f"HTTP_{m.group(1).split()[0]}"
    # Falls lang: erstes signifikantes Wort + nächste 3
    words = re.findall(r"[A-Z]\w*", msg)
    if words:
        return "_".join(words[:3])[:60]
    # Letzter Fallback: erstes Wort
    first = msg.split()[0] if msg.split() else msg
    return first[:40]


def generate_alerts(error_rate: dict, patterns: dict, state: dict) -> list[dict]:
    """Generiere Alerts basierend auf Error-Rate und neuen Patterns."""
    alerts: list[dict] = []
    known = state.get("known_patterns", {})

    # Alarm bei Error-Rate > Schwellwert
    rate = error_rate.get("current_rate", 0)
    if rate > ALERT_ERROR_RATE_PER_MIN:
        alerts.append({
            "type": "ALARM",
            "severity": "high",
            "message": (
                f"Error-Rate {rate:.1f}/min überschreitet "
                f"Schwellwert von {ALERT_ERROR_RATE_PER_MIN}/min"
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    # Info bei neuen Patterns
    for key, p in patterns.items():
        if p.get("new"):
            alerts.append({
                "type": "INFO",
                "severity": "medium",
                "message": (
                    f"Neues Fehler-Pattern entdeckt: '{key}' "
                    f"({p['count']}×)"
                ),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

    # Trend-Warnung
    if not alerts:
        alerts.append({
            "type": "OK",
            "severity": "low",
            "message": "Keine Auffälligkeiten — System gesund.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    return alerts


def parse_ts(ts_str: str) -> datetime | None:
    """Versuche, einen Timestamp-String zu parsen."""
    if not ts_str:
        return None
    try:
        # ISO-Format mit Zeitzone
        if "T" in ts_str:
            return datetime.fromisoformat(ts_str)
        # Log-Format: 2026-08-18 10:40:53,834
        cleaned = ts_str.replace(",", ".")
        return datetime.strptime(cleaned[:19], "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=timezone.utc
        )
    except (ValueError, TypeError):
        try:
            # Nur Datum
            return datetime.strptime(ts_str[:10], "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
        except (ValueError, TypeError):
            return None


# ── State-Management ───────────────────────────────────────────────────────

def load_state() -> dict:
    """Lade gespeicherten State."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "last_scan": None,
        "known_patterns": {},
        "error_history": [],
        "alert_history": [],
        "version": 1,
    }


def save_state(result: dict, state: dict) -> dict:
    """Aktualisiere State mit neuen Erkenntnissen."""
    now = datetime.now(timezone.utc).isoformat()

    # Patterns zusammenführen
    for key, p in result.get("patterns", {}).items():
        if key not in state["known_patterns"]:
            state["known_patterns"][key] = {
                "first_seen": p["first_seen"] or now,
                "total_count": p["count"],
            }
        else:
            state["known_patterns"][key]["total_count"] = (
                state["known_patterns"][key].get("total_count", 0) + p["count"]
            )
        state["known_patterns"][key]["last_seen"] = p["last_seen"] or now

    # Error-History (max 100)
    rate_entry = {
        "timestamp": now,
        "rate": result["error_rate"]["current_rate"],
        "total_errors": result["summary"]["errors"],
    }
    state["error_history"].append(rate_entry)
    if len(state["error_history"]) > 100:
        state["error_history"] = state["error_history"][-100:]

    # Alert-History (max 50)
    for alert in result.get("alerts", []):
        state["alert_history"].append(alert)
    if len(state["alert_history"]) > 50:
        state["alert_history"] = state["alert_history"][-50:]

    state["last_scan"] = now

    LOG_ANALYZER_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps(state, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return state


# ── HTML-Dashboard ─────────────────────────────────────────────────────────

def generate_dashboard(result: dict, state: dict) -> str:
    """Erzeuge ein HTML-Dashboard."""
    s = result["summary"]
    color_bg = "#0d1117"
    color_card = "#161b22"
    color_border = "#30363d"
    color_text = "#c9d1d9"
    color_green = "#3fb950"
    color_yellow = "#d29922"
    color_red = "#f85149"

    # Error-Rate-Chart (Mini Sparkline aus Buckets)
    buckets = result["error_rate"].get("buckets", {})
    max_bucket = max(buckets.values()) if buckets else 1
    sparkline = ""
    if buckets:
        bars = []
        for k in sorted(buckets)[-20:]:
            h = int(buckets[k] / max_bucket * 60)
            bars.append(
                f'<div style="width:12px;height:{max(2,h)}px;'
                f'background:{color_red};border-radius:2px;'
                f'title="{k}: {buckets[k]} errors"></div>'
            )
        sparkline = (
            f'<div style="display:flex;align-items:flex-end;gap:2px;'
            f'margin-top:8px;">{"".join(bars)}</div>'
        )

    # Trend-Farbe
    trend_color = color_green
    trend_icon = "↓"
    if result["trends"]["direction"] == "rising":
        trend_color = color_red
        trend_icon = "↑"
    elif result["trends"]["direction"] == "falling":
        trend_color = color_green
        trend_icon = "↓"

    # Alerts
    alert_rows = ""
    for a in result.get("alerts", []):
        c = color_red if a["type"] == "ALARM" else (
            color_yellow if a["type"] == "INFO" else color_green
        )
        icon = "🔴" if a["type"] == "ALARM" else (
            "🟡" if a["type"] == "INFO" else "🟢"
        )
        alert_rows += (
            f'<tr><td style="color:{c}">{icon} {html.escape(a["type"])}</td>'
            f'<td style="color:{color_text}">{html.escape(a["message"])}</td>'
            f'<td style="color:{color_border}">{a["timestamp"][:19]}</td></tr>'
        )

    # Top Errors
    top_rows = ""
    for i, te in enumerate(result.get("top_errors", []), 1):
        top_rows += (
            f'<tr><td style="color:{color_border}">#{i}</td>'
            f'<td style="color:{color_text}">'
            f'{html.escape(te["message"][:100])}</td>'
            f'<td style="color:{color_red};font-weight:bold;">{te["count"]}×'
            f'</td></tr>'
        )

    # Patterns
    pattern_rows = ""
    for key, p in sorted(
        result.get("patterns", {}).items(),
        key=lambda x: -x[1]["count"],
    )[:15]:
        tag = "🆕" if p["new"] else " "
        label_color = color_yellow if p["new"] else color_text
        pattern_rows += (
            f'<tr>'
            f'<td style="color:{label_color}">{tag} '
            f'{html.escape(key[:50])}</td>'
            f'<td style="color:{color_red};font-weight:bold;">{p["count"]}×'
            f'</td>'
            f'<td style="color:{color_border}">{p["last_seen"][:19]}</td>'
            f'</tr>'
        )

    # Error-History-Tabelle
    error_history_rows = ""
    for eh in state.get("error_history", [])[-20:]:
        rate_val = eh.get("rate", 0)
        rate_color = color_green if rate_val < 1 else (
            color_yellow if rate_val < ALERT_ERROR_RATE_PER_MIN else color_red
        )
        error_history_rows += (
            f'<tr><td style="color:{color_border}">'
            f'{eh["timestamp"][:19]}</td>'
            f'<td style="color:{rate_color};font-weight:bold;">'
            f'{rate_val}/min</td>'
            f'<td style="color:{color_text}">{eh["total_errors"]}</td></tr>'
        )

    html_content = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Log Analyzer Dashboard</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen,
                 Ubuntu, Cantarell, sans-serif;
    background: {color_bg};
    color: {color_text};
    padding: 20px;
  }}
  h1 {{ font-size: 24px; margin-bottom: 4px; }}
  h2 {{ font-size: 18px; margin: 20px 0 10px; color: #8b949e; }}
  .subtitle {{ color: #8b949e; font-size: 13px; margin-bottom: 20px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
           gap: 12px; margin-bottom: 20px; }}
  .card {{
    background: {color_card};
    border: 1px solid {color_border};
    border-radius: 8px;
    padding: 16px;
  }}
  .card .label {{ font-size: 12px; color: #8b949e; text-transform: uppercase;
                  letter-spacing: 0.5px; }}
  .card .value {{ font-size: 28px; font-weight: 700; margin-top: 4px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{ text-align: left; padding: 8px 12px; color: #8b949e;
        border-bottom: 2px solid {color_border}; font-weight: 600; }}
  td {{ padding: 6px 12px; border-bottom: 1px solid {color_border}; }}
  tr:hover td {{ background: rgba(255,255,255,0.03); }}
  .footer {{ margin-top: 30px; padding: 12px; text-align: center;
             color: #484f58; font-size: 11px;
             border-top: 1px solid {color_border}; }}
</style>
</head>
<body>
<h1>📊 Log Analyzer Dashboard</h1>
<p class="subtitle">Letzter Scan: {result["scan_time"][:19]} UTC
&nbsp;·&nbsp; {result["total_entries"]} Einträge
&nbsp;·&nbsp; {len(result["files_scanned"])} Quellen</p>

<div class="grid">
  <div class="card">
    <div class="label">Fehler (ERROR)</div>
    <div class="value" style="color:{color_red}">{s["errors"]}</div>
  </div>
  <div class="card">
    <div class="label">Warnungen</div>
    <div class="value" style="color:{color_yellow}">{s["warnings"]}</div>
  </div>
  <div class="card">
    <div class="label">Error-Rate (aktuell)</div>
    <div class="value" style="color:{color_red if s['error_rate_per_min'] > 0 else color_green}">{s["error_rate_per_min"]}/min</div>
  </div>
  <div class="card">
    <div class="label">Trend ({result["trends"]["last_30min"]} vs {result["trends"]["prior_30min"]})</div>
    <div class="value" style="color:{trend_color}">{trend_icon} {result["trends"]["direction"].upper()}</div>
  </div>
  <div class="card">
    <div class="label">Patterns (einzigartig)</div>
    <div class="value" style="color:{color_text}">{s["unique_patterns"]}</div>
  </div>
  <div class="card">
    <div class="label">Alerts</div>
    <div class="value" style="color:{color_red if s["alert_count"] > 1 else color_green}">{s["alert_count"]}</div>
  </div>
</div>

<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:20px;">
  <div class="card">
    <div class="label">Error-Rate Verlauf (letzte 20 Buckets)</div>
    {sparkline if sparkline else '<p style="color:#484f58;margin-top:8px;">Keine Daten</p>'}
  </div>
  <div class="card">
    <div class="label">Level-Verteilung</div>
    <div style="margin-top:8px;">
      {render_level_bars(result["by_level"], color_green, color_yellow, color_red)}
    </div>
  </div>
</div>

<h2>🔔 Alerts</h2>
<table>
  <tr><th>Typ</th><th>Nachricht</th><th>Zeit</th></tr>
  {alert_rows if alert_rows else '<tr><td colspan="3" style="color:#484f58;text-align:center;">Keine Alerts</td></tr>'}
</table>

<h2>🔝 Top 10 Fehler</h2>
<table>
  <tr><th>#</th><th>Fehler</th><th>Count</th></tr>
  {top_rows if top_rows else '<tr><td colspan="3" style="color:#484f58;text-align:center;">Keine Fehler gefunden</td></tr>'}
</table>

<h2>🧩 Pattern-Erkennung</h2>
<table>
  <tr><th>Pattern</th><th>Count</th><th>Zuletzt</th></tr>
  {pattern_rows if pattern_rows else '<tr><td colspan="3" style="color:#484f58;text-align:center;">Keine Patterns erkannt</td></tr>'}
</table>

<h2>📈 Error-Rate Historie (letzte 20 Scans)</h2>
<table>
  <tr><th>Zeit</th><th>Rate</th><th>Total Errors</th></tr>
  {error_history_rows if error_history_rows else '<tr><td colspan="3" style="color:#484f58;text-align:center;">Noch keine Historie</td></tr>'}
</table>

<h2>📁 Gescannte Quellen</h2>
<p style="font-size:12px;color:#484f58;">
{[html.escape(s) for s in result["files_scanned"][:20]]}
{"..." if len(result["files_scanned"]) > 20 else ""}
</p>

<div class="footer">
Log Analyzer v1 &mdash; OpenAmer Agent &mdash; {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
</div>
</body>
</html>"""
    return html_content


def render_level_bars(by_level: dict, g: str, y: str, r: str) -> str:
    """Erzeuge horizontale Balken für Level-Verteilung."""
    total = sum(by_level.values()) or 1
    parts = [
        ("ERROR", by_level.get("ERROR", 0), r),
        ("WARNING", by_level.get("WARNING", 0), y),
        ("INFO", by_level.get("INFO", 0), g),
        ("DEBUG", by_level.get("DEBUG", 0), "#58a6ff"),
    ]
    bars = []
    for label, cnt, color in parts:
        pct = cnt / total * 100
        if cnt == 0:
            continue
        bars.append(
            f'<div style="margin:4px 0;">'
            f'<span style="font-size:12px;color:#8b949e;">{label}</span>'
            f'<div style="background:{color};height:16px;width:{pct:.1f}%;'
            f'border-radius:4px;margin-top:2px;min-width:4px;" '
            f'title="{cnt} ({pct:.1f}%)"></div>'
            f'<span style="font-size:11px;color:#484f58;float:right;">'
            f'{cnt} ({pct:.1f}%)</span></div>'
        )
    return "".join(bars)


# ── CLI ────────────────────────────────────────────────────────────────────

def cmd_scan() -> None:
    """Einmaliger Scan."""
    print("🔍 Log Analyzer — Scan läuft...")
    state = load_state()
    entries = collect_logs()
    result = analyze(entries, state)
    state = save_state(result, state)

    s = result["summary"]
    print(f"   {s['total']} Einträge, {s['errors']} Errors, "
          f"{s['warnings']} Warnings")
    print(f"   Error-Rate: {s['error_rate_per_min']}/min")
    print(f"   Trend: {s['trend_direction']}")
    print(f"   Alerts: {s['alert_count']}")

    for alert in result["alerts"]:
        print(f"   {'⚠️' if alert['type']=='ALARM' else 'ℹ️'} "
              f"[{alert['type']}] {alert['message']}")

    print(f"   ✅ State gespeichert: {STATE_FILE}")


def cmd_watch() -> None:
    """Daemon-Modus: alle 60s scannen."""
    print(f"👁️  Log Analyzer Watch — Scanne alle {WATCH_INTERVAL}s")
    print(f"   Drücke Ctrl+C zum Beenden\n")
    try:
        while True:
            state = load_state()
            entries = collect_logs()
            result = analyze(entries, state)
            state = save_state(result, state)
            s = result["summary"]
            ts = datetime.now().strftime("%H:%M:%S")
            alert_icon = "🔴" if s["alert_count"] > 1 else "🟢"
            print(
                f"{ts} {alert_icon} "
                f"{s['total']} Einträge | "
                f"Errors: {s['errors']} | "
                f"Rate: {s['error_rate_per_min']}/min | "
                f"Trend: {s['trend_direction']} | "
                f"Alerts: {s['alert_count']}"
            )
            time.sleep(WATCH_INTERVAL)
    except KeyboardInterrupt:
        print("\n   👋 Watch beendet.")


def cmd_report() -> None:
    """JSON-Report ausgeben."""
    state = load_state()
    entries = collect_logs()
    result = analyze(entries, state)
    state = save_state(result, state)
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_dashboard() -> None:
    """HTML-Dashboard erstellen."""
    state = load_state()
    entries = collect_logs()
    result = analyze(entries, state)
    state = save_state(result, state)

    html_content = generate_dashboard(result, state)
    dashboard_path = LOG_ANALYZER_DIR / "dashboard.html"
    dashboard_path.write_text(html_content, encoding="utf-8")
    print(f"📊 Dashboard erstellt: {dashboard_path}")
    print(f"   Dateigröße: {dashboard_path.stat().st_size / 1024:.1f} KB")
    print(f"   Öffne im Browser: file://{dashboard_path.as_posix()}")


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Log Analyzer — Error-Rate, Patterns, Alerts, Dashboard",
    )
    parser.add_argument(
        "--scan", action="store_true", help="Einmaligen Scan durchführen"
    )
    parser.add_argument(
        "--watch", action="store_true",
        help=f"Daemon-Modus (alle {WATCH_INTERVAL}s scannen)"
    )
    parser.add_argument(
        "--report", action="store_true", help="JSON-Report ausgeben"
    )
    parser.add_argument(
        "--dashboard", action="store_true",
        help="HTML-Dashboard erzeugen und speichern"
    )
    parser.add_argument(
        "--interval", type=int, default=None,
        help="Watch-Intervall in Sekunden (default: 60)"
    )

    args = parser.parse_args()

    interval = args.interval if args.interval is not None else 60
    # Watch-Modus mit benutzerdefiniertem Intervall
    if args.watch:
        _watch_with_interval(interval)
    elif args.report:
        cmd_report()
    elif args.dashboard:
        cmd_dashboard()
    else:
        # Default: --scan
        cmd_scan()


def _watch_with_interval(interval: int) -> None:
    """Watch-Daemon mit variablem Intervall."""
    global WATCH_INTERVAL
    WATCH_INTERVAL = interval
    cmd_watch()


if __name__ == "__main__":
    main()
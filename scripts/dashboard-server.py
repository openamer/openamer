#!/usr/bin/env python3
"""
OpenAmer Live Dashboard — Port 8899
======================================
Cron-Status, System-Health, Security-Status, Skill-Graph
Built with Python stdlib only (http.server).
"""
import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from functools import lru_cache
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

# ── Paths ──────────────────────────────────────────────────────────────────
OPENAMER_HOME = Path(os.environ.get(
    "OPENAMER_HOME",
    str(Path.home() / "AppData" / "Local" / "openamer-laptop"),
))
CRON_DIR = OPENAMER_HOME / "cron"
SCRIPTS_DIR = OPENAMER_HOME / "scripts"
SECURITY_DIR = OPENAMER_HOME / ".security-cve"
GRAPH_JSON = OPENAMER_HOME / "skill-graph.json"
JOBS_JSON = CRON_DIR / "jobs.json"
EXECUTIONS_DB = CRON_DIR / "executions.db"
TICKER_HEARTBEAT = CRON_DIR / "ticker_heartbeat"

# ── Cache ──────────────────────────────────────────────────────────────────
_cache = {"ts": 0, "data": {}}
CACHE_TTL = 5  # seconds


def _cached(key, fn, ttl=CACHE_TTL):
    now = time.time()
    if now - _cache["ts"] > ttl or key not in _cache["data"]:
        _cache["data"][key] = fn()
        _cache["ts"] = now
    return _cache["data"][key]


# ── Data Collectors ────────────────────────────────────────────────────────

def collect_cron():
    """Read cron jobs.json + executions.db → structured status."""
    jobs = []
    if JOBS_JSON.exists():
        try:
            with open(JOBS_JSON) as f:
                data = json.load(f)
            for j in data.get("jobs", []):
                jobs.append({
                    "id": j.get("id", "")[:12],
                    "name": j.get("name", "?"),
                    "state": j.get("state", "?"),
                    "enabled": j.get("enabled", False),
                    "schedule": j.get("schedule_display", "?"),
                    "last_run": j.get("last_run_at", "—"),
                    "last_status": j.get("last_status", "—"),
                    "last_error": j.get("last_error"),
                    "next_run": j.get("next_run_at", "—"),
                    "completed": (j.get("repeat") or {}).get("completed", 0),
                })
        except Exception as e:
            jobs.append({"error": str(e)})

    # Latest executions from DB
    executions = []
    if EXECUTIONS_DB.exists():
        try:
            conn = sqlite3.connect(str(EXECUTIONS_DB), timeout=3)
            cur = conn.cursor()
            rows = cur.execute(
                "SELECT job_id, status, started_at, finished_at "
                "FROM executions ORDER BY started_at DESC LIMIT 20"
            ).fetchall()
            for r in rows:
                dur = 0
                if r[3] and r[2]:
                    try:
                        from datetime import datetime
                        s = datetime.fromisoformat(r[2])
                        f = datetime.fromisoformat(r[3])
                        dur = int((f - s).total_seconds() * 1000)
                    except: pass
                executions.append({
                    "job_id": (r[0] or "?")[:12],
                    "status": r[1] or "?",
                    "started": r[2] or "—",
                    "finished": r[3] or "—",
                    "duration_ms": dur,
                })
            conn.close()
        except Exception as e:
            executions.append({"error": str(e)})

    # Ticker heartbeat
    heartbeat = None
    if TICKER_HEARTBEAT.exists():
        try:
            heartbeat = TICKER_HEARTBEAT.read_text().strip()
        except Exception:
            pass

    return {"jobs": jobs, "executions": executions,
            "ticker_heartbeat": heartbeat,
            "total_jobs": len(jobs),
            "enabled_jobs": sum(1 for j in jobs if j.get("enabled")),
            "ok_jobs": sum(1 for j in jobs if j.get("last_status") == "ok"),
            "failed_jobs": sum(1 for j in jobs if j.get("last_status") == "error"),
        }


def collect_health():
    """Run perf-optimizer.py and parse phases."""
    result = {"ram": {}, "disk": {}, "cpu": {}, "cron_timing": {},
              "summary": {}, "status": "unknown", "error": None}
    perf = SCRIPTS_DIR / "perf-optimizer.py"
    if not perf.exists():
        result["error"] = "perf-optimizer.py not found"
        return result

    try:
        r = subprocess.run(
            [sys.executable, str(perf)],
            capture_output=True, text=True, timeout=25,
        )
        if r.returncode != 0:
            result["error"] = r.stderr[:500]
            return result

        for block in r.stdout.strip().split("\n\n"):
            block = block.strip()
            if not block:
                continue
            try:
                data = json.loads(block)
            except json.JSONDecodeError:
                continue
            phase = data.get("phase", "")
            if phase == "ram":
                result["ram"] = {
                    "total_mb": data["data"].get("total_mb", 0),
                    "used_mb": data["data"].get("used_mb", 0),
                    "free_mb": data["data"].get("free_mb", 0),
                    "usage_pct": data["data"].get("usage_pct", 0),
                    "top": data["data"].get("top_processes", [])[:5],
                }
            elif phase == "disk":
                result["disk"] = {
                    "drives": data["data"].get("drives", []),
                    "temp_mb": (data["data"].get("temp_analysis", {})
                                .get("_total_mb", 0)),
                }
            elif phase == "cpu":
                result["cpu"] = data.get("data", {})
            elif phase == "cron_timing":
                result["cron_timing"] = {
                    "slow": data["data"].get("slow_jobs", []),
                    "failed": data["data"].get("failed_jobs", []),
                }
            elif phase == "summary":
                result["summary"] = data.get("data", {})
                result["status"] = "ok" if not data.get("data", {})\
                    .get("has_issues") else "warning"
    except subprocess.TimeoutExpired:
        result["error"] = "perf-optimizer timed out"
    except Exception as e:
        result["error"] = str(e)
    return result


def collect_security():
    """Read CVE state from .security-cve/."""
    result = {"state": {}, "report": {}, "status": "unknown"}
    state_file = SECURITY_DIR / "state.json"
    report_file = SECURITY_DIR / "last-report.json"
    if state_file.exists():
        try:
            with open(state_file) as f:
                result["state"] = json.load(f)
        except Exception:
            pass
    if report_file.exists():
        try:
            with open(report_file) as f:
                report = json.load(f)
            result["report"] = {
                "timestamp": report.get("timestamp", "—"),
                "duration": report.get("duration_seconds", 0),
                "packages": report.get("packages_scanned", 0),
                "total_cves": report.get("summary", {}).get("total_cves", 0),
                "new_cves": report.get("summary", {}).get("new_cves", 0),
                "critical": report.get("summary", {}).get("critical", 0),
                "high": report.get("summary", {}).get("high", 0),
                "medium": report.get("summary", {}).get("medium", 0),
                "patches": report.get("summary", {}).get("patches_applied", 0),
                "findings": report.get("findings", [])[:10],
            }
        except Exception:
            pass

    known = result.get("state", {}).get("known_cves", {})
    total_known = sum(len(v) for v in known.values())
    stats = result.get("state", {}).get("stats", {})
    result["overview"] = {
        "known_cves": total_known,
        "affected_packages": len(known),
        "scans": stats.get("scans", 0),
        "patches_applied": stats.get("patches_applied", 0),
        "last_scan": result.get("state", {}).get("last_scan", "—"),
    }
    result["packages"] = known
    result["status"] = "ok"
    return result


def collect_graph():
    """Read skill-graph.json and produce a simplified version for viz."""
    if not GRAPH_JSON.exists():
        # Try to build it
        kg = SCRIPTS_DIR / "skill-knowledge-graph.py"
        if kg.exists():
            try:
                subprocess.run(
                    [sys.executable, str(kg), "--json"],
                    capture_output=True, timeout=60,
                )
            except Exception:
                pass

    if not GRAPH_JSON.exists():
        return {"nodes": [], "edges": [], "error": "No graph data"}

    try:
        with open(GRAPH_JSON) as f:
            graph = json.load(f)
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])

        # Build category counts
        cats = {}
        for n in nodes:
            c = n.get("category", "uncategorized")
            cats[c] = cats.get(c, 0) + 1

        # Edges use skill NAME as source/target, nodes use integer id.
        # Build name → id map for filtering
        name_to_id = {n["name"]: n["id"] for n in nodes}

        # For dashboard: return top-level stats + edges as link data
        # Limit nodes to ~200 for rendering performance
        display_nodes = nodes
        if len(nodes) > 200:
            # Keep the first 200 with highest degree
            degree = {}
            for e in edges:
                s, t = e.get("source"), e.get("target")
                sid = name_to_id.get(s)
                tid = name_to_id.get(t)
                if sid is not None:
                    degree[sid] = degree.get(sid, 0) + 1
                if tid is not None:
                    degree[tid] = degree.get(tid, 0) + 1
            sorted_nodes = sorted(nodes,
                                  key=lambda n: degree.get(n["id"], 0),
                                  reverse=True)
            display_nodes = sorted_nodes[:200]
            display_names = {n["name"] for n in display_nodes}
            display_edges = [e for e in edges
                             if e.get("source") in display_names
                             and e.get("target") in display_names]
        else:
            display_edges = edges

        return {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "display_nodes": len(display_nodes),
            "display_edges": len(display_edges),
            "categories": cats,
            "nodes": display_nodes,
            "edges": display_edges,
        }
    except Exception as e:
        return {"nodes": [], "edges": [], "error": str(e)}


# ── HTML Template ──────────────────────────────────────────────────────────

HTML = r"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OpenAmer Dashboard</title>
<style>
  :root {
    --bg: #0d1117;
    --card: #161b22;
    --border: #30363d;
    --text: #c9d1d9;
    --muted: #8b949e;
    --green: #3fb950;
    --red: #f85149;
    --orange: #d29922;
    --blue: #58a6ff;
    --purple: #bc8cff;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    padding: 20px;
    min-height: 100vh;
  }
  .header {
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 24px; padding-bottom: 16px;
    border-bottom: 1px solid var(--border);
  }
  .header h1 {
    font-size: 24px; font-weight: 600;
    background: linear-gradient(135deg, var(--blue), var(--purple));
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  }
  .header .status-bar {
    display: flex; gap: 16px; font-size: 13px;
  }
  .header .status-bar span {
    display: flex; align-items: center; gap: 6px;
  }
  .dot {
    width: 8px; height: 8px; border-radius: 50%; display: inline-block;
  }
  .dot.green { background: var(--green); }
  .dot.yellow { background: var(--orange); }
  .dot.red { background: var(--red); }
  .dot.gray { background: var(--muted); }
  .grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-bottom: 16px;
  }
  .card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px;
    position: relative;
  }
  .card.full { grid-column: 1 / -1; }
  .card h2 {
    font-size: 14px; font-weight: 600; color: var(--muted);
    text-transform: uppercase; letter-spacing: 0.05em;
    margin-bottom: 12px;
  }
  .stat-row {
    display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 12px;
  }
  .stat {
    flex: 1; min-width: 100px;
  }
  .stat .value {
    font-size: 28px; font-weight: 700; line-height: 1.2;
  }
  .stat .label {
    font-size: 11px; color: var(--muted); text-transform: uppercase;
  }
  table {
    width: 100%; border-collapse: collapse;
    font-size: 13px;
  }
  th {
    text-align: left; color: var(--muted); font-weight: 500;
    padding: 6px 8px; border-bottom: 1px solid var(--border);
    font-size: 11px; text-transform: uppercase;
  }
  td {
    padding: 6px 8px; border-bottom: 1px solid var(--border);
  }
  .badge {
    display: inline-block; padding: 1px 8px; border-radius: 10px;
    font-size: 11px; font-weight: 600;
  }
  .badge.ok { background: #0b2e1a; color: var(--green); }
  .badge.error { background: #3d1114; color: var(--red); }
  .badge.running { background: #0a2d3b; color: var(--blue); }
  .badge.scheduled { background: #1c1c1c; color: var(--muted); }
  .badge.high { background: #3d1114; color: var(--red); }
  .badge.critical { background: #5c0000; color: #ff6b6b; }
  .badge.medium { background: #2d1b00; color: var(--orange); }
  .bar {
    height: 8px; background: #21262d; border-radius: 4px; overflow: hidden;
    margin: 4px 0;
  }
  .bar-fill {
    height: 100%; border-radius: 4px; transition: width 1s ease;
  }
  .bar-fill.green { background: var(--green); }
  .bar-fill.yellow { background: var(--orange); }
  .bar-fill.red { background: var(--red); }
  .bar-fill.blue { background: var(--blue); }
  #graph-canvas {
    width: 100%; height: 400px; background: #0d1117;
    border-radius: 6px;
  }
  .error-box {
    background: #3d1114; border: 1px solid var(--red);
    border-radius: 6px; padding: 12px; color: var(--red);
    font-size: 13px; margin: 8px 0;
  }
  .footer {
    text-align: center; color: var(--muted); font-size: 12px;
    padding: 16px 0;
  }
  .progress-ring { position: relative; display: inline-flex; }
  @media (max-width: 768px) {
    .grid { grid-template-columns: 1fr; }
  }
  .timestamp { font-size: 11px; color: var(--muted); }
  .clickable { cursor: pointer; }
  .clickable:hover { opacity: 0.8; }
</style>
</head>
<body>
<div class="header">
  <h1>🔮 OpenAmer Dashboard</h1>
  <div class="status-bar" id="status-bar">
    <span id="last-updated">Lade…</span>
    <span id="server-status"><span class="dot green"></span> Live</span>
  </div>
</div>

<div class="grid">
  <!-- CRON STATUS -->
  <div class="card">
    <h2>⏰ Cron-Status</h2>
    <div class="stat-row" id="cron-stats">
      <div class="stat"><div class="value" id="cron-total">-</div><div class="label">Jobs</div></div>
      <div class="stat"><div class="value" id="cron-enabled">-</div><div class="label">Aktiv</div></div>
      <div class="stat"><div class="value" id="cron-ok">-</div><div class="label">OK</div></div>
      <div class="stat"><div class="value" id="cron-failed">-</div><div class="label">Fehler</div></div>
    </div>
    <table id="cron-table">
      <thead><tr><th>Job</th><th>Status</th><th>Letzter Run</th><th>Nächster</th></tr></thead>
      <tbody id="cron-body"></tbody>
    </table>
    <div id="cron-heartbeat" class="timestamp" style="margin-top:8px"></div>
  </div>

  <!-- SYSTEM HEALTH -->
  <div class="card">
    <h2>🖥️ System-Health</h2>
    <div id="health-content">
      <div class="stat-row">
        <div class="stat"><div class="value" id="health-ram-pct">-</div><div class="label">RAM</div></div>
        <div class="stat"><div class="value" id="health-disk-pct">-</div><div class="label">Festplatte (C:)</div></div>
        <div class="stat"><div class="value" id="health-temp">-</div><div class="label">Temp</div></div>
      </div>
      <div id="ram-bar-container">
        <div class="bar"><div class="bar-fill green" id="ram-bar" style="width:0%"></div></div>
      </div>
      <div id="disk-bar-container">
        <div class="bar"><div class="bar-fill blue" id="disk-bar" style="width:0%"></div></div>
      </div>
      <table id="process-table" style="margin-top:8px">
        <thead><tr><th>Prozess</th><th>PID</th><th>RAM</th></tr></thead>
        <tbody id="process-body"></tbody>
      </table>
      <div id="health-error" class="error-box" style="display:none"></div>
    </div>
  </div>

  <!-- SECURITY STATUS -->
  <div class="card">
    <h2>🔒 Security-Status</h2>
    <div class="stat-row" id="sec-stats">
      <div class="stat"><div class="value" id="sec-known">-</div><div class="label">Bekannte CVEs</div></div>
      <div class="stat"><div class="value" id="sec-packages">-</div><div class="label">Pakete betroffen</div></div>
      <div class="stat"><div class="value" id="sec-patches">-</div><div class="label">Patches</div></div>
      <div class="stat"><div class="value" id="sec-scans">-</div><div class="label">Scans</div></div>
    </div>
    <div id="sec-last-scan" class="timestamp" style="margin-bottom:8px"></div>
    <table id="cve-table">
      <thead><tr><th>Paket</th><th>CVEs</th><th>Schwere</th></tr></thead>
      <tbody id="cve-body"></tbody>
    </table>
  </div>

  <!-- SKILL GRAPH -->
  <div class="card">
    <h2>🔗 Skill-Graph</h2>
    <div class="stat-row" id="graph-stats">
      <div class="stat"><div class="value" id="graph-nodes">-</div><div class="label">Skills</div></div>
      <div class="stat"><div class="value" id="graph-edges">-</div><div class="label">Verbindungen</div></div>
      <div class="stat"><div class="value" id="graph-cats">-</div><div class="label">Kategorien</div></div>
    </div>
    <canvas id="graph-canvas"></canvas>
    <div id="graph-error" class="error-box" style="display:none"></div>
  </div>
</div>

<div class="card full">
  <h2>📋 Letzte Cron-Ausführungen</h2>
  <table id="exec-table">
    <thead><tr><th>Job-ID</th><th>Status</th><th>Start</th><th>Dauer</th></tr></thead>
    <tbody id="exec-body"></tbody>
  </table>
</div>

<div class="footer">
  OpenAmer Dashboard · <span id="footer-time">–</span> · Auto-Refresh alle 60s
</div>

<script>
// ── State ──────────────────────────────────────────────────────────────
const COLORS = ["#58a6ff","#3fb950","#d29922","#f85149","#bc8cff",
                "#79c0ff","#56d364","#e3b341","#ff7b72","#d2a8ff",
                "#7ee787","#a5d6ff","#ffa657","#ffc107","#c9d1d9"];

// ── Fetch ──────────────────────────────────────────────────────────────
async function fetchJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

function ago(ts) {
  if (!ts || ts === "—") return "—";
  const d = new Date(ts);
  if (isNaN(d.getTime())) return ts;
  const sec = Math.floor((Date.now() - d.getTime()) / 1000);
  if (sec < 60) return "gerade eben";
  if (sec < 3600) return `${Math.floor(sec/60)}m`;
  if (sec < 86400) return `${Math.floor(sec/3600)}h`;
  return `${Math.floor(sec/86400)}d`;
}

function fmtDate(ts) {
  if (!ts || ts === "—") return "—";
  const d = new Date(ts);
  if (isNaN(d.getTime())) return ts;
  return d.toLocaleString("de-DE");
}

// ── Cron Panel ─────────────────────────────────────────────────────────
function renderCron(data) {
  document.getElementById("cron-total").textContent = data.total_jobs ?? "?";
  document.getElementById("cron-enabled").textContent = data.enabled_jobs ?? "?";
  document.getElementById("cron-ok").textContent = data.ok_jobs ?? "?";
  document.getElementById("cron-failed").textContent = data.failed_jobs ?? "?";
  const tbody = document.getElementById("cron-body");
  if (!data.jobs || data.jobs.length === 0) {
    tbody.innerHTML = "<tr><td colspan='4' style='color:var(--muted)'>Keine Jobs</td></tr>";
    return;
  }
  tbody.innerHTML = data.jobs.map(j => {
    const st = j.last_status || "?";
    const cls = st === "ok" ? "ok" : st === "error" ? "error" : "scheduled";
    return `<tr>
      <td><strong>${j.name}</strong><br><span class="timestamp">${j.schedule}</span></td>
      <td><span class="badge ${cls}">${st}</span></td>
      <td class="timestamp">${ago(j.last_run)}</td>
      <td class="timestamp">${ago(j.next_run)}</td>
    </tr>`;
  }).join("");
  const hb = document.getElementById("cron-heartbeat");
  if (data.ticker_heartbeat) {
    hb.textContent = "❤️ Ticker: " + ago(data.ticker_heartbeat);
  } else {
    hb.textContent = "";
  }
}

// ── Health Panel ───────────────────────────────────────────────────────
function renderHealth(data) {
  const err = document.getElementById("health-error");
  if (data.error) {
    err.textContent = "❌ " + data.error;
    err.style.display = "block";
    return;
  }
  err.style.display = "none";

  // RAM
  const ram = data.ram || {};
  const ramPct = ram.usage_pct || 0;
  const ramLabel = document.getElementById("health-ram-pct");
  if (ramPct > 0) {
    ramLabel.textContent = ramPct + "%";
  } else {
    // Fallback: show total top process memory
    const top = ram.top || [];
    const totalTop = top.reduce((s, p) => s + (p.mem_mb || 0), 0);
    ramLabel.textContent = totalTop > 0 ? Math.round(totalTop) + " MB" : "?";
  }
  const ramBar = document.getElementById("ram-bar");
  const barPct = ramPct > 0 ? ramPct : 50;
  ramBar.style.width = Math.min(barPct, 100) + "%";
  ramBar.className = "bar-fill " + (barPct > 85 ? "red" : barPct > 70 ? "yellow" : "green");

  // Disk
  const disk = data.disk || {};
  const drives = disk.drives || [];
  if (drives.length > 0) {
    const d = drives[0];
    document.getElementById("health-disk-pct").textContent = d.used_pct + "%";
    const diskBar = document.getElementById("disk-bar");
    diskBar.style.width = Math.min(d.used_pct, 100) + "%";
    diskBar.className = "bar-fill " + (d.used_pct > 90 ? "red" : d.used_pct > 75 ? "yellow" : "blue");
  }
  document.getElementById("health-temp").textContent = disk.temp_mb ? Math.round(disk.temp_mb) + " MB" : "?";

  // Top processes
  const procBody = document.getElementById("process-body");
  const top = ram.top || [];
  if (top.length === 0) {
    procBody.innerHTML = "<tr><td colspan='3' style='color:var(--muted)'>Keine Daten</td></tr>";
  } else {
    procBody.innerHTML = top.map(p => `<tr>
      <td>${p.name}</td>
      <td>${p.pid}</td>
      <td>${p.mem_mb ? p.mem_mb.toFixed(1) + " MB" : "?"}</td>
    </tr>`).join("");
  }
}

// ── Security Panel ─────────────────────────────────────────────────────
function renderSecurity(data) {
  const overview = data.overview || {};
  document.getElementById("sec-known").textContent = overview.known_cves ?? "?";
  document.getElementById("sec-packages").textContent = overview.affected_packages ?? "?";
  document.getElementById("sec-patches").textContent = overview.patches_applied ?? "?";
  document.getElementById("sec-scans").textContent = overview.scans ?? "?";

  const lbl = document.getElementById("sec-last-scan");
  if (overview.last_scan && overview.last_scan !== "—") {
    lbl.textContent = "Letzter Scan: " + fmtDate(overview.last_scan);
  } else { lbl.textContent = ""; }

  const tbody = document.getElementById("cve-body");
  const pkgs = data.packages || {};
  const entries = Object.entries(pkgs);
  if (entries.length === 0) {
    tbody.innerHTML = "<tr><td colspan='3' style='color:var(--muted)'>Keine CVEs</td></tr>";
    return;
  }
  tbody.innerHTML = entries.map(([pkg, cves]) => {
    const sevMap = {high: 0, critical: 0, medium: 0};
    let worst = "medium";
    (cves || []).forEach(c => {
      const cl = c.toLowerCase();
      if (cl.includes("critical")) { sevMap.critical++; worst = "critical"; }
      else if (cl.includes("high")) { sevMap.high++; worst = "high"; }
      else { sevMap.medium++; }
    });
    // Use GHSA / PYSEC prefix as severity hint
    const highCount = cves.filter(c => c.startsWith("GHSA-") || c.includes("HIGH")).length;
    const severity = highCount > 5 ? "critical" : highCount > 0 ? "high" : "medium";
    return `<tr>
      <td>${pkg}</td>
      <td>${cves.length}</td>
      <td><span class="badge ${severity}">${severity}</span></td>
    </tr>`;
  }).join("");
}

// ── Skill Graph ────────────────────────────────────────────────────────
function renderGraph(data) {
  document.getElementById("graph-nodes").textContent = data.total_nodes ?? "?";
  document.getElementById("graph-edges").textContent = data.total_edges ?? "?";
  const cats = data.categories || {};
  document.getElementById("graph-cats").textContent = Object.keys(cats).length ?? "?";
  document.getElementById("graph-error").style.display = "none";

  const canvas = document.getElementById("graph-canvas");
  const ctx = canvas.getContext("2d");
  const rect = canvas.parentElement.getBoundingClientRect();
  canvas.width = canvas.clientWidth * 2;
  canvas.height = canvas.clientHeight * 2;
  ctx.scale(2, 2);
  const W = canvas.clientWidth, H = canvas.clientHeight;
  ctx.clearRect(0, 0, W, H);

  const nodes = data.nodes || [];
  const edges = data.edges || [];
  if (nodes.length === 0 || edges.length === 0) {
    ctx.fillStyle = "#8b949e";
    ctx.font = "14px sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("Keine Graph-Daten", W/2, H/2);
    return;
  }

  // Simple force layout simulation
  const positions = {};
  const centerX = W / 2, centerY = H / 2;
  const radius = Math.min(W, H) * 0.35;

  // Arrange nodes in a circle by category
  const catKeys = Object.keys(cats);
  const nodeCats = {};
  nodes.forEach(n => {
    const c = n.category || "uncategorized";
    if (!nodeCats[c]) nodeCats[c] = [];
    nodeCats[c].push(n);
  });

  let angle = 0;
  const angleStep = (2 * Math.PI) / Math.max(nodes.length, 1);
  const catColors = {};
  catKeys.forEach((c, i) => { catColors[c] = COLORS[i % COLORS.length]; });

  nodes.forEach((n, i) => {
    const a = angleStep * i;
    const r = radius * (0.5 + 0.5 * (i % 3) / 3);
    positions[n.name] = {
      x: centerX + r * Math.cos(a),
      y: centerY + r * Math.sin(a),
    };
  });

  // Draw edges
  ctx.strokeStyle = "#30363d";
  ctx.lineWidth = 0.5;
  const maxEdge = Math.min(edges.length, 5000);
  ctx.beginPath();
  for (let i = 0; i < maxEdge; i++) {
    const e = edges[i];
    const s = positions[e.source], t = positions[e.target];
    if (!s || !t) continue;
    ctx.moveTo(s.x, s.y);
    ctx.lineTo(t.x, t.y);
  }
  ctx.stroke();

  // Draw nodes
  const names = Object.keys(positions);
  names.forEach((name) => {
    const p = positions[name];
    const node = nodes.find(n => n.name === name);
    const cat = (node && node.category) || "uncategorized";
    const color = catColors[cat] || "#8b949e";
    ctx.beginPath();
    ctx.arc(p.x, p.y, 3, 0, 2 * Math.PI);
    ctx.fillStyle = color;
    ctx.fill();
  });

  // Category legend
  let ly = 10;
  ctx.font = "10px sans-serif";
  catKeys.slice(0, 10).forEach((c, i) => {
    ctx.fillStyle = catColors[c] || COLORS[i % COLORS.length];
    ctx.fillRect(10, ly, 8, 8);
    ctx.fillStyle = "#8b949e";
    ctx.fillText(c + " (" + cats[c] + ")", 22, ly + 8);
    ly += 14;
  });
}

// ── Executions Table ───────────────────────────────────────────────────
function renderExecutions(data) {
  const tbody = document.getElementById("exec-body");
  const execs = data.executions || [];
  if (execs.length === 0) {
    tbody.innerHTML = "<tr><td colspan='4' style='color:var(--muted)'>Keine Ausführungen</td></tr>";
    return;
  }
  tbody.innerHTML = execs.map(e => {
    const st = e.status || "?";
    const cls = st === "completed" ? "ok" : st === "failed" ? "error" : "running";
    const dur = e.duration_ms ? (e.duration_ms / 1000).toFixed(1) + "s" : "—";
    return `<tr>
      <td><code>${e.job_id}</code></td>
      <td><span class="badge ${cls}">${st}</span></td>
      <td class="timestamp">${ago(e.started)}</td>
      <td>${dur}</td>
    </tr>`;
  }).join("");
}

// ── Refresh ────────────────────────────────────────────────────────────
async function refresh() {
  const ts = Date.now();
  try {
    const data = await fetchJSON("/api/all?" + ts);
    renderCron(data.cron);
    renderHealth(data.health);
    renderSecurity(data.security);
    renderGraph(data.graph);
    renderExecutions(data.cron);
    document.getElementById("last-updated").textContent = "Letztes Update: " + new Date().toLocaleTimeString("de-DE");
    document.getElementById("footer-time").textContent = new Date().toLocaleString("de-DE");
  } catch (e) {
    document.getElementById("last-updated").textContent = "❌ Fehler: " + e.message;
  }
  setTimeout(refresh, 60000);
}

refresh();
</script>
</body>
</html>"""


# ── HTTP Handler ──────────────────────────────────────────────────────────

class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/dashboard":
            self._serve_html()
        elif path == "/api/all":
            self._serve_json(self._collect_all())
        elif path == "/api/cron":
            self._serve_json(_cached("cron", collect_cron))
        elif path == "/api/health":
            self._serve_json(_cached("health", collect_health, ttl=10))
        elif path == "/api/security":
            self._serve_json(_cached("security", collect_security))
        elif path == "/api/graph":
            self._serve_json(_cached("graph", collect_graph, ttl=30))
        else:
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"404 Not Found")

    def _collect_all(self):
        return {
            "cron": _cached("cron", collect_cron),
            "health": _cached("health", collect_health, ttl=10),
            "security": _cached("security", collect_security),
            "graph": _cached("graph", collect_graph, ttl=30),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _serve_html(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(HTML.encode("utf-8"))

    def _serve_json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode("utf-8"))

    def log_message(self, fmt, *args):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]} {args[1]} {args[2]}")


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    port = 8899
    server = HTTPServer(("127.0.0.1", port), DashboardHandler)
    print(f"🚀 OpenAmer Dashboard → http://127.0.0.1:{port}")
    print(f"📂 OpenAmer Home: {OPENAMER_HOME}")
    print(f"⏱  Cache TTL: {CACHE_TTL}s / Health: 10s / Graph: 30s")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Dashboard gestoppt.")


if __name__ == "__main__":
    main()
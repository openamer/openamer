#!/usr/bin/env python3
"""
remote-web.py — Remote Web Platform für OpenAmer
=================================================
Full Web UI from any device:
  Port 8901, stdlib only (http.server, json, threading, subprocess)

Endpoints:
  GET  /             → HTML-Dashboard (Chat + Status + Skills + Logs)
  GET  /api/status   → JSON System Snapshot
  GET  /api/skills   → JSON Alle Skills
  POST /api/chat     → JSON {prompt, response, duration}
  GET  /health       → 200 OK

Auth: Token aus .remote-web/auth.txt (SHA256)
Cron: Eigenen Health-Check alle 5min schreiben
"""
import hashlib
import hmac
import json
import os
import re
import sqlite3
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# ── Konfiguration ──────────────────────────────────────────────────────────
OPENAMER_HOME = Path(os.environ.get(
    "OPENAMER_HOME",
    str(Path.home() / "AppData" / "Local" / "openamer-laptop"),
))
REPO_DIR = Path(os.environ.get("OPENAMER_REPO", str(Path.home() / "openamer-repo")))
REMOTE_WEB_DIR = OPENAMER_HOME / ".remote-web"
AUTH_FILE = REMOTE_WEB_DIR / "auth.txt"
HEALTH_FILE = REMOTE_WEB_DIR / "health.json"
PORT = 8901
SNAPSHOT_TTL = 60  # seconds between snapshot refreshes

# ── Auth ───────────────────────────────────────────────────────────────────
def load_auth_token():
    """Load auth token from .remote-web/auth.txt, create default if missing."""
    REMOTE_WEB_DIR.mkdir(parents=True, exist_ok=True)
    if not AUTH_FILE.exists():
        default_token = "openamer-remote-secret"
        AUTH_FILE.write_text(default_token)
        return default_token
    return AUTH_FILE.read_text().strip()


AUTH_TOKEN = load_auth_token()


def check_auth(headers):
    """Check Authorization header against stored SHA256 token."""
    auth = headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return False
    token = auth[7:]
    expected_hash = hashlib.sha256(AUTH_TOKEN.encode()).hexdigest()
    provided_hash = hashlib.sha256(token.encode()).hexdigest()
    return hmac.compare_digest(expected_hash, provided_hash)


# ── Snapshot (Background-Thread) ──────────────────────────────────────────
_snapshot_cache = {"ts": 0, "data": {}}
_snapshot_lock = threading.Lock()


def run_cmd(cmd, timeout=10):
    """Run shell command, return (stdout, stderr, exit_code)."""
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            shell=True,
        )
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except subprocess.TimeoutExpired:
        return "", "timeout", -1
    except FileNotFoundError:
        return "", "not found", -1
    except Exception:
        return "", "error", -1


def get_size_str(path_obj):
    try:
        sz = path_obj.stat().st_size
        for unit in ("B", "KB", "MB", "GB"):
            if sz < 1024:
                return f"{sz:.1f}{unit}"
            sz /= 1024
        return f"{sz:.1f}TB"
    except (OSError, ValueError):
        return "0B"


def collect_skills_json():
    """Collect all skills from home and repo."""
    skills = {}
    # Home skills
    home_skills_dir = OPENAMER_HOME / "skills"
    if home_skills_dir.exists():
        for f in sorted(home_skills_dir.iterdir()):
            if f.is_dir():
                md = f / "SKILL.md"
                cat = "home"
                size = "?"
                if md.exists():
                    size = get_size_str(md)
                skills[f.name] = {"name": f.name, "category": cat, "size": size, "location": "home"}
            elif f.suffix == ".md":
                skills[f.stem] = {"name": f.stem, "category": "home", "size": get_size_str(f), "location": "home"}
    # Repo skills
    repo_skills_dir = REPO_DIR / "skills"
    if repo_skills_dir.exists():
        for f in sorted(repo_skills_dir.iterdir()):
            if f.is_dir():
                md = f / "SKILL.md"
                cat = "repo"
                size = "?"
                if md.exists():
                    size = get_size_str(md)
                if f.name not in skills:
                    skills[f.name] = {"name": f.name, "category": cat, "size": size, "location": "repo"}
    return skills


def collect_cron_status():
    """Read cron jobs.json + executions.db."""
    cron_dir = OPENAMER_HOME / "cron"
    jobs_json = cron_dir / "jobs.json"
    exec_db = cron_dir / "executions.db"
    result = {"jobs": [], "executions": [], "ticker_heartbeat": None}

    # Jobs
    if jobs_json.exists():
        try:
            data = json.loads(jobs_json.read_text())
            for j in data.get("jobs", []):
                result["jobs"].append({
                    "id": str(j.get("id", ""))[:12],
                    "name": j.get("name", "?"),
                    "state": j.get("state", "?"),
                    "enabled": j.get("enabled", False),
                    "schedule": j.get("schedule", ""),
                })
        except Exception:
            result["jobs_error"] = traceback.format_exc()

    # Executions
    if exec_db.exists():
        try:
            conn = sqlite3.connect(str(exec_db))
            c = conn.cursor()
            c.execute("SELECT job_id, started_at, finished_at, exit_code FROM executions ORDER BY started_at DESC LIMIT 10")
            rows = c.fetchall()
            for r in rows:
                result["executions"].append({
                    "job_id": str(r[0])[:12] if r[0] else "?",
                    "started": r[1] or "",
                    "finished": r[2] or "",
                    "exit_code": r[3],
                })
            conn.close()
        except Exception:
            pass

    # Ticker heartbeat
    hb = cron_dir / "ticker_heartbeat"
    if hb.exists():
        try:
            result["ticker_heartbeat"] = hb.read_text().strip()
        except Exception:
            pass

    return result


def collect_system_snapshot():
    """Build full system snapshot dict."""
    now = datetime.now(timezone.utc)
    snapshot = {
        "timestamp": now.isoformat(),
        "os": {},
        "python": {},
        "openamer": {},
        "cron": collect_cron_status(),
        "health": {},
        "skills_count": 0,
        "disk": {},
    }

    # OS info
    try:
        out, _, _ = run_cmd("uname -a", 5)
        snapshot["os"]["uname"] = out or "Windows"
        out, _, _ = run_cmd("wmic os get Caption,Version /format:csv 2>/dev/null || ver", 5)
        snapshot["os"]["version"] = out[:200] if out else "Windows 10"
    except Exception:
        snapshot["os"]["version"] = "Windows"

    # Python info
    snapshot["python"]["version"] = sys.version.split()[0]
    snapshot["python"]["executable"] = sys.executable

    # OpenAmer info
    try:
        out, _, _ = run_cmd("openamer version", 10)
        snapshot["openamer"]["version"] = out[:200] if out else "?"
    except Exception:
        snapshot["openamer"]["version"] = "?"

    # Health (RAM, CPU, Disk)
    try:
        import psutil
        mem = psutil.virtual_memory()
        snapshot["health"]["ram_total_gb"] = round(mem.total / (1024**3), 1)
        snapshot["health"]["ram_used_gb"] = round(mem.used / (1024**3), 1)
        snapshot["health"]["ram_percent"] = mem.percent
        cpu = psutil.cpu_percent(interval=0.5)
        snapshot["health"]["cpu_percent"] = cpu
        disk = psutil.disk_usage(OPENAMER_HOME.drive + "/" if OPENAMER_HOME.drive else "/")
        snapshot["disk"]["total_gb"] = round(disk.total / (1024**3), 1)
        snapshot["disk"]["free_gb"] = round(disk.free / (1024**3), 1)
        snapshot["disk"]["used_percent"] = disk.percent
    except ImportError:
        # Fallback: shell commands
        try:
            out, _, _ = run_cmd("wmic OS get TotalVisibleMemorySize,FreePhysicalMemory /format:csv 2>/dev/null", 5)
            m = re.findall(r'\d+', out)
            if len(m) >= 2:
                total_kb, free_kb = int(m[-2]), int(m[-1])
                snapshot["health"]["ram_total_gb"] = round(total_kb / (1024*1024), 1)
                snapshot["health"]["ram_used_gb"] = round((total_kb - free_kb) / (1024*1024), 1)
                snapshot["health"]["ram_percent"] = round(100 - (free_kb / total_kb * 100), 1)
        except Exception:
            snapshot["health"]["ram_total_gb"] = "?"
            snapshot["health"]["ram_percent"] = "?"
        try:
            import shutil
            usage = shutil.disk_usage(OPENAMER_HOME.drive + "/" if OPENAMER_HOME.drive else "/")
            snapshot["disk"]["total_gb"] = round(usage.total / (1024**3), 1)
            snapshot["disk"]["free_gb"] = round(usage.free / (1024**3), 1)
            snapshot["disk"]["used_percent"] = round((1 - usage.free / usage.total) * 100, 1)
        except Exception:
            snapshot["disk"]["total_gb"] = "?"

    # Skills count
    skills = collect_skills_json()
    snapshot["skills_count"] = len(skills)
    snapshot["skills_categories"] = {}
    for sk in skills.values():
        cat = sk.get("category", "other")
        snapshot["skills_categories"][cat] = snapshot["skills_categories"].get(cat, 0) + 1

    # Scripts count
    scripts_dir = OPENAMER_HOME / "scripts"
    snapshot["scripts_count"] = len([f for f in scripts_dir.iterdir() if f.is_file() and f.suffix == ".py"]) if scripts_dir.exists() else 0

    # Git info
    try:
        out, _, _ = run_cmd("git log --oneline -1", 5)
        snapshot["openamer"]["git_commit"] = out[:80] if out else ""
    except Exception:
        snapshot["openamer"]["git_commit"] = ""

    # Uptime
    snapshot["server_uptime_seconds"] = round(time.time() - _server_start_time) if _server_start_time else 0

    return snapshot


def snapshot_worker():
    """Background thread: refresh snapshot every SNAPSHOT_TTL seconds."""
    while True:
        try:
            data = collect_system_snapshot()
            with _snapshot_lock:
                _snapshot_cache["ts"] = time.time()
                _snapshot_cache["data"] = data
            # Write health file for external cron check
            health_data = {
                "status": "ok",
                "ts": datetime.now(timezone.utc).isoformat(),
                "uptime_seconds": data.get("server_uptime_seconds", 0),
            }
            try:
                REMOTE_WEB_DIR.mkdir(parents=True, exist_ok=True)
                (REMOTE_WEB_DIR / "health.json").write_text(json.dumps(health_data, indent=2))
            except Exception:
                pass
        except Exception as exc:
            print(f"[remote-web] snapshot error: {exc}", file=sys.stderr)
        time.sleep(SNAPSHOT_TTL)


_server_start_time = 0


# ── Chat via subprocess ────────────────────────────────────────────────────
def run_chat(prompt_text, timeout=120):
    """Run openamer chat -q with prompt, return (response, duration_s)."""
    t0 = time.time()
    try:
        r = subprocess.run(
            ["openamer", "chat", "-q", prompt_text],
            capture_output=True, text=True, timeout=timeout,
        )
        duration = round(time.time() - t0, 2)
        response = r.stdout.strip()
        if not response:
            response = r.stderr.strip() or "(no output)"
        return response, duration
    except subprocess.TimeoutExpired:
        return "(timeout)", round(time.time() - t0, 2)
    except FileNotFoundError:
        return "(openamer binary not found)", round(time.time() - t0, 2)
    except Exception as exc:
        return f"(error: {exc})", round(time.time() - t0, 2)


# ── Logs ───────────────────────────────────────────────────────────────────
def get_recent_logs(lines=100):
    """Read last N lines from agent log file."""
    log_file = None
    for name in ("agent.log", "openamer.log", "openamer-agent.log"):
        candidate = OPENAMER_HOME / "logs" / name
        if candidate.exists():
            log_file = candidate
            break
    if log_file is None:
        for name in ("agent.log", "openamer.log", "openamer-agent.log"):
            candidate = REPO_DIR / "logs" / name
            if candidate.exists():
                log_file = candidate
                break
    if log_file is None:
        return ["(no log file found - logs may use different filename)"]
    try:
        text = log_file.read_text(encoding="utf-8", errors="replace")
        parts = text.strip().split("\n")
        return parts[-lines:]
    except Exception as exc:
        return [f"(error reading log: {exc})"]


# ── HTML Dashboard ─────────────────────────────────────────────────────────
HTML_DASHBOARD = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>OpenAmer Remote Web</title>
<style>
  :root{--bg:#0d1117;--card:#161b22;--border:#30363d;--text:#c9d1d9;--accent:#58a6ff;--green:#3fb950;--red:#f85149;--yellow:#d29922}
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Oxygen,Ubuntu,sans-serif;background:var(--bg);color:var(--text);min-height:100vh}
  .header{background:var(--card);border-bottom:1px solid var(--border);padding:16px 24px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px}
  .header h1{font-size:20px;font-weight:600;color:#fff;display:flex;align-items:center;gap:8px}
  .header h1 span{color:var(--accent)}
  .header .status-badge{padding:4px 12px;border-radius:12px;font-size:12px;font-weight:500}
  .badge-ok{background:rgba(63,185,80,.15);color:var(--green);border:1px solid var(--green)}
  .badge-err{background:rgba(248,81,73,.15);color:var(--red);border:1px solid var(--red)}
  .container{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:16px;max-width:1400px;margin:0 auto}
  @media(max-width:900px){.container{grid-template-columns:1fr}}
  .card{background:var(--card);border:1px solid var(--border);border-radius:8px;overflow:hidden}
  .card-header{padding:12px 16px;border-bottom:1px solid var(--border);font-size:13px;font-weight:600;text-transform:uppercase;letter-spacing:.5px;color:#8b949e}
  .card-body{padding:16px}
  .full{grid-column:1/-1}
  .flex{display:flex;gap:8px;flex-wrap:wrap}
  .stat{flex:1;min-width:100px;padding:12px;background:rgba(255,255,255,.03);border-radius:6px;text-align:center}
  .stat-value{font-size:24px;font-weight:700;color:#fff}
  .stat-label{font-size:11px;color:#8b949e;margin-top:4px}
  table{width:100%;border-collapse:collapse;font-size:13px}
  th,td{padding:8px 12px;text-align:left;border-bottom:1px solid var(--border)}
  th{color:#8b949e;font-weight:500;font-size:11px;text-transform:uppercase}
  td{font-family:'SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace;font-size:12px}
  .chat-area{display:flex;flex-direction:column;gap:8px}
  .chat-area textarea{width:100%;min-height:80px;background:#0d1117;border:1px solid var(--border);border-radius:6px;color:var(--text);padding:12px;font-size:13px;font-family:inherit;resize:vertical}
  .chat-area textarea:focus{outline:none;border-color:var(--accent)}
  .chat-area button{padding:10px 24px;background:var(--accent);color:#fff;border:none;border-radius:6px;font-size:14px;font-weight:500;cursor:pointer;transition:opacity .2s}
  .chat-area button:hover{opacity:.85}
  .chat-area button:disabled{opacity:.4;cursor:not-allowed}
  .chat-response{background:#0d1117;border:1px solid var(--border);border-radius:6px;padding:12px;min-height:60px;font-size:13px;line-height:1.5;white-space:pre-wrap;word-break:break-word;max-height:400px;overflow-y:auto}
  .chat-meta{font-size:11px;color:#8b949e;margin-top:4px}
  .log-viewer{max-height:300px;overflow-y:auto;font-family:'SFMono-Regular',Consolas,monospace;font-size:11px;line-height:1.6;background:#0d1117;border:1px solid var(--border);border-radius:4px;padding:8px}
  .log-viewer .line{white-space:pre-wrap;word-break:break-all}
  .skill-list{max-height:400px;overflow-y:auto;font-size:12px}
  .skill-item{padding:6px 0;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center}
  .skill-item:last-child{border-bottom:none}
  .skill-name{color:var(--accent)}
  .skill-cat{font-size:10px;background:rgba(88,166,255,.1);color:var(--accent);padding:2px 8px;border-radius:10px}
  .loading{text-align:center;padding:20px;color:#8b949e}
  .error-msg{color:var(--red);font-size:12px;padding:8px;background:rgba(248,81,73,.1);border-radius:4px;margin:4px 0}
  pre.json{background:#0d1117;padding:12px;border-radius:6px;font-size:11px;overflow-x:auto;max-height:300px}
  .nav-bar{display:flex;gap:6px;flex-wrap:wrap}
  .nav-btn{background:rgba(255,255,255,.05);color:var(--text);border:1px solid var(--border);padding:6px 14px;border-radius:6px;cursor:pointer;font-size:12px;transition:all .15s}
  .nav-btn:hover{background:rgba(255,255,255,.1);border-color:var(--accent)}
  .nav-btn.active{background:var(--accent);border-color:var(--accent);color:#fff}
  .tab-content{display:none}
  .tab-content.active{display:block}
</style>
</head>
<body>
<div class="header">
  <h1>&#9670; <span>OpenAmer</span> Remote Web</h1>
  <div class="flex">
    <div class="status-badge badge-ok" id="healthBadge">&#9679; Online</div>
    <div class="nav-bar">
      <button class="nav-btn active" onclick="switchTab('dashboard')">Dashboard</button>
      <button class="nav-btn" onclick="switchTab('chat')">Chat</button>
      <button class="nav-btn" onclick="switchTab('logs')">Logs</button>
    </div>
  </div>
</div>

<div class="container">
  <!-- TAB: Dashboard -->
  <div id="tab-dashboard" class="tab-content active">
    <div class="card full">
      <div class="card-header">System Status</div>
      <div class="card-body">
        <div class="flex" id="statsContainer">
          <div class="stat"><div class="stat-value" id="statRam">-</div><div class="stat-label">RAM</div></div>
          <div class="stat"><div class="stat-value" id="statDisk">-</div><div class="stat-label">Disk Free</div></div>
          <div class="stat"><div class="stat-value" id="statSkills">-</div><div class="stat-label">Skills</div></div>
          <div class="stat"><div class="stat-value" id="statScripts">-</div><div class="stat-label">Scripts</div></div>
          <div class="stat"><div class="stat-value" id="statUptime">-</div><div class="stat-label">Uptime</div></div>
          <div class="stat"><div class="stat-value" id="statPython">-</div><div class="stat-label">Python</div></div>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-header">Cron Jobs</div>
      <div class="card-body">
        <div id="cronContainer"><div class="loading">Lade...</div></div>
      </div>
    </div>

    <div class="card">
      <div class="card-header">Skills Browser</div>
      <div class="card-body">
        <div id="skillSearch">
          <input type="text" placeholder="Skills durchsuchen..." oninput="filterSkills(this.value)"
            style="width:100%;padding:8px 12px;background:#0d1117;border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:13px;margin-bottom:8px">
        </div>
        <div class="skill-list" id="skillList"><div class="loading">Lade Skills...</div></div>
      </div>
    </div>

    <div class="card">
      <div class="card-header">JSON Snapshot</div>
      <div class="card-body">
        <pre class="json" id="jsonSnapshot">Lade...</pre>
      </div>
    </div>
  </div>

  <!-- TAB: Chat -->
  <div id="tab-chat" class="tab-content">
    <div class="card full">
      <div class="card-header">OpenAmer Chat</div>
      <div class="card-body">
        <div class="chat-area">
          <textarea id="chatInput" placeholder="Nachricht an OpenAmer eingeben..." onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendChat()}"></textarea>
          <button id="chatBtn" onclick="sendChat()">Senden</button>
          <div class="chat-response" id="chatResponse">Antwort erscheint hier...</div>
          <div class="chat-meta" id="chatMeta"></div>
        </div>
      </div>
    </div>
  </div>

  <!-- TAB: Logs -->
  <div id="tab-logs" class="tab-content">
    <div class="card full">
      <div class="card-header">Log Viewer (letzte 100 Zeilen)</div>
      <div class="card-body">
        <div class="log-viewer" id="logViewer"><div class="loading">Lade Logs...</div></div>
      </div>
    </div>
  </div>
</div>

<script>
const API_BASE = '';

function switchTab(name) {
  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  document.querySelectorAll('.nav-btn').forEach(b => {
    if(b.textContent.toLowerCase().includes(name)) b.classList.add('active');
  });
}

async function api(method, path, body) {
  const opt = { method, headers: {} };
  const token = localStorage.getItem('authToken');
  if (token) opt.headers['Authorization'] = 'Bearer ' + token;
  if (body) { opt.headers['Content-Type'] = 'application/json'; opt.body = JSON.stringify(body); }
  const r = await fetch(API_BASE + path, opt);
  if (r.status === 401) {
    const t = prompt('Auth-Token erforderlich:');
    if (t) { localStorage.setItem('authToken', t); return api(method, path, body); }
    throw new Error('Unauthorized');
  }
  return r.json();
}

async function loadStatus() {
  try {
    const data = await api('GET', '/api/status');
    const h = data.health || {};
    const d = data.disk || {};
    document.getElementById('statRam').textContent = h.ram_percent != null ? h.ram_percent + '%' : '-';
    document.getElementById('statDisk').textContent = d.free_gb != null ? d.free_gb + 'GB' : '-';
    document.getElementById('statSkills').textContent = data.skills_count ?? '-';
    document.getElementById('statScripts').textContent = data.scripts_count ?? '-';
    const upt = data.server_uptime_seconds;
    if (upt != null) {
      const hh = Math.floor(upt / 3600), mm = Math.floor((upt % 3600) / 60);
      document.getElementById('statUptime').textContent = hh + 'h ' + mm + 'm';
    }
    document.getElementById('statPython').textContent = (data.python || {}).version || '-';
    document.getElementById('jsonSnapshot').textContent = JSON.stringify(data, null, 2);
    const badge = document.getElementById('healthBadge');
    if (data.health && data.health.ram_percent !== '?' && data.health.ram_percent > 90) {
      badge.textContent = '\\u26a0 Kritisch';
      badge.className = 'status-badge badge-err';
    } else {
      badge.textContent = '\\u25cf Online';
      badge.className = 'status-badge badge-ok';
    }
    // Cron
    const cronHtml = (data.cron && data.cron.jobs && data.cron.jobs.length > 0)
      ? '<table><tr><th>Name</th><th>Schedule</th><th>State</th><th>Enabled</th></tr>' +
        data.cron.jobs.map(j => '<tr><td>' + (j.name||'') + '</td><td>' + (j.schedule||'') + '</td><td>' + (j.state||'') + '</td><td>' + (j.enabled ? '\\u2705' : '\\u274c') + '</td></tr>').join('') +
        '</table>' +
        (data.cron.executions && data.cron.executions.length > 0
          ? '<div style="margin-top:8px;font-size:11px;color:#8b949e">Letzte Ausf&uuml;hrungen:</div><table><tr><th>Job</th><th>Started</th><th>Exit</th></tr>' +
            data.cron.executions.slice(0,5).map(e => '<tr><td>' + (e.job_id||'') + '</td><td>' + (e.started||'') + '</td><td>' + (e.exit_code != null ? e.exit_code : '-') + '</td></tr>').join('') +
            '</table>'
          : '<div style="margin-top:8px;color:#8b949e;font-size:12px">Keine Ausf&uuml;hrungen</div>')
      : '<div style="color:#8b949e;font-size:13px">Keine Cron-Jobs gefunden</div>';
    document.getElementById('cronContainer').innerHTML = cronHtml;
  } catch(e) {
    document.getElementById('statsContainer').innerHTML = '<div class="error-msg">Fehler: ' + e.message + '</div>';
  }
}

async function loadSkills() {
  try {
    const data = await api('GET', '/api/skills');
    const skills = data.skills || data;
    const list = document.getElementById('skillList');
    if (Array.isArray(skills)) {
      list.innerHTML = skills.map(s =>
        '<div class="skill-item"><span class="skill-name">' + (s.name||'') + '</span><span class="skill-cat">' + (s.category||'') + '</span></div>'
      ).join('');
    } else if (typeof skills === 'object') {
      list.innerHTML = Object.values(skills).map(s =>
        '<div class="skill-item"><span class="skill-name">' + (s.name||'') + '</span><span class="skill-cat">' + (s.category||'') + '</span></div>'
      ).join('');
    }
    window._allSkills = skills;
  } catch(e) {
    document.getElementById('skillList').innerHTML = '<div class="error-msg">Fehler: ' + e.message + '</div>';
  }
}

function filterSkills(q) {
  const list = document.getElementById('skillList');
  const skills = window._allSkills || [];
  const items = Array.isArray(skills) ? skills : Object.values(skills);
  const filtered = q ? items.filter(s => (s.name||'').toLowerCase().includes(q.toLowerCase())) : items;
  list.innerHTML = filtered.map(s =>
    '<div class="skill-item"><span class="skill-name">' + (s.name||'') + '</span><span class="skill-cat">' + (s.category||'') + '</span></div>'
  ).join('') || '<div class="error-msg">Keine Skills gefunden</div>';
}

async function loadLogs() {
  try {
    const data = await api('GET', '/api/logs');
    const lines = data.lines || [];
    document.getElementById('logViewer').innerHTML = lines.map(l =>
      '<div class="line">' + l.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;') + '</div>'
    ).join('');
  } catch(e) {
    document.getElementById('logViewer').innerHTML = '<div class="error-msg">Fehler: ' + e.message + '</div>';
  }
}

async function sendChat() {
  const input = document.getElementById('chatInput');
  const btn = document.getElementById('chatBtn');
  const response = document.getElementById('chatResponse');
  const meta = document.getElementById('chatMeta');
  const prompt = input.value.trim();
  if (!prompt) return;
  btn.disabled = true;
  btn.textContent = 'Sende...';
  response.textContent = 'Warte auf Antwort...';
  meta.textContent = '';
  try {
    const data = await api('POST', '/api/chat', { prompt });
    response.textContent = data.response || '(keine Antwort)';
    meta.textContent = 'Dauer: ' + (data.duration || '?') + 's';
  } catch(e) {
    response.textContent = 'Fehler: ' + e.message;
  }
  btn.disabled = false;
  btn.textContent = 'Senden';
}

// Initial load
loadStatus();
loadSkills();
loadLogs();
// Auto-refresh status every 30s
setInterval(loadStatus, 30000);
setInterval(loadLogs, 60000);
</script>
</body>
</html>"""


# ── HTTP Handler ───────────────────────────────────────────────────────────
class RemoteWebHandler(BaseHTTPRequestHandler):
    """HTTP request handler for Remote Web Platform."""

    def log_message(self, format, *args):
        """Suppress default log, use our own format."""
        print(f"[remote-web] {datetime.now():%H:%M:%S} {args[0]} {args[1]} {args[2]}", file=sys.stderr)

    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, default=str).encode("utf-8"))

    def _send_html(self, html, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def _send_plain(self, text, status=200, content_type="text/plain"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(text.encode("utf-8"))

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length > 0:
            return self.rfile.read(length).decode("utf-8")
        return ""

    def _require_auth(self):
        """Check auth; return True if allowed, else send 401 and return False."""
        if not check_auth(self.headers):
            self._send_json({"error": "Unauthorized", "message": "Bearer-Token erforderlich"}, 401)
            return False
        return True

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = self._parse_path(self.path)
        path = parsed["path"]

        if path == "/" or path == "":
            self._send_html(HTML_DASHBOARD)
        elif path == "/health":
            self._send_plain("OK")
        elif path == "/api/status":
            if not self._require_auth():
                return
            with _snapshot_lock:
                data = _snapshot_cache["data"]
            self._send_json(data)
        elif path == "/api/skills":
            if not self._require_auth():
                return
            skills = collect_skills_json()
            self._send_json(skills)
        elif path == "/api/logs":
            if not self._require_auth():
                return
            lines = get_recent_logs()
            self._send_json({"lines": lines, "count": len(lines)})
        else:
            self._send_json({"error": "Not Found"}, 404)

    def do_POST(self):
        parsed = self._parse_path(self.path)
        path = parsed["path"]

        if path == "/api/chat":
            if not self._require_auth():
                return
            try:
                body = json.loads(self._read_body())
                prompt = body.get("prompt", "").strip()
                if not prompt:
                    self._send_json({"error": "prompt field required"}, 400)
                    return
                response, duration = run_chat(prompt)
                self._send_json({
                    "prompt": prompt,
                    "response": response,
                    "duration": duration,
                })
            except json.JSONDecodeError:
                self._send_json({"error": "Invalid JSON"}, 400)
            except Exception as exc:
                self._send_json({"error": str(exc)}, 500)
        else:
            self._send_json({"error": "Not Found"}, 404)

    @staticmethod
    def _parse_path(url):
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return {"path": parsed.path.rstrip("/") or "/", "query": parsed.query}


# ── Server Start ───────────────────────────────────────────────────────────
def main():
    global _server_start_time

    # Parse CLI args
    port = PORT
    bind = "0.0.0.0"  # Default: all interfaces
    for arg in sys.argv[1:]:
        if arg.startswith("--port="):
            port = int(arg.split("=")[1])
        elif arg == "--local":
            bind = "127.0.0.1"
        elif arg == "--help":
            print("Usage: remote-web.py [--port=8901] [--local]")
            sys.exit(0)

    # Start background snapshot thread
    _server_start_time = time.time()
    t = threading.Thread(target=snapshot_worker, daemon=True)
    t.start()

    # Wait for first snapshot
    time.sleep(2)

    # Print auth info
    print(f"[remote-web] Auth-Token: {AUTH_TOKEN}", file=sys.stderr)
    token_hash = hashlib.sha256(AUTH_TOKEN.encode()).hexdigest()[:16]
    print(f"[remote-web] Token-Hash: {token_hash}...", file=sys.stderr)
    print(f"[remote-web] Auth-Datei: {AUTH_FILE}", file=sys.stderr)

    # Start server
    server = HTTPServer((bind, port), RemoteWebHandler)
    print(f"[remote-web] Server gestartet auf http://{bind}:{port}", file=sys.stderr)
    if bind == "0.0.0.0":
        print(f"[remote-web] Lokal:      http://127.0.0.1:{port}", file=sys.stderr)
        # Try to show LAN IP
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            lan_ip = s.getsockname()[0]
            s.close()
            print(f"[remote-web] Netzwerk:   http://{lan_ip}:{port}", file=sys.stderr)
        except Exception:
            pass
    print(f"[remote-web] Auth:        Authorization: Bearer <token>", file=sys.stderr)
    print(f"[remote-web] Fertig. Drücke Ctrl+C zum Beenden.", file=sys.stderr)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[remote-web] Server gestoppt.", file=sys.stderr)
        server.server_close()


if __name__ == "__main__":
    main()
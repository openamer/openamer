"""Web Observability Portal — live agent activity dashboard, session browser,
trace viewer, and JSON export.

Starts a local web server that provides a visual observability interface
for inspecting agent execution traces, tool calls, and session history.

Usage:
    openamer observe               # Start portal on default port 8081
    openamer observe --port 9090   # Custom port
"""

from __future__ import annotations

import json
import logging
import os
import time
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict, List, Optional

from openamer_cli.observability import (
    AgentTrace,
    TraceEvent,
    build_trace_from_events,
    get_recent_traces,
    get_trace_stats,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# HTML Template — all-in-one observability portal
# ---------------------------------------------------------------------------

_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OpenAmer Observability Portal</title>
<style>
  :root {
    --bg: #0d1117; --card: #161b22; --border: #30363d;
    --text: #c9d1d9; --text-dim: #8b949e;
    --accent: #22D3EE; --accent-dim: #155e6b;
    --green: #3fb950; --red: #f85149; --yellow: #d29922;
    --purple: #bc8cff;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); height: 100vh; overflow: hidden; }

  #app { display: flex; height: 100vh; }
  #sidebar { width: 260px; min-width: 260px; background: var(--card); border-right: 1px solid var(--border); display: flex; flex-direction: column; overflow-y: auto; }
  #main { flex: 1; display: flex; flex-direction: column; overflow: hidden; }

  .brand { padding: 16px; border-bottom: 1px solid var(--border); }
  .brand h1 { font-size: 16px; color: var(--accent); margin: 0; }
  .brand small { font-size: 11px; color: var(--text-dim); }

  .nav-item { padding: 10px 16px; cursor: pointer; font-size: 13px; display: flex; align-items: center; gap: 8px; transition: background 0.15s; border-left: 3px solid transparent; }
  .nav-item:hover { background: rgba(34,211,238,0.05); }
  .nav-item.active { background: rgba(34,211,238,0.1); border-left-color: var(--accent); color: var(--accent); }
  .nav-item .badge { margin-left: auto; background: #21262d; padding: 1px 8px; border-radius: 10px; font-size: 11px; }

  #content { flex: 1; padding: 24px; overflow-y: auto; }

  .card { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 20px; margin-bottom: 16px; }
  .card h2 { font-size: 16px; margin-bottom: 12px; }
  .card h3 { font-size: 14px; margin-bottom: 8px; color: var(--text-dim); }

  .stat-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 12px; margin-bottom: 16px; }
  .stat-card { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 16px; text-align: center; }
  .stat-card .value { font-size: 28px; font-weight: 700; color: var(--accent); }
  .stat-card .label { font-size: 11px; color: var(--text-dim); margin-top: 4px; }

  table { width: 100%; border-collapse: collapse; }
  th, td { text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--border); font-size: 13px; }
  th { color: var(--text-dim); font-weight: 500; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; }
  tr:hover td { background: rgba(34,211,238,0.03); }
  tr.clickable { cursor: pointer; }

  .badge { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; background: #21262d; color: var(--text-dim); }
  .badge-green { background: #0d5320; color: var(--green); }
  .badge-red { background: #3d1111; color: var(--red); }
  .badge-blue { background: #0d1f3d; color: var(--accent); }
  .badge-purple { background: #1f0d3d; color: var(--purple); }
  .badge-yellow { background: #3d3d0d; color: var(--yellow); }

  .search-box { width: 100%; padding: 8px 12px; background: #0d1117; border: 1px solid var(--border); border-radius: 6px; color: var(--text); font-size: 13px; margin-bottom: 12px; }
  .search-box:focus { border-color: var(--accent); outline: none; }

  .tool-call-item { padding: 8px 12px; margin: 4px 0; border-left: 3px solid var(--border); background: #0d1117; border-radius: 0 4px 4px 0; font-size: 12px; }
  .tool-call-item .tc-name { font-weight: 600; color: var(--accent); }
  .tool-call-item .tc-duration { float: right; font-size: 11px; }
  .tool-call-item .tc-args { color: var(--text-dim); font-family: monospace; font-size: 11px; margin-top: 4px; white-space: pre-wrap; word-break: break-all; max-height: 80px; overflow-y: auto; }

  .btn { padding: 6px 14px; border: 1px solid var(--border); border-radius: 6px; background: #21262d; color: var(--text); font-size: 12px; cursor: pointer; transition: all 0.15s; }
  .btn:hover { border-color: var(--accent); background: var(--accent-dim); }
  .btn.primary { background: var(--accent); color: #000; border-color: var(--accent); font-weight: 600; }
  .btn.primary:hover { background: #1ab8d0; }
  .btn.danger { border-color: var(--red); color: var(--red); }
  .btn.danger:hover { background: var(--red); color: #fff; }

  .toast { position: fixed; bottom: 20px; right: 20px; padding: 10px 20px; border-radius: 8px; font-size: 13px; z-index: 2000; animation: fadein 0.3s; }
  .toast.success { background: #0d5320; color: var(--green); border: 1px solid var(--green); }
  .toast.error { background: #3d1111; color: var(--red); border: 1px solid var(--red); }
  @keyframes fadein { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }

  .timeline { position: relative; padding-left: 24px; }
  .timeline::before { content: ''; position: absolute; left: 8px; top: 0; bottom: 0; width: 2px; background: var(--border); }
  .timeline-item { position: relative; padding: 8px 0 8px 16px; }
  .timeline-item::before { content: ''; position: absolute; left: -20px; top: 12px; width: 10px; height: 10px; border-radius: 50%; background: var(--border); }
  .timeline-item.tl-tool_call::before { background: var(--accent); }
  .timeline-item.tl-tool_result::before { background: var(--green); }
  .timeline-item.tl-user_message::before { background: var(--yellow); }
  .timeline-item.tl-assistant_message::before { background: var(--purple); }
  .timeline-item.tl-error::before { background: var(--red); }
  .timeline-item .tl-time { font-size: 11px; color: var(--text-dim); }
  .timeline-item .tl-content { font-size: 13px; margin-top: 2px; }

  .flex { display: flex; gap: 8px; align-items: center; }
  .flex-between { display: flex; justify-content: space-between; align-items: center; }
  .mt-12 { margin-top: 12px; }
  .mb-12 { margin-bottom: 12px; }
  .text-dim { color: var(--text-dim); font-size: 12px; }

  ::-webkit-scrollbar { width: 6px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

  /* Bar chart */
  .bar-chart { display: flex; align-items: flex-end; gap: 4px; height: 100px; padding: 8px 0; }
  .bar { flex: 1; background: var(--accent); border-radius: 2px 2px 0 0; min-height: 4px; transition: height 0.3s; position: relative; }
  .bar:hover { background: var(--accent-dim); }
  .bar .bar-tooltip { display: none; position: absolute; bottom: 100%; left: 50%; transform: translateX(-50%); background: #000; color: #fff; padding: 4px 8px; border-radius: 4px; font-size: 10px; white-space: nowrap; z-index: 100; }
  .bar:hover .bar-tooltip { display: block; }

  .empty-state { text-align: center; padding: 60px 20px; color: var(--text-dim); }
  .empty-state .icon { font-size: 48px; margin-bottom: 12px; }

  .auto-refresh { display: flex; align-items: center; gap: 4px; }
  .auto-refresh input { width: auto; margin: 0; }
</style>
</head>
<body>
<div id="app">
  <div id="sidebar">
    <div class="brand">
      <h1>🔭 Observability</h1>
      <small>Agent activity &amp; traces</small>
    </div>
    <div class="nav-item active" data-page="dashboard" onclick="switchPage('dashboard')">
      📊 Dashboard
    </div>
    <div class="nav-item" data-page="sessions" onclick="switchPage('sessions')">
      📋 Sessions
    </div>
    <div class="nav-item" data-page="traces" onclick="switchPage('traces')">
      🧬 Trace Viewer
    </div>
    <div style="margin-top:auto;padding:12px 16px;border-top:1px solid var(--border)">
      <div class="auto-refresh mb-12">
        <input type="checkbox" id="autoRefresh" onchange="toggleAutoRefresh()">
        <label for="autoRefresh" style="font-size:12px">Auto-refresh (5s)</label>
      </div>
      <button class="btn" style="width:100%" onclick="exportAllTraces()">📦 Export All as JSON</button>
    </div>
  </div>
  <div id="main">
    <div id="content"></div>
  </div>
</div>

<script>
// ── State ──
let currentPage = 'dashboard';
let autoRefreshTimer = null;
let allTraces = [];
let selectedTrace = null;

// ── Init ──
switchPage('dashboard');

// ── Navigation ──
function switchPage(page) {
  currentPage = page;
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.querySelector(`.nav-item[data-page="${page}"]`).classList.add('active');
  if (page === 'dashboard') loadDashboard();
  else if (page === 'sessions') loadSessions();
  else if (page === 'traces') loadTraces();
}

function showLoading() {
  document.getElementById('content').innerHTML = '<div class="empty-state"><div class="icon">⏳</div><p>Loading...</p></div>';
}

// ── Dashboard ──
function loadDashboard() {
  showLoading();
  fetch('/api/observe/stats')
    .then(r => r.json())
    .then(stats => renderDashboard(stats))
    .catch(() => renderDashboard({}));
}

function renderDashboard(stats) {
  const durationMs = (stats.total_duration_ms || 0) / 1000;
  const html = `
    <div class="stat-grid">
      <div class="stat-card"><div class="value">${stats.total_events || 0}</div><div class="label">Total Events</div></div>
      <div class="stat-card"><div class="value">${stats.total_tool_calls || 0}</div><div class="label">Tool Calls</div></div>
      <div class="stat-card"><div class="value">${stats.trace_files || 0}</div><div class="label">Trace Files</div></div>
      <div class="stat-card"><div class="value">${stats.brain_records || 0}</div><div class="label">Brain Records</div></div>
    </div>
    <div class="card">
      <div class="flex-between">
        <h2>📊 Tool Call Timeline</h2>
      </div>
      <div id="graphBars"><div class="empty-state">No tool call data yet</div></div>
    </div>
    <div class="card">
      <div class="flex-between">
        <h2>🔧 Top Tools</h2>
      </div>
      <div id="topTools"></div>
    </div>
    <div class="card">
      <div class="flex-between">
        <h2>📋 Event Distribution</h2>
      </div>
      <div id="eventDist"></div>
    </div>`;
  document.getElementById('content').innerHTML = html;

  // Build tool timeline bars
  const topToolsDiv = document.getElementById('topTools');
  if (stats.top_tools && Object.keys(stats.top_tools).length > 0) {
    const tools = Object.entries(stats.top_tools);
    const maxVal = Math.max(...tools.map(([,c]) => c));
    topToolsDiv.innerHTML = `<div class="bar-chart">${tools.map(([name, count]) =>
      `<div class="bar" style="height:${(count/maxVal)*80 + 20}px"><div class="bar-tooltip">${name}: ${count}x</div></div>`
    ).join('')}</div>`;
    topToolsDiv.innerHTML += '<div class="flex" style="flex-wrap:wrap;gap:4px">' +
      tools.slice(0, 10).map(([name, count]) => `<span class="badge badge-blue">${name}: ${count}</span>`).join('') + '</div>';
  } else {
    topToolsDiv.innerHTML = '<div class="text-dim">No tool calls recorded yet.</div>';
  }

  // Event distribution
  const eventDistDiv = document.getElementById('eventDist');
  if (stats.event_type_distribution && Object.keys(stats.event_type_distribution).length > 0) {
    eventDistDiv.innerHTML = '<div class="flex" style="flex-wrap:wrap;gap:4px">' +
      Object.entries(stats.event_type_distribution).map(([type, count]) =>
        `<span class="badge badge-purple">${type}: ${count}</span>`
      ).join('') + '</div>';
  } else {
    eventDistDiv.innerHTML = '<div class="text-dim">No events recorded yet.</div>';
  }
}

// ── Sessions Browser ──
function loadSessions() {
  showLoading();
  fetch('/api/observe/traces')
    .then(r => r.json())
    .then(data => {
      allTraces = data.traces || [];
      renderSessions();
    })
    .catch(() => renderSessions());
}

function renderSessions(filter) {
  let list = allTraces;
  if (filter) {
    const f = filter.toLowerCase();
    list = list.filter(t => (t.session_id || '').toLowerCase().includes(f) || (t.title || '').toLowerCase().includes(f));
  }

  const html = `
    <div class="card">
      <div class="flex-between">
        <h2>📋 Session Browser</h2>
        <button class="btn btn-sm" onclick="loadSessions()">🔄 Refresh</button>
      </div>
      <input class="search-box" placeholder="Search session ID or title..." oninput="renderSessions(this.value)">
      ${list.length === 0 ? '<div class="empty-state"><p>No sessions found</p></div>' : `
      <table>
        <tr><th>Session ID</th><th>Events</th><th>Tool Calls</th><th>Duration</th><th>Action</th></tr>
        ${list.map(t => `
          <tr class="clickable" onclick="showTrace('${t.session_id}')">
            <td><span class="badge badge-blue">${(t.session_id || '?').substring(0, 24)}</span></td>
            <td>${t.event_count || 0}</td>
            <td>${t.tool_calls || 0}</td>
            <td>${formatDuration(t.total_duration_ms)}</td>
            <td><button class="btn btn-sm" onclick="event.stopPropagation();exportTrace('${t.session_id}')">📦</button></td>
          </tr>
        `).join('')}
      </table>`}
    </div>`;
  document.getElementById('content').innerHTML = html;
}

// ── Trace Viewer ──
function loadTraces() {
  showLoading();
  fetch('/api/observe/traces')
    .then(r => r.json())
    .then(data => {
      allTraces = data.traces || [];
      renderTraceList();
    })
    .catch(() => renderTraceList());
}

function renderTraceList() {
  const html = `
    <div class="card">
      <div class="flex-between">
        <h2>🧬 Trace Viewer</h2>
        <button class="btn btn-sm" onclick="loadTraces()">🔄 Refresh</button>
      </div>
      ${allTraces.length === 0 ? '<div class="empty-state"><p>No traces available</p></div>' : `
      <table>
        <tr><th>Session</th><th>Events</th><th>Tool Calls</th><th>Duration</th></tr>
        ${allTraces.map(t => `
          <tr class="clickable" onclick="showTrace('${t.session_id}')">
            <td><span class="badge badge-blue">${(t.session_id || '?').substring(0, 24)}</span></td>
            <td>${t.event_count || 0}</td>
            <td>${t.tool_calls || 0}</td>
            <td>${formatDuration(t.total_duration_ms)}</td>
          </tr>
        `).join('')}
      </table>`}
    </div>`;
  document.getElementById('content').innerHTML = html;
}

function showTrace(sessionId) {
  showLoading();
  fetch('/api/observe/trace/' + encodeURIComponent(sessionId))
    .then(r => r.json())
    .then(trace => {
      selectedTrace = trace;
      renderTraceDetail(trace);
    })
    .catch(() => {
      document.getElementById('content').innerHTML = '<div class="empty-state"><p>Trace not found</p></div>';
    });
}

function renderTraceDetail(trace) {
  const events = trace.events || [];
  let timelineHtml = events.length === 0 ? '<div class="text-dim">No events</div>' :
    events.map(e => {
      const icon = {user_message:'💬', assistant_message:'🤖', tool_call:'🔧', tool_result:'✅', thinking:'💭', error:'🔥'}[e.event_type] || '•';
      return `<div class="timeline-item tl-${e.event_type}">
        <div class="tl-time">${formatTime(e.timestamp)} ${e.duration_ms ? '(' + formatDuration(e.duration_ms) + ')' : ''}</div>
        <div class="tl-content">${icon} <strong>${e.event_type}</strong>
          ${e.tool_name ? ' — ' + e.tool_name : ''}</div>
        ${e.content ? '<div class="tl-content text-dim" style="font-size:12px">' + escapeHtml(e.content.substring(0, 200)) + '</div>' : ''}
        ${e.tool_name && e.tool_args && Object.keys(e.tool_args).length ? '<div class="tl-content" style="font-size:11px;color:var(--accent)">args: ' + escapeHtml(JSON.stringify(e.tool_args).substring(0, 120)) + '</div>' : ''}
      </div>`;
    }).join('');

  const html = `
    <div class="flex-between mb-12">
      <h2>🧬 Trace: <span class="badge badge-blue">${trace.session_id || '?'}</span></h2>
      <div class="flex">
        <span class="text-dim">${trace.event_count || 0} events | ${trace.tool_calls || 0} tool calls | ${formatDuration(trace.total_duration_ms)}</span>
        <button class="btn btn-sm primary" onclick="exportTrace('${trace.session_id}')">📦 Export JSON</button>
        <button class="btn btn-sm" onclick="loadTraces()">← Back</button>
      </div>
    </div>
    <div class="card">
      <h3>Timeline</h3>
      <div class="timeline">${timelineHtml}</div>
    </div>`;
  document.getElementById('content').innerHTML = html;
}

// ── Export ──
function exportAllTraces() {
  const data = JSON.stringify({ traces: allTraces, exported_at: new Date().toISOString() }, null, 2);
  downloadJSON(data, 'openamer-traces-all.json');
  toast('Traces exported', 'success');
}

function exportTrace(sessionId) {
  fetch('/api/observe/trace/' + encodeURIComponent(sessionId))
    .then(r => r.json())
    .then(trace => {
      const data = JSON.stringify({ trace, exported_at: new Date().toISOString() }, null, 2);
      downloadJSON(data, `trace-${sessionId.substring(0, 20)}.json`);
      toast('Trace exported', 'success');
    })
    .catch(() => toast('Failed to export trace', 'error'));
}

function downloadJSON(data, filename) {
  const blob = new Blob([data], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
}

// ── Auto-refresh ──
function toggleAutoRefresh() {
  if (autoRefreshTimer) { clearInterval(autoRefreshTimer); autoRefreshTimer = null; }
  if (document.getElementById('autoRefresh').checked) {
    autoRefreshTimer = setInterval(() => {
      if (currentPage === 'dashboard') loadDashboard();
      else if (currentPage === 'sessions') loadSessions();
      else if (currentPage === 'traces') loadTraces();
    }, 5000);
  }
}

// ── Helpers ──
function formatDuration(ms) {
  if (!ms) return '-';
  if (ms < 1) return (ms * 1000).toFixed(0) + '\\u00b5s';
  if (ms < 1000) return ms.toFixed(0) + 'ms';
  return (ms / 1000).toFixed(1) + 's';
}

function formatTime(ts) {
  if (!ts) return '?';
  try { return new Date(ts).toLocaleTimeString(); } catch(e) { return ts.substring(0, 19); }
}

function escapeHtml(s) {
  if (!s) return '';
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function toast(msg, type) {
  const el = document.createElement('div');
  el.className = 'toast ' + type;
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3000);
}
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# HTTP Handler
# ---------------------------------------------------------------------------


class _ObserveHandler(BaseHTTPRequestHandler):
    """HTTP handler for the Observability Portal."""

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send_html(200, _HTML)
        elif self.path == "/api/observe/stats":
            try:
                stats = get_trace_stats()
                # Add total duration estimate
                traces = get_recent_traces(limit=50)
                total_ms = sum(t.total_duration_ms for t in traces if t.total_duration_ms)
                stats["total_duration_ms"] = total_ms
                self._send_json(200, stats)
            except Exception as exc:
                self._send_json(500, {"error": str(exc)})
        elif self.path == "/api/observe/traces":
            try:
                traces = get_recent_traces(limit=50)
                self._send_json(200, {
                    "traces": [_trace_to_dict(t) for t in traces],
                })
            except Exception as exc:
                self._send_json(500, {"error": str(exc)})
        elif self.path.startswith("/api/observe/trace/"):
            session_id = self.path.split("/")[-1]
            try:
                from openamer_cli.observability import _brainlog_files, _read_brainlog
                for f in _brainlog_files():
                    if session_id in f.stem:
                        events = _read_brainlog(f, max_lines=200)
                        trace = build_trace_from_events(events, session_id=f.stem)
                        self._send_json(200, _trace_to_dict(trace))
                        return
                self._send_json(404, {"error": f"Trace '{session_id}' not found"})
            except Exception as exc:
                self._send_json(500, {"error": str(exc)})
        else:
            self._send_json(404, {"error": "Not found"})

    def _send_html(self, code: int, html: str):
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def _send_json(self, code: int, data: dict):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def log_message(self, fmt, *args):
        logger.debug(fmt, *args)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _trace_to_dict(trace: AgentTrace) -> dict:
    """Convert an AgentTrace to a JSON-serializable dict."""
    return {
        "session_id": trace.session_id,
        "title": trace.title,
        "started_at": trace.started_at,
        "total_duration_ms": trace.total_duration_ms,
        "event_count": trace.event_count,
        "tool_calls": trace.tool_calls,
        "events": [
            {
                "timestamp": e.timestamp,
                "event_type": e.event_type,
                "content": e.content,
                "tool_name": e.tool_name,
                "tool_args": e.tool_args,
                "duration_ms": e.duration_ms,
                "success": e.success,
            }
            for e in trace.events
        ],
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def cmd_observe(args) -> None:
    """Start the Observability Portal web server."""
    port = getattr(args, "port", 8081)
    server = HTTPServer(("127.0.0.1", port), _ObserveHandler)
    url = f"http://127.0.0.1:{port}"
    print(f"OpenAmer Observability Portal running at: {url}")
    print("Dashboard: agent activity, tool timeline, event stats")
    print("Sessions:  search & browse past sessions")
    print("Traces:    view full execution traces with timeline")
    print("Press Ctrl+C to stop.")

    try:
        webbrowser.open(url)
    except Exception:
        pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        server.server_close()


def build_observe_parser(subparsers) -> None:
    """Add the ``openamer observe`` subcommand."""
    parser = subparsers.add_parser(
        "observe",
        help="Start the Web Observability Portal (agent activity dashboard, session browser, traces)",
        description=(
            "Start a local web server with a visual observability portal. "
            "Provides a dashboard with live agent activity, tool call timeline, "
            "session browser with search, full trace viewer with execution timeline, "
            "and JSON export."
        ),
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8081,
        help="Port to listen on (default: 8081)",
    )
    parser.set_defaults(func=cmd_observe)
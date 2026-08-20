"""Visual Agent Builder Web UI — Browser-based agent creation.

Starts a local web server that provides a visual interface for creating,
editing, and managing agents. Uses the agent_builder module as backend.

Usage:
    openamer agent ui              # Start web UI on default port
    openamer agent ui --port 8080  # Custom port
"""

from __future__ import annotations

import json
import logging
import os
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict, Optional

from openamer_cli.agent_builder import (
    AgentSpec,
    build_agent,
    list_agents,
    delete_agent,
    show_agent,
    create_agent_from_description,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# HTML Template
# ---------------------------------------------------------------------------

_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OpenAmer Agent Builder</title>
<style>
  :root { --bg: #0d1117; --card: #161b22; --border: #30363d; --text: #c9d1d9; --accent: #22D3EE; --green: #3fb950; --red: #f85149; }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); padding: 20px; }
  .container { max-width: 900px; margin: 0 auto; }
  h1 { color: var(--accent); margin-bottom: 20px; }
  h1 small { font-size: 14px; color: #8b949e; font-weight: normal; }
  .card { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 20px; margin-bottom: 20px; }
  .card h2 { margin-bottom: 15px; font-size: 18px; }
  label { display: block; margin-bottom: 5px; color: #8b949e; font-size: 13px; }
  input, textarea, select { width: 100%; padding: 8px 12px; background: #0d1117; border: 1px solid var(--border); border-radius: 6px; color: var(--text); font-size: 14px; margin-bottom: 12px; }
  textarea { min-height: 80px; font-family: monospace; }
  button { padding: 8px 16px; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; font-weight: 500; }
  .btn-primary { background: var(--accent); color: #000; }
  .btn-danger { background: var(--red); color: #fff; }
  .btn-secondary { background: #21262d; color: var(--text); border: 1px solid var(--border); }
  .btn-sm { padding: 4px 10px; font-size: 12px; }
  .flex { display: flex; gap: 10px; align-items: center; }
  .flex-between { display: flex; justify-content: space-between; align-items: center; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 11px; background: #21262d; color: #8b949e; }
  .badge-success { background: #0d5320; color: var(--green); }
  .msg { padding: 10px; border-radius: 6px; margin-bottom: 10px; display: none; }
  .msg-success { background: #0d5320; color: var(--green); display: block; }
  .msg-error { background: #3d1111; color: var(--red); display: block; }
  table { width: 100%; border-collapse: collapse; }
  th, td { text-align: left; padding: 10px; border-bottom: 1px solid var(--border); font-size: 14px; }
  th { color: #8b949e; font-weight: 500; }
  .empty { text-align: center; padding: 40px; color: #8b949e; }
  pre { background: #0d1117; padding: 10px; border-radius: 6px; overflow-x: auto; font-size: 13px; }
</style>
</head>
<body>
<div class="container">
  <h1>🤖 OpenAmer Agent Builder <small>visual agent creation</small></h1>

  <div id="msg" class="msg"></div>

  <div class="card">
    <h2>🧠 Natural Language Agent Creator</h2>
    <p style="color:#8b949e;margin-bottom:12px;font-size:13px">Describe what you want the agent to do in plain English.</p>
    <textarea id="nlDesc" placeholder="e.g. 'Send a daily summary of Hacker News to my Telegram every morning at 9am'"></textarea>
    <button class="btn-primary" onclick="createFromNL()">✨ Create Agent from Description</button>
  </div>

  <div class="card">
    <h2>⚙️ Manual Agent Builder</h2>
    <div class="flex" style="gap:15px;flex-wrap:wrap">
      <div style="flex:2;min-width:200px">
        <label>Agent Name</label>
        <input id="name" placeholder="my-agent">
      </div>
      <div style="flex:1;min-width:150px">
        <label>Schedule (optional)</label>
        <input id="schedule" placeholder="0 9 * * *">
      </div>
      <div style="flex:1;min-width:150px">
        <label>Skills (comma-separated)</label>
        <input id="skills" placeholder="web-research, github">
      </div>
    </div>
    <label>Description & Goal</label>
    <textarea id="desc" placeholder="Describe what this agent should do and its primary goal"></textarea>
    <button class="btn-primary" onclick="buildAgent()">🔨 Build Agent</button>
  </div>

  <div class="card">
    <div class="flex-between">
      <h2>📋 Your Agents</h2>
      <button class="btn-secondary btn-sm" onclick="refreshList()">🔄 Refresh</button>
    </div>
    <div id="agentList"><div class="empty">Loading...</div></div>
  </div>
</div>

<script>
function showMsg(text, type) {
  const m = document.getElementById('msg');
  m.textContent = text; m.className = 'msg msg-' + type;
  setTimeout(() => m.className = 'msg', 5000);
}

function createFromNL() {
  const desc = document.getElementById('nlDesc').value.trim();
  if (!desc) return showMsg('Please enter a description', 'error');
  fetch('/api/agent/create-from-nl', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({description: desc}) })
    .then(r => r.json()).then(d => {
      if (d.ok) { showMsg('Agent created: ' + d.name, 'success'); refreshList(); }
      else showMsg(d.error || 'Failed', 'error');
    }).catch(e => showMsg('Error: ' + e, 'error'));
}

function buildAgent() {
  const name = document.getElementById('name').value.trim();
  const desc = document.getElementById('desc').value.trim();
  const schedule = document.getElementById('schedule').value.trim();
  const skills = document.getElementById('skills').value.trim().split(',').map(s => s.trim()).filter(Boolean);
  if (!name || !desc) return showMsg('Name and description are required', 'error');
  fetch('/api/agent/build', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name, description: desc, goal: desc, cron_schedule: schedule || null, skills}) })
    .then(r => r.json()).then(d => {
      if (d.ok) { showMsg('Agent built: ' + d.name, 'success'); refreshList(); }
      else showMsg(d.error || 'Failed', 'error');
    }).catch(e => showMsg('Error: ' + e, 'error'));
}

function deleteAgent(name) {
  if (!confirm('Delete agent "' + name + '"?')) return;
  fetch('/api/agent/delete', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name}) })
    .then(r => r.json()).then(d => {
      showMsg(d.ok ? 'Deleted: ' + name : 'Failed', d.ok ? 'success' : 'error');
      refreshList();
    }).catch(e => showMsg('Error: ' + e, 'error'));
}

function refreshList() {
  const el = document.getElementById('agentList');
  fetch('/api/agents').then(r => r.json()).then(data => {
    if (!data.agents || data.agents.length === 0) {
      el.innerHTML = '<div class="empty">No agents yet. Create one above!</div>';
      return;
    }
    let html = '<table><tr><th>Name</th><th>Description</th><th>Schedule</th><th>Skills</th><th>Actions</th></tr>';
    data.agents.forEach(a => {
      html += '<tr><td><strong>' + a.name + '</strong></td><td>' + (a.description || '').substring(0, 40) + '</td>'
        + '<td>' + (a.cron_schedule ? '<span class="badge badge-success">' + a.cron_schedule + '</span>' : '<span class="badge">none</span>') + '</td>'
        + '<td>' + (a.skills || []).map(s => '<span class="badge">' + s + '</span>').join(' ') + '</td>'
        + '<td><button class="btn-danger btn-sm" onclick="deleteAgent(\'' + a.name + '\')">Delete</button></td></tr>';
    });
    html += '</table>';
    el.innerHTML = html;
  }).catch(() => el.innerHTML = '<div class="empty">Error loading agents</div>');
}

refreshList();
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# HTTP Handler
# ---------------------------------------------------------------------------


class _AgentUIHandler(BaseHTTPRequestHandler):
    """HTTP handler for the Agent Builder UI."""

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self._send_html(200, _HTML)
        elif self.path == "/api/agents":
            self._send_json(200, {"agents": list_agents()})
        elif self.path.startswith("/api/agent/show/"):
            name = self.path.split("/")[-1]
            agent = show_agent(name)
            if agent:
                self._send_json(200, agent)
            else:
                self._send_json(404, {"error": f"Agent '{name}' not found"})
        else:
            self._send_json(404, {"error": "Not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b"{}"
        data = json.loads(body) if body else {}

        if self.path == "/api/agent/build":
            spec = AgentSpec(
                name=data.get("name", ""),
                description=data.get("description", ""),
                goal=data.get("goal", ""),
                cron_schedule=data.get("cron_schedule"),
                skills=data.get("skills", []),
                tools=data.get("tools", []),
            )
            result = build_agent(spec)
            self._send_json(200 if result.get("ok", True) else 400, result)

        elif self.path == "/api/agent/create-from-nl":
            desc = data.get("description", "")
            if not desc:
                self._send_json(400, {"ok": False, "error": "No description provided"})
                return
            spec = create_agent_from_description(desc)
            result = build_agent(spec)
            self._send_json(200 if result.get("ok", True) else 400, result)

        elif self.path == "/api/agent/delete":
            name = data.get("name", "")
            if not name:
                self._send_json(400, {"ok": False, "error": "No name provided"})
                return
            ok = delete_agent(name)
            self._send_json(200, {"ok": ok, "name": name})

        else:
            self._send_json(404, {"error": "Not found"})

    def _send_html(self, code: int, html: str):
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
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
# CLI entry point
# ---------------------------------------------------------------------------


def cmd_agent_ui(args) -> None:
    """Start the Agent Builder web UI."""
    port = getattr(args, "port", 8080)
    server = HTTPServer(("127.0.0.1", port), _AgentUIHandler)
    url = f"http://127.0.0.1:{port}"
    print(f"OpenAmer Agent Builder UI running at: {url}")
    print("Press Ctrl+C to stop.")

    # Try to open browser
    try:
        webbrowser.open(url)
    except Exception:
        pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        server.server_close()


def build_agent_ui_parser(subparsers) -> None:
    """Add the ``openamer agent ui`` subcommand."""
    # Find the agent subparser
    for name, parser in subparsers.choices.items():
        if name == "agent":
            agent_sub = parser._subparsers._group_actions[0].choices
            ui_p = agent_sub.get("agent_action", parser).add_parser if hasattr(parser, '_subparsers') else None
            break

    # Alternative: add as standalone command
    parser = subparsers.add_parser(
        "agent-ui",
        help="Start the Agent Builder web UI",
        description="Start a local web server with a visual agent builder interface.",
    )
    parser.add_argument("--port", "-p", type=int, default=8080, help="Port to listen on (default: 8080)")
    parser.set_defaults(func=cmd_agent_ui)
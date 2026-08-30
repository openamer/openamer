#!/usr/bin/env python3
"""
Darwin Live Dashboard - HTTP server exposing the ecosystem state.
Endpoints:
  /           -> HTML dashboard (dark, auto-refresh)
  /api/status -> JSON status_overview()
  /api/trend  -> JSON fitness trend
  /api/report -> markdown report
Port: 8910 (configurable via --port)
"""
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import importlib.util
spec = importlib.util.spec_from_file_location(
    "darwin_engine", REPO / "scripts" / "darwin_engine.py")
darwin = importlib.util.module_from_spec(spec)
sys.modules["darwin_engine"] = darwin
spec.loader.exec_module(darwin)

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta http-equiv="refresh" content="30">
<title>Darwin Live</title>
<style>
  body { background:#0d1117; color:#c9d1d9; font-family:'Segoe UI',sans-serif;
         padding:2rem; max-width:760px; margin:auto; }
  h1 { color:#7ee787; }
  .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr));
          gap:1rem; margin:1.5rem 0; }
  .card { background:#161b22; border:1px solid #30363d; border-radius:10px;
          padding:1rem 1.25rem; }
  .k { color:#8b949e; font-size:.8rem; text-transform:uppercase; }
  .v { font-size:1.5rem; font-weight:700; color:#79c0ff; }
  table { width:100%; border-collapse:collapse; }
  td,th { padding:.4rem .6rem; border-bottom:1px solid #30363d; text-align:left; }
  th { color:#8b949e; font-weight:600; }
</style>
</head>
<body>
<h1>&#129516; Darwin Live Dashboard</h1>
<p style="color:#8b949e">Self-evolving skill ecosystem &middot; auto-refresh 30s</p>
<div class="grid" id="cards"></div>
<table id="top"></table>
<script>
fetch('/api/status').then(r=>r.json()).then(s=>{
  const cards = [
    ['Population', s.population],
    ['Trend', s.trend],
    ['Fittest', s.fittest],
    ['Species installed', s.species.installed],
    ['Active trials', s.active_trials],
    ['Harvested ideas', s.harvested_blueprints],
  ];
  document.getElementById('cards').innerHTML = cards.map(c=>
    `<div class="card"><div class="k">${c[0]}</div><div class="v">${c[1]}</div></div>`).join('');
});
fetch('/api/status').then(r=>r.json()).then(()=>{});
fetch('/api/top').then(r=>r.json()).then(rows=>{
  document.getElementById('top').innerHTML =
    '<tr><th>Skill</th><th>Fitness</th><th>Usage</th></tr>' +
    rows.map(r=>`<tr><td>${r[0]}</td><td>${r[1]}</td><td>${r[2]}</td></tr>`).join('');
});
</script>
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def do_GET(self):
        try:
            if self.path == "/":
                self._send(200, HTML, "text/html; charset=utf-8")
            elif self.path == "/api/status":
                s = darwin.status_overview()
                self._send(200, json.dumps(s, indent=1), "application/json")
            elif self.path == "/api/trend":
                self._send(200, json.dumps(darwin.fitness_trend(), indent=1),
                           "application/json")
            elif self.path == "/api/top":
                fitness = darwin._load_json(darwin.FITNESS_FILE, {}).get(
                    "skills", {})
                ranked = sorted(fitness.items(),
                                key=lambda kv: kv[1].get("fitness", 0),
                                reverse=True)[:10]
                rows = [[n, s.get("fitness", 0), s.get("usage", 0)]
                        for n, s in ranked]
                self._send(200, json.dumps(rows), "application/json")
            elif self.path == "/api/report":
                md = darwin.REPORT_FILE.read_text("utf-8") \
                    if darwin.REPORT_FILE.exists() else "# no report yet"
                self._send(200, md, "text/plain; charset=utf-8")
            else:
                self._send(404, "not found", "text/plain")
        except Exception as e:
            self._send(500, f"error: {e}", "text/plain")

    def log_message(self, *a):
        pass  # keep the console quiet


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8910)
    args = ap.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"darwin dashboard on http://127.0.0.1:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()

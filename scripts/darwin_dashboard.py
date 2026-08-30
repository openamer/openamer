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

_spec_sw = importlib.util.spec_from_file_location(
    "swarm_os", REPO / "scripts" / "swarm_os.py")
swarm_os_mod = importlib.util.module_from_spec(_spec_sw)
sys.modules["swarm_os"] = swarm_os_mod
_spec_sw.loader.exec_module(swarm_os_mod)

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


def build_world() -> dict:
    """Ecosystem as 3D world entities: workers, skills, species, memories,
    events, territories. The frontend renders this as a living game world."""
    import math
    fitness = darwin._load_json(darwin.FITNESS_FILE, {}).get("skills", {})
    population = darwin._load_json(darwin.POPULATION_FILE, {})
    lineage = _load_lineage_events()
    sw = swarm_state()

    organisms = []
    # skills as organisms - position on a fitness spiral
    ranked = sorted(fitness.items(), key=lambda kv: kv[1].get("fitness", 0),
                    reverse=True)
    n = max(len(ranked), 1)
    for i, (name, s) in enumerate(ranked):
        angle = (i / n) * math.pi * 2
        radius = 3 + (1 - min(s.get("fitness", 0) / 60.0, 1)) * 12
        organisms.append({
            "id": name,
            "type": "skill",
            "fitness": s.get("fitness", 0),
            "usage": s.get("usage", 0),
            "age_days": s.get("age_days", 0),
            "x": round(math.cos(angle) * radius, 2),
            "z": round(math.sin(angle) * radius, 2),
            "y": round(min(s.get("fitness", 0), 60) / 6, 2),  # height = fitness
        })
    # swarm workers as larger creatures
    for name, w in sw.get("workers", {}).items():
        import hashlib
        h = int(hashlib.md5(name.encode()).hexdigest(), 16)
        organisms.append({
            "id": name, "type": "worker",
            "wins": w.get("wins", 0), "losses": w.get("losses", 0),
            "energy": w.get("energy", 0),
            "generation": w.get("generation", 1),
            "x": round(math.cos(h % 360 / 57.3) * 8, 2),
            "z": round(math.sin(h % 360 / 57.3) * 8, 2),
            "y": 6,
        })
    # species as crystals
    sp_dir = darwin.DARWIN_DIR / "species"
    if sp_dir.exists():
        for j, mp in enumerate(sp_dir.glob("*.json")):
            meta = darwin._load_json(mp, {})
            organisms.append({
                "id": meta.get("child", mp.stem), "type": "species",
                "status": meta.get("status", "candidate"),
                "kind": meta.get("kind", "speciation"),
                "x": round(math.cos(j * 0.7) * 15, 2),
                "z": round(math.sin(j * 0.7) * 15, 2),
                "y": 2,
            })
    # recent events as fading sparks
    events = [{"id": f"ev-{k}", "kind": e.get("kind", "?"),
               "parent": e.get("parent", ""), "child": e.get("child", ""),
               "when": e.get("when", "")}
              for k, e in enumerate(lineage[-12:])]
    # territories as glowing zones
    territories = _load_territories()
    stats = {"population": len(fitness), "workers": len(sw.get("workers", {})),
             "species_count": sum(1 for o in organisms if o["type"] == "species"),
             "events": len(events)}
    return {"organisms": organisms, "events": events,
            "territories": territories, "stats": stats}


def _load_lineage_events():
    try:
        lin = darwin._load_json(darwin.LINEAGE_FILE, {"events": []})
        return lin.get("events", [])
    except Exception:
        return []


def _load_territories():
    try:
        return darwin._load_json(darwin.TERRITORIES_FILE, {})
    except Exception:
        return {}


def swarm_state():
    try:
        return darwin._load_json(swarm_os_mod.SWARM_FILE,
                                 {"workers": {}, "tasks": {}})
    except Exception:
        return {"workers": {}}



class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def do_GET(self):
        try:
            if self.path == "/":
                world_html = (Path(REPO / "scripts" / "darwin_world.html")
                              .read_text("utf-8"))
                self._send(200, world_html, "text/html; charset=utf-8")
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
            elif self.path == "/api/world":
                self._send(200, json.dumps(build_world(), indent=1),
                           "application/json")
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

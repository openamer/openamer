#!/usr/bin/env python3
"""
Darwin Grid Server - the world's first natural-selection package registry.

Machines push their genomes (evolved skills + evidence), pull foreign
genomes, and duel cross-machine: foreign skills compete against local ones
with real exit codes as the only currency.

Endpoints:
  POST /push      body=darwin-genome.json  -> store by machine-id
  GET  /pull      ?machine=<id>            -> that machine's genome
  GET  /pull-all                            -> every stored genome
  GET  /list                                -> machine registry
  GET  /health                              -> liveness

Storage: grid-store/<machine-id>/genome.json (file-based, zero deps)
Port 8920.
"""
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

STORE = Path(__file__).resolve().parent / "grid-store"
STORE.mkdir(exist_ok=True)
LOCK = threading.Lock()


def _safe_id(machine_id: str) -> str | None:
    if not machine_id or not re.fullmatch(r"[a-zA-Z0-9_-]{3,64}", machine_id):
        return None
    return machine_id


def _genome_path(machine_id: str) -> Path:
    d = STORE / machine_id
    d.mkdir(exist_ok=True)
    return d / "genome.json"


def handle_push(machine_id: str, body: dict) -> tuple[int, dict]:
    mid = _safe_id(machine_id)
    if not mid:
        return 400, {"error": "invalid machine id"}
    if not isinstance(body, dict) or "population" not in body:
        return 400, {"error": "genome must contain 'population'"}
    with LOCK:
        body.setdefault("machine_id", mid)
        body.setdefault("pushed_at", "")
        _genome_path(mid).write_text(
            json.dumps(body, indent=1, ensure_ascii=False), "utf-8")
    skills = len(body.get("population", {}))
    return 200, {"ok": True, "machine": mid, "skills": skills}


def handle_pull(machine_id: str) -> tuple[int, dict]:
    mid = _safe_id(machine_id)
    if not mid:
        return 400, {"error": "invalid machine id"}
    p = _genome_path(mid)
    if not p.exists():
        return 404, {"error": "unknown machine"}
    return 200, json.loads(p.read_text(encoding="utf-8"))


def handle_pull_all() -> tuple[int, dict]:
    genomes = {}
    for d in STORE.iterdir():
        if d.is_dir():
            p = d / "genome.json"
            if p.exists():
                genomes[d.name] = json.loads(p.read_text(encoding="utf-8"))
    return 200, {"machines": len(genomes), "genomes": genomes}


def handle_list() -> tuple[int, dict]:
    machines = []
    for d in STORE.iterdir():
        if d.is_dir():
            p = d / "genome.json"
            info = {"machine": d.name}
            if p.exists():
                g = json.loads(p.read_text(encoding="utf-8"))
                info["skills"] = len(g.get("population", {}))
                info["pushed_at"] = g.get("pushed_at", "")
            machines.append(info)
    return 200, {"machines": machines}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def do_GET(self):
        try:
            if self.path == "/health":
                self._send(200, {"ok": True, "grid": True})
            elif self.path == "/list":
                code, obj = handle_list()
                self._send(code, obj)
            elif self.path.startswith("/pull-all"):
                code, obj = handle_pull_all()
                self._send(code, obj)
            elif self.path.startswith("/pull"):
                from urllib.parse import urlparse, parse_qs
                qs = parse_qs(urlparse(self.path).query)
                mid = (qs.get("machine") or [""])[0]
                code, obj = handle_pull(mid)
                self._send(code, obj)
            else:
                self._send(404, {"error": "not found"})
        except Exception as e:
            self._send(500, {"error": str(e)})

    def do_POST(self):
        try:
            if self.path.startswith("/push"):
                from urllib.parse import urlparse, parse_qs
                qs = parse_qs(urlparse(self.path).query)
                mid = (qs.get("machine") or [""])[0]
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length) or b"{}")
                code, obj = handle_push(mid, body)
                self._send(code, obj)
            else:
                self._send(404, {"error": "not found"})
        except Exception as e:
            self._send(500, {"error": str(e)})

    def log_message(self, *a):
        pass


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8920)
    args = ap.parse_args()
    print(f"darwin grid on http://127.0.0.1:{args.port}")
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()

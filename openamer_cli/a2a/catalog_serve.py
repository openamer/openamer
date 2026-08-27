"""openamer_cli/a2a/catalog_serve.py — serve the ARD ai-catalog over HTTP.

A tiny, dependency-free stdlib HTTP server that serves the ARD catalog at the
standard discovery locations:
    GET /ai-catalog.json
    GET /.well-known/ai-catalog.json
    GET /health
so an ARD `navigate <host>` client can autodiscover the OpenAmer agent.

Usage (as the `openamer a2a serve` subcommand):
    openamer a2a serve [--port 8799] [--host 127.0.0.1] [--catalog path]
"""
from __future__ import annotations

import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# The two standard locations ARD navigate checks; both serve the same catalog.
CATALOG_PATHS = {"/ai-catalog.json", "/.well-known/ai-catalog.json"}

_default_catalog = None  # set by serve_cmd before starting


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # quieter
        return

    def _send(self, code, body: bytes, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except BrokenPipeError:
            pass

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/health":
            self._send(200, b'{"status":"ok"}')
            return
        if path in CATALOG_PATHS:
            data = _default_catalog
            if data is None:
                self._send(500, b'{"error":"catalog not loaded"}')
                return
            self._send(200, data)
            return
        self._send(404, b'{"error":"not found"}')


def load_catalog_bytes(catalog_path: str | None) -> bytes:
    if catalog_path:
        p = Path(catalog_path)
    else:
        # default: repo docs/.well-known/ai-catalog.json (or docs/ai-catalog.json)
        from openamer_cli.a2a import ard
        p = Path.cwd() / "docs" / "ai-catalog.json"
        wk = Path.cwd() / "docs" / ".well-known" / "ai-catalog.json"
        p = wk if wk.exists() else p
    if not p.exists():
        raise FileNotFoundError(f"catalog not found: {p}")
    return p.read_bytes()


def serve(host: str, port: int, catalog_path: str | None):
    """Start the catalog HTTP server (blocking until Ctrl-C / KeyboardInterrupt)."""
    global _default_catalog
    _default_catalog = load_catalog_bytes(catalog_path)

    server = ThreadingHTTPServer((host, port), _Handler)
    print(f"[catalog] ARD ai-catalog serving at http://{host}:{port}")
    print(f"[catalog]   {catalog_path or 'repo docs/ai-catalog.json'}")
    print(f"[catalog]   discovery: http://{host}:{port}/.well-known/ai-catalog.json")
    print(f"[catalog]   discover : http://{host}:{port}/ai-catalog.json")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[catalog] stopped")
        return 0
    finally:
        server.server_close()
    return 0


def serve_cmd(args) -> int:
    return serve(getattr(args, "host", "127.0.0.1"),
                 int(getattr(args, "port", 8799)),
                 getattr(args, "catalog", None))


def start_in_background(port: int = 8799, host: str = "127.0.0.1",
                        catalog_path: str | None = None) -> int:
    """Non-blocking helper: spawn thread so callers can immediately hit it."""
    t = threading.Thread(target=serve, args=(host, port, catalog_path),
                         daemon=True)
    t.start()
    return port
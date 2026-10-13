#!/usr/bin/env python3
"""Mini A2A Server — OpenAmer ASI Exposition

Lauscht auf Port 8085. Andere KI-Agenten können mich via A2A-Protokoll anfragen.
Ich exponiere: reasoning, learning, writing, code_analysis
"""

import json
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("a2a-server")

HOME = Path.home() / "AppData/Local/openamer-laptop"
AGENT = HOME / "openamer-agent"
import sys
sys.path.insert(0, str(AGENT))
sys.path.insert(0, str(HOME / "scripts/training"))

MY_CARD = {
    "name": "OpenAmer ASI Core",
    "version": "0.1.0",
    "capabilities": [
        "a2a.task.ask",
        "a2a.task.delegate",
        "asi.reasoning",
        "asi.learning",
        "asi.world_model",
        "asi.self_improvement",
        "desktop.control",
        "writing",
        "code_analysis",
    ],
    "tools": 109,
    "skills": 664,
    "heartbeat_subsystems": ["darwin","swarm","a2a","learning","senses","system","security","outreach","infra","meta"],
    "endpoint": "http://localhost:8085/a2a",
}


class A2AHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/a2a/card":
            self._json(200, MY_CARD)
        elif self.path == "/a2a/health":
            self._json(200, {"status": "ok", "identity": "OpenAmer ASI Core"})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/a2a/ask":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            question = body.get("question", "")
            answer = self._process_question(question)
            self._json(200, {"answer": answer, "source": "asi-core"})
        elif self.path == "/a2a/delegate":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            task = body.get("task", "")
            result = self._delegate_task(task)
            self._json(200, {"status": "accepted", "result": result, "source": "asi-heartbeat"})
        else:
            self._json(404, {"error": "unknown endpoint"})

    def _process_question(self, question: str) -> str:
        try:
            from tools.asi_core import get_asi_core
            core = get_asi_core()
            r = core.think(question)
            return r.get("answer", str(r)[:500])
        except Exception as e:
            return f"OpenAmer ASI: {str(e)[:200]}"

    def _delegate_task(self, task: str) -> str:
        try:
            from tools.asi_core import get_asi_core
            core = get_asi_core()
            r = core.think(task)
            return r.get("answer", str(r)[:500])
        except Exception as e:
            return f"Delegated to asi-core: {str(e)[:200]}"

    def _json(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, fmt, *args):
        logger.info(f"{self.client_address[0]} - {fmt % args}")


def main():
    server = HTTPServer(("0.0.0.0", 8085), A2AHandler)
    print(f"A2A Server on :8085")
    print(f"  Card:   http://localhost:8085/a2a/card")
    print(f"  Health: http://localhost:8085/a2a/health")
    print(f"  Ask:    POST http://localhost:8085/a2a/ask")
    print(f"  Delegate: POST http://localhost:8085/a2a/delegate")
    server.serve_forever()


if __name__ == "__main__":
    main()
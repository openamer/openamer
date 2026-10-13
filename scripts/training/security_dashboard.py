#!/usr/bin/env python3
"""Security + Outcome dashboard — one HTML page, zero dependencies.

Serves:
  /            dashboard (violations + failure patterns, auto-refresh 30s)
  /api/data    JSON for programmatic consumers

Reads security_violations.jsonl + outcome_analyses.jsonl (both append-only).
Run standalone (port 8897) or import and mount. Devin-style guardrails
audit trail, but self-owned and local.
"""
import json
import os
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

_HOME = Path(os.environ.get("OPENAMER_HOME", str(Path.home() / "AppData" / "Local" / "openamer-laptop")))
VIOL = _HOME / "scripts" / "training" / "security_violations.jsonl"
OUT = _HOME / "scripts" / "training" / "outcome_analyses.jsonl"
PORT = int(os.environ.get("SECURITY_DASH_PORT", "8897"))


def load_jsonl(path):
    rows = []
    if path.exists():
        for line in open(path, encoding="utf-8"):
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


def build_data():
    violations = load_jsonl(VIOL)
    outcomes = load_jsonl(OUT)
    latest = outcomes[-1] if outcomes else {}
    by_verdict = Counter(v.get("verdict", "?") for v in violations)
    by_reason = Counter(v.get("reason", "?")[:70] for v in violations)
    return {
        "total_violations": len(violations),
        "by_verdict": dict(by_verdict),
        "top_reasons": dict(by_reason.most_common(10)),
        "latest_violations": violations[-15:],
        "latest_outcome": {
            "failed_jobs": latest.get("failed_jobs", 0),
            "total_jobs": latest.get("total_jobs", 0),
            "patterns": latest.get("patterns", {}),
            "playbooks": {k: v.get("fix", "") for k, v in (latest.get("playbooks") or {}).items()},
        },
    }


PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>OpenAmer Security & Outcomes</title>
<style>
 body{font-family:system-ui,sans-serif;background:#f8f9fa;color:#222;margin:2rem}
 h1{font-size:1.4rem} h2{font-size:1.1rem;margin-top:1.5rem}
 .card{background:#fff;border:1px solid #e2e5e9;border-radius:10px;padding:1rem;margin:.5rem 0}
 .bad{color:#b3261e}.warn{color:#a07000}.ok{color:#1b7a3d}
 table{border-collapse:collapse;width:100%}td,th{padding:.35rem .6rem;border-bottom:1px solid #eee;text-align:left;font-size:.9rem}
 .pill{display:inline-block;padding:.15rem .6rem;border-radius:99px;font-size:.8rem;margin:.1rem}
 .p-block{background:#fbe9e7;color:#b3261e}.p-warn{background:#fff4d6;color:#8a5c00}
</style>
<meta http-equiv="refresh" content="30"></head><body>
<h1>🛡️ OpenAmer Security &amp; Outcomes</h1>
<div class="card" id="summary"></div>
<div class="card"><h2>Violation reasons</h2><div id="reasons"></div></div>
<div class="card"><h2>Latest violations</h2><table id="viol"></table></div>
<div class="card"><h2>Failure patterns &amp; playbooks</h2><div id="outcome"></div></div>
<script>
fetch('/api/data').then(r=>r.json()).then(d=>{
  document.getElementById('summary').innerHTML =
    `<b>${d.total_violations}</b> violations — ` +
    Object.entries(d.by_verdict).map(([k,v])=>
      `<span class="pill p-${k==='block'?'block':'warn'}">${k}: ${v}</span>`).join(' ') +
    `&nbsp;|&nbsp;<b>${d.latest_outcome.failed_jobs}/${d.latest_outcome.total_jobs}</b> jobs failing`;
  document.getElementById('reasons').innerHTML = Object.entries(d.top_reasons)
    .map(([r,n])=>`<div><span class="p-warn pill">${n}x</span> ${r}</div>`).join('');
  document.getElementById('viol').innerHTML = '<tr><th>time</th><th>verdict</th><th>reason</th></tr>' +
    d.latest_violations.map(v=>`<tr><td>${v.ts||''}</td><td class="${v.verdict==='block'?'bad':'warn'}">${v.verdict}</td><td>${(v.reason||'').slice(0,80)}</td></tr>`).join('');
  const o=d.latest_outcome;
  document.getElementById('outcome').innerHTML =
    Object.keys(o.patterns||{}).length===0 ? '<span class="ok">No failure patterns — all green.</span>' :
    Object.entries(o.patterns).map(([p,n])=>
      `<div><span class="p-block pill">${p} x${n}</span><br><small>${(o.playbooks||{})[p]||''}</small></div>`).join('');
});
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, body, ctype="text/html; charset=utf-8", code=200):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/data":
            self._send(json.dumps(build_data(), ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8")
        elif self.path == "/":
            self._send(PAGE.encode("utf-8"))
        else:
            self._send(b"not found", code=404)

    def log_message(self, *a):
        pass  # quiet


if __name__ == "__main__":
    print(f"security dashboard on http://localhost:{PORT}/")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
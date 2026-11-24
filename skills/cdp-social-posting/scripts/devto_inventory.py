"""Read-only Dev.to article inventory over CDP :9222.

Why this exists
---------------
Every Dev.to outreach cron needs the *authoritative* published-article list to
(a) apply the per-run mass-post gate and (b) diff the repo README's
``## Writing`` cross-link section against reality. Fetching it by hand each run
produced drifted, mis-dated readings (local vs UTC) and re-typed one-off probes.

Contract: READ-ONLY. GET requests only. It never publishes, edits or deletes.

Run with the HOME VENV (needs the ``websocket`` module; bare ``python`` lacks it):

    ./venv/Scripts/python.exe skills/cdp-social-posting/scripts/devto_inventory.py

Output: one JSON object on stdout:

    {"me_status":200,"me":"openamer","art_status":200,"count":7,
     "articles":[{"id":4831400,"published":true,
                  "published_at":"2026-10-11T05:42:09.325Z",
                  "title":"...","url":"https://dev.to/openamer/..."}]}

Exit 0 means the probe RAN, not that anything is postable. Read the JSON.
``me_status`` 401 / a ``/magic_links/new`` redirect means the session is stale
(run ``session_manager.py restore`` first); ``me_status`` 200 means the session
IS the credential — a missing DEVTO_API_KEY is not a blocker.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:9222"

# Own tab, matched by id. Parallel cron workers navigate freshly created tabs to
# Bing, so never reuse a saved tab id and never fall back to tabs[0].
JS = """
(async () => {
  const out = {};
  const me = await fetch('/api/users/me', {credentials:'same-origin'});
  out.me_status = me.status;
  try { out.me = (await me.json()).username; } catch (e) { out.me = null; }
  const a = await fetch('/api/articles/me/all?per_page=50', {credentials:'same-origin'});
  out.art_status = a.status;
  try {
    const j = await a.json();
    out.count = j.length;
    out.articles = j.map(x => ({
      id: x.id, published: x.published, published_at: x.published_at,
      title: x.title, url: x.url
    }));
  } catch (e) { out.err = String(e); }
  return JSON.stringify(out);
})()
"""


def _http(url: str, method: str = "GET", timeout: int = 15):
    req = urllib.request.Request(url, method=method)
    return urllib.request.urlopen(req, timeout=timeout).read()


def main() -> int:
    try:
        from websocket import create_connection
    except ImportError:
        print("ERROR: no `websocket` module — run with ./venv/Scripts/python.exe", file=sys.stderr)
        return 2

    try:
        tab = json.loads(_http(BASE + "/json/new?about:blank", method="PUT"))
    except Exception as exc:  # noqa: BLE001 - CDP down is a real, reportable state
        print("ERROR: CDP :9222 not reachable (%s) — start Chrome first "
              "(see scripts/cron-browser-watchdog.py)" % exc, file=sys.stderr)
        return 3

    tid = tab["id"]
    ws = None
    try:
        lst = json.loads(_http(BASE + "/json"))
        wsu = next((t.get("webSocketDebuggerUrl") for t in lst
                    if t.get("id") == tid and t.get("webSocketDebuggerUrl")), None)
        if not wsu:
            print("ERROR: no ws for own tab %s" % tid, file=sys.stderr)
            return 4

        ws = create_connection(wsu, suppress_origin=True, timeout=30)
        ws.send(json.dumps({"id": 2, "method": "Page.navigate",
                            "params": {"url": "https://dev.to/dashboard"}}))
        time.sleep(6)  # let the session + SPA settle

        ws.send(json.dumps({"id": 3, "method": "Runtime.evaluate",
                            "params": {"expression": "location.href", "returnByValue": True}}))
        while True:
            msg = json.loads(ws.recv())
            if msg.get("id") == 3:
                print("HREF:", msg["result"]["result"].get("value"), file=sys.stderr)
                break

        ws.send(json.dumps({"id": 4, "method": "Runtime.evaluate",
                            "params": {"expression": JS, "awaitPromise": True,
                                       "returnByValue": True}}))
        while True:
            msg = json.loads(ws.recv())
            if msg.get("id") == 4:
                print(msg["result"]["result"].get("value"))
                break
        return 0
    finally:
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass
        try:
            _http(BASE + "/json/close/" + tid, timeout=10)
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())

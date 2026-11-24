"""Probe N platform login states via CDP :9222 with real evidence.

Fresh WebSocket per navigation (long-lived WS dies on renderer swap ->
WinError 10054). Writes a PNG per site and prints url/title/innerText/login-marker.

Usage:
    python3 platform_login_probe.py [url1 url2 ...]
    # defaults to the monetization platform set if no args

Requires: system python3 with `websocket-client` (NOT the OpenAmer venv),
Chrome running with --remote-debugging-port=9222 (profile Chrome, UA != HeadlessChrome).
Evidence dir defaults to <HOME>/AppData/Local/openamer-laptop/memory/si/evidence.
"""
import base64
import json
import os
import sys
import time
import urllib.parse
import urllib.request

import websocket

CDP = "http://127.0.0.1:9222"
EVID = os.path.join(os.path.expanduser("~"), "AppData", "Local", "openamer-laptop",
                    "memory", "si", "evidence")

DEFAULTS = [
    "https://gumroad.com/products",
    "https://issuehunt.io/",
    "https://algora.io/",
    "https://polar.sh/dashboard",
    "https://hackerone.com/users/sign_in",
]


def newtab(url):
    req = urllib.request.Request(CDP + "/json/new?" + urllib.parse.quote(url, safe=""),
                                 method="PUT")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


def clos(tid):
    try:
        urllib.request.urlopen(CDP + "/json/close/" + tid, timeout=10).read()
    except Exception:
        pass


def probe(url, name, settle=7):
    t = newtab(url)
    ws = websocket.create_connection(t["webSocketDebuggerUrl"], suppress_origin=True, timeout=30)
    n = 0

    def send(method, params=None):
        nonlocal n
        n += 1
        mid = n
        ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(ws.recv())
            if msg.get("id") == mid:
                return msg

    send("Page.enable")
    time.sleep(settle)
    info = send("Runtime.evaluate", {
        "expression": "({url:location.href, title:document.title, "
                      "text:(document.body?document.body.innerText:'').replace(/\\s+/g,' ').slice(0,1200), "
                      "login:[...document.querySelectorAll('a,button')].map(x=>x.innerText.trim())"
                      ".filter(x=>/log ?in|sign ?in|sign ?up|logout|sign ?out/i.test(x)).slice(0,10)})",
        "returnByValue": True})
    val = info.get("result", {}).get("result", {}).get("value", {})
    shot = send("Page.captureScreenshot", {"format": "png"})
    d = shot.get("result", {}).get("data")
    path = None
    if d:
        os.makedirs(EVID, exist_ok=True)
        path = os.path.join(EVID, name)
        with open(path, "wb") as f:
            f.write(base64.b64decode(d))
        sz = os.path.getsize(path)
        # PNG-size sanity: <3KB == blank/error page, not usable as evidence
        if sz < 3000:
            print(f"  !! WARNING {name} is only {sz} bytes (blank page?)")
    ws.close()
    clos(t["id"])
    return {"req": url, "final_url": val.get("url"), "title": val.get("title"),
            "text": val.get("text"), "login_links": val.get("login"), "shot": path}


def main():
    urls = sys.argv[1:] or DEFAULTS
    for i, u in enumerate(urls):
        nm = f"ev_probe_{i}.png"
        try:
            r = probe(u, nm)
            print(f"=== {u} ===")
            print("FINAL:", r["final_url"], "| TITLE:", r["title"])
            print("LOGIN:", r["login_links"])
            print("TEXT:", (r["text"] or "")[:400])
            print()
        except Exception as e:  # noqa: BLE001
            print(f"=== {u} ERROR: {e}")


if __name__ == "__main__":
    main()

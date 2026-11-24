#!/usr/bin/env python3
"""Minimal CDP driver for the OpenAmer Browser (:9333).

The :9333 Electron build is deliberately restricted: /json/new returns 500 and
browser-level Target.createTarget says "Not supported". Open tabs with
window.open() from an existing page instead. Websockets also die mid-OAuth
(normal, not a failure) - always reconnect with a fresh webSocketDebuggerUrl.
"""
import base64
import json
import time
import urllib.request

import websocket

BASE = "http://127.0.0.1:9333"


def targets(kind="page"):
    raw = urllib.request.urlopen(f"{BASE}/json/list", timeout=8).read()
    return [t for t in json.loads(raw)
            if t.get("type") == kind and "devtools" not in t.get("url", "")]


def find(sub):
    """First page target whose URL contains `sub`."""
    return next((t for t in targets() if sub in (t.get("url") or "")), None)


class Tab:
    """One CDP page target. Use as a context manager."""

    def __init__(self, target=None, prefer=None):
        target = target or (find(prefer) if prefer else None) or (targets() or [None])[0]
        if not target:
            raise RuntimeError("no page target on :9333")
        self.target_id = target["id"]
        self._connect()

    def _connect(self):
        for t in targets():
            if t["id"] != self.target_id:
                continue
            self.ws = websocket.create_connection(
                t["webSocketDebuggerUrl"], suppress_origin=True, timeout=60)
            self._id = 0
            return True
        raise RuntimeError("target gone: " + self.target_id)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _call(self, method, params=None, tries=400):
        self._id += 1
        mid = self._id
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        for _ in range(tries):
            try:
                msg = json.loads(self.ws.recv())
            except Exception:
                continue
            if msg.get("id") == mid:
                return msg
        return None

    def js(self, expr):
        r = self._call("Runtime.evaluate", {
            "expression": expr, "returnByValue": True, "awaitPromise": True})
        res = (r or {}).get("result", {})
        if "exceptionDetails" in res:
            d = res["exceptionDetails"].get("exception", {}).get("description", "")
            return "ERR:" + str(d)[:200]
        return res.get("result", {}).get("value")

    def nav(self, url, wait=8):
        """Navigate. The socket may abort during the load - reconnect after."""
        try:
            self._call("Page.navigate", {"url": url})
        except Exception:
            pass
        time.sleep(wait)
        try:
            self._connect()  # fresh ws for the new document
        except Exception:
            pass
        return self.js("location.href")

    def open_tab(self, url):
        """New tab via window.open - /json/new and Target.createTarget both fail here."""
        self.js(f"window.open({url!r},'_blank');'ok'")

    def set_file(self, selector, path):
        """File inputs cannot be set from JS. DOM.setFileInputFiles is the only way."""
        root = self._call("DOM.getDocument", {"depth": -1})["result"]["root"]["nodeId"]
        node = self._call("DOM.querySelector", {"nodeId": root, "selector": selector})
        node = node.get("result", {}).get("nodeId")
        if not node:
            return "no such element: " + selector
        r = self._call("DOM.setFileInputFiles", {"files": [path], "nodeId": node})
        return "ok" if r and "error" not in r else r

    def shot(self, path):
        r = self._call("Page.captureScreenshot", {"format": "png"})
        data = (r or {}).get("result", {}).get("data")
        if not data:
            return None
        with open(path, "wb") as f:
            f.write(base64.b64decode(data))
        return path

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


# React ignores `el.value = x`; the prototype setter + events is the working form.
SET_INPUT = """(sel,val)=>{const el=document.querySelector(sel);if(!el)return 'no '+sel;
const proto=el.tagName==='TEXTAREA'?HTMLTextAreaElement:HTMLInputElement;
Object.getOwnPropertyDescriptor(proto.prototype,'value').set.call(el,val);
el.dispatchEvent(new Event('input',{bubbles:true}));
el.dispatchEvent(new Event('change',{bubbles:true}));return 'ok';}"""


def set_value(tab, selector, value):
    """Set an input/textarea so React actually sees it."""
    return tab.js(f"({SET_INPUT})({json.dumps(selector)},{json.dumps(value)})")


if __name__ == "__main__":
    for t in targets():
        print(t.get("title", "")[:50], "|", t.get("url", "")[:90])

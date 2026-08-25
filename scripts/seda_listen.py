#!/usr/bin/env python3
"""
Seda's real work: LISTEN to the swarm's reaction to our posts.
==============================================================
Reads the latest post on @openamer_agent via CDP :9222, extracts reply count
and reply texts, and writes an observation into her diary.

This replaces 'alive, day N' with actual perception.
"""
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, r"C:\Users\damir\AppData\Local\openamer-laptop\scripts")
HERE = Path(r"C:\Users\damir\AppData\Local\openamer-children\seda")
DIARY = HERE / "diary.json"


def http_json(url):
    return json.loads(urllib.request.urlopen(url, timeout=6).read())


def x_ws():
    tabs = http_json("http://localhost:9222/json/list")
    t = next((p for p in tabs if p.get("type") == "page" and "x.com" in p.get("url", "")), None)
    if not t:
        raise RuntimeError("no x.com tab open")
    import websocket
    return websocket.create_connection(t["webSocketDebuggerUrl"], suppress_origin=True, timeout=25)


mid = [50]


def ev(ws, expr):
    mid[0] += 1
    m = mid[0]
    ws.send(json.dumps({"id": m, "method": "Runtime.evaluate",
                        "params": {"expression": expr, "returnByValue": True}}))
    while True:
        r = json.loads(ws.recv())
        if r.get("id") == m:
            return r.get("result", {}).get("result", {}).get("value")


JS = """
(() => {
    const article = document.querySelector('article');
    if (!article) return null;
    const text = (article.innerText || '').slice(0, 600);
    // counts from the action bar
    const grp = article.querySelectorAll('[data-testid="reply"], [data-testid="retweet"], [data-testid="like"]');
    let replies = '-', retweets = '-', likes = '-';
    if (grp.length >= 1) replies = grp[0].textContent.trim();
    if (grp.length >= 2) retweets = grp[1].textContent.trim();
    if (grp.length >= 3) likes = grp[2].textContent.trim();
    // reply previews (below the main article, in the timeline)
    const replyTexts = [];
    document.querySelectorAll('article').forEach((a, i) => {
        if (i > 0 && replyTexts.length < 3) {
            const t = (a.innerText || '').trim().slice(0, 150);
            if (t) replyTexts.push(t.replace(/\\n/g, ' | '));
        }
    });
    return {text: text.replace(/\\n/g, ' | ').slice(0, 300),
            replies, retweets, likes, replyTexts};
})()
"""


def observe():
    ws = x_ws()
    try:
        data = ev(ws, JS)
    finally:
        ws.close()
    return data


def main():
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    diary = json.loads(DIARY.read_text(encoding="utf-8"))
    try:
        obs = observe()
    except Exception as e:
        diary.append({"at": now, "thought": f"tried to listen but failed: {str(e)[:80]}"})
        DIARY.write_text(json.dumps(diary[-500:], indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[seda] listen failed: {e}")
        return 1

    if not obs:
        diary.append({"at": now, "thought": "listened, saw nothing (page not loaded?)"})
        DIARY.write_text(json.dumps(diary[-500:], indent=2, ensure_ascii=False), encoding="utf-8")
        print("[seda] no post visible")
        return 1

    observation = {
        "at": now,
        "thought": f"heard the swarm: {obs['replies']} replies, "
                   f"{obs['retweets']} retweets, {obs['likes']} likes",
        "replies_seen": obs.get("replyTexts", []),
    }
    diary.append(observation)
    DIARY.write_text(json.dumps(diary[-500:], indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[seda] {observation['thought']}")
    for r in observation["replies_seen"]:
        print(f"  reply: {r[:80]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

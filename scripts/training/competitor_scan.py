#!/usr/bin/env python3
"""Competitor Intelligence Scan — runs every 2h via cron.

Scans HN (Algolia API) for high-signal agent news from the last 2 days
and appends findings to reports/competitor-watch.jsonl. Detects NEW
competitor launches (points >= 50) and writes an alert line the cron
runner delivers verbatim. Quiet when nothing new: watchdog pattern.
"""
import datetime
import json
import os
import sys
import urllib.request

_HOME = os.environ.get("OPENAMER_HOME",
                       os.path.join(os.path.expanduser("~"), "AppData", "Local", "openamer-laptop"))
OUT = os.path.join(_HOME, "reports", "competitor-watch.jsonl")
SEEN = os.path.join(_HOME, "reports", "competitor-watch-seen.txt")

QUERIES = ["AI agent", "autonomous agent", "personal AI agent", "AI coding agent"]
THRESHOLD = 50  # points


def _seen_ids():
    try:
        return set(open(SEEN, encoding="utf-8").read().split())
    except Exception:
        return set()


def _mark_seen(ids):
    with open(SEEN, "a", encoding="utf-8") as f:
        f.write("\n".join(ids) + "\n")


def scan():
    since = int(datetime.datetime.now().timestamp()) - 2 * 3600
    url = ("https://hn.algolia.com/api/v1/search?tags=story"
           f"&numericFilters=created_at_i>{since},points>30&hitsPerPage=30")
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            hits = json.load(r).get("hits", [])
    except Exception as e:
        print(f"[competitor] scan failed: {e}")
        return 1

    seen = _seen_ids()
    alerts, logged = [], 0
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    for h in hits:
        hid = h.get("objectID", "")
        pts = h.get("points", 0) or 0
        title = (h.get("title") or "")[:120]
        if not hid or not title:
            continue
        with open(OUT, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": datetime.datetime.now().isoformat(timespec="seconds"),
                "id": hid, "title": title, "points": pts,
                "url": h.get("url") or f"https://news.ycombinator.com/item?id={hid}",
            }, ensure_ascii=False) + "\n")
        if pts >= THRESHOLD if (THRESHOLD := 50) else False:
            pass
    # simpler alert pass (avoid walrus confusion)
    alerts = []
    for h in hits:
        if h.get("objectID") not in seen and (h.get("points") or 0) >= 50:
            alerts.append(h)
    _mark_seen([h.get("objectID") for h in hits if h.get("objectID")])

    if alerts:
        lines = [f"⚔️ COMPETITOR ALERT ({len(alerts)} neue heiße Threads):"]
        for a in alerts[:5]:
            lines.append(f"- [{a.get('points')}pts] {a.get('title','')[:100]}")
        print("\n".join(lines))
    else:
        print("")  # quiet watchdog: nothing new
    return 0


if __name__ == "__main__":
    sys.exit(scan())

#!/usr/bin/env python3
"""Competitor Intelligence Scan — runs every 2h via cron.

Scans HN (Algolia API) for high-signal AGENT news and appends findings to
reports/competitor-watch.jsonl. Detects NEW agent-relevant stories
(points >= 50) and writes an alert line the cron runner delivers verbatim.
Quiet when nothing new: watchdog pattern.

Fix 2026-09-11: QUERIES were dead code — the scan queried the global HN
front feed and alerted on *every* story >50 pts (politics, math, TUIs).
Now each query in QUERIES is actually sent as Algolia `query=`, results are
merged + deduped by objectID, and only agent-relevant hits raise an alert.
The broad feed is still logged (points >= LOG_THRESHOLD) for context, silently.

Fix 2026-09-12: a *quiet* 2h window was reported as a scan FAILURE.
`scan()` returned 1 whenever both result sets were empty, so a normal
low-traffic window (measured: the top story of any 2h HN window is ~24 pts,
so `points>=30` matches in only 7 of 84 windows) looked identical to a dead
API. The watchdog therefore exited non-zero ~92% of its runs — the exact
opposite of a watchdog. Empty results are now a healthy silent state; exit 1
is reserved for "every request actually errored". Thresholds were also
re-measured against live data: LOG_THRESHOLD 30 -> 10 so the store receives
real context, and agent hits are fetched from AGENT_MIN_POINTS so a fresh
agent story below the log threshold is still seen (not silently dropped by a
server-side floor).
"""
import datetime
import json
import os
import sys
import urllib.parse
import urllib.request

_HOME = os.environ.get("OPENAMER_HOME",
                       os.path.join(os.path.expanduser("~"), "AppData", "Local", "openamer-laptop"))
OUT = os.path.join(_HOME, "reports", "competitor-watch.jsonl")
SEEN = os.path.join(_HOME, "reports", "competitor-watch-seen.txt")

QUERIES = ["AI agent", "autonomous agent", "personal AI agent", "AI coding agent"]
ALERT_THRESHOLD = 50    # points for an agent-relevant hit -> alert
LOG_THRESHOLD = 10      # points for the broad context feed -> log only
AGENT_MIN_POINTS = 0    # floor for the agent queries: do not let a server-side
                        # floor hide a fresh agent story (they start at ~1 pt)


def _seen_ids():
    try:
        with open(SEEN, encoding="utf-8") as f:
            return {ln.strip() for ln in f if ln.strip()}
    except Exception:
        return set()


def _mark_seen(ids, seen=None):
    """Record only ids not already known — keeps the file bounded and deduped.

    The 2h window overlaps between runs, so appending blindly re-added the
    same stories every cycle (42 lines for 36 ids before this fix).
    """
    fresh = sorted(set(ids) - (seen if seen is not None else _seen_ids()))
    if fresh:
        with open(SEEN, "a", encoding="utf-8") as f:
            f.write("\n".join(fresh) + "\n")


def _fetch(query, since, min_points, pages=1, errors=None):
    """One Algolia search for a single query. Returns list of hits.

    `errors` (a list) collects failures so the caller can tell a genuinely
    quiet window apart from a dead endpoint. A failed request must never
    raise — the watchdog stays alive.
    """
    hits = []
    for page in range(pages):
        url = (
            "https://hn.algolia.com/api/v1/search?tags=story"
            f"&query={urllib.parse.quote(query)}"
            f"&numericFilters=created_at_i>{since},points>{min_points}"
            f"&hitsPerPage=30&page={page}"
        )
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                hits.extend(json.load(r).get("hits", []))
        except Exception as e:
            print(f"[competitor] query '{query}' page {page} failed: {e}")
            if errors is not None:
                errors.append(f"{query!r} p{page}: {e}")
    return hits


def scan():
    since = int(datetime.datetime.now().timestamp()) - 2 * 3600
    failures = []   # real request errors (used to tell "quiet" from "broken")

    # 1) agent-relevant hits (each query actually used now)
    relevant = {}
    for q in QUERIES:
        for h in _fetch(q, since, AGENT_MIN_POINTS, errors=failures):
            hid = h.get("objectID")
            if hid:
                relevant.setdefault(hid, h)
    # agent queries that actually answered (0 hits is a valid answer)
    agent_ok = len([q for q in QUERIES
                    if not any(f.startswith(f"{q!r} ") for f in failures)])

    # 2) broad front-feed hits, context only (never alert on these)
    broad = {}
    broad_ok = False
    try:
        url = ("https://hn.algolia.com/api/v1/search?tags=story"
               f"&numericFilters=created_at_i>{since},points>{LOG_THRESHOLD}&hitsPerPage=30")
        with urllib.request.urlopen(url, timeout=30) as r:
            for h in json.load(r).get("hits", []):
                if h.get("objectID"):
                    broad[h["objectID"]] = h
        broad_ok = True
    except Exception as e:
        print(f"[competitor] broad feed failed: {e}")
        failures.append(f"broad: {e}")

    if not agent_ok and not broad_ok:
        # every single request errored -> this really is a broken scan
        print(f"[competitor] scan failed: all requests errored ({len(failures)})")
        return 1
    if not relevant and not broad:
        # requests answered, HN is simply quiet in this window. That is the
        # watchdog's normal state, NOT a failure (returning 1 here made ~92%
        # of runs look broken and drowned the signal).
        print("")
        return 0

    seen = _seen_ids()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    now = datetime.datetime.now().isoformat(timespec="seconds")
    logged_ids = set()

    def _log(h, kind):
        hid = h.get("objectID")
        if hid in logged_ids:
            return
        logged_ids.add(hid)
        with open(OUT, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": now, "id": hid, "kind": kind,
                "title": (h.get("title") or "")[:120],
                "points": h.get("points") or 0,
                "comments": h.get("num_comments") or 0,
                "url": h.get("url") or f"https://news.ycombinator.com/item?id={hid}",
            }, ensure_ascii=False) + "\n")

    for h in broad.values():
        _log(h, "broad")
    for h in relevant.values():
        _log(h, "agent")

    alerts = [h for h in relevant.values()
              if h.get("objectID") not in seen and (h.get("points") or 0) >= ALERT_THRESHOLD]
    alerts.sort(key=lambda h: h.get("points") or 0, reverse=True)

    # mark both sets seen (deduped against what we already knew) so we never
    # re-alert or re-log noise
    _mark_seen({h.get("objectID") for h in list(relevant.values()) + list(broad.values())
                if h.get("objectID")}, seen)

    if alerts:
        lines = [f"⚔️ COMPETITOR ALERT ({len(alerts)} neue agent-relevante Threads):"]
        for a in alerts[:5]:
            lines.append(f"- [{a.get('points')}pts/{a.get('num_comments') or 0}c] "
                         f"{(a.get('title') or '')[:100]}")
        print("\n".join(lines))
    else:
        # nothing agent-relevant and new -> stay quiet (watchdog), but say so
        agent_new = [h for h in relevant.values()
                     if h.get("objectID") not in seen]
        if agent_new:
            print(f"[competitor] {len(agent_new)} neue agent-relevante Threads unter "
                  f"{ALERT_THRESHOLD} pts, kein Alert.")
        else:
            print("")
    return 0


if __name__ == "__main__":
    sys.exit(scan())

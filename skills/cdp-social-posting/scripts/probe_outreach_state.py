#!/usr/bin/env python3
"""Deterministic read-only outreach state probe for HN + Reddit.

Why this exists: every outreach cron run re-derives the same verification by hand
(HN via urllib+cookie, Reddit via same-origin in-page fetch on an owned CDP tab).
That hand-typing is where the mistakes live. Run this instead.

Usage
-----
    python scripts/probe_outreach_state.py all
    python scripts/probe_outreach_state.py hn
    python scripts/probe_outreach_state.py reddit --reddit-user Realistic_Kitchen_65
    python scripts/probe_outreach_state.py reddit --submitted-of 1wguh1q

Exit code is 0 when the probe itself ran (regardless of what it found) — this is a
MEASUREMENT tool, not a pass/fail gate. Read the JSON it prints.

Read-only by contract: it never POSTs, never submits, never navigates a form.
It creates its own CDP tab and closes it again (never reuses tabs[0] — parallel
cron workers hijack that).
"""
import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path


def _find_sessions():
    """Locate openamer-browser/sessions.json by walking up from this file, then
    falling back to OPENAMER_HOME. (Skill dirs live under <home>/skills/<name>/,
    so a fixed parents[N] index breaks whenever the skill is moved.)"""
    here = Path(__file__).resolve()
    for base in list(here.parents) + [Path(os.environ.get("OPENAMER_HOME", ""))]:
        if not base or not str(base):
            continue
        cand = base / "openamer-browser" / "sessions.json"
        if cand.is_file():
            return cand
    return here.parents[3] / "openamer-browser" / "sessions.json"


HOME = Path(__file__).resolve().parent.parent
SESSIONS = _find_sessions()
CDP = "http://127.0.0.1:9222"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36")


def load_cookies(platform):
    """Return 'name=value; ...' for a platform key in sessions.json."""
    data = json.loads(SESSIONS.read_text(encoding="utf-8"))
    jar = data.get(platform) or []
    return "; ".join(f"{c['name']}={c['value']}" for c in jar if c.get("name"))


# --------------------------------------------------------------------------- HN
def probe_hn(username):
    """HN has NO usable JSON API for this: the cookie-authenticated HTML is the
    ground truth. /submitted?id=<u> shows '[flagged]' inline for flagged items;
    /threads?id=<u> counts flagged comments."""
    out = {"platform": "hackernews", "user": username}
    cookie = load_cookies("HN")
    out["cookie_present"] = bool(cookie)

    def get(path):
        req = urllib.request.Request(
            f"https://news.ycombinator.com/{path}",
            headers={"User-Agent": UA, "Cookie": cookie,
                     "Accept": "text/html,application/xhtml+xml"})
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, r.read().decode("utf-8", "replace")

    import re
    try:
        st, html = get(f"submitted?id={username}")
        out["submitted_status"] = st
        # header login tell: 'logout' link appears only when authenticated
        out["logged_in"] = "logout" in html.lower()
        items = []
        for block in re.split(r"<tr class=.athing", html)[1:]:
            mid = re.search(r"id=.(\d+)", block)
            title = re.search(r'class="titleline"[^>]*><a[^>]*>(.*?)</a>', block, re.S)
            items.append({
                "id": mid.group(1) if mid else None,
                "flagged": "[flagged]" in block,
                "title": (re.sub(r"<[^>]+>", "", title.group(1))[:90]
                          if title else None),
            })
        out["items"] = items
        out["flagged_count"] = sum(1 for i in items if i["flagged"])
    except Exception as e:
        out["submitted_error"] = f"{type(e).__name__}: {e}"

    try:
        st, html = get(f"threads?id={username}")
        out["threads_status"] = st
        out["threads_flagged_markers"] = html.count("[flagged]")
    except Exception as e:
        out["threads_error"] = f"{type(e).__name__}: {e}"
    return out


# ----------------------------------------------------------------------- Reddit
def _new_tab(url):
    req = urllib.request.Request(
        f"{CDP}/json/new?{urllib.parse.quote(url, safe='')}", method="PUT")
    return json.loads(urllib.request.urlopen(req, timeout=15).read())


class _Tab:
    """Own CDP tab. suppress_origin=True is MANDATORY or the ws handshake 403s."""

    def __init__(self, tid):
        import websocket
        for t in json.loads(urllib.request.urlopen(f"{CDP}/json", timeout=8).read()):
            if t["id"] == tid and t.get("type") == "page":
                self.ws = websocket.create_connection(
                    t["webSocketDebuggerUrl"], suppress_origin=True, timeout=90)
                self._id = 0
                return
        raise RuntimeError("tab gone")

    def ev(self, expr, await_promise=True, timeout=45000):
        import websocket  # noqa: F401  (kept local to this class by design)
        self._id += 1
        mid = self._id
        self.ws.send(json.dumps({"id": mid, "method": "Runtime.evaluate",
                                 "params": {"expression": expr,
                                            "awaitPromise": await_promise,
                                            "returnByValue": True,
                                            "timeout": timeout}}))
        for _ in range(700):
            m = json.loads(self.ws.recv())
            if m.get("id") == mid:
                res = m.get("result", {})
                if "exceptionDetails" in res:
                    return "EXC:" + json.dumps(res["exceptionDetails"])[:300]
                return res.get("result", {}).get("value")

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


# Reddit's host-level curl gets HTTP 403 Blocked, so every call MUST be a
# same-origin fetch inside a logged-in reddit.com tab.
REDDIT_JS = """
(async () => {
  const out = {};
  // /api/me.json can return an EMPTY body transiently in a fresh tab.
  // Fetch it as text with a status code, and retry once.
  const tryMe = async () => {
    for (let i = 0; i < 3; i++) {
      try {
        const r = await fetch('/api/me.json', {credentials:'include'});
        const t = await r.text();
        if (t && t.length > 2) return {status: r.status, body: t};
      } catch(e) {}
      await new Promise(res => setTimeout(res, 1000));
    }
    return {status: null, body: ''};
  };
  out.me = await tryMe();
  try {
    const r = await fetch('/user/__USER__/about.json', {credentials:'include'});
    out.about_status = r.status;
    const j = await r.json();
    const d = j && j.data;
    if (d) out.about = {name:d.name, comment_karma:d.comment_karma,
                        link_karma:d.link_karma, total_karma:d.total_karma,
                        has_verified_email:d.has_verified_email,
                        created_utc:d.created_utc};
  } catch(e) { out.about_err = String(e); }
  try {
    const r = await fetch('/user/__USER__/submitted.json?limit=25', {credentials:'include'});
    const j = await r.json();
    out.submitted = (j.data.children || []).map(c => ({
      id:c.data.id, sub:c.data.subreddit, title:(c.data.title||'').slice(0,70),
      removed_by_category:c.data.removed_by_category, score:c.data.score,
      created_utc:c.data.created_utc}));
  } catch(e) { out.submitted_err = String(e); }
  try {
    const r = await fetch('/user/__USER__/comments.json?limit=100', {credentials:'include'});
    const j = await r.json();
    out.comments = (j.data.children || []).map(c => ({
      id:c.data.id, sub:c.data.subreddit, score:c.data.score,
      removal_reason:c.data.removal_reason || c.data.removed_by_category || null,
      created_utc:c.data.created_utc}));
  } catch(e) { out.comments_err = String(e); }
  return JSON.stringify(out);
})()
"""

# Comment BODIES: /comments/<id>.json returns 404 for a bare comment id.
# /api/info.json with t1_ prefixed ids (comma-joined) is the endpoint that works.
INFO_JS = """
(async () => {
  const out = {};
  try {
    const r = await fetch('/api/info.json?id=__IDS__&raw_json=1', {credentials:'include'});
    out.status = r.status;
    const j = await r.json();
    out.comments = (j.data.children || []).map(c => ({
      id:c.data.id, author:c.data.author, sub:c.data.subreddit,
      link_id:c.data.link_id, score:c.data.score, created_utc:c.data.created_utc,
      removed:c.data.removed_by_category || c.data.removal_reason || null,
      body:c.data.body}));
  } catch(e) { out.err = String(e); }
  return JSON.stringify(out);
})()
"""


def probe_reddit(username, comment_ids=None, submitted_of=None):
    out = {"platform": "reddit", "user": username}
    tid = _new_tab("https://www.reddit.com/")
    tab = _Tab(tid["id"])
    try:
        time.sleep(3)

        def run(js):
            raw = tab.ev(js)
            try:
                return json.loads(raw)
            except Exception:
                return {"_raw": raw}

        out.update(run(REDDIT_JS.replace("__USER__", username)))

        # dedupe check: does the item we are about to post already exist?
        if submitted_of:
            hit = [s for s in (out.get("submitted") or []) if s["id"] == submitted_of]
            out["already_submitted"] = bool(hit)
            out["already_submitted_detail"] = hit

        if comment_ids:
            ids = ",".join(f"t1_{c}" for c in comment_ids)
            out["comment_bodies"] = run(INFO_JS.replace("__IDS__", ids))
    finally:
        tab.close()
        try:
            urllib.request.urlopen(f"{CDP}/json/close/{tid['id']}", timeout=8).read()
        except Exception:
            pass
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target", choices=["all", "hn", "reddit"])
    ap.add_argument("--hn-user", default="openamer")
    ap.add_argument("--reddit-user", default="Realistic_Kitchen_65")
    ap.add_argument("--comments", nargs="*", default=[],
                    help="Reddit comment ids to fetch bodies for (via /api/info.json)")
    ap.add_argument("--submitted-of", default=None,
                    help="Reddit post id to dedupe-check against submitted.json")
    a = ap.parse_args()

    result = {}
    if a.target in ("all", "hn"):
        result["hn"] = probe_hn(a.hn_user)
    if a.target in ("all", "reddit"):
        result["reddit"] = probe_reddit(a.reddit_user, a.comments, a.submitted_of)

    print(json.dumps(result, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

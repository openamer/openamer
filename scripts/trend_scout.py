#!/usr/bin/env python3
"""trend_scout.py — hourly, zero-cost AI-agent trend radar.

Polls free public sources (no key, no LLM tokens) for what's new/better in the
agentic-AI space, filters for relevant signals, and writes a scored report into
reports/ so future sessions can quickly see what to evaluate & integrate.

Run as a no_agent cron (cheap, no tokens). Sources:
  - Hacker News Algolia API (front page / search)  — free, no key
  - arXiv API (cs.AI agentic)                       — free, no key
  - Google News RSS "AI agent"                      — free, no key

Output: reports/trend-scout-latest.md (machine + human readable).
Exit 0 always (never noise the cron when healthy).
"""
import datetime as _dt
import html
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(r"C:\Users\damir\openamer-repo")
OUT_DIR = REPO / "reports"

KEYWORDS = (
    "ai agent", "autonomous agent", "agentic", "multi-agent", "agent framework",
    "computer use", "agent orchestration", "mcp", "model context protocol",
    "tool use", "swarm", "a2a", "agent-to-agent", "coding agent",
)

_HN_QUERY = '"ai agent" OR "autonomous agent" OR "agentic" OR "agent framework" OR "multi-agent"'


def _get(url, timeout=15, headers=None):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "openamer-trend-scout/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def _hn():
    out = []
    try:
        q = urllib.parse.quote(_HN_QUERY)
        data = json.loads(_get(
            f"https://hn.algolia.com/api/v1/search?query={q}&tags=story&hitsPerPage=12"))
        for h in data.get("hits", []):
            title = html.unescape(h.get("title") or "")
            url = h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}"
            pts = h.get("points") or 0
            out.append((pts, f"[HN {pts}pts] {title} — {url}"))
    except Exception as e:
        out.append((0, f"[HN error: {e}]"))
    return out


def _arxiv():
    out = []
    try:
        q = urllib.parse.quote('all:"AI agent"')
        data = _get(f"https://export.arxiv.org/api/query?search_query={q}&start=0&max_results=8")
        # crude parse: <entry><title>...</title>
        for m in re.finditer(r"<entry>.*?<title>(.*?)</title>.*?<id>(.*?)</id>", data, re.S):
            title = html.unescape(m.group(1)).strip().replace("\n", " ")
            url = m.group(2).strip()
            out.append((0, f"[arXiv] {title} — {url}"))
    except Exception as e:
        out.append((0, f"[arXiv error: {e}]"))
    return out


def _google_news():
    out = []
    try:
        q = urllib.parse.quote("AI agent agentic")
        data = _get(f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en")
        for m in re.finditer(r"<item>.*?<title>(.*?)</title>.*?<link>(.*?)</link>", data, re.S):
            title = html.unescape(m.group(1)).strip()
            link = m.group(2).strip()
            if title.lower() != "ai agent agentic":
                out.append((0, f"[News] {title} — {link}"))
    except Exception as e:
        out.append((0, f"[News error: {e}]"))
    return out


def _dedupe(items, cap=25):
    """Sort by score desc, drop duplicates, cap at `cap`."""
    seen, uniq = set(), []
    for score, line in sorted(items, key=lambda x: -x[0]):
        if line in seen:
            continue
        seen.add(line)
        uniq.append(line)
    return uniq[:cap]


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    items = _hn() + _arxiv() + _google_news()
    uniq = _dedupe(items, cap=25)

    now = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="minutes")
    out = OUT_DIR / "trend-scout-latest.md"
    out.write_text(
        f"# AI-Agent Trend Scout\n\n_updated: {now} (auto, hourly, zero-token)_\n\n"
        + "".join(f"- {line}\n" for line in uniq)
        + f"\n---\nScanned: HackerNews + arXiv + Google-News. "
        f"{len(uniq)} signals.\n",
        encoding="utf-8")
    # keep a dated copy too
    dated = OUT_DIR / f"trend-scout-{time.strftime('%Y%m%d-%H')}.md"
    if not dated.exists():
        dated.write_text(out.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"trend-scout wrote {len(uniq)} signals to reports/trend-scout-latest.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
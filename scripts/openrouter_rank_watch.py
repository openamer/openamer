#!/usr/bin/env python
"""OpenRouter ranking watchdog for OpenAmer Agent.

Why this exists
---------------
OpenAmer accumulated 7.71B attributed tokens on OpenRouter but appeared in
*no* marketplace category, because ``X-OpenRouter-Categories`` carried group
names (``coding``/``productivity``) instead of recognised category names.
OpenRouter drops unrecognised values silently — the app page still exists and
still counts tokens, so nothing looks broken from the inside. The only place
the truth is visible is the public category listing.

Implementation note
-------------------
The listing page ships a server-rendered ``application/ld+json`` ItemList
(name + position, 50 entries) — a stable, structured source that needs no JS
engine and no HTML heuristics. We read that. Fetching via ``curl --max-time``
rather than ``urllib``: urllib stalls for minutes against openrouter.ai from
this host, curl returns the same page in ~0.2s.

Usage
-----
    python openrouter_rank_watch.py                 # status report
    python openrouter_rank_watch.py --alert-only    # silent unless changed
    python openrouter_rank_watch.py --json          # machine-readable

Exit codes: 0 = ok (whether or not we are listed), 1 = could not read any
category (so a cron failure is visible rather than a false "absent").
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

APP_NAME = "OpenAmer Agent"
APP_URL = "https://github.com/openamer/openamer"

CATEGORIES = {
    "cli-agent": "https://openrouter.ai/apps/category/coding/cli-agent",
    "ide-extension": "https://openrouter.ai/apps/category/coding/ide-extension",
    "cloud-agent": "https://openrouter.ai/apps/category/coding/cloud-agent",
    "personal-agent": "https://openrouter.ai/apps/category/productivity/personal-agent",
}

STATE_PATH = Path(
    os.environ.get("OPENAMER_STATE_DIR", Path.home() / ".openamer")
) / "openrouter-rank-state.json"

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0 Safari/537.36"
_ITEMLIST_RE = re.compile(r'"itemListElement":(\[.*?\])\s*\}', re.S)
_ENTRY_RE = re.compile(r'"position":\s*(\d+)\s*,\s*"name":\s*"(.*?)"')


def _curl(url: str, timeout: int = 45) -> str:
    proc = subprocess.run(
        ["curl", "-sL", "--max-time", str(timeout), "-A", _UA, url],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
    )
    if proc.returncode != 0 and not proc.stdout:
        raise RuntimeError(f"curl exit {proc.returncode}: {proc.stderr.strip()[:200]}")
    return proc.stdout or ""


def _parse_listing(html: str) -> list[dict]:
    """Extract [(position, name)] from the page's JSON-LD ItemList.

    The page carries more than one ItemList — the site navigation is one too
    (4 entries, leader "Home"). The app ranking is the long one, so pick the
    ItemList with the most entries rather than the first match.
    """
    best: list[dict] = []
    for blob in _ITEMLIST_RE.findall(html):
        rows = [
            {"rank": int(pos), "name": name}
            for pos, name in _ENTRY_RE.findall(blob)
        ]
        if len(rows) > len(best):
            best = rows
    return best


def collect() -> dict:
    out: dict = {"app_url": APP_URL, "app_name": APP_NAME, "categories": {}}
    for cat, url in CATEGORIES.items():
        try:
            rows = _parse_listing(_curl(url))
        except Exception as exc:  # noqa: BLE001 - a watchdog must not crash
            out["categories"][cat] = {"error": f"{type(exc).__name__}: {exc}"}
            continue
        hit = next(
            (r for r in rows if r["name"].strip().lower() == APP_NAME.lower()), None
        )
        rec: dict = {
            "listed": bool(hit),
            "listed_count": len(rows),
            "leader": rows[0]["name"] if rows else None,
        }
        if hit:
            rec["rank"] = hit["rank"]
        out["categories"][cat] = rec
    return out


def _load_state() -> dict:
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _summary(data: dict) -> str:
    parts = []
    for cat, res in data["categories"].items():
        if "error" in res:
            parts.append(f"{cat}:ERR")
        elif res.get("listed"):
            parts.append(f"{cat}:#{res['rank']}/{res['listed_count']}")
        else:
            parts.append(f"{cat}:absent")
    return " ".join(parts)


def _changes(prev: dict, cur: dict) -> list[str]:
    msgs = []
    for cat, res in cur["categories"].items():
        old = (prev.get("categories") or {}).get(cat) or {}
        if res.get("listed") and not old.get("listed"):
            msgs.append(
                f"🎉 OpenAmer Agent erscheint jetzt in OpenRouter '{cat}': "
                f"Platz #{res['rank']} von {res['listed_count']} "
                f"(Führung: {res.get('leader')})"
            )
        elif res.get("listed") and old.get("listed") and res.get("rank") != old.get("rank"):
            direction = "▲" if res["rank"] < old["rank"] else "▼"
            msgs.append(f"{direction} {cat}: Platz {old['rank']} → {res['rank']}")
        elif old.get("listed") and not res.get("listed"):
            msgs.append(f"⚠️ {cat}: nicht mehr gelistet (war #{old.get('rank')})")
    return msgs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="OpenRouter ranking watchdog for OpenAmer")
    ap.add_argument("--alert-only", action="store_true", help="print only on change")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    cur = collect()
    readable = [c for c, r in cur["categories"].items() if "error" not in r]
    if not readable:
        errs = "; ".join(f"{c}: {r['error']}" for c, r in cur["categories"].items())
        print(f"OpenRouter listing WATCHDOG FEHLER — keine Kategorie lesbar: {errs}")
        return 1

    prev = _load_state()
    changes = _changes(prev, cur)
    _save_state(cur)

    if args.json:
        print(json.dumps({"summary": _summary(cur), "changes": changes}, indent=2, ensure_ascii=False))
        return 0

    if args.alert_only:
        if changes:
            print("\n".join(changes))
        return 0

    print(f"OpenRouter Listing: {_summary(cur)}")
    for cat, res in cur["categories"].items():
        print(f"  {cat}: {json.dumps(res, ensure_ascii=False)}")
    for c in changes:
        print(f"  → {c}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
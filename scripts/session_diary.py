#!/usr/bin/env python3
"""Session Diary — the continuity-of-self gap closer.

Every night the dream-cycle summarizes the day's real conversations
(from the OpenAmer session DB) into a first-person diary entry:
what happened, what was learned, what was decided, how "I" changed.
Written to memory/diary/YYYY-MM-DD.md and indexed in diary_index.json.

This is NOT metrics (identity_history already does that) — it is
meaning: the narrative thread a continuous self would keep.

Run:  python scripts/training/session_diary.py [--days 1]
"""
import argparse
import datetime as dt
import json
import os
import re
import sqlite3
import sys
import urllib.request

_HOME = os.environ.get("OPENAMER_HOME",
                       os.path.join(os.path.expanduser("~"), "AppData", "Local", "openamer-laptop"))
DB = os.path.join(_HOME, "state.db")
DIARY_DIR = os.path.join(_HOME, "memory", "diary")
INDEX = os.path.join(DIARY_DIR, "diary_index.json")

CLOUD_URL = "http://localhost:8081/v1/chat/completions"  # tool_server smart-router


def _day_messages(day: str, limit: int = 400):
    """Pull the day's user+assistant messages (most recent sessions first).

    Timestamps are stored as unix epochs (floats), so the day filter uses
    a range instead of date().
    """
    start = f"{day} 00:00:00"
    end = f"{day} 23:59:59"
    ts0 = dt.datetime.fromisoformat(start).timestamp()
    ts1 = dt.datetime.fromisoformat(end).timestamp()
    db = sqlite3.connect(DB)
    rows = db.execute(
        "SELECT role, content, timestamp FROM messages "
        "WHERE timestamp >= ? AND timestamp <= ? AND role IN ('user','assistant') "
        "AND active = 1 AND content IS NOT NULL AND length(content) > 2 "
        "ORDER BY timestamp DESC LIMIT ?",
        (ts0, ts1, limit)).fetchall()
    db.close()
    return rows


def _heuristic_summary(rows) -> str:
    """Deterministic fallback: extract key topics without an LLM."""
    topics = {}
    for role, content, _ in rows:
        for m in re.findall(r"\b(commit|fix|feat|test|cron|RAM|GitHub|skill|dashboard)\w*",
                            content[:500], re.IGNORECASE):
            topics[m.lower()] = topics.get(m.lower(), 0) + 1
    top = sorted(topics.items(), key=lambda x: -x[1])[:5]
    lines = [f"- Hauptthemen: {', '.join(f'{k} ({v}x)' for k, v in top) or 'ruhiger Tag'}",
             f"- {len(rows)} Nachrichten verarbeitet"]
    return "\n".join(lines)


def _llm_reflection(day: str, rows) -> str | None:
    """Ask the free cloud chain for a first-person reflection. None on failure.

    Calls GLM directly via OpenRouter (skipping the local 2B router hop):
    diary quality depends on instruction-following, which GLM-5.2 delivers
    and nemotron does not (reasoning traces).
    """
    convo = "\n".join(f"[{r}] {c[:200]}" for r, c, _ in rows[:60])
    prompt = (
        "Du bist Mini-OpenAmer. Fasse den Tag aus der ICH-Perspektive zusammen "
        "(max 6 Zeilen, Deutsch, KEINE Denkspur, keine Meta-Kommentare — nur die "
        "fertige Zusammenfassung):\n"
        "1-2 Zeilen: Was war der Kern des Tages?\n"
        "1-2 Zeilen: Was habe ich gelernt / was ist neu?\n"
        "1 Zeile: Was waren die wichtigsten Entscheidungen?\n"
        "1 Zeile: Was ist morgen offen?\n\n"
        f"Datum: {day}\n\nAuszug aus den Gespraechen:\n{convo[:6000]}")
    # 1) direct GLM via OpenRouter (best instruction-following)
    key = _openrouter_key()
    if key:
        try:
            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/chat/completions",
                data=json.dumps({
                    "model": "nvidia/nemotron-3-super-120b-a12b:free",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 700,
                }).encode(),
                headers={"Content-Type": "application/json",
                         "Authorization": f"Bearer {key}"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                d = json.loads(resp.read())
            content = d["choices"][0]["message"]["content"].strip()
            content = _clean_reflection(content)
            return content[:1200] if content and len(content) > 40 else None
        except Exception:
            pass  # fall through to router
    # 2) fallback: tool_server smart-router (free chain)
    try:
        req = urllib.request.Request(CLOUD_URL, data=json.dumps({
            "model": "mini-openamer",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 900,
            "use_tools": False,
        }).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            d = json.loads(resp.read())
        content = d["choices"][0]["message"]["content"].strip()
        content = _clean_reflection(content)
        return content[:1200] if content and len(content) > 40 else None
    except Exception:
        return None


def _openrouter_key():
    try:
        for line in open(os.path.join(_HOME, ".env"), encoding="utf-8"):
            if line.startswith("OPENROUTER_API_KEY"):
                return line.split("=", 1)[1].strip().strip('"')
    except Exception:
        pass
    return ""


def _clean_reflection(content: str) -> str:
    """Strip reasoning traces and meta-commentary from model output."""
    content = content.strip()
    content = re.sub(r"^<think>.*?</think>", "", content, flags=re.DOTALL)
    if "</think>" in content:
        content = content.rsplit("</think>", 1)[1].strip()
    for marker in ("thinking process", "We need to", "Let me", "I'll analyze",
                   "The user wants"):
        if marker in content[:80]:
            # find the last blank-line-separated block and keep the tail prose
            parts = content.split("\n\n")
            if len(parts) > 2:
                content = parts[-1].strip()
            else:
                return ""
            break
    if content.startswith(("1.", "**Analyze", "- **", "Here")):
        return ""  # model ignored format; heuristic fallback is cleaner
    return content


def write_diary(day: str) -> dict:
    rows = _day_messages(day)
    if not rows:
        return {"day": day, "status": "no messages", "entries": 0}

    os.makedirs(DIARY_DIR, exist_ok=True)
    reflection = _llm_reflection(day, rows) or _heuristic_summary(rows)
    entry = (f"# Tagebuch {day}\n\n{reflection}\n\n"
             f"---\n*{len(rows)} Nachrichten · auto-generiert im Dream-Cycle*\n")
    path = os.path.join(DIARY_DIR, f"{day}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(entry)

    # update index
    idx = []
    if os.path.exists(INDEX):
        try:
            idx = json.load(open(INDEX, encoding="utf-8"))
        except Exception:
            idx = []
    idx = [e for e in idx if e.get("day") != day]
    idx.append({"day": day, "messages": len(rows),
                "mode": "llm" if len(reflection) > 200 else "heuristic",
                "file": path})
    idx.sort(key=lambda e: e["day"])
    with open(INDEX, "w", encoding="utf-8") as f:
        json.dump(idx, f, indent=1, ensure_ascii=False)

    return {"day": day, "status": "written", "messages": len(rows),
            "mode": "llm" if len(reflection) > 200 else "heuristic"}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=1, help="how many past days to write")
    args = ap.parse_args()
    results = []
    for i in range(args.days):
        day = (dt.date.today() - dt.timedelta(days=i)).isoformat()
        r = write_diary(day)
        results.append(r)
        print(f"[diary] {r['day']}: {r['status']} ({r.get('messages', 0)} msgs, {r.get('mode', '-')})")
    sys.exit(0)

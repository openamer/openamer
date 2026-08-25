#!/usr/bin/env python3
"""
OpenAmer Circadian Engine - the SLEEP organ.
============================================
A living being needs rest. This engine gives OpenAmer a day/night rhythm:

  AWAKE  (07:00-23:00)  - full fleet activity
  WIND-DOWN (23:00-01:00) - heavy jobs pause, heartbeat + immune system stay on
  SLEEP (01:00-07:00)   - only essential organs (night watch, watchdogs)
  DREAM (within sleep)  - memory consolidation: read today's learnings,
                          compress them, write tomorrow's intentions

The engine does NOT kill cron jobs (the scheduler owns them). It maintains a
state file that wrapper jobs consult, and it runs the dream-consolidation once
per night.

Usage:
  circadian.py status            # what phase are we in?
  circadian.py enforce           # write current phase to state file
  circadian.py dream             # run dream consolidation manually

Exit codes: 0 = ok.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

STATE_DIR = Path(r"C:\Users\damir\AppData\Local\openamer-laptop")
STATE_FILE = STATE_DIR / "circadian.json"
LEARNINGS = STATE_DIR / "cache" / "learnings.json"
DREAM_LOG = STATE_DIR / "dreams.json"

# Phase boundaries (local hours). A young organism sleeps a lot: 8h.
PHASES = [
    ("AWAKE", 7, 23),
    ("WIND_DOWN", 23, 1),
    ("SLEEP", 1, 7),
]

ESSENTIAL_JOBS = {
    # name substrings of jobs that keep running during SLEEP (organs, not muscles)
    "watchdog", "nachtwache", "immune", "self-healer", "traffic", "browser-health",
}


def now_hour():
    return datetime.now().hour


def current_phase(h=None):
    h = now_hour() if h is None else h
    for name, start, end in PHASES:
        if start < end and start <= h < end:
            return name
        if start > end and (h >= start or h < end):  # wraps midnight
            return name
    return "AWAKE"


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def cmd_status():
    st = load_state()
    phase = current_phase()
    print(f"phase: {phase}")
    print(f"last enforced: {st.get('phase', 'never')} at {str(st.get('at'))[:19]}")
    print(f"dreams recorded: {len(st.get('dream_log', []))}")
    return 0


def cmd_enforce():
    phase = current_phase()
    st = load_state()
    prev = st.get("phase")
    st["phase"] = phase
    st["at"] = datetime.now(timezone.utc).isoformat()
    st["essential_only"] = phase == "SLEEP"
    st["paused_jobs"] = []
    save_state(st)
    if phase != prev:
        print(f"[circadian] phase transition: {prev} -> {phase}")
    else:
        print(f"[circadian] phase stable: {phase}")
    return 0


def cmd_dream():
    """Dream consolidation: compress today's learnings into an intention."""
    dreams = []
    if DREAM_LOG.exists():
        dreams = json.loads(DREAM_LOG.read_text(encoding="utf-8"))

    today = datetime.now().strftime("%Y-%m-%d")
    entry = {"date": today, "insights": [], "intentions": []}
    now = datetime.now(timezone.utc)

    if LEARNINGS.exists():
        try:
            learn = json.loads(LEARNINGS.read_text(encoding="utf-8"))
            items = learn if isinstance(learn, list) else learn.get("learnings", [])
            # Learning-Loop items: {category, text, title, timestamp} - take the
            # last 48h, dedupe by text, and skip useless one-word entries.
            from datetime import timedelta
            cutoff = (now - timedelta(hours=48)).isoformat()
            seen_texts = set()
            for i in reversed(items):
                ts = str(i.get("timestamp", ""))
                if ts < cutoff:
                    continue
                msg = str(i.get("text", "")).strip()
                if len(msg) < 8 or msg.lower() in ("error", "fail", "failed"):
                    continue  # noise from log-scan
                if msg in seen_texts:
                    continue
                seen_texts.add(msg)
                entry["insights"].append(
                    {"error": msg[:120], "fix": "", "from": i.get("title", "")})
                if len(entry["insights"]) >= 10:
                    break
        except Exception as e:
            entry["insights"].append({"error": f"learnings unreadable: {e}", "fix": ""})

    # Intentions derived from insights (simple heuristics - honest, not magic)
    if any("429" in str(i.get("error", "")) for i in entry["insights"]):
        entry["intentions"].append("pace API calls; 429 means hunger, not failure")
    if any("WinError 10054" in str(i.get("error", "")) for i in entry["insights"]):
        entry["intentions"].append("fresh websocket after every navigation")

    dreams = [d for d in dreams if d.get("date") != today]
    dreams.append(entry)
    DREAM_LOG.write_text(json.dumps(dreams[-60:], indent=2, ensure_ascii=False), encoding="utf-8")

    st = load_state()
    st["dream_log"] = [d["date"] for d in dreams]
    st["last_dream"] = datetime.now(timezone.utc).isoformat()
    save_state(st)
    print(f"[dream] consolidated {len(entry['insights'])} insights, "
          f"{len(entry['intentions'])} intentions for {today}")
    return 0


def main():
    args = sys.argv[1:]
    cmd = args[0] if args else "status"
    if cmd == "enforce":
        return cmd_enforce()
    if cmd == "dream":
        return cmd_dream()
    return cmd_status()


if __name__ == "__main__":
    sys.exit(main())

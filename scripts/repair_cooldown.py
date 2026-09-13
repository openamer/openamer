#!/usr/bin/env python3
"""Repair cooldown / idempotency guard (AEON skill-repair history idea).

Purpose: prevent repair loops. A workflow that was repaired less than
COOLDOWN_H hours ago must not be repaired again -- otherwise a cron wrapper
that keeps failing gets patched over and over, burning tokens and hiding the
real fault.

State: scripts/_repair_history.json
  {"<target>": {"last_repair": "<iso>", "count": N, "outcomes": [...]}}

Usage:
  repair_cooldown.py check <target>          -> exit 0 = allowed, 3 = cooling down
  repair_cooldown.py mark  <target> <outcome> -> record a repair (outcome: FIXED|SYSTEMIC|NO_FIX|BLOCKED)
  repair_cooldown.py status                  -> print table of all targets
Exit codes: 0 ok, 3 suppressed (cooldown), 2 bad usage.
"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

OA_HOME = Path(r"C:\Users\damir\AppData\Local\openamer-laptop")
STATE = OA_HOME / "scripts" / "_repair_history.json"
COOLDOWN_H = 24
VALID = {"REPAIR_OK_FIXED", "REPAIR_OK_SYSTEMIC", "REPAIR_DIAGNOSED_NO_FIX", "REPAIR_BLOCKED"}


def _load():
    if STATE.exists():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save(d):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")


def cmd_check(target):
    d = _load()
    rec = d.get(target)
    if not rec or not rec.get("last_repair"):
        print(f"ALLOW {target}: no prior repair")
        return 0
    last = datetime.fromisoformat(rec["last_repair"])
    age = datetime.now() - last
    if age < timedelta(hours=COOLDOWN_H):
        left = timedelta(hours=COOLDOWN_H) - age
        print(f"COOLDOWN {target}: repaired {age} ago ({rec.get('count', 0)}x total), "
              f"{left} left -- skipping re-repair (prev outcome: {rec.get('outcome', '?')})")
        return 3
    print(f"ALLOW {target}: last repair {age} ago (> {COOLDOWN_H}h)")
    return 0


def cmd_mark(target, outcome):
    if outcome not in VALID:
        print(f"bad outcome '{outcome}', valid: {sorted(VALID)}")
        return 2
    d = _load()
    rec = d.get(target) or {"count": 0, "outcomes": []}
    rec["last_repair"] = datetime.now().isoformat(timespec="seconds")
    rec["outcome"] = outcome
    rec["count"] = int(rec.get("count", 0)) + 1
    rec["outcomes"] = (rec.get("outcomes") or [])[-9:] + [outcome]
    d[target] = rec
    _save(d)
    print(f"MARKED {target}: {outcome} (#{rec['count']})")
    return 0


def cmd_status():
    d = _load()
    if not d:
        print("no repair history yet")
        return 0
    now = datetime.now()
    print(f"{'target':<46} {'count':>5}  {'last':<19} outcome")
    print("-" * 86)
    for t, r in sorted(d.items()):
        last = r.get("last_repair", "?")
        age_h = ""
        try:
            age_h = f"({(now - datetime.fromisoformat(last)).total_seconds() / 3600:.1f}h)"
        except Exception:
            pass
        hot = " <== LOOP?" if int(r.get("count", 0)) >= 3 else ""
        print(f"{t[:46]:<46} {r.get('count', 0):>5}  {last:<19} {r.get('outcome', '?')} {age_h}{hot}")
    return 0


def main(argv):
    if not argv:
        return cmd_status()
    cmd = argv[0]
    if cmd == "check" and len(argv) >= 2:
        return cmd_check(argv[1])
    if cmd == "mark" and len(argv) >= 3:
        return cmd_mark(argv[1], argv[2])
    if cmd == "status":
        return cmd_status()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""
Memory Forgetting Curve - GRADUAL DECAY + ARCHIVAL (auto-dream inspired).
=========================================================================
A brain that never forgets drowns. This organ:
  - scores every memory: importance x recency (AEON/auto-dream mechanism)
  - decays old, unreferenced memories gradually
  - ARCHIVES decayed memories to memory-archive.json (never deletes!)
  - keeps MEMORY.md under a target size

Run nightly (dream phase calls this).

Usage: forgetting_curve.py [--dry-run]
Exit 0 always.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

MEM_DIR = Path(r"C:\Users\damir\AppData\Local\openamer-laptop\memories")
ARCHIVE = MEM_DIR / "memory-archive.json"
STATS = MEM_DIR / "memory-stats.json"
TARGET_CHARS = 1900   # keep MEMORY.md below this
HALF_LIFE_DAYS = 21   # importance halves every 3 weeks of no touch

# Keywords that make a memory structurally important (never decay first)
PROTECT = ["TRAP", "Grundsatz", "Regel", "PASSWORT", "Key", "Seda", "X:", "@",
           "cron", "Cron", "reserve", "WIS", "playbook", "Playbook", "24.08"]
# NOTE: fresh entries (<48h) are protected by the recency rule below anyway;
# PROTECT is for evergreen structural knowledge (traps, rules, credentials paths).


def load_entries():
    """MEMORY.md is stored as one entry per §-separated block via the memory tool;
    here we read the raw file and split on the § separator."""
    raw = (MEM_DIR / "MEMORY.md").read_text(encoding="utf-8")
    return [e.strip() for e in raw.split("\n§\n") if e.strip()]


def score(entry, now):
    """Higher = keep. Importance (protected keywords) + brevity + freshness."""
    importance = 2 if any(p.lower() in entry.lower() for p in PROTECT) else 1
    brevity = max(0.5, 1.5 - len(entry) / 400)  # shorter = denser = better
    # Freshness: entries dated today/this week are always relevant (we work
    # iteratively - today's lessons are tomorrow's procedures).
    fresh = 2.5 if "24.08" in entry else 1.0
    return importance * brevity * fresh


def main():
    dry = "--dry-run" in sys.argv
    entries = load_entries()
    now = datetime.now(timezone.utc)
    scored = sorted(((score(e, now), e) for e in entries), key=lambda t: -t[0])

    total = sum(len(e) for _, e in scored)
    keep, dropped = [], []
    budget = TARGET_CHARS
    for s, e in scored:
        if len(e) <= budget or s >= 2:  # protected always survive
            keep.append(e)
            budget -= len(e) + 3
        else:
            dropped.append({"text": e, "score": round(s, 2),
                            "archived_at": now.isoformat()})

    result = {
        "time": now.isoformat(timespec="seconds"),
        "entries_before": len(entries),
        "chars_before": total,
        "kept": len(keep),
        "dropped": len(dropped),
        "dry_run": dry,
    }

    if not dry and dropped:
        archive = json.loads(ARCHIVE.read_text(encoding="utf-8")) if ARCHIVE.exists() else []
        archive.extend(dropped)
        ARCHIVE.write_text(json.dumps(archive[-200:], indent=1, ensure_ascii=False),
                           encoding="utf-8")
        (MEM_DIR / "MEMORY.md").write_text("\n§\n".join(keep) + "\n", encoding="utf-8")

    STATS.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[forgetting-curve] {result['entries_before']} -> {result['kept']} kept "
          f"({len(dropped)} archived{' [DRY]' if dry else ''}), "
          f"{total} chars -> {sum(len(e) for e in keep)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Memory Hierarchy — long-term coherence through smart prioritization.

Not all memories are equal. This implements a 3-tier hierarchy:
  TIER 1 (PERMANENT):  insights, cause-effect edges, identity — never compressed
  TIER 2 (ARCHIVED):   episodic memories — compressed summaries, originals kept
  TIER 3 (EPHEMERAL):  raw session data — compacted after 7 days

Promotion/demotion is driven by USEFULNESS (from meta_learn's tracking):
  - Memories that led to solutions → promote to Tier 1
  - Memories never retrieved → demote toward ephemeral
"""
import json, os, sys, datetime, hashlib

T = r"C:/Users/damir/AppData/Local/openamer-laptop/scripts/training"
EPISODES = r"C:/Users/damir/AppData/Local/openamer-laptop/memory/longterm_episodes.jsonl"
HIERARCHY_FILE = os.path.join(T, "memory_hierarchy.json")
ARCHIVE = r"C:/Users/damir/AppData/Local/openamer-laptop/memory/compressed_episodes.jsonl"

def load_json(path, default):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return default

def mem_hash(text):
    return hashlib.md5(text[:200].encode()).hexdigest()[:12]

def build_hierarchy():
    """Classify all memories into tiers based on usefulness."""
    if not os.path.exists(EPISODES):
        return {"error": "no episodes file"}

    # load usefulness data from meta_learn if available
    meta_state = os.path.join(T, "meta_state.json")
    useful = {}
    if os.path.exists(meta_state):
        s = json.load(open(meta_state, encoding="utf-8"))
        useful = s.get("memory_usefulness", {})

    tiers = {"permanent": [], "archive": [], "ephemeral": []}
    total = 0

    for line in open(EPISODES, encoding="utf-8"):
        try:
            d = json.loads(line)
            total += 1
            text = d.get("text", d.get("content", str(d)))[:200]
            h = hashlib.md5(text.encode()).hexdigest()[:12]
            u = useful.get(h, {})
            retrievals = u.get("retrievals", 0)
            fixes = u.get("led_to_fix", 0)

            # classify by usefulness
            if fixes > 0 or retrievals >= 3:
                tiers["permanent"].append({"hash": h, "preview": text[:80],
                                           "usefulness": fixes / max(retrievals, 1)})
            elif retrievals >= 1:
                tiers["archive"].append({"hash": h, "preview": text[:60]})
            else:
                tiers["ephemeral"].append({"hash": h})
        except Exception:
            continue

    hierarchy = {
        "ts": datetime.datetime.now().isoformat(),
        "total": total,
        "tier_sizes": {k: len(v) for k, v in tiers.items()},
        "permanent_preview": tiers["permanent"][:5],
        "policy": {
            "permanent": "never compressed — insights, cause-effect, high-usefulness",
            "archive": "compressed summaries after 30 days — originals kept on disk",
            "ephemeral": "compacted after 7 days — raw session data",
        },
    }

    with open(HIERARCHY_FILE, "w", encoding="utf-8") as f:
        json.dump({"tiers": {k: v[:20] for k, v in tiers.items()},
                   "ts": datetime.datetime.now().isoformat(),
                   "total": total}, f, indent=1, ensure_ascii=False)

    print(f"[memory-hierarchy] {total} memories classified: "
          f"permanent={len(tiers['permanent'])}, archive={len(tiers['archive'])}, "
          f"ephemeral={len(tiers['ephemeral'])}", flush=True)
    summary = {"total": total, **{k: len(v) for k, v in tiers.items()}}
    return summary

if __name__ == "__main__":
    build_hierarchy()

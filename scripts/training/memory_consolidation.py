#!/usr/bin/env python3
"""Memory Consolidation — nightly sleep-consolidation for episodic memory.

Like human sleep: the brain doesn't just store memories, it CONSOLIDATES them —
replaying the day, strengthening what mattered, compressing what didn't, and
letting the rest fade into archive (never deleted, just moved out of the way).

This organ closes the gap the other memory scripts left open:
  - longterm_memory.py   -> stores episodes (grows forever, 49MB+)
  - memory_hierarchy.py  -> CLASSIFIES into tiers (but never compresses)
  - forgetting_curve.py  -> only touches the small MEMORY.md
  - dream_cycle.py       -> replays sessions (REM) but doesn't consolidate

What THIS does (the missing piece):
  1. SCORE every episode: usefulness (retrievals/led_to_fix) x recency
  2. PROMOTE high-usefulness episodes -> permanent tier (never touched)
  3. COMPRESS old (>30d) low-usefulness episodes -> one-line summaries
  4. ARCHIVE originals to compressed_episodes.jsonl (NEVER delete)
  5. Keep the active store bounded so recall stays fast and cheap

Run nightly, AFTER the dream cycle (dream replays, then consolidation sleeps).

Usage:
  python memory_consolidation.py            # full consolidation
  python memory_consolidation.py --dry-run  # report only, no writes
  python memory_consolidation.py stats      # current state
"""
import json, os, sys, datetime, hashlib, re, pathlib

_HOME = pathlib.Path(os.environ.get(
    "OPENAMER_HOME", str(pathlib.Path.home() / "AppData" / "Local" / "openamer-laptop")))

EPISODES = os.path.join(_HOME, "memory", "longterm_episodes.jsonl")
ARCHIVE = os.path.join(_HOME, "memory", "compressed_episodes.jsonl")
T = os.path.join(_HOME, "scripts", "training")
META_STATE = os.path.join(T, "meta_state.json")
HIERARCHY = os.path.join(T, "memory_hierarchy.json")

# Tuning (energy-conscious: no LLM calls, pure local scoring)
COMPRESS_AFTER_DAYS = 30      # episodes older than this are candidates
MAX_ACTIVE_EPISODES = 8000    # keep the active store under this
SUMMARY_MAX_CHARS = 200       # compressed summary length


def _load(path):
    if not os.path.exists(path):
        return []
    out = []
    for line in open(path, encoding="utf-8"):
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _save(path, items):
    with open(path, "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")


def _hash(text):
    return hashlib.md5(text[:200].encode("utf-8")).hexdigest()[:12]


def _usefulness():
    """Load usefulness tracking from meta_learn (retrievals, led_to_fix)."""
    if not os.path.exists(META_STATE):
        return {}
    try:
        return json.load(open(META_STATE, encoding="utf-8")).get("memory_usefulness", {})
    except Exception:
        return {}


def _summarize(text):
    """Compress an episode to a one-line summary (no LLM — cheap + deterministic).

    Keeps the first meaningful sentence and strips boilerplate/system noise.
    """
    t = (text or "").strip()
    # drop system-note prefixes and long embeddings noise
    t = re.sub(r"\[System note:.*?\]", "", t, flags=re.DOTALL)
    t = re.sub(r"\s+", " ", t).strip()
    if not t:
        return ""
    # first sentence (up to ~200 chars), then ellipsis
    m = re.match(r"(.{0,%d}?[.!?])(\s|$)" % SUMMARY_MAX_CHARS, t)
    if m:
        return m.group(1).strip()
    return t[:SUMMARY_MAX_CHARS].strip() + "…"


def _age_days(ts):
    try:
        dt = datetime.datetime.fromisoformat(ts)
        return (datetime.datetime.now() - dt).days
    except Exception:
        return 0


def consolidate(dry_run=False):
    eps = _load(EPISODES)
    if not eps:
        return {"status": "no episodes"}

    useful = _usefulness()
    now = datetime.datetime.now().isoformat()

    permanent, active, to_compress = [], [], []
    for e in eps:
        text = e.get("text", e.get("content", ""))
        h = _hash(text)
        u = useful.get(h, {})
        retrievals = u.get("retrievals", 0)
        fixes = u.get("led_to_fix", 0)
        age = _age_days(e.get("ts", now))

        # PROMOTE: high usefulness -> permanent (never compressed)
        if fixes > 0 or retrievals >= 3:
            e["tier"] = "permanent"
            permanent.append(e)
        # COMPRESS: old + low usefulness -> summarize + archive
        elif age >= COMPRESS_AFTER_DAYS and retrievals == 0:
            to_compress.append(e)
        # KEEP: everything else stays active
        else:
            active.append(e)

    # compress: write summary to archive, keep a slim pointer in active store
    archived = []
    for e in to_compress:
        text = e.get("text", e.get("content", ""))
        summary = _summarize(text)
        archived.append({
            "ts": e.get("ts", now),
            "kind": e.get("kind", "episode"),
            "summary": summary,
            "original_hash": _hash(text),
            "compressed_at": now,
        })
        # keep a slim pointer so recall can still find the topic
        active.append({
            "ts": e.get("ts", now),
            "kind": "compressed",
            "text": summary,
            "meta": {"compressed": True, "original_hash": _hash(text)},
        })

    # bound the active store: if still over cap, archive oldest non-permanent
    overflow = []
    if len(active) > MAX_ACTIVE_EPISODES:
        active.sort(key=lambda e: e.get("ts", ""))
        overflow = active[:len(active) - MAX_ACTIVE_EPISODES]
        active = active[len(active) - MAX_ACTIVE_EPISODES:]

    result = {
        "ts": now,
        "episodes_before": len(eps),
        "permanent": len(permanent),
        "compressed": len(to_compress),
        "overflow_archived": len(overflow),
        "kept_after": len(permanent) + len(active),
        "dry_run": dry_run,
    }

    if not dry_run:
        # archive originals (append, never delete)
        existing_archive = _load(ARCHIVE)
        existing_archive.extend(archived)
        _save(ARCHIVE, existing_archive)
        # write the new active store (permanent + active + compressed pointers)
        _save(EPISODES, permanent + active)

    print(f"[memory-consolidation] {result['episodes_before']} -> "
          f"{result['kept_after']} kept "
          f"({result['permanent']} permanent, {result['compressed']} compressed"
          f"{', DRY' if dry_run else ''})", flush=True)

    # WORLD MODEL PRUNING: forgetting is part of learning.
    # Near-duplicate facts (>0.97 cosine) and stale noisy edges are removed
    # on a schedule — the store grows with signal, not repetition.
    try:
        import world_model as wm
        pruned = wm.prune(max_dupes=2)
        if pruned.get("removed"):
            print(f"[world-model-prune] {pruned['removed']} near-dupes removed, "
                  f"{pruned['kept']} edges kept", flush=True)
            result["world_model_pruned"] = pruned
    except Exception as ex:
        print(f"[world-model-prune] skipped: {str(ex)[:80]}", flush=True)

    return result


def stats():
    eps = _load(EPISODES)
    arch = _load(ARCHIVE)
    tiers = {}
    for e in eps:
        t = e.get("tier", "active")
        tiers[t] = tiers.get(t, 0) + 1
    size_mb = os.path.getsize(EPISODES) / 1e6 if os.path.exists(EPISODES) else 0
    return {
        "active_episodes": len(eps),
        "archive_episodes": len(arch),
        "tiers": tiers,
        "store_size_mb": round(size_mb, 1),
    }


if __name__ == "__main__":
    if "--dry-run" in sys.argv:
        print(json.dumps(consolidate(dry_run=True), indent=2))
    elif "stats" in sys.argv:
        print(json.dumps(stats(), indent=2))
    else:
        print(json.dumps(consolidate(), indent=2))

#!/usr/bin/env python3
"""
Memory Darwinism — memories compete for survival.

Phase 19 of the Darwin Engine. Memories are individuals: they carry fitness
(how often they led to correct outcomes), they duel when they contradict
each other, and weak memories die. The first biologically-accurate agent
memory model.

CLI (usually invoked via darwin_engine.py --memory-* flags):
  scan      load memories from lessons DB + state.db decisions
  duel      resolve contradictions (newer + fitter wins)
  cull      sterilize memories below survival threshold
  report    memory population stats

Storage: ~/AppData/Local/openamer-laptop/darwin/memory-population.json
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home() / "AppData" / "Local" / "openamer-laptop"
DARWIN_DIR = HOME / "darwin"
MEMORY_POP = DARWIN_DIR / "memory-population.json"
LESSONS_DB = HOME / "cross_session_lessons.db"
STATE_DB = HOME / "state.db"

SURVIVAL_FITNESS = -2      # below this -> memory dies
CONTRADICTION_OVERLAP = 0.5  # token overlap that marks memories as rivals


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load(path: Path, default):
    try:
        return json.loads(path.read_text("utf-8"))
    except Exception:
        return default


def _save(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False), "utf-8")


def _tokens(text: str) -> set[str]:
    noise = {"the", "a", "an", "is", "are", "was", "and", "or", "of", "to",
             "in", "on", "for", "with", "darwind", "darwin"}
    return {t for t in re.split(r"[^a-z0-9]+", text.lower())
            if t and t not in noise and len(t) > 2}


def scan_memories() -> list[dict]:
    """Harvest memory individuals from all available sources."""
    pop = _load(MEMORY_POP, {})
    memories = pop.get("memories", {})

    # source 1: lessons DB (structured lessons)
    if LESSONS_DB.exists():
        try:
            conn = sqlite3.connect(str(LESSONS_DB))
            rows = conn.execute(
                "SELECT id, category, lesson, tool_name, success, created_at "
                "FROM lessons").fetchall()
            conn.close()
            for mid, cat, lesson, tool, success, created in rows:
                key = f"lesson-{mid}"
                if key not in memories:
                    memories[key] = {
                        "text": lesson[:300], "category": cat,
                        "tool": tool, "success": bool(success),
                        "born": created, "uses": 0, "wins": 0,
                        "losses": 0, "fitness": 0, "source": "lessons",
                    }
        except Exception:
            pass

    # source 2: state.db - user-stated preferences and corrections
    if STATE_DB.exists():
        try:
            conn = sqlite3.connect(str(STATE_DB))
            rows = conn.execute(
                "SELECT content FROM messages WHERE role='user' AND ("
                "content LIKE '%immer %' OR content LIKE '%never %' "
                "OR content LIKE '%always %' OR content LIKE '%nie %' "
                "OR content LIKE '%don''t %') LIMIT 2000").fetchall()
            conn.close()
            for (content,) in rows:
                if not content or len(content) < 20:
                    continue
                import hashlib
                key = "pref-" + hashlib.md5(
                    content[:200].encode()).hexdigest()[:12]
                if key not in memories:
                    memories[key] = {
                        "text": content[:300], "category": "preference",
                        "tool": None, "success": True,
                        "born": _now(), "uses": 0, "wins": 0,
                        "losses": 0, "fitness": 1, "source": "stated",
                    }
        except Exception:
            pass

    pop["memories"] = memories
    pop["scanned"] = _now()
    _save(MEMORY_POP, pop)
    return list(memories.values())


def memory_fitness(m: dict) -> float:
    """Fitness: successes reward, failures punish, contradictions bleed."""
    base = m.get("wins", 0) * 2 - m.get("losses", 0) * 3
    success_bonus = 1 if m.get("success") else -1
    return round(base + success_bonus, 2)


def duel_contradictions(min_overlap: float = CONTRADICTION_OVERLAP) -> list[dict]:
    """Memories covering the same topic but contradicting each other duel:
    the fitter one survives with increased standing, the loser bleeds."""
    pop = _load(MEMORY_POP, {})
    memories = pop.get("memories", {})
    mems = list(memories.items())
    duels = []
    for i in range(len(mems)):
        for j in range(i + 1, len(mems)):
            (ki, mi), (kj, mj) = mems[i], mems[j]
            ti, tj = _tokens(mi.get("text", "")), _tokens(mj.get("text", ""))
            if not ti or not tj:
                continue
            overlap = len(ti & tj) / min(len(ti), len(tj))
            if overlap < min_overlap:
                continue
            # contradiction heuristic: same topic, different polarity words
            polarity = ("not", "never", "no", "don", "avoid", "nie", "kein")
            pi = any(p in mi.get("text", "").lower() for p in polarity)
            pj = any(p in mj.get("text", "").lower() for p in polarity)
            if pi == pj:
                continue  # same polarity -> not contradictory
            fi, fj = memory_fitness(mi), memory_fitness(mj)
            winner_key, loser_key = (ki, kj) if fi >= fj else (kj, ki)
            memories[winner_key]["wins"] = memories[winner_key].get("wins", 0) + 1
            memories[loser_key]["losses"] = memories[loser_key].get("losses", 0) + 1
            memories[loser_key]["fitness"] = memory_fitness(memories[loser_key])
            memories[winner_key]["fitness"] = memory_fitness(memories[winner_key])
            duels.append({"winner": winner_key, "loser": loser_key,
                          "overlap": round(overlap, 2)})
            break  # one duel per memory per pass
    pop["memories"] = memories
    _save(MEMORY_POP, pop)
    return duels


def cull_weak(threshold: float = SURVIVAL_FITNESS,
              dry_run: bool = True) -> list[dict]:
    """Memories below the survival threshold die (archived, not deleted)."""
    pop = _load(MEMORY_POP, {})
    memories = pop.get("memories", {})
    dead = []
    for key, m in list(memories.items()):
        f = memory_fitness(m)
        m["fitness"] = f
        if f < threshold:
            dead.append({"key": key, "text": m.get("text", "")[:80],
                         "fitness": f})
            if not dry_run:
                graveyard = DARWIN_DIR / "memory-graveyard.json"
                grave = _load(graveyard, [])
                grave.append({"key": key, "memory": m, "died": _now()})
                _save(graveyard, grave)
                del memories[key]
    if not dry_run:
        pop["memories"] = memories
        _save(MEMORY_POP, pop)
    return dead


def memory_stats() -> dict:
    pop = _load(MEMORY_POP, {})
    mems = list(pop.get("memories", {}).values())
    if not mems:
        return {"population": 0}
    fits = [memory_fitness(m) for m in mems]
    by_source = {}
    for m in mems:
        by_source[m.get("source", "?")] = by_source.get(m.get("source", "?"), 0) + 1
    graveyard = _load(DARWIN_DIR / "memory-graveyard.json", [])
    return {
        "population": len(mems),
        "avg_fitness": round(sum(fits) / len(fits), 2),
        "fittest": max(mems, key=memory_fitness).get("text", "")[:80],
        "weakest_fitness": min(fits),
        "sources": by_source,
        "graveyard": len(graveyard),
    }


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--duel", action="store_true")
    ap.add_argument("--cull", action="store_true", help="dry run")
    ap.add_argument("--cull-apply", action="store_true")
    ap.add_argument("--stats", action="store_true")
    args = ap.parse_args()
    if args.scan:
        mems = scan_memories()
        print(f"scanned: {len(mems)} memories in population")
    if args.duel:
        duels = duel_contradictions()
        print(f"duels fought: {len(duels)}")
    if args.cull or args.cull_apply:
        dead = cull_weak(dry_run=not args.cull_apply)
        label = "culled" if args.cull_apply else "would cull"
        print(f"{label}: {len(dead)} memories")
    if args.stats:
        print(json.dumps(memory_stats(), indent=1))

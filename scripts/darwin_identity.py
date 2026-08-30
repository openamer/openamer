#!/usr/bin/env python3
"""
Organism Identity (Phase 27) - every Darwin entity gets a human identity:
a real name, a face (facial parameters), a personality, a mood, a biography.

Deterministic per entity-id: the same skill always gets the same identity.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOME = Path.home() / "AppData" / "Local" / "openamer-laptop"
IDENTITY_FILE = HOME / "darwin" / "identities.json"

FIRST_NAMES = [
    "Aria", "Boris", "Cleo", "Dax", "Elsa", "Finn", "Gaia", "Hugo", "Iris",
    "Juno", "Kai", "Luna", "Milo", "Nora", "Otis", "Pia", "Quinn", "Rex",
    "Sage", "Tara", "Ugo", "Vera", "Wren", "Xeno", "Yara", "Zeno",
    "Ada", "Bruno", "Cora", "Dante", "Eda", "Felix", "Greta", "Hank",
    "Ines", "Jasper", "Kira", "Leon", "Mara", "Nico", "Opal", "Pax",
]
EPITHETS = [
    "the Builder", "the Curious", "the Silent", "the Bold", "the Wise",
    "the Swift", "the Steady", "the Spark", "the Watcher", "the Hunter",
    "the Gardener", "the Ancient", "the Young", "the Kind", "the Fierce",
    "the Patient", "the Bright", "the Deep", "the Loyal", "the Free",
    "the Architect", "the Healer", "the Judge", "the Jester", "the Sage",
]
MOODS = {
    "thriving": {"face": "happy", "color": "#7ee787", "emoji": "😄"},
    "healthy": {"face": "content", "color": "#79c0ff", "emoji": "🙂"},
    "hungry": {"face": "worried", "color": "#f0883e", "emoji": "😟"},
    "hurt": {"face": "sad", "color": "#f85149", "emoji": "😢"},
    "dying": {"face": "grave", "color": "#8b949e", "emoji": "💀"},
    "newborn": {"face": "curious", "color": "#d2a8ff", "emoji": "👶"},
}
PERSONALITY_TRAITS = [
    "analytical", "brave", "cautious", "curious", "disciplined", "energetic",
    "friendly", "independent", "patient", "playful", "protective", "stubborn",
]


def _hash(entity_id: str) -> int:
    return int(hashlib.md5(entity_id.encode()).hexdigest(), 16)


def identity_for(entity_id: str, kind: str = "skill",
                 fitness: float = 0, energy: float = 50,
                 age_days: int = 0, wins: int = 0, losses: int = 0) -> dict:
    """Deterministic human identity for any Darwin entity."""
    h = _hash(entity_id)
    first = FIRST_NAMES[h % len(FIRST_NAMES)]
    epithet = EPITHETS[(h // 7) % len(EPITHETS)]
    name = f"{first} {epithet}"
    # mood from lifecycle state
    if age_days <= 0:
        mood_key = "newborn"
    elif energy < 5:
        mood_key = "dying"
    elif energy < 15:
        mood_key = "hungry"
    elif losses > wins * 2 and losses >= 2:
        mood_key = "hurt"
    elif fitness >= 25:
        mood_key = "thriving"
    else:
        mood_key = "healthy"
    mood = MOODS[mood_key]
    # personality: 3 traits from hash
    trait_pool = list(PERSONALITY_TRAITS)
    traits = []
    for _ in range(3):
        t = trait_pool.pop((h := _hash(entity_id + str(len(traits)))) % len(trait_pool))
        traits.append(t)
    # face parameters (3D rendering)
    face = {
        "eye_size": 0.8 + (h % 5) * 0.08,
        "eye_spacing": 0.35 + (h % 4) * 0.05,
        "mouth_curve": _mouth_curve(mood_key),
        "head_hue": h % 360,
        "body_hue": (h // 3) % 360,
        "scale": 0.85 + (h % 6) * 0.05,
    }
    bio = _bio(entity_id, kind, name, fitness, age_days, wins, losses, traits)
    return {
        "entity_id": entity_id, "kind": kind, "name": name,
        "first_name": first, "epithet": epithet,
        "mood": mood_key, "emoji": mood["emoji"], "color": mood["color"],
        "face": mood["face"], "face_params": face,
        "personality": traits, "bio": bio,
    }


def _mouth_curve(mood: str) -> float:
    return {"happy": .8, "content": .4, "curious": .2, "worried": -.3,
            "sad": -.7, "grave": -.2}.get(mood, 0)


def _bio(entity_id, kind, name, fitness, age_days, wins, losses, traits) -> str:
    age = f"{age_days} days" if age_days == 1 else f"{age_days} days"
    record = f"{wins} victories, {losses} defeats"
    if kind == "worker":
        role = "swarm agent"
    elif kind == "species":
        role = "newly-born species"
    else:
        role = "skill organism"
    t1, t2, t3 = (traits + ["mysterious"])[:3]
    if fitness >= 25:
        feel = "a pillar of the ecosystem"
    elif fitness >= 10:
        feel = "finding its place"
    elif fitness <= 0:
        feel = "struggling to survive"
    else:
        feel = "growing steadily"
    return (f"{name}, {role}. {age} old, {record}. "
            f"{t1.capitalize()} and {t2}, known for being {t3}. "
            f"Currently {feel}.")


def identities_batch(entities: list[dict]) -> list[dict]:
    """Attach identities to a list of world organisms."""
    out = []
    store = _load(IDENTITY_FILE, {})
    changed = False
    for o in entities:
        eid = o["id"]
        ident = store.get(eid)
        if not ident:
            ident = identity_for(
                eid, kind=o.get("type", "skill"),
                fitness=o.get("fitness", 0),
                energy=o.get("energy", 50),
                age_days=o.get("age_days", 0),
                wins=o.get("wins", 0), losses=o.get("losses", 0))
            store[eid] = ident
            changed = True
        out.append({**o, "identity": ident})
    if changed:
        _save(IDENTITY_FILE, store)
    return out


def _save(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False), "utf-8")


def _load(path: Path, default):
    try:
        return json.loads(path.read_text("utf-8"))
    except Exception:
        return default


if __name__ == "__main__":
    # demo: identity for a few ids
    for eid in ("self-rewriter", "alpha-worker", "git-credentials"):
        ident = identity_for(eid, "skill", fitness=30, age_days=6)
        print(f"{eid} -> {ident['name']} {ident['emoji']} "
              f"[{', '.join(ident['personality'])}]")

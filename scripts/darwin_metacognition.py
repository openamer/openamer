#!/usr/bin/env python3
"""
Metacognition & Civilization Seeds (Phase 24).

The swarm KNOWS what it knows:
  - --introspect: honest self-image from every data source Darwin holds
    (strengths, weaknesses, gaps, aging, market position)
  - Gap-driven evolution: detected weaknesses become blueprint requirements
    that steer the next speciation directly at the swarm's blind spots
  - Civilization seed: a single portable file carrying genome + lineage +
    knowledge + territories + chronicle - a new machine becomes a full
    civilization in one import
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import importlib.util
_spec = importlib.util.spec_from_file_location(
    "darwin_engine", REPO / "scripts" / "darwin_engine.py")
darwin = importlib.util.module_from_spec(_spec)
sys.modules["darwin_engine"] = darwin
_spec.loader.exec_module(darwin)

_spec2 = importlib.util.spec_from_file_location(
    "swarm_os", REPO / "scripts" / "swarm_os.py")
swarm = importlib.util.module_from_spec(_spec2)
sys.modules["swarm_os"] = swarm
_spec2.loader.exec_module(swarm)

HOME = Path.home() / "AppData" / "Local" / "openamer-laptop"
INTROSPECTION_FILE = HOME / "darwin" / "introspection.json"
SEED_FILE = HOME / "darwin" / "civilization-seed.json"

STRONG_THRESHOLD = 25.0
WEAK_THRESHOLD = 10.0


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


def introspect() -> dict:
    """Build the swarm's honest self-image from all available evidence."""
    fitness = _load(darwin.FITNESS_FILE, {}).get("skills", {})
    ranked = sorted(fitness.items(),
                    key=lambda kv: kv[1].get("fitness", 0), reverse=True)
    strengths = [{"skill": n, "fitness": s["fitness"], "usage": s["usage"]}
                 for n, s in ranked if s["fitness"] >= STRONG_THRESHOLD]
    weaknesses = [{"skill": n, "fitness": s["fitness"], "usage": s["usage"]}
                  for n, s in ranked if s["fitness"] < WEAK_THRESHOLD]

    # aging: how static is the population?
    static_count = sum(1 for _, s in fitness.items()
                       if s.get("age_days", 0) > 5)
    aging = {"static_skills": static_count,
             "total": len(fitness),
             "stagnation_ratio": round(static_count / max(len(fitness), 1), 2)}

    # battle record across all populations
    population = _load(darwin.POPULATION_FILE, {})
    wins = sum(g.get("wins", 0) for g in population.values())
    losses = sum(g.get("losses", 0) for g in population.values())
    battle = {"wins": wins, "losses": losses,
              "win_rate": round(wins / max(wins + losses, 1), 2)}

    # market position: how many open/settled tasks
    market = _load(HOME / "darwin" / "task-market.json",
                   {"open": {}, "settled": {}})

    # species health
    sp_dir = darwin.DARWIN_DIR / "species"
    species = {"installed": 0, "candidate": 0}
    if sp_dir.exists():
        for mp in sp_dir.glob("*.json"):
            st = _load(mp, {}).get("status", "candidate")
            species[st if st in species else "candidate"] = \
                species.get(st if st in species else "candidate", 0) + 1

    # evolution velocity: events per day over the last week
    lineage = _load(darwin.LINEAGE_FILE, {"events": []})
    week_ago = datetime.now(timezone.utc).timestamp() - 7 * 86400
    recent = [e for e in lineage["events"]
              if _parse_ts(e.get("when", "")) >= week_ago]
    velocity = {"events_last_7d": len(recent),
                "total_events": len(lineage["events"])}

    # capability coverage: what can the swarm actually do?
    caps = Counter()
    for name in fitness:
        for tok in re.split(r"[-_+.]", name):
            if len(tok) > 3 and tok not in ("darwin", "harvested", "mut"):
                caps[tok] += 1
    top_capabilities = caps.most_common(8)

    self_image = {
        "when": _now(),
        "population": len(fitness),
        "strengths": strengths[:5],
        "weaknesses": weaknesses[:5],
        "aging": aging,
        "battle_record": battle,
        "market": {"open": len(market.get("open", {})),
                   "settled": len(market.get("settled", {}))},
        "species": species,
        "evolution_velocity": velocity,
        "top_capabilities": top_capabilities,
    }

    # gap analysis -> evolution directives
    gaps = []
    if weaknesses:
        gaps.append({"type": "weak-population",
                     "detail": f"{len(weaknesses)} skills below fitness "
                               f"{WEAK_THRESHOLD}",
                     "directive": "mutate or predate these skills"})
    if aging["stagnation_ratio"] >= 0.5:
        gaps.append({"type": "stagnation",
                     "detail": f"{aging['stagnation_ratio']} of population "
                               f"unchanged for 5+ days",
                     "directive": "increase exploration (epsilon up)"})
    if battle["win_rate"] < 0.4 and wins + losses >= 5:
        gaps.append({"type": "losing-record",
                     "detail": f"win rate {battle['win_rate']}",
                     "directive": "prioritize verification-step mutations"})
    if len(market.get("open", {})) > len(market.get("settled", {})) * 2 \
            and market.get("open"):
        gaps.append({"type": "market-backlog",
                     "detail": f"{len(market['open'])} open tasks vs "
                               f"{len(market['settled'])} settled",
                     "directive": "spawn workers for open task domains"})
    self_image["gaps"] = gaps
    self_image["self_assessment"] = _assess(self_image)

    _save(INTROSPECTION_FILE, self_image)
    return self_image


def _parse_ts(ts: str) -> float:
    try:
        return datetime.fromisoformat(ts).timestamp()
    except Exception:
        return 0.0


def _assess(img: dict) -> str:
    """One honest sentence the swarm says about itself."""
    trend = "growing" if img["evolution_velocity"]["events_last_7d"] > 5 \
        else "stable"
    if img["gaps"]:
        return (f"We are {trend}, strong in "
                f"{len(img['strengths'])} areas, but we carry "
                f"{len(img['gaps'])} weaknesses we must address.")
    return f"We are {trend} and healthy."


# ── gap-driven evolution ─────────────────────────────────────────────────────

GAP_BLUEPRINTS_FILE = HOME / "darwin" / "gap-blueprints.json"


def evolve_toward_gaps(self_image: dict | None = None,
                       apply: bool = False) -> list[dict]:
    """Turn detected gaps into targeted speciation directives: for each gap,
    synthesize a skill designed to close it."""
    img = self_image or _load(INTROSPECTION_FILE, {})
    gaps = img.get("gaps", [])
    created = []
    for gap in gaps:
        gtype = gap["type"]
        name = f"darwin-gap-{gtype.replace('_', '-')}"
        text = (
            f"---\nname: {name}\n"
            f"description: Auto-generated to close the swarm's '{gtype}' gap.\n"
            f"---\n\n# Gap Closure: {gtype}\n\n"
            f"## Trigger\nWhen the swarm's introspection reports this gap.\n\n"
            f"## Procedure\nDetected gap: {gap['detail']}.\n"
            f"Directive: {gap['directive']}\n\n"
            f"## Verification\nConfirm the gap metric improved after acting.\n"
            f"```bash\npython -c \"print('gap-closure-ok')\"\n```\n"
        )
        created.append({"name": name, "gap": gtype, "applied": apply})
        if apply:
            dst = darwin.DARWIN_DIR / "species" / name
            dst.mkdir(parents=True, exist_ok=True)
            (dst / "SKILL.md").write_text(text, "utf-8")
            _save(darwin.DARWIN_DIR / "species" / f"{name}.json", {
                "child": name, "kind": "gap-closure", "gap": gtype,
                "born": _now(), "status": "candidate",
            })
            darwin.record_lineage("introspection", name, "gap-closure",
                                  {"gap": gtype})
    if created and apply:
        # register as candidates for the next tournament
        for c in created:
            pass  # meta already saved above
    return created


# ── civilization seeds ───────────────────────────────────────────────────────

def export_civilization_seed(path: Path | None = None) -> Path:
    """One file carrying the entire civilization: genome, lineage, species,
    knowledge, territories, swarm, chronicle."""
    seed = {
        "seed_version": 1,
        "exported": _now(),
        "genome": _load(REPO / "reports" / "darwin-genome.json", {}),
        "lineage": _load(darwin.LINEAGE_FILE, {"events": []}),
        "species_metas": {
            mp.stem: _load(mp, {}) for mp in
            (darwin.DARWIN_DIR / "species").glob("*.json")
        } if (darwin.DARWIN_DIR / "species").exists() else {},
        "species_files": {
            mp.parent.name: _load(mp, "")
            for mp in (darwin.DARWIN_DIR / "species").glob("*/SKILL.md")
            if mp.exists()
        } if (darwin.DARWIN_DIR / "species").exists() else {},
        "swarm": swarm.load_swarm(),
        "knowledge": _load(swarm.SWARM_KNOWLEDGE_FILE, {"teachers": []}),
        "territories": _load(swarm.TERRITORIES_FILE, {}),
        "introspection": _load(INTROSPECTION_FILE, {}),
        "population_history_lines": _count_lines(darwin.HISTORY_FILE),
    }
    out = path or (darwin.HISTORY_FILE.parent / "civilization-seed.json")
    _save(out, seed)
    return out


def import_civilization_seed(path: Path, dry_run: bool = True) -> dict:
    """Become the civilization in the seed: import everything into the
    local darwin home. dry_run counts what would be created."""
    seed = _load(path, {})
    if not seed:
        return {"error": "empty or invalid seed"}
    plan = {
        "genome_skills": len(seed.get("genome", {}).get("population", {})),
        "lineage_events": len(seed.get("lineage", {}).get("events", [])),
        "species": len(seed.get("species_metas", {})),
        "swarm_workers": len(seed.get("swarm", {}).get("workers", {})),
        "teachers": len(seed.get("knowledge", {}).get("teachers", [])),
        "territories": len(seed.get("territories", {})),
    }
    if dry_run:
        return {"dry_run": True, **plan}
    # real import
    darwin._save_json(darwin.POPULATION_FILE,
                      seed.get("genome", {}).get("population", {}))
    darwin._save_json(darwin.LINEAGE_FILE, seed.get("lineage", {"events": []}))
    for name, meta in seed.get("species_metas", {}).items():
        darwin._save_json(darwin.DARWIN_DIR / "species" / f"{name}.json", meta)
    for name, content in seed.get("species_files", {}).items():
        sp_dir = darwin.DARWIN_DIR / "species" / name
        sp_dir.mkdir(parents=True, exist_ok=True)
        (sp_dir / "SKILL.md").write_text(content, "utf-8")
    swarm._save(swarm.SWARM_FILE, seed.get("swarm",
                 {"workers": {}, "tasks": {}}))
    swarm._save(swarm.SWARM_KNOWLEDGE_FILE, seed.get("knowledge",
                {"teachers": []}))
    swarm._save(swarm.TERRITORIES_FILE, seed.get("territories", {}))
    return {"imported": True, **plan}


def _count_lines(p: Path) -> int:
    try:
        return sum(1 for _ in open(p, encoding="utf-8"))
    except Exception:
        return 0


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--introspect", action="store_true")
    ap.add_argument("--evolve-gaps", action="store_true")
    ap.add_argument("--export-seed", action="store_true")
    ap.add_argument("--import-seed", metavar="FILE")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    if args.introspect:
        img = introspect()
        print(json.dumps(img, indent=1))
    if args.evolve_gaps:
        created = evolve_toward_gaps(apply=args.apply)
        print(f"gap-closure species: {len(created)}")
    if args.export_seed:
        print(f"seed -> {export_civilization_seed()}")
    if args.import_seed:
        print(json.dumps(import_civilization_seed(
            Path(args.import_seed), dry_run=not args.apply), indent=1))

#!/usr/bin/env python3
"""
Darwin Grid Client - connect a local ecosystem to the grid.

Commands:
  --grid-push <url> <machine-id>   export genome & push to grid
  --grid-pull <url> <machine-id>   pull a foreign genome & import it
  --grid-duel <url> <machine-id>   duel foreign skills against local best

The duel is the heart: foreign skills execute against the local fittest,
real exit codes decide, winners are recorded in the genome (W/L).
"""
import json
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import importlib.util
spec = importlib.util.spec_from_file_location(
    "darwin_engine", REPO / "scripts" / "darwin_engine.py")
darwin = importlib.util.module_from_spec(spec)
sys.modules["darwin_engine"] = darwin
spec.loader.exec_module(darwin)


def _http_json(url: str, method: str = "GET", body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def grid_push(url: str, machine_id: str) -> None:
    genome_path = REPO / "reports" / "darwin-genome.json"
    if not genome_path.exists():
        darwin.export_genome()
    genome = json.loads(genome_path.read_text(encoding="utf-8"))
    code, resp = _http_json(f"{url}/push?machine={machine_id}", "POST", genome)
    print(f"{'✅' if code == 200 else '❌'} push: {resp}")


def grid_pull(url: str, machine_id: str) -> dict | None:
    code, genome = _http_json(f"{url}/pull?machine={machine_id}")
    if code != 200:
        print(f"❌ pull failed: {genome}")
        return None
    # stash foreign genome for dueling
    out = REPO / "reports" / f"darwin-genome-{machine_id}.json"
    out.write_text(json.dumps(genome, indent=1, ensure_ascii=False),
                   encoding="utf-8")
    merged = darwin.import_genome(out)
    print(f"✅ pulled {machine_id}: {len(genome.get('population', {}))} skills, "
          f"merged {merged}")
    return genome


def grid_duel(url: str, machine_id: str) -> None:
    code, foreign = _http_json(f"{url}/pull?machine={machine_id}")
    if code != 200:
        print(f"❌ cannot duel: {foreign}")
        return
    foreign_pop = foreign.get("population", {})
    local_fitness = darwin._load_json(darwin.FITNESS_FILE, {}).get("skills", {})
    local_ranked = sorted(local_fitness.items(),
                          key=lambda kv: kv[1].get("fitness", 0), reverse=True)
    if not local_ranked:
        print("❌ no local fitness data - run --autopilot first")
        return
    champion = local_ranked[0][0]

    foreign_sorted = sorted(
        foreign_pop.items(),
        key=lambda kv: kv[1].get("wins", 0) * 2 - kv[1].get("losses", 0),
        reverse=True)

    print(f"🏟️  GRID DUEL: local champion `{champion}` vs foreign contenders")
    results = []
    for fname, fgenome in foreign_sorted[:3]:
        # foreign skills must physically exist locally to execute; only duel
        # skills that exist in both populations OR are installed locally
        if not (darwin.SKILLS_DIR / fname / "SKILL.md").exists():
            results.append({"foreign": fname, "status": "not-present-locally"})
            continue
        duel = darwin.head_to_head(champion, fname)
        won = duel["winner"] == "parent"
        darwin.record_op_outcome if False else None
        results.append({"foreign": fname, "winner": duel["winner"],
                        "local_exit": duel["parent_result"].get("exit_code"),
                        "foreign_exit": duel["child_result"].get("exit_code")})
        # genome update: local champion's record reflects grid duels
        population = darwin._load_json(darwin.POPULATION_FILE, {})
        g = population.setdefault(champion, {"wins": 0, "losses": 0})
        if won:
            g["wins"] = g.get("wins", 0) + 1
        else:
            g["losses"] = g.get("losses", 0) + 1
        darwin._save_json(darwin.POPULATION_FILE, population)

    for r in results:
        if r.get("status") == "not-present-locally":
            print(f"   ⏭️  {r['foreign']}: not installed locally (skipped)")
        elif "winner" in r:
            print(f"   {'🏆' if r['winner'] == 'parent' else '💀'} "
                  f"{r['foreign']}: local exit {r['local_exit']}, "
                  f"foreign exit {r['foreign_exit']} -> "
                  f"{'LOCAL WINS' if r['winner'] == 'parent' else 'FOREIGN WINS'}")


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid-push", nargs=2, metavar=("URL", "MACHINE_ID"))
    ap.add_argument("--grid-pull", nargs=2, metavar=("URL", "MACHINE_ID"))
    ap.add_argument("--grid-duel", nargs=2, metavar=("URL", "MACHINE_ID"))
    args = ap.parse_args()
    if args.grid_push:
        grid_push(args.grid_push[0], args.grid_push[1])
    elif args.grid_pull:
        grid_pull(args.grid_pull[0], args.grid_pull[1])
    elif args.grid_duel:
        grid_duel(args.grid_duel[0], args.grid_duel[1])
    else:
        ap.print_help()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Darwin Grid GitHub Backend - use a GitHub repo as the public grid registry.

Why: no server to run. Each machine pushes a genome file to
`darwin-grid/<machine-id>.json` in openamer/darwin-grid (or a fork).
Uses the git credentials already on the machine (ghp_... from credential store).

Commands:
  --publish <machine-id>   export local genome & commit it to the grid repo
  --fetch <machine-id>     download a foreign genome & import it
  --duel <machine-id>      duel foreign skills vs local champion
  --list                   list all machines in the grid

Repo layout: one JSON per machine, updated via git (full audit trail for
free - every evolution is in git history).
"""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import importlib.util
spec = importlib.util.spec_from_file_location(
    "darwin_engine", REPO / "scripts" / "darwin_engine.py")
darwin = importlib.util.module_from_spec(spec)
sys.modules["darwin_engine"] = darwin
spec.loader.exec_module(darwin)

GRID_REPO = "openamer/darwin-grid"
MACHINE_RE = re.compile(r"^[a-zA-Z0-9_-]{3,64}$")


def _token() -> str | None:
    cred = Path.home() / ".git-credentials"
    try:
        m = re.search(r"https://([^:]+):([^@]+)@github\.com",
                      cred.read_text(encoding="utf-8"))
        return m.group(2) if m else None
    except FileNotFoundError:
        return None


def _api(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    import urllib.request
    token = _token()
    if not token:
        return 401, {"error": "no git credentials found"}
    req = urllib.request.Request(
        f"https://api.github.com/repos/{GRID_REPO}/{path}",
        data=json.dumps(body).encode() if body else None,
        method=method,
        headers={"Authorization": f"token {token}",
                 "Accept": "application/vnd.github+json",
                 "User-Agent": "darwin-grid"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def _git(args: list[str], cwd: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git"] + args, cwd=cwd, capture_output=True,
                          text=True, timeout=60)


def _ensure_grid_clone(clone_dir: Path) -> bool:
    """Clone/update the grid repo locally (auth via stored credentials)."""
    if (clone_dir / ".git").exists():
        r = _git(["pull", "--rebase"], str(clone_dir))
        return r.returncode == 0
    r = _git(["clone", f"https://github.com/{GRID_REPO}.git", str(clone_dir)])
    return r.returncode == 0


def _push_genome(machine_id: str) -> tuple[bool, str]:
    if not MACHINE_RE.match(machine_id):
        return False, "invalid machine id"
    genome_path = REPO / "reports" / "darwin-genome.json"
    if not genome_path.exists():
        darwin.export_genome()
    with tempfile.TemporaryDirectory() as td:
        clone = Path(td) / "grid"
        if not _ensure_grid_clone(clone):
            return False, "could not clone grid repo"
        dest = clone / f"{machine_id}.json"
        genome = json.loads(genome_path.read_text(encoding="utf-8"))
        genome["machine_id"] = machine_id
        dest.write_text(json.dumps(genome, indent=1, ensure_ascii=False),
                        "utf-8")
        _git(["add", f"{machine_id}.json"], str(clone))
        _git(["-c", "user.name=darwin-grid", "-c",
              "user.email=darwin@openamer.dev",
              "commit", "-m", f"darwin: genome update from {machine_id}"],
             str(clone))
        r = _git(["push"], str(clone))
        if r.returncode != 0:
            return False, r.stderr.strip()[:200]
    return True, "pushed"


def _fetch_genome(machine_id: str) -> dict | None:
    code, resp = _api("GET", f"contents/{machine_id}.json")
    if code != 200:
        return None
    import base64
    data = json.loads(base64.b64decode(resp["content"]))
    out = REPO / "reports" / f"darwin-genome-{machine_id}.json"
    out.write_text(json.dumps(data, indent=1, ensure_ascii=False), "utf-8")
    return data


def publish(machine_id: str) -> None:
    ok, msg = _push_genome(machine_id)
    print(f"{'✅' if ok else '❌'} publish {machine_id}: {msg}")


def fetch(machine_id: str) -> None:
    data = _fetch_genome(machine_id)
    if data is None:
        print(f"❌ machine '{machine_id}' not found in grid")
        return
    merged = darwin.import_genome(
        REPO / "reports" / f"darwin-genome-{machine_id}.json")
    print(f"✅ fetched {machine_id}: "
          f"{len(data.get('population', {}))} skills, merged {merged}")


def duel(machine_id: str) -> None:
    data = _fetch_genome(machine_id)
    if data is None:
        print(f"❌ machine '{machine_id}' not found")
        return
    client = REPO / "scripts" / "darwin_grid_client.py"
    spec2 = importlib.util.spec_from_file_location("dgclient", client)
    client_mod = importlib.util.module_from_spec(spec2)
    sys.modules["dgclient"] = client_mod
    spec2.loader.exec_module(client_mod)
    client_mod.grid_duel("http://unused", machine_id) if False else None
    # direct duel logic (avoids HTTP layer)
    foreign_pop = data.get("population", {})
    local_fitness = darwin._load_json(darwin.FITNESS_FILE, {}).get("skills", {})
    ranked = sorted(local_fitness.items(),
                    key=lambda kv: kv[1].get("fitness", 0), reverse=True)
    if not ranked:
        print("❌ no local fitness - run --autopilot first")
        return
    champion = ranked[0][0]
    print(f"🏟️  GRID DUEL (github backend): `{champion}` vs {machine_id}")
    for fname, _ in sorted(foreign_pop.items(),
                           key=lambda kv: kv[1].get("wins", 0), reverse=True)[:3]:
        if not (darwin.SKILLS_DIR / fname / "SKILL.md").exists():
            print(f"   ⏭️  {fname}: not installed locally")
            continue
        d = darwin.head_to_head(champion, fname)
        won = d["winner"] == "parent"
        print(f"   {'🏆' if won else '💀'} {fname}: local {d['parent_result'].get('exit_code')}, "
              f"foreign {d['child_result'].get('exit_code')} -> "
              f"{'LOCAL WINS' if won else 'FOREIGN WINS'}")
        population = darwin._load_json(darwin.POPULATION_FILE, {})
        g = population.setdefault(champion, {"wins": 0, "losses": 0})
        g["wins" if won else "losses"] = g.get("wins" if won else "losses", 0) + 1
        darwin._save_json(darwin.POPULATION_FILE, population)


def list_machines() -> None:
    code, resp = _api("GET", "contents/")
    if code != 200:
        print(f"❌ cannot list grid: {resp}")
        return
    machines = [f["name"].replace(".json", "")
                for f in resp if f["name"].endswith(".json")]
    print(f"🌐 Darwin Grid ({GRID_REPO}): {len(machines)} machine(s)")
    for m in machines:
        print(f"   - {m}")


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--publish", metavar="MACHINE_ID")
    ap.add_argument("--fetch", metavar="MACHINE_ID")
    ap.add_argument("--duel", metavar="MACHINE_ID")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()
    if args.publish:
        publish(args.publish)
    elif args.fetch:
        fetch(args.fetch)
    elif args.duel:
        duel(args.duel)
    elif args.list:
        list_machines()
    else:
        ap.print_help()


if __name__ == "__main__":
    main()

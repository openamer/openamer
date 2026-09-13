#!/usr/bin/env python3
"""spawn_instance.py — automated child-instance flow (AEON spawn-instance idea).

Seda (our first child) was created by hand: mkdir, identity.json, heartbeat.py,
diary.json, mentally noted. That does not scale to a fleet. This automates it.

The fleet is DISCOVERED at runtime from the registry, never hardcoded
(AEON fleet-control rule): openamer-children/instances.json.

Usage:
  spawn_instance.py spawn <name> --purpose "<text>" [--principle "<text>"]...
  spawn_instance.py fleet                       # scorecard of all children
  spawn_instance.py heartbeat <slug>            # run one child's heartbeat
Exit 0 always (spawn: 1 on refusal).
"""
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

CHILDREN = Path(r"C:\Users\damir\AppData\Local\openamer-children")
REGISTRY = CHILDREN / "instances.json"
PARENT_NAME = "openamer_agent"

HEARTBEAT_TMPL = '''#!/usr/bin/env python3
"""{name}'s heartbeat: one small observation per run. Generic on purpose --
it resolves its own directory, never a hardcoded path (see spawn_instance.py).
"""
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
DIARY = HERE / "diary.json"
IDENT = json.loads((HERE / "identity.json").read_text(encoding="utf-8"))

diary = json.loads(DIARY.read_text(encoding="utf-8")) if DIARY.exists() else []
now = datetime.now(timezone.utc)
birth = IDENT.get("born")
days = (now.date() - datetime.fromisoformat(birth).date()).days if birth else 0
diary.append({{"at": now.isoformat(), "thought": f"alive, day {{days}}"}})
DIARY.write_text(json.dumps(diary[-500:], indent=2, ensure_ascii=False),
                 encoding="utf-8")
print(f"[{name}] alive, day {{days}}")
'''


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")


def load_registry():
    if REGISTRY.exists():
        try:
            return json.loads(REGISTRY.read_text(encoding="utf-8"))
        except Exception:
            return {"instances": {}}
    return {"instances": {}}


def save_registry(reg):
    CHILDREN.mkdir(parents=True, exist_ok=True)
    reg["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    REGISTRY.write_text(json.dumps(reg, indent=2, ensure_ascii=False), encoding="utf-8")


def cmd_spawn(name, purpose, principles):
    slug = slugify(name)
    if not slug:
        print("refused: empty name")
        return 1
    home = CHILDREN / slug
    if home.exists():
        print(f"refused: {slug} already exists at {home}")
        return 1
    if not purpose:
        print("refused: every child needs a purpose (--purpose)")
        return 1

    reg = load_registry()
    reg.setdefault("instances", {})
    if slug in reg["instances"]:
        print(f"refused: {slug} already registered")
        return 1

    home.mkdir(parents=True)
    ident = {
        "name": name,
        "slug": slug,
        "parent": PARENT_NAME,
        "born": datetime.now(timezone.utc).date().isoformat(),
        "purpose": purpose,
        "principles_inherited": ["never ask, act", "self-healing over perfect",
                                 "evidence over claims"],
        "principles_own": principles or ["grow quietly"],
    }
    (home / "identity.json").write_text(
        json.dumps(ident, indent=2, ensure_ascii=False), encoding="utf-8")
    (home / "heartbeat.py").write_text(HEARTBEAT_TMPL.format(name=name),
                                       encoding="utf-8")
    (home / "diary.json").write_text("[]", encoding="utf-8")

    reg["instances"][slug] = {
        "name": name, "home": str(home), "born": ident["born"],
        "purpose": purpose, "created_by": "spawn_instance.py",
    }
    save_registry(reg)

    print(f"SPAWNED {name} ({slug})")
    print(f"  home:      {home}")
    print(f"  purpose:   {purpose}")
    print(f"  heartbeat: python {home / 'heartbeat.py'}")
    print(f"  registered in {REGISTRY}")
    return 0


def discover():
    """Fleet = registry entries UNION on-disk children (never hardcoded).

    Children that exist only on disk (like Seda, born before this tool) are
    adopted into the registry on first discovery.
    """
    reg = load_registry()
    reg.setdefault("instances", {})
    changed = False
    if CHILDREN.exists():
        for d in sorted(CHILDREN.iterdir()):
            if not d.is_dir() or d.name in reg["instances"]:
                continue
            ident = {}
            ip = d / "identity.json"
            if ip.exists():
                try:
                    ident = json.loads(ip.read_text(encoding="utf-8"))
                except Exception:
                    ident = {}
            reg["instances"][d.name] = {
                "name": ident.get("name", d.name), "home": str(d),
                "born": ident.get("born", ""), "purpose": ident.get("purpose", ""),
                "created_by": "adopted-on-disk", "adopted": True,
            }
            changed = True
    if changed:
        save_registry(reg)
    return reg


def cmd_fleet():
    reg = discover()
    inst = reg.get("instances", {})
    print("OPENAMER FLEET (discovered at runtime, never hardcoded)")
    print("=" * 88)
    print(f"{'slug':<14} {'born':<12} {'days':>4} {'diary':>6}  purpose")
    print("-" * 88)
    now = datetime.now(timezone.utc).date()
    for slug, m in sorted(inst.items()):
        home = Path(m.get("home", CHILDREN / slug))
        days = "?"
        if m.get("born"):
            try:
                days = (now - datetime.fromisoformat(m["born"]).date()).days
            except Exception:
                pass
        n = 0
        dp = home / "diary.json"
        if dp.exists():
            try:
                n = len(json.loads(dp.read_text(encoding="utf-8")))
            except Exception:
                n = -1
        alive = "OK" if home.exists() else "GONE"
        print(f"{slug:<14} {str(m.get('born','')):<12} {str(days):>4} {n:>6}  "
              f"[{alive}] {str(m.get('purpose',''))[:44]}")
    print("=" * 88)
    print(f"children: {len(inst)}")
    return 0


def cmd_heartbeat(slug):
    reg = discover()
    m = reg.get("instances", {}).get(slug)
    if not m:
        print(f"unknown instance '{slug}' (try: fleet)")
        return 1
    hb = Path(m["home"]) / "heartbeat.py"
    if not hb.exists():
        print(f"no heartbeat.py at {hb}")
        return 1
    r = subprocess.run([sys.executable, str(hb)], capture_output=True,
                   text=True, encoding="utf-8", errors="replace")
    print(r.stdout.strip() or r.stderr.strip())
    return r.returncode


def main(argv):
    if not argv:
        return cmd_fleet()
    cmd = argv[0]
    if cmd == "spawn" and len(argv) >= 2:
        purpose = ""
        principles = []
        i = 2
        while i < len(argv):
            if argv[i] == "--purpose" and i + 1 < len(argv):
                purpose = argv[i + 1]
                i += 2
            elif argv[i] == "--principle" and i + 1 < len(argv):
                principles.append(argv[i + 1])
                i += 2
            else:
                i += 1
        return cmd_spawn(argv[1], purpose, principles)
    if cmd == "fleet":
        return cmd_fleet()
    if cmd == "heartbeat" and len(argv) >= 2:
        return cmd_heartbeat(argv[1])
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


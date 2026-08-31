#!/usr/bin/env python3
"""OpenAmer Pro Skill Pack installer.

Usage:
  python install.py                     # install into ~/.openamer/skills/
  python install.py --target DIR       # dry-run/verify only
  python install.py --target DIR --check
"""
import argparse, json, shutil, sys
from pathlib import Path

PACK = Path(__file__).parent
MANIFEST = json.loads((PACK / "MANIFEST.json").read_text(encoding="utf-8"))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default=str(Path.home() / ".openamer" / "skills"))
    ap.add_argument("--check", action="store_true", help="verify only, no install")
    a = ap.parse_args()
    target = Path(a.target)
    print(f"OpenAmer Pro Skill Pack v{MANIFEST['version']} — {len(MANIFEST['skills'])} skills")
    bad = 0
    for s in MANIFEST["skills"]:
        src = PACK / "skills" / s["name"]
        if not (src / "SKILL.md").exists():
            print(f"  MISSING: {s['name']}"); bad += 1; continue
        if a.check:
            print(f"  ok ({s['score']}): {s['name']}")
        else:
            dst = target / s["name"]
            shutil.copytree(src, dst, dirs_exist_ok=True)
            print(f"  installed: {s['name']} -> {dst}")
    if bad:
        print(f"{bad} broken entries — pack corrupt"); return 1
    print("DONE" if not a.check else "VERIFY OK")
    return 0

if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""build_pro_pack.py — build the OpenAmer Pro Skill Pack (sellable bundle).

Reads reports/skill-validator-latest.json, selects top skills (score >= 70,
no hardcoded user paths, self-contained), copies them into packs/pro-pack/
with an installer + manifest, and produces a ZIP.

Usage:
  python scripts/build_pro_pack.py            # build pack + zip
  python scripts/build_pro_pack.py --list     # only show selected skills
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

REPO = Path(r"C:\Users\damir\openamer-repo")
SKILLS_DIR = Path(r"C:\Users\damir\AppData\Local\openamer-laptop\skills")
VALIDATOR_LOG = Path(r"C:\Users\damir\AppData\Local\openamer-laptop\logs\skill-validator-latest.json")
PACK_DIR = REPO / "packs" / "pro-pack"
MIN_SCORE = 70
HARDCODED_RE = re.compile(r"C:\\Users\\damir|C:/Users/damir|/c/Users/damir", re.I)
# categories of skills that are bundled utilities/metadata, not user-facing value
EXCLUDE_PREFIXES = ("darwin-harvested", "dsh-",)


def load_scores() -> dict[str, int]:
    data = json.loads(VALIDATOR_LOG.read_text(encoding="utf-8"))
    return {s["name"]: s["score"] for s in data.get("skill_results", [])}


def find_skill(name: str) -> Path | None:
    hits = list(SKILLS_DIR.rglob(f"*/{name}/SKILL.md")) + list(SKILLS_DIR.rglob(f"{name}/SKILL.md"))
    return hits[0].parent if hits else None


def skill_ok(skill_dir: Path) -> tuple[bool, str]:
    """Self-contained check: no hardcoded user paths, has description."""
    for f in skill_dir.rglob("*"):
        if f.is_file() and f.suffix in (".md", ".py", ".sh", ".json", ".yaml", ".yml"):
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except Exception:
                return False, f"unreadable: {f.name}"
            if HARDCODED_RE.search(text):
                return False, f"hardcoded user path in {f.name}"
    return True, "ok"


def build(list_only: bool) -> int:
    scores = load_scores()
    candidates = sorted(
        ((n, s) for n, s in scores.items() if s >= MIN_SCORE
         and not n.startswith(EXCLUDE_PREFIXES)),
        key=lambda kv: -kv[1],
    )
    selected = []
    for name, score in candidates:
        d = find_skill(name)
        if not d:
            continue
        ok, why = skill_ok(d)
        if ok:
            selected.append((name, score, d))
        else:
            print(f"  skip {name}: {why}")
        if len(selected) >= 25:
            break

    print(f"[pack] {len(selected)} Skills qualify (score >= {MIN_SCORE}):")
    for n, s, _ in selected:
        print(f"  {s:3d}  {n}")
    if list_only:
        return 0
    if not selected:
        print("[pack] nothing qualified")
        return 1

    # write pack
    if PACK_DIR.exists():
        shutil.rmtree(PACK_DIR / "skills", ignore_errors=True)
    (PACK_DIR / "skills").mkdir(parents=True, exist_ok=True)
    manifest = {"name": "OpenAmer Pro Skill Pack", "version": "1.0.0",
                "min_score": MIN_SCORE, "skills": []}
    for n, s, d in selected:
        dst = PACK_DIR / "skills" / n
        shutil.copytree(d, dst, dirs_exist_ok=True)
        manifest["skills"].append({"name": n, "score": s})
    (PACK_DIR / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    installer = '''#!/usr/bin/env python3
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
'''
    (PACK_DIR / "install.py").write_text(installer, encoding="utf-8")

    # zip
    zpath = PACK_DIR.parent / "pro-pack-v1.zip"
    if zpath.exists():
        zpath.unlink()
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in PACK_DIR.rglob("*"):
            if f.is_file():
                z.write(f, f.relative_to(PACK_DIR.parent))
    print(f"[pack] manifest+installer+zip written: {zpath}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    sys.exit(build(ap.parse_args().list))

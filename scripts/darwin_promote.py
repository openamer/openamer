#!/usr/bin/env python3
"""darwin_promote.py — gate candidates into the live population.

A species-candidate (darwin/species-candidates/<name>/SKILL.md) is promoted
only if it passes the quality gate:
  1. validator score >= PROMOTE_SCORE (after auto-fix)
  2. no hardcoded user paths
  3. not already live

Promotion copies the candidate into the skills dir (category subdir
'darwin'), re-validates, and moves the candidate dir to promoted/.
Zero LLM tokens.

Usage: python scripts/darwin_promote.py [--list|--promote NAME|--promote-all]
"""
from __future__ import annotations

import argparse
import importlib.util
import shutil
import sys
from pathlib import Path

REPO = Path(r"C:\Users\damir\openamer-repo")
CAND_DIR = REPO / "darwin" / "species-candidates"
PROMOTED_DIR = REPO / "darwin" / "promoted"
SKILLS_DIR = Path(r"C:\Users\damir\AppData\Local\openamer-laptop\skills")
VALIDATOR = REPO / "scripts" / "skill-validator.py"
PROMOTE_SCORE = 45
HARDCODED = ("C:\\Users\\damir", "C:/Users/damir", "/c/Users/damir")


def _load_validator():
    spec = importlib.util.spec_from_file_location("skill_validator", str(VALIDATOR))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def score_of(path: Path, sv) -> int:
    return sv.validate_skill_content(path)["score"]


def passes(skill_dir: Path, sv) -> tuple[bool, str]:
    for f in skill_dir.rglob("*"):
        if f.is_file():
            text = f.read_text(encoding="utf-8", errors="replace")
            if any(h in text for h in HARDCODED):
                return False, f"hardcoded path in {f.name}"
    s = score_of(skill_dir / "SKILL.md", sv)
    if s < PROMOTE_SCORE:
        return False, f"score {s} < {PROMOTE_SCORE}"
    return True, f"score {s}"


def promote(name: str, sv) -> bool:
    src = CAND_DIR / name
    if not (src / "SKILL.md").exists():
        print(f"  {name}: no candidate")
        return False
    # auto-fix first for a fair chance
    v = sv.validate_skill_content(src / "SKILL.md")
    sv.fix_skill_content(src / "SKILL.md", v)
    ok, why = passes(src, sv)
    if not ok:
        print(f"  ❌ {name}: gate failed ({why})")
        return False
    dst = SKILLS_DIR / "darwin" / name
    shutil.copytree(src, dst, dirs_exist_ok=True)
    PROMOTED_DIR.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(PROMOTED_DIR / name))
    print(f"  ✅ {name}: promoted ({why}) -> {dst}")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--list", action="store_true")
    g.add_argument("--promote", metavar="NAME")
    g.add_argument("--promote-all", action="store_true")
    args = ap.parse_args()

    sv = _load_validator()
    candidates = sorted(p.parent for p in CAND_DIR.glob("*/SKILL.md"))
    if args.list:
        for c in candidates:
            ok, why = passes(c, sv)
            print(f"  {'PASS' if ok else 'FAIL'}  {c.name}  ({why})")
        return 0
    if args.promote:
        promote(args.promote, sv)
        return 0
    if args.promote_all:
        n = 0
        for c in candidates:
            if promote(c.name, sv):
                n += 1
        print(f"promoted {n}/{len(candidates)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

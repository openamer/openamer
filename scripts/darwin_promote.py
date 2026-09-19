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

import os
import argparse
import importlib.util
import shutil
import sys
from pathlib import Path

# Markers only a real OpenAmer home carries. Darwin never creates these, so they
# separate a genuine install from a scratch directory that merely exists -- e.g.
# a stray ``OPENAMER_HOME=/c/tmp/oa-home``, which made the swarm loop resolve an
# empty population and report "0 tasks, everything clean" (observed 2026-09-19).
_HOME_MARKERS = ("config.yaml", ".env", "cron", "memories", "openamer-agent")


def _is_install_root(pth: Path) -> bool:
    """True when *pth* looks like a real OpenAmer home, not a scratch dir."""
    try:
        return any((pth / m).exists() for m in _HOME_MARKERS)
    except OSError:
        return False


def _resolve_openamer_home(default: Path) -> Path:
    """Resolve OPENAMER_HOME robustly across shells (see darwin_engine.py).

    git-bash exports OPENAMER_HOME as an MSYS path ("/c/Users/..."). Native
    Windows Python treats that as relative and lands in a phantom "C:/c/..."
    tree. Normalise MSYS drive forms and reject doubled-drive artefacts so the
    script never silently operates on a directory that isn't the real install.
    """
    raw = os.environ.get("OPENAMER_HOME")
    if not raw:
        return default
    norm = raw.replace(os.sep, "/") if os.sep != "/" else raw
    cand = None
    if len(norm) >= 3 and norm[0] == "/" and norm[1].isalpha() and norm[2] == "/":
        cand = Path(norm[1].upper() + ":/" + norm[3:])
    else:
        p = Path(raw)
        if p.is_absolute():
            cand = p
    if cand is None:
        return default
    parts = cand.parts
    drive = parts[0].rstrip("/").rstrip(os.sep)
    if len(drive) == 2 and drive[1] == ":" and len(parts) >= 2:
        head = parts[1].strip("/").strip(os.sep).lower()
        if head and head == drive[0].lower():
            return default
    if cand is None or not cand.exists():
        return default
    # An existing directory is not enough: a scratch dir adopted as the install
    # silently evolves an empty population while the real home is untouched.
    if _is_install_root(cand):
        return cand
    print(f"[home] WARNING: OPENAMER_HOME={cand} exists but is not an OpenAmer "
          f"install root; falling back to {default}.", file=sys.stderr)
    return default




REPO = Path(r"C:\Users\damir\openamer-repo")
CAND_DIR = REPO / "darwin" / "species-candidates"
PROMOTED_DIR = REPO / "darwin" / "promoted"
SKILLS_DIR = _resolve_openamer_home(Path.home() / "AppData" / "Local" / "openamer") / "skills"
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

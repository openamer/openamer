#!/usr/bin/env python3
"""darwin_skill_probe.py — executable verification of what a skill claims.

Why this exists
---------------
Darwin's fitness is `usage * 3 + health * 5 + mutation_bonus - age_penalty`.
`usage` counts how often a skill name appeared in sessions, so a skill that is
invoked often and helps little outranks one that is rarely needed and always
right. Nothing anywhere checked whether a skill still *works*.

The validator scores prose heuristics. This probe answers a narrower, harder
question with a fact instead of an opinion:

    do the artifacts this skill tells the agent to use still exist?

A SKILL.md that says "run `scripts/foo.py`" while `foo.py` is gone is unfit no
matter how well it reads, and the agent following it burns a turn discovering
that. That is a real outcome, measured without an LLM, a human, or any tokens.

Scoring
-------
probe_score = resolved_references / total_references  (1.0 when a skill
references nothing — it cannot be judged, so it is not punished).

Output: reports/darwin-probe.json

    {"updated": iso, "skills": {"<name>": {"refs": 4, "ok": 3,
                                           "score": 0.75, "missing": ["..."]}}}

CLI:
    python scripts/darwin_skill_probe.py            # scan, write report
    python scripts/darwin_skill_probe.py --json     # also print the report
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HOME = Path(os.environ.get("OPENAMER_HOME") or (Path.home() / "AppData" / "Local" / "openamer-laptop"))
SKILLS_DIR = HOME / "skills"
REPORT = REPO / "reports" / "darwin-probe.json"

# A *claim* is an invocation: the skill tells the agent to run this. A bare
# backtick mention is prose — `script.py` as an example, or `src/extension.ts`
# as a file the skill is about to create. Scoring mentions flagged four healthy
# skills as broken, so only invocation forms count.
REF_RE = re.compile(
    r"(?:python3?|bash|sh|pwsh|powershell|node|npx|uv|pip3?)\s+"
    r"`?(\.{0,2}/?[\w./-]*?[\w-]+\.(?:py|sh|ps1|js|ts))`?"
    r"|`(\.{1,2}/[\w./-]+\.(?:py|sh|ps1|js|ts))`"
)


# Directories never worth walking for a skill's referenced artifact.
_SKIP_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    ".mypy_cache", ".pytest_cache", "dist", "build", "release", "release-alt",
}

# Subtrees that legitimately hold a skill's referenced scripts. Bounded on
# purpose: walking all of $HOME is minutes of I/O across a venv, node_modules
# and two Electron builds.
_SEARCH_ROOTS = (
    "openamer-agent/scripts",
    "openamer-agent/tools",
    "openamer-browser",
    "scripts",
    "tools",
    "openamer-repo/scripts",
    "openamer-repo/tools",
    "openamer-repo/agent",
    "openamer-repo/openamer_cli",
)

_INDEX: dict[str, str] | None = None


def candidate_roots() -> list[Path]:
    """Where a referenced path may legitimately live."""
    roots = [HOME, REPO, REPO / "scripts", REPO / "tools", HOME / "scripts"]
    roots += [HOME / r for r in _SEARCH_ROOTS]
    return roots


def _basename_index() -> dict[str, str]:
    """basename -> path of the first match under the search roots.

    A SKILL.md says "run `active_learn.py`", not an absolute path — the file
    lives wherever the runtime keeps it. Resolving only exact relative paths
    made an earlier version of this probe report ten perfectly healthy skills as
    broken, because their scripts sit under openamer-agent/scripts/training/ and
    openamer-browser/ rather than inside the repo. A probe that punishes working
    skills is worse than no probe, since it feeds fitness.
    """
    global _INDEX
    if _INDEX is not None:
        return _INDEX

    index: dict[str, str] = {}
    for rel in _SEARCH_ROOTS:
        base = HOME / rel
        if not base.is_dir():
            base = REPO / rel
        if not base.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
            for filename in filenames:
                index.setdefault(filename, os.path.join(dirpath, filename))

    _INDEX = index
    return index


def resolve(ref: str, skill_dir: Path | None = None) -> bool:
    ref = ref.strip()
    if not ref or ref.startswith(("http", "~")):
        return True  # not a filesystem claim; nothing to verify
    # `SKILL_DIR/` is a DOCUMENTED template variable, not a broken path: the
    # youtube-content skill defines it as "the directory containing this
    # SKILL.md". Resolve it against the skill's own directory before judging.
    if skill_dir is not None and ref.startswith("SKILL_DIR/"):
        if (skill_dir / ref[len("SKILL_DIR/"):]).exists():
            return True
    # A skill that ships scripts next to its own SKILL.md is well-formed, and
    # most do. Without this, `scripts/extract_metadata.py` counted as broken for
    # every skill that carries its own tooling.
    if skill_dir is not None and (skill_dir / ref).exists():
        return True
    for root in candidate_roots():
        if (root / ref).exists():
            return True
    if Path(ref).exists():
        return True
    # Last resort: does a file of that name exist anywhere we ship scripts?
    return Path(ref).name in _basename_index()


# Placeholder names used in examples. `python script.py --once` documents the
# *shape* of an invocation; `C:/path/to/script.py` shows where a file goes. They
# are not claims that a file exists. Excluded by name, because after the
# invocation filter landed these two were the only remaining "broken" hits and
# both were documentation, not damage.
_PLACEHOLDER_RE = re.compile(
    r"(?:^|/)(?:script|test_x|example|sample|foo|bar|your_script|my_script)\."
    r"|path/to/|<[^>]+>|YOUR_|XXX",
    re.IGNORECASE,
)


def _is_placeholder(ref: str) -> bool:
    return bool(_PLACEHOLDER_RE.search(ref))


# A ref that does not resolve is forgiven when its LINE marks it as an example
# rather than a claim: a project-tree drawing, an existence probe, or prose that
# says "e.g."/"example". Measured 2026-10-10: of 37 unresolved refs across 19
# skills, 35 were exactly this class - `x.py`/`f.py` in an edit example,
# `manage.py` as a Django detection marker, llama.cpp's `convert_hf_to_gguf.py`
# named as an EXTERNAL tool. Forgiving them by name would be guessing; the line
# they sit on is the actual evidence.
_EXAMPLE_LINE_RE = re.compile(
    r"[|\u2502\u251c\u2514\u2500]"
    r"|\[\s*-[fd]\s"
    r"|e\.g\.|for instance|for example|such as|placeholder|your own",
    re.IGNORECASE,
)


def _is_example_line(line: str) -> bool:
    return bool(_EXAMPLE_LINE_RE.search(line))


def score_text(text: str, skill_dir: Path | None = None) -> dict:
    """Score a SKILL.md body without touching disk.

    Split out so Darwin can judge a candidate that exists only in memory:
    mutate() generates the variant, measures it against the parent, and only
    then decides whether to keep it. The regex and the arithmetic live here;
    reading a path is the thin wrapper below.
    """
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for line in text.splitlines():
        for m in REF_RE.finditer(line):
            ref = m.group(1) or m.group(2)
            if ref and ref not in seen:
                seen.add(ref)
                found.append((ref, line))

    # Placeholder-shaped names are forgiven only when they do NOT resolve: an
    # example like `python script.py --once` documents a shape, while
    # `/path/to/scripts/session_to_brain.py` with that file present is a real
    # reference that happens to carry a placeholder prefix. Filtering at
    # collection time hid that one; filtering here only forgives fiction.
    #
    # A bare basename that resolves nowhere is DELIBERATELY still a claim, not
    # unmeasurable. It cannot be told apart from an example by any name rule,
    # but test_a_variant_that_adds_a_dead_reference_scores_lower pins the A/B
    # floor to it: if `ghost.py` stopped counting, a damaging mutation would tie
    # its parent and the whole Darwin A/B would go blind. Over-punishing an
    # example costs a few fitness points; under-punishing damage breaks the
    # selection it feeds. (Tried the "unmeasurable" variant 2026-10-10; the
    # repo's tests refuted it - reverted.)
    missing = [r for r, line in found
               if not resolve(r, skill_dir)
               and not _is_placeholder(r)
               and not _is_example_line(line)]
    total = len(found)
    ok = total - len(missing)
    return {
        "refs": total,
        "ok": ok,
        "score": round(ok / total, 3) if total else 1.0,
        "missing": missing[:5],
    }


def probe_skill(skill_md: Path) -> dict:
    """Score the SKILL.md at *skill_md*, resolving against its own directory."""
    return score_text(
        skill_md.read_text(encoding="utf-8", errors="replace"), skill_dir=skill_md.parent
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="print the report")
    args = ap.parse_args()

    if not SKILLS_DIR.is_dir():
        print(f"error: no skills directory at {SKILLS_DIR}", file=sys.stderr)
        return 1

    skills: dict[str, dict] = {}
    # rglob, not iterdir. Skills live in category subdirectories too
    # (bundled/productivity/..., darwin-harvested-*/...), and iterating only the
    # top level judged 81 of the 714 SKILL.md files on this machine. The
    # validator has always used rglob; the probe silently disagreed with it, so
    # "0 broken, average 1.0" was a statement about 11% of the population.
    # First match wins on a name collision, and sorted() makes that the
    # shallowest path.
    for md in sorted(SKILLS_DIR.rglob("SKILL.md")):
        skills.setdefault(md.parent.name, probe_skill(md))

    report = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "skills_dir": str(SKILLS_DIR),
        "total": len(skills),
        "skills": skills,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    judged = [s for s in skills.values() if s["refs"]]
    broken = [n for n, s in skills.items() if s["missing"]]
    avg = round(sum(s["score"] for s in judged) / len(judged), 3) if judged else 1.0

    print(f"skills: {len(skills)} | judged: {len(judged)} | avg probe_score: {avg}")
    print(f"skills with a broken reference: {len(broken)}")
    for name in broken[:12]:
        print(f"  ✗ {name}: {', '.join(skills[name]['missing'])}")

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

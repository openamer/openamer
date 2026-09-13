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

# Paths the instructions point at: `scripts/x.py`, `./tools/y.sh`, `agent/z.py`.
# Deliberately conservative — only things that look like repo/home artifacts,
# never bare words, so real prose never counts as a broken reference.
REF_RE = re.compile(
    r"`(\.{0,2}/?[\w./-]*?[\w-]+\.(?:py|sh|ps1|js|ts))`"
    r"|(?:python3?|bash|sh|\./)\s+(\.{0,2}/?[\w./-]*?[\w-]+\.(?:py|sh|ps1|js|ts))"
)


def candidate_roots() -> list[Path]:
    """Where a referenced path may legitimately live."""
    return [HOME, REPO, REPO / "scripts", REPO / "tools", HOME / "scripts"]


def resolve(ref: str) -> bool:
    ref = ref.strip()
    if not ref or ref.startswith(("http", "~")):
        return True  # not a filesystem claim; nothing to verify
    for root in candidate_roots():
        if (root / ref).exists():
            return True
    return Path(ref).exists()


def probe_skill(skill_md: Path) -> dict:
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    refs: list[str] = []
    for m in REF_RE.finditer(text):
        ref = m.group(1) or m.group(2)
        if ref and ref not in refs:
            refs.append(ref)

    missing = [r for r in refs if not resolve(r)]
    total = len(refs)
    ok = total - len(missing)
    return {
        "refs": total,
        "ok": ok,
        "score": round(ok / total, 3) if total else 1.0,
        "missing": missing[:5],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="print the report")
    args = ap.parse_args()

    if not SKILLS_DIR.is_dir():
        print(f"error: no skills directory at {SKILLS_DIR}", file=sys.stderr)
        return 1

    skills: dict[str, dict] = {}
    for d in sorted(SKILLS_DIR.iterdir()):
        if not d.is_dir():
            continue
        md = d / "SKILL.md"
        if md.is_file():
            skills[d.name] = probe_skill(md)

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

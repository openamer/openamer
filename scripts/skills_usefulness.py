#!/usr/bin/env python3
"""Skill usefulness: do a skill's own claims still hold?

Skill count is not capability (1389 SKILL.md on this install). This measures the
narrower, checkable question for a defined population: *does what the skill says
about its own files still match the files on disk?*

Population (measured, not chosen by taste):

* skills referenced from ``SKILL.md`` backticks by other skills — link
  centrality, which is what "most-referenced" can actually mean here. Note that
  centrality is not value: the DOCA suite tops the list purely because its
  members cross-link each other.
* skills attached to cron jobs — the ones the fleet actually loads.

Per skill, three checkable claim classes (static only — no skill content is
executed, because that would run unreviewed commands):

  FRONTMATTER  name + description present, name matches the directory
  REFERENCE    every path a skill cites in backticks resolves
               (``references/x.md`` against the skill dir, ``scripts/x.py``
               against the repo and the install home)
  COMPILE      every ``*.py`` shipped inside the skill compiles

Verdicts: BROKEN (a hard claim failed), VERIFIED (claims checked, all hold),
UNKNOWN (no checkable claim — not a failure, but not evidence either).

Exit codes: 0 all verified or unknown, 1 at least one broken, 2 inputs missing.
"""

from __future__ import annotations

import argparse
import ast
import collections
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

HOME = Path(
    os.environ.get("OPENAMER_HOME")
    or (
        Path.home() / "AppData" / "Local" / "openamer-laptop"
        if os.name == "nt"
        else Path.home() / ".openamer-laptop"
    )
)
SKILLS = HOME / "skills"
REPO = HOME / "openamer-agent"
OUT = HOME / "reports" / "skills-usefulness"
JOBS = HOME / "cron" / "jobs.json"

# Path-shaped backtick tokens that a skill is asserting exist.
#
# `scripts/` is deliberately NOT in the relative pattern. The first version of
# this checker included it, and every repo script a skill cited was then
# resolved against the skill's own directory and reported missing — 25 of 44
# skills came out BROKEN, most of them on that single false positive. A
# `scripts/x.py` reference means the repo's (or the install's) scripts tree
# unless the skill ships its own `scripts/` next to the SKILL.md, which
# REPO_REF checks as a second location.
RELATIVE_REF = re.compile(
    r"`((?:references|templates|assets|examples)/[A-Za-z0-9_.\-/]+\.(?:md|py|sh|json|yaml|yml|ts|js|txt))`"
)
REPO_REF = re.compile(r"`(scripts/[A-Za-z0-9_.\-/]+\.(?:py|sh))`")
BACKTICK_NAME = re.compile(r"`([a-z0-9][a-z0-9_-]{5,})`")


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    block = text[3:end]
    fields: dict[str, str] = {}
    for line in block.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip().strip("\"'")
    return fields


def skill_files() -> dict[str, Path]:
    """name -> SKILL.md path, for the install's skill tree."""
    return {p.parent.name: p for p in SKILLS.rglob("SKILL.md")}


def referenced_population(files: dict[str, Path], limit: int) -> list[tuple[str, int]]:
    counts: collections.Counter = collections.Counter()
    names = {name for name in files if len(name) >= 6}
    for name, path in files.items():
        text = path.read_text(encoding="utf-8", errors="replace")
        for token in set(BACKTICK_NAME.findall(text)):
            if token in names and token != name:
                counts[token] += 1
    return counts.most_common(limit)


def cron_population() -> set[str]:
    if not JOBS.is_file():
        return set()
    data = json.loads(JOBS.read_text(encoding="utf-8"))
    jobs = data if isinstance(data, list) else data.get("jobs", [])
    names: set[str] = set()
    for job in jobs:
        for skill in job.get("skills") or []:
            names.add(skill)
        if job.get("skill"):
            names.add(job["skill"])
    return names


def check_skill(name: str, path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    directory = path.parent
    problems: list[str] = []
    checked = 0

    front = parse_frontmatter(text)
    if not front.get("name"):
        problems.append("frontmatter: no name")
    elif front["name"] != name:
        problems.append(f"frontmatter: name '{front['name']}' != directory '{name}'")
    if not front.get("description"):
        problems.append("frontmatter: no description")
    checked += 2

    for relative in sorted(set(RELATIVE_REF.findall(text))):
        checked += 1
        if not (directory / relative).exists():
            problems.append(f"reference: {relative} does not exist")

    for repo_path in sorted(set(REPO_REF.findall(text))):
        checked += 1
        if (
            not (REPO / repo_path).exists()
            and not (HOME / repo_path).exists()
            and not (directory / repo_path).exists()
        ):
            problems.append(
                f"reference: {repo_path} exists neither in the repo, the install, "
                f"nor the skill's own tree"
            )

    for script in sorted(directory.rglob("*.py")):
        checked += 1
        try:
            ast.parse(script.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError as exc:
            problems.append(f"compile: {script.name} line {exc.lineno}: {exc.msg}")

    verdict = "BROKEN" if problems else ("VERIFIED" if checked else "UNKNOWN")
    return {
        "skill": name,
        "path": str(path),
        "verdict": verdict,
        "claims_checked": checked,
        "problems": problems,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--limit", type=int, default=30, help="centrality population size")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not SKILLS.is_dir():
        print(f"SKILL-USEFULNESS: no skill tree at {SKILLS}", file=sys.stderr)
        return 2

    files = skill_files()
    central = referenced_population(files, args.limit)
    population = [name for name, _ in central]
    already = set(population)
    for name in sorted(cron_population()):
        if name not in already and name in files:
            population.append(name)

    rows = [check_skill(name, files[name]) for name in population if name in files]
    counts = collections.Counter(row["verdict"] for row in rows)

    if not rows:
        # An empty population means nothing was measured. Reporting that as a
        # pass would be the exact false green this tool exists to prevent.
        print(
            "SKILL-USEFULNESS: population resolved to zero skills — nothing was measured",
            file=sys.stderr,
        )
        return 2

    payload = {
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "skill_files_on_disk": len(files),
        "population": len(rows),
        "centrality_top": [{"skill": n, "references": c} for n, c in central],
        "verdicts": dict(counts),
        "rows": rows,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "latest.json").write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")

    if args.json:
        print(json.dumps({k: v for k, v in payload.items() if k != "rows"}, indent=2, ensure_ascii=False))
        return 1 if counts.get("BROKEN") else 0

    print(
        f"Skill usefulness — {len(files)} SKILL.md on disk, population {len(rows)} "
        f"(top {args.limit} by reference centrality + cron-attached)"
    )
    print(f"  VERIFIED {counts.get('VERIFIED', 0)}  BROKEN {counts.get('BROKEN', 0)}  "
          f"UNKNOWN {counts.get('UNKNOWN', 0)}")
    broken = [row for row in rows if row["verdict"] == "BROKEN"]
    if broken:
        print("\nBROKEN (the skill's own claims do not hold):")
        for row in broken[:20]:
            print(f"  {row['skill']}")
            for problem in row["problems"][:4]:
                print(f"      {problem}")
    print(f"\nstored: {OUT / 'latest.json'}")
    return 1 if broken else 0


if __name__ == "__main__":
    raise SystemExit(main())

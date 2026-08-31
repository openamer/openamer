#!/usr/bin/env python3
"""darwin_synthesize.py — synthesize new skill candidates from trend intelligence.

Phase 2: Darwin no longer only patches weak skills — it BUILDS new ones.
Reads reports/trend-scout-latest.md, groups signals by topic, and for topics
we have no skill coverage of yet, generates a structured skill candidate into
darwin/species-candidates/<name>/SKILL.md. Candidates are NOT live: they wait
for --promote (or darwin_engine promote-species) after human/agent review.

Zero LLM tokens: templates + trend metadata only. The next autopatch cycle
can iterate on candidates' scores.

Usage:
  python scripts/darwin_synthesize.py            # generate candidates (dry-run listing)
  python scripts/darwin_synthesize.py --apply    # write candidate SKILL.md files
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

REPO = Path(r"C:\Users\damir\openamer-repo")
TRENDS_MD = REPO / "reports" / "trend-scout-latest.md"
SKILLS_DIR = Path(r"C:\Users\damir\AppData\Local\openamer-laptop\skills")
CAND_DIR = REPO / "darwin" / "species-candidates"
MAX_PER_RUN = 2

# topic buckets: (candidate_name, regex over trend titles, what the skill should cover)
TOPICS = [
    ("agent-security-governance",
     re.compile(r"security|guardrails|governance|identity|zero-trust", re.I),
     "AI agent security and governance: permission scoping, audit trails, "
     "behavioral guardrails, zero-trust tool access for autonomous agents."),
    ("agentic-commerce-payments",
     re.compile(r"payment|commerce|checkout|transaction|Visa|Mastercard", re.I),
     "Agentic commerce: machine-native payments, checkout automation safety, "
     "transaction limits and human-approval gates for agent-driven purchases."),
    ("agent-orchestration-economics",
     re.compile(r"orchestration|economics|pricing|cost", re.I),
     "Agent orchestration and cost control: model routing for cost efficiency, "
     "token budgeting, multi-agent workload placement decisions."),
    ("enterprise-agent-deployment",
     re.compile(r"enterprise|private ai cloud|platform|deployment", re.I),
     "Enterprise agent deployment: on-prem patterns, compliance checklists, "
     "identity integration and observability for production agent fleets."),
]


def load_trend_titles() -> list[str]:
    text = TRENDS_MD.read_text(encoding="utf-8", errors="replace")
    return re.findall(r"- \[\w+\] ([^—]+) —", text)


def existing_skill_names() -> set[str]:
    return {p.parent.name.lower() for p in SKILLS_DIR.rglob("*/SKILL.md")}


def coverage_gap(names: set[str], keywords: list[str]) -> bool:
    joined = " ".join(names)
    return not any(k in joined for k in keywords)


TEMPLATE = """---
name: {name}
description: 'Use for {human} tasks. Candidate synthesized from trend radar; awaiting trial promotion.'
version: 0.1.0
metadata:
  openamer:
    tags: [darwin-candidate, trend-synthesized]
    related_skills: []
platforms: [linux, macos, windows]
---

# {title} (Darwin Candidate)

## Overview
{scope}

Synthesized by `darwin_synthesize.py` on {date} from trend-radar signals:
{signals}

## When to use
Whenever a task touches {human}: research, tool selection, or workflow design
in this area.

## Usage
1. Collect the 3 most relevant sources from the origin signals.
2. Extract concrete practices applicable to OpenAmer (commands, configs, policies).
3. Turn each practice into a verifiable step with a health check.

## Setup / Installation
No external setup required — this skill guides analysis and synthesis work
using the standard OpenAmer toolset (terminal, web, file).

## Example

```bash
# scan the trend report for this topic's latest signals
grep -i "{keyword}" reports/trend-scout-latest.md
```

## Verification
- Candidate is only promotable after `darwin_engine --head-to-head` shows it
  beating an existing related skill OR no related skill exists and a cron
  trial runs error-free.
- Record outcomes in reports/darwin-autopatch.md for fitness scoring.

## Pitfalls
- Do not promote without real execution evidence (see Verification).
- Trend hype != practice: only extract steps that were demonstrated to work.

## Troubleshooting
- If signals are stale (>48h), re-run the trend scout before acting.
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write candidate files")
    args = ap.parse_args()

    titles = load_trend_titles()
    names = existing_skill_names()
    today = datetime.date.today().isoformat()
    made = []
    for cname, rx, scope in TOPICS:
        if len(made) >= MAX_PER_RUN:
            break
        if cname in names:
            continue  # already live
        if not coverage_gap(names, cname.split("-")[:2]):
            continue  # coverage exists
        hits = [t.strip() for t in titles if rx.search(t)]
        if not hits:
            continue
        made.append((cname, hits[:5], scope))

    if not made:
        print("no viable candidates this run")
        return 0

    for cname, hits, scope in made:
        signal_lines = "\n".join(f"- {h}" for h in hits)
        content = TEMPLATE.format(
            name=cname,
            title=cname.replace("-", " ").title(),
            human=cname.replace("-", " "),
            date=today,
            signals=signal_lines,
            scope=scope,
            keyword=cname.split("-")[0],
        )
        target = CAND_DIR / cname / "SKILL.md"
        if args.apply:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        print(f"{'written' if args.apply else 'candidate'}: {target}")

    print(f"done: {len(made)} candidate(s) {'applied' if args.apply else '(dry-run)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

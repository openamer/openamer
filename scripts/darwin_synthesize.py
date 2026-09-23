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

import os
import argparse
import datetime
import json
import re
import sys
from pathlib import Path

_HOME_MARKERS = ("config.yaml", ".env", "cron", "memories", "openamer-agent")


def _is_install_root(pth: Path) -> bool:
    """True when *pth* looks like a real OpenAmer home, not a scratch dir.

    A marker only counts when it carries real content:

    * file markers (``config.yaml``/``.env``) must be non-empty.
    * directory markers (``cron``/``memories``/``openamer-agent``) must hold at
      least one NON-EMPTY file. ``any(p.iterdir())`` was not enough: the live
      scratch tree ``OPENAMER_HOME=C:/Users/damir/_vaultfinal`` carries
      ``cron/executions.db`` at 0 bytes plus an empty ``memories/``, so a
      0-byte file proved "install" and that tree was adopted over the real
      189-skill install. The 15-minute darwin autopilot cron then evolved a
      3-skill phantom population and wrote 2-skill snapshots into the
      append-only history ledger, flipping ``auto_tune()`` to "declining".
    """
    try:
        for m in _HOME_MARKERS:
            p = pth / m
            if p.is_file():
                if p.stat().st_size > 0:
                    return True
            elif p.is_dir():
                for child in p.iterdir():
                    if child.is_file() and child.stat().st_size > 0:
                        return True
        return False
    except OSError:
        return False

def _resolve_openamer_home(default: Path) -> Path:
    """Resolve OPENAMER_HOME robustly across shells (single source: darwin_engine.py).

    git-bash exports OPENAMER_HOME as an MSYS path ("/c/Users/..."). Native
    Windows Python treats that as relative and lands in a phantom "C:/c/..."
    tree, so the swarm would operate on a directory that is not the install.
    Normalise MSYS drive forms and reject doubled-drive artefacts.

    Prefer an installed candidate that actually carries a ``skills`` dir: on this
    host "openamer-laptop" is the real install while plain "openamer" is only a
    near-empty upstream default. Choosing the bare default made every sibling
    script resolve a DIFFERENT home than darwin_engine -- observed live
    2026-09-22, when the autonomous loop reported "0 tasks, everything clean"
    while writing its swarm into C:/Users/damir/AppData/Local/openamer (27 skills)
    instead of the real home (183 skills). A mis-set OPENAMER_HOME pointing at a
    scratch dir is likewise rejected via the install-root markers.
    """
    local = default.parent
    candidates = [local / "openamer-laptop", local / "openamer"]
    picked = next((c for c in candidates if (c / "skills").is_dir()), default)

    raw = os.environ.get("OPENAMER_HOME")
    if not raw:
        return picked
    norm = raw.replace(os.sep, "/") if os.sep != "/" else raw
    cand = None
    if len(norm) >= 3 and norm[0] == "/" and norm[1].isalpha() and norm[2] == "/":
        cand = Path(norm[1].upper() + ":/" + norm[3:])
    else:
        p = Path(raw)
        if p.is_absolute():
            cand = p
    if cand is None or not cand.exists():
        return picked
    parts = cand.parts
    drive = parts[0].rstrip("/").rstrip(os.sep)
    if len(drive) == 2 and drive[1] == ":" and len(parts) >= 2:
        head = parts[1].strip("/").strip(os.sep).lower()
        if head and head == drive[0].lower():
            return picked
    if _is_install_root(cand):
        return cand
    print(f"[home] WARNING: OPENAMER_HOME={cand} exists but is not an OpenAmer "
          f"install root; falling back to {picked}.", file=sys.stderr)
    return picked

REPO = Path(r"C:\Users\damir\openamer-repo")
TRENDS_MD = REPO / "reports" / "trend-scout-latest.md"
SKILLS_DIR = _resolve_openamer_home(Path.home() / "AppData" / "Local" / "openamer") / "skills"
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
    """True = no existing skill covers this topic.

    Old version: substring match of ANY keyword -> with 618 skills a generic
    token like 'agent' matched almost everything and blocked all candidates.
    New version: coverage only counts if a skill name matches the MAJORITY of
    the topic tokens (specific compound, e.g. 'agent-security' needs both
    'agent' AND 'security' in one name) or an exact multi-word phrase.
    """
    # require >= 2 tokens so single generic words can never claim coverage
    tokens = [t for t in keywords if len(t) > 3]
    if len(tokens) < 2:
        tokens = keywords
    need = max(2, len(tokens)) if len(tokens) >= 2 else len(tokens)
    for name in names:
        hits = sum(1 for t in tokens if t in name)
        if hits >= need:
            return False
    return True


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

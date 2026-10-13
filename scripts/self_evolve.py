#!/usr/bin/env python3
"""self_evolve.py — Autonomous growth logger for OpenAmer.

Scans recent sessions for new patterns, capabilities, and bugs.
Updates reports/growth.md with today's entry.
Runs as no_agent cron (zero LLM tokens).

Tracks:
- New tools/plugins added
- Bugs found & fixed
- Patterns learned
- Skill gaps identified
"""

from __future__ import annotations

import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(r"C:\Users\damir\openamer-repo")
GROWTH_FILE = REPO / "reports" / "growth.md"

# ── Git-based change detection ──────────────────────────────────────────

def _today_commits() -> int:
    """Count commits authored by me today."""
    try:
        since = datetime.datetime.now().strftime("%Y-%m-%dT00:00:00")
        result = subprocess.run(
            ["git", "log", "--oneline", "--after=" + since,
             "--author=openamer", "--author=github-actions"],
            capture_output=True, text=True, cwd=REPO, timeout=15,
        )
        count = len(result.stdout.strip().split("\n")) if result.stdout.strip() else 0
        return count
    except Exception:
        return 0


def _new_files_today() -> list[str]:
    """Get files created today in tracked directories."""
    try:
        since = datetime.datetime.now().strftime("%Y-%m-%dT00:00:00")
        result = subprocess.run(
            ["git", "diff", "--diff-filter=A", "--name-only",
             f"@{since}..HEAD"],
            capture_output=True, text=True, cwd=REPO, timeout=15,
        )
        files = [f for f in result.stdout.strip().split("\n") if f.strip()]
        return files
    except Exception:
        return []


# ── Growth File Update ──────────────────────────────────────────────────

def _update_growth(commits: int, new_files: list[str]) -> bool:
    """Append a daily entry to growth.md if there's something new."""
    if commits == 0 and not new_files:
        return False  # Nothing new — stay quiet

    today = datetime.datetime.now().strftime("%Y-%m-%d")
    marker = f"## {today}"
    content = GROWTH_FILE.read_text(encoding="utf-8") if GROWTH_FILE.exists() else "# OpenAmer — Self-Evolution Log\n"

    if marker in content:
        return False  # Already logged today

    entry = [
        f"\n## {today}\n",
    ]
    if new_files:
        entry.append(f"### Neue Dateien ({len(new_files)})")
        for f in new_files:
            entry.append(f"- `{f}`")
        entry.append("")

    if commits:
        entry.append(f"### Commits heute: {commits}")
        entry.append("")

    entry.append("---\n")

    with open(GROWTH_FILE, "a", encoding="utf-8") as f:
        f.write("\n".join(entry))

    print(f"growth: logged {today} — {commits} commits, {len(new_files)} files")
    return True


# ── Main ────────────────────────────────────────────────────────────────

def main() -> int:
    commits = _today_commits()
    new_files = _new_files_today()

    updated = _update_growth(commits, new_files)
    if not updated:
        print("growth: nothing new today — silent exit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
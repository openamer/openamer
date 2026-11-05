#!/usr/bin/env python3
"""Audit every desktop locale for completeness.

For each locale the report answers three questions:

  1. Does the locale have the same sections and keys as en.ts?
  2. How many strings are still English (i.e. not translated)?
  3. Which of the remaining English strings are real gaps, and which are
     proper nouns that must stay English (product name, acronyms, URLs)?

The real gaps are the ones that need work. The proper nouns are not gaps —
 translating them would be a bug.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
I18N = REPO / "apps" / "desktop" / "src" / "i18n"
TMP = REPO / "tmp"

SKIP = {
    "catalog.ts", "types.ts", "index.ts", "define-locale.ts", "plugin-i18n.ts",
    "runtime.ts", "languages.ts",
}

# Strings that must stay in English. Translating them would be wrong.
PROPER_NOUNS = {
    "MCP", "OpenAmer", "OpenAmer Cloud", "OpenAmer Desktop", "OpenAmeric",
    "Telegram", "Discord", "Slack", "Hub", "Cron", "Webhooks", "URL", "Pro",
    "YOLO", "Terminal", "Code", "Web", "SOURCE", "DIFF", "A–Z",
    "Notifications", "Notification", "Sessions", "Session", "Navigation",
    "Diagnostics", "Version", "Port", "Vision", "Compression", "Maintenance",
    "Branches", "Description", "Pause", "Actions", "Profiles", "Profile",
    "Messages", "Message", "Agents", "Agent", "Options", "Effort", "Minimal",
    "Max", "Ultra", "Auto", "Conversation", "Images", "Image", "images",
    "image", "env", "zone", "h", "pagination", "Items", "Item", "Skills",
    "Skill", "Jobs", "Job", "Changes", "Change", "Tools", "Tool", "Models",
    "Model", "Nodes", "Node", "Results", "Result", "Findings", "Finding",
    "Attachments", "Attachment", "Lines", "Line", "Commits", "Commit",
    "Subagents", "Subagent", "subagents", "subagent", "Services", "Service",
    "Actions", "Zones", "Zone", "Entries", "Entry", "Updates", "Update",
    "Warnings", "Warning", "Errors", "Error", "Commands", "Command",
    "Steps", "Step", "Tokens", "Token", "Credits", "Credit", "Replies",
    "Reply", "Providers", "Provider", "Releases", "Release", "Artifacts",
    "Artifact", "Memories", "Memory", "Databases", "Database",
    "Workspaces", "Workspace", "Contexts", "Context",
    "Triggers", "Trigger", "Runs", "Run", "Health", "Live", "Ready",
    "Enabled", "Disabled", "Default", "Custom", "Auto",
}


def leaves_of(locale: str) -> dict:
    out = TMP / f"i18n_{locale}_audit.json"
    r = subprocess.run(
        ["node", str(REPO / "scripts" / "i18n_extract_locale.mjs"),
         str(I18N / f"{locale}.ts"), str(out)],
        capture_output=True, text=True, cwd=str(REPO),
    )
    if r.returncode != 0:
        raise SystemExit(f"extract failed for {locale}: {r.stderr[-300:]}")
    return {l["path"]: l for l in json.loads(out.read_text(encoding="utf-8"))["leaves"]}


def is_real_gap(path: str, text: str) -> bool:
    t = text.strip()
    if not t:
        return False
    if t in PROPER_NOUNS:
        return False
    if t.startswith("http") or t.startswith("@") or t.startswith("www."):
        return False
    if re.fullmatch(r"[\d\W_]+", t):
        return False
    # a pure interpolation or a label made only of a variable
    if re.fullmatch(r"[\$\{\}\w\s\W]*", t) and re.search(r"\$\{", t):
        rest = re.sub(r"\$\{[^}]*\}", "", t).strip()
        if not rest or rest in PROPER_NOUNS:
            return False
    return True


def main() -> int:
    locales = sorted(
        p.stem for p in I18N.glob("*.ts")
        if p.name not in SKIP and not p.name.endswith(".test.ts")
    )
    en = leaves_of("en")
    en_text = {p: l["text"] for p, l in en.items() if l["kind"] in ("string", "func")}

    print(f"{'locale':10} {'leaves':>7} {'translated':>11} {'english':>8} {'gaps':>5}  status")
    print("-" * 62)
    bad = []
    total_gaps = 0
    for loc in locales:
        lv = leaves_of(loc)
        # only the translatable leaves are compared — the array elements
        # ("path.0", "path.1") are an artifact of the extraction and are
        # addressed as "path" by the translation table
        lv_text = {p for p, l in lv.items() if l["kind"] in ("string", "func")}
        missing = set(en_text) - lv_text
        extra = lv_text - set(en_text)
        tgt_text = {p: l["text"] for p, l in lv.items() if l["kind"] in ("string", "func")}
        same = [p for p, t in en_text.items()
                if p in tgt_text and tgt_text[p] == t]
        gaps = [p for p in same if is_real_gap(p, en_text[p])]
        if loc == "en":
            gaps = []
        total_gaps += len(gaps)
        status = "OK"
        if missing or extra:
            status = f"MISSING {len(missing)} / EXTRA {len(extra)}"
            bad.append(loc)
        elif gaps:
            status = f"{len(gaps)} gaps"
        print(f"{loc:10} {len(lv):7} {len(en_text) - len(same):11} {len(same):8} "
              f"{len(gaps):5}  {status}")
        if gaps and len(gaps) <= 6:
            for p in gaps:
                print(f"             - {p}: {en_text[p][:60]!r}")

    print()
    print(f"locales: {len(locales)}   structural problems: {len(bad)}   "
          f"total real gaps: {total_gaps}")
    if bad:
        print("problem locales:", bad)
    return 0


if __name__ == "__main__":
    sys.exit(main())

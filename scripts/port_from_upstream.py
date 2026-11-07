"""Port a file (or symbol) from upstream hermes-agent into the openamer tree.

Applies the openamer rebrand to the copied text and fails loudly on any
leftover ``hermes`` token so a port can never ship branding leaks.

Usage:
    python scripts/port_from_upstream.py --file agent/provider_media.py
    python scripts/port_from_upstream.py --file hermes_cli/archive_safe.py --to openamer_cli/archive_safe.py
    python scripts/port_from_upstream.py --check-only
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from upstream_rebrand import (  # noqa: E402
    KEEP_PATTERN,
    RENAMES,
    leftover_hermes,
    rebrand,
)

OPENAMER = Path(__file__).resolve().parent.parent
UPSTREAM = Path(r"C:\Users\damir\AppData\Local\hermes\hermes-agent")

# Directories that are not part of the shipped tree. Worktrees, scratch
# copies and archived snapshots live inside the checkout and would otherwise
# be scanned as if they were product code.
SKIP_DIRS = frozenset(
    {
        "tests",
        "node_modules",
        "venv",
        ".venv",
        "website",
        "tmp",
        "out",
        "reports",
        "wt-gate179",
        "oa-v28",
    }
)

# The audit tooling itself necessarily names upstream modules and paths. It is
# not product code and its mentions are the audit working as intended.
TOOLING_FILES = frozenset(
    {
        "scripts/port_from_upstream.py",
        "scripts/upstream_rebrand.py",
        "scripts/audit_upstream_coupling.py",
        "scripts/audit_upstream_independence.py",
        "scripts/audit_upstream_independence_desktop.py",
    }
)

# Attribution sites: a file that names its upstream origin on purpose.
# ``openamer_cli/identity.py`` guards against claiming a foreign lineage and
# therefore names the marker it forbids.
ATTRIBUTION_FILES = frozenset(
    {
        "agent/error_classifier.py",
        "apps/desktop/src/lib/preview-act/act-in-page.ts",
        "openamer_cli/_early_recovery.py",
        "openamer_cli/archive_safe.py",
        "openamer_cli/identity.py",
        "openamer_cli/kanban_db.py",
        "openamer_cli/kanban_db_connect.py",
        "openamer_cli/kanban_db_graph.py",
        "openamer_cli/kanban_swarm.py",
        "openamer_state.py",
        "tools/desktop_ui.py",
        "tools/drive_preview_tool.py",
    }
)

__all__ = [
    "ATTRIBUTION_FILES",
    "KEEP_PATTERN",
    "RENAMES",
    "OPENAMER",
    "UPSTREAM",
    "SKIP_DIRS",
    "TOOLING_FILES",
    "leftover_hermes",
    "rebrand",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", help="path relative to the upstream tree")
    ap.add_argument("--to", help="destination relative to the openamer tree")
    ap.add_argument("--check-only", action="store_true", help="audit the tree for leaks")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.check_only:
        bad = 0
        attributed = 0
        for path in sorted(OPENAMER.rglob("*.py")):
            rel = path.relative_to(OPENAMER)
            rel_posix = rel.as_posix()
            if any(p in rel.parts for p in SKIP_DIRS):
                continue
            if rel_posix in TOOLING_FILES:
                continue
            hits = leftover_hermes(path.read_text(encoding="utf-8", errors="replace"), str(rel))
            if rel_posix in ATTRIBUTION_FILES:
                attributed += len(hits)
                continue
            bad += len(hits)
            for h in hits:
                print(h)
        print(f"leftover hermes tokens: {bad}")
        print(f"attributed upstream mentions: {attributed}")
        return 1 if bad else 0

    if not args.file:
        ap.error("--file is required unless --check-only")

    src = UPSTREAM / args.file
    if not src.is_file():
        print(f"upstream file not found: {src}")
        return 1

    dest_rel = args.to
    if dest_rel is None:
        dest_rel = args.file
        if dest_rel.startswith("hermes_cli/"):
            dest_rel = dest_rel.replace("hermes_cli/", "openamer_cli/", 1)
    dest = OPENAMER / dest_rel
    if dest.exists() and not args.dry_run:
        print(f"REFUSING to overwrite existing file: {dest_rel} (delete/symbol-port it instead)")
        return 1

    text = rebrand(src.read_text(encoding="utf-8", errors="replace"))
    hits = leftover_hermes(text, args.file)
    if hits:
        print("BRANDING LEAK — refusing to write:")
        for h in hits:
            print("  " + h)
        return 1

    if args.dry_run:
        print(f"would write {dest_rel} ({len(text.splitlines())} lines)")
        return 0

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {dest_rel} ({len(text.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

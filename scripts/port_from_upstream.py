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
import re
import sys
from pathlib import Path

OPENAMER = Path(__file__).resolve().parent.parent
UPSTREAM = Path(r"C:\Users\damir\AppData\Local\hermes\hermes-agent")

# Ordered: longest / most specific first so partial renames can't fire early.
RENAMES: tuple[tuple[str, str], ...] = (
    ("hermes_cli", "openamer_cli"),
    ("hermes_constants", "openamer_constants"),
    ("hermes_state", "openamer_state"),
    ("hermes_logging", "openamer_logging"),
    ("get_hermes_home", "get_openamer_home"),
    ("get_default_hermes_root", "get_default_openamer_root"),
    ("hermes_home_key", "openamer_home_key"),
    ("set_hermes_home_override", "set_openamer_home_override"),
    ("reset_hermes_home_override", "reset_openamer_home_override"),
    ("get_hermes_home_override", "get_openamer_home_override"),
    ("HERMES_HOME", "OPENAMER_HOME"),
    ("HERMES_KANBAN", "OPENAMER_KANBAN"),
    ("HERMES_", "OPENAMER_"),
    ("`hermes ", "`openamer "),
    ("hermes-agent", "openamer-agent"),
    ("HermesAgent", "OpenAmerAgent"),
    ("HermesCLI", "OpenAmerCLI"),
    ("hermes_pkce", "openamer_pkce"),
    ("Hermes", "OpenAmer"),
    ("hermes", "openamer"),
)

# ``hermes-parser`` / ``@hermes/`` are the Meta JS toolchain, deliberately kept.
KEEP_PATTERN = re.compile(r"hermes-(?:parser|estimator)|@hermes/")


def rebrand(text: str) -> str:
    for src, dst in RENAMES:
        text = text.replace(src, dst)
    return text


def leftover_hermes(text: str, source_name: str) -> list[str]:
    hits = []
    for lineno, line in enumerate(text.splitlines(), 1):
        if "hermes" not in line.lower():
            continue
        stripped = KEEP_PATTERN.sub("", line)
        if "hermes" in stripped.lower():
            hits.append(f"{source_name}:{lineno}: {line.strip()[:120]}")
    return hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", help="path relative to the upstream tree")
    ap.add_argument("--to", help="destination relative to the openamer tree")
    ap.add_argument("--check-only", action="store_true", help="audit the tree for leaks")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.check_only:
        bad = 0
        for path in sorted(OPENAMER.rglob("*.py")):
            rel = path.relative_to(OPENAMER)
            if any(p in rel.parts for p in ("tests", "node_modules", "venv", ".venv", "website")):
                continue
            hits = leftover_hermes(path.read_text(encoding="utf-8", errors="replace"), str(rel))
            bad += len(hits)
            for h in hits:
                print(h)
        print(f"leftover hermes tokens: {bad}")
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

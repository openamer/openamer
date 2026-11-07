"""Extend the upstream-independence audit to the TypeScript desktop tree.

The Python audit covers agent/ and openamer_cli/. The desktop app is a
separate surface, so it gets the same treatment: rebrand, diff, classify.
"""

from __future__ import annotations

import argparse
import difflib
import pathlib
import re
import json

OA = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_UP = pathlib.Path(r"C:\Users\damir\AppData\Local\hermes\hermes-agent")
UP = DEFAULT_UP

RENAMES = (
    ("hermes_cli", "openamer_cli"), ("hermes_constants", "openamer_constants"),
    ("hermes_state", "openamer_state"), ("hermes_logging", "openamer_logging"),
    ("hermes_platform", "openamer_platform"),
    ("get_hermes_home", "get_openamer_home"),
    ("get_default_hermes_root", "get_default_openamer_root"),
    ("HERMES_HOME", "OPENAMER_HOME"), ("HERMES_", "OPENAMER_"),
    ("hermes-agent", "openamer-agent"), ("HermesAgent", "OpenAmerAgent"),
    ("HermesCLI", "OpenAmerCLI"), ("Hermes", "OpenAmer"), ("hermes", "openamer"),
)
KEEP = re.compile(r"hermes-(?:parser|estimator)|@hermes/")
NOISE = re.compile(
    r"^\s*(//|/\*|\*|#\s*-{3,}|from\s+openamer|import\s+openamer|"
    r"import\s+.*openamer|export\s+\{)", re.IGNORECASE)


def rebrand(t: str) -> str:
    for s, d in RENAMES:
        t = t.replace(s, d)
    return KEEP.sub("", t)


def classify(src: str, dst: str):
    a, b = src.splitlines(), dst.splitlines()
    if src.strip() == dst.strip():
        return "IDENTICAL", 0, len(a)
    changed = 0
    for line in difflib.unified_diff(a, b, lineterm="", n=0):
        if line.startswith(("---", "+++", "@@")):
            continue
        if line.startswith(("+", "-")):
            body = line[1:].strip()
            if not body or len(body) < 4 or NOISE.match(line[1:]):
                continue
            changed += 1
    ratio = changed / max(len(a), 1)
    if changed == 0:
        return "COSMETIC", 0, len(a)
    if ratio < 0.10:
        return "MINOR", changed, len(a)
    return "SUBSTANTIVE", changed, len(a)


def walk(base: pathlib.Path, exts):
    if not base.is_dir():
        return []
    return [p for p in sorted(base.rglob("*"))
            if p.is_file() and p.suffix.lower() in exts and "node_modules" not in p.parts]


def main():
    global UP
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--upstream", default=str(DEFAULT_UP))
    args = ap.parse_args()
    UP = pathlib.Path(args.upstream).expanduser()
    if not UP.is_dir():
        print(f"upstream checkout not found: {UP}")
        return 2

    up_files = walk(UP / "apps" / "desktop" / "src", {".ts", ".tsx"})
    oa_files = walk(OA / "apps" / "desktop" / "src", {".ts", ".tsx"})
    oa_by_rel = {p.relative_to(OA / "apps" / "desktop" / "src").as_posix(): p for p in oa_files}

    counts = {"IDENTICAL": 0, "COSMETIC": 0, "MINOR": 0, "SUBSTANTIVE": 0}
    lines = {"IDENTICAL": 0, "COSMETIC": 0, "MINOR": 0, "SUBSTANTIVE": 0}
    only_up = 0
    identical_files = []

    for up in up_files:
        rel = up.relative_to(UP / "apps" / "desktop" / "src").as_posix()
        oa = oa_by_rel.get(rel)
        if oa is None:
            only_up += 1
            continue
        try:
            src = rebrand(up.read_text(encoding="utf-8", errors="replace"))
            dst = oa.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        cls, changed, up_lines = classify(src, dst)
        counts[cls] += 1
        lines[cls] += up_lines
        if cls == "IDENTICAL":
            identical_files.append(rel)

    total = sum(lines.values())
    print("=" * 68)
    print("DESKTOP TREE (apps/desktop/src) — UPSTREAM INDEPENDENCE")
    print("=" * 68)
    print(f"upstream files: {len(up_files)}   openamer files: {len(oa_files)}")
    print(f"compared: {sum(counts.values())}   upstream-only (dropped): {only_up}")
    print()
    for k in ("IDENTICAL", "COSMETIC", "MINOR", "SUBSTANTIVE"):
        pct = (lines[k] / total * 100) if total else 0
        print(f"  {k:<12} {counts[k]:5d} files  {lines[k]:>7d} lines  {pct:6.2f}%")
    print()
    if identical_files:
        print(f"--- verbatim-identical desktop files ({len(identical_files)}) ---")
        for f in identical_files[:25]:
            print(f"  {f}")
        if len(identical_files) > 25:
            print(f"  ... +{len(identical_files)-25} more")

    out = OA / "reports" / "upstream-independence-audit-desktop.json"
    out.write_text(json.dumps({
        "upstream_files": len(up_files), "openamer_files": len(oa_files),
        "compared": sum(counts.values()), "upstream_only_dropped": only_up,
        "classes": counts, "lines": lines,
        "identical_files": identical_files,
    }, indent=2), encoding="utf-8")
    print(f"\nreport written: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from upstream_rebrand import rebrand  # noqa: E402

OA = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_UP = pathlib.Path(r"C:\Users\damir\AppData\Local\hermes\hermes-agent")
UP = DEFAULT_UP

NOISE = re.compile(
    r"^\s*(//|/\*|\*|#\s*-{3,}|from\s+openamer|import\s+openamer|"
    r"import\s+.*openamer|export\s+\{)", re.IGNORECASE)



def _changed_lines(a: list[str], b: list[str], noise: re.Pattern[str]) -> tuple[int, int]:
    """Return (upstream_lines_changed, new_lines_added).

    ``upstream_lines_changed`` counts the upstream lines that no longer survive
    unchanged in the OpenAmer version -- the honest denominator for "how much
    of upstream is still here". ``new_lines_added`` counts the lines OpenAmer
    wrote that upstream never had.

    A modified line is one change, not two: ``difflib.unified_diff`` emits a
    ``-`` and a ``+`` line for it. ``SequenceMatcher`` opcodes report the
    replacement block once, so a modified block counts as
    ``max(removed, added)``.
    """
    matcher = difflib.SequenceMatcher(None, a, b)
    upstream_changed = 0
    added = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if tag == "replace":
            removed, new = a[i1:i2], b[j1:j2]
        elif tag == "delete":
            removed, new = a[i1:i2], []
        elif tag == "insert":
            removed, new = [], b[j1:j2]
        else:  # pragma: no cover - difflib emits no other tags
            continue

        def _substantive(lines: list[str]) -> int:
            return sum(
                1
                for line in lines
                if line.strip()
                and len(line.strip()) >= 4
                and not noise.match(line)
            )

        upstream_changed += _substantive(removed)
        added += _substantive(new)
    # A modified block counts once, not as removed+added.
    return max(upstream_changed, added), added


def classify(src: str, dst: str):
    a, b = src.splitlines(), dst.splitlines()
    if src.strip() == dst.strip():
        return "IDENTICAL", 0, len(a)
    changed, _added = _changed_lines(a, b, NOISE)
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


def main(argv: list[str] | None = None) -> int:
    global UP
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--upstream", default=str(DEFAULT_UP))
    args = ap.parse_args(argv)
    upstream = pathlib.Path(args.upstream).expanduser()
    if not upstream.is_dir():
        print(f"upstream checkout not found: {upstream}")
        return 2
    return audit(upstream, OA)


def audit(upstream: pathlib.Path, openamer: pathlib.Path) -> int:
    """Audit ``openamer`` against ``upstream`` and write the JSON report."""
    up_files = walk(upstream / "apps" / "desktop" / "src", {".ts", ".tsx"})
    oa_files = walk(openamer / "apps" / "desktop" / "src", {".ts", ".tsx"})
    oa_root = openamer / "apps" / "desktop" / "src"
    oa_by_rel = {p.relative_to(oa_root).as_posix(): p for p in oa_files}

    counts = {"IDENTICAL": 0, "COSMETIC": 0, "MINOR": 0, "SUBSTANTIVE": 0}
    lines = {"IDENTICAL": 0, "COSMETIC": 0, "MINOR": 0, "SUBSTANTIVE": 0}
    only_up = 0
    identical_files = []

    for up in up_files:
        rel = up.relative_to(upstream / "apps" / "desktop" / "src").as_posix()
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

    out = openamer / "reports" / "upstream-independence-audit-desktop.json"
    out.parent.mkdir(parents=True, exist_ok=True)
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

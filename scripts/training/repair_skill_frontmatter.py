#!/usr/bin/env python3
"""Repair SKILL.md frontmatter whose scalar values break strict YAML parsing.

Why this exists
---------------
`scripts/training/auto_skill_creation.py` writes SKILL.md frontmatter through
`SKILL_TEMPLATE`, which emitted the values RAW:

    description: {description}          # unquoted, unescaped
    source_insight: "{source}"          # double-quoted, inner quotes unescaped

Any insight containing ": " (a mapping separator), a leading "-", "[", "{",
"*", "&", or a quote therefore produced frontmatter that PyYAML refuses to
parse. Those files then break `website/scripts/generate-skill-docs.py`, which
parses with STRICT `yaml.safe_load` (unlike `agent/skill_utils.py`, which has a
lenient fallback) and raises ValueError on the first bad file — so the CI job
"Docs Site / docs-site-checks" dies in the step "Regenerate per-skill docs
pages + catalogs" before `npm run lint:diagrams` or `npm run build` ever run.

This script is the DATA half of the fix. It rewrites only the files that
actually fail a strict parse, and only the two affected keys, taking each value
from the file itself (via the writer's own `clean_text`, which collapses
whitespace and drops control bytes) and re-emitting it as a JSON-quoted
single-line scalar — the exact form a YAML parser round-trips back.

The CODE half is the one-line change in `auto_skill_creation.py` that stops new
broken files from being written. Both are needed: repairing the data without
fixing the writer just moves the breakage to the next batch.

Usage
-----
    python scripts/training/repair_skill_frontmatter.py            # report only
    python scripts/training/repair_skill_frontmatter.py --write    # apply
    python scripts/training/repair_skill_frontmatter.py --write --root skills

Exit status is 0 when every scanned SKILL.md parses strictly afterwards, 1
otherwise, so it can be used as a gate.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

import yaml

_REPO = Path(__file__).resolve().parents[2]

# Keys the auto-generated template emits. The repair only ever rewrites
# `description` and `source_insight`; everything else is passed through
# byte-for-byte (including the body below the closing fence).
_REPAIRABLE = ("description", "source_insight")

# Keys that end a (possibly multi-line) value block.
_FRONTMATTER_KEYS = (
    "name", "description", "auto_generated", "created", "source_insight",
    "status", "fitness_score", "trials", "wins",
)
_KEY_LINE = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_]*):(?:[ \t]?)(.*)$")


def _clean_text():
    """Reuse the writer's own cleaner so repaired values match what it intends.

    Imported by path (not `import auto_skill_creation`) because that module
    runs directory setup at import time and exits when OPENAMER_HOME is not a
    real install.
    """
    src = Path(__file__).with_name("auto_skill_creation.py")
    spec = importlib.util.spec_from_file_location("_asc_clean", src)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except SystemExit:
        pass
    return getattr(mod, "clean_text", lambda s: re.sub(r"\s+", " ", s).strip())


def split_frontmatter(text: str):
    """Return (fm_text, body) or (None, None) when there is no fence block.

    Mirrors `website/scripts/generate-skill-docs.py:parse_skill_md` — that
    parser is the consumer whose failure we are repairing, so the split must be
    identical (it splits on the first two "---" occurrences, not line-wise).
    """
    if not text.startswith("---"):
        return None, None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None, None
    return parts[1], parts[2]


def parses_strictly(fm_text: str) -> bool:
    try:
        yaml.safe_load(fm_text)
        return True
    except yaml.YAMLError:
        return False


def decode_scalar(raw: str, clean):
    """Recover the value the writer INTENDED for a frontmatter key.

    The raw text may be: an unquoted fragment (possibly spread over several
    lines), or a double-quoted scalar whose inner quotes were never escaped.
    Try the strict reading first, then the "one outer quote pair" reading, and
    fall back to the writer's own cleaner. Falling straight to `clean(raw)`
    would leave the surrounding quotes in the value (`"foo"` becomes the
    literal `'"foo"'`), and stripping quotes unconditionally would corrupt a
    value that legitimately starts with one.
    """
    try:
        parsed = yaml.safe_load(raw)
        if isinstance(parsed, str):
            return parsed
    except yaml.YAMLError:
        pass
    stripped = raw.strip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] == '"':
        return clean(stripped[1:-1].replace('\\"', '"'))
    return clean(raw)


def rebuild_frontmatter(fm_text: str, clean) -> str:
    """Re-emit `description` / `source_insight` as quoted single-line scalars.

    A value may span several physical lines (the pre-`clean_text` writer wrote
    them raw), so a value block is collected until the next frontmatter key
    line. The output is always the quoted form, so the function is idempotent
    on its own output only in the sense that a second pass changes nothing.

    The trailing separator is preserved deliberately: `split_frontmatter`
    slices between the fences, so the returned text carries the fence's own
    newline, and `"---" + fm + "---"` in the caller only keeps the closing
    fence on its own line if that newline survives. Dropping it produces
    `wins: 0---` — frontmatter that parses to nothing under
    `agent/skill_utils.parse_frontmatter` (its `\\n---\\s*\\n` search fails), so
    every skill silently loses its name and description.
    """
    sep = "\r\n" if "\r\n" in fm_text else "\n"
    had_trailing = fm_text.endswith(("\n", "\r"))
    lines = fm_text.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        m = _KEY_LINE.match(lines[i])
        key = m.group(1) if m else None
        if key in _REPAIRABLE:
            raw = [m.group(2)]
            i += 1
            while i < len(lines):
                nxt = _KEY_LINE.match(lines[i])
                if nxt and nxt.group(1) in _FRONTMATTER_KEYS:
                    break
                raw.append(lines[i])
                i += 1
            value = decode_scalar("\n".join(raw), clean)
            out.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
            continue
        out.append(lines[i])
        i += 1
    rebuilt = sep.join(out)
    return rebuilt + sep if had_trailing else rebuilt


def _rel(path: Path) -> str:
    """Path relative to the repo when possible, else the absolute path.

    `--root` accepts temp directories (the tests use one), and those are not
    under the repo, so `Path.relative_to` would raise and abort a repair run
    mid-way. Reporting is cosmetic here — it must never be able to fail a scan.
    """
    try:
        return str(path.relative_to(_REPO))
    except ValueError:
        return str(path)


def main() -> int:
    ap = argparse.ArgumentParser(prog="repair-skill-frontmatter")
    ap.add_argument("--write", action="store_true",
                    help="apply the repair (default: report only)")
    ap.add_argument("--root", action="append", default=None,
                    help="directory to scan, repeatable (default: skills, optional-skills)")
    a = ap.parse_args()

    roots = [Path(r) for r in (a.root or ["skills", "optional-skills"])]
    roots = [r if r.is_absolute() else _REPO / r for r in roots]
    clean = _clean_text()

    scanned = repaired = still_bad = 0
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("SKILL.md")):
            scanned += 1
            # Byte-exact I/O on purpose: Path.read_text() applies universal
            # newline translation, and the mix of CRLF (most files) and LF
            # (a few) in this tree means a text-mode round-trip silently
            # rewrites the body of the odd file out. The body is not ours to
            # touch, so it must come back bit-for-bit.
            raw_bytes = path.read_bytes()
            text = raw_bytes.decode("utf-8")
            fm_text, body = split_frontmatter(text)
            if fm_text is None:
                print(f"  skip (no frontmatter): {_rel(path)}")
                continue
            if parses_strictly(fm_text):
                continue
            fixed = rebuild_frontmatter(fm_text, clean)
            ok = parses_strictly(fixed)
            rel = _rel(path)
            if not ok:
                still_bad += 1
                print(f"  UNREPAIRED: {rel}")
                continue
            repaired += 1
            if a.write:
                path.write_bytes(("---" + fixed + "---" + body).encode("utf-8"))
                print(f"  fixed: {rel}")
            else:
                print(f"  would fix: {rel}")

    print(f"\nscanned {scanned} SKILL.md · repair needed {repaired} · still broken {still_bad}")
    if not a.write and repaired:
        print("(dry run — re-run with --write to apply)")
    return 1 if still_bad else 0


if __name__ == "__main__":
    sys.exit(main())

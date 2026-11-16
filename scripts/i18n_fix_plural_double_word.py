#!/usr/bin/env python3
"""Repair plural templates that repeat their own stem word.

Measured 2026-11-16: the German update dialog showed
"+ 1 weitere ÄnderungÄnderung enthalten". Root shape (a generator artifact,
present in many locales):

    `+ ${count} weitere Änderung${count === 1 ? 'Änderung' : 'Änderungen'} enthalten.`
                                 ^^^^^^^^^ stem already ends with "Änderung"

For count === 1 the branch appends the word a second time. The same shape exists
in bg ("нова промяна" + 'промяна'), ar ("نموذج " + 'نموذج'), and others.

Repair: drop the stem word from the literal text in front of the interpolation
and let the branch supply it ('' or the plural form). That removes the duplicate
without inventing words and without touching the plural logic.

    python scripts/i18n_fix_plural_double_word.py            # dry run
    python scripts/i18n_fix_plural_double_word.py --apply    # write files
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

I18N = pathlib.Path(__file__).resolve().parent.parent / "apps" / "desktop" / "src" / "i18n"
SKIP = {"catalog", "types", "index", "languages", "context", "runtime",
        "plugin-i18n", "define-locale"}

BRANCH = re.compile(r"\$\{[^{}]*?===\s*1\s*\?\s*'([^']*)'\s*:\s*'([^']*)'[^{}]*\}")
INTERP = re.compile(r"\$\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}")
WORD = re.compile(r"[^\W\d_]+", re.UNICODE)


def repair_line(line: str) -> tuple[str, list[str]]:
    """Remove a duplicated stem word in front of each plural interpolation."""
    notes: list[str] = []
    matches = list(BRANCH.finditer(line))
    for m in reversed(matches):
        sing, plur = m.group(1), m.group(2)
        literal_start = line.rfind("`", 0, m.start())
        if literal_start < 0:
            continue
        literal = INTERP.sub(" ", line[literal_start:m.start()])
        words = WORD.findall(literal)
        if not words:
            continue
        stem = words[-1]
        if len(stem) < 4:
            continue
        # Only the branch's FIRST word can repeat the stem word that sits
        # immediately before the interpolation. A looser "any word" test
        # destroyed legitimate phrases (ar "حيوان أليف" -> "حيوان").
        sing_first = (WORD.findall(sing) or [""])[0].lower()[:6]
        plur_first = (WORD.findall(plur) or [""])[0].lower()[:6]
        if stem.lower()[:6] not in (sing_first, plur_first):
            continue
        cut_from = m.start()
        while cut_from > literal_start and line[cut_from - 1] == " ":
            cut_from -= 1
        if line[cut_from - len(stem):cut_from] != stem:
            continue
        start = cut_from - len(stem)
        notes.append(line[start:cut_from])
        line = line[:start] + line[m.start():]
    return line, notes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    total = 0
    per_file: dict[str, int] = {}
    samples: list[str] = []
    for path in sorted(I18N.glob("*.ts")):
        code = path.stem
        if code in SKIP or code.endswith(".test"):
            continue
        raw = path.read_bytes()
        crlf = raw.count(b"\r\n")
        lone_lf = raw.count(b"\n") - crlf
        lines = raw.decode("utf-8", "replace").split("\r\n")
        changed = 0
        for i, line in enumerate(lines):
            new, notes = repair_line(line)
            if notes:
                changed += len(notes)
                if new != line:
                    lines[i] = new
                    if len(samples) < 6:
                        samples.append(f"{code}:{i + 1} dropped '{', '.join(notes)}'")
        if changed:
            total += changed
            per_file[code] = changed
            if args.apply:
                out = "\r\n".join(lines).encode("utf-8")
                if out.count(b"\r\n") != crlf or (out.count(b"\n") - out.count(b"\r\n")) != lone_lf:
                    print(f"ABORT {code}: EOL census changed", file=sys.stderr)
                    return 2
                path.write_bytes(out)

    print(f"locales touched: {len(per_file)}   duplicates repaired: {total}")
    print(f"applied: {args.apply}")
    for s in samples:
        print("  sample:", s)
    worst = sorted(per_file.items(), key=lambda kv: -kv[1])[:10]
    print("  most affected:", ", ".join(f"{k}:{v}" for k, v in worst))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

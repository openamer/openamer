#!/usr/bin/env python3
"""Find plural-branch strings whose singular/plural branch repeats the stem word.

The measured defect: de.ts had

    moreChanges: count => `+ ${count} weitere Änderung${count === 1 ? 'Änderung' : 'Änderungen'} enthalten.`

For count === 1 that concatenates "Änderung" + "Änderung" -> "ÄnderungÄnderung".
The bug shape is: a template whose literal text already ends with a word, and a
conditional branch that begins with the SAME word again.

Scans every catalog in apps/desktop/src/i18n and prints suspects.
"""
import pathlib
import re
import sys

I18N = pathlib.Path(__file__).resolve().parent.parent / "apps" / "desktop" / "src" / "i18n"
SKIP = {"catalog", "types", "index", "languages", "context", "runtime",
        "plugin-i18n", "define-locale"}

# `${... count === 1 ? 'A' : 'B' ...}` anywhere inside a template literal
BRANCH = re.compile(r"\$\{[^{}]*?===\s*1\s*\?\s*'([^']*)'\s*:\s*'([^']*)'[^{}]*\}")
INTERP = re.compile(r"\$\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}")
WORD = re.compile(r"[^\W\d_]+", re.UNICODE)


def main() -> int:
    suspects = []
    for path in sorted(I18N.glob("*.ts")):
        code = path.stem
        if code in SKIP or code.endswith(".test"):
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            for m in BRANCH.finditer(line):
                sing, plur = m.group(1), m.group(2)
                prefix = line[: m.start()]
                tail = prefix.rsplit("`", 1)[-1]
                # Variables inside ${...} are not literal words: `... with ${nodes}
                # ${nodes === 1 ? 'node' : 'nodes'}` is CORRECT, and only a
                # remaining LITERAL word can be duplicated by the branch.
                literal = INTERP.sub(" ", tail)
                words = WORD.findall(literal)
                if not words:
                    continue
                stem = words[-1]
                if len(stem) < 4:
                    continue
                # The stem word must sit DIRECTLY in front of the interpolation.
                # `model ${count}${... 'model'}` (hr) is correct Croatian: the
                # variable separates them, so nothing is duplicated.
                if not tail.rstrip().endswith(stem):
                    continue
                for branch, label in ((sing, "singular"), (plur, "plural")):
                    bw = WORD.findall(branch)
                    if not bw:
                        continue
                    # Only the FIRST word of the branch can duplicate the stem
                    # word directly in front of the interpolation. Matching any
                    # word in the branch destroys legitimate phrases: ar had
                    # `... حيوان أليف ${... 'حيوان أليف'}` (a correct "1 pet"),
                    # and a looser rule stripped "أليف" out of it.
                    if bw[0].lower()[:6] == stem.lower()[:6]:
                        suspects.append((code, lineno, label, stem, branch, line.strip()))

    print(f"scan: {len(list(I18N.glob('*.ts')))} files")
    if not suspects:
        print("suspects: 0")
        return 0
    print(f"suspects: {len(suspects)}")
    for code, lineno, label, stem, branch, line in suspects:
        print(f"\n  {code}:{lineno} [{label}] stem='{stem}' branch='{branch}'")
        print(f"    {line[:160]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

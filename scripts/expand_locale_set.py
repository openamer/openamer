"""Expand OpenAmer's locale set from 41 curated languages to every ISO 639-1 code.

Two things have to stay in lockstep or the suite goes red:

  * ``agent/i18n.py:SUPPORTED_LANGUAGES`` -- the advertised list the CLI, the
    gateway and the desktop read.
  * ``locales/<code>.yaml`` -- one catalog per advertised language; a test
    asserts every advertised code has a file.

This script adds the missing languages to both, writing each new catalog as a
copy of en.yaml so nothing is ever blank. That copy is *not* a translation: the
gap detector in scripts/i18n_fill_cli_locales.py counts a value identical to
English as untranslated, so the honest state ("declared, not yet translated")
is visible instead of looking done.

Idempotent: re-running only adds what is missing.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LANGS = REPO / "locales" / "_languages.json"
I18N = REPO / "agent" / "i18n.py"
LOCALES = REPO / "locales"
EN = LOCALES / "en.yaml"


def main() -> int:
    names: dict[str, str] = json.loads(LANGS.read_text(encoding="utf-8"))
    codes = list(names.keys())

    src = I18N.read_text(encoding="utf-8")
    m = re.search(r"SUPPORTED_LANGUAGES: tuple\[str, \.\.\.\] = \(\n(.*?)\n\)\n", src, re.S)
    if not m:
        print("could not find SUPPORTED_LANGUAGES tuple", file=sys.stderr)
        return 2

    # Keep the intentionally non-ISO Torbeski application locale in the
    # declared set.  It has no ISO 639 code, so treating only two-letter codes
    # as valid makes every idempotence check try to add it again.
    current = re.findall(r'"([a-z]{2}(?:-[a-z]{4})?|torbeski)"', m.group(1))
    added = [c for c in codes if c not in current]
    removed = [c for c in current if c not in codes]
    print(f"declared before : {len(current)}")
    print(f"target set      : {len(codes)}")
    print(f"to add          : {len(added)}  {' '.join(added[:20])}{' ...' if len(added) > 20 else ''}")
    if removed:
        print(f"WARNING would drop: {' '.join(removed)}")

    # Re-emit the tuple, 5 codes per line, in the JSON's order. Only write when
    # it actually differs -- rewriting an identical file churns line endings and
    # makes an idempotent run look like a change.
    lines = []
    for i in range(0, len(codes), 5):
        chunk = ", ".join(f'"{c}"' for c in codes[i:i + 5])
        lines.append(f"    {chunk},")
    new_block = "SUPPORTED_LANGUAGES: tuple[str, ...] = (\n" + "\n".join(lines) + "\n)\n"
    if new_block == m.group(0):
        print(f"{I18N.name} already up to date")
    else:
        I18N.write_text(src[:m.start()] + new_block + src[m.end():],
                        encoding="utf-8", newline="\n")
        print(f"rewrote {I18N.name}")

    en_text = EN.read_text(encoding="utf-8")
    created = 0
    for code in codes:
        if code == "en":
            continue
        path = LOCALES / f"{code}.yaml"
        if path.exists():
            continue
        header = (
            f"# OpenAmer static-message catalog -- {names[code]} ({code})\n"
            "# Placeholder catalog: every value is still the English source text.\n"
            "# Run scripts/i18n_fill_cli_locales.py " + code + " to translate it.\n\n"
        )
        body = en_text.split("\n\n", 1)[1] if "\n\n" in en_text else en_text
        path.write_text(header + body, encoding="utf-8", newline="\n")
        created += 1
    print(f"created catalogs : {created}")
    print(f"total catalogs   : {len(list(LOCALES.glob('*.yaml')))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

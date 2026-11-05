#!/usr/bin/env python3
"""Fill the plural-word table with the base words of the suffix pairs.

The English source contains two shapes of plural ternary:

    ${count === 1 ? 'message' : 'messages'}    full word pair
    ${count} model${count === 1 ? '' : 's'}      suffix pair

For the suffix pair the base word ("model") sits in front of the
interpolation. The word table needs that base word, otherwise the ternary
cannot be translated.

This script adds the missing base words to scripts/i18n_plural_words.json
by asking the model for the singular/plural form of the English word.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from i18n_translate_locale import (  # noqa: E402
    BACKENDS,
    LANGUAGE_NAMES,
    load_env,
    translate_batch,
)

TABLE = REPO / "scripts" / "i18n_plural_words.json"


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python i18n_fill_plural_words.py <locale> [locale ...]")
        return 1
    table = json.loads(TABLE.read_text(encoding="utf-8"))
    env = load_env()
    # the base words that are missing from every locale's table
    base_words = [
        "Subagent", "attachment", "change", "commit", "finding", "line",
        "model", "pet", "result", "subagent", "tool",
    ]
    for locale in sys.argv[1:]:
        language = LANGUAGE_NAMES.get(locale, locale)
        entries = table.get(locale, {})
        need = [w for w in base_words if w not in entries]
        if not need:
            print(f"{locale}: complete")
            continue
        items = [f"{w}:::{w}s" for w in need]
        result = None
        for backend in BACKENDS:
            result = translate_batch(items, language, backend, env)
            if result is not None:
                break
        if result is None:
            print(f"{locale}: FAILED")
            continue
        added = 0
        for w, out in zip(need, result):
            if ":::" not in out:
                continue
            s, p = out.split(":::", 1)
            entries[w] = [s.strip(), p.strip()]
            added += 1
        table[locale] = entries
        print(f"{locale}: +{added} base words")
        TABLE.write_text(json.dumps(table, ensure_ascii=False, indent=1) + "\n",
                         encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

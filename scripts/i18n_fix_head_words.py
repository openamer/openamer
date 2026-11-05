#!/usr/bin/env python3
"""Fix the overlay strings the model keeps in English.

A handful of labels are built around a single English word and an
interpolation:

    Model · ${provider}: ${model}
    Backend v${version}
    SSH: ${host}

The model translates the sentence around the interpolation but leaves the
head word in English ("Model" stays "Model" in Slovak, Turkish and Dutch).
This script asks the model for the head word alone — one short word, no
interpolation — and substitutes it.

The word list is the set of head words that survive untranslated.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OVERLAYS = REPO / "scripts" / "i18n_overlays"
SPECIAL = REPO / "scripts" / "i18n_special_words.json"

sys.path.insert(0, str(REPO / "scripts"))

from i18n_translate_locale import (  # noqa: E402
    BACKENDS,
    LANGUAGE_NAMES,
    load_env,
    translate_batch,
)

# The English head word -> the key it belongs to
HEAD_WORDS = {
    "Model": "shell.statusbar.modelTitle",
    "Backend": "shell.statusbar.backendVersion",
    "backend": "shell.statusbar.backendLabel",
    "client": "shell.statusbar.clientLabel",
}


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python i18n_fix_head_words.py <locale> [locale ...]")
        return 1
    env = load_env()
    special = json.loads(SPECIAL.read_text(encoding="utf-8"))
    for locale in sys.argv[1:]:
        path = OVERLAYS / f"{locale}.json"
        if not path.exists():
            continue
        overlay = json.loads(path.read_text(encoding="utf-8"))
        # the head word of every special string that is still English
        need = []
        for key, value in list(overlay.items()):
            for word in HEAD_WORDS:
                if re.search(rf"\b{re.escape(word)}\b", value):
                    need.append((key, word))
                    break
        if not need:
            continue
        language = LANGUAGE_NAMES.get(locale, locale)
        # ask for the word alone, in a list, so the model cannot get lost in
        # the surrounding sentence
        words = sorted({w for _, w in need})
        result = None
        for backend in BACKENDS:
            result = translate_batch(words, language, backend, env)
            if result is not None:
                break
        if result is None:
            print(f"{locale}: FAILED")
            continue
        mapping = dict(zip(words, result))
        n = 0
        for key, word in need:
            translated = mapping.get(word, "").strip()
            if not translated or translated.lower() == word.lower():
                continue
            overlay[key] = re.sub(rf"\b{re.escape(word)}\b", translated, overlay[key])
            n += 1
        path.write_text(json.dumps(overlay, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8", newline="\n")
        print(f"{locale}: {n} head words translated")
    return 0


if __name__ == "__main__":
    sys.exit(main())

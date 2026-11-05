#!/usr/bin/env python3
"""Build the plural-word table for every locale.

The translation model will not translate the words inside a ternary:

    ${count} ${count === 1 ? 'message' : 'messages'}

It treats the interpolation as code and returns the English source. So the
words are collected separately and translated as a plain list of English
words — the model has no reason to refuse those.

The result is written to scripts/i18n_plural_words.json and consumed by
i18n_build_overlays.py.
"""
from __future__ import annotations

import json
import re
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

TERNARY = re.compile(r"\? '([^']*)' : '([^']*)'")
OUT = REPO / "scripts" / "i18n_plural_words.json"


def collect_pairs() -> list[tuple[str, str]]:
    """Every (singular, plural) pair that appears inside a ternary in en.ts.

    Two shapes occur:
      ${count === 1 ? 'message' : 'messages'}   -> a full word pair
      ${count === 1 ? '' : 's'}                  -> a suffix pair; the
                                                  word itself sits in front
                                                  of the interpolation
                                                  ('model' + 's')
    For the second shape we recover the base word from the text before the
    interpolation, so the model gets a real word to translate.
    """
    en = json.loads((REPO / "tmp" / "i18n_en.json").read_text(encoding="utf-8"))
    pairs: dict[tuple[str, str], None] = {}
    for leaf in en["leaves"]:
        if leaf["kind"] not in ("string", "func"):
            continue
        text = leaf["text"]
        for m in TERNARY.finditer(text):
            s, p = m.group(1), m.group(2)
            # The suffix pair can appear in two shapes:
            #   ${count} model${count === 1 ? '' : 's'}   empty singular
            #   ${count} log entr${count === 1 ? 'y' : 'ies'}  the "y" of
            #      "entry" is the singular suffix, so the singular is "y"
            #      and the plural is "ies"
            # In both cases the base word sits in front of the
            # interpolation that contains this ternary.
            if s in ("", "y") and p in ("s", "ies"):
                interp_start = text.rfind("${", 0, m.start())
                if interp_start < 0:
                    continue
                before = text[:interp_start]
                base = re.search(r"([A-Za-z]+)\s*$", before)
                if not base:
                    continue
                stem = base.group(1)
                if p == "ies":
                    # "entr" + "y"/"ies" is the English word
                    # "entry"/"entries": the "y" was consumed by the suffix
                    # rule and is missing from the text. Put it back, so the
                    # model sees the real English word.
                    pairs[(stem + "y", stem + "ies")] = None
                else:
                    pairs[(stem, stem + "s")] = None
                continue
            pairs[(s, p)] = None
    return sorted(pairs)


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python i18n_build_plural_words.py <locale> [locale ...]")
        return 1
    pairs = collect_pairs()
    print(f"{len(pairs)} distinct ternary pairs")
    env = load_env()
    table: dict[str, dict[str, list[str]]] = {}
    outfile = OUT
    if outfile.exists():
        table = json.loads(outfile.read_text(encoding="utf-8"))

    for locale in sys.argv[1:]:
        language = LANGUAGE_NAMES.get(locale, locale)
        # ask for the pair in one string: "singular:::plural"
        items = [f"{s}:::{p}" for s, p in pairs]
        result = None
        for backend in BACKENDS:
            result = translate_batch(items, language, backend, env)
            if result is not None:
                break
        if result is None:
            print(f"{locale}: FAILED")
            continue
        table[locale] = {}
        for (s, p), out in zip(pairs, result):
            if ":::" not in out:
                continue
            ts, tp = out.split(":::", 1)
            # An empty singular means the plural is formed by a suffix
            # ('model' -> 'models'). The model has no word to translate, so
            # it echoes the English suffix — that is wrong for every
            # language that does not use the "s" suffix. The suffix is
            # handled by the plural rule of the target language instead.
            if not s:
                continue
            table[locale][s] = [ts.strip(), tp.strip()]
        print(f"{locale}: {len(table[locale])}/{len(pairs)} pairs")
        outfile.write_text(json.dumps(table, ensure_ascii=False, indent=1) + "\n",
                           encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

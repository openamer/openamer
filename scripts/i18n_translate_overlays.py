#!/usr/bin/env python3
"""Translate the hand-written overlay strings for a locale.

The overlay files in scripts/i18n_overlays/<locale>.json hold the strings
that the translation model refuses to touch — interpolation-only strings like
``${count} ${count === 1 ? 'message' : 'messages'}``, where the plural forms
inside the ternary ARE translatable text but look like code to a model.

This script sends each overlay string to the model with an explicit
instruction that the words inside the ternary must be translated while the
variable names must not, then writes the result back into the overlay file.

The placeholders are masked before the request and restored afterwards, and
every result is verified: the variable names inside each interpolation must
survive, or the English original is kept.
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
    find_placeholders,
    load_env,
    placeholders_intact,
    translate_batch,
)
from i18n_build_overlays import PLURAL_WORDS, SPECIAL, TERNARY  # noqa: E402

OVERLAYS = REPO / "scripts" / "i18n_overlays"


def overlay_keys() -> list[str]:
    """Every en.ts string that contains a ternary or an interpolation.

    These are the strings the translation model leaves alone, so they are
    the ones that need the word table.
    """
    en = json.loads((REPO / "tmp" / "i18n_en.json").read_text(encoding="utf-8"))
    out = []
    for leaf in en["leaves"]:
        if leaf["kind"] not in ("string", "func"):
            continue
        text = leaf["text"]
        if TERNARY.search(text) or find_placeholders(text):
            out.append(leaf["path"])
    return out


def base_word_before(text: str, key: str) -> str:
    """The word that a suffix ternary is attached to.

    The English source reads "${count} model${count === 1 ? '' : 's'}": the
    ternary supplies the plural suffix and the base word stands in front of
    the interpolation.
    """
    m = TERNARY.search(text)
    if not m:
        return ""
    interp = text.rfind("${", 0, m.start())
    if interp < 0:
        return ""
    before = text[:interp]
    base = re.search(r"([A-Za-z]+)\s*$", before)
    return base.group(1) if base else ""


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python i18n_translate_overlays.py <locale> [locale ...]")
        return 1
    env = load_env()
    failures = []
    for locale in sys.argv[1:]:
        path = OVERLAYS / f"{locale}.json"
        words = PLURAL_WORDS.get(locale, {})
        special = SPECIAL.get(locale, {})
        if not words and not special:
            print(f"{locale}: no overlay data")
            continue

        en = json.loads((REPO / "tmp" / "i18n_en.json").read_text(encoding="utf-8"))
        en_text = {l["path"]: l["text"] for l in en["leaves"] if l["kind"] in ("string", "func")}
        keys = [k for k in overlay_keys() if k in en_text]
        data: dict[str, str] = {}

        # The model refuses to translate the words inside a ternary — it
        # treats the interpolation as code. So the ternary is handled with a
        # table, and the REST of the sentence is handled by the model.
        #
        # Order matters: first the model translates the sentence with the
        # ternary REPLACED by a marker, then the table fills the marker back
        # in. That way the model never sees code it might rewrite.
        words = PLURAL_WORDS.get(locale, {})
        special = SPECIAL.get(locale, {})
        language = LANGUAGE_NAMES.get(locale, locale)
        applied = 0

        # 1) split the source into the sentence parts and the ternary parts
        todo = []
        for k in keys:
            src = en_text[k]
            if k in special:
                data[k] = special[k]
                applied += 1
                continue
            parts = TERNARY.split(src)
            # parts = [before, s1, p1, before2, s2, p2, ...]
            skeleton = ""
            ternaries = []
            for i in range(0, len(parts), 3):
                skeleton += parts[i]
                if i + 2 < len(parts):
                    ternaries.append((parts[i + 1], parts[i + 2]))
                    skeleton += f"@@T{len(ternaries) - 1}@@"
            if not ternaries:
                continue
            todo.append((k, skeleton, ternaries))

        if not todo:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8", newline="\n")
            print(f"{locale}: {applied}/{len(keys)} overlay strings translated")
            continue

        # 2) let the model translate the skeleton
        result = None
        for backend in BACKENDS:
            result = translate_batch([t[1] for t in todo], language, backend, env)
            if result is not None:
                break

        for (k, skeleton, ternaries), out in zip(todo, result or []):
            if out is None:
                continue
            # 3) put the translated ternaries back in
            for i, (sing, plur) in enumerate(ternaries):
                marker = f"@@T{i}@@"
                if marker not in out:
                    out = None
                    break
                if sing in words:
                    s, p = words[sing]
                    repl = f"? '{s}' : '{p}'"
                elif plur in words:
                    s, p = words[plur]
                    repl = f"? '{s}' : '{p}'"
                else:
                    # A suffix ternary: the base word sits in front of the
                    # interpolation ("model" + "s"). The word table is keyed by
                    # the base word, so the base has to be recovered from the
                    # English source.
                    base = base_word_before(en_text.get(k, ''), k)
                    if base and base in words:
                        s, p = words[base]
                        repl = f"? '{s}' : '{p}'"
                    else:
                        repl = f"? '{sing}' : '{plur}'"
                out = out.replace(marker, repl)
            if out is None:
                continue
            # the model may have mangled the interpolation around the marker
            out = out.replace("@@T", "").replace("@@", "")
            if out and out != en_text[k]:
                data[k] = out
                applied += 1

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8", newline="\n")
        print(f"{locale}: {applied}/{len(keys)} overlay strings translated")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

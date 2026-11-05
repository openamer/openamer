#!/usr/bin/env python3
"""Translate the last English leftovers of a locale.

The bulk translation run leaves a handful of strings in English: sentences
built around an interpolation ("Show ${count} more in ${label}") and short
labels ("Model · ${provider}: ${model}"). The model handles those, but only
when it is asked for exactly that string — the big batches drown them.

This script collects the English leftovers of one locale, sends them as a
single batch and writes the result back into the translation table.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TMP = REPO / "tmp"
sys.path.insert(0, str(REPO / "scripts"))

from i18n_translate_locale import (  # noqa: E402
    BACKENDS,
    LANGUAGE_NAMES,
    find_placeholders,
    load_env,
    placeholders_intact,
    translate_batch,
)

# Strings that are the same in every language and must stay English.
SKIP = {
    "MCP", "OpenAmer", "Telegram", "Discord", "Slack", "YOLO", "URL", "SSH",
    "Email", "Manual", "Auto", "Hub", "Cron", "Webhooks", "Pro",
}


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python i18n_translate_leftovers.py <locale> [locale ...]")
        return 1
    en = json.loads((TMP / "i18n_en.json").read_text(encoding="utf-8"))
    en_text = {l["path"]: l["text"] for l in en["leaves"] if l["kind"] in ("string", "func")}
    env = load_env()

    for locale in sys.argv[1:]:
        f = TMP / f"i18n_{locale}_translations.json"
        if not f.exists():
            print(f"{locale}: no table")
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        left = []
        for k, v in en_text.items():
            if k not in d:
                continue
            if d[k] != v:
                continue
            t = v.strip()
            if not t or t in SKIP:
                continue
            if t.startswith("http") or t.startswith("@"):
                continue
            # only sentences: something around the interpolation
            rest = t
            for _, _, ph in find_placeholders(t):
                rest = rest.replace(ph, "")
            if not rest.strip(" .·:—…"):
                # nothing but the interpolation — a label the model refuses
                continue
            left.append(k)
        if not left:
            print(f"{locale}: nothing left")
            continue

        language = LANGUAGE_NAMES.get(locale, locale)
        items = [en_text[k] for k in left]
        result = None
        for backend in BACKENDS:
            result = translate_batch(items, language, backend, env)
            if result is not None:
                break
        if result is None:
            print(f"{locale}: FAILED ({len(left)} strings)")
            continue

        applied = 0
        for k, src, out in zip(left, items, result):
            if not out or not out.strip():
                continue
            if not placeholders_intact(src, out):
                continue
            d[k] = out
            applied += 1
        f.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
        print(f"{locale}: {applied}/{len(left)} leftovers translated")
    return 0


if __name__ == "__main__":
    sys.exit(main())

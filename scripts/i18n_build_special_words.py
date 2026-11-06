#!/usr/bin/env python3
"""Generate the SPECIAL overlay strings for every locale.

The SPECIAL strings are the UI labels that consist mostly of an
interpolation ('${count} actions', 'Version ${value}', …). The translation
model handles them, because they contain no ternary — the ternary case is
what i18n_build_plural_words.py covers.

The result is written to scripts/i18n_special_words.json and consumed by
i18n_build_overlays.py.
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

OUT = REPO / "scripts" / "i18n_special_words.json"

SPECIAL_KEYS = [
    "settings.about.version",
    "agents.durationSeconds",
    "agents.durationMinutes",
    "commandCenter.actions",
    "composer.images",
    "composer.url",
    "shell.statusbar.desktopVersion",
    "shell.statusbar.clientLabel",
    "shell.statusbar.backendVersion",
    "shell.statusbar.backendLabel",
    "shell.statusbar.providerModelTitle",
    "shell.statusbar.modelTitle",
    "shell.statusbar.connectionSsh",
    "zones.zoneTag",
    "zones.zoneCount",
    "assistant.tool.titleTemplates.actionCommand",
    "assistant.tool.titleTemplates.actionQuoted",
    "assistant.tool.titleTemplates.actionTarget",
    "assistant.tool.titleTemplates.prefixedDone",
    "sidebar.showMoreIn",
    "settings.gateway.sshHostTitle",
    "settings.gateway.sshHostPickTitle",
    "commandCenter.sections.system",
]


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python i18n_build_special_words.py <locale> [locale ...]")
        return 1
    en = json.loads((REPO / "tmp" / "i18n_en.json").read_text(encoding="utf-8"))
    en_text = {l["path"]: l["text"] for l in en["leaves"] if l["kind"] in ("string", "func")}
    items = [en_text[k] for k in SPECIAL_KEYS]
    env = load_env()
    table: dict[str, dict[str, str]] = {}
    if OUT.exists():
        table = json.loads(OUT.read_text(encoding="utf-8"))

    for locale in sys.argv[1:]:
        language = LANGUAGE_NAMES.get(locale, locale)
        result = None
        for backend in BACKENDS:
            result = translate_batch(items, language, backend, env)
            if result is not None:
                break
        if result is None:
            print(f"{locale}: FAILED")
            continue
        table[locale] = {}
        for k, out in zip(SPECIAL_KEYS, result):
            if out and out.strip():
                table[locale][k] = out
        print(f"{locale}: {len(table[locale])}/{len(SPECIAL_KEYS)} special strings")
        OUT.write_text(json.dumps(table, ensure_ascii=False, indent=1) + "\n",
                       encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

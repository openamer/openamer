#!/usr/bin/env python3
"""Translate the overlay strings the model refuses to touch.

A few strings defeat the model no matter how often they are asked for —
"Show ${count} more in ${label}" has three interpolations and the model
returns it unchanged. This script asks for the sentence WITHOUT the
interpolations (the mask hides them anyway) and with an explicit
instruction to translate the words around them.

The result is written into the overlay files, so it survives into the
locale.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OVERLAYS = REPO / "scripts" / "i18n_overlays"

sys.path.insert(0, str(REPO / "scripts"))

from i18n_translate_locale import (  # noqa: E402
    BACKENDS,
    LANGUAGE_NAMES,
    find_placeholders,
    load_env,
    placeholders_intact,
    translate_batch,
)

# The strings that stay English in the overlay although they are not
# proper nouns. The value is the English source.
STUBBORN = {
    "sidebar.showMoreIn": "Show ${count} more in ${label}",
    "shell.statusbar.desktopVersion": "OpenAmer Desktop v${version}",
    "shell.statusbar.backendVersion": "Backend v${version}",
    "shell.statusbar.backendLabel": "backend v${version}",
    "shell.statusbar.clientLabel": "client v${version}",
    "settings.gateway.sshHostTitle": "Host",
    "settings.gateway.sshHostPickTitle": "Host",
    "commandCenter.sections.system": "System",
    "settings.modeOptions.system.label": "System",
    "shell.gatewayMenu.gateway": "Gateway",
    "shell.gatewayMenu.offline": "Offline",
    "shell.approvalMode.smart": "Smart",
    "shell.approvalMode.manual": "Manual",
    "artifacts.colLocationLink": "URL",
    "composer.url": "URL…",
}


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python i18n_fix_stubborn.py <locale> [locale ...]")
        return 1
    env = load_env()
    for locale in sys.argv[1:]:
        path = OVERLAYS / f"{locale}.json"
        if not path.exists():
            continue
        overlay = json.loads(path.read_text(encoding="utf-8"))
        need = [k for k, src in STUBBORN.items()
                if overlay.get(k) == src and k in overlay]
        if not need:
            continue
        language = LANGUAGE_NAMES.get(locale, locale)
        items = [STUBBORN[k] for k in need]
        result = None
        for backend in BACKENDS:
            result = translate_batch(items, language, backend, env)
            if result is not None:
                break
        if result is None:
            print(f"{locale}: FAILED")
            continue
        n = 0
        for k, src, out in zip(need, items, result):
            if not out or not out.strip():
                continue
            if out == src:
                continue
            if not placeholders_intact(src, out):
                continue
            overlay[k] = out
            n += 1
        path.write_text(json.dumps(overlay, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8", newline="\n")
        print(f"{locale}: {n}/{len(need)} stubborn strings translated")
    return 0


if __name__ == "__main__":
    sys.exit(main())

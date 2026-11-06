#!/usr/bin/env python3
"""Generate the per-locale FIELD_LABELS / FIELD_DESCRIPTIONS.

The desktop locales reference two constants that live outside the locale
files:

    import { FIELD_DESCRIPTIONS, FIELD_LABELS } from '@/app/settings/constants'

    export const zh = defineLocale({
      settings: {
        fieldLabels: FIELD_LABELS,
        fieldDescriptions: FIELD_DESCRIPTIONS,
        ...

Those constants are English only. Every locale therefore shows English
labels in the settings panel, no matter which language is selected — that
is a real gap, not a cosmetic one.

This script extracts the field copy from the English source, translates it
for every locale and writes one module per locale:

    apps/desktop/src/i18n/field-copy/<locale>.ts

The locale file then imports its own copy instead of the English one.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DESKTOP = REPO / "apps" / "desktop"
CONSTANTS = DESKTOP / "src" / "app" / "settings" / "constants.ts"
OUT_DIR = DESKTOP / "src" / "i18n" / "field-copy"

sys.path.insert(0, str(REPO / "scripts"))

from i18n_translate_locale import (  # noqa: E402
    BACKENDS,
    LANGUAGE_NAMES,
    find_placeholders,
    load_env,
    placeholders_intact,
    translate_batch,
)


def extract_field_copy() -> dict[str, list[str]]:
    """Pull FIELD_LABELS and FIELD_DESCRIPTIONS out of constants.ts.

    The two constants are object literals; we read them with the TypeScript
    compiler so the nested structure survives.
    """
    src = CONSTANTS.read_text(encoding="utf-8")
    # find the two object literals by their export name
    out: dict[str, list[str]] = {}
    for name in ("FIELD_LABELS", "FIELD_DESCRIPTIONS"):
        m = re.search(
            r"export const " + name + r":[^=]*=\s*defineFieldCopy\(\{",
            src,
        )
        if not m:
            raise SystemExit(f"{name} not found in {CONSTANTS}")
        # brace matching from the opening '{'
        start = src.index("{", m.end() - 1)
        depth = 0
        i = start
        while i < len(src):
            c = src[i]
            if c == "'" or c == '"':
                q = c
                i += 1
                while i < len(src) and src[i] != q:
                    if src[i] == "\\":
                        i += 1
                    i += 1
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        body = src[start:i + 1]
        entries = parse_entries(body)
        # the first entry carries the root object as an empty prefix — drop it
        cleaned = []
        for k, v in entries:
            cleaned.append((k.lstrip("."), v))
        out[name] = cleaned
    return out


def parse_entries(body: str) -> list[tuple[str, str]]:
    """Return [(dotted.key, value)] from a field-copy object literal."""
    entries: list[tuple[str, str]] = []

    # walk the literal and track the nesting
    stack: list[str] = []
    i = 0
    pending_key = None
    while i < len(body):
        c = body[i]
        if c == "'" or c == '"':
            q = c
            j = i + 1
            buf = []
            while j < len(body) and body[j] != q:
                if body[j] == "\\":
                    nxt = body[j + 1]
                    buf.append({"n": "\n", "t": "\t", "\\": "\\", "'": "'", '"': '"'}.get(nxt, nxt))
                    j += 2
                    continue
                buf.append(body[j])
                j += 1
            value = "".join(buf)
            if pending_key is not None:
                entries.append((".".join(stack + [pending_key]), value))
                pending_key = None
            i = j + 1
            continue
        if c == "{":
            stack.append(pending_key or "")
            pending_key = None
            i += 1
            continue
        if c == "}":
            if stack:
                stack.pop()
            i += 1
            continue
        m = re.match(r"([A-Za-z_$][A-Za-z0-9_$]*)\s*:", body[i:])
        if m:
            pending_key = m.group(1)
            i += len(m.group(0))
            continue
        i += 1
    return entries


def render_nested(pairs: dict[str, str], indent: int) -> list[str]:
    """Render flat dotted keys as a nested object literal.

    "display.showReasoning" becomes
        display: {
          showReasoning: '…',
        },
    """
    tree: dict = {}
    for key, value in pairs.items():
        parts = key.split(".")
        node = tree
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value

    pad = " " * indent

    def emit(node: dict, depth: int) -> list[str]:
        out = []
        inner = " " * (depth + 2)
        for k, v in node.items():
            if isinstance(v, dict):
                out.append(f"{inner}{k}: {{")
                out.extend(emit(v, depth + 2))
                out.append(f"{inner}}},")
            else:
                out.append(f"{inner}{k}: {json.dumps(v, ensure_ascii=False)},")
        return out

    return emit(tree, indent)


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python i18n_build_field_copy.py <locale> [locale ...]")
        return 1
    field_copy = extract_field_copy()
    labels = field_copy["FIELD_LABELS"]
    descriptions = field_copy["FIELD_DESCRIPTIONS"]
    print(f"FIELD_LABELS: {len(labels)} entries")
    print(f"FIELD_DESCRIPTIONS: {len(descriptions)} entries")

    env = load_env()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for locale in sys.argv[1:]:
        language = LANGUAGE_NAMES.get(locale, locale)
        translated: dict[str, dict[str, str]] = {}
        for name, entries in (("FIELD_LABELS", labels),
                              ("FIELD_DESCRIPTIONS", descriptions)):
            items = [v for _, v in entries]
            result = None
            for backend in BACKENDS:
                result = translate_batch(items, language, backend, env)
                if result is not None:
                    break
            if result is None:
                print(f"{locale}: FAILED ({name})")
                continue
            pairs = {}
            for (k, src), out in zip(entries, result):
                if out and out.strip():
                    pairs[k] = out
            translated[name] = pairs
        if len(translated) != 2:
            continue

        # The keys are dotted paths into a nested object; the flat key
        # "display.showReasoning" has to become
        #   display: { showReasoning: '…' }
        lines = [
            "// Generated by scripts/i18n_build_field_copy.py — do not edit.",
            "//",
            "// The English field copy lives in src/app/settings/constants.ts.",
            f"// This module is its localized counterpart for the {language} locale.",
            "",
            "import { defineFieldCopy } from '@/app/settings/field-copy'",
            "",
        ]
        for name in ("FIELD_LABELS", "FIELD_DESCRIPTIONS"):
            pairs = translated[name]
            lines.append(f"export const {name}: Record<string, string> = defineFieldCopy({{")
            lines.extend(render_nested(pairs, 2))
            lines.append("})")
            lines.append("")
        out_file = OUT_DIR / f"{locale}.ts"
        out_file.write_text("\n".join(lines), encoding="utf-8", newline="\n")
        print(f"{locale}: wrote {out_file.name} "
              f"({len(translated['FIELD_LABELS'])} labels, "
              f"{len(translated['FIELD_DESCRIPTIONS'])} descriptions)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

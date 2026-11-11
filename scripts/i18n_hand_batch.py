#!/usr/bin/env python3
"""Batch helper for hand translation of desktop locales.

The agent translates the strings itself; this helper only does the mechanical
work that must be exact:

  dump   <locale> <n>   print the next n untranslated English strings as JSON
  merge  <locale> <f>   validate a chunk of translations and merge into the cache
  stat   <locale>       report how many strings remain

Placeholder safety is enforced on merge: every ``${...}`` in the English source
must appear verbatim in the translation, otherwise the entry is rejected and the
English text is kept.  That is the same contract scripts/i18n_translate_locale.py
enforces, so a hand-translated catalog cannot be worse than a model-translated
one.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
I18N = REPO / "apps" / "desktop" / "src" / "i18n"
TMP = REPO / "tmp"


def find_placeholders(text: str) -> list[str]:
    """Return every ${...} in text, brace-counted (nested interpolations)."""
    out: list[str] = []
    i = 0
    while True:
        start = text.find("${", i)
        if start < 0:
            break
        depth = 0
        j = start
        closed = False
        while j < len(text):
            if text.startswith("${", j):
                depth += 1
                j += 2
                continue
            if text[j] == "}":
                depth -= 1
                if depth == 0:
                    j += 1
                    closed = True
                    break
            j += 1
        if not closed:
            out.append(text[start:])
            break
        out.append(text[start:j])
        i = j
    return out


def load_en() -> dict[str, str]:
    path = TMP / "i18n_en.json"
    if not path.exists():
        subprocess.run(
            ["node", str(REPO / "scripts" / "i18n_extract_locale.mjs"),
             str(I18N / "en.ts"), str(path)],
            check=True, cwd=str(REPO), capture_output=True, text=True,
        )
    leaves = json.loads(path.read_text(encoding="utf-8"))["leaves"]
    return {l["path"]: l["text"] for l in leaves if l["kind"] in ("string", "func")}


def cache_path(locale: str) -> Path:
    return TMP / f"i18n_{locale}_translations.json"


def load_cache(locale: str) -> dict[str, str]:
    p = cache_path(locale)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return {k: v for k, v in data.items() if isinstance(v, str)}
    except json.JSONDecodeError:
        return {}


def remaining(locale: str) -> list[str]:
    """Paths that still need a decision from the translator.

    Presence in the cache counts as done. A hand translation deliberately leaves
    proper nouns ("MCP", "OpenAmer", "Theme") byte-identical to English, so
    comparing against the English text would re-emit them forever.
    """
    en = load_en()
    done = load_cache(locale)
    out = []
    for path, text in en.items():
        if not text.strip():
            continue
        if path in done:
            if find_placeholders(text) == find_placeholders(done[path]):
                continue
        out.append(path)
    return out


def cmd_dump(locale: str, n: int) -> int:
    en = load_en()
    todo = remaining(locale)[:n]
    rows = [{"p": p, "t": en[p]} for p in todo]
    print(json.dumps(rows, ensure_ascii=False, indent=0))
    print(f"# {len(rows)} of {len(remaining(locale))} remaining", file=sys.stderr)
    return 0


def cmd_merge(locale: str, chunk_file: str) -> int:
    en = load_en()
    data = json.loads(Path(chunk_file).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        print("chunk must be an object {path: translation}", file=sys.stderr)
        return 2
    merged = load_cache(locale)
    accepted = rejected = 0
    for path, text in data.items():
        if path not in en:
            print(f"  REJECT unknown key {path}")
            rejected += 1
            continue
        if not isinstance(text, str) or not text.strip():
            print(f"  REJECT empty {path}")
            rejected += 1
            continue
        src_ph = find_placeholders(en[path])
        tgt_ph = find_placeholders(text)
        if src_ph != tgt_ph:
            print(f"  REJECT placeholder drift {path}: {src_ph} -> {tgt_ph}")
            rejected += 1
            continue
        if text.strip() == en[path].strip():
            pass  # legitimate for proper nouns; keep it, it still counts as done
        merged[path] = text
        accepted += 1
    cache_path(locale).write_text(
        json.dumps(merged, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"{locale}: accepted {accepted}, rejected {rejected}, "
          f"cache now {len(merged)}, remaining {len(remaining(locale))}")
    return 0 if rejected == 0 else 1


def cmd_stat(locale: str) -> int:
    en = load_en()
    print(f"{locale}: {len(en)} translatable strings, {len(remaining(locale))} remaining")
    return 0


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2
    cmd = sys.argv[1]
    if cmd == "dump":
        return cmd_dump(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 200)
    if cmd == "merge":
        return cmd_merge(sys.argv[2], sys.argv[3])
    if cmd == "stat":
        return cmd_stat(sys.argv[2])
    print(f"unknown command {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())

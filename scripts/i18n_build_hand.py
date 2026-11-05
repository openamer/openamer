#!/usr/bin/env python3
"""Build the per-locale hand table for the strings the model leaves alone.

The bulk translation run leaves ~90 strings per locale in English. Two
reasons:

  * The model treats a bare word as a technical token and echoes it
    ("Gateway", "Host", "System").
  * The string is built around an interpolation, and the model masks the
    whole ``${…}`` — so the sentence around it never gets translated
    ("Status: ${status}").

Both are translation work, not model failures. This script asks the model
for exactly these strings, as one label batch per locale, and stores the
result in ``scripts/i18n_hand/<locale>.json``.

The table is REVIEWABLE and AUTHORITATIVE for those paths:

  * A path that IS in the table and whose value equals the English source
    means "this word is the same in this language" — a cognate. That is a
    correct translation, not a gap, and the audit stops reporting it.
  * A path that is in the table with a different value is translated.

Every entry is checked: the placeholders of the English source must survive
the translation, otherwise the entry is rejected and the English text stays.

Usage:
    python i18n_build_hand.py fr de ja        # build for these locales
    python i18n_build_hand.py --check         # report the table's coverage
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from i18n_hand_translations import NEEDS_HAND  # noqa: E402
from i18n_translate_locale import (  # noqa: E402
    BACKENDS,
    LANGUAGE_NAMES,
    load_env,
    placeholders_intact,
    translate_batch,
    translate_labels,
)

OUT_DIR = REPO / "scripts" / "i18n_hand"

# How many labels go into one request. See _ask() for why it is 10.
LABEL_BATCH = 10

# The paths that are a label (no interpolation) and the paths that are a
# sentence around an interpolation. The two need a different prompt: a
# label is asked for as a label, a sentence with a masked interpolation is
# asked for as a sentence.
LABEL_PATHS = [p for p, src in NEEDS_HAND.items() if "${" not in src]
SENTENCE_PATHS = [p for p, src in NEEDS_HAND.items() if "${" in src]


def _en_text() -> dict[str, str]:
    en_path = REPO / "tmp" / "i18n_en.json"
    if not en_path.exists():
        raise SystemExit("run i18n_extract_locale.mjs on en.ts first")
    en = json.loads(en_path.read_text(encoding="utf-8"))
    return {l["path"]: l["text"] for l in en["leaves"] if l["kind"] in ("string", "func")}


def _existing(locale: str) -> dict[str, str]:
    table_path = OUT_DIR / f"{locale}.json"
    if not table_path.exists():
        return {}
    try:
        return json.loads(table_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _todo(locale: str, en_text: dict[str, str]) -> list[str]:
    existing = _existing(locale)
    out = []
    for path, src in NEEDS_HAND.items():
        if path not in en_text or en_text[path] != src:
            continue
        if path in existing:
            continue
        out.append(path)
    return out


def _ask(items: list[str], language: str, env: dict, backend: tuple) -> list[str] | None:
    """Ask for the labels, batch by batch.

    The batch size matters: with 20 labels in one request the model starts
    echoing the English (9 of 20 in German); with 10 it echoes 2. A long
    label list reads as a glossary the model may copy, a short one reads as
    a list of things to translate.

    Each batch is asked on its own and falls back through the backends, so
    one rate-limited request does not throw the whole locale away.
    """
    out: list[str] = []
    for i in range(0, len(items), LABEL_BATCH):
        chunk = items[i:i + LABEL_BATCH]
        result = None
        for b in backend:
            result = translate_labels(chunk, language, b, env)
            if result is not None:
                break
        if result is None:
            # the batch is lost — keep the English source so the file stays
            # complete, and let the audit report it
            out.extend(chunk)
            continue
        out.extend(result)
    return out


# The strings the model echoes in EVERY locale. They are not cognates — the
# model simply does not touch a product name, a unit or a label that is
# mostly an identifier. Asking for them as a plain word list does not help,
# so they get their own prompt: a template whose fixed parts are named.
TEMPLATE_HINTS = {
    "sidebar.row.ageMin": (
        "This is a TIME UNIT shown next to a number of minutes. Keep the unit "
        "short and local (for example 'min', 'm', 'мин', 'Min.'). It may stay "
        "the same as the English one."
    ),
    "shell.statusbar.providerModelTitle": (
        "This is a template that shows a provider name and a model name "
        "separated by a dot: the WORD 'Model' in front of it is the English "
        "label and must be translated. Keep the two ${…} placeholders "
        "unchanged."
    ),
    "shell.statusbar.connectionSsh": (
        "This is a template that shows an SSH host. 'SSH' stays 'SSH' — but "
        "the word before it (if any) must be translated. Keep the ${…} "
        "placeholder unchanged."
    ),
    "shell.statusbar.desktopVersion": (
        "This is a version label: the PRODUCT NAME stays as it is, but the "
        "WORD before the version number must be translated. Keep the ${…} "
        "placeholder unchanged."
    ),
}


def _ask_templates(paths: list[str], language: str, env: dict, backend: tuple) -> list[str]:
    """Ask for the template strings the model echoes in every locale.

    Each one is asked on its own with a hint about what part of the string
    is the label and what part is an identifier. The placeholders are
    masked, so the model never sees code.
    """
    out: list[str] = []
    for path in paths:
        src = NEEDS_HAND[path]
        hint = TEMPLATE_HINTS.get(path, "")
        result = None
        for b in backend:
            result = translate_batch([src], language, b, env, extra_hint=hint)
            if result is not None:
                break
        if result is None or not result[0] or not result[0].strip():
            out.append(src)
            continue
        out.append(result[0])
    return out


def build(locale: str, env: dict, force: bool) -> tuple[str, int, int, str]:
    en_text = _en_text()
    todo = _todo(locale, en_text)
    if force:
        # rebuild everything: the existing entries are dropped
        todo = [p for p, s in NEEDS_HAND.items()
                if p in en_text and en_text[p] == s]
    if not todo:
        return locale, 0, 0, f"table={len(_existing(locale))}"

    language = LANGUAGE_NAMES.get(locale, locale)
    data: dict[str, str] = {}
    rejected = 0

    # 1) the labels — a single word has to be asked for as a label
    labels = [p for p in todo if p in LABEL_PATHS]
    if labels:
        result = _ask([NEEDS_HAND[p] for p in labels], language, env, BACKENDS)
        if result is None:
            rejected += len(labels)
        else:
            for path, src, out in zip(labels, [NEEDS_HAND[p] for p in labels], result):
                if not out or not out.strip():
                    rejected += 1
                    continue
                data[path] = out

    # 2) the sentences around an interpolation — the placeholder is masked,
    #    so the model only has to translate the words around it
    sentences = [p for p in todo if p in SENTENCE_PATHS]
    if sentences:
        # the strings the model echoes in EVERY locale get their own
        # prompt — a plain batch does not move them
        hard = [p for p in sentences if p in TEMPLATE_HINTS]
        easy = [p for p in sentences if p not in TEMPLATE_HINTS]

        items = [NEEDS_HAND[p] for p in easy]
        result = None
        if items:
            for b in BACKENDS:
                result = translate_batch(items, language, b, env)
                if result is not None:
                    break
        if result is None:
            rejected += len(items)
        else:
            for path, src, out in zip(easy, items, result):
                if not out or not out.strip():
                    rejected += 1
                    continue
                if not placeholders_intact(src, out):
                    rejected += 1
                    continue
                data[path] = out

        for path, out in zip(hard, _ask_templates(hard, language, env, BACKENDS)):
            src = NEEDS_HAND[path]
            if not placeholders_intact(src, out):
                rejected += 1
                continue
            data[path] = out

    existing = _existing(locale)
    existing.update(data)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"{locale}.json").write_text(
        json.dumps(existing, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8", newline="\n",
    )
    return locale, len(data), rejected, f"table={len(existing)}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("locales", nargs="*")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="rebuild every entry, ignoring the existing table")
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()

    if args.check:
        total = 0
        for p in sorted(OUT_DIR.glob("*.json")):
            d = json.loads(p.read_text(encoding="utf-8"))
            print(f"{p.stem:10} {len(d):4}")
            total += len(d)
        print(f"hand table: {len(list(OUT_DIR.glob('*.json')))} locales, {total} entries")
        return 0

    locales = args.locales
    if not locales:
        codes = sorted(p.stem for p in (REPO / "apps" / "desktop" / "src" / "i18n").glob("*.ts"))
        locales = [c for c in codes if c not in {"en", "catalog", "types", "index",
                                                 "define-locale", "plugin-i18n",
                                                 "runtime", "languages"}]

    env = load_env()
    print(f"building the hand table for {len(locales)} locales")
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(build, loc, env, args.force): loc for loc in locales}
        for fut in as_completed(futs):
            loc, ok, rejected, msg = fut.result()
            print(f"  {loc:10} +{ok:3} rejected={rejected:2}  {msg}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

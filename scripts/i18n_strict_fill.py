#!/usr/bin/env python3
"""Translate the last few REAL gaps of a locale, one short list at a time.

Why this exists: the batch translator marks a string done when the model returns
something different from English, and it deliberately does not push. Measured
2026-11-16, the converge loop reached `hy 98.6% -> 98.6%` and `ru -> +0.24`: the
remaining strings are short words (`size`, `name`, `optional`) that the model
answers in English, so a locale can sit at 99% forever.

This script runs the same batch machinery with `force_translate=True` and an
explicit hint, on the small set the audit considers a real gap, and writes the
accepted values into the locale cache. Delivery stays a separate step.

    python scripts/i18n_strict_fill.py el            # report + fill
    python scripts/i18n_strict_fill.py el --dry-run  # list the gaps only

Refuses (rather than inventing) when a placeholder would drift, when the reply is
empty, or when the model still answers English - that last case is a genuine
cognate and belongs in scripts/i18n_hand/<locale>.json, not in a translation.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import i18n_translate_locale as tr  # noqa: E402
from i18n_deliver_locales import extract, real_gaps  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parent.parent
TMP = REPO / "tmp"

HINT = ("Short interface text. Translate it into the target language even when it "
        "is a single common word (for example 'size', 'name', 'details'). Keep "
        "product names, identifiers and code unchanged.")


def gaps_of(locale: str) -> tuple[dict[str, str], list[str]]:
    en_text = extract("en") or {}
    return en_text, real_gaps(locale, en_text)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("locale")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=60)
    args = ap.parse_args()

    en_text, gaps = gaps_of(args.locale)
    gaps = gaps[: args.limit]
    print(f"{args.locale}: {len(gaps)} real gaps")
    if args.dry_run or not gaps:
        for path in gaps:
            print(f"  {path}: {en_text[path][:70]}")
        return 0

    language = tr.LANGUAGE_NAMES.get(args.locale, args.locale)
    env = tr.load_env()
    items = [en_text[p] for p in gaps]
    accepted: dict[str, str] = {}

    for backend in tr.BACKENDS:
        if backend[2] != "-" and not env.get(backend[2]):
            continue
        out = tr.translate_batch(items, language, backend, env,
                                 force_translate=True, extra_hint=HINT)
        if not out or len(out) != len(items):
            print(f"  [{backend[0]}] no usable reply", file=sys.stderr)
            continue
        for path, src, got in zip(gaps, items, out):
            if path in accepted or not got or got.strip() == src.strip():
                continue
            if not tr.placeholders_intact(src, got):
                print(f"  reject placeholder drift {path}", file=sys.stderr)
                continue
            accepted[path] = got
        if len(accepted) == len(gaps):
            break

    print(f"{args.locale}: accepted {len(accepted)}/{len(gaps)}")
    rejected = [p for p in gaps if p not in accepted]
    for path in rejected[:10]:
        print(f"  still English: {path} -> {en_text[path][:50]!r}")
    if not accepted:
        return 0

    cache = TMP / f"i18n_{args.locale}_translations.json"
    current = {}
    if cache.exists():
        try:
            current = json.loads(cache.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            current = {}
    current.update(accepted)
    cache.write_text(json.dumps(current, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"cache written: {cache.name} (+{len(accepted)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

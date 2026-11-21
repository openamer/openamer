#!/usr/bin/env python3
"""Fill the `intro` i18n section in every locale, one cache at a time.

The desktop intro copy (15 personalities x 5 lines x 2 fields + fallback +
persona-mode templates = 170 strings) used to live in a hardcoded English
JSONL file. It is now a normal i18n section, which means every locale needs it
translated or the picker promises a language the first screen does not deliver.

This script only touches `intro.*` keys: a locale that is otherwise partial
does not get 2000 unrelated strings pushed through the model, and a locale that
is already complete gains exactly the section that was missing.

    python scripts/i18n_fill_intro_all.py --dry-run
    python scripts/i18n_fill_intro_all.py --locales de,fr,tr
    python scripts/i18n_fill_intro_all.py --all --workers 4

Resumable: progress lands in tmp/intro_fill_progress.json, translations in
tmp/i18n_<locale>_translations.json, and a locale with zero remaining intro
gaps is skipped. Delivery into the locale module is a separate step
(`i18n_deliver_locales.py --deliver --only <locale>`), run by --deliver here.

torbeski is excluded on purpose: the user's native language strings come from
him, never from a model.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import threading
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import i18n_translate_locale as tr  # noqa: E402
from i18n_deliver_locales import extract  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parent.parent
TMP = REPO / "tmp"
PROGRESS = TMP / "intro_fill_progress.json"
PREFIX = "intro."
HINT = ("This is the greeting copy of a developer assistant's empty chat screen. "
        "Keep the tone, keep product names (OpenAmer) unchanged, and keep ${label} "
        "and other placeholders exactly as they are.")

# torbeski is the user's own language — his strings, not a model's.
SKIP = {"en", "torbeski"}

_print_lock = threading.Lock()
_deliver_lock = threading.Lock()


def deliver_one(locale: str) -> None:
    """Write the locale's cache into apps/desktop/src/i18n/<locale>.ts."""
    import subprocess
    with _deliver_lock:
        r = subprocess.run([sys.executable, str(REPO / "scripts/i18n_deliver_locales.py"),
                            "--deliver", "--only", locale],
                           cwd=REPO, capture_output=True, text=True, encoding="utf-8")
    state = "ok" if r.returncode == 0 else f"FAILED {r.stderr.strip()[-120:]}"
    log(f"deliver {locale}: {state}")


def log(msg: str) -> None:
    with _print_lock:
        print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def locales() -> list[str]:
    src = (REPO / "apps/desktop/src/i18n/languages.ts").read_text(encoding="utf-8")
    start = src.index("export const LOCALE_OPTIONS")
    body = src[start:]
    import re
    return re.findall(r"^\s*id: '([^']+)'", body, re.M)


def remaining(locale: str, en_intro: dict[str, str]) -> list[str]:
    """intro keys that are still English in the module or absent from both."""
    tgt = extract(locale) or {}
    cache_path = TMP / f"i18n_{locale}_translations.json"
    cache: dict[str, str] = {}
    if cache_path.is_file():
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            cache = {}
    out = []
    for path, english in en_intro.items():
        have = cache.get(path) or tgt.get(path)
        if not have or have.strip() == english.strip():
            out.append(path)
    return out


def fill(locale: str, en_intro: dict[str, str], batch_size: int, env: dict,
         only_model: str = "") -> tuple[int, int]:
    todo = remaining(locale, en_intro)
    if not todo:
        return 0, 0
    language = tr.LANGUAGE_NAMES.get(locale)
    if not language:
        log(f"{locale}: SKIP — no English language name in LANGUAGE_NAMES")
        return 0, len(todo)

    cache_path = TMP / f"i18n_{locale}_translations.json"
    accepted: dict[str, str] = {}
    if cache_path.is_file():
        try:
            accepted = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            accepted = {}

    done = 0
    for start in range(0, len(todo), batch_size):
        chunk = todo[start:start + batch_size]
        items = [en_intro[p] for p in chunk]
        got = None
        for backend in tr.BACKENDS:
            if only_model and backend[0] != only_model:
                continue
            if backend[2] not in ("-", "NO_AUTH") and not env.get(backend[2]):
                continue
            got = tr.translate_batch(items, language, backend, env,
                                     force_translate=True, extra_hint=HINT)
            if got and len(got) == len(items):
                break
            got = None
        if not got:
            log(f"{locale}: batch {start // batch_size} — no usable reply, keeping {len(accepted)} so far")
            break
        for path, src, value in zip(chunk, items, got):
            if not value or not value.strip() or value.strip() == src.strip():
                continue
            if not tr.placeholders_intact(src, value):
                log(f"{locale}: reject placeholder drift {path}")
                continue
            accepted[path] = value.strip()
            done += 1
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(accepted, ensure_ascii=False, indent=1), encoding="utf-8")

    left = len(remaining(locale, en_intro))
    log(f"{locale} ({language}): +{done} translated, {left} still open")
    return done, left


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--locales", default="")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--batch-size", type=int, default=20)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--deliver", action="store_true", help="write each locale into its module as it finishes")
    ap.add_argument("--model", default="", help="use only this backend (e.g. ollama-deepseek)")
    args = ap.parse_args()

    en = extract("en") or {}
    # `extract` also reports the array container itself (`intro.personas.none.headlines`
    # -> the raw "[ … ]" source text). That is not a translatable string: the
    # writer resolves array items by their `<path>.<index>` keys only, so a
    # container entry would just burn model tokens and never clear.
    en_intro = {
        k: v for k, v in en.items()
        if k.startswith(PREFIX) and v.strip() and not v.lstrip().startswith("[")
    }
    log(f"intro strings in en: {len(en_intro)}")

    if args.locales:
        targets = [x.strip() for x in args.locales.split(",") if x.strip()]
    elif args.all:
        targets = [x for x in locales() if x not in SKIP]
    else:
        raise SystemExit("pass --all or --locales a,b,c")

    order = {loc: i for i, loc in enumerate(locales())}
    targets.sort(key=lambda x: order.get(x, 9999))

    if args.dry_run:
        for loc in targets:
            log(f"  {loc}: {len(remaining(loc, en_intro))} open")
        return 0

    env = tr.load_env()
    progress: dict[str, dict] = {}
    if PROGRESS.is_file():
        try:
            progress = json.loads(PROGRESS.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            progress = {}

    queue = list(targets)
    queue_lock = threading.Lock()

    def worker() -> None:
        while True:
            with queue_lock:
                if not queue:
                    return
                loc = queue.pop(0)
            if len(remaining(loc, en_intro)) == 0:
                progress[loc] = {"state": "done", "open": 0}
                continue
            try:
                done, left = fill(loc, en_intro, args.batch_size, env, args.model)
            except Exception as exc:  # a single locale must not kill the run
                log(f"{loc}: ERROR {type(exc).__name__}: {exc}")
                progress[loc] = {"state": "error", "error": str(exc)[:200]}
                continue
            if args.deliver:
                deliver_one(loc)
            progress[loc] = {"state": "partial" if left else "done", "added": done, "open": left}
            PROGRESS.write_text(json.dumps(progress, ensure_ascii=False, indent=1), encoding="utf-8")

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(max(1, args.workers))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    done = [k for k, v in progress.items() if v.get("state") == "done"]
    partial = [k for k, v in progress.items() if v.get("state") == "partial"]
    log(f"finished: {len(done)} complete, {len(partial)} partial")
    if partial:
        log("partial: " + ", ".join(f"{k}({progress[k]['open']})" for k in partial[:30]))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

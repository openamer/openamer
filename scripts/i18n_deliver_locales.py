#!/usr/bin/env python3
"""Deliver translated strings from the cache into the desktop catalogs, and measure it.

Why this exists: the model work was already done for 184 locales
(tmp/i18n_<locale>_translations.json), but the catalogs were never regenerated
from those caches. Measured 2026-11-16: `sg` had 2532 cached translations and
sat at 14.8% in sg.ts; regenerating the file took it to 96.8% with ZERO model
calls. That gap is the difference between "translated" and "delivered".

Two steps, deliberately separate:

  --deliver   regenerate <locale>.ts from tmp/i18n_<locale>_translations.json
              (node scripts/i18n_write_locale.mjs), then re-measure
  --report    measure only, no writes

Measurement uses the repo's own AST extractor (i18n_extract_locale.mjs), so it
counts what the UI actually loads - a value counts as translated when it differs
from the English text at the same path.

Usage:
    python scripts/i18n_deliver_locales.py --report
    python scripts/i18n_deliver_locales.py --deliver
    python scripts/i18n_deliver_locales.py --deliver --only sg,se,nd
    python scripts/i18n_deliver_locales.py --report --json reports/i18n-delivery.json
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import pathlib
import subprocess
import sys
from collections.abc import Callable

REPO = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
I18N = REPO / "apps" / "desktop" / "src" / "i18n"
TMP = REPO / "tmp"
EXTRACT = REPO / "scripts" / "i18n_extract_locale.mjs"
WRITE = REPO / "scripts" / "i18n_write_locale.mjs"
NODE = "node"

# Files in src/i18n that are infrastructure, not locales.
NOT_A_LOCALE = {"catalog", "types", "index", "languages", "context", "runtime",
                "plugin-i18n", "define-locale", "en"}


def node(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run([NODE, *args], capture_output=True, text=True, cwd=str(REPO),
                          encoding="utf-8", errors="replace")


def locales() -> list[str]:
    return sorted(p.stem for p in I18N.glob("*.ts")
                  if p.stem not in NOT_A_LOCALE and not p.stem.endswith(".test"))


def extract(locale: str) -> dict[str, str] | None:
    # Per-process temp name: several converge processes run at once during a
    # backfill and all of them extract `en`. A shared filename made the second
    # process fail with PermissionError while the first still held the file open
    # (measured 2026-11-17: worker 3 died on tmp/_deliver_en.json).
    out = TMP / f"_deliver_{locale}_{os.getpid()}.json"
    r = node([str(EXTRACT), str(I18N / f"{locale}.ts"), str(out)])
    if r.returncode != 0:
        print(f"  extract failed {locale}: {r.stderr.strip()[-160:]}", file=sys.stderr)
        return None
    try:
        leaves = json.loads(out.read_text(encoding="utf-8"))["leaves"]
    except (OSError, ValueError, KeyError) as exc:
        print(f"  extract unreadable {locale}: {exc}", file=sys.stderr)
        return None
    finally:
        out.unlink(missing_ok=True)
    return {leaf["path"]: leaf.get("text", "") for leaf in leaves}


def cache(locale: str) -> dict[str, str] | None:
    path = TMP / f"i18n_{locale}_translations.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _audit_module():
    spec = importlib.util.spec_from_file_location(
        "i18n_audit_locales", SCRIPTS / "i18n_audit_locales.py")
    if spec is None or spec.loader is None:
        raise ImportError("cannot load i18n_audit_locales")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _real_gap() -> Callable[[str, str], bool]:
    """The audit's own "is there anything to translate here" predicate.

    Without it, a raw `!= English` count never converges: measured 2026-11-16,
    `el` sat at 99.1% with 22 "open" strings that were the product name
    `OpenAmer`, the constants `FIELD_LABELS`/`FIELD_DESCRIPTIONS`, URLs, `'.'`,
    `'0'`, and templates like `${provider} · ${model}`. Nothing there is text.
    """
    return _audit_module().is_real_gap


REAL_GAP: Callable[[str, str], bool] = _real_gap()


def _translatable_keys() -> set[str]:
    """The paths the translator actually works on.

    `i18n_extract_locale.mjs` also returns `raw`, `ref` and `array` leaves (3 + 2 +
    2 of 2539 measured). The translator only touches `string` and `func`, so
    counting the others as "open" invents gaps nothing can ever close.
    """
    from i18n_translate_locale import load_leaves
    return {leaf["path"] for leaf in load_leaves("en") if leaf["kind"] in ("string", "func")}


KEYS = _translatable_keys()
HAND = _audit_module().hand_table


def real_gaps(locale: str, en: dict[str, str], values: dict[str, str] | None = None) -> list[str]:
    """Paths that are genuinely still to translate in this locale.

    One definition, used by the metric, the converge loop and the strict filler:
    in scope (string/func), open (absent or identical to English), a real gap by
    the audit's own predicate, and not already answered by the hand table.
    """
    values = values if values is not None else (extract(locale) or {})
    accepted = HAND(locale)
    return [path for path, text in en.items()
            if path in KEYS and values.get(path) in (None, text)
            and REAL_GAP(path, text) and path not in accepted]


def measure(locale: str, en: dict[str, str]) -> dict | None:
    values = extract(locale)
    if values is None:
        return None
    scope = {p: t for p, t in en.items() if p in KEYS}
    translated = sum(1 for path, text in scope.items() if values.get(path) not in (None, text))
    total = len(scope)
    real = real_gaps(locale, en, values)
    return {
        "locale": locale,
        "total": total,
        "translated": translated,
        "share": round(translated / total, 4) if total else 0.0,
        "missing_paths": sum(1 for path in en if path not in values),
        "real_gaps": len(real),
        "share_real": round((total - len(real)) / total, 4) if total else 0.0,
    }


def cache_quality(locale: str, en: dict[str, str]) -> int:
    """How many catalog paths the cache would actually translate.

    -1 means "no usable cache". A count is needed because presence alone is not
    translation: a cache entry identical to English is a gap.
    """
    cached = cache(locale)
    if not cached:
        return -1
    return sum(1 for path, text in en.items() if cached.get(path) not in (None, text))


def drop_foreign_values(locale: str) -> int:
    """Remove cache entries written in a script this locale does not use.

    One transliterated word must not block 2 500 good strings. Measured
    2026-11-17: `ps` had 2 521 correct Pashto values and 13 that spelled
    "agent" with Cyrillic letters -- the whole delivery was rejected and the
    locale made no progress. Dropping the bad entries makes them fall back to
    English, and the rest ships.
    """
    path = TMP / f"i18n_{locale}_translations.json"
    if not path.exists():
        return 0
    try:
        from i18n_script_check import expected_script, foreign_values
    except ImportError:
        return 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0
    if not isinstance(data, dict):
        return 0
    expected = expected_script(locale, "")
    bad = {text for text, _ in foreign_values(
        [v for v in data.values() if isinstance(v, str)], expected)}
    if not bad:
        return 0
    kept = {k: v for k, v in data.items() if v not in bad}
    try:
        path.write_text(json.dumps(kept, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        return 0
    return len(data) - len(kept)


def deliver(locale: str, en: dict[str, str], current: dict | None = None) -> tuple[bool, str]:
    """Regenerate the catalog from its cache - never at the cost of the catalog.

    The cache and the catalog are two sources and either can be ahead. Measured
    2026-11-16: delivering `vo` from its cache cut the catalog from 2453 to 2443
    translated strings, because a later translation pass had written ten English
    values back into the cache. Overwriting a better catalog with a poorer cache
    is silent data loss, so the write is refused and the caller reports why.
    """
    cached_q = cache_quality(locale, en)
    if cached_q < 0:
        return False, "no cache"
    cur = current if current is not None else measure(locale, en)
    if cur and cached_q < cur["translated"]:
        # Merge instead of refusing: keep every value the catalog already has and
        # only then regenerate. Measured 2026-11-16 on `vo`/`ms` - the cache held
        # three fresh translations AND ten stale English values, so a plain
        # refusal threw the three away.
        values = extract(locale) or {}
        cached = cache(locale) or {}
        gained = 0
        for path, text in values.items():
            if text and text != en.get(path) and cached.get(path) in (None, en.get(path)):
                cached[path] = text
                gained += 1
        if gained:
            (TMP / f"i18n_{locale}_translations.json").write_text(
                json.dumps(cached, ensure_ascii=False, indent=1), encoding="utf-8")
            cached_q = cache_quality(locale, en)
        if cur and cached_q < cur["translated"]:
            return False, f"refused: cache {cached_q} < catalog {cur['translated']}"
    dropped = drop_foreign_values(locale)
    if dropped:
        print(f"  {locale}: dropped {dropped} foreign-script value(s) from the cache",
              file=sys.stderr)
    r = node([str(WRITE), str(I18N / f"{locale}.ts"),
              str(TMP / f"i18n_{locale}_translations.json")])
    if r.returncode != 0:
        print(f"  write failed {locale}: {r.stderr.strip()[-160:]}", file=sys.stderr)
        return False, "write failed"
    return True, ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--deliver", action="store_true", help="regenerate catalogs from cache")
    ap.add_argument("--report", action="store_true", help="measure only")
    ap.add_argument("--only", default="", help="comma separated locale list")
    ap.add_argument("--json", default="", help="write the report to this path")
    args = ap.parse_args()

    en = extract("en")
    if en is None:
        print("cannot extract en.ts", file=sys.stderr)
        return 2

    todo = [s for s in (args.only.split(",") if args.only else locales()) if s]
    rows, delivered, refused = [], 0, []
    for locale in todo:
        cached = cache(locale)
        current = measure(locale, en)
        if args.deliver and cached:
            wrote, why = deliver(locale, en, current)
            if wrote:
                delivered += 1
            elif why.startswith("refused"):
                refused.append(locale)
        row = current
        if row is None:
            continue
        row["cache_entries"] = len(cached) if cached else 0
        rows.append(row)

    rows.sort(key=lambda r: r["share"])
    shares = [r["share"] for r in rows]
    median = shares[len(shares) // 2] if shares else 0
    full = sum(1 for s in shares if s >= 0.999)
    below50 = sum(1 for s in shares if s < 0.5)
    print(f"locales={len(rows)} delivered={delivered} refused={len(refused)} "
          f"median={median*100:.1f}% "
          f"min={shares[0]*100:.1f}% max={shares[-1]*100:.1f}% at100={full} below50={below50}")

    print("worst:", " ".join(f"{r['locale']}:{r['share']*100:.0f}%" for r in rows[:10]))

    if args.json:
        out = pathlib.Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"en_keys": len(en), "locales": rows}, indent=1,
                                  ensure_ascii=False), encoding="utf-8")
        print(f"json -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

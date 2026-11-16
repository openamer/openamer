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
import json
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
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
    out = TMP / f"_deliver_{locale}.json"
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


def measure(locale: str, en: dict[str, str]) -> dict | None:
    values = extract(locale)
    if values is None:
        return None
    translated = sum(1 for path, text in en.items() if values.get(path) not in (None, text))
    total = len(en)
    return {
        "locale": locale,
        "total": total,
        "translated": translated,
        "share": round(translated / total, 4) if total else 0.0,
        "missing_paths": sum(1 for path in en if path not in values),
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
        return False, f"refused: cache {cached_q} < catalog {cur['translated']}"
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

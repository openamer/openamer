"""Apply the translation cache to the locale modules, additively.

Why this exists: the swarm fills `HOME/tmp/desktop_<code>.json`, but a worker
only rewrites a module it classifies as a stub. A module with a few handwritten
strings counts as mature and keeps only its cache entry ("mature module
preserved") — so 159.460 translated strings sat in the cache while the UI still
showed 37% coverage.

The merge is strictly additive: a key is written only when the module either
lacks it or still holds the English source. A value a human wrote is never
overwritten, even when the cache disagrees.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOME = Path(os.environ.get("OPENAMER_HOME")
            or (Path.home() / "AppData" / "Local" / "openamer-laptop"))
LOCALES = REPO / "apps" / "desktop" / "src" / "i18n"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--locales", nargs="*", help="default: every cache file")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    fill = load("fill_apply", REPO / "scripts" / "fill_desktop_locales.py")
    en = fill.parse_en()
    codes = args.locales or sorted(
        p.stem.replace("desktop_", "") for p in (HOME / "tmp").glob("desktop_*.json"))
    total_added = 0
    touched = 0
    report = []
    for code in codes:
        cache_path = HOME / "tmp" / f"desktop_{code}.json"
        module_path = LOCALES / f"{code}.ts"
        if not cache_path.is_file() or not module_path.is_file():
            continue
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        current = fill.parse_literals(module_path.read_text(encoding="utf-8"))
        merged = dict(current)
        added = 0
        for raw_key, value in cache.items():
            # The cache uses the unit separator as its path delimiter, the
            # modules use dots: "common\x1ferror" -> "common.error".
            key = str(raw_key).replace("\x1f", ".")
            if key not in en or not isinstance(value, str) or not value.strip():
                continue
            existing = str(current.get(key, "")).strip()
            # Never overwrite a human value; fill only a gap or the English source.
            if existing and existing != str(en[key]).strip():
                continue
            if value.strip() == str(en[key]).strip():
                continue
            if fill.validation_error(str(en[key]), value):
                continue
            merged[key] = value
            added += 1
        if added:
            touched += 1
            total_added += added
            if not args.dry_run:
                text = "export default " + fill.render(fill.unflatten(merged)) + "\n"
                fill.atomic_write(module_path, text)
        report.append({"locale": code, "added": added, "keys_after": len(merged)})

    report.sort(key=lambda row: -row["added"])
    print(json.dumps({"locales_touched": touched, "keys_added": total_added,
                      "dry_run": args.dry_run, "top": report[:10]}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

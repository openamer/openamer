"""Apply the translation cache to locale modules WITHOUT regenerating them.

The previous implementation rebuilt each module from its literals
(`"export default " + render(unflatten(merged))`). That destroyed every module
it touched: it dropped the `defineLocale()` wrapper, the `import` lines, the
field-copy import and all 302 interpolated arrow-function translations, leaving
invalid TypeScript (`export default   common: {`). Measured 2026-11-11: 27
modules corrupted, 13 of them lost exactly 302 function entries each.

Every locale module is generated from en.ts, so it already contains EVERY key -
untranslated ones simply hold the English text. Applying the cache therefore
never has to insert anything: it replaces the value on an existing leaf line.
That is what this script does, path by path, and it leaves the rest of the file
byte-identical.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOME = Path(os.environ.get("OPENAMER_HOME")
            or (Path.home() / "AppData" / "Local" / "openamer-laptop"))
LOCALES = REPO / "apps" / "desktop" / "src" / "i18n"
SEP = "\x1f"

LEAF_RE = re.compile(r"""^(?P<indent>\s*)(?P<key>'(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*"|[A-Za-z_$][\w$.-]*)\s*:\s*
                          (?P<value>'(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*")\s*,\s*$""", re.VERBOSE)
OPEN_RE = re.compile(r"""^(?P<indent>\s*)(?P<key>'(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*"|[A-Za-z_$][\w$.-]*)\s*:\s*\{\s*$""")
CLOSE_RE = re.compile(r"^\s*\},?\s*$")


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _unquote(token: str) -> str:
    if len(token) >= 2 and token[0] == token[-1] and token[0] in "'\"":
        body = token[1:-1]
        return body.replace("\\'", "'").replace('\\"', '"').replace("\\\\", "\\")
    return token


def _quote(text: str) -> str:
    return "'" + text.replace("\\", "\\\\").replace("'", "\\'") + "'"


def patch_module(text: str, replacements: dict[str, str]) -> tuple[str, int, list[str]]:
    """Replace leaf values by their SEP-joined path. Returns (text, n, missing)."""
    lines = text.split("\n")
    stack: list[tuple[int, str]] = []
    applied = 0
    seen: set[str] = set()
    out: list[str] = []

    for line in lines:
        m_open = OPEN_RE.match(line)
        m_leaf = LEAF_RE.match(line)
        m_close = CLOSE_RE.match(line)

        if m_leaf:
            indent = len(m_leaf.group("indent"))
            path = SEP.join([seg for _, seg in stack] + [_unquote(m_leaf.group("key"))])
            seen.add(path)
            if path in replacements:
                value = replacements[path]
                out.append(
                    f"{m_leaf.group('indent')}{m_leaf.group('key')}: {_quote(value)},")
                applied += 1
                continue
            out.append(line)
            continue

        if m_open:
            stack.append((len(m_open.group("indent")), _unquote(m_open.group("key"))))
            out.append(line)
            continue

        if m_close:
            indent = len(line) - len(line.lstrip())
            while stack and stack[-1][0] >= indent:
                stack.pop()
            out.append(line)
            continue

        out.append(line)

    missing = [k for k in replacements if k not in seen]
    return "\n".join(out), applied, missing


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--locales", nargs="*")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    fill = load("fill_apply", REPO / "scripts" / "fill_desktop_locales.py")
    en = fill.parse_en()
    codes = args.locales or sorted(
        p.stem.replace("desktop_", "") for p in (HOME / "tmp").glob("desktop_*.json"))

    total, touched, report = 0, 0, []
    for code in codes:
        cache_path = HOME / "tmp" / f"desktop_{code}.json"
        module_path = LOCALES / f"{code}.ts"
        if not cache_path.is_file() or not module_path.is_file():
            continue
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        text = module_path.read_text(encoding="utf-8")
        current = fill.parse_literals(text)

        replacements: dict[str, str] = {}
        for raw_key, value in cache.items():
            key = str(raw_key)
            if key not in en or not isinstance(value, str) or not value.strip():
                continue
            existing = str(current.get(key, "")).strip()
            # Never overwrite a human value; fill only a gap or the English source.
            if existing and existing != str(en[key]).strip():
                continue
            if value.strip() == str(en[key]).strip():
                continue
            if fill.validation_error(str(en[key]), value, code):
                continue
            replacements[key] = value.strip()

        patched, added, missing = patch_module(text, replacements)
        if added and not args.dry_run:
            fill.atomic_write(module_path, patched)
        if added:
            touched += 1
            total += added
        report.append({"locale": code, "added": added,
                       "keys_after": len(current), "unmatched": len(missing)})

    report.sort(key=lambda row: -row["added"])
    print(json.dumps({"locales_touched": touched, "keys_added": total,
                      "dry_run": args.dry_run, "top": report[:10]},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

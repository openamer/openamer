"""Replace foreign-script values in every catalog with their English source.

Measured 2026-11-17: the contamination left after the parallel backfill is tiny
but real — 1-2 strings per locale, e.g. `M透明度 ya madirisa` (Venda) or
`OpenAmer工作在 en fond` (Occitan). One Chinese word inside an otherwise correct
translation is not a reason to discard 2 600 good strings, and it is not
something `--report` notices either, because the locale still counts as
translated.

`strip_foreign_in_catalog()` (the function the converge loop uses on a rejected
delivery) is applied here to every locale at once, so the catalogs are clean
before the release build.

    python scripts/i18n_strip_all.py            # report only
    python scripts/i18n_strip_all.py --apply    # rewrite the catalogs
"""
from __future__ import annotations

import argparse
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from i18n_deliver_locales import extract, locales, strip_foreign_in_catalog  # noqa: E402
from i18n_script_check import expected_script, foreign_values, values  # noqa: E402

I18N = REPO / "apps" / "desktop" / "src" / "i18n"


def dirty_locales() -> list[tuple[str, int]]:
    # Use the deliverer's locale list, not a glob: catalog.test.ts and
    # languages.ts live in the same folder and are not locales.
    found = []
    for loc in locales():
        path = I18N / f"{loc}.ts"
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        bad = foreign_values(values(text), expected_script(loc, text))
        if bad:
            found.append((loc, len(bad)))
    return found


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="rewrite the catalogs")
    args = ap.parse_args()

    dirty = dirty_locales()
    if not dirty:
        print("keine fremdschriftigen Werte in irgendeinem Katalog")
        return 0

    total = sum(n for _, n in dirty)
    print(f"{len(dirty)} Kataloge mit fremdschriftigen Werten, {total} Strings gesamt")
    for loc, n in dirty:
        print(f"  {loc:>9}: {n}")

    if not args.apply:
        print("\n(nur Bericht — mit --apply werden die Werte durch Englisch ersetzt)")
        return 0

    en = extract("en")
    if not en:
        print("en.ts nicht lesbar", file=sys.stderr)
        return 2
    fixed_total = 0
    for loc, _ in dirty:
        n = strip_foreign_in_catalog(loc, en)
        fixed_total += n
        print(f"  {loc:>9}: {n} Wert(e) auf Englisch zurückgesetzt")

    remaining = dirty_locales()
    print(f"\n{fix_total_label(fixed_total)} ersetzt; verbleibend: {len(remaining)} Kataloge")
    return 1 if remaining else 0


def fix_total_label(n: int) -> str:
    return f"{n} Wert(e)"


if __name__ == "__main__":
    sys.exit(main())

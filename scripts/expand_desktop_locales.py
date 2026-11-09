"""Bring the desktop i18n catalog to the same language set as the CLI.

The CLI advertises every ISO 639-1 code (185 total, from locales/_languages.json).
Desktop had its own curated list of 41 plus a hand-written `Locale` union, so a
user whose language the CLI supports still saw only 41 entries in the app's
picker.

This script makes desktop follow the same source of truth:

  * apps/desktop/src/i18n/<code>.ts   -- one module per language, new ones via
    defineLocale({}) which merges over English (partial by construction, never
    a missing key)
  * apps/desktop/src/i18n/catalog.ts  -- imports + TRANSLATIONS entries
  * apps/desktop/src/i18n/types.ts    -- the Locale union
  * apps/desktop/src/i18n/languages.ts -- LOCALE_OPTIONS (picker metadata)

Idempotent: existing modules and existing picker entries are kept verbatim, so
running it again only appends what is missing.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
I18N = REPO / "apps" / "desktop" / "src" / "i18n"
LANGS = REPO / "locales" / "_languages.json"

# Native names for the picker. Existing desktop entries are preserved verbatim;
# this map covers the ones being added here. A language missing from the map
# falls back to its English name, which is honest and still selectable.
def js(value: str) -> str:
    """Render a TS single-quoted string literal.

    Native language names carry apostrophes (Guaraní is "Avañe'ẽ"), which would
    terminate the literal and break the whole module -- caught by tsc, but only
    after the file is already written.
    """
    escaped = value.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


NATIVE = {
    "bn": "বাংলা", "ur": "اردو", "mr": "मराठी", "te": "తెలుగు", "ta": "தமிழ்",
    "gu": "ગુજરાતી", "kn": "ಕನ್ನಡ", "ml": "മലയാളം", "or": "ଓଡ଼ିଆ", "pa": "ਪੰਜਾਬੀ",
    "sw": "Kiswahili", "ha": "Hausa", "yo": "Yorùbá", "ig": "Igbo", "am": "አማርኛ",
    "ne": "नेपाली", "si": "සිංහල", "km": "ខ្មែរ", "my": "မြန်မာ", "lo": "ລາວ",
    "mn": "Монгол", "kk": "Қазақша", "uz": "Oʻzbekcha", "az": "Azərbaycan",
    "ku": "Kurdî", "ka": "ქართული", "hy": "Հայերեն", "he": "עברית", "ca": "Català",
    "sr": "Српски", "mk": "Македонски", "be": "Беларуская", "ky": "Кыргызча",
    "tg": "Тоҷикӣ", "tk": "Türkmençe", "ug": "ئۇيغۇرچە", "ps": "پښتو", "sd": "سنڌي",
    "so": "Soomaali", "zu": "isiZulu", "xh": "isiXhosa", "st": "Sesotho",
    "tn": "Setswana", "sn": "chiShona", "rw": "Ikinyarwanda", "mg": "Malagasy",
    "ny": "Chichewa", "om": "Afaan Oromoo", "ti": "ትግርኛ", "ff": "Fulfulde",
    "bm": "Bamanankan", "wo": "Wolof", "jv": "Basa Jawa", "su": "Basa Sunda",
    "ms": "Bahasa Melayu", "tl": "Tagalog", "as": "অসমীয়া", "bo": "བོད་སྐད",
    "dz": "རྫོང་ཁ", "iu": "ᐃᓄᒃᑎᑐᑦ", "kl": "Kalaallisut", "se": "Davvisámegiella",
    "gd": "Gàidhlig", "cy": "Cymraeg", "ga": "Gaeilge", "gl": "Galego",
    "eu": "Euskara", "mt": "Malti", "is": "Íslenska", "lb": "Lëtzebuergesch",
    "fy": "Frysk", "fo": "Føroyskt", "br": "Brezhoneg", "oc": "Occitan",
    "co": "Corsu", "sc": "Sardu", "rm": "Rumantsch", "wa": "Walon",
    "la": "Latina", "eo": "Esperanto", "yi": "ייִדיש", "ht": "Kreyòl ayisyen",
    "mi": "Te Reo Māori", "sm": "Gagana Samoa", "to": "Lea faka-Tonga",
    "fj": "Na Vosa Vakaviti", "qu": "Runa Simi", "gn": "Avañe'ẽ", "ay": "Aymar aru",
    "nv": "Diné bizaad", "oj": "Anishinaabemowin", "iu ": "",
    "ak": "Akan", "ee": "Eʋegbe", "lg": "Luganda", "ln": "Lingála", "lu": "Tshiluba",
    "kg": "Kikongo", "ki": "Gĩkũyũ", "kj": "Kuanyama", "kr": "Kanuri", "nd": "isiNdebele",
    "nr": "isiNdebele", "ss": "siSwati", "ts": "Xitsonga", "ve": "Tshivenḓa",
    "ng": "Ndonga", "hz": "Otjiherero", "mh": "Kajin M̧ajeļ", "na": "Dorerin Naoero",
    "ty": "Reo Tahiti", "ch": "Chamoru", "bi": "Bislama", "ho": "Hiri Motu",
    "sg": "Sängö", "rn": "Ikirundi", "tw": "Twi", "za": "Vahcuengh",
    "aa": "Afaraf", "ab": "Аҧсуа", "av": "Авар", "ba": "Башҡортса", "ce": "Нохчийн",
    "cv": "Чӑвашла", "os": "Ирон", "tt": "Татарча", "ug ": "",
    "an": "Aragonés", "ast": "", "bh": "भोजपुरी", "bho": "",
    "ia": "Interlingua", "ie": "Interlingue", "io": "Ido", "vo": "Volapük",
    "cu": "Словѣньскъ", "pi": "पालि", "sa": "संस्कृतम्", "ae": "Avesta",
    "ks": "کٲشُر", "dv": "ދިވެހި", "tzm": "", "ber": "",
}


def add_modules(names: dict[str, str]) -> int:
    created = 0
    for code in names:
        if code == "en":
            continue
        path = I18N / f"{code}.ts"
        if path.exists():
            continue
        path.write_text(
            "import { defineLocale } from './define-locale'\n\n"
            f"// {names[code]} ({code}). Partial on purpose: every string not listed here\n"
            "// falls back to English via defineLocale, so the app is fully usable before\n"
            "// this catalog is translated. Fill in overrides as translations land.\n"
            f"export const {code.replace('-', '_')} = defineLocale({{}})\n",
            encoding="utf-8", newline="\n",
        )
        created += 1
    return created


def export_name(code: str) -> str:
    """Whatever identifier the module actually exports.

    Most modules export the bare code, but pre-existing ones may camel-case a
    script subtag (zh-hant -> zhHant). Guessing produced a broken import for
    exactly that one file, so read it.
    """
    path = I18N / f"{code}.ts"
    if path.exists():
        m = re.search(r"^export const (\w+)", path.read_text(encoding="utf-8"), re.M)
        if m:
            return m.group(1)
    return code.replace("-", "_")


def rewrite_catalog(names: dict[str, str]) -> None:
    path = I18N / "catalog.ts"
    codes = [c for c in names if c != "en"]
    ident = {c: export_name(c) for c in names}

    # One alphabetically sorted import block (the repo's perfectionist/sort-imports
    # rule fails otherwise, and a generator that emits code the linter rejects has
    # to be re-fixed after every run).
    imports = [f"import {{ {ident[c]} }} from './{c}'" for c in names if c != "en"]
    imports.append("import { en } from './en'")
    imports.append("import type { Locale, Translations } from './types'")
    imports.sort(key=lambda line: line.rsplit("./", 1)[-1].rstrip("'"))

    # Key is the locale code, value the module's identifier: 'zh-hant' is not a
    # valid shorthand property name, so keys stay explicit.
    entries = ",\n".join(f"  '{c}': {ident[c]}" for c in codes)

    body = (
        "\n".join(imports) + "\n\n"
        "export const TRANSLATIONS: Record<Locale, Translations> = {\n"
        "  en,\n" + entries + "\n}\n"
    )
    path.write_text(body, encoding="utf-8", newline="\n")


def rewrite_types(names: dict[str, str]) -> None:
    path = I18N / "types.ts"
    src = path.read_text(encoding="utf-8")
    union = "export type Locale = " + " | ".join(f"'{c}'" for c in names) + "\n"
    new, n = re.subn(r"^export type Locale = [^\n]*\n", union, src, flags=re.M)
    if n != 1:
        raise SystemExit(f"expected exactly one Locale union in types.ts, found {n}")
    path.write_text(new, encoding="utf-8", newline="\n")


def rewrite_picker(names: dict[str, str]) -> None:
    path = I18N / "languages.ts"
    src = path.read_text(encoding="utf-8")

    existing: dict[str, dict[str, str]] = {}
    for m in re.finditer(
        r"\{\s*id: '([^']+)',\s*name: '([^']*)',\s*englishName: '([^']*)',\s*"
        r"configValue: '([^']*)'\s*\}", src, re.S):
        existing[m.group(1)] = {
            "id": m.group(1), "name": m.group(2),
            "englishName": m.group(3), "configValue": m.group(4),
        }

    blocks = []
    for code, english in names.items():
        old = existing.get(code)
        if old:
            blocks.append(old)
            continue
        native = NATIVE.get(code) or english
        blocks.append({"id": code, "name": native,
                       "englishName": english, "configValue": code})

    rendered = ",\n".join(
        "  {\n"
        f"    id: {js(b['id'])},\n"
        f"    name: {js(b['name'])},\n"
        f"    englishName: {js(b['englishName'])},\n"
        f"    configValue: {js(b['configValue'])}\n"
        "  }" for b in blocks
    )

    # The array ends with "] as const satisfies readonly {...}[]" -- replacing
    # only the bracketed body keeps that type assertion (and the Locale typing
    # it enforces) intact.
    m = re.search(
        r"(export const LOCALE_OPTIONS = \[)(.*?)(\r?\n\] as const satisfies[^\n]*)",
        src, re.S)
    if not m:
        raise SystemExit("could not locate the LOCALE_OPTIONS array body")
    new = src[:m.start()] + m.group(1) + "\n" + rendered + m.group(3) + src[m.end():]
    path.write_text(new, encoding="utf-8", newline="\n")


def main() -> int:
    names: dict[str, str] = json.loads(LANGS.read_text(encoding="utf-8"))
    print(f"target set: {len(names)} languages")
    print(f"modules created: {add_modules(names)}")
    rewrite_catalog(names)
    rewrite_types(names)
    rewrite_picker(names)
    print("catalog.ts, types.ts, languages.ts rewritten")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

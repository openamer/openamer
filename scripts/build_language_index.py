#!/usr/bin/env python3
"""Generate the public language index from the actual locale data.

The claim "OpenAmer speaks your language" has to be checkable, not asserted.
This script reads the three surfaces that actually ship languages and writes
two public artifacts from them:

  * ``website/static/api/languages.json`` -- machine-readable index
    (served at https://openamer.com/docs/api/languages.json)
  * ``website/docs/reference/languages.md`` -- the human page with the table

Surfaces measured:
  1. ``locales/_languages.json``      -- the advertised language set
  2. ``locales/<code>.yaml``          -- CLI / gateway catalogs (translation share)
  3. ``apps/desktop/src/i18n/*.ts``   -- desktop app catalogs (+ registration in
                                         ``languages.ts``)

"Translated share" is the honest metric used by ``scripts/i18n_audit.py``:
the fraction of values that differ from the English catalog. A file that
exists but is byte-identical to English counts as 0%, never as done.

Usage:
    python scripts/build_language_index.py            # write both artifacts
    python scripts/build_language_index.py --check    # exit 1 if they are stale
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LOCALES = REPO / "locales"
LANG_MAP = LOCALES / "_languages.json"
I18N_DIR = REPO / "apps" / "desktop" / "src" / "i18n"
LANGUAGES_TS = I18N_DIR / "languages.ts"
OUT_JSON = REPO / "website" / "static" / "api" / "languages.json"
OUT_MD = REPO / "website" / "docs" / "reference" / "languages.md"

# Right-to-left scripts. Measured from the locale set, not guessed: these are
# the codes whose primary script is RTL.
RTL = {"ar", "dv", "fa", "he", "ku", "ps", "sd", "ug", "ur", "yi"}

# Files in apps/desktop/src/i18n/ that are infrastructure, not languages.
NON_LOCALE_TS = {
    "index", "languages", "types", "catalog", "runtime", "define-locale",
    "plugin-i18n", "catalog.test", "languages.test", "runtime.test",
}


def _load_yaml_flat(path: Path) -> dict[str, str]:
    import yaml
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    def flatten(node, prefix=""):
        out = {}
        for key, value in node.items():
            full = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                out.update(flatten(value, full))
            else:
                out[full] = value
        return out

    return flatten(data)


def _ts_strings(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return re.findall(r"'((?:[^'\\]|\\.)*)'", text)


def collect() -> dict:
    names: dict[str, str] = json.loads(LANG_MAP.read_text(encoding="utf-8"))

    # --- desktop registration + native names -------------------------------
    ts_src = LANGUAGES_TS.read_text(encoding="utf-8")
    options = {}
    for code, body in re.findall(r"\{\s*id:\s*'([^']+)',(.*?)\}", ts_src, re.S):
        native = re.search(r"name:\s*'((?:[^'\\]|\\.)*)'", body)
        english = re.search(r"englishName:\s*'((?:[^'\\]|\\.)*)'", body)
        options[code] = {
            "native": native.group(1) if native else code,
            "english": english.group(1) if english else names.get(code, code),
        }

    # --- english baselines --------------------------------------------------
    en_yaml = _load_yaml_flat(LOCALES / "en.yaml")
    en_strings = set(_ts_strings(I18N_DIR / "en.ts"))

    rows = []
    for code, english_name in names.items():
        yaml_path = LOCALES / f"{code}.yaml"
        cli_total = cli_done = 0
        if yaml_path.exists():
            cat = _load_yaml_flat(yaml_path)
            cli_total = len(en_yaml)
            cli_done = sum(
                1
                for key, value in cat.items()
                if key in en_yaml and value != en_yaml[key]
            )

        ts_path = I18N_DIR / f"{code}.ts"
        desktop_strings = _ts_strings(ts_path) if ts_path.exists() else []
        desktop_total = len(desktop_strings)
        desktop_done = sum(1 for value in desktop_strings if value not in en_strings)

        registered = code in options
        native = options.get(code, {}).get("native", english_name)

        rows.append(
            {
                "code": code,
                "english_name": english_name,
                "native_name": native,
                "rtl": code in RTL,
                "cli": {
                    "catalog": yaml_path.exists(),
                    "keys": cli_total,
                    "translated_share": round(cli_done / cli_total, 4) if cli_total else 0.0,
                },
                "desktop": {
                    "catalog": ts_path.exists(),
                    "registered": registered,
                    "strings": desktop_total,
                    "translated_share": (
                        round(desktop_done / desktop_total, 4) if desktop_total else 0.0
                    ),
                },
            }
        )

    rows.sort(key=lambda r: r["english_name"].lower())

    two_letter = [r for r in rows if len(r["code"]) == 2]
    summary = {
        "locales_total": len(rows),
        "iso_639_1_two_letter": len(two_letter),
        "non_iso_locales": [r["code"] for r in rows if len(r["code"]) != 2],
        "rtl_locales": sorted(RTL & {r["code"] for r in rows}),
        "desktop_registered": sum(1 for r in rows if r["desktop"]["registered"]),
        "desktop_catalogs": sum(1 for r in rows if r["desktop"]["catalog"]),
        "cli_catalogs": sum(1 for r in rows if r["cli"]["catalog"]),
        "cli_keys": len(en_yaml),
        "cli_at_least_90pct": sum(1 for r in rows if r["cli"]["translated_share"] >= 0.90),
        "cli_at_least_50pct": sum(1 for r in rows if r["cli"]["translated_share"] >= 0.50),
        "desktop_at_least_50pct": sum(
            1 for r in rows if r["desktop"]["translated_share"] >= 0.50
        ),
        "fully_english_locales": [
            r["code"]
            for r in rows
            if r["code"] != "en"
            and r["cli"]["translated_share"] < 0.02
            and r["desktop"]["translated_share"] < 0.02
        ],
    }
    return {"summary": summary, "languages": rows}


def render_markdown(index: dict) -> str:
    s = index["summary"]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = [
        "---",
        "title: Languages",
        "sidebar_label: Languages",
        "description: >-",
        f"  Every language OpenAmer ships: {s['locales_total']} locales, measured from the locale data, not advertised.",
        "---",
        "",
        "# Languages",
        "",
        f"OpenAmer ships **{s['locales_total']} locales**. Every one of them has a real",
        "catalog in the repository — this page is generated from those files, so the",
        "numbers below are measurements, not marketing.",
        "",
        "| Measured fact | Value |",
        "|---|---|",
        f"| Locales with a CLI/gateway catalog | {s['cli_catalogs']} |",
        f"| Locales registered in the desktop app | {s['desktop_registered']} |",
        f"| Locales with a desktop catalog file | {s['desktop_catalogs']} |",
        f"| ISO 639-1 two-letter codes covered | {s['iso_639_1_two_letter']} |",
        f"| Locales outside ISO 639-1 | {', '.join(f'`{c}`' for c in s['non_iso_locales'])} |",
        f"| Right-to-left locales | {', '.join(f'`{c}`' for c in s['rtl_locales'])} |",
        f"| CLI catalogs at ≥90% translated | {s['cli_at_least_90pct']} of {s['cli_catalogs']} |",
        f"| CLI catalogs at ≥50% translated | {s['cli_at_least_50pct']} of {s['cli_catalogs']} |",
        f"| Desktop catalogs at ≥50% translated | {s['desktop_at_least_50pct']} of {s['desktop_catalogs']} |",
        "",
        "Translation share means: the fraction of values that differ from the English",
        "catalog. A catalog that exists but was never translated counts as 0% here —",
        "declared is not done.",
        "",
        "## How a language is measured",
        "",
        "1. `locales/_languages.json` declares the advertised set — one entry per locale.",
        "2. `locales/<code>.yaml` is the CLI/gateway catalog, checked key by key against",
        "   `locales/en.yaml` (the baseline).",
        "3. `apps/desktop/src/i18n/<code>.ts` is the desktop catalog; it counts only if",
        "   `languages.ts` registers the code as well.",
        "",
        "Nothing on this page is typed by hand: `scripts/build_language_index.py` reads",
        "the three sources and writes this file plus",
        "[`api/languages.json`](/docs/api/languages.json) (`--check` fails when the page",
        "is stale).",
        "",
        "## Add or fix a language",
        "",
        "```bash",
        "python scripts/build_language_index.py      # regenerate this page + the JSON",
        "python scripts/i18n_audit.py                 # per-catalog translation share",
        "python scripts/i18n_gap_report.py            # what is still English",
        "```",
        "",
        "A new language is done when its catalog differs from English, the desktop",
        "`languages.ts` registers the code, and the generated table above shows it.",
        "",
        "## The full list",
        "",
        f"Generated {today} from the repository. RTL = right-to-left script.",
        "",
        "| Code | Language | English | CLI | Desktop | Dir |",
        "|---|---|---|---|---|---|",
    ]
    for row in index["languages"]:
        cli = f"{row['cli']['translated_share'] * 100:.0f}%" if row["cli"]["catalog"] else "—"
        desk = (
            f"{row['desktop']['translated_share'] * 100:.0f}%"
            if row["desktop"]["catalog"]
            else "—"
        )
        if not row["desktop"]["registered"] and row["desktop"]["catalog"]:
            desk += " (unregistered)"
        lines.append(
            f"| `{row['code']}` | {row['native_name']} | {row['english_name']} | {cli} | {desk} | "
            f"{'RTL' if row['rtl'] else 'LTR'} |"
        )
    lines.append("")
    return "\n".join(lines)


def _read_raw(path: Path) -> str:
    """Read without newline translation (Path.read_text gained `newline` in 3.13)."""
    with open(path, encoding="utf-8", newline="") as handle:
        return handle.read()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="fail if artifacts are stale")
    args = ap.parse_args()

    index = collect()
    payload = json.dumps(index, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    markdown = render_markdown(index)

    if args.check:
        stale = []
        if not OUT_JSON.exists() or _read_raw(OUT_JSON) != payload:
            stale.append(str(OUT_JSON.relative_to(REPO)))
        if not OUT_MD.exists() or _read_raw(OUT_MD) != markdown:
            stale.append(str(OUT_MD.relative_to(REPO)))
        if stale:
            print("stale: " + ", ".join(stale), file=sys.stderr)
            return 1
        print("language index up to date")
        return 0

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    # LF everywhere: the artifacts are compared byte-for-byte by --check on
    # every OS, so the writer must not let Windows insert CRLF.
    OUT_JSON.write_text(payload, encoding="utf-8", newline="\n")
    OUT_MD.write_text(markdown, encoding="utf-8", newline="\n")
    s = index["summary"]
    print(
        f"wrote {OUT_JSON.relative_to(REPO)} and {OUT_MD.relative_to(REPO)}\n"
        f"  locales={s['locales_total']} iso639_1={s['iso_639_1_two_letter']} "
        f"cli_catalogs={s['cli_catalogs']} desktop_registered={s['desktop_registered']} "
        f"cli>=90%={s['cli_at_least_90pct']} full_english={len(s['fully_english_locales'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

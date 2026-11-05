#!/usr/bin/env python3
"""Report, per locale, exactly which en.ts sections/keys are still missing.

The desktop locales were created with the PARTIAL pattern (see the
desktop-i18n-locale skill): only a handful of sections were translated and
everything else fell back to English through defineLocale().  This tool
turns "partly translated" into a concrete, per-locale work list.

Usage:
    python i18n_gap_report.py                 # all locales
    python i18n_gap_report.py fr de           # specific locales
    python i18n_gap_report.py --keys fr       # list missing KEYS too
    python i18n_gap_report.py --sections fr   # list missing SECTIONS only
    python i18n_gap_report.py --template fr   # emit a TS skeleton for the gap
"""
import re
import sys
from pathlib import Path

I18N = Path(__file__).resolve().parent.parent / "apps" / "desktop" / "src" / "i18n"

SKIP = {
    "catalog.ts", "types.ts", "index.ts", "define-locale.ts", "plugin-i18n.ts",
    "runtime.ts", "languages.ts", "languages.test.ts", "runtime.test.ts",
    "en.ts",
}


def sections_of(path: Path) -> list[str]:
    src = path.read_text(encoding="utf-8")
    return re.findall(r"^  ([A-Za-z_][A-Za-z0-9_]*)\s*:\s*\{", src, re.M)


def keys_of(path: Path) -> set[str]:
    src = path.read_text(encoding="utf-8")
    return set(re.findall(r"^\s{0,4}([A-Za-z_][A-Za-z0-9_]*)\s*:", src, re.M))


def locale_files() -> list[Path]:
    return sorted(p for p in I18N.glob("*.ts") if p.name not in SKIP)


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    en = I18N / "en.ts"
    en_sections = sections_of(en)
    en_keys = keys_of(en)

    targets = locale_files()
    if args:
        wanted = {a if a.endswith(".ts") else f"{a}.ts" for a in args}
        targets = [p for p in targets if p.name in wanted]

    print(f"en.ts reference: {len(en_sections)} sections / {len(en_keys)} keys\n")
    rows = []
    for p in targets:
        have_s = sections_of(p)
        have_k = keys_of(p)
        rows.append((p.name, len(have_s), len(have_k), len(en_sections), len(en_keys)))

    print(f"{'locale':14} {'sect':>8} {'keys':>12}   {'pct':>6}")
    for name, ns, nk, ts, tk in rows:
        pct = 100 * nk / tk
        print(f"{name[:-3]:14} {ns:3}/{ts:<4} {nk:6}/{tk:<6} {pct:5.1f}%")

    print("\n=== MISSING SECTIONS ===")
    for p in targets:
        have = sections_of(p)
        missing = [s for s in en_sections if s not in have]
        print(f"{p.name[:-3]:14} {len(missing):2} missing: {missing}")

    if "--keys" in flags:
        print("\n=== MISSING KEYS (per section) ===")
        for p in targets:
            have = keys_of(p)
            missing = sorted(en_keys - have)
            print(f"\n--- {p.name[:-3]} ({len(missing)} missing) ---")
            for k in missing:
                print(f"    {k}")

    if "--template" in flags:
        for name in args:
            p = I18N / f"{name}.ts"
            if not p.exists():
                continue
            have = sections_of(p)
            missing = [s for s in en_sections if s not in have]
            src = p.read_text(encoding="utf-8")
            # print the English source of each missing section so the
            # translator has the exact strings to work from
            en_src = en.read_text(encoding="utf-8")
            print(f"\n\n########## TEMPLATE for {name}: sections {missing} ##########")
            for sec in missing:
                m = re.search(
                    r"^  " + re.escape(sec) + r"\s*:\s*\{\n(.*?)^  \},",
                    en_src, re.M | re.S,
                )
                if m:
                    print(f"\n  {sec}: {{\n{m.group(1)}  }},")
            print(f"\n// existing file starts:\n{src[:200]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

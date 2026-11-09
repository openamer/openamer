#!/usr/bin/env python3
"""Audit every locale catalog and report what is actually translated.

Counting keys proves nothing -- a catalog can hold all 330 keys as English
fallback. This reports, per language, the honest numbers:

  total   keys in the catalog
  transl  values that differ from en.yaml
  same    values byte-identical to English (fallback or deliberate)
  ph_bad  entries whose {placeholder} set differs from English (a real bug)
  hk_bad  entries that lost a [x] keyboard hotkey (a real bug)

Exit code is 0 unless a *correctness* rule fails (placeholder or hotkey drift);
low translation coverage is reported, not failed -- a small language may
legitimately stay partly English.

Usage:
    python scripts/i18n_audit.py            # table for all locales
    python scripts/i18n_audit.py --json     # machine-readable
    python scripts/i18n_audit.py --min 0.9  # exit 1 if any locale below 90%
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
LOCALES = REPO / "locales"
PH = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")
HOTKEY = re.compile(r"\[([A-Za-z])\]")

VERBATIM_KEYS = {"approval.smart_deny_once_inputs", "approval.smart_deny_deny_inputs"}


def flatten(d, prefix=""):
    out = {}
    for k, v in (d or {}).items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.update(flatten(v, key))
        else:
            out[key] = v
    return out


def load(code: str) -> dict[str, str]:
    path = LOCALES / f"{code}.yaml"
    if not path.exists():
        return {}
    return flatten(yaml.safe_load(path.read_text(encoding="utf-8")) or {})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--min", type=float, default=None,
                    help="exit 1 when a locale's translated share is below this")
    args = ap.parse_args()

    en = load("en")
    rows = []
    for path in sorted(LOCALES.glob("*.yaml")):
        code = path.stem
        if code == "en":
            continue
        cat = load(code)
        transl = same = 0
        ph_bad: list[str] = []
        hk_bad: list[str] = []
        for key, en_val in en.items():
            got = cat.get(key)
            if got is None:
                continue
            got_s, en_s = str(got).strip(), str(en_val).strip()
            if got_s == en_s:
                same += 1
            else:
                transl += 1
            if key in VERBATIM_KEYS:
                continue
            if sorted(PH.findall(got_s)) != sorted(PH.findall(en_s)):
                ph_bad.append(key)
            if sorted(HOTKEY.findall(got_s)) != sorted(HOTKEY.findall(en_s)):
                hk_bad.append(key)
        rows.append({
            "code": code,
            "total": len(cat),
            "translated": transl,
            "same": same,
            "share": round(transl / len(en), 4) if en else 0.0,
            "ph_bad": ph_bad,
            "hk_bad": hk_bad,
        })

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
    else:
        rows.sort(key=lambda r: r["share"])
        print(f"{'loc':8} {'trans':>6} {'same':>5} {'share':>7}  issues")
        for r in rows:
            issues = []
            if r["ph_bad"]:
                issues.append(f"placeholder x{len(r['ph_bad'])}")
            if r["hk_bad"]:
                issues.append(f"hotkey x{len(r['hk_bad'])}")
            print(f"{r['code']:8} {r['translated']:6} {r['same']:5} "
                  f"{100 * r['share']:6.1f}%  {', '.join(issues) or '-'}")
        good = sum(1 for r in rows if r["share"] >= 0.9)
        print(f"\n{good}/{len(rows)} locales at >=90% translated; "
              f"{sum(1 for r in rows if r['ph_bad'])} with placeholder drift, "
              f"{sum(1 for r in rows if r['hk_bad'])} with hotkey drift")

    bad = [r for r in rows if r["ph_bad"] or r["hk_bad"]]
    if bad:
        print(f"\nCORRECTNESS FAILURES in: {', '.join(r['code'] for r in bad)}",
              file=sys.stderr)
        return 1
    if args.min is not None:
        low = [r["code"] for r in rows if r["share"] < args.min]
        if low:
            print(f"\nBelow {args.min:.0%}: {' '.join(low)}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

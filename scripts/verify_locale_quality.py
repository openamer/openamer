"""Cross-model verification: is a shipped translation reproducible by a second model?

The existing gate rejects *unchanged English*. It cannot reject a confident
invention, and that is the real risk: measured on this install, Afar "Save" came
back as `Dhaagi` from one model and `Kay` from another, and Avestan — an extinct
liturgical language — was answered with invented forms.

This asks a DIFFERENT model to translate the same English source and compares the
two answers. Agreement is not proof, but disagreement is a reliable warning: it
is the only cheap signal that distinguishes "the model knows this language" from
"the model produced something plausible-looking".

Output: per-locale agreement rate, divergent examples, and a verdict per locale.
Nothing here edits a catalog — verification reports, it does not mutate.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOME = Path(os.environ.get("OPENAMER_HOME")
            or (Path.home() / "AppData" / "Local" / "openamer-laptop"))
OUT = REPO / "tmp" / "locale-verification.json"
SUPPORTED = 0.70  # agreement ratio that counts as reproducible


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def normalise(text: str) -> str:
    """Casefold, strip accents and punctuation: orthographic variance is not disagreement."""
    decomposed = unicodedata.normalize("NFKD", str(text))
    plain = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"[^\w]+", "", plain.casefold())


def similar(left: str, right: str) -> bool:
    """Same string, or one contains the other (clitics and articles drift)."""
    a, b = normalise(left), normalise(right)
    if not a or not b:
        return False
    if a == b:
        return True
    short, long = (a, b) if len(a) <= len(b) else (b, a)
    return len(short) >= 4 and short in long


def ratio(values: list[tuple[str, str]]) -> float:
    if not values:
        return 0.0
    return sum(1 for original, second in values if similar(original, second)) / len(values)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=12, help="strings checked per locale")
    ap.add_argument("--locales", nargs="*", help="default: every non-English locale in the cache")
    ap.add_argument("--report", default=str(OUT))
    args = ap.parse_args()

    fill = load("fill_verify", REPO / "scripts" / "fill_desktop_locales.py")
    env = fill.load_env()
    chain = fill.backend_chain(env)
    if len(chain) < 2:
        print("need at least two usable lanes to verify anything")
        return 1
    # Verifier = the last lane, so it is a different model than the first lane
    # that likely produced the cached value.
    verifier = chain[-1]
    name, url, keyenv, model = verifier
    key = "-" if keyenv == "-" else env.get(keyenv, "")
    if not key:
        print(f"verifier lane {name} has no key")
        return 1

    en = fill.parse_en()
    names = json.loads((REPO / "locales" / "_languages.json").read_text(encoding="utf-8"))
    cache_dir = HOME / "tmp"
    locales = args.locales or sorted(
        p.stem.replace("desktop_", "") for p in cache_dir.glob("desktop_*.json"))
    report = {"verifier": {"lane": name, "model": model}, "supported_at": SUPPORTED, "locales": {}}

    for code in locales:
        path = cache_dir / f"desktop_{code}.json"
        if not path.is_file():
            continue
        cache = json.loads(path.read_text(encoding="utf-8"))
        items = [(k, en[k]) for k in cache if k in en and str(cache[k]).strip()
                 and str(cache[k]).strip() != str(en[k]).strip()][: args.sample]
        if not items:
            continue
        try:
            second = fill.translate_chunk(items, names.get(code, code), env)
        except Exception as exc:  # noqa: BLE001 - one bad locale must not stop the sweep
            report["locales"][code] = {"error": f"{type(exc).__name__}: {exc}"}
            continue
        pairs = [(cache[k], second.get(k, "")) for k, _ in items if second.get(k)]
        agreed = sum(1 for original, other in pairs if similar(original, other))
        agreement = ratio(pairs)
        report["locales"][code] = {
            "checked": len(items), "answered": len(pairs), "agreed": agreed,
            "agreement": round(agreement, 3),
            "verdict": "supported" if pairs and agreement >= SUPPORTED else "unverified",
            "divergent": [{"source": en[k], "cached": cache[k], "second": second[k]}
                          for k, _ in items if second.get(k) and not similar(cache[k], second[k])][:5],
        }
        print(f"  {code}: {agreed}/{len(pairs)} agree -> {report['locales'][code]['verdict']}", flush=True)

    supported = [c for c, row in report["locales"].items() if row.get("verdict") == "supported"]
    report["summary"] = {
        "locales_checked": len(report["locales"]),
        "supported": len(supported),
        "unverified": len(report["locales"]) - len(supported),
    }
    out = Path(args.report)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print(json.dumps(report["summary"], ensure_ascii=False))
    print(f"report: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

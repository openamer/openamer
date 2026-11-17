#!/usr/bin/env python3
"""Compare each modified catalog against its HEAD version, per locale.

The delivery step regenerates a catalog from its cache. That is only safe if the
cache is at least as complete as the file it replaces; otherwise it silently
throws away hand-paired strings. This script proves it either way.

For every `apps/desktop/src/i18n/<locale>.ts` that differs from HEAD:
  extract HEAD version -> measure, extract working-tree version -> measure,
  report delta. Exits 1 if any locale got WORSE.

It also exits 1 when a change introduces a FOREIGN writing system: coverage alone
is not quality, and the converge loop once called 18 catalogs "complete" while
they carried another language's script (see scripts/i18n_script_check.py).
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
I18N = REPO / "apps" / "desktop" / "src" / "i18n"
TMP = REPO / "tmp"
EXTRACT = REPO / "scripts" / "i18n_extract_locale.mjs"


def sh(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, cwd=str(REPO),
                          encoding="utf-8", errors="replace")


def leaf_map(ts_path: pathlib.Path) -> dict[str, str] | None:
    """Flatten a catalog to {leaf path: text} via the shared node extractor."""
    out = TMP / f"_cmp_{ts_path.stem}.json"
    r = sh(["node", str(EXTRACT), str(ts_path), str(out)])
    if r.returncode != 0:
        return None
    try:
        leaves = json.loads(out.read_text(encoding="utf-8"))["leaves"]
    except (OSError, ValueError, KeyError):
        return None
    finally:
        out.unlink(missing_ok=True)
    return {leaf["path"]: leaf.get("text", "") for leaf in leaves}


def script_module():
    """Load scripts/i18n_script_check.py (not a package member) by path."""
    path = REPO / "scripts" / "i18n_script_check.py"
    spec = importlib.util.spec_from_file_location("i18n_script_check", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("i18n_script_check", module)
    spec.loader.exec_module(module)
    return module


def script_regression(changed: list[pathlib.Path]) -> list[tuple[str, int, int]]:
    """Locales whose working tree carries more foreign-script text than HEAD."""
    mod = script_module()
    if mod is None:
        return []
    regressions = []
    for path in changed:
        rel = path.relative_to(REPO).as_posix()
        old = sh(["git", "show", f"HEAD:{rel}"])
        if old.returncode != 0:
            continue
        expected = mod.expected_script(path.stem, old.stdout)
        before = len(mod.foreign_values(mod.values(old.stdout), expected))
        after = len(mod.foreign_values(mod.values(path.read_text(encoding="utf-8", errors="replace")), expected))
        if after > before:
            regressions.append((path.stem, before, after))
    return regressions


def main() -> int:
    en = leaf_map(I18N / "en.ts")
    if en is None:
        print("cannot extract en.ts", file=sys.stderr)
        return 2

    changed = [p for p in sorted(I18N.glob("*.ts"))
               if p.stem != "en" and not p.stem.endswith(".test")
               and sh(["git", "diff", "--quiet", "HEAD", "--", str(p)]).returncode == 1]
    print(f"changed catalogs: {len(changed)}")

    worse, better, same, failed = [], [], [], []
    for path in changed:
        rel = path.relative_to(REPO).as_posix()
        old_blob = sh(["git", "show", f"HEAD:{rel}"])
        if old_blob.returncode != 0:
            failed.append(path.stem)
            continue
        old_path = TMP / f"_head_{path.stem}.ts"
        old_path.write_text(old_blob.stdout, encoding="utf-8")
        old = leaf_map(old_path)
        old_path.unlink(missing_ok=True)
        new = leaf_map(path)
        if old is None or new is None:
            failed.append(path.stem)
            continue
        before = sum(1 for k, v in en.items() if old.get(k) not in (None, v))
        after = sum(1 for k, v in en.items() if new.get(k) not in (None, v))
        delta = after - before
        if delta < 0:
            worse.append((path.stem, before, after, delta))
        elif delta > 0:
            better.append((path.stem, before, after, delta))
        else:
            same.append(path.stem)

    print(f"better: {len(better)}   same: {len(same)}   WORSE: {len(worse)}   failed: {len(failed)}")
    if better:
        print("  biggest gains:", ", ".join(f"{l}+{d}" for l, b, a, d in
                                             sorted(better, key=lambda x: -x[3])[:12]))
    for loc, before, after, delta in sorted(worse, key=lambda x: x[3])[:15]:
        print(f"  REGRESSION {loc}: {before} -> {after} ({delta})")
    if failed:
        print("  failed:", failed[:10])

    # Coverage is only half of "better": a catalog can gain 300 translated
    # strings and still be unusable because they arrived in the wrong writing
    # system. Count those too so the delivery step stops calling a
    # wrong-language catalog an improvement.
    foreign = script_regression(changed)
    if foreign:
        print(f"  FOREIGN-SCRIPT REGRESSIONS: {len(foreign)}")
        for loc, before, after in foreign[:15]:
            print(f"  REGRESSION {loc}: foreign-script values {before} -> {after}")

    return 1 if (worse or foreign) else 0


if __name__ == "__main__":
    raise SystemExit(main())

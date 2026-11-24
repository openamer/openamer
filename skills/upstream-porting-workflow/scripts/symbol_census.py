#!/usr/bin/env python3
"""Static symbol census: find EVERY missing import in one pass.

Why this exists
---------------
After a port wave you get hundreds of red tests whose only real content is
"module X is not here". Fixing them by chasing one ImportError at a time costs
N debug cycles and hides the true size of the gap. This resolves every
`from <pkg>... import A, B, C` in the tree and reports, in ONE pass:

  * unresolvable modules      (port the file)
  * missing names in modules that DO resolve  (add the symbol in place)

Those two need different fixes -- a whole-file port vs a name-level addition --
so separating them up front is the point.

Run it before touching anything, and again after each batch.

Usage
-----
    # default: census the gateway package and its plugin consumers
    .venv/Scripts/python.exe scripts/symbol_census.py

    # narrower / wider
    .venv/Scripts/python.exe scripts/symbol_census.py --roots gateway plugins agent
    .venv/Scripts/python.exe scripts/symbol_census.py --prefix gateway

Notes
-----
* Run it from the repo root; it inserts cwd on sys.path so local packages
  import instead of any installed copy.
* Set OPENAMER_HOME to keep the app from loading the user's real profile.
  A "Deprecated .env settings detected" banner on stderr is harmless.
* `from X import *` is skipped (nothing to check).
* The `restart_loop_guard`-style FALSE POSITIVE: `from gateway import <submodule>`
  can report missing because the submodule attribute only appears on the package
  after something imports it. Re-test any single hit with a real
  `python -c "from gateway import <name>"` before you go fix it.
"""
from __future__ import annotations

import argparse
import ast
import importlib
import sys
from pathlib import Path

SKIP_PARTS = {"__pycache__", "node_modules", ".git", ".venv", "venv", "build", "dist"}


def census(repo: Path, roots: list[str], prefix: str) -> tuple[dict, dict]:
    """Return (missing_modules, missing_names) -> {key: {files}}."""
    missing_modules: dict[str, set[str]] = {}
    missing_names: dict[str, set[str]] = {}

    for root in roots:
        base = repo / root
        if not base.is_dir():
            continue
        for path in base.rglob("*.py"):
            if SKIP_PARTS & set(path.parts):
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError as exc:
                print(f"  ! syntax error, skipped: {path.relative_to(repo)} ({exc})",
                      file=sys.stderr)
                continue

            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom):
                    continue
                module = node.module or ""
                if not module.startswith(prefix):
                    continue
                rel = str(path.relative_to(repo))
                try:
                    imported = importlib.import_module(module)
                except Exception as exc:  # noqa: BLE001 - any failure == unresolvable
                    missing_modules.setdefault(
                        f"{module}  <{type(exc).__name__}>", set()).add(rel)
                    continue
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    if not hasattr(imported, alias.name):
                        missing_names.setdefault(
                            f"{module} :: {alias.name}", set()).add(rel)

    return missing_modules, missing_names


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default=".", help="repo root (default: cwd)")
    ap.add_argument("--roots", nargs="+", default=["gateway", "plugins", "agent", "tools"],
                    help="subdirectories to scan")
    ap.add_argument("--prefix", default="gateway", help="module prefix to resolve")
    ap.add_argument("--max-files", type=int, default=4, help="example consumers per hit")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    sys.path.insert(0, str(repo))

    missing_modules, missing_names = census(repo, args.roots, args.prefix)

    print("=== UNRESOLVABLE MODULES ===")
    if not missing_modules:
        print("  (none)")
    for key, files in sorted(missing_modules.items(), key=lambda kv: -len(kv[1])):
        print(f"  {len(files):>3}x  {key}")
        for f in sorted(files)[:args.max_files]:
            print(f"          {f}")

    print()
    print("=== MISSING NAMES (module resolves, symbol does not) ===")
    if not missing_names:
        print("  (none)")
    for key, files in sorted(missing_names.items(), key=lambda kv: -len(kv[1])):
        print(f"  {len(files):>3}x  {key}")
        for f in sorted(files)[:args.max_files]:
            print(f"          {f}")

    total = len(missing_modules) + len(missing_names)
    print()
    print(f"counts: {len(missing_modules)} modules / {len(missing_names)} names")
    print()
    print("Fix shape: unresolvable MODULE -> port the file "
          "(scripts/port_from_upstream.py --file ...).")
    print("           missing NAME      -> add the symbol in place; do NOT overwrite "
          "a locally-evolved file with upstream's.")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())

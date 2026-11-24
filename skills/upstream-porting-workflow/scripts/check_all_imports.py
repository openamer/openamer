#!/usr/bin/env python3
"""Import every module and report which ones ACTUALLY fail — Python as the oracle.

WHY THIS EXISTS
---------------
The AST heuristic for "which module-level names are missing" (walk for Name/Load
with no matching Store) cannot know scope, so it overshoots massively: measured
2026-09-22 it reported 6895 orphans, then 5240 after adding Lambda/arg handling,
when the true count was 51. The false positives are lambda/comprehension/walrus
bindings, `except ... as` names, and decorator-factory locals.

Importing the module answers it exactly, and the traceback hands you the file AND
line of the failure — no guessing, no candidate list to triage.

HOW TO READ THE OUTPUT
----------------------
  NameError: name 'X' is not defined        -> a module CONSTANT is missing.
      If X appears in a default argument, it must be inserted ABOVE its first
      consumer, not appended at end-of-file (defaults evaluate at import time).
  ImportError: cannot import name 'X' ...   -> port the symbol / widen a re-export.
  No module named '<third-party>'           -> ENVIRONMENT gap, install it.
      Do NOT treat this as a port gap; it is not durable and not yours to fix.
  No module named '<local.submodule>'       -> real port gap (size it with
      port_closure.py before copying anything).

Iterate the real gaps until the summary reads "N import OK, 0 FAIL".

USAGE
-----
    python check_all_imports.py --root <repo> --python <venv>/bin/python \
        [--filter openamer_cli] [--limit 40]

    # WSL python cannot see C:\\ paths — pass the /mnt/c form:
    python check_all_imports.py --root /mnt/c/Users/<u>/repo \
        --python ~/oav/bin/python --filter openamer_cli

    # Windows repo venv:
    .venv/Scripts/python.exe check_all_imports.py --root . --filter openamer_cli

Each module gets its OWN subprocess so one hard failure (segfault-ish import,
sys.exit at module level) cannot poison the next.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# Runs inside the child. Prints exactly one line: "OK" or "<Type>|<message>".
SNIPPET = (
    "import sys, importlib\n"
    "sys.path.insert(0, {root!r})\n"
    "try:\n"
    "    importlib.import_module({mod!r}); print('OK')\n"
    "except BaseException as e:\n"
    "    print(type(e).__name__ + '|' + str(e)[:200])\n"
)

SKIP_DIRS = {".venv", "venv", "__pycache__", "node_modules", "build", "dist",
             ".git", "dgpublish", "tests"}


def collect_modules(root: Path, prefix: str) -> list[str]:
    """Dotted names of every module under root whose path starts with prefix."""
    out: list[str] = []
    for p in sorted(root.rglob("*.py")):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        rel = p.relative_to(root)
        if rel.name == "__init__.py":
            continue
        mod = ".".join(rel.with_suffix("").parts)
        # startswith the DOTTED form — a bare `in mod` match also hits
        # "scripts/openamer_cli_notes.py" and silently drops everything.
        if prefix and not mod.startswith(prefix):
            continue
        out.append(mod)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True,
                    help="repo root (use /mnt/c/... when --python is WSL)")
    ap.add_argument("--python", default=sys.executable,
                    help="interpreter to import with (the venv under test)")
    ap.add_argument("--filter", default="",
                    help="only modules whose dotted name starts with this")
    ap.add_argument("--limit", type=int, default=40,
                    help="max failures to detail")
    ap.add_argument("--timeout", type=int, default=120)
    args = ap.parse_args()

    root = Path(args.root)
    if not root.is_dir():
        print(f"ABORT: root not visible at {root} "
              f"(under WSL use /mnt/c/... instead of C:\\...)")
        return 1

    mods = collect_modules(root, args.filter)
    if not mods:
        print(f"ABORT: no modules matched --filter {args.filter!r} under {root}. "
              f"Check the dotted prefix and that root is the real repo (not a "
              f"subdir), otherwise this reports a clean 0/0 run.")
        return 1

    ok = 0
    failures: list[tuple[str, str, str]] = []   # (mod, kind, detail)

    for mod in mods:
        try:
            r = subprocess.run(
                [args.python, "-c", SNIPPET.format(root=str(root), mod=mod)],
                capture_output=True, text=True, timeout=args.timeout,
            )
            out = (r.stdout or "").strip()
        except subprocess.TimeoutExpired:
            failures.append((mod, "Timeout", f">{args.timeout}s"))
            continue

        if out.startswith("OK"):
            ok += 1
            continue

        kind, _, detail = out.partition("|")
        if not detail:                       # empty stdout: hard child failure
            kind, detail = "NoOutput", (r.stderr or "")[-200:].replace("\n", " ")
        # capture the deepest project frame for file:line
        frame = ""
        for line in (r.stderr or "").splitlines():
            s = line.strip()
            if s.startswith("File ") and str(root) in s:
                frame = s
        failures.append((mod, kind.strip(), f"{detail}   {frame}".strip()))

    print(f"=== {ok} import OK, {len(failures)} FAIL (of {len(mods)}) ===")
    for mod, kind, detail in failures[: args.limit]:
        print(f"\n  {mod}")
        print(f"    {kind}: {detail[:180]}")

    if len(failures) > args.limit:
        print(f"\n  ... {len(failures) - args.limit} more (raise --limit)")

    # Bucket so the fix order is obvious: environment first (someone else's
    # problem), then real port gaps.
    env = [m for m, k, d in failures if "No module named" in f"{k}{d}"
           and not _is_local(d, root)]
    if env:
        print(f"\n=== ENVIRONMENT gaps ({len(env)}) — install, not a port gap ===")
        for m in env[:15]:
            print(f"  {m}")
    return 1 if failures else 0


def _is_local(detail: str, root: Path) -> bool:
    """True when the missing module names something inside this repo."""
    for line in detail.split("'"):
        if line and (root / line.replace(".", "/")).with_suffix(".py").is_file():
            return True
    return False


if __name__ == "__main__":
    sys.exit(main())

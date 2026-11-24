#!/usr/bin/env python3
"""Append specific upstream top-level definitions to a local module, IDEMPOTENTLY.

WHY THIS EXISTS
---------------
The first version of this tool appended by name with no "already defined" guard.
Driven in a loop it turned THREE missing constants into 351 duplicate lines in a
9568-line file before anyone noticed. An auto-porter is a loop; a loop without a
guard is a corruption generator.

The guard is the whole point: re-running must be a no-op, because after a bad run
you WILL re-run it.

SECOND RULE THIS ENCODES: constants go ABOVE their first use.
A definition referenced from a default argument

    def resolve_turn_limit(raw, default: int = TURN_LIMIT_UNLIMITED) -> int:

is evaluated at IMPORT time. Appending the constant at end-of-file parses fine,
passes py_compile, and still makes every importer die with NameError. Use
--before-first-use to insert above the first consumer instead of at the tail.

USAGE
-----
    # dry run (shows to-append / already-present / not-found-upstream)
    python port_symbols.py --module openamer_cli/config.py \
        --upstream <upstream-package>/config.py \
        --symbols TURN_LIMIT_UNLIMITED _UNLIMITED_SPELLINGS \
        --root <repo> --upstream-root <upstream> [--before-first-use TURN_LIMIT_UNLIMITED]

    # verify idempotency by running it TWICE; second run must print
    #   to append: []   already present (skipped): [...]

    # recover from a bad append:
    git -C <repo> checkout HEAD -- <module>
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path


def top_level_blocks(path: Path) -> dict[str, list[str]]:
    """name -> source lines of each top-level def/class/assignment."""
    src = path.read_bytes().decode("utf-8", "replace")
    tree = ast.parse(src)
    lines = src.splitlines()
    out: dict[str, list[str]] = {}
    for n in tree.body:
        name = getattr(n, "name", None)
        if name is None and isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name):
            name = n.targets[0].id
        if name is None:
            continue
        start = min([n.lineno] + [d.lineno for d in getattr(n, "decorator_list", [])]) - 1
        # pull in the comment block that introduces it (it explains WHY)
        while start > 0 and lines[start - 1].lstrip().startswith("#"):
            start -= 1
        out[name] = lines[start:n.end_lineno]
    return out


def already_defined(path: Path, name: str) -> bool:
    """THE GUARD. Matches a top-level def/class/assignment for `name`."""
    try:
        src = path.read_bytes().decode("utf-8", "replace")
        tree = ast.parse(src)
    except Exception:
        return False
    for n in tree.body:
        got = getattr(n, "name", None)
        if got is None and isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name):
            got = n.targets[0].id
        if got == name:
            return True
    return False


def insert_before_first_use(lines: list[str], blocks: list[list[str]], anchor: str) -> int:
    """Insert blocks immediately above the first line matching `anchor`."""
    pat = re.compile(re.escape(anchor))
    for i, l in enumerate(lines):
        if pat.search(l):
            payload: list[str] = []
            for b in blocks:
                payload += b + [""]
            lines[i:i] = payload
            return i
    return -1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--module", required=True, help="local module, repo-relative")
    ap.add_argument("--upstream", required=True, help="upstream twin, upstream-relative")
    ap.add_argument("--symbols", nargs="+", required=True)
    ap.add_argument("--root", required=True)
    ap.add_argument("--upstream-root", required=True)
    ap.add_argument("--before-first-use", default=None,
                    help="anchor line: insert above the first match instead of EOF")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    root, up_root = Path(args.root), Path(args.upstream_root)
    local, up = root / args.module, up_root / args.upstream

    # Both roots must be visible to THIS interpreter's path flavour.
    for label, p in (("repo", local), ("upstream twin", up)):
        if not p.is_file():
            hint = ("  (under WSL python, pass /mnt/c/... not C:\\...)" 
                    if "C:" in str(p) else "")
            print(f"ABORT: {label} not visible at {p}{hint}")
            return 1

    local_blocks = top_level_blocks(local)
    up_blocks = top_level_blocks(up)

    # rebrand via the repo's own tool so renames live in exactly one place
    sys.path.insert(0, str(root / "scripts"))
    try:
        from port_from_upstream import rebrand
    except Exception:
        def rebrand(t: str) -> str:            # noqa: D401 - explicit fallback
            """No-op when the repo tool is unavailable; caller is warned."""
            print("WARN: scripts/port_from_upstream.py not importable -- "
                  "text is NOT rebranded. Check for leftover upstream tokens "
                  "with `--check-only` before committing.")
            return t

    to_add, already, absent = [], [], []
    for sym in args.symbols:
        if sym in local_blocks or already_defined(local, sym):
            already.append(sym)                # <- the idempotency guard
        elif sym not in up_blocks:
            absent.append(sym)
        else:
            to_add.append((sym, rebrand("\n".join(up_blocks[sym]))))

    print(f"to append: {[s for s, _ in to_add]}")
    print(f"already present (skipped): {already}")
    print(f"not found upstream: {absent}")

    if not args.apply or not to_add:
        print("(no write)")
        return 0

    raw = local.read_bytes().decode("utf-8")
    # NOTE: a CRLF file can carry lone-LF lines (the port tool writes some blocks
    # with \n). Splitting on "\r\n" alone merges those into their neighbours and
    # breaks exact matching. splitlines() sees both.
    had_crlf = "\r\n" in raw
    nl = "\r\n" if had_crlf else "\n"
    lines = raw.splitlines()

    if args.before_first_use:
        blocks = [b.splitlines() for _, b in to_add]
        at = insert_before_first_use(lines, blocks, args.before_first_use)
        if at < 0:
            print(f"ABORT: anchor {args.before_first_use!r} not found in {args.module}")
            return 1
        print(f"inserted above first use (line {at + 1})")
    else:
        blocks = [b.splitlines() for _, b in to_add]
        payload: list[str] = []
        for b in blocks:
            payload += b + [""]
        lines = lines + [""] + payload
        print("appended at end-of-file -- WRONG for a constant used in a "
              "default argument; use --before-first-use in that case")

    text = nl.join(lines).rstrip(nl) + nl
    compile(text, str(local), "exec")          # syntax gate before writing
    local.write_bytes(text.encode("utf-8"))
    print(f"written: {args.module} (+{len(to_add)} block(s))")
    print("now re-run WITHOUT --apply and confirm `to append: []`")
    return 0


if __name__ == "__main__":
    sys.exit(main())

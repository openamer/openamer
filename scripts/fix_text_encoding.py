#!/usr/bin/env python3
"""fix_text_encoding.py - AST-guided sweep for the Windows subprocess footgun.

The footgun: subprocess.call/run/Popen/check_* with text=True but no encoding=.
On a non-UTF-8 default codepage (e.g. cp936 on Chinese Windows) the child's
output is decoded with the locale codec and crashes the reader thread.

The repo has a line-based linter for this (scripts/check-windows-footguns.py).
That linter is intentionally strict and flags a call even when encoding= sits on
the continuation line -- useful as a gate, noisy as a to-do list. This tool
reports the REAL functional gaps (AST: no encoding kwarg anywhere in the call)
and can fix them without hand-editing 100+ sites.

Usage:
  fix_text_encoding.py scan  [--root DIR]            -> report real gaps
  fix_text_encoding.py apply [--root DIR] [--dry-run]

Safety: only inserts two keywords after `text=True`; never deletes or reorders.
Always run `scan` afterwards -- it must report 0 gaps -- then py_compile.
"""
import argparse
import ast
import re
import sys
from pathlib import Path

DEFAULT_ROOT = Path(r"C:\Users\damir\AppData\Local\openamer-laptop\scripts")
CALLS = {"run", "Popen", "check_output", "check_call", "call", "getoutput", "getstatusoutput"}
SKIP_DIRS = {"__pycache__", "lora_out", "adapter_backup", "merged", "node_modules",
             ".git", ".venv", "venv", "site-packages"}
ENC = ', encoding="utf-8"'
ERR = ', errors="replace"'


def iter_files(root):
    for p in sorted(Path(root).rglob("*.py")):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        # skip HuggingFace/model dirs masquerading as scripts
        if (p.parent / "tokenizer.json").exists() or (p.parent / "config.json").exists():
            continue
        yield p


def gaps_in(path):
    """Return [(lineno, col, need_errors)] for text=True calls lacking encoding.

    need_errors is False when the call ALREADY passes errors= -- inserting it
    again is a syntax error ("keyword argument repeated"), which is exactly what
    the first sweep produced on ssh-manager.py before this was fixed.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return []
    out = []
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        name = getattr(n.func, "attr", None) or getattr(n.func, "id", None)
        if name not in CALLS:
            continue
        kw = {k.arg for k in n.keywords if k.arg}
        if "text" in kw and "encoding" not in kw:
            for k in n.keywords:
                if k.arg == "text" and isinstance(k.value, ast.Constant) \
                        and k.value.value is True:
                    out.append((k.lineno, k.col_offset + 1,
                                "errors" not in kw))
    return out


def apply_to(path, hits):
    """Insert the encoding kwargs after each `text=True` on its own line."""
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    changed = 0
    # process bottom-up: multiple hits per line are impossible, but line indexes
    # stay valid because we only edit inside lines
    for lineno, col, need_errors in hits:
        i = lineno - 1
        if i >= len(lines):
            continue
        line = lines[i]
        # a hit's col points at `text`; match it forward from there
        m = re.compile(r"text\s*=\s*True").search(line, col - 1)
        if not m:
            continue
        add = ENC + (ERR if need_errors else "")
        lines[i] = line[:m.end()] + add + line[m.end():]
        changed += 1
    if changed:
        path.write_text("".join(lines), encoding="utf-8")
    return changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["scan", "apply"])
    ap.add_argument("--root", default=str(DEFAULT_ROOT))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    total, files = 0, 0
    for p in iter_files(a.root):
        hits = gaps_in(p)
        if not hits:
            continue
        files += 1
        total += len(hits)
        if a.cmd == "scan":
            print(f"  {p.relative_to(a.root)}: {len(hits)} gap(s) "
                  f"@ lines {sorted({h[0] for h in hits})}")
        elif not a.dry_run:
            n = apply_to(p, hits)
            print(f"  fixed {n} in {p.relative_to(a.root)}")

    verb = "would fix" if (a.cmd == "apply" and a.dry_run) else "fixed"
    if a.cmd == "scan":
        print(f"REAL gaps: {total} in {files} file(s)")
    else:
        print(f"{verb}: {total} call site(s) in {files} file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
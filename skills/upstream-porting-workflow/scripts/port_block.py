#!/usr/bin/env python3
"""Port named method/class blocks VERBATIM from an upstream git revision.

Why this exists: slicing an upstream file by LINE NUMBER is off by one between
`sed -n 'A,Bp'` and a Python slice, and the failure is silent when the dropped
line is a closer (measured 2026-10-13: a dropped `        )` produced
`SyntaxError: '(' was never closed` in plugins/platforms/feishu/adapter.py).
This extracts by SYMBOL instead, so the off-by-one cannot happen.

It also:
  * sources the block from the git OBJECT (`git show <rev>:<path>`), never from
    a hand-transcription;
  * PRESERVES the target's line endings (pure CRLF or pure LF) and refuses a
    mixed-EOL file rather than corrupting it;
  * PROVES byte-identity after writing (`occurrences == 1` per block);
  * is IDEMPOTENT (a symbol already defined in the target is skipped, and a
    second run writes nothing).

Typical use — insert two methods before an anchor line:

  python port_block.py --repo <repo> \\
      --path plugins/platforms/feishu/adapter.py --rev origin/main \\
      --symbol _flush_text_batch --symbol _flush_text_batch_now \\
      --insert-before "    @staticmethod" --occurrence 2

Add --dry-run to preview. Details and the full recipe:
references/verbatim-block-extraction.md
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys


def read_upstream(repo: str, rev: str, path: str) -> list[str]:
    out = subprocess.run(
        ["git", "show", f"{rev}:{path}"], cwd=repo,
        capture_output=True, text=True, encoding="utf-8",
    )
    if out.returncode != 0:
        sys.exit(f"ABORT: `git show {rev}:{path}` failed\n{out.stderr.strip()}")
    return out.stdout.replace("\r\n", "\n").split("\n")


def extract_block(lines: list[str], name: str) -> list[str] | None:
    """Return the source lines of `def <name>` incl. its decorators and body.

    The block ends at the first following non-blank line whose indentation is
    <= the def's, so a trailing `@staticmethod` stays with the NEXT method.
    """
    pat = re.compile(rf"^(\s*)(?:async\s+)?def\s+{re.escape(name)}\s*\(")
    for i, line in enumerate(lines):
        m = pat.match(line)
        if not m:
            continue
        indent = len(m.group(1))
        start = i
        while start > 0 and lines[start - 1].strip().startswith("@"):
            start -= 1
        end = i + 1
        while end < len(lines):
            stripped = lines[end].strip()
            if stripped and (len(lines[end]) - len(lines[end].lstrip())) <= indent:
                break
            end += 1
        while end > start and not lines[end - 1].strip():
            end -= 1
        return lines[start:end]
    return None


def detect_eol(raw: bytes) -> str:
    crlf, lf = raw.count(b"\r\n"), raw.count(b"\n")
    if raw.count(b"\r") != crlf:
        sys.exit("ABORT: target has a lone CR — inspect the file by hand")
    if lf == 0:
        return "\n"
    if crlf == lf:
        return "\r\n"
    if crlf == 0:
        return "\n"
    sys.exit(
        "ABORT: target mixes CRLF and LF "
        f"({crlf} CRLF / {lf} LF). Use the `patch` tool for a surgical edit "
        "instead of a scripted re-encode — see references/verbatim-block-extraction.md"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default=".", help="repo root (default: cwd)")
    ap.add_argument("--path", required=True, help="path as git sees it")
    ap.add_argument("--rev", default="origin/main",
                    help="git revision to source from (default: origin/main)")
    ap.add_argument("--upstream-path", default=None,
                    help="source path if it differs from --path")
    ap.add_argument("--symbol", action="append", required=True,
                    help="method/function name to port (repeatable, order preserved)")
    ap.add_argument("--insert-before", required=True,
                    help="exact text of the anchor line to insert BEFORE")
    ap.add_argument("--occurrence", type=int, default=1,
                    help="which occurrence of the anchor (1-based, default 1)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    up_path = args.upstream_path or args.path
    up_lines = read_upstream(args.repo, args.rev, up_path)

    blocks, absent = [], []
    for name in args.symbol:
        blk = extract_block(up_lines, name)
        if blk is None:
            absent.append(name)
        else:
            blocks.append((name, blk))
    if absent:
        sys.exit(f"ABORT: not found in {args.rev}:{up_path} -> {absent}")

    raw = open(args.path, "rb").read()
    eol = detect_eol(raw)
    text = raw.decode("utf-8")
    work = text.replace("\r\n", "\n") if eol == "\r\n" else text

    # Idempotency: skip symbols the target already defines.
    already = [n for n, _ in blocks
               if re.search(rf"^\s*(?:async\s+)?def\s+{re.escape(n)}\s*\(", work, re.M)]
    todo = [(n, b) for n, b in blocks if n not in already]
    if already:
        print(f"already present (skipped): {already}")
    if not todo:
        print("nothing to do — all symbols already defined in the target")
        return 0

    lines = work.split("\n")
    idxs = [i for i, l in enumerate(lines) if l == args.insert_before]
    if len(idxs) < args.occurrence:
        sys.exit(f"ABORT: anchor {args.insert_before!r} has {len(idxs)} occurrence(s), "
                 f"need #{args.occurrence}")
    idx = idxs[args.occurrence - 1]

    ins: list[str] = []
    for _name, blk in todo:
        ins.extend(blk)
        ins.append("")
    new_lines = lines[:idx] + ins + lines[idx:]

    new_text = "\n".join(new_lines)
    out = new_text.replace("\n", "\r\n").encode("utf-8") if eol == "\r\n" \
        else new_text.encode("utf-8")

    # Prove byte-identity before writing anything.
    check = out.decode("utf-8")
    for name, blk in todo:
        want = "\n".join(blk).replace("\n", eol)
        n = check.count(want)
        if n != 1:
            sys.exit(f"ABORT: {name} would appear {n}x (expected 1) — refusing to write")

    print(f"EOL={eol!r}  inserting {len(ins)} lines before line {idx + 1} "
          f"({args.insert_before.strip()!r} #{args.occurrence})")
    for name, blk in todo:
        print(f"  + {name}  ({len(blk)} lines, verbatim from {args.rev})")

    if args.dry_run:
        print("dry-run: nothing written")
        return 0

    open(args.path, "wb").write(out)

    raw2 = open(args.path, "rb").read()
    if raw2.count(b"\r") != raw2.count(b"\r\n"):
        sys.exit("ABORT: write introduced a lone CR — restore from git")
    written = raw2.decode("utf-8")
    for name, blk in todo:
        want = "\n".join(blk).replace("\n", eol)
        assert written.count(want) == 1, f"{name} not verbatim after write"
    print(f"OK: wrote {args.path}  "
          f"(verbatim x{len(todo)})  -> now run: ruff check {args.path} && py_compile")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

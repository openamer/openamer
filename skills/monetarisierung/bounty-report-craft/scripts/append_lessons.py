#!/usr/bin/env python3
"""Append a drafted lessons block to bounty-factory/lessons.md and normalise EOLs.

Why this exists
----------------
Appending to lessons.md from Python text mode on Windows rewrites "\\n" as
"\\r\\n", leaving the otherwise LF-only file with mixed EOLs. Reading the draft
in text mode and writing with newline="" avoids the rewrite; we still sweep any
stray "\\r\\n" afterwards so the file stays LF-only.

Usage
-----
    python append_lessons.py <draft.md>

<draft.md> is the block you want appended (usually starting with
"\\n## <date> — Run N" plus the Lesson paragraphs). It may live at any path; a
scratch file written by the harness lands under C:/tmp when you pass a POSIX
/tmp path, so prefer an absolute Windows path.
"""
import sys
import os

LESSONS = r"C:\Users\damir\openamer-product\bounty-factory\lessons.md"


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python append_lessons.py <draft.md>")
        return 2
    draft_path = sys.argv[1]
    if not os.path.exists(draft_path):
        print(f"ERROR: draft not found: {draft_path}")
        return 1

    # Read draft without newline translation; ensure exactly one leading blank line.
    with open(draft_path, "r", encoding="utf-8", newline="") as f:
        block = f.read().replace("\r\n", "\n").replace("\r", "\n")
    if not block.startswith("\n"):
        block = "\n" + block
    if not block.endswith("\n"):
        block += "\n"

    before = os.path.getsize(LESSONS) if os.path.exists(LESSONS) else 0

    # Append in binary to guarantee NO newline translation by the runtime.
    with open(LESSONS, "ab") as f:
        f.write(block.encode("utf-8"))

    # Normalise any pre-existing CRLF that earlier sessions may have introduced.
    with open(LESSONS, "rb") as f:
        data = f.read()
    crlf = data.count(b"\r\n")
    if crlf:
        data = data.replace(b"\r\n", b"\n")
    with open(LESSONS, "wb") as f:
        f.write(data)

    lf = data.count(b"\n")
    after = os.path.getsize(LESSONS)
    runs = sum(1 for ln in data.decode("utf-8", "replace").splitlines()
               if ln.startswith("## ") and "Run" in ln)
    print(f"appended {after - before} bytes; CRLF={data.count(chr(13).encode()+chr(10).encode())} LF={lf} total_Run_blocks={runs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""EOL-matched, idempotent block append for an EXISTING file (skill refs, logs, archives).

Usage:
    python append_block_eol_safe.py <target-file> <block-file> <marker> [--dry-run]

Appends the text of <block-file> to <target-file> using the EOL the target ALREADY uses
(CRLF when CRLF-dominant, otherwise LF) and refuses to append twice: a target that already
contains <marker> is reported as `skip` and left byte-untouched.

This exists because the hand-rolled heredoc version of this recipe failed twice in one
session (2026-10-13): a `\\n`-only block mixed line endings into a CRLF file, and a backslash
inside an f-string raised SyntaxError BEFORE the write, so the append silently never happened.
Both failure modes are removed here.

Exit codes: 0 appended or skipped | 1 usage error | 2 target missing.
"""

import hashlib
import sys


def eol_of(raw: bytes) -> bytes:
    """The EOL this file already uses. Measure per FILE, never per tree."""
    crlf = raw.count(b"\r\n")
    return b"\r\n" if crlf > raw.count(b"\n") - crlf else b"\n"


def stats(raw: bytes) -> str:
    crlf = raw.count(b"\r\n")
    barelf = raw.count(b"\n") - crlf
    dblcr = raw.count(b"\r\r\n")
    digest = hashlib.md5(raw).hexdigest()[:12]
    return f"CRLF={crlf} bareLF={barelf} dblCR={dblcr} md5={digest}"


def main(argv: list) -> int:
    dry_run = "--dry-run" in argv
    args = [arg for arg in argv if arg != "--dry-run"]
    if len(args) != 3:
        print(__doc__)
        return 1
    target, block_file, marker = args
    try:
        with open(target, "rb") as fh:
            raw = fh.read()
    except FileNotFoundError:
        print(f"target missing: {target}")
        return 2
    print(f"{target}: {stats(raw)}")

    text = raw.decode("utf-8")
    if marker in text:
        print(f"skip: already carries marker {marker!r} - nothing written")
        return 0

    with open(block_file, "rb") as fh:
        block = fh.read().decode("utf-8")

    eol = eol_of(raw)
    eol_text = eol.decode()  # hoisted: an f-string expression may not contain a backslash (<3.12)
    if not text.endswith(("\n", "\r\n")):
        text += eol_text
    new = (text + block.replace("\r\n", "\n").replace("\n", eol_text)).encode("utf-8")

    if dry_run:
        print(f"dry-run: would append {len(new) - len(raw)} B with eol {eol!r}")
        return 0

    with open(target, "wb") as fh:
        fh.write(new)
    print(f"appended with eol {eol!r}: {stats(new)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

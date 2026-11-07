"""Insert the Upstream-Derived provenance marker into derived files.

Byte-level edit: preserves the file's existing line endings (CRLF vs LF)
exactly, and only touches the header of the file.

For Python, the marker goes inside the module docstring. For TypeScript,
which usually has no header comment, the marker is inserted as a leading
line comment after any directive prologue (``"use client"`` / ``"use strict"``)
and after a leading license comment block.

The same marker text is used for both languages so one regex finds it:

    Upstream-Derived: <path> @ <commit> (MIT)

Usage:

    python scripts/insert_provenance_marker.py py <file> "<path> @ <commit> (MIT)"
    python scripts/insert_provenance_marker.py ts <file> "<path> @ <commit> (MIT)"
"""

from __future__ import annotations

import pathlib
import sys


def _split_keep_trailing_newline(raw: bytes, nl: bytes) -> tuple[bytes, bytes]:
    """Split off the final newline so we can re-attach it unchanged."""
    if raw.endswith(nl):
        return raw[: -len(nl)], nl
    return raw, b""


def insert_python_marker(path: pathlib.Path, marker_body: str) -> str:
    """Insert the marker into the module docstring."""
    raw = path.read_bytes()
    nl = b"\r\n" if b"\r\n" in raw else b"\n"
    marker = f"Upstream-Derived: {marker_body}".encode()

    if marker in raw:
        return f"SKIP (marker present): {path.name}"

    start = raw.find(b'"""')
    if start == -1:
        return f"FAIL (no docstring): {path.name}"
    body_start = start + 3
    end = raw.find(b'"""', body_start)
    if end == -1:
        return f"FAIL (unterminated docstring): {path.name}"

    doc = raw[body_start:end]
    if not doc.endswith(nl):
        doc = doc + nl
    doc = doc + nl + marker + nl
    path.write_bytes(raw[:body_start] + doc + raw[end:])
    return f"OK (py): {path.name}"


def insert_ts_marker(path: pathlib.Path, marker_body: str) -> str:
    """Insert the marker as a leading line comment."""
    raw = path.read_bytes()
    nl = b"\r\n" if b"\r\n" in raw else b"\n"
    marker = f"// Upstream-Derived: {marker_body}".encode()

    if marker in raw:
        return f"SKIP (marker present): {path.name}"

    body, trailing = _split_keep_trailing_newline(raw, nl)
    lines = body.decode("utf-8", errors="replace").split(nl.decode("ascii"))

    # Keep a directive prologue ("use client", "use strict") first: it must
    # stay at the very top of the file to take effect.
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        if stripped.startswith(('"use ', "'use ")) or stripped.startswith("/*"):
            index += 1
            continue
        break

    # Keep an existing leading comment block (license header) first.
    if index < len(lines) and lines[index].lstrip().startswith(("//", "/*", "*")):
        while index < len(lines) and lines[index].lstrip().startswith(("//", "/*", "*")):
            index += 1

    lines.insert(index, marker.decode("utf-8"))
    path.write_bytes(nl.decode("ascii").join(lines).encode("utf-8") + trailing)
    return f"OK (ts): {path.name}"


def main(argv: list[str]) -> int:
    if len(argv) < 4:
        print(
            "usage: insert_provenance_marker.py <py|ts> <path> "
            '"<upstream-path> @ <commit> (MIT)"'
        )
        return 2
    kind, target, body = argv[1], argv[2], argv[3]
    path = pathlib.Path(target)
    if kind == "py":
        print(insert_python_marker(path, body))
    elif kind == "ts":
        print(insert_ts_marker(path, body))
    else:
        print(f"unknown kind: {kind}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

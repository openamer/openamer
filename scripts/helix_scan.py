#!/usr/bin/env python
"""helix_scan — OpenAmer's own static analyzer for JavaScript and Electron apps.

This is not a port of any existing tool. It reads the formats OpenAmer walks
every day and reports what it can prove, with the limits stated in its output.

Scope, deliberately narrow:
    * unpack an Electron ASAR archive, including members stored beside it in
      <archive>.unpacked/
    * inventory the JavaScript modules it contains
    * count IPC surface: literal channels registered in the main process and
      literal channels invoked or subscribed from a renderer
    * count contextBridge exposure points and their top-level member names
    * count BrowserWindow constructions

What it does not do, and does not pretend to:
    * it never resolves a computed channel expression, so any IPC name built at
      runtime is invisible here and is reported under unresolved_call_sites
    * it does not evaluate control flow, so a channel mentioned in dead code
      still counts
    * it does not decompile native code, read .NET metadata, APK, firmware or
      model files

Standard library only. Every number printed is derived from bytes on disk.
"""

from __future__ import annotations

import argparse
import json
import re
import struct
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

ASAR_HEADER_MAGIC = 4
JS_SUFFIXES = (".js", ".mjs", ".cjs")
LITERAL = r"""["'`]([^"'`\n]{1,120})["'`]"""


# --------------------------------------------------------------------------- #
# ASAR
# --------------------------------------------------------------------------- #
@dataclass
class AsarEntry:
    path: str
    size: int
    offset: int
    unpacked: bool = False


def read_asar(path: Path) -> tuple[list[AsarEntry], bytes]:
    """Return the file inventory and the raw payload of an ASAR archive.

    Measured layout on a real archive:

        offset 0   uint32  4                marker
        offset 4   uint32  header_size      spans offset 8 .. payload start
        offset 8   uint32  header_size - 4
        offset 12  uint32  json_size        exact JSON byte length
        offset 16  ...     JSON             padded up to 8 + header_size
        offset 8 + header_size: payload; entry offsets are relative to it

    Reading the JSON at offset 8 or 12 yields a decode error, because both of
    those words are lengths.
    """
    with path.open("rb") as handle:
        prefix = handle.read(16)
        if len(prefix) != 16:
            raise ValueError("file is shorter than an ASAR header")
        magic, header_size, _mirror, json_size = struct.unpack("<IIII", prefix)
        if magic != ASAR_HEADER_MAGIC:
            raise ValueError(f"not an ASAR archive (leading word {magic}, expected 4)")
        if not 0 < header_size < 256 * 1024 * 1024:
            raise ValueError(f"implausible ASAR header size {header_size}")
        if not 0 < json_size <= header_size:
            raise ValueError(f"implausible ASAR JSON size {json_size}")
        handle.seek(16)
        header_raw = handle.read(json_size)
        try:
            header = json.loads(header_raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as cause:
            raise ValueError(f"ASAR header is not valid JSON: {cause}") from cause
        handle.seek(8 + header_size)
        payload = handle.read()

    entries: list[AsarEntry] = []

    def walk(node: dict, prefix: str = "") -> None:
        for name, child in (node.get("files") or {}).items():
            current = f"{prefix}/{name}" if prefix else name
            if "files" in child:
                walk(child, current)
            elif child.get("unpacked") is True:
                # Unpacked members carry no offset: Electron keeps them as plain
                # files beside the archive, under <archive>.unpacked/<path>.
                entries.append(AsarEntry(current, int(child.get("size") or 0), -1, True))
            elif "offset" in child and "size" in child:
                entries.append(AsarEntry(current, int(child["size"]), int(child["offset"])))

    walk(header)
    return entries, payload


def entry_bytes(entry: AsarEntry, payload: bytes, archive: Path) -> bytes:
    if entry.unpacked:
        unpacked_root = archive.with_name(archive.name + ".unpacked")
        return (unpacked_root / entry.path).read_bytes()
    return payload[entry.offset : entry.offset + entry.size]


# --------------------------------------------------------------------------- #
# scans
# --------------------------------------------------------------------------- #
PATTERNS = {
    "main_handler": re.compile(r"ipcMain\s*\.\s*(?:handle|handleOnce|on)\s*\(\s*" + LITERAL),
    "renderer_send": re.compile(
        r"ipcRenderer\s*\.\s*(?:invoke|send|sendSync|postMessage)\s*\(\s*" + LITERAL
    ),
    "renderer_listen": re.compile(
        r"ipcRenderer\s*\.\s*(?:on|once|addListener)\s*\(\s*" + LITERAL
    ),
    "expose": re.compile(r"exposeInMainWorld\s*\(\s*" + LITERAL + r"\s*,\s*", re.DOTALL),
    "browser_window": re.compile(r"new\s+[A-Za-z_$][\w$]*\s*BrowserWindow\s*\("),
}

# A channel built at runtime never matches LITERAL. Counting the call sites
# that yield no literal keeps that blind spot visible instead of silent.
NON_LITERAL = {
    "main_handler": re.compile(
        r"ipcMain\s*\.\s*(?:handle|handleOnce|on)\s*\(\s*([^\"'`\s])"
    ),
    "renderer": re.compile(
        r"ipcRenderer\s*\.\s*(?:invoke|send|sendSync|on|once)\s*\(\s*([^\"'`\s])"
    ),
}


def member_keys(source: str, start: int) -> list[tuple[int, str]]:
    """Every object-literal key inside the literal that begins at `start`.

    Returns (depth, name) pairs, so callers can report a top-level count and a
    count including nested objects without scanning twice. Depth 1 is the
    literal itself.

    Skips strings, template literals and both comment styles: a comma inside a
    comment or a string must not be read as a key separator. Nested object
    literals are followed to the bottom, which also means keys inside an arrow
    function body are counted — declared as a limitation rather than guessed at.
    """
    depth = 0
    keys: list[tuple[int, str]] = []
    expect_key = False
    quote: str | None = None
    index = start
    length = len(source)

    while index < length:
        char = source[index]

        if quote is not None:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = None
            index += 1
            continue

        if char in "'\"`":
            quote = char
            index += 1
            continue

        if char == "/" and source[index : index + 2] == "//":
            newline = source.find(chr(10), index)
            index = length if newline == -1 else newline + 1
            continue
        if char == "/" and source[index : index + 2] == "/*":
            closing = source.find("*/", index + 2)
            index = length if closing == -1 else closing + 2
            continue

        if char == "{":
            depth += 1
            expect_key = True
            index += 1
            continue

        if char == "}":
            depth -= 1
            if depth == 0:
                return keys
            index += 1
            continue

        if depth >= 1:
            if char == ",":
                expect_key = True
                index += 1
                continue
            if expect_key:
                if char.isalpha() or char in "_$":
                    match = re.match(r"[A-Za-z_$][\w$]*", source[index:])
                    if match:
                        name = match.group(0)
                        following = source[index + len(name) :].lstrip()
                        if following[:1] in (":", ",", "}"):
                            keys.append((depth, name))
                        expect_key = False
                        index += len(name)
                        continue
                elif char.isspace():
                    index += 1
                    continue
                else:
                    expect_key = False

        index += 1
    return keys


def top_level_members(source: str, start: int) -> list[str]:
    """Keys directly on the exposed object, in source order."""
    return [name for depth, name in member_keys(source, start) if depth == 1]


def all_members(source: str, start: int) -> list[str]:
    """Keys at every depth, de-duplicated, for comparison with tools that count nested."""
    seen: list[str] = []
    for _depth, name in member_keys(source, start):
        if name not in seen:
            seen.append(name)
    return seen


@dataclass
class Finding:
    root: str
    kind: str
    modules: int = 0
    js_bytes: int = 0
    main_handlers: Counter = field(default_factory=Counter)
    renderer_sends: Counter = field(default_factory=Counter)
    renderer_listeners: Counter = field(default_factory=Counter)
    exposures: dict[str, list[str]] = field(default_factory=dict)
    member_depths: Counter = field(default_factory=Counter)
    browser_windows: int = 0
    unresolved: Counter = field(default_factory=Counter)
    limitations: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        channels = set(self.main_handlers) | set(self.renderer_sends) | set(self.renderer_listeners)
        paired = set(self.main_handlers) & (set(self.renderer_sends) | set(self.renderer_listeners))
        return {
            "root": self.root,
            "kind": self.kind,
            "js_modules": self.modules,
            "js_bytes": self.js_bytes,
            "ipc_channels_literal": len(channels),
            "ipc_main_handlers": sum(self.main_handlers.values()),
            "ipc_renderer_transmissions": sum(self.renderer_sends.values()),
            "ipc_renderer_listeners": sum(self.renderer_listeners.values()),
            "ipc_paired_channels": len(paired),
            "ipc_one_sided_channels": sorted(channels - paired)[:20],
            "context_bridge_exposures": {name: len(items) for name, items in self.exposures.items()},
            "context_bridge_members_total": sum(len(items) for items in self.exposures.values()),
            "context_bridge_members_by_depth": {
                str(depth): count for depth, count in sorted(self.member_depths.items())
            },
            "browser_windows": self.browser_windows,
            "unresolved_call_sites": dict(self.unresolved),
            "limitations": self.limitations,
            "top_channels": sorted(
                channels,
                key=lambda name: -(
                    self.main_handlers[name]
                    + self.renderer_sends[name]
                    + self.renderer_listeners[name]
                ),
            )[:15],
        }


def scan_sources(root: str, kind: str, sources: list[tuple[str, str]]) -> Finding:
    finding = Finding(root=root, kind=kind)
    finding.modules = len(sources)
    payload = "\n".join(text for _name, text in sources)
    finding.js_bytes = sum(len(text.encode("utf-8", "ignore")) for _name, text in sources)

    for match in PATTERNS["main_handler"].finditer(payload):
        finding.main_handlers[match.group(1)] += 1
    for match in PATTERNS["renderer_send"].finditer(payload):
        finding.renderer_sends[match.group(1)] += 1
    for match in PATTERNS["renderer_listen"].finditer(payload):
        finding.renderer_listeners[match.group(1)] += 1
    finding.browser_windows = len(PATTERNS["browser_window"].findall(payload))

    for _match in NON_LITERAL["main_handler"].finditer(payload):
        finding.unresolved["main_handler_non_literal"] += 1
    for _match in NON_LITERAL["renderer"].finditer(payload):
        finding.unresolved["renderer_non_literal"] += 1

    for match in PATTERNS["expose"].finditer(payload):
        name = match.group(1)
        merged = finding.exposures.setdefault(name, [])
        for member in top_level_members(payload, match.end()):
            if member not in merged:
                merged.append(member)
        for depth, _name in member_keys(payload, match.end()):
            finding.member_depths[depth] += 1

    finding.limitations = [
        (
            "Literal channels only: a channel assembled at runtime is invisible"
            " here and is reported under unresolved_call_sites, not guessed."
        ),
        "Counts are mentions, not live registrations: a channel in unreachable code still counts.",
        (
            "contextBridge members are reported per nesting depth, because a single"
            " member count is only comparable once both tools state their depth rule."
        ),
        (
            "computed spreads, getters and keys built at runtime are not enumerated."
        ),
        "No decompilation, no .NET, no APK, no firmware, no model metadata.",
    ]
    return finding


def collect_from_asar(path: Path) -> Finding:
    entries, payload = read_asar(path)
    sources: list[tuple[str, str]] = []
    skipped: list[str] = []
    for entry in entries:
        if not entry.path.lower().endswith(JS_SUFFIXES):
            continue
        try:
            data = entry_bytes(entry, payload, path)
        except OSError as cause:
            # A missing unpacked member is not an empty module. Keep it visible
            # rather than counting it as zero bytes.
            skipped.append(f"{entry.path}: {cause.strerror or cause}")
            continue
        sources.append((entry.path, data.decode("utf-8", "replace")))
    finding = scan_sources(str(path), "electron-asar", sources)
    if skipped:
        finding.limitations.insert(
            0, f"{len(skipped)} unpacked module(s) could not be read: {skipped[:3]}"
        )
    return finding


def collect_from_directory(directory: Path) -> Finding:
    sources = [
        (str(file.relative_to(directory)), file.read_text(encoding="utf-8", errors="replace"))
        for file in sorted(directory.rglob("*"))
        if file.is_file() and file.suffix.lower() in JS_SUFFIXES
    ]
    return scan_sources(str(directory), "javascript-directory", sources)


# --------------------------------------------------------------------------- #
# cli
# --------------------------------------------------------------------------- #
def summarize(report: dict) -> str:
    lines = [
        f"root            {report['root']}",
        f"kind            {report['kind']}",
        f"js modules      {report['js_modules']}  ({report['js_bytes'] // 1024} KB)",
        "",
        (
            f"ipc channels    {report['ipc_channels_literal']} literal,"
            f" {report['ipc_paired_channels']} with both sides present"
        ),
        f"  main handlers {report['ipc_main_handlers']}",
        f"  renderer send {report['ipc_renderer_transmissions']}",
        f"  renderer recv {report['ipc_renderer_listeners']}",
        (
            f"context bridge  {report['context_bridge_exposures'] or '—'}"
            f"  (depth histogram {report['context_bridge_members_by_depth']})"
        ),
        f"browser windows {report['browser_windows']}",
    ]
    if report["unresolved_call_sites"]:
        lines.append(f"unresolved      {report['unresolved_call_sites']}")
    if report["ipc_one_sided_channels"]:
        lines.append(f"one-sided       {report['ipc_one_sided_channels'][:6]} …")
    lines.append("")
    lines.append("limits")
    lines.extend(f"  · {limitation}" for limitation in report["limitations"])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="helix_scan", description="OpenAmer's own JavaScript/Electron static scanner."
    )
    parser.add_argument("target", type=Path, help="ASAR archive or directory of JavaScript")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    try:
        if args.target.is_dir():
            finding = collect_from_directory(args.target)
        elif args.target.suffix.lower() == ".asar":
            finding = collect_from_asar(args.target)
        else:
            parser.error("target must be an .asar archive or a directory")
    except (OSError, ValueError) as cause:
        print(f"helix_scan: {cause}", file=sys.stderr)
        return 2

    report = finding.as_dict()
    print(json.dumps(report, indent=2, ensure_ascii=False) if args.json else summarize(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

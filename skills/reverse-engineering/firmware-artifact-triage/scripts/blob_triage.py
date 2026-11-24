#!/usr/bin/env python3
"""Triage an opaque firmware/vendor blob: what is it, and can it be read?

Answers four questions in one pass, with the measurements that justify each:

  1. container  - outer format magic (ZIP / gzip / squashfs / UBI / ELF / ...)
  2. structure  - entropy sweep over the WHOLE file, listing transitions
  3. compression vs encryption - magic census + real decompressor probes
  4. plaintext  - how many readable strings the head actually carries

Writes ``sections.json`` next to the input when entropy gaps are found.

Usage:
    python blob_triage.py <file> [--window 65536] [--no-census]

Stdlib only. Reads in chunks; never loads the whole file.
"""

from __future__ import annotations

import bz2
import collections
import json
import lzma
import math
import re
import sys
import zipfile
import zlib
from array import array
from pathlib import Path

MAGICS = [
    (b"PK\x03\x04", "ZIP archive"),
    (b"\x1f\x8b\x08", "gzip stream"),
    (b"hsqs", "squashfs (LE)"),
    (b"sqsh", "squashfs (BE)"),
    (b"#UBI", "UBI/UBIFS"),
    (b"UBI#", "UBI image (old)"),
    (b"\x45\x3d\xcd\x28", "cramfs"),
    (b"\x53\xef", "ext2/3/4 superblock"),
    (b"\x7fELF", "ELF"),
    (b"\x27\x05\x19\x56", "uImage (U-Boot)"),
    (b"ANDROID!", "Android boot image"),
    (b"\xd0\x0d\xfe\xed", "device tree blob (DTB)"),
]

# Counted across the whole payload: their presence means a real filesystem or
# kernel image is in there somewhere, so extraction is plausible.
CENSUS = [
    (b"hsqs", "squashfs"),
    (b"#UBI", "UBI"),
    (b"\x27\x05\x19\x56", "uImage"),
    (b"ANDROID!", "android-boot"),
    (b"\x1f\x8b\x08", "gzip"),
    (b"BZh9", "bzip2"),
    (b"\xfd7zXZ", "xz"),
    (b"ustar", "tar"),
]

HIGH_ENTROPY = 7.0


def entropy(block: bytes) -> float:
    if not block:
        return 0.0
    counts = collections.Counter(block)
    n = len(block)
    return -sum((v / n) * math.log2(v / n) for v in counts.values())


def identify(head: bytes) -> str:
    for magic, label in MAGICS:
        if head.startswith(magic):
            return label
    for off in range(min(len(head) - 8, 4096)):
        for magic, label in MAGICS:
            if head[off:off + len(magic)] == magic:
                return f"{label} @ +{off}"
    return "unknown"


def sweep(path: Path, window: int) -> tuple[list[tuple[int, int]], list[tuple[int, float]]]:
    """Return (low-entropy runs, transitions). One pass over the whole file."""
    size = path.stat().st_size
    low: list[tuple[int, int]] = []
    transitions: list[tuple[int, float]] = []
    state = None
    run_start = 0
    with path.open("rb") as fh:
        off = 0
        tail = b""
        while True:
            chunk = fh.read(8 << 20)
            if not chunk:
                break
            data = tail + chunk
            base = off - len(tail)
            step = 0
            while step + window <= len(data):
                e = entropy(data[step:step + window])
                is_low = e < HIGH_ENTROPY
                pos = base + step
                if state is None:
                    state = is_low
                    run_start = pos
                    transitions.append((pos, e))
                elif is_low != state:
                    transitions.append((pos, e))
                    if is_low:
                        run_start = pos
                    else:
                        low.append((run_start, pos))
                    state = is_low
                step += window
            tail = data[step:]
            off += len(chunk)
    if state is False:
        low.append((run_start, size))
    return low, transitions


def census(path: Path) -> dict[str, int]:
    counts: dict[str, int] = {label: 0 for _, label in CENSUS}
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(8 << 20)
            if not chunk:
                break
            for magic, label in CENSUS:
                counts[label] += chunk.count(magic)
    return counts


def deep_samples(path: Path, size: int) -> list[tuple[int, bytes]]:
    points = [int(size * frac) - (int(size * frac) % 4096) for frac in (0.3, 0.55, 0.8)]
    out = []
    with path.open("rb") as fh:
        for pos in points:
            fh.seek(pos)
            out.append((pos, fh.read(256 << 10)))
    return out


def probe_codecs(path: Path, size: int, gzip_hits: int) -> list[str]:
    """Which decompressors succeed on a real sample? gzip only at a gzip header."""
    ok: list[str] = []
    for pos, blob in deep_samples(path, size):
        for name, fn in (
            ("zlib", lambda b: zlib.decompressobj().decompress(b)),
            ("bz2", lambda b: bz2.BZ2Decompressor().decompress(b)),
            ("lzma", lambda b: lzma.LZMADecompressor().decompress(b)),
        ):
            try:
                fn(blob)
                ok.append(f"{name}@{pos:#x}")
            except Exception:
                pass
    return ok


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    path = Path(argv[1])
    window = 65536
    if "--window" in argv:
        window = int(argv[argv.index("--window") + 1])
    if not path.is_file():
        print(f"not a file: {path}")
        return 2

    size = path.stat().st_size
    with path.open("rb") as fh:
        head = fh.read(65536)

    print(f"file      {path.name}  ({size:,} bytes, {size / 2**20:.1f} MiB)")
    print(f"container {identify(head)}")

    if head.startswith(b"PK\x03\x04"):
        print("\n== ZIP members ==")
        try:
            with zipfile.ZipFile(path) as z:
                for info in z.infolist()[:20]:
                    print(f"  {info.file_size:>14,}  {info.filename}")
                    if not info.is_dir() and info.file_size > 4096:
                        probe = z.open(info).read(65536)
                        print(f"  {'':>14}  inner: {identify(probe)}")
        except zipfile.BadZipFile as exc:
            print(f"  unreadable: {exc}")

    print(f"\n== entropy sweep (window {window:,}) ==")
    low, transitions = sweep(path, window)
    dense = size - sum(b - a for a, b in low)
    print(f"  transitions     {len(transitions)}")
    print(f"  low-entropy runs {len(low):,}  ({sum(b - a for a, b in low):,} bytes)")
    print(f"  dense bytes      {dense:,}  ({dense / max(1, size):.1%} of file)")
    for pos, e in transitions[:12]:
        print(f"    0x{pos:09x}  H={e:5.2f}")
    if len(transitions) > 12:
        print(f"    ... {len(transitions) - 12} more")

    sections = []
    prev_end = 0
    for a, b in low:
        if a - prev_end > 1024:
            sections.append({"start": prev_end, "end": a, "size": a - prev_end})
        prev_end = b
    if size - prev_end > 1024:
        sections.append({"start": prev_end, "end": size, "size": size - prev_end})

    print("\n== magic census over the whole payload ==")
    counts = census(path) if "--no-census" not in argv else {}
    for label, n in counts.items():
        print(f"  {label:<14} {n}")

    print("\n== decompressor probes ==")
    ok = probe_codecs(path, size, counts.get("gzip", 0)) if counts else []
    print(f"  succeeding: {ok or 'none'}")

    print("\n== plaintext head ==")
    strs = re.findall(rb"[\x20-\x7e]{6,}", head)
    print(f"  readable strings (>=6 chars) in first 64 KiB: {len(strs)}")
    for s in strs[:8]:
        print(f"    {s.decode('ascii', 'replace')[:70]}")

    filesystem = sum(counts.get(k, 0) for k in ("squashfs", "UBI", "uImage", "android-boot"))
    print("\n== verdict ==")
    if filesystem:
        verdict = "EXTRACTABLE - a filesystem or kernel image is present"
    elif ok:
        verdict = f"PACKED - decompress with {ok[0].split('@')[0]}"
    elif counts.get("gzip", 0) > 8 and not ok:
        verdict = "MIXED - gzip headers present but no sample decompresses; carve at a header and retry"
    elif dense > size * 0.5:
        verdict = "ENCRYPTED (or compressed) - no filesystem magic, no codec succeeds"
    else:
        verdict = "INCONCLUSIVE - mostly sparse; inspect the low-entropy regions as data, not padding"
    print(f"  {verdict}")
    print(f"  sections carved: {len(sections)}  (gaps are boundaries, not necessarily headers)")

    if sections:
        out = path.with_name("sections.json")
        out.write_text(json.dumps({"file": path.name, "size": size, "window": window,
                                   "gaps": low, "sections": sections}, indent=1),
                       encoding="utf-8")
        print(f"  written: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

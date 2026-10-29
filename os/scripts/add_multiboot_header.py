"""Add a Multiboot header to the kernel.

The Multiboot header is how a kernel says to a bootloader: "load me
this way, and start me like this". It is what GRUB speaks, what
QEMU's `-kernel` speaks, and what every other bootloader on the
planet speaks -- so a kernel with a Multiboot header boots on real
hardware without anything OpenAmer-specific in the boot path.

The header is 8 bytes of magic plus the flags, and it has to appear
in the first 8 KiB of the file, aligned to 4 bytes.

Usage:
    python scripts/add_multiboot_header.py <kernel.elf> <output.elf>
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

# The magic number every Multiboot bootloader looks for.
MULTIBOOT_MAGIC = 0x1BADB002

# The flags: the header asks for the memory map and the module list.
MULTIBOOT_FLAGS = 0x00000003

# The checksum: the magic plus the flags plus the checksum must be
# zero. It is what makes a random block of data not look like a
# header.
MULTIBOOT_CHECKSUM = -(MULTIBOOT_MAGIC + MULTIBOOT_FLAGS)

# The header has to be in the first 8 KiB of the file, aligned to 4.
MAX_HEADER_OFFSET = 8192

# The header itself: the magic, the flags, the checksum.
#
# The checksum is the two's-complement negative of the magic plus the
# flags, so that the sum of all three is zero. It is packed as an
# unsigned 32-bit value because that is how it appears in the file.
HEADER = struct.pack(
    "<III",
    MULTIBOOT_MAGIC,
    MULTIBOOT_FLAGS,
    MULTIBOOT_CHECKSUM & 0xFFFFFFFF,
)


def add_header(data: bytes) -> bytes:
    """Add the Multiboot header to an ELF and return the new bytes."""
    # The header goes into the first LOAD segment, at an offset that
    # is a multiple of 4. The first segment starts at the file's
    # beginning in a link that puts the code first, but the search
    # has to be general.
    #
    # The ELF may be 32-bit or 64-bit, and the program header table
    # has a different layout in each: the 32-bit one uses 4-byte
    # offsets and addresses, the 64-bit one 8-byte ones.
    #
    # The header table's own offset is a 4-byte value in both; the
    # entry size and the entry count are 2-byte values in both.
    if data[4] == 2:
        header_offset = 32
        header_size_at = 54
        header_count_at = 56
        read_dword = lambda o: struct.unpack_from("<Q", data, o)[0]
    else:
        header_offset = 28
        header_size_at = 42
        header_count_at = 44
        read_dword = lambda o: struct.unpack_from("<I", data, o)[0]

    read_word = lambda o: struct.unpack_from("<I", data, o)[0]
    read_halfword = lambda o: struct.unpack_from("<H", data, o)[0]

    program_header_offset = read_word(header_offset)
    program_header_size = read_halfword(header_size_at)
    program_header_count = read_halfword(header_count_at)

    # The header has to sit BEFORE the entry point, both in the file
    # and in memory: a bootloader that finds the header jumps to the
    # entry point, and if the header is there instead of the code, the
    # machine executes the header.
    #
    # The header goes at the end of the last segment that lies below
    # the entry point, and it is aligned to 4 bytes.
    entry = struct.unpack_from("<I", data, 24)[0]

    segments = []
    for index in range(program_header_count):
        header = program_header_offset + index * program_header_size
        segment_type = read_word(header)
        if segment_type != 1:  # PT_LOAD
            continue
        offset = read_dword(header + 4 if data[4] == 1 else header + 8)
        vaddr = read_dword(header + 8 if data[4] == 1 else header + 16)
        size = read_dword(header + 16 if data[4] == 1 else header + 32)
        segments.append((vaddr, offset, size))

    if not segments:
        raise ValueError("the ELF has no loadable segments")

    # The segment that holds the entry point, and the one below it.
    entry_segment = None
    below = None
    for vaddr, offset, size in segments:
        if vaddr <= entry < vaddr + size:
            entry_segment = (vaddr, offset, size)
        elif vaddr + size <= entry:
            if below is None or vaddr + size > below[0] + below[2]:
                below = (vaddr, offset, size)

    if entry_segment is None:
        raise ValueError("no loadable segment contains the entry point")

    vaddr, offset, size = entry_segment
    entry_in_segment = entry - vaddr

    if entry_in_segment >= len(HEADER):
        # There is room in front of the entry point inside its own
        # segment.
        header_offset = offset + entry_in_segment - len(HEADER)
    elif below is not None:
        # The entry point is at the very start of its segment: the
        # header goes at the end of the segment below it.
        header_offset = below[1] + below[2] - len(HEADER)
    else:
        raise ValueError("no room for the Multiboot header")

    # The header must be within the first 8 KiB of the file, and
    # aligned to 4 bytes.
    header_offset &= ~3
    if header_offset + len(HEADER) > MAX_HEADER_OFFSET:
        raise ValueError("the Multiboot header would be outside the first 8 KiB")

    result = bytearray(data)
    result[header_offset : header_offset + len(HEADER)] = HEADER
    return bytes(result)


def main() -> int:
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} <kernel.elf> <output.elf>", file=sys.stderr)
        return 2

    source = Path(sys.argv[1])
    target = Path(sys.argv[2])

    data = source.read_bytes()
    if data[:4] != b"\x7fELF":
        print("not an ELF file", file=sys.stderr)
        return 1

    result = add_header(data)
    target.write_bytes(result)
    print(f"wrote {target} ({len(result)} bytes)")
    print(f"  the Multiboot header is at the start of the first segment")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

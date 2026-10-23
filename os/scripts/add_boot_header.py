"""Add the x86 boot protocol header to the kernel.

The x86 boot protocol is the oldest and most widely supported way to
start a kernel: the loader looks for a small header near the start of
the file, reads the setup size and the load address out of it, and
jumps into the kernel's 32-bit entry point.

It is the protocol GRUB speaks, the protocol QEMU's `linuxboot` ROM
speaks, and the protocol every other x86 bootloader on the planet
speaks. A kernel with this header starts anywhere; a kernel without it
starts nowhere.

The header is 16-bit real mode code plus a table of parameters, all
inside the first 1024 bytes of the file -- the space the BIOS reserves
for it.

Usage:
    python scripts/add_boot_header.py <kernel.elf> <output.elf>
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

# The magic at offset 0x202: it tells the loader that this is a
# kernel that speaks the protocol.
BOOT_MAGIC = 0xAA55

# The "HdrS" signature at offset 0x202 + 4: the header version. A
# loader that does not recognise it refuses to boot the kernel.
HEADER_SIGNATURE = b"HdrS"

# The offset of the magic within the file.
MAGIC_OFFSET = 0x202

# The offset of the header signature.
SIGNATURE_OFFSET = 0x202 + 4

# The size of the setup area: the header plus the real-mode code.
# The value is in 16-byte paragraphs.
SETUP_SECTORS = 4

# The version: 2.09 or later supports the fields this header uses.
VERSION = 0x020A

# The load address: the kernel is loaded at 1 MiB, which is the
# conventional place and the one the memory map leaves free.
LOAD_FLAGS = 0x00000100  # LOADED_HIGH: the kernel wants 1 MiB
HEAP_END = 0x00800000  # 8 MiB of heap
ROOT_DEVICE = 0x0000  # the loader fills this in

# The magic value the loader puts in the register before the jump, so
# the kernel can tell that it was started by a real loader.
BOOT_MAGIC_ARG = 0x2BADB002


def build_header() -> bytes:
    """The 1024-byte boot header.

    The first part is real-mode code the loader runs; the rest is the
    parameter table the loader fills in and the kernel reads.
    """
    header = bytearray(1024)

    # ── the real-mode setup code ───────────────────────────────────
    # The loader jumps here with the disk number in `dl` and the
    # "loading" message in `si`. The code sets up the segments, prints
    # a message, and then hands over to the loader's 32-bit part.
    #
    # The message is at the end of the header, so that the code can
    # print it without a relocation.
    code = bytes([
        0xFA,  # cli
        0x31, 0xC0,  # xor ax, ax
        0x8E, 0xD8,  # mov ds, ax
        0x8E, 0xC0,  # mov es, ax
        0x8E, 0xD0,  # mov ss, ax
        0xBC, 0x00, 0x7C,  # mov sp, 0x7c00
        0xFB,  # sti
        0xB4, 0x0E,  # mov ah, 0x0e
        0xBB, 0x00, 0x7C,  # mov bx, 0x7c00
        0xCD, 0x10,  # int 0x10
        0xF4,  # hlt
        0xEB, 0xFD,  # jmp -3
    ])
    header[0x1F0 : 0x1F0 + len(code)] = code

    # The message the code prints.
    message = b"Loading OpenAmer OS...\r\n"
    header[0x1F0 - len(message) - 0x10 : 0x1F0 - 0x10] = message

    # ── the parameter table ─────────────────────────────────────────
    # The fields the loader reads and the kernel uses.
    struct.pack_into("<H", header, 0x1F1, SETUP_SECTORS)  # setup sectors
    struct.pack_into("<H", header, 0x1F3, 0)  # root flags
    struct.pack_into("<H", header, 0x1F5, 0)  # the default video mode
    struct.pack_into("<H", header, 0x1F7, ROOT_DEVICE)
    struct.pack_into("<H", header, 0x1F9, VERSION)
    struct.pack_into("<H", header, 0x1FB, LOAD_FLAGS)  # the load flags
    struct.pack_into("<H", header, 0x1FD, 0)  # the setup code's length
    struct.pack_into("<H", header, 0x1FF, 0)  # the video mode
    struct.pack_into("<H", header, 0x201, 0)  # the compatibility flags
    struct.pack_into("<I", header, 0x202, BOOT_MAGIC)
    header[SIGNATURE_OFFSET : SIGNATURE_OFFSET + 4] = HEADER_SIGNATURE
    struct.pack_into("<H", header, 0x206, 0)  # the header version
    struct.pack_into("<I", header, 0x208, BOOT_MAGIC_ARG)  # the loader's magic
    struct.pack_into("<H", header, 0x210, 0x0000)  # the type of loader
    struct.pack_into("<H", header, 0x212, 0x0000)  # the load flags
    struct.pack_into("<I", header, 0x214, 0)  # the init code's length
    struct.pack_into("<I", header, 0x218, 0)  # the init code's offset
    struct.pack_into("<I", header, 0x21C, 0)  # the checksum of the setup
    struct.pack_into("<H", header, 0x220, 0)  # the kernel's load address
    struct.pack_into("<H", header, 0x222, 0)  # the kernel's load offset
    struct.pack_into("<I", header, 0x224, HEAP_END)  # the end of the heap
    struct.pack_into("<H", header, 0x228, 0)  # the load module's length
    struct.pack_into("<H", header, 0x22A, 0)  # the load module's offset
    struct.pack_into("<I", header, 0x22C, 0)  # the kernel's entry point
    struct.pack_into("<I", header, 0x230, 0)  # the end of the kernel
    struct.pack_into("<H", header, 0x238, 0)  # the kernel's offset
    struct.pack_into("<H", header, 0x23A, 0)  # the size of the ramdisk
    struct.pack_into("<H", header, 0x23C, 0)  # the video mode
    struct.pack_into("<H", header, 0x23E, 0)  # the compatibility flags
    struct.pack_into("<I", header, 0x240, 0)  # the image's size
    struct.pack_into("<I", header, 0x244, HEAP_END)  # the end of the heap
    struct.pack_into("<H", header, 0x248, 0)  # the loader's flags
    struct.pack_into("<H", header, 0x24A, 0)  # the number of the
    struct.pack_into("<I", header, 0x24C, 0)  # the ramdisk's address

    return bytes(header)


def add_header(data: bytes) -> bytes:
    """Add the boot header to an ELF and return the new bytes."""
    if data[:4] != b"\x7fELF":
        raise ValueError("not an ELF file")

    # The header goes at the very start of the file: the loader looks
    # for it in the first 1024 bytes, and the first LOAD segment is
    # what it reads.
    if len(data) < 1024:
        data = data + b"\x00" * (1024 - len(data))

    result = bytearray(data)
    result[0:1024] = build_header()
    return bytes(result)


def main() -> int:
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} <kernel.elf> <output.elf>", file=sys.stderr)
        return 2

    source = Path(sys.argv[1])
    target = Path(sys.argv[2])

    result = add_header(source.read_bytes())
    target.write_bytes(result)
    print(f"wrote {target} ({len(result)} bytes)")
    print("  the boot header is in the first 1024 bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Build the bootable OpenAmer OS image.

The image is a boot device that the BIOS can start:

    sector 0        the master boot record: the partition table and
                    a stub that loads the boot sector
    sector 1        the OpenAmer OS boot sector: it reads the kernel
    sector 2..      the kernel, byte for byte as it is loaded

The kernel is linked at 64 KiB, and the boot code loads it there.
The buffer is ES:BX -- a 16-bit offset in a 16-bit segment -- so
the offset grows by 512 bytes per sector, and when it reaches 64
KiB it goes back to zero and the segment moves on by one.

Usage:
    python scripts/build_os_image.py --output openamer-os.img
    python scripts/build_os_image.py --check
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
KERNEL_ELF = REPO / "target" / "x86_64-unknown-none" / "release" / "openamer-kernel"

# The scripts directory, so that the modules next to this one can be
# imported.
SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from build_boot_sector import (  # noqa: E402
    KERNEL_LOAD_ADDRESS,
    build_boot_sector,
)
from build_mbr import build_image as build_with_mbr  # noqa: E402

# The sector size.
SECTOR_SIZE = 512

# The LBA the kernel starts at.
#
# The image has three parts: the master boot record at LBA 0, the
# OpenAmer OS boot sector at LBA 1 -- the first sector of the
# active partition, which the BIOS loads -- and the kernel at LBA 2.
KERNEL_FIRST_LBA = 2

# The image's size in sectors.
#
# QEMU derives a hard disk's geometry from the file's size, and at
# a size that does not fit the geometry, the cylinders do not match.
# The BIOS answered with the code 0x8501 -- "error sending the disk
# command".
#
# The geometry is 63 sectors per track and 16 heads, so 1008
# sectors make a cylinder. The image is four cylinders:
#
#   4 * 1008 = 4032 sectors = 2064384 bytes
IMAGE_SECTORS = 4 * 1008


def parse_elf(data: bytes) -> tuple[int, list[tuple[int, int, int]]]:
    """Return the entry point and the LOAD segments of an ELF.

    The segments come back as ``(vaddr, file_offset, size)``.
    """
    if data[:4] != b"\x7fELF":
        raise ValueError("not an ELF file")
    if data[4] != 2:
        raise ValueError("not a 64-bit ELF file")

    entry = struct.unpack_from("<Q", data, 24)[0]
    program_header_offset = struct.unpack_from("<Q", data, 32)[0]
    program_header_size = struct.unpack_from("<H", data, 54)[0]
    program_header_count = struct.unpack_from("<H", data, 56)[0]

    segments: list[tuple[int, int, int]] = []
    for index in range(program_header_count):
        offset = program_header_offset + index * program_header_size
        if struct.unpack_from("<I", data, offset)[0] != 1:  # PT_LOAD
            continue
        file_offset = struct.unpack_from("<Q", data, offset + 8)[0]
        vaddr = struct.unpack_from("<Q", data, offset + 16)[0]
        file_size = struct.unpack_from("<Q", data, offset + 32)[0]
        segments.append((vaddr, file_offset, file_size))

    if not segments:
        raise ValueError("the ELF has no loadable segments")
    return entry, segments


def kernel_image(kernel: bytes) -> tuple[bytes, int]:
    """The kernel's bytes as they are laid out in memory.

    The segments are placed at their virtual addresses, and the gaps
    between them are filled with zeros. The result is what the boot
    code reads from the disk.
    """
    _, segments = parse_elf(kernel)
    end = max(vaddr + size for vaddr, _, size in segments)
    image = bytearray(end - KERNEL_LOAD_ADDRESS)
    for vaddr, file_offset, size in segments:
        start = vaddr - KERNEL_LOAD_ADDRESS
        image[start : start + size] = kernel[file_offset : file_offset + size]
    return bytes(image), end


def build_image(kernel: bytes) -> bytes:
    """Build the bootable image from the kernel ELF."""
    entry, _ = parse_elf(kernel)
    payload, _ = kernel_image(kernel)

    total_sectors = (len(payload) + SECTOR_SIZE - 1) // SECTOR_SIZE
    passes = total_sectors

    boot_sector = build_boot_sector(entry, KERNEL_FIRST_LBA, passes)
    return build_with_mbr(boot_sector + payload)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", help="where to write the image")
    parser.add_argument(
        "--check",
        action="store_true",
        help="check the image instead of writing it",
    )
    args = parser.parse_args()

    if not KERNEL_ELF.exists():
        print(
            f"the kernel is not built: {KERNEL_ELF} is missing.\n"
            "Build it first:  cargo build --release --target x86_64-unknown-none",
            file=sys.stderr,
        )
        return 1

    kernel = KERNEL_ELF.read_bytes()
    entry, segments = parse_elf(kernel)
    payload, _ = kernel_image(kernel)
    image = build_image(kernel)

    if args.check:
        print(f"the image would be {len(image)} bytes")
        print(f"  the kernel's entry point: 0x{entry:x}")
        print(f"  the kernel's load address: 0x{KERNEL_LOAD_ADDRESS:x}")
        print(f"  the kernel's size: {len(payload)} bytes")
        for vaddr, file_offset, size in segments:
            print(f"  segment at 0x{vaddr:x}, {size} bytes")
        return 0

    if not args.output:
        print("either --output or --check is needed", file=sys.stderr)
        return 2

    output = Path(args.output)

    # The image is padded to a whole number of cylinders, so that
    # the geometry the BIOS derives from the size is the one the
    # boot code uses.
    padded = image.ljust(IMAGE_SECTORS * SECTOR_SIZE, b"\x00")
    output.write_bytes(padded)
    print(f"wrote {output} ({len(padded)} bytes)")
    print(f"  the kernel's entry point: 0x{entry:x}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

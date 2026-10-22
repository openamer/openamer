"""Build the master boot record for the OpenAmer OS image.

A hard disk does not boot from its first sector: the BIOS reads the
master boot record, looks for a partition table, finds the active
partition, and loads that partition's first sector -- which is the
OpenAmer OS boot sector.

The MBR's boot code loads that sector with the extended read
(AH = 42h), which takes an LBA and needs no geometry. The old
interface (AH = 02h) would need a CHS address, and the geometry of
the medium is something the BIOS and the boot code have to agree
on -- which is one more thing that can go wrong.

Usage:
    python scripts/build_mbr.py
"""

from __future__ import annotations

import struct

# The MBR's signature.
MBR_SIGNATURE = 0xAA55

# The partition type: 0x0B is FAT32.
PARTITION_TYPE_FAT32 = 0x0B

# The partition's first sector: the boot sector, which the BIOS
# loads and jumps to.
PARTITION_START_LBA = 1

# The sectors per track and the number of heads of the medium. The
# partition table's CHS fields are filled in from them -- the BIOS
# reads the LBA field when it can, and the CHS field only for the
# old interface.
SECTORS_PER_TRACK = 63
HEADS = 16

# The address the boot sector is loaded to. It is not 0x7C00 -- the
# MBR's own address. Loading the boot sector there overwrote the
# MBR's code, and the short jump that reached the MBR's error
# handler then jumped into the boot sector's bytes.
BOOT_SECTOR_ADDRESS = 0x7E00


def chs(lba: int) -> tuple[int, int]:
    """The CHS address of an LBA, as two bytes.

    The first byte holds the head in its lower six bits and the
    cylinder's upper two bits above it. The second holds the sector
    in its lower six bits and the cylinder's lower two bits above
    it.
    """
    cylinder = lba // (SECTORS_PER_TRACK * HEADS)
    head = (lba // SECTORS_PER_TRACK) % HEADS
    sector = (lba % SECTORS_PER_TRACK) + 1

    if cylinder > 1023:
        cylinder = 1023
    if head > 63:
        head = 63

    return (
        (head & 0x3F) | ((cylinder >> 2) & 0xC0),
        ((cylinder & 0x03) << 6) | (sector & 0x3F),
    )


def build_partition_entry(lba: int, sectors: int) -> bytes:
    """One partition table entry."""
    first = chs(lba)
    last = chs(lba + sectors - 1)

    entry = bytearray(16)
    entry[0] = 0x80  # the status: the active partition
    entry[1] = first[0]
    entry[2] = first[1]
    entry[3] = 0x00
    entry[4] = PARTITION_TYPE_FAT32
    entry[5] = last[0]
    entry[6] = last[1]
    entry[7] = 0x00
    struct.pack_into("<I", entry, 8, lba)
    struct.pack_into("<I", entry, 12, sectors)
    return bytes(entry)


def build_mbr(kernel_sectors: int) -> bytes:
    """The master boot record.

    The boot code loads the partition's first sector -- the OpenAmer
    OS boot sector -- and jumps to it.
    """
    code = bytearray()

    def emit(*values: int) -> None:
        for value in values:
            code.append(value & 0xFF)

    # The boot code follows the jump, and the jump points at it.
    #
    #   0x000  the jump
    #   0x002  the boot code
    #   0x0BE  the OEM name and the gap
    #   0x1BE  the partition table
    #   0x1FE  the signature
    emit(0xEB, 0x00)  # jmp <the boot code> -- the distance is patched
    jump_distance = len(code) - 1

    emit(0xFA)  # cli
    emit(0x31, 0xC0)  # xor ax, ax
    emit(0x8E, 0xD8, 0x8E, 0xC0, 0x8E, 0xD0)  # mov ds/es/ss, ax
    # The stack goes to 0x6C00.
    #
    # At 0x7C00 -- the MBR's own address -- the BIOS's interrupt
    # frame grew into the MBR's code: the bytes behind the
    # `int 0x13` were the BIOS's frame, and the processor came back
    # and executed it instead of the MBR's own code.
    emit(0xBC, 0x00, 0x6C)  # mov sp, 0x6c00

    # The drive number, which the BIOS left in DL.
    emit(0x88, 0x16, 0x20, 0x7F)  # mov [0x7F20], dl

    # ── the disk address packet ───────────────────────────────────
    # The extended read takes the packet in DS:SI.
    #
    #   0x00  the size of the packet: 16
    #   0x01  reserved
    #   0x02  the number of sectors
    #   0x04  the buffer: the offset
    #   0x06  the buffer: the segment
    #   0x08  the LBA, 64 bits
    emit(0xC7, 0x06, 0x00, 0x7F, 0x10, 0x00)  # the size
    emit(0xC6, 0x06, 0x01, 0x7F, 0x00)  # reserved
    emit(0xC7, 0x06, 0x02, 0x7F, 0x01, 0x00)  # one sector
    emit(0xC7, 0x06, 0x04, 0x7F, 0x00, 0x00)  # the buffer's offset
    emit(
        0xC7,
        0x06,
        0x06,
        0x7F,
        (BOOT_SECTOR_ADDRESS // 16) & 0xFF,
        (BOOT_SECTOR_ADDRESS // 16) >> 8,
    )  # the buffer's segment
    emit(0xC7, 0x06, 0x08, 0x7F, PARTITION_START_LBA & 0xFF, 0x00)
    emit(0xC7, 0x06, 0x0A, 0x7F, 0x00, 0x00)
    emit(0xC7, 0x06, 0x0C, 0x7F, 0x00, 0x00)
    emit(0xC7, 0x06, 0x0E, 0x7F, 0x00, 0x00)

    # The read.
    emit(0xB0, 0x00)  # mov al, 0x00 -- the read
    emit(0xB4, 0x42)  # mov ah, 0x42
    # DL is the drive number, which the BIOS left there when it
    # called the boot code.
    #
    # The BIOS's dispatch compares DL with 0x0F to tell a floppy
    # from a hard disk:
    #
    #   cmpb $0xf, %dl     ja  <the error path>
    #
    # So a version in DL -- 0x42 -- took the error path. The
    # version is in the packet itself: the "size" field.
    emit(0x8A, 0x16, 0x20, 0x7F)  # mov dl, [0x7F20]
    emit(0xBE, 0x00, 0x7F)  # mov si, 0x7F00 -- the packet
    emit(0xF8)  # clc -- the BIOS sets the carry flag on an error
    emit(0xCD, 0x13)  # int 0x13
    emit(0x72, 0x00)  # jc disk_error
    read_error_jump = len(code) - 2

    # Into the boot sector.
    emit(0xEA, 0x00, 0x7E, 0x00, 0x00)  # jmp 0x0000:0x7E00

    disk_error = len(code)
    emit(0xBA, 0xE9, 0x00)  # mov dx, 0xE9 -- the debug port
    emit(0x86, 0xC4)  # xchg ah, al -- the error code is in AH
    emit(0xEE)  # out dx, al
    emit(0x86, 0xC4)  # xchg ah, al
    emit(0xF4)  # hlt
    emit(0xEB, 0xFD)  # jmp -3

    # The jump's distance. The jump is at offset 0, its operand at
    # offset 1, and the boot code starts at offset 2. The distance is
    # measured from the byte after the instruction, so it is the
    # target minus two -- and the boot code follows the jump
    # directly, so it is zero.
    code[jump_distance] = 0

    # The jump to the error handler: a short jump's distance is a
    # signed byte, measured from the byte after the instruction.
    distance = disk_error - (read_error_jump + 2)
    if not -128 <= distance <= 127:
        raise ValueError(
            f"the jump at 0x{read_error_jump:x} is {distance} bytes away -- "
            "too far for a short jump"
        )
    code[read_error_jump + 1] = distance & 0xFF

    # The OEM name, and the rest of the gap.
    code.extend(b"OpenAmer")
    code.extend(b"\x00" * (0x1BE - len(code)))

    # The partition table: one active partition, and three empty ones.
    code.extend(build_partition_entry(PARTITION_START_LBA, 0xFFFF))
    code.extend(b"\x00" * 48)

    # The signature.
    code.extend(struct.pack("<H", MBR_SIGNATURE))

    if len(code) != 512:
        raise ValueError(f"the MBR is {len(code)} bytes, not 512")

    return bytes(code)


def build_image(payload: bytes) -> bytes:
    """The image: the MBR, the boot sector, and the kernel."""
    kernel_sectors = (len(payload) + 511) // 512
    mbr = build_mbr(kernel_sectors)

    # The boot sector follows the MBR.
    image = bytearray(512 + len(payload))
    image[0:512] = mbr
    image[512:] = payload
    return bytes(image)

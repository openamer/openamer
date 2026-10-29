"""Build the OpenAmer OS boot sector.

The boot sector reads the kernel from the disk and hands control to
it. It is hand-assembled, because it has to fit in 512 bytes and be
position independent.

Two facts from the BIOS specification shape the code.

The CHS address, for the old read interface (AH = 02h):

    CH   the cylinder, its lower eight bits
    CL   bits 0-5 the sector, bits 6-7 the cylinder's upper two bits
    DH   the head

The code had the head in CH and the sector in CL, and the BIOS
rejected every read.

The extended interface (AH = 42h) takes an LBA and needs no
geometry at all. The master boot record uses it, and it works, so
the boot sector uses it as well -- the read is the same for every
sector and no arithmetic is needed.

The boot sector runs at 0x7E00: the master boot record loads it
there and jumps to it. Everything the code needs lives in the
sector's own bytes, at fixed offsets near the end:

    0x1A0  the GDT
    0x1C0  the GDT pointer
    0x1D0  the disk address packet
    0x1E0  the variables

Usage:
    python scripts/build_boot_sector.py
"""

from __future__ import annotations

import struct

# The address the boot sector runs at. The master boot record
# loads it there and jumps to it.
BOOT_SECTOR_BASE = 0x7E00

# The offsets of the boot sector's own data.
GDT_OFFSET = 0x1A0
GDT_POINTER_OFFSET = 0x1C0
PACKET_OFFSET = 0x1D0
VARIABLES_OFFSET = 0x1E0

# The signature the BIOS looks for in the last two bytes.
BOOT_SIGNATURE = 0xAA55

# The address the kernel is linked at. The boot code loads it
# there.
KERNEL_LOAD_ADDRESS = 0x10000

# The sectors one pass reads. One sector is 512 bytes, and the
# buffer is a 16-bit offset in a 16-bit segment, so the offset
# grows by 512 bytes per sector and the segment moves on when the
# offset reaches 64 KiB.
SECTORS_PER_PASS = 1

# The variables, at their offsets in the boot sector.
VARIABLE_COUNT = 0x1E0  # the number of sectors still to read
VARIABLE_OFFSET = 0x1E2  # the buffer: the offset
VARIABLE_SEGMENT = 0x1E4  # the buffer: the segment
VARIABLE_LBA = 0x1E6  # the LBA
VARIABLE_DRIVE = 0x1E8  # the drive number


def absolute(offset: int) -> int:
    """The absolute address of a byte in the boot sector.

    The boot sector runs at 0x7E00, and the segment registers are
    zero, so the absolute address of the offset X is 0x7E00 + X.
    """
    return BOOT_SECTOR_BASE + offset


def build_boot_sector(entry: int, kernel_first_lba: int, passes: int) -> bytes:
    """The boot sector: read the kernel, switch to protected mode."""
    code = bytearray()

    def emit(*values: int) -> None:
        for value in values:
            code.append(value & 0xFF)

    def emit_word_at(offset: int, value: int) -> None:
        """A `mov word [addr], value` instruction."""
        address = absolute(offset)
        emit(0xC7, 0x06, address & 0xFF, (address >> 8) & 0xFF)
        emit(value & 0xFF, (value >> 8) & 0xFF)

    def emit_byte_at(offset: int, value: int) -> None:
        """A `mov byte [addr], value` instruction."""
        address = absolute(offset)
        emit(0xC6, 0x06, address & 0xFF, (address >> 8) & 0xFF, value & 0xFF)

    # The drive number, which the BIOS left in DL. It goes into the
    # boot sector's own bytes: the copy used to go to 0x7DFC, which
    # is in the BIOS's own memory area, and the BIOS writes over
    # that.
    emit(0x88, 0x16, absolute(VARIABLE_DRIVE) & 0xFF, (absolute(VARIABLE_DRIVE) >> 8) & 0xFF)

    # ── real mode ──────────────────────────────────────────────────
    emit(0xFA, 0xFC)  # cli; cld
    emit(0x31, 0xC0)  # xor ax, ax
    # DS, ES and SS stay zero.
    #
    # The BIOS's interrupt handlers read the BIOS data area -- at
    # 0x40 -- through SS, and with SS pointing elsewhere they read
    # rubbish. The interrupt's return then jumped to 0.
    emit(0x8E, 0xD8, 0x8E, 0xC0, 0x8E, 0xD0)  # mov ds/es/ss, ax
    # The stack goes to 0x6A00 -- below the boot sector, above the
    # BIOS's own data -- so that the BIOS's interrupt frame does
    # not grow into the code.
    emit(0xBC, 0x00, 0x6A)  # mov sp, 0x6a00

    # ── the read's state ───────────────────────────────────────────
    emit_word_at(VARIABLE_COUNT, passes)
    emit_word_at(VARIABLE_OFFSET, 0)
    emit_word_at(VARIABLE_SEGMENT, KERNEL_LOAD_ADDRESS // 16)
    emit_word_at(VARIABLE_LBA, kernel_first_lba)

    # ── the disk address packet ───────────────────────────────────
    # The extended read takes the packet in DS:SI.
    #
    #   0x00  the size of the packet: 16
    #   0x01  reserved
    #   0x02  the number of sectors
    #   0x04  the buffer: the offset
    #   0x06  the buffer: the segment
    #   0x08  the LBA, 64 bits
    emit_word_at(PACKET_OFFSET + 0, 16)  # the size
    emit_byte_at(PACKET_OFFSET + 1, 0)  # reserved
    emit_word_at(PACKET_OFFSET + 2, SECTORS_PER_PASS)  # the count
    emit_word_at(PACKET_OFFSET + 4, 0)  # the buffer's offset
    emit_word_at(PACKET_OFFSET + 6, KERNEL_LOAD_ADDRESS // 16)  # the segment
    emit_word_at(PACKET_OFFSET + 8, kernel_first_lba)  # the LBA, low half
    emit_word_at(PACKET_OFFSET + 10, 0)  # the LBA, the next two
    emit_word_at(PACKET_OFFSET + 12, 0)  # the LBA, the high two
    emit_word_at(PACKET_OFFSET + 14, 0)

    # ── the read loop ──────────────────────────────────────────────
    read_loop = len(code)

    # The buffer: ES is the segment, BX the offset.
    emit(0xA1, absolute(VARIABLE_SEGMENT) & 0xFF, (absolute(VARIABLE_SEGMENT) >> 8) & 0xFF)
    emit(0x8E, 0xC0)  # mov es, ax
    emit(0xA1, absolute(VARIABLE_OFFSET) & 0xFF, (absolute(VARIABLE_OFFSET) >> 8) & 0xFF)
    emit(0x89, 0xC3)  # mov bx, ax

    # The packet's count, the buffer and the LBA go into the packet
    # before every read: they move with the read.
    emit_word_at(PACKET_OFFSET + 2, SECTORS_PER_PASS)
    emit(0xA1, absolute(VARIABLE_OFFSET) & 0xFF, (absolute(VARIABLE_OFFSET) >> 8) & 0xFF)
    emit(0x89, 0x06, absolute(PACKET_OFFSET + 4) & 0xFF, (absolute(PACKET_OFFSET + 4) >> 8) & 0xFF)
    emit(0xA1, absolute(VARIABLE_SEGMENT) & 0xFF, (absolute(VARIABLE_SEGMENT) >> 8) & 0xFF)
    emit(0x89, 0x06, absolute(PACKET_OFFSET + 6) & 0xFF, (absolute(PACKET_OFFSET + 6) >> 8) & 0xFF)
    emit(0xA1, absolute(VARIABLE_LBA) & 0xFF, (absolute(VARIABLE_LBA) >> 8) & 0xFF)
    emit(0x89, 0x06, absolute(PACKET_OFFSET + 8) & 0xFF, (absolute(PACKET_OFFSET + 8) >> 8) & 0xFF)

    # The read.
    emit(0xB0, 0x00)  # mov al, 0x00 -- the read
    emit(0xB4, 0x42)  # mov ah, 0x42
    # DL is the drive number, which the BIOS left there when it
    # called the boot code. The packet's version is not in DL: the
    # BIOS's dispatch compares DL with 0x0F to tell a floppy from a
    # hard disk, and a version in DL took the floppy's path.
    emit(0x8A, 0x16, absolute(VARIABLE_DRIVE) & 0xFF, (absolute(VARIABLE_DRIVE) >> 8) & 0xFF)
    emit(0xBE, absolute(PACKET_OFFSET) & 0xFF, (absolute(PACKET_OFFSET) >> 8) & 0xFF)  # mov si, the packet
    emit(0xF8)  # clc -- the BIOS sets the carry flag on an error
    # The interrupts stay off.
    #
    # The `sti` before the read let the timer interrupt fire while
    # the processor was in the BIOS's handler. That handler expects
    # protected mode, and the machine jumped into the BIOS's code.
    # And on the way back the carry flag was set -- so the error
    # path was taken even though the read had worked.
    emit(0xCD, 0x13)  # int 0x13
    emit(0x72, 0x00)  # jc disk_error
    read_error_jump = len(code) - 2  # the opcode's own position

    # The next pass: the LBA and the buffer move on by one sector.
    emit(0x83, 0x06, absolute(VARIABLE_LBA) & 0xFF, (absolute(VARIABLE_LBA) >> 8) & 0xFF, 0x01)
    emit(0x83, 0x06, absolute(VARIABLE_OFFSET) & 0xFF, (absolute(VARIABLE_OFFSET) >> 8) & 0xFF, 0x20)
    # The offset reaches 64 KiB: it goes back to zero and the
    # segment moves on by one.
    emit(0x81, 0xFE, absolute(VARIABLE_OFFSET) & 0xFF, (absolute(VARIABLE_OFFSET) >> 8) & 0xFF, 0x00, 0x00)
    emit(0x75, 0x04)  # jne offset_ok
    offset_jump = len(code) - 2  # the opcode's own position
    # The segment moves on by 0x800 paragraphs -- 64 KiB, a whole
    # segment. It moved on by one, and the buffer ended up 16 bytes
    # further instead of 64 KiB further: after 128 sectors the BIOS
    # wrote over the area it had already filled.
    emit(0x81, 0x06, absolute(VARIABLE_SEGMENT) & 0xFF, (absolute(VARIABLE_SEGMENT) >> 8) & 0xFF, 0x00, 0x08)
    emit_word_at(VARIABLE_OFFSET, 0)
    offset_ok = len(code)

    # The jump back into the loop is a near jump: the loop is longer
    # than a short jump's signed byte reaches.
    #
    #   E9 <rel16>   jmp <rel16>
    emit(0xE9, 0x00, 0x00)
    read_loop_jump = len(code) - 3  # the opcode's own position

    # The counter.
    emit(0xFF, 0x0E, absolute(VARIABLE_COUNT) & 0xFF, (absolute(VARIABLE_COUNT) >> 8) & 0xFF)
    emit(0x75, 0x00)  # jnz read_loop
    counter_jump = len(code) - 2  # the opcode's own position

    # ── the disk failed ───────────────────────────────────────────
    # The handler goes here, right behind the code that reaches it:
    # a short jump's distance is a signed byte, so it reaches at
    # most 127 bytes forward and 128 bytes back.
    disk_error = len(code)
    emit(0xBA, 0xE9, 0x00)  # mov dx, 0xE9 -- the debug port
    emit(0x86, 0xC4)  # xchg ah, al -- the error code is in AH
    emit(0xEE)  # out dx, al
    emit(0x86, 0xC4)  # xchg ah, al
    emit(0xF4)  # hlt
    emit(0xEB, 0xFD)  # jmp -3

    # ── the A20 gate ──────────────────────────────────────────────
    emit(0xE4, 0x92)  # in al, 0x92
    emit(0xA8, 0x02)  # test al, 2
    emit(0x75, 0x06)  # jnz a20_done
    emit(0x0C, 0x02)  # or al, 2
    emit(0xE6, 0x92)  # out 0x92, al
    a20_done = len(code)

    # ── the GDT and protected mode ────────────────────────────────
    emit(0x0F, 0x01, 0x16)  # lgdt [gdt_pointer]
    gdt_pointer_operand = len(code)
    emit(0x00, 0x00)

    emit(0x0F, 0x20, 0xC0)  # mov eax, cr0
    emit(0x0D, 0x05, 0x00, 0x00, 0x00, 0x80)  # or eax, 0x80000000
    emit(0x0F, 0x22, 0xC0)  # mov cr0, eax

    # The jump into protected mode. It needs a 32-bit offset: the
    # kernel is at 0x10000, and 0x10000 does not fit in 16 bits.
    # The offset was cut off, and the processor jumped to 0x0000.
    #
    #   66 EA <offset:32> <selector:16>   jmp far
    emit(0x66, 0xEA)
    protected_mode_offset = len(code)
    emit(0x00, 0x00, 0x00, 0x00, 0x08, 0x00)

    # ── protected mode ────────────────────────────────────────────
    protected_mode = len(code)
    code[protected_mode_offset] = protected_mode & 0xFF
    code[protected_mode_offset + 1] = (protected_mode >> 8) & 0xFF
    code[protected_mode_offset + 2] = (protected_mode >> 16) & 0xFF
    code[protected_mode_offset + 3] = (protected_mode >> 24) & 0xFF

    emit(0x66, 0xB8, 0x10, 0x00)  # mov ax, 0x10
    emit(0x8E, 0xD8, 0x8E, 0xC0, 0x8E, 0xD0)  # mov ds/es/ss, ax

    # Into the kernel.
    #
    # The selector is 0x08 -- the code segment of the GDT. It was
    # 0x00, and that is the null descriptor: the processor raised a
    # fault and landed at 0x0000.
    emit(0x66, 0xEA)
    kernel_jump_offset = len(code)
    emit(0x00, 0x00, 0x00, 0x00, 0x08, 0x00)

    # ── the data ───────────────────────────────────────────────────
    # The GDT, the GDT pointer, the packet and the variables live at
    # their fixed offsets. The code ends here, and the rest of the
    # sector is filled in below.
    data_start = len(code)
    if data_start > GDT_OFFSET:
        raise ValueError(
            f"the boot code is {data_start} bytes long -- it does not fit "
            f"before the data at 0x{GDT_OFFSET:x}"
        )

    # The GDT: a null descriptor, a flat code segment, a flat data
    # segment, and a 64-bit code segment.
    gdt = bytearray()

    def gdt_entry(base: int, limit: int, access: int, flags: int) -> None:
        # The limit is sixteen bits, and it goes into the entry as
        # two bytes: the low half first, the high nibble together
        # with the flags in the fourth byte.
        gdt.append(limit & 0xFF)
        gdt.append((limit >> 8) & 0xFF)
        gdt.append(base & 0xFF)
        gdt.append((base >> 16) & 0xFF)
        gdt.append(access)
        gdt.append(((limit >> 16) & 0x0F) | (flags & 0xF0))
        gdt.append((base >> 24) & 0xFF)

    gdt_entry(0, 0, 0x00, 0x00)  # the null descriptor
    gdt_entry(0, 0xFFFFF, 0x9A, 0xC0)  # the code segment
    gdt_entry(0, 0xFFFFF, 0x92, 0xC0)  # the data segment
    gdt_entry(0, 0xFFFFF, 0x9A, 0xA0)  # the 64-bit code segment

    # The GDT pointer: the limit, then the base.
    gdt_base = absolute(GDT_OFFSET)
    gdt_pointer = bytearray(struct.pack("<H", len(gdt)))
    gdt_pointer += struct.pack("<I", gdt_base)

    # The packet, with the values the loop writes into it.
    packet = bytearray(16)
    packet[0] = 16  # the size
    packet[2] = SECTORS_PER_PASS & 0xFF
    packet[3] = (SECTORS_PER_PASS >> 8) & 0xFF
    struct.pack_into("<H", packet, 6, KERNEL_LOAD_ADDRESS // 16)
    struct.pack_into("<H", packet, 8, kernel_first_lba)

    # The variables.
    variables = bytearray(8)
    struct.pack_into("<H", variables, 0, passes)

    # The data goes into the sector at its fixed offsets.
    def place(offset: int, data: bytes) -> None:
        if offset + len(data) > 512:
            raise ValueError(f"the data at 0x{offset:x} does not fit in the sector")
        # The code is shorter than the offsets, so the sector is
        # filled with zeros up to the offset first.
        #
        # Without that, the assignment `code[offset:offset+len] =
        # data` put the data at the *end* of the code -- Python cuts
        # the slice at the end of the list, and appends there. The
        # GDT ended up at the wrong place, and the processor loaded
        # zeroes into the segment registers.
        if len(code) < offset:
            code.extend(b"\x00" * (offset - len(code)))
        code[offset : offset + len(data)] = data

    place(GDT_OFFSET, bytes(gdt))
    place(GDT_POINTER_OFFSET, bytes(gdt_pointer))
    place(PACKET_OFFSET, bytes(packet))
    place(VARIABLES_OFFSET, bytes(variables))

    # The lgdt operand: the linear address of the pointer.
    code[gdt_pointer_operand] = gdt_base & 0xFF
    code[gdt_pointer_operand + 1] = (gdt_base >> 8) & 0xFF

    # The kernel's address goes into the far jump.
    code[kernel_jump_offset] = entry & 0xFF
    code[kernel_jump_offset + 1] = (entry >> 8) & 0xFF
    code[kernel_jump_offset + 2] = (entry >> 16) & 0xFF
    code[kernel_jump_offset + 3] = (entry >> 24) & 0xFF

    def set_jump(position: int, target: int) -> None:
        # The position is the opcode's own, and the distance is
        # measured from the byte after the instruction.
        distance = target - (position + 2)
        if not -128 <= distance <= 127:
            raise ValueError(
                f"the jump at 0x{position:x} is {distance} bytes away -- "
                "too far for a short jump"
            )
        code[position + 1] = distance & 0xFF

    def set_near_jump(position: int, target: int) -> None:
        # The position is the opcode's own, and the distance is
        # measured from the byte after the three-byte instruction.
        distance = target - (position + 3)
        code[position + 1] = distance & 0xFF
        code[position + 2] = (distance >> 8) & 0xFF

    set_jump(read_error_jump, disk_error)
    set_jump(offset_jump, offset_ok)
    set_jump(counter_jump, read_loop)
    set_near_jump(read_loop_jump, read_loop)

    if len(code) > 510:
        raise ValueError(f"the boot sector is too big: {len(code)} bytes")

    code.extend(b"\x00" * (510 - len(code)))
    code.extend(struct.pack("<H", BOOT_SIGNATURE))
    return bytes(code)

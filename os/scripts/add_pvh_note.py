"""Add the PVH ELF note to the kernel.

QEMU (and the Linux boot protocol in general) can load an ELF kernel
directly -- but only if the ELF carries a note that says where the
kernel wants to be entered and what it expects to find in the
registers.

That note is the PVH note: "Protocol Virtual Host". It is three
32-bit words in a note section:

    the entry point offset from the start of the file,
    the physical address of the entry point,
    the physical address of the start of the .bss section.

With the note in place, the kernel can be started by QEMU's `-kernel`,
by GRUB, and by any other loader that speaks the Linux boot
protocol -- which is exactly what an installer on real hardware needs.

The note has to be in a PT_NOTE segment: that is where the loaders
look for it, and a note that is only in a section is invisible to
them.

Usage:
    python scripts/add_pvh_note.py <kernel.elf> <output.elf>
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

# The note's name and type. "PVH" is the note type the boot protocol
# defines; the name is the four-byte string "Xen".
NOTE_TYPE = 0x12  # XEN_ELFNOTE_PHYS32_ENTRY
NOTE_NAME = b"Xen\x00"

# The note section's alignment.
NOTE_ALIGNMENT = 4


class Elf:
    """The parts of an ELF the note insertion needs.

    A 32-bit and a 64-bit ELF differ in the width of their addresses
    and offsets, and in where the header tables live. Rather than two
    copies of the same code, the widths are read through these.
    """

    def __init__(self, data: bytes) -> None:
        self.data = data
        self.is_64 = data[4] == 2

        if self.is_64:
            self.address = lambda o: struct.unpack_from("<Q", data, o)[0]
            self.entry = struct.unpack_from("<Q", data, 24)[0]
            self.program_header_offset = struct.unpack_from("<Q", data, 32)[0]
            self.section_header_offset = struct.unpack_from("<Q", data, 40)[0]
            self.program_header_size = struct.unpack_from("<H", data, 54)[0]
            self.program_header_count = struct.unpack_from("<H", data, 56)[0]
            self.section_header_size = struct.unpack_from("<H", data, 58)[0]
            self.section_count = struct.unpack_from("<H", data, 60)[0]
            self.string_table_index = struct.unpack_from("<H", data, 62)[0]
            self.program_header_count_at = 56
            self.section_count_at = 60
        else:
            self.address = lambda o: struct.unpack_from("<I", data, o)[0]
            self.entry = struct.unpack_from("<I", data, 24)[0]
            self.program_header_offset = struct.unpack_from("<I", data, 28)[0]
            self.section_header_offset = struct.unpack_from("<I", data, 32)[0]
            self.program_header_size = struct.unpack_from("<H", data, 42)[0]
            self.program_header_count = struct.unpack_from("<H", data, 44)[0]
            self.section_header_size = struct.unpack_from("<H", data, 46)[0]
            self.section_count = struct.unpack_from("<H", data, 48)[0]
            self.string_table_index = struct.unpack_from("<H", data, 50)[0]
            self.program_header_count_at = 44
            self.section_count_at = 48

        # The segment offsets differ too: in a 64-bit ELF the file
        # offset is at +8, in a 32-bit one at +4.
        # The program header's fields: p_offset, p_vaddr, p_filesz,
        # p_memsz.
        self.segment_file_offset = 8 if self.is_64 else 4
        self.segment_vaddr = 16 if self.is_64 else 8
        self.segment_physical = 24 if self.is_64 else 12
        self.segment_file_size = 32 if self.is_64 else 16
        self.segment_memory_size = 40 if self.is_64 else 20

        # The section header's fields have their OWN layout, and it is
        # not the program header's: sh_name, sh_type, sh_flags,
        # sh_addr, sh_offset, sh_size. Using the program header's
        # offsets for a section header reads the wrong numbers -- the
        # section table's addresses instead of its file offsets.
        self.section_file_offset = 24 if self.is_64 else 16
        self.section_size = 32 if self.is_64 else 20
        self.section_address = 16 if self.is_64 else 12

    def program_headers(self) -> list[tuple[int, int, int, int]]:
        """The program headers as ``(type, file_offset, vaddr, size)``."""
        headers = []
        for index in range(self.program_header_count):
            offset = self.program_header_offset + index * self.program_header_size
            segment_type = struct.unpack_from("<I", self.data, offset)[0]
            file_offset = self.address(offset + self.segment_file_offset)
            vaddr = self.address(offset + self.segment_vaddr)
            file_size = self.address(offset + self.segment_file_size)
            headers.append((segment_type, file_offset, vaddr, file_size))
        return headers


def add_note(
    data: bytes, entry: int, paddr: int, bss_addr: int, note_vaddr: int
) -> bytes:
    """Add the PVH note to an ELF and return the new bytes."""
    elf = Elf(data)

    # The note itself: namesz, descsz, type, name, descriptor.
    descriptor = struct.pack("<III", entry, paddr, bss_addr)
    name = NOTE_NAME
    note = struct.pack(
        "<III", len(name), len(descriptor), NOTE_TYPE
    ) + name + descriptor

    # The note section's name in the string table: ".notes".
    section_name = b".notes\x00"

    # The string table.
    string_header = (
        elf.section_header_offset + elf.string_table_index * elf.section_header_size
    )
    string_offset = elf.address(string_header + elf.section_file_offset)
    string_size = elf.address(string_header + elf.section_size)
    strings = data[string_offset : string_offset + string_size]

    # The note goes right behind the first LOAD segment: there is
    # space there, and both its file address and the address it will
    # have in memory are known before anything is written.
    first_load_end = 0
    for segment_type, file_offset, vaddr, file_size in elf.program_headers():
        if segment_type != 1:  # PT_LOAD
            continue
        first_load_end = max(first_load_end, file_offset + file_size)

    note_offset = (first_load_end + NOTE_ALIGNMENT - 1) & ~(NOTE_ALIGNMENT - 1)

    # The new string table: the old one plus the new section's name.
    new_string_offset = note_offset + len(note)
    new_strings = strings + section_name
    new_string_name_offset = len(strings)

    # The section header table moves to the end, after the new string
    # table.
    new_section_header_offset = (
        new_string_offset + len(new_strings) + NOTE_ALIGNMENT - 1
    ) & ~(NOTE_ALIGNMENT - 1)

    # The program header table moves after the section headers.
    new_program_header_offset = new_section_header_offset + (
        elf.section_count + 1
    ) * elf.section_header_size

    # Build the new file.
    out = bytearray()
    out.extend(data[:note_offset])
    out.extend(note)
    out.extend(b"\x00" * (new_string_offset - len(out)))
    out.extend(new_strings)
    out.extend(b"\x00" * (new_section_header_offset - len(out)))

    # The section headers: the original ones, with the string table
    # updated, plus the new note section.
    for index in range(elf.section_count):
        header = bytearray(
            data[
                elf.section_header_offset + index * elf.section_header_size :
                elf.section_header_offset + (index + 1) * elf.section_header_size
            ]
        )
        if index == elf.string_table_index:
            struct.pack_into(
                "<I", header, elf.section_file_offset, new_string_offset
            )
            struct.pack_into(
                "<I", header, elf.section_size, len(new_strings)
            )
        out.extend(header)

    # The new note section's header.
    #
    # The section header's layout is its own: sh_name, sh_type,
    # sh_flags, sh_addr, sh_offset, sh_size. The flags are a 64-bit
    # field in the 64-bit form and a 32-bit one in the 32-bit form,
    # and they say that the section is part of the loaded image.
    note_header = bytearray(elf.section_header_size)
    struct.pack_into("<I", note_header, 0, new_string_name_offset)
    struct.pack_into("<I", note_header, 4, 7)  # SHT_NOTE
    if elf.is_64:
        struct.pack_into("<Q", note_header, 8, 0x2)  # SHF_ALLOC
    else:
        struct.pack_into("<I", note_header, 8, 0x2)  # SHF_ALLOC
    struct.pack_into("<I", note_header, elf.section_address, note_offset)
    struct.pack_into("<I", note_header, elf.section_file_offset, note_offset)
    struct.pack_into("<I", note_header, elf.section_size, len(note))
    out.extend(note_header)

    # The program headers: the original ones, copied verbatim, plus a
    # PT_NOTE segment for the note.
    for index in range(elf.program_header_count):
        start = elf.program_header_offset + index * elf.program_header_size
        out.extend(data[start : start + elf.program_header_size])

    # The PT_NOTE segment. The physical address is the address the
    # loader will place the note at: the note is read from the file,
    # and the address tells the loader where the entry point is.
    note_program_header = bytearray(elf.program_header_size)
    struct.pack_into("<I", note_program_header, 0, 4)  # PT_NOTE
    struct.pack_into("<I", note_program_header, 4, 4)  # PF_R
    struct.pack_into(
        "<I" if elf.is_64 else "<I", note_program_header, elf.segment_file_offset,
        note_offset,
    )
    # p_vaddr: where the note lands in memory. The loader places the
    # segments at their virtual addresses, so the note's address has
    # to be the note's file offset translated the same way the
    # segments are: the load address plus the offset within the
    # first segment.
    struct.pack_into(
        "<I" if elf.is_64 else "<I", note_program_header, elf.segment_vaddr,
        note_vaddr,
    )
    # p_paddr: the physical address of the note. The loader reads the
    # note from the file, but it wants to know where the entry point
    # is in physical memory -- and that is what the note's descriptor
    # says, not the segment's p_paddr. The segment's own p_paddr is
    # the address the loader would place the note at, which is zero
    # for a note that is read from the file.
    struct.pack_into(
        "<I" if elf.is_64 else "<I", note_program_header,
        elf.segment_physical, paddr,
    )
    struct.pack_into(
        "<I" if elf.is_64 else "<I", note_program_header, elf.segment_file_size, len(note)
    )
    struct.pack_into(
        "<I" if elf.is_64 else "<I", note_program_header,
        elf.segment_memory_size, len(note)
    )
    out.extend(note_program_header)

    # The ELF header: the new header table offsets and counts.
    if elf.is_64:
        struct.pack_into("<Q", out, 32, new_program_header_offset)
        struct.pack_into("<Q", out, 40, new_section_header_offset)
    else:
        struct.pack_into("<I", out, 28, new_program_header_offset)
        struct.pack_into("<I", out, 32, new_section_header_offset)
    struct.pack_into("<H", out, elf.program_header_count_at, elf.program_header_count + 1)
    struct.pack_into("<H", out, elf.section_count_at, elf.section_count + 1)

    return bytes(out)


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

    elf = Elf(data)

    # The physical entry point: the lowest LOAD segment's address plus
    # the entry point's offset within it.
    # The segment that contains the entry point. The note's first word
    # is the entry point's offset WITHIN THE FILE, so it is that
    # segment's file offset plus the entry point's offset inside it.
    # Using the FIRST segment's offset is wrong whenever the entry
    # point lives in a later one -- which is the normal case for a
    # link that puts the code first.
    entry_segment = None
    first_load = None
    bss_addr = 0
    for segment_type, file_offset, vaddr, file_size in elf.program_headers():
        if segment_type != 1:  # PT_LOAD
            continue
        if first_load is None or vaddr < first_load[2]:
            first_load = (file_offset, file_size, vaddr)
        if vaddr <= elf.entry < vaddr + file_size:
            entry_segment = (file_offset, file_size, vaddr)

    if entry_segment is None:
        print("no loadable segment contains the entry point", file=sys.stderr)
        return 1

    load_offset, load_size, load_vaddr = first_load
    entry_file_offset, entry_size, entry_vaddr = entry_segment

    # The entry point's position in the file.
    entry_offset = entry_file_offset + (elf.entry - entry_vaddr)
    if bss_addr == 0:
        bss_addr = load_vaddr

    # Where the note will land in memory: the load address plus the
    # note's offset within the first segment.
    # The note lands right behind the first segment in memory too.
    first_load_end = 0
    for segment_type, file_offset, vaddr, file_size in elf.program_headers():
        if segment_type != 1:  # PT_LOAD
            continue
        first_load_end = max(first_load_end, file_offset + file_size)
    note_file_offset = (first_load_end + NOTE_ALIGNMENT - 1) & ~(NOTE_ALIGNMENT - 1)
    note_vaddr = load_vaddr + (note_file_offset - load_offset)
    result = add_note(data, entry_offset, elf.entry, bss_addr, note_vaddr)
    target.write_bytes(result)
    print(f"wrote {target} ({len(result)} bytes)")
    print(f"  entry offset: 0x{entry_offset:x}, paddr: 0x{elf.entry:x}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

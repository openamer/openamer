/* The link script for the OpenAmer OS kernel.
 *
 * The kernel is one loadable segment: the boot code reads it from
 * the disk in one go, so the segments cannot have gaps between them.
 * A linker that pads every section to a page boundary would put
 * kilobytes of zeros between the code and the data, and the boot
 * code's single read would not cover them.
 */

/* The entry point is the 32-bit boot stub: the boot code jumps
 * there, and the stub switches the processor into long mode before
 * it jumps into the 64-bit kernel.
 *
 * The 64-bit entry function is reached through a fixed address
 * rather than through a symbol, so the linker cannot see the
 * reference and would collect the whole kernel. Listing it as an
 * undefined symbol makes the linker keep it. */
ENTRY(_start)

SECTIONS
{
    /* The 32-bit boot stub, at the kernel's load address. The boot
     * code jumps straight here, and this is the entry point. */
    . = 0x10000;
    .text32 : {
        KEEP(*(.text32))
    }

    /* The 64-bit kernel code, at a fixed address.
     *
     * The 32-bit stub has to jump to it, and the stub cannot compute
     * the address: the assembler turns a symbol into a memory access
     * rather than an immediate, and a displacement relative to the
     * instruction pointer is filled in before the linker knows the
     * final layout. A fixed address sidesteps the whole problem --
     * the stub knows where the 64-bit code is, because the layout
     * says so.
     *
     * The Rust code lives in `.text`; the `link_section` on the
     * entry function is not what puts it here, so every text
     * section goes into this one.
     */
    . = 0x11000;
    .text64 : {
        KEEP(*(.text64))
        KEEP(*(.text .text.*))
        KEEP(*(.text.startup .text.startup.*))
    }

    .rodata : {
        *(.rodata .rodata.*)
    }

    .data : {
        *(.data .data.*)
    }

    .bss : {
        __bss_start = .;
        *(.bss .bss.*)
        *(COMMON)
        __bss_end = .;
    }

    /DISCARD/ : {
        *(.eh_frame)
        *(.comment)
        *(.note.*)
    }
}

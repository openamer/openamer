//! The OpenAmer OS kernel binary.
//!
//! The bootloader loads this file from the boot partition and jumps
//! into it. It is a freestanding static ELF: no libc, no operating
//! system underneath, no runtime start-up -- the kernel's own entry
//! point is the first thing the CPU executes.
//!
//! The entry has two stages, and that is not an accident:
//!
//!   * `_start` is 32-bit assembly, because a loader that speaks the
//!     Linux boot protocol hands control over in 32-bit protected
//!     mode with paging switched off. It builds the page tables,
//!     switches the processor into long mode, and far-jumps into the
//!     64-bit code.
//!   * `kmain` is the 64-bit kernel proper, ordinary Rust.
//!
//! The two cannot be one function: the compiler emits 64-bit
//! instructions for a 64-bit target, and the processor cannot execute
//! them while it is still in 32-bit mode.

#![no_std]
#![no_main]

extern crate openamer_kernel;

use core::panic::PanicInfo;

use openamer_kernel::boot;
use crate::tables::*;


/// The kernel's page tables.
///
/// The tables are `no_mangle` because the 32-bit stub addresses them
/// directly -- a bare `mov eax, <symbol>`. A Rust reference would
/// have to be cast to an integer at compile time, which the compiler
/// refuses to do for a static's address.
pub mod tables {
    /// One page table: 512 entries of 8 bytes.
    #[repr(C, align(4096))]
    pub struct PageTable {
        /// The entries. The meaning of an entry depends on the table
        /// it is in.
        pub entries: [u64; 512],
    }

    /// The top-level table.
    ///
    /// The kernel builds its own page tables rather than using the
    /// loader's: the loader's mapping is the loader's business, and a
    /// kernel that uses it has no say over where its own memory lives.
    #[unsafe(no_mangle)]
    pub static mut OPENAMER_PML4: PageTable = PageTable { entries: [0; 512] };

    /// The page directory for the low gigabyte.
    #[unsafe(no_mangle)]
    pub static mut OPENAMER_PDP_LOW: PageTable = PageTable { entries: [0; 512] };

    /// The page directory for the next three gigabytes.
    #[unsafe(no_mangle)]
    pub static mut OPENAMER_PDP_HIGH: PageTable = PageTable { entries: [0; 512] };

    /// The page table for the low gigabyte.
    #[unsafe(no_mangle)]
    pub static mut OPENAMER_PT_LOW: PageTable = PageTable { entries: [0; 512] };

    /// The page table for the next three gigabytes.
    #[unsafe(no_mangle)]
    pub static mut OPENAMER_PT_HIGH: PageTable = PageTable { entries: [0; 512] };
}

/// The 32-bit entry point.
///
/// This is assembly rather than Rust because the compiler would emit
/// 64-bit instructions for it. The loader has prepared nothing but a
/// flat 32-bit protected mode, so the kernel does the rest itself.
core::arch::global_asm!(
    // The syntax is Intel, the same dialect Rust's inline assembler
    // uses.
    //
    // The `.code32` directive comes FIRST: the control registers --
    // CR0, CR3, EFER -- cannot be touched in the 64-bit dialect, and
    // the assembler rejects the whole block if the dialect is wrong.
    ".code32",
    // The stub lives in its own section: the link script puts it at
    // the kernel's load address and the 64-bit code further up, and
    // the entry point has to be the stub.
    ".section .text32, \"ax\"",
    ".globl _start",
    "_start:",
    // The kernel stack: 64 KiB below the kernel's load address, which
    // is out of the way of the kernel's own image.
    "mov esp, 0x000EF000",
    // ── the page tables ───────────────────────────────────────────
    // The identity map: entry i of a page table covers 2 MiB, and
    // entry i of the page directory covers 1 GiB.
    //
    // The page table for the low gigabyte: 512 entries of 2 MiB.
    "mov edi, OPENAMER_PT_LOW",
    "mov eax, 0x00000083", // present, writable, huge page
    "xor ecx, ecx",
    "openamer_fill_low:",
    "mov [edi + ecx * 8], eax",
    "add eax, 0x200000", // the next 2 MiB
    "inc ecx",
    "cmp ecx, 512",
    "jl openamer_fill_low",
    // The page table for the next three gigabytes: 1 GiB pages.
    "mov edi, OPENAMER_PT_HIGH",
    "mov eax, 0x00000083",
    "add eax, 0x200000",
    "xor ecx, ecx",
    "openamer_fill_high:",
    "mov [edi + ecx * 8], eax",
    "add eax, 0x40000000", // the next gigabyte
    "inc ecx",
    "cmp ecx, 510",
    "jl openamer_fill_high",
    // The page directories: one entry per gigabyte.
    "mov edi, OPENAMER_PDP_LOW",
    "mov eax, OPENAMER_PT_LOW",
    "or eax, 0x03", // present, writable
    "mov [edi], eax",
    "mov edi, OPENAMER_PDP_HIGH",
    "mov eax, OPENAMER_PT_HIGH",
    "or eax, 0x03",
    "mov [edi], eax",
    // The top-level table: one entry per page directory.
    "mov edi, OPENAMER_PML4",
    "mov eax, OPENAMER_PDP_LOW",
    "or eax, 0x03",
    "mov [edi], eax",
    "mov eax, OPENAMER_PDP_HIGH",
    "or eax, 0x03",
    "mov [edi + 8], eax",
    // Load the top-level table into the processor.
    "mov eax, OPENAMER_PML4",
    "mov cr3, eax",
    // ── into 64-bit mode ──────────────────────────────────────────
    // The long-mode bit and the no-execute bit in EFER.
    "mov ecx, 0xC0000080",
    "rdmsr",
    "or eax, 0x00000100",
    "or eax, 0x00000800",
    "mov edx, 0",
    "wrmsr",
    // Enable paging: that is what activates long mode.
    "mov eax, cr0",
    "or eax, 0x80000000",
    "mov cr0, eax",
    // Into the 64-bit code. The far jump also loads a 64-bit code
    // segment, which the processor needs before it can execute the
    // 64-bit instructions there.
    "mov eax, 0x08",
    // The far jump into 64-bit mode.
    //
    // The jump is a far jump through memory: the offset and the
    // segment selector sit next to each other there, and the
    // processor reads them from that place. A far jump into a
    // 64-bit code segment is what switches the processor into long
    // mode.
    //
    // The offset is a 32-bit one, and the upper half of the
    // instruction pointer is zero -- the kernel is linked below
    // 4 GiB, so the 32-bit offset is the whole address.
    // The address of the 64-bit entry point.
    //
    // The 32-bit dialect cannot express a RIP-relative address, and
    // the assembler does not turn a symbol into an absolute
    // immediate: `mov eax, symbol` encodes a memory access, and
    // `lea` encodes a displacement relative to the instruction
    // pointer -- which the linker fills in before it knows the final
    // layout, so the jump landed two bytes before the 64-bit code.
    //
    // The way out is a label in the assembly itself: the assembler
    // knows the distance between two labels, and it can encode that
    // distance as an immediate. The stub asks for the distance from
    // The address of the 64-bit entry point.
    //
    // The 32-bit dialect cannot express a RIP-relative address, and
    // the assembler does not turn a symbol into an absolute
    // immediate: `mov eax, symbol` encodes a memory access, and
    // `lea` encodes a displacement relative to the instruction
    // pointer -- which the linker fills in before it knows the final
    // layout, so the jump landed two bytes before the 64-bit code.
    //
    // The link script gives the 64-bit code a fixed address, and the
    // stub knows it. That is the whole point of a fixed address: it
    // is a number, and a number can be an immediate.
    "mov dword ptr [esp], 0x11000",
    "mov word ptr [esp + 4], 0x18",
    // jmp far ptr16:32 [esp]
    ".byte 0xFF, 0x24, 0x24",
    // The 64-bit code that follows needs the 64-bit dialect, and its
    // own section: the link script puts it at a fixed address.
    ".code64",
    ".section .text64, \"ax\"",
    // A reference to the kernel's 64-bit entry point, so that the
    // linker keeps the library's code: the jump above goes to a
    // fixed address, and a fixed address is invisible to the
    // linker. This call is never reached -- the jump before it
    // leaves the processor for good -- but the reference is what the
    // linker needs to see.
    ".globl openamer_kernel_entry64",
    "call openamer_kernel_entry64",
);

/// The 64-bit entry point.
///
/// The 32-bit stub above jumps here once the processor is in long
/// mode. Everything from here on is ordinary 64-bit code.
#[no_mangle]
pub extern "C" fn openamer_kernel_entry64() -> ! {
    // The stack the 32-bit stub set up is still in place.
    let stack_top = boot::KERNEL_LOAD_ADDRESS - 0x1000;

    boot::kmain(boot::BootInfo::defaults(), stack_top)
}


/// The panic handler.
///
/// Rust allows exactly one panic handler per program, and the program
/// is this binary -- the library cannot have one.
#[panic_handler]
fn kernel_panic(info: &PanicInfo) -> ! {
    openamer_kernel::panic::panic_with(info)
}

//! The Global Descriptor Table.
//!
//! The x86_64 segmentation model is vestigial: the segments are flat,
//! and the table exists mostly to give the CPU a valid code segment to
//! jump into and a place to put the TSS. The kernel sets it up once,
//! at boot, and never changes it.

use core::arch::asm;

/// The GDT selector of the kernel's code segment.
pub const KERNEL_CODE: u16 = 0x08;

/// The GDT selector of the kernel's data segment.
pub const KERNEL_DATA: u16 = 0x10;

/// A GDT entry.
#[derive(Clone, Copy)]
#[repr(C, packed)]
pub struct GdtEntry {
    limit_low: u16,
    base_low: u16,
    base_middle: u8,
    access: u8,
    limit_high_flags: u8,
    base_high: u8,
}

/// The Task State Segment: where the CPU puts the stack pointer when
/// an interrupt moves the processor from ring 3 to ring 0.
#[derive(Clone, Copy)]
#[repr(C, packed)]
pub struct Tss {
    reserved0: u32,
    rsp0: u64,
    rsp1: u64,
    rsp2: u64,
    reserved1: u64,
    ist: [u64; 7],
    reserved2: u64,
    ss0: u16,
    reserved3: u16,
    iomap_base: u16,
}

/// The GDT itself.
static mut GDT: [GdtEntry; 6] = [GdtEntry {
    limit_low: 0,
    base_low: 0,
    base_middle: 0,
    access: 0,
    limit_high_flags: 0,
    base_high: 0,
}; 6];

/// The TSS.
static mut TSS: Tss = Tss {
    reserved0: 0,
    rsp0: 0,
    rsp1: 0,
    rsp2: 0,
    reserved1: 0,
    ist: [0; 7],
    reserved2: 0,
    ss0: 0,
    reserved3: 0,
    iomap_base: 0,
};

/// The pointer the LGDT instruction takes.
#[derive(Clone, Copy)]
#[repr(C, packed)]
struct GdtPointer {
    limit: u16,
    base: u64,
}

/// Set one GDT entry.
///
/// The flags byte carries the granularity and the table indicator in
/// its high nibble and the limit's high bits in its low one.
fn set_gate(index: usize, base: u64, limit: u32, access: u8, flags: u8) {
    unsafe {
        let entry = &mut *core::ptr::addr_of_mut!(GDT[index]);
        entry.limit_low = (limit & 0xFFFF) as u16;
        entry.base_low = (base & 0xFFFF) as u16;
        entry.base_middle = ((base >> 16) & 0xFF) as u8;
        entry.access = access;
        entry.limit_high_flags = (((limit >> 16) & 0x0F) | ((flags as u32) & 0xF0)) as u8;
        entry.base_high = ((base >> 24) & 0xFF) as u8;
    }
}

/// Set up the GDT and load it into the processor.
pub fn init() {
    unsafe {
        let tss_address = core::ptr::addr_of!(TSS) as u64;

        // The null segment: the CPU faults on a reference to selector
        // zero, which is a safety net rather than a nicety.
        set_gate(0, 0, 0, 0, 0);
        // The kernel's code segment: ring 0, executable, readable.
        //
        // The flags carry three bits:
        //
        //   0x20  the long mode bit: the segment is a 64-bit one
        //   0x40  default operand size: must be CLEAR when L=1
        //   0x80  the granularity: the limit is in pages, not bytes
        //
        // The long mode bit is the one that matters here: without
        // it the code segment is a 32-bit one, and the 64-bit
        // instructions in it raise a fault.
        set_gate(1, 0, 0xFFFFF, 0x9A, 0xA0);
        // The kernel's data segment: ring 0, writable.
        set_gate(2, 0, 0xFFFFF, 0x92, 0xC0);
        // The user code segment: ring 3, executable, readable.
        set_gate(3, 0, 0xFFFFF, 0xFA, 0xA0);
        // The user data segment: ring 3, writable.
        set_gate(4, 0, 0xFFFFF, 0xF2, 0xC0);
        // The TSS.
        set_gate(5, tss_address, core::mem::size_of::<Tss>() as u32 - 1, 0x89, 0x00);

        let pointer = GdtPointer {
            limit: (core::mem::size_of::<[GdtEntry; 6]>() - 1) as u16,
            base: core::ptr::addr_of!(GDT) as u64,
        };

        // The GDT pointer: the limit, and then the base.
        //
        // The limit is sixteen bits, and the base is sixty-four. The
        // instruction takes the pointer's address, and the pointer
        // has to be where the instruction can reach it -- in a
        // register, and not on the stack: the stack is the kernel's,
        // and the loader's stack is not this one any more.
        //
        // The layout is the one the instruction reads:
        //
        //   0x00  the limit, two bytes
        //   0x02  the base, eight bytes
        //
        // The base is written as a 64-bit value, because the
        // instruction reads eight bytes of it.

        asm!(
            "lgdt [{pointer}]",
            pointer = in(reg) &pointer,
            options(preserves_flags),
        );
        load_segments();
    }
}

/// Reload the segment registers and jump to the 64-bit code segment.
///
/// The far jump is what actually switches the processor from the
/// bootloader's flat segment over to the kernel's own table.
///
/// Reload CS with a local far-return target, then the data selectors.
unsafe fn load_segments() {
    // RETFQ pops RIP first, then CS: push CS first and RIP last.
    // Local label 2 is valid in Rust inline assembly (avoid labels 0/1).

    asm!(
        "push 0x08",
        "lea rax, [rip + 2f]",
        "push rax",
        "retfq",
        "2:",
        "mov ax, 0x10",
        "mov ds, ax",
        "mov es, ax",
        "mov ss, ax",
        "mov fs, ax",
        "mov gs, ax",
        out("rax") _,
        options(preserves_flags),
    );
}


/// Set the kernel stack pointer the CPU uses when an interrupt moves
/// the processor to ring 0.
pub fn set_kernel_stack(stack: u64) {
    unsafe {
        let tss = &mut *core::ptr::addr_of_mut!(TSS);
        tss.rsp0 = stack;
        tss.ss0 = KERNEL_DATA;
    }
}

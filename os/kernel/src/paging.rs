//! The kernel's own page tables.
//!
//! The kernel builds its own page tables and loads them into the
//! processor. That is not a detour around the loader's: it is the
//! point. A loader that prepares the page tables decides where the
//! kernel's memory lives; a kernel that builds its own decides that
//! itself -- and the mapping is then a fact of the kernel, not a
//! favour the loader did it.
//!
//! The first table is a 1 GiB identity map with the huge pages the
//! processor has: four entries cover the low 4 GiB, so the kernel, the
//! loader's memory and the hardware's own memory are all reachable at
//! their physical addresses. A kernel that runs at 1 MiB and maps its
//! own memory at the same address needs nothing else to start.

use core::arch::asm;

/// The size of one page table entry.
const ENTRY_SIZE: u64 = 8;

/// The number of entries in a page table.
const ENTRIES: u64 = 512;

/// The page table entries that map the low gigabyte.
const LOW_GIGABYTE_ENTRIES: u64 = 2;

/// The page table entries that map the next three gigabytes.
const HIGH_ENTRIES: u64 = ENTRIES - LOW_GIGABYTE_ENTRIES;

/// The page table flag: the entry is present.
const PRESENT: u64 = 1 << 0;

/// The page table flag: the entry is writable.
const WRITABLE: u64 = 1 << 1;

/// The page table flag: the entry is a huge page.
const HUGE_PAGE: u64 = 1 << 7;

/// The page table flag: the entry is accessible from user mode.
const USER: u64 = 1 << 2;

/// The PML4: the top-level table.
static mut PML4: [u64; ENTRIES as usize] = [0; ENTRIES as usize];

/// The page directory pointers for the first two gigabytes.
static mut PDP_LOW: [u64; ENTRIES as usize] = [0; ENTRIES as usize];

/// The page directory pointers for the next two gigabytes.
static mut PDP_HIGH: [u64; ENTRIES as usize] = [0; ENTRIES as usize];

/// The page tables themselves.
static mut PT_LOW: [u64; ENTRIES as usize] = [0; ENTRIES as usize];
static mut PT_HIGH: [u64; ENTRIES as usize] = [0; ENTRIES as usize];

/// Set up the page tables and load them into the processor.
pub unsafe fn init() {
    // The low gigabyte, in 2 MiB pages.
    for index in 0..LOW_GIGABYTE_ENTRIES {
        // Each entry covers 2 MiB.
        let physical = index * 2 * 1024 * 1024;
        PT_LOW[index as usize] = physical | PRESENT | WRITABLE | HUGE_PAGE;
    }
    // The next three gigabytes, in 1 GiB pages.
    for index in 0..HIGH_ENTRIES {
        let physical = (LOW_GIGABYTE_ENTRIES + index) * 1024 * 1024 * 1024;
        PT_HIGH[index as usize] = physical | PRESENT | WRITABLE | HUGE_PAGE;
    }

    // The page directory pointers: one per gigabyte, each pointing at
    // a page table.
    PDP_LOW[0] = (PT_LOW.as_ptr() as u64) | PRESENT | WRITABLE;
    PDP_HIGH[0] = (PT_HIGH.as_ptr() as u64) | PRESENT | WRITABLE;

    // The PML4: one entry pointing at each page directory.
    PML4[0] = (PDP_LOW.as_ptr() as u64) | PRESENT | WRITABLE;
    PML4[1] = (PDP_HIGH.as_ptr() as u64) | PRESENT | WRITABLE;

    // Load the PML4 into the processor.
    asm!("mov cr3, {pml4}", pml4 = in(reg) PML4.as_ptr() as u64, options(nomem, nostack, preserves_flags));
}

/// The physical address the CR3 register holds.
pub fn current_root() -> u64 {
    let value: u64;
    unsafe {
        asm!("mov {value}, cr3", value = out(reg) value, options(nomem, nostack, preserves_flags));
    }
    value
}

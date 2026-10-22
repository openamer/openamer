//! The OpenAmer OS kernel binary.
//!
//! The bootloader loads this file from the boot partition and jumps
//! into it. It is a freestanding static ELF: no libc, no operating
//! system underneath, no runtime start-up -- the kernel's own entry
//! point is the first thing the CPU executes.
//!
//! The boot loader hands over in 64-bit mode with the page tables
//! already in place: it has read the kernel's configuration from a
//! section of this file, built the page tables, and switched the
//! processor. The kernel's own entry point is therefore ordinary
//! 64-bit Rust, with no assembly stub in front of it.

#![no_std]
#![no_main]

extern crate openamer_kernel;

use bootloader_api::BootInfo;
use core::panic::PanicInfo;

use openamer_kernel::boot;

/// The kernel's entry point.
///
/// The boot loader calls it with the information it gathered: the
/// memory map, the framebuffer, the framebuffer's format.
fn kernel_main(boot_info: &'static mut BootInfo) -> ! {
    // The stack the loader set up: it grows downwards, so its top is
    // the bottom plus the length.
    let stack_top = boot_info.kernel_stack_bottom + boot_info.kernel_stack_len;

    let info = boot::BootInfo::from_loader(boot_info);
    let framebuffer = boot::framebuffer_from_loader(boot_info);

    boot::kmain(info, framebuffer, stack_top)
}

// The entry point registration.
//
// The macro writes the kernel's configuration into a section of the
// ELF file, and the boot loader reads it from there: it is how the
// loader learns the stack size and the memory layout the kernel
// wants. The macro also generates the `_start` symbol, which is
// where the loader jumps to.
bootloader_api::entry_point!(kernel_main);

/// The panic handler.
///
/// Rust allows exactly one panic handler per program, and the program
/// is this binary -- the library cannot have one.
#[panic_handler]
fn kernel_panic(info: &PanicInfo) -> ! {
    openamer_kernel::panic::panic_with(info)
}

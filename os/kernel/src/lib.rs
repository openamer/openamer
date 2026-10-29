//! OpenAmer OS kernel: the hardware layer.
//!
//! Everything here talks to the machine directly: the VGA text buffer,
//! the I/O ports, the interrupt descriptor table. There is no
//! abstraction layer borrowed from a host operating system, because
//! there is no host operating system -- DIR-04 makes the kernel the
//! lowest layer of the machine, and DIR-13 has it work on the CPU's
//! own terms.

#![no_std]
#![no_main]

/// Write a formatted message to the VGA console and the debug console.
///
/// The debug console is what a serial capture (or QEMU's debug port)
/// reads, and it is the only output that survives once the screen is
/// not there any more.
#[macro_export]
macro_rules! klog {
    ($($arg:tt)*) => {{
        $crate::vga::print_fmt(format_args!($($arg)*));
        $crate::ports::debug_write_fmt(format_args!($($arg)*));
    }};
}

/// Write a formatted message to the VGA console only.
#[macro_export]
macro_rules! kprint {
    ($($arg:tt)*) => {{
        $crate::vga::print_fmt(format_args!($($arg)*));
    }};
}

pub mod boot;
pub mod cpu;
pub mod gdt;
pub mod interrupts;
pub mod memory;
pub mod panic;
pub mod ports;
pub mod scheduler;
pub mod vga;

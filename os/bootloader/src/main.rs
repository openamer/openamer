//! The OpenAmer OS boot sector.
//!
//! The first 512 bytes of the boot device. The BIOS loads it, it
//! switches the processor from 16-bit real mode into 32-bit protected
//! mode, and it goes looking for the kernel.
//!
//! The boot sector itself is not Rust: it has to fit in 512 bytes and
//! be position-independent, which is the one thing a normal Rust
//! binary is not. It is therefore a small assembly file, assembled by
//! the build script, and everything after it -- the part that actually
//! loads the kernel -- is Rust.

#![no_std]
#![no_main]

use core::panic::PanicInfo;

mod disk;
mod stage2;

#[panic_handler]
fn panic(_: &PanicInfo) -> ! {
    stage2::halt()
}

/// The entry point of the boot sector.
///
/// The BIOS jumps here with the drive number in `dl`.
#[no_mangle]
pub extern "C" fn _start() -> ! {
    stage2::run()
}

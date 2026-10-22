//! The kernel's panic handling.
//!
//! A kernel panic is not a stack trace: there is no debugger to catch
//! it and no process to kill. The machine stops, and the reason is
//! written to every output the kernel has -- the screen, the debug
//! console -- because that is the only record of what happened.

use core::panic::PanicInfo;

use crate::vga::Color;

/// What the kernel does when a Rust panic reaches it.
///
/// The panic handler itself lives in the binary crate: Rust allows
/// exactly one per program, and the program is the binary.
///
/// The message is written through the console's own formatter rather
/// than through `format!`: the kernel has no allocator, and
/// `format!` needs one.
pub fn panic_with(info: &PanicInfo) -> ! {
    crate::vga::Console::set_color(Color::LightRed);
    crate::kprint!("\nKERNEL PANIC: ");
    crate::vga::Console::set_color(Color::White);
    crate::vga::print_fmt(format_args!("{}", info));
    crate::kprint!("\n");
    halt();
}

/// A kernel panic with a message.
///
/// Used where the panic mechanism cannot be: a CPU exception, for
/// instance, where the fault is not a Rust panic at all.
pub fn panic(message: &str) -> ! {
    report(message);
}

/// Write the reason and stop the machine.
fn report(message: &str) -> ! {
    crate::vga::Console::set_color(Color::LightRed);
    crate::kprint!("\nKERNEL PANIC: ");
    crate::vga::Console::set_color(Color::White);
    crate::kprint!("{}", message);
    crate::kprint!("\n");
    halt();
}

/// Stop the machine.
fn halt() -> ! {
    // The machine stops. There is no way to continue safely once an
    // invariant is broken, and a kernel that limps on after a broken
    // invariant corrupts the machine silently.
    loop {
        unsafe { core::arch::asm!("cli; hlt", options(nomem, nostack, preserves_flags)) };
    }
}

//! Port I/O: the way the kernel talks to hardware.
//!
//! One instruction, one port, no layer in between. The legacy device
//! buses -- the PIC, the VGA controller, a disk controller -- are all
//! reached this way.
//!
//! DIR-13: operate directly on CPU patterns. This is the pattern.

use core::fmt::{self, Write};

/// The Bochs/QEMU debug console port. A byte written here appears on
/// the emulated serial line, and nothing else uses the port. It is how
/// the kernel says something before the display is up, and how a test
/// harness reads the kernel's output.
pub const DEBUG: u16 = 0xE9;

/// Write a byte to an I/O port.
///
/// # Safety
/// Writing to an I/O port has side effects on the device behind it.
/// The caller must know which device the port belongs to.
pub unsafe fn outb(port: u16, value: u8) {
    // The port number goes in DX and the byte in AL: the I/O
    // instructions have no other form.
    core::arch::asm!(
        "out dx, al",
        in("dx") port,
        in("al") value,
        options(nomem, nostack, preserves_flags)
    );
}

/// Write a word to an I/O port.
///
/// # Safety
/// See [`outb`].
pub unsafe fn outw(port: u16, value: u16) {
    core::arch::asm!(
        "out dx, ax",
        in("dx") port,
        in("ax") value,
        options(nomem, nostack, preserves_flags)
    );
}

/// Write a double word to an I/O port.
///
/// # Safety
/// See [`outb`].
pub unsafe fn outl(port: u16, value: u32) {
    core::arch::asm!(
        "out dx, ax",
        in("dx") port,
        in("ax") value,
        options(nomem, nostack, preserves_flags)
    );
}

/// Read a byte from an I/O port.
///
/// # Safety
/// Reading an I/O port has side effects on the device behind it.
pub unsafe fn inb(port: u16) -> u8 {
    let mut value: u8;
    core::arch::asm!(
        "in al, dx",
        out("al") value,
        in("dx") port,
        options(nomem, nostack, preserves_flags)
    );
    value
}

/// Read a word from an I/O port.
///
/// # Safety
/// See [`inb`].
pub unsafe fn inw(port: u16) -> u16 {
    let mut value: u16;
    core::arch::asm!(
        "in ax, dx",
        out("ax") value,
        in("dx") port,
        options(nomem, nostack, preserves_flags)
    );
    value
}

/// Read a double word from an I/O port.
///
/// # Safety
/// See [`inb`].
pub unsafe fn inl(port: u16) -> u32 {
    let mut value: u32;
    core::arch::asm!(
        "in ax, dx",
        out("ax") value,
        in("dx") port,
        options(nomem, nostack, preserves_flags)
    );
    value
}

/// Wait for an I/O operation to complete.
///
/// The legacy buses need a short delay between an output and the next
/// access. The canonical way to burn it is a write to the unused debug
/// port: it exists precisely to be slow.
///
/// # Safety
/// Performs a port write.
pub unsafe fn io_wait() {
    outb(DEBUG, 0);
}

/// The debug console: a writer that sends every byte to the debug
/// port, where a serial capture can pick it up.
pub struct DebugWriter;

impl Write for DebugWriter {
    fn write_str(&mut self, s: &str) -> fmt::Result {
        for byte in s.bytes() {
            unsafe { outb(DEBUG, byte) };
        }
        Ok(())
    }
}

/// Write formatted output to the debug console.
pub fn debug_write_fmt(args: fmt::Arguments) {
    let mut writer = DebugWriter;
    let _ = writer.write_fmt(args);
}

/// Write a string to the debug console.
pub fn debug_write(text: &str) {
    unsafe { core::arch::asm!("out dx, al", in("dx") DEBUG, in("al") b'\n', options(nomem, nostack, preserves_flags)) };
    debug_write_fmt(format_args!("{}", text));
}

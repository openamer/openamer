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

/// The first serial port, Com1.
///
/// The serial port is the console that survives everything: it needs
/// no screen, no framebuffer and no memory mapped device, and it is
/// what a machine without a display is talked to through.
pub const SERIAL: u16 = 0x3F8;

/// The serial port's data register: the byte goes out here.
const SERIAL_DATA: u16 = SERIAL;
/// The serial port's interrupt enable register.
const SERIAL_INTERRUPT_ENABLE: u16 = SERIAL + 1;
/// The serial port's divisor low byte: the baud rate.
const SERIAL_DIVISOR_LOW: u16 = SERIAL;
/// The serial port's divisor high byte.
const SERIAL_DIVISOR_HIGH: u16 = SERIAL + 1;
/// The serial port's line control register.
const SERIAL_LINE_CONTROL: u16 = SERIAL + 3;
/// The serial port's modem control register.
const SERIAL_MODEM_CONTROL: u16 = SERIAL + 4;
/// The serial port's line status register: the transmit buffer is
/// empty when bit 5 is set.
const SERIAL_LINE_STATUS: u16 = SERIAL + 5;

/// Set the serial port up: 115200 baud, eight data bits, no parity,
/// one stop bit, and the interrupts off.
///
/// # Safety
/// Must be called before the serial port is used.
pub unsafe fn serial_init() {
    unsafe {
        // The interrupts off: the kernel drives the port by polling
        // it, and a serial interrupt would need an interrupt
        // handler that the kernel does not have yet.
        outb(SERIAL_INTERRUPT_ENABLE, 0x00);
        // The divisor: 115200 baud from a 1.8432 MHz clock is a
        // divisor of one.
        outb(SERIAL_DIVISOR_LOW, 0x01);
        outb(SERIAL_DIVISOR_HIGH, 0x00);
        // Eight data bits, no parity, one stop bit.
        outb(SERIAL_LINE_CONTROL, 0x03);
        // The modem control: the port's output is enabled.
        outb(SERIAL_MODEM_CONTROL, 0x0B);
    }
}

/// Write a byte to the serial port.
///
/// The port has a one-byte transmit buffer, and the next byte may
/// only be handed over once that one is gone. The line status says
/// so: bit 5 is set when the buffer is empty.
pub fn serial_write(byte: u8) {
    unsafe {
        while inb(SERIAL_LINE_STATUS) & 0x20 == 0 {
            core::hint::spin_loop();
        }
        outb(SERIAL_DATA, byte);
    }
}

/// Write formatted output to the serial port.
pub fn serial_write_fmt(args: fmt::Arguments) {
    use core::fmt::Write;

    struct SerialWriter;

    impl Write for SerialWriter {
        fn write_str(&mut self, text: &str) -> fmt::Result {
            for byte in text.bytes() {
                serial_write(byte);

                // The port's buffer is one byte, and a line break
                // has to get through before the next byte does.
                if byte == 0x0A {
                    unsafe {
                        while inb(SERIAL_LINE_STATUS) & 0x20 == 0 {
                            core::hint::spin_loop();
                        }
                    }
                }
            }
            Ok(())
        }
    }

    let mut writer = SerialWriter;
    let _ = writer.write_fmt(args);
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

//! The VGA text-mode console.
//!
//! The character cells live at physical address 0xB8000: a fixed
//! address the CPU writes to with ordinary stores. The cursor is moved
//! by writing the CRTC's index registers through the I/O ports.
//!
//! DIR-13: the kernel knows where the character cells are and how the
//! cursor register works, because the kernel owns the machine.

use core::fmt::{self, Write};

/// The physical address of the VGA text buffer.
pub const TEXT_BUFFER: usize = 0xB8000;

/// Characters per line.
pub const WIDTH: usize = 80;

/// Lines on the screen.
pub const HEIGHT: usize = 25;

/// The colour of a character.
#[derive(Clone, Copy, PartialEq, Eq)]
pub enum Color {
    Black = 0,
    Blue = 1,
    Green = 2,
    Cyan = 3,
    Red = 4,
    Magenta = 5,
    Brown = 6,
    LightGrey = 7,
    DarkGrey = 8,
    LightBlue = 9,
    LightGreen = 10,
    LightCyan = 11,
    LightRed = 12,
    LightMagenta = 13,
    Yellow = 14,
    White = 15,
}

/// A cursor position on the screen.
#[derive(Clone, Copy)]
pub struct Writer {
    column: usize,
    row: usize,
    color: Color,
}

impl Writer {
    /// A writer at the top left.
    pub const fn new() -> Self {
        Writer { column: 0, row: 0, color: Color::LightGrey }
    }

    /// The colour new characters are written in.
    pub fn set_color(&mut self, color: Color) {
        self.color = color;
    }

    /// Move the cursor to the top left and clear the screen.
    pub fn clear(&mut self) {
        let blank = self.cell(b' ', Color::Black);
        for index in 0..(WIDTH * HEIGHT) {
            unsafe { self.buffer_write(index, blank) }
        }
        self.column = 0;
        self.row = 0;
        self.set_cursor();
    }

    /// A character cell: the character in the low byte, the attribute
    /// in the high one.
    const fn cell(&self, character: u8, color: Color) -> u16 {
        let attribute = ((color as u16) << 4) | ((self.color as u16) & 0x0F);
        ((character as u16) | (attribute << 8)) & 0xFFFF
    }

    /// Write a character cell into the buffer.
    ///
    /// # Safety
    /// The index must be within the text buffer.
    unsafe fn buffer_write(&mut self, index: usize, value: u16) {
        let address = TEXT_BUFFER + index * 2;
        core::ptr::write_volatile(address as *mut u16, value);
    }

    /// The character cell at a position, for the tests.
    pub fn cell_at(&self, row: usize, column: usize) -> u16 {
        if row >= HEIGHT || column >= WIDTH {
            return 0;
        }
        let address = TEXT_BUFFER + (row * WIDTH + column) * 2;
        unsafe { core::ptr::read_volatile(address as *const u16) }
    }

    /// Write one character, advancing the cursor.
    pub fn write_char(&mut self, character: u8) {
        match character {
            b'\n' => {
                self.column = 0;
                self.row += 1;
            }
            b'\r' => self.column = 0,
            b'\t' => self.column = (self.column + 4) & !3,
            _ => {
                let index = self.row * WIDTH + self.column;
                let value = self.cell(character, self.color);
                unsafe { self.buffer_write(index, value) };
                self.column += 1;
            }
        }

        if self.column >= WIDTH {
            self.column = 0;
            self.row += 1;
        }
        if self.row >= HEIGHT {
            self.scroll();
        }
        self.set_cursor();
    }

    /// Scroll the text up by one line.
    fn scroll(&mut self) {
        for index in 1..(WIDTH * HEIGHT) {
            let value = unsafe { core::ptr::read_volatile((TEXT_BUFFER + index * 2) as *const u16) };
            unsafe { self.buffer_write(index - 1, value) };
        }
        let blank = self.cell(b' ', Color::Black);
        for index in (WIDTH * HEIGHT - WIDTH)..(WIDTH * HEIGHT) {
            unsafe { self.buffer_write(index, blank) };
        }
        self.row = HEIGHT - 1;
    }

    /// Move the hardware cursor to the writer's position.
    fn set_cursor(&self) {
        let offset = (self.row * WIDTH + self.column) as u16;

        // The CRTC holds the cursor position in two registers; the
        // index register selects which one.
        unsafe {
            crate::ports::outb(0x3D4, 14);
            crate::ports::outb(0x3D5, (offset >> 8) as u8);
            crate::ports::outb(0x3D4, 15);
            crate::ports::outb(0x3D5, (offset & 0xFF) as u8);
        }
    }
}

impl Write for Writer {
    fn write_str(&mut self, s: &str) -> fmt::Result {
        for byte in s.bytes() {
            self.write_char(byte);
        }
        Ok(())
    }
}

/// The one console writer the kernel uses.
static mut WRITER: Writer = Writer::new();

/// A handle to the console that is safe to use from anywhere.
///
/// The VGA buffer is a single global resource; a `static mut` with
/// exclusive access is the honest way to express that in a kernel that
/// has no threads yet.
pub struct Console;

impl Console {
    /// Write a string to the console.
    pub fn write_str(text: &str) {
        unsafe {
            let writer = &mut *core::ptr::addr_of_mut!(WRITER);
            let _ = writer.write_str(text);
        }
    }

    /// Write formatted output to the console.
    pub fn print_fmt(args: fmt::Arguments) {
        unsafe {
            let writer = &mut *core::ptr::addr_of_mut!(WRITER);
            let _ = writer.write_fmt(args);
        }
    }

    /// Set the colour new characters are written in.
    pub fn set_color(color: Color) {
        unsafe {
            let writer = &mut *core::ptr::addr_of_mut!(WRITER);
            writer.set_color(color);
        }
    }

    /// Clear the screen.
    pub fn clear() {
        unsafe {
            let writer = &mut *core::ptr::addr_of_mut!(WRITER);
            writer.clear();
        }
    }

    /// The character cell at a position, for the tests.
    pub fn cell_at(row: usize, column: usize) -> u16 {
        unsafe {
            let writer = &*core::ptr::addr_of!(WRITER);
            writer.cell_at(row, column)
        }
    }
}

/// Print formatted output to the console.
pub fn print_fmt(args: fmt::Arguments) {
    Console::print_fmt(args);
}

/// Print a string to the console.
pub fn print(text: &str) {
    Console::write_str(text);
}

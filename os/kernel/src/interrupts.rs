//! Interrupts: the IDT, the PIC, and the dispatch path.

use crate::cpu;
use crate::ports;

/// The number of interrupt vectors the IDT has.
pub const IDT_ENTRIES: usize = 256;

/// The number of hardware interrupt lines.
pub const IRQ_COUNT: usize = 16;

/// The master's PIC command port.
pub const PIC1_COMMAND: u16 = 0x20;
/// The master's PIC data port.
pub const PIC1_DATA: u16 = 0x21;
/// The slave's PIC command port.
pub const PIC2_COMMAND: u16 = 0xA0;
/// The slave's PIC data port.
pub const PIC2_DATA: u16 = 0xA1;
/// The cascade line the slave hangs off.
pub const PIC_CASCADE: u8 = 0x04;

/// An IDT entry.
#[derive(Clone, Copy)]
#[repr(C, packed)]
pub struct IdtEntry {
    offset_low: u16,
    selector: u16,
    zero: u8,
    flags: u8,
    offset_high: u16,
}

/// The register set the interrupt stubs save.
#[derive(Clone, Copy)]
#[repr(C)]
pub struct InterruptFrame {
    pub vector: u64,
    pub error_code: u64,
    pub rip: u64,
    pub cs: u64,
    pub rflags: u64,
    pub rsp: u64,
    pub ss: u64,
}

/// A handler for a hardware interrupt.
pub type IrqHandler = extern "C" fn(frame: &mut InterruptFrame);

/// The IDT.
static mut IDT: [IdtEntry; IDT_ENTRIES] = [IdtEntry {
    offset_low: 0,
    selector: 0,
    zero: 0,
    flags: 0,
    offset_high: 0,
}; IDT_ENTRIES];

/// The pointer the LIDT instruction takes.
#[derive(Clone, Copy)]
#[repr(C, packed)]
struct IdtPointer {
    limit: u16,
    base: u64,
}

/// The registered handlers.
static mut HANDLERS: [Option<IrqHandler>; IRQ_COUNT] = [None; IRQ_COUNT];

/// How many interrupts are unmasked.
static mut ENABLED_COUNT: u64 = 0;

/// How many interrupts were handled.
static mut HANDLED_COUNT: u64 = 0;

/// Set one IDT entry.
fn set_gate(vector: usize, handler: u64, flags: u8) {
    unsafe {
        let entry = &mut *core::ptr::addr_of_mut!(IDT[vector]);
        entry.offset_low = (handler & 0xFFFF) as u16;
        entry.selector = crate::gdt::KERNEL_CODE;
        entry.zero = 0;
        entry.flags = flags;
        entry.offset_high = ((handler >> 16) & 0xFFFF) as u16;
    }
}

/// The common dispatch path.
///
/// The hardware IRQs are remapped to 0x20..0x2F, so a vector at or
/// above 32 is a device interrupt and a vector below it is a CPU
/// exception.
pub extern "C" fn dispatch(frame: &mut InterruptFrame) {
    if frame.vector >= 32 {
        let irq = (frame.vector - 32) as usize;

        unsafe {
            HANDLED_COUNT += 1;

            // Acknowledge the PIC before the handler runs: a handler
            // that takes long would otherwise see the interrupt
            // re-asserted.
            if irq < 8 {
                ports::outb(PIC1_COMMAND, 0x20);
            } else {
                ports::outb(PIC2_COMMAND, 0x20);
            }

            if let Some(handler) = HANDLERS[irq] {
                handler(frame);
            }
        }
        return;
    }

    // A CPU exception. The vector number is the CPU's own fault code.
    let message = match frame.vector {
        0 => "divide error",
        6 => "invalid opcode",
        8 => "double fault",
        13 => "general protection fault",
        14 => "page fault",
        _ => "unhandled CPU exception",
    };
    crate::panic::panic(message);
}

/// The interrupt stubs.
///
/// One stub per vector: the CPU pushes a different frame layout for
/// the error-code vectors than for the others, and the stub has to
/// normalise that before it can call the common path. The stub is
/// written in assembly because the compiler cannot express "push the
/// frame the CPU built" in Rust.
macro_rules! irq_stub {
    ($name:ident, $vector:expr) => {
        extern "C" fn $name(frame: &mut InterruptFrame) {
            frame.vector = $vector;
            dispatch(frame);
        }
    };
}

irq_stub!(isr0, 0);
irq_stub!(isr1, 1);
irq_stub!(isr2, 2);
irq_stub!(isr3, 3);
irq_stub!(isr4, 4);
irq_stub!(isr5, 5);
irq_stub!(isr6, 6);
irq_stub!(isr7, 7);
irq_stub!(isr8, 8);
irq_stub!(isr9, 9);
irq_stub!(isr10, 10);
irq_stub!(isr11, 11);
irq_stub!(isr12, 12);
irq_stub!(isr13, 13);
irq_stub!(isr14, 14);
irq_stub!(isr15, 15);
irq_stub!(isr16, 16);
irq_stub!(isr17, 17);
irq_stub!(isr18, 18);
irq_stub!(isr19, 19);
irq_stub!(isr20, 20);
irq_stub!(isr21, 21);
irq_stub!(isr22, 22);
irq_stub!(isr23, 23);
irq_stub!(isr24, 24);
irq_stub!(isr25, 25);
irq_stub!(isr26, 26);
irq_stub!(isr27, 27);
irq_stub!(isr28, 28);
irq_stub!(isr29, 29);
irq_stub!(isr30, 30);
irq_stub!(isr31, 31);

/// Set up the IDT and load it into the processor.
pub fn init() {
    unsafe {
        for vector in 0..32 {
            let handler: extern "C" fn(&mut InterruptFrame) = match vector {
                0 => isr0,
                1 => isr1,
                2 => isr2,
                3 => isr3,
                4 => isr4,
                5 => isr5,
                6 => isr6,
                7 => isr7,
                8 => isr8,
                9 => isr9,
                10 => isr10,
                11 => isr11,
                12 => isr12,
                13 => isr13,
                14 => isr14,
                15 => isr15,
                16 => isr16,
                17 => isr17,
                18 => isr18,
                19 => isr19,
                20 => isr20,
                21 => isr21,
                22 => isr22,
                23 => isr23,
                24 => isr24,
                25 => isr25,
                26 => isr26,
                27 => isr27,
                28 => isr28,
                29 => isr29,
                30 => isr30,
                _ => isr31,
            };
            set_gate(vector, handler as u64, 0x8E);
        }

        let pointer = IdtPointer {
            limit: (core::mem::size_of::<[IdtEntry; IDT_ENTRIES]>() - 1) as u16,
            base: core::ptr::addr_of!(IDT) as u64,
        };
        core::arch::asm!("lidt [{}]", in(reg) &pointer, options(nostack, preserves_flags));
    }

    remap_pic();
}

/// Move the PIC's interrupts out of the CPU exception range.
///
/// The default mapping puts the master's interrupts at 0x08..0x0F and
/// the slave's at 0x70..0x77, which collides with the CPU's
/// exception vectors. Moving them to 0x20..0x2F is what makes the
/// split between "CPU fault" and "device interrupt" possible at all.
fn remap_pic() {
    unsafe {
        // The master.
        ports::outb(PIC1_COMMAND, 0x11);
        ports::io_wait();
        ports::outb(PIC1_DATA, 0x20);
        ports::io_wait();
        ports::outb(PIC1_DATA, PIC_CASCADE);
        ports::io_wait();
        ports::outb(PIC1_DATA, 0x01);
        ports::io_wait();

        // The slave.
        ports::outb(PIC2_COMMAND, 0x11);
        ports::io_wait();
        ports::outb(PIC2_DATA, 0x28);
        ports::io_wait();
        ports::outb(PIC2_DATA, 0x02);
        ports::io_wait();
        ports::outb(PIC2_DATA, 0x01);
        ports::io_wait();

        // Everything masked until a driver says otherwise.
        mask_all();
    }
}

/// Register a handler for a hardware interrupt.
pub fn register(irq: usize, handler: IrqHandler) {
    if irq < IRQ_COUNT {
        unsafe {
            HANDLERS[irq] = Some(handler);
        }
    }
}

/// Unmask a hardware interrupt.
pub fn enable(irq: usize) {
    if irq >= IRQ_COUNT {
        return;
    }
    unsafe {
        if irq < 8 {
            let mask = ports::inb(PIC1_DATA);
            ports::outb(PIC1_DATA, mask & !(1 << irq));
        } else {
            let mask = ports::inb(PIC2_DATA);
            ports::outb(PIC2_DATA, mask & !(1 << (irq - 8)));
        }
        ENABLED_COUNT += 1;
    }
}

/// Mask a hardware interrupt.
pub fn disable(irq: usize) {
    if irq >= IRQ_COUNT {
        return;
    }
    unsafe {
        if irq < 8 {
            let mask = ports::inb(PIC1_DATA);
            ports::outb(PIC1_DATA, mask | (1 << irq));
        } else {
            let mask = ports::inb(PIC2_DATA);
            ports::outb(PIC2_DATA, mask | (1 << (irq - 8)));
        }
        if ENABLED_COUNT > 0 {
            ENABLED_COUNT -= 1;
        }
    }
}

/// Mask every hardware interrupt.
pub fn mask_all() {
    unsafe {
        ports::outb(PIC1_DATA, 0xFF);
        ports::outb(PIC2_DATA, 0xFF);
        ENABLED_COUNT = 0;
    }
}

/// Unmask every hardware interrupt.
pub fn unmask_all() {
    unsafe {
        ports::outb(PIC1_DATA, 0x00);
        ports::outb(PIC2_DATA, 0x00);
        ENABLED_COUNT = IRQ_COUNT as u64;
    }
}

/// How many interrupts are unmasked.
pub fn enabled_count() -> u64 {
    unsafe { ENABLED_COUNT }
}

/// How many interrupts were handled.
pub fn handled_count() -> u64 {
    unsafe { HANDLED_COUNT }
}

/// Enable the interrupts on the processor.
pub fn enable_interrupts() {
    cpu::interrupts_enable();
}

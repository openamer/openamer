/*
 * OpenAmer OS -- interrupt handling and the 8259 PIC.
 *
 * The kernel installs its own interrupt descriptor table, programs the
 * two 8259 Programmable Interrupt Controllers, and dispatches IRQs to
 * registered handlers.
 *
 * DIR-13: operate directly on CPU patterns. There is no "signal" and
 * no "handler registration API" borrowed from a host OS -- the kernel
 * writes the IDT and the PIC masks itself.
 */

#include "kernel.h"

static idt_entry_t idt[IDT_ENTRIES];
static u64 idt_limit = sizeof(idt) - 1;

static irq_handler_t irq_handlers[IRQ_COUNT];
static u8 irq_enabled_mask[IRQ_COUNT];

static u64 irq_enabled = 0;
static u64 irq_handled = 0;

/*
 * The interrupt stubs.
 *
 * One stub per vector: the CPU pushes a different frame layout for
 * error-code vectors than for the others, and the stub has to normalise
 * that before it can call a common path. The stub is written in
 * assembly because the compiler cannot express "push the frame the CPU
 * built" in C.
 *
 * The hosted build has no interrupts to take, so the stubs there are
 * plain functions that call the same dispatch path. The dispatch logic
 * -- the PIC acknowledgement, the handler lookup -- is identical in
 * both builds, which is what the tests exercise.
 */
#if defined(OPENAMER_HOSTED)

/* Hosted build: the stubs are ordinary C functions. */
#define IRQ_STUB_N(name, vector) IRQ_STUB(name)
#define IRQ_STUB(name)                                     \
    void name(void) {                                      \
        interrupt_frame_t frame;                           \
        kernel_memset(&frame, 0, sizeof(frame));                  \
        irq_dispatch(&frame);                              \
    }

#else

/* Freestanding build: the stubs are assembly. */
#define IRQ_STUB_N(name, vector) IRQ_STUB(name, vector)
#define IRQ_STUB(name, vector)                                       \
    void name(void);                                                 \
    void name(void) {                                                \
        __asm__ volatile (                                           \
            "pushq $0\n\t"          /* placeholder for the error code */ \
            "pushq %rax\n\t"                                            \
            "movq  %rsp, %rdi\n\t"   /* frame pointer */               \
            "call  irq_dispatch\n\t"                                   \
            "addq  $16, %rsp\n\t"                                     \
            "iretq\n\t"                                                \
        );                                                            \
    }

#endif

IRQ_STUB_N(isr0, 0)
IRQ_STUB_N(isr1, 1)
IRQ_STUB_N(isr2, 2)
IRQ_STUB_N(isr3, 3)
IRQ_STUB_N(isr4, 4)
IRQ_STUB_N(isr5, 5)
IRQ_STUB_N(isr6, 6)
IRQ_STUB_N(isr7, 7)
IRQ_STUB_N(isr8, 8)
IRQ_STUB_N(isr9, 9)
IRQ_STUB_N(isr10, 10)
IRQ_STUB_N(isr11, 11)
IRQ_STUB_N(isr12, 12)
IRQ_STUB_N(isr13, 13)
IRQ_STUB_N(isr14, 14)
IRQ_STUB_N(isr15, 15)
IRQ_STUB_N(isr16, 16)
IRQ_STUB_N(isr17, 17)
IRQ_STUB_N(isr18, 18)
IRQ_STUB_N(isr19, 19)
IRQ_STUB_N(isr20, 20)
IRQ_STUB_N(isr21, 21)
IRQ_STUB_N(isr22, 22)
IRQ_STUB_N(isr23, 23)
IRQ_STUB_N(isr24, 24)
IRQ_STUB_N(isr25, 25)
IRQ_STUB_N(isr26, 26)
IRQ_STUB_N(isr27, 27)
IRQ_STUB_N(isr28, 28)
IRQ_STUB_N(isr29, 29)
IRQ_STUB_N(isr30, 30)
IRQ_STUB_N(isr31, 31)

static void *isr_table[32] = {
    (void *)isr0,  (void *)isr1,  (void *)isr2,  (void *)isr3,
    (void *)isr4,  (void *)isr5,  (void *)isr6,  (void *)isr7,
    (void *)isr8,  (void *)isr9,  (void *)isr10, (void *)isr11,
    (void *)isr12, (void *)isr13, (void *)isr14, (void *)isr15,
    (void *)isr16, (void *)isr17, (void *)isr18, (void *)isr19,
    (void *)isr20, (void *)isr21, (void *)isr22, (void *)isr23,
    (void *)isr24, (void *)isr25, (void *)isr26, (void *)isr27,
    (void *)isr28, (void *)isr29, (void *)isr30, (void *)isr31,
};

/*
 * The common dispatch path.
 *
 * The IRQs are remapped so that the hardware vectors 0x20..0x2F do not
 * collide with the CPU exception vectors 0x00..0x1F.
 */
void irq_dispatch(interrupt_frame_t *frame) {
    u64 vector = frame->vector;

    if (vector >= 32) {
        u8 irq = (u8)(vector - 32);
        irq_handled++;

        /* Acknowledge the PIC before the handler runs: a handler that
         * takes long would otherwise see the interrupt re-asserted. */
        if (irq < 8) {
            port_out_b(PORT_PIC_COMMAND, 0x20);
        } else {
            port_out_b(PORT_PIC2_COMMAND, 0x20);
        }

        if (irq < IRQ_COUNT && irq_handlers[irq]) {
            irq_handlers[irq](frame);
        }
        return;
    }

    /* An exception: the vector number is the CPU's own fault code. */
    switch (vector) {
        case 0:  kernel_panic("divide error"); break;
        case 6:  kernel_panic("invalid opcode"); break;
        case 8:  kernel_panic("double fault"); break;
        case 13: kernel_panic("general protection fault"); break;
        case 14: kernel_panic("page fault"); break;
        default: kernel_panic("unhandled CPU exception"); break;
    }
}

void idt_set_gate(u8 vector, u64 handler, u8 flags) {
    idt[vector].offset_low  = (u16)(handler & 0xFFFF);
    idt[vector].selector    = GDT_KERNEL_CODE;
    idt[vector].zero        = 0;
    idt[vector].flags       = flags;
    idt[vector].offset_high = (u16)((handler >> 16) & 0xFFFF);
}

void idt_init(void) {
    for (int i = 0; i < 32; i++) {
        idt_set_gate((u8)i, (u64)isr_table[i], 0x8E);
    }
    /* The hardware IRQs live at 0x20..0x2F after the PIC remap. */
    for (int i = 0; i < (int)IRQ_COUNT; i++) {
        idt_set_gate((u8)(32 + i), (u64)isr_table[32 + i % 16], 0x8E);
    }

#if !defined(OPENAMER_HOSTED)
    __asm__ volatile ("lidt %0" : : "m"(idt_limit) : "memory");
#else
    /* Hosted build: the table is prepared but not loaded -- there is no
     * privileged instruction available to load it. The entries are
     * asserted by the tests instead. */
    (void)idt_limit;
#endif
}

/*
 * Remap the two PICs.
 *
 * The default mapping puts the master's interrupts at 0x08..0x0F and
 * the slave's at 0x70..0x77, which collides with the CPU's exception
 * vectors. Moving them to 0x20..0x2F is what makes the split between
 * "CPU fault" and "device interrupt" possible at all.
 */
void pic_remap(int master_offset, int slave_offset) {
    port_out_b(PORT_PIC_COMMAND, 0x11); /* ICW1: init, expect ICW4 */
    io_wait();
    port_out_b(PORT_PIC_DATA, (u8)master_offset);
    io_wait();
    port_out_b(PORT_PIC_DATA, 0x04); /* ICW2: slave is on IRQ2 */
    io_wait();
    port_out_b(PORT_PIC_DATA, 0x02); /* ICW3: 8086 mode */
    io_wait();

    port_out_b(PORT_PIC2_COMMAND, 0x11);
    io_wait();
    port_out_b(PORT_PIC2_DATA, (u8)slave_offset);
    io_wait();
    port_out_b(PORT_PIC2_DATA, 0x02);
    io_wait();
    port_out_b(PORT_PIC2_DATA, 0x02);
    io_wait();

    /* Everything masked until a driver says otherwise. */
    irq_mask_all();
}

void irq_register(u8 irq, irq_handler_t handler) {
    if (irq < IRQ_COUNT) {
        irq_handlers[irq] = handler;
    }
}

void irq_enable(u8 irq) {
    if (irq >= IRQ_COUNT) {
        return;
    }
    irq_enabled_mask[irq] = 1;
    if (irq < 8) {
        port_out_b(PORT_PIC_DATA, (u8)(port_in_b(PORT_PIC_DATA) & ~(1u << irq)));
    } else {
        port_out_b(PORT_PIC2_DATA, (u8)(port_in_b(PORT_PIC2_DATA) & ~(1u << (irq - 8))));
    }
    irq_enabled++;
}

void irq_disable(u8 irq) {
    if (irq >= IRQ_COUNT) {
        return;
    }
    irq_enabled_mask[irq] = 0;
    if (irq < 8) {
        port_out_b(PORT_PIC_DATA, (u8)(port_in_b(PORT_PIC_DATA) | (1u << irq)));
    } else {
        port_out_b(PORT_PIC2_DATA, (u8)(port_in_b(PORT_PIC2_DATA) | (1u << (irq - 8))));
    }
    if (irq_enabled) {
        irq_enabled--;
    }
}

void irq_mask_all(void) {
    port_out_b(PORT_PIC_DATA, 0xFF);
    port_out_b(PORT_PIC2_DATA, 0xFF);
    for (int i = 0; i < (int)IRQ_COUNT; i++) {
        irq_enabled_mask[i] = 0;
    }
    irq_enabled = 0;
}

void irq_unmask_all(void) {
    port_out_b(PORT_PIC_DATA, 0x00);
    port_out_b(PORT_PIC2_DATA, 0x00);
    for (int i = 0; i < (int)IRQ_COUNT; i++) {
        irq_enabled_mask[i] = 1;
    }
    irq_enabled = IRQ_COUNT;
}

void interrupts_init(void) {
    pic_remap(0x20, 0x28);
    irq_mask_all();
}

u64 interrupts_enabled_count(void) { return irq_enabled; }
u64 interrupts_handled_count(void) { return irq_handled; }

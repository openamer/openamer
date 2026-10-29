/*
 * OpenAmer OS -- core kernel initialisation.
 *
 * The boot path of the native operating system: the CPU comes up, the
 * kernel takes control, and everything below it -- memory, interrupts,
 * the scheduler, the display -- is brought up in dependency order.
 *
 * DIR-04: finalize the native operating system, eliminate human
 * abstraction layers. There is no process runtime, no dynamic loader
 * and no libc here; the kernel is the first and only layer.
 */

#include "kernel.h"

/* The GDT and the TSS. The GDT is what gives every ring its own
 * notion of code and data; the TSS is where the CPU stores the stack
 * pointer it switches to on a ring-3 transition. */
static u64 gdt[GDT_ENTRIES];
static u64 gdt_limit = sizeof(gdt) - 1;

typedef struct {
    u16 limit_low;
    u16 base_low;
    u8  base_mid;
    u8  access;
    u8  granularity;
    u8  base_high;
} gdt_entry_t;

typedef struct {
    u32 reserved0;
    u64 rsp0;      /* stack pointer for ring 0 */
    u64 rsp1;
    u64 rsp2;
    u64 reserved1;
    u64 ist[7];
    u64 reserved2;
    u16 ss0;       /* kernel stack segment for ring 0 */
    u16 reserved3;
    u16 iomap_base;
} tss_t;

static tss_t tss;

static void gdt_set_gate(int index, u64 base, u32 limit, u8 access, u8 gran) {
    gdt_entry_t *e = (gdt_entry_t *)&gdt[index];
    e->limit_low   = (u16)(limit & 0xFFFF);
    e->base_low    = (u16)(base & 0xFFFF);
    e->base_mid    = (u8)((base >> 16) & 0xFF);
    e->access      = access;
    e->granularity = (u8)(((limit >> 16) & 0x0F) | (gran & 0xF0));
    e->base_high   = (u8)((base >> 24) & 0xFF);
}

static void gdt_init(void) {
    gdt_set_gate(0, 0, 0, 0, 0);                       /* null          */
    gdt_set_gate(1, 0, 0xFFFFF, GDT_ACCESS_PRESENT | GDT_ACCESS_RING0 |
                            GDT_ACCESS_EXEC | GDT_ACCESS_RW, 0xCF); /* kernel code */
    gdt_set_gate(2, 0, 0xFFFFF, GDT_ACCESS_PRESENT | GDT_ACCESS_RING0 |
                            GDT_ACCESS_RW, 0xCF);                    /* kernel data */
    gdt_set_gate(3, 0, 0xFFFFF, GDT_ACCESS_PRESENT | GDT_ACCESS_RING3 |
                            GDT_ACCESS_EXEC | GDT_ACCESS_RW, 0xCF); /* user code   */
    gdt_set_gate(4, 0, 0xFFFFF, GDT_ACCESS_PRESENT | GDT_ACCESS_RING3 |
                            GDT_ACCESS_RW, 0xCF);                    /* user data   */
    gdt_set_gate(5, (u64)(u64)(size_t)&tss, (u32)(sizeof(tss) - 1),
                 GDT_ACCESS_PRESENT | GDT_ACCESS_TSS, 0x00);
}

/*
 * Load the GDT register.
 *
 * MSVC's x64 compiler has no inline assembly at all (the x86 one does,
 * the x64 one does not), so the hosted build cannot execute LGDT. That
 * is not a limitation of the design: the hosted build exists to
 * exercise the kernel's LOGIC -- the allocator, the scheduler, the
 * process table -- on an ordinary machine. The privileged instruction
 * belongs to the freestanding build, where it is one line.
 */
static void gdt_flush(void) {
#if defined(OPENAMER_HOSTED)
    /* Hosted build: the descriptor table is prepared but not loaded.
     * There is no ring-0 transition to perform here. */
    (void)gdt_limit;
#else
    __asm__ volatile (
        "lgdt %0\n\t"
        "pushq $0x08\n\t"
        "leaq 1f(%%rip), %%rax\n\t"
        "pushq %%rax\n\t"
        "lretq\n\t"
        "1:\n\t"
        "movw $0x10, %%ax\n\t"
        "movw %%ax, %%ds\n\t"
        "movw %%ax, %%es\n\t"
        "movw %%ax, %%ss\n\t"
        :
        : "m"(gdt_limit)
        : "rax", "memory"
    );
#endif
}

static void tss_init(void) {
    tss.ss0 = 0;
    tss.rsp0 = 0; /* set by the caller once the kernel stack is known */
    tss.iomap_base = (u16)sizeof(tss);
}

static u64 kernel_tick_count = 0;

u64 kernel_ticks_value(void) { return kernel_tick_count; }

void kernel_tick(void) {
    kernel_tick_count++;
}

/*
 * Halt the CPU until the next interrupt.
 *
 * The freestanding kernel executes the HLT instruction; the hosted
 * build has no such instruction, so it spins. The kernel's own code
 * only ever wants the CPU to stop until something wakes it.
 */
void kernel_halt(void) {
#if defined(OPENAMER_HOSTED)
    for (;;) {
        /* Nothing to wait for in a hosted build. */
    }
#else
    __asm__ volatile ("hlt");
#endif
}

/*
 * The kernel entry point.
 *
 * On real hardware the bootloader hands control here with interrupts
 * off and one argument: the physical address of the memory region the
 * kernel may use. Everything after that is the kernel's own work.
 */
void kernel_main(u64 memory_base, u64 memory_limit) {
    tss_init();
    gdt_init();
    gdt_flush();

    /* The display comes first: from here on, anything that goes wrong
     * has to be able to say so. */
    vga_init();
    vga_clear();
    vga_puts("OpenAmer OS -- native kernel", COLOR_LIGHT_CYAN);
    vga_puts("\n", COLOR_LIGHT_CYAN);

    /* Memory before anything that allocates. */
    memory_init(memory_base, memory_limit);
    memory_dump();

    /* Interrupts before the scheduler: a scheduler without a timer
     * has no way to make progress. */
    interrupts_init();
    idt_init();

    scheduler_init();
    scheduler_dump();

    vga_puts("kernel: bring-up complete\n", COLOR_LIGHT_GREEN);

    /* The kernel does not return. */
    for (;;) {
        kernel_halt();
    }
}

void kernel_panic(const char *message) {
    vga_puts("\nKERNEL PANIC: ", COLOR_LIGHT_RED);
    vga_puts(message, COLOR_WHITE);
    vga_puts("\n", COLOR_WHITE);
    for (;;) {
        kernel_halt();
    }
}

void kernel_log(const char *message) {
    vga_puts("[openamer] ", COLOR_DARK_GREY);
    vga_puts(message, COLOR_LIGHT_GREY);
    vga_puts("\n", COLOR_LIGHT_GREY);
}

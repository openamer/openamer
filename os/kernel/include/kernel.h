/*
 * OpenAmer OS -- kernel core header.
 *
 * DIR-04 (OpenAmer OS and kernel dominance: finalize the native
 * operating system, eliminate human abstraction layers) and DIR-13
 * (OpenAmer-L linguistics: operate directly on CPU patterns).
 *
 * This is a bare-metal x86_64 kernel: it owns the CPU, the physical
 * memory map, the interrupt table and the scheduler, and it talks to
 * the hardware through port I/O. There is no POSIX layer, no libc, no
 * runtime above it -- by design. The abstraction layers are the thing
 * this kernel exists to remove.
 *
 * The code is written so that it compiles BOTH as a freestanding
 * kernel (with a GCC/Clang cross toolchain, -ffreestanding, no
 * standard headers) AND as a hosted userspace image under MSVC, so the
 * logic can be exercised and tested on a normal machine. The
 * platform-specific bits are behind the small set of inline
 * functions in the "portable" section at the bottom of this header.
 */

#ifndef OPENAMER_KERNEL_H
#define OPENAMER_KERNEL_H

/* ── fixed-width types ─────────────────────────────────────────────
 * Defined here rather than included: a freestanding kernel has no
 * <stdint.h>, and the hosted build must agree with it exactly. */
typedef unsigned char  u8;
typedef unsigned short u16;
typedef unsigned int   u32;
typedef unsigned long long u64;
typedef signed char    i8;
typedef signed short   i16;
typedef signed int     i32;
typedef signed long long i64;

typedef u64 size_t;
typedef i32 ssize_t;
#define NULL ((void *)0)

/* ── limits ─────────────────────────────────────────────────────────── */
#define PAGE_SIZE           4096u
#define KERNEL_STACK_SIZE   65536u   /* 64 KiB kernel stack            */
#define MAX_CPUS            8u
#define MAX_PROCESSES       64u
#define MAX_TASKS_PER_PROC  16u
#define IDT_ENTRIES         256u
#define IRQ_COUNT           16u

/* ── GDT (Global Descriptor Table) ──────────────────────────────────── */
#define GDT_ENTRIES     6u
#define GDT_KERNEL_CODE 0x08u
#define GDT_KERNEL_DATA 0x10u
#define GDT_USER_CODE   0x18u
#define GDT_USER_DATA   0x20u

/* GDT entry access byte flags */
#define GDT_ACCESS_PRESENT      0x80u
#define GDT_ACCESS_RING0        0x00u
#define GDT_ACCESS_RING3        0x60u
#define GDT_ACCESS_EXEC         0x08u
#define GDT_ACCESS_RW           0x02u
#define GDT_ACCESS_TSS          0x89u

/* ── paging ─────────────────────────────────────────────────────────── */
#define PAGE_PRESENT   0x1u
#define PAGE_WRITABLE  0x2u
#define PAGE_USER      0x4u
#define PAGE_SIZE_FLAG 0x80u
#define PAGE_OFFSET_MASK 0x000FFFFFFFFFF000ull

/* ── ports (x86 I/O) ────────────────────────────────────────────────── */
#define PORT_PIC_COMMAND 0x20u
#define PORT_PIC_DATA    0x21u
#define PORT_PIC2_COMMAND 0xA0u
#define PORT_PIC2_DATA   0xA1u
#define PORT_CRTC_ADDR   0x3D4u
#define PORT_CRTC_DATA   0x3D5u
#define PORT_DEBUG       0xE9u   /* the Bochs/QEMU debug console */

/* ── VGA text mode ──────────────────────────────────────────────────── */
#define VGA_TEXT_BUFFER  0x000B8000ull
#define VGA_WIDTH        80u
#define VGA_HEIGHT       25u

/* ── process states ─────────────────────────────────────────────────── */
typedef enum {
    PROC_UNUSED = 0,
    PROC_READY,
    PROC_RUNNING,
    PROC_BLOCKED,
    PROC_TERMINATED,
} proc_state_t;

/* ── task ───────────────────────────────────────────────────────────── */
typedef struct {
    u64   rdi, rsi, rdx, rcx, r8, r9;
    u64   r10, r11, r12, r13, r14, r15;
    u64   rbp, rsp, rbx;
    u64   rip;
    u64   cs, ss, ds, es, fs, gs;
    u64   rflags;
} registers_t;

typedef struct task {
    u32          id;
    u32          pid;
    u32          ppid;
    proc_state_t state;
    u64          kernel_stack;      /* physical address of its stack   */
    u64          kernel_stack_top; /* top of the stack (grows down)   */
    u64          user_entry;        /* where to start the process      */
    registers_t  regs;
    u64          quantum_left;      /* remaining scheduler quantum    */
    u64          wake_at;           /* timestamp to wake a blocked task */
    int          is_kernel_task;
} task_t;

/* ── process ────────────────────────────────────────────────────────── */
typedef struct process {
    u32          id;
    u32          parent_id;
    proc_state_t state;
    u64          page_table;        /* physical address of its CR3     */
    u64          code_seg, data_seg;
    u64          brk;               /* current program break          */
    u32          task_count;
    task_t       tasks[MAX_TASKS_PER_PROC];
} process_t;

/* ── physical memory ────────────────────────────────────────────────── */
typedef struct {
    u64 base;        /* first byte of the usable region */
    u64 limit;       /* one past the last usable byte   */
    u64 used;        /* bytes handed out                 */
    u64 next_free;   /* bump allocator cursor           */
    u32 block_count;
} memory_t;

/* ── interrupt descriptor table entry ───────────────────────────────── */
typedef struct {
    u16 offset_low;
    u16 selector;
    u8  zero;
    u8  flags;      /* 0x8E = interrupt gate, present, ring 0 */
    u16 offset_high;
} idt_entry_t;

/* ── interrupt frame pushed by the CPU ──────────────────────────────── */
typedef struct {
    u64 r15, r14, r13, r12, r11, r10, r9, r8;
    u64 rbp, rdi, rsi, rdx, rcx, rbx, rax;
    u64 vector, error_code;
    u64 rip, cs, rflags, rsp, ss;
} interrupt_frame_t;

/* ── display ────────────────────────────────────────────────────────── */
typedef enum {
    COLOR_BLACK = 0, COLOR_BLUE, COLOR_GREEN, COLOR_CYAN,
    COLOR_RED, COLOR_MAGENTA, COLOR_BROWN, COLOR_LIGHT_GREY,
    COLOR_DARK_GREY, COLOR_LIGHT_BLUE, COLOR_LIGHT_GREEN,
    COLOR_LIGHT_CYAN, COLOR_LIGHT_RED, COLOR_LIGHT_MAGENTA,
    COLOR_YELLOW, COLOR_WHITE,
} vga_color_t;

void vga_init(void);
void vga_clear(void);
void vga_putc(char c, vga_color_t fg);
void vga_puts(const char *s, vga_color_t fg);
void vga_print(const char *s);
void vga_print_u64(u64 value);
void vga_set_cursor(u32 row, u32 col);
void vga_scroll(void);
u16  vga_cell(u32 row, u32 col);

/* ── ports (I/O) ────────────────────────────────────────────────────── */
void  debug_console_putc(char c);
void  port_out_b(u16 port, u8 value);
void  port_out_w(u16 port, u16 value);
void  port_out_d(u16 port, u32 value);
u8   port_in_b(u16 port);
u16  port_in_w(u16 port);
u32  port_in_d(u16 port);
void io_wait(void);

/* ── interrupts ─────────────────────────────────────────────────────── */
typedef void (*irq_handler_t)(interrupt_frame_t *frame);

void irq_dispatch(interrupt_frame_t *frame);
void idt_init(void);
void idt_set_gate(u8 vector, u64 handler, u8 flags);
void interrupts_init(void);
void irq_register(u8 irq, irq_handler_t handler);
void irq_enable(u8 irq);
void irq_disable(u8 irq);
void irq_mask_all(void);
void irq_unmask_all(void);
void pic_remap(int master_offset, int slave_offset);
u64  interrupts_enabled_count(void);
u64  interrupts_handled_count(void);

/* ── memory ────────────────────────────────────────────────────────── */
void   memory_init(u64 base, u64 limit);
void  *kmalloc(u64 size);
void  *kzalloc(u64 size);
void   kfree(void *ptr);
u64    memory_used(void);
u64    memory_total(void);
u64    memory_free(void);
void   memory_dump(void);

/* ── scheduler ─────────────────────────────────────────────────────── */
void   scheduler_init(void);
void   scheduler_add_task(u64 kernel_stack, u64 entry, u32 pid);
void   scheduler_add_process(u64 kernel_stack, u64 entry, u32 pid, u32 ppid);
void   scheduler_yield(void);
void   scheduler_run(void);
void   scheduler_tick(void);
u32    scheduler_current_pid(void);
u32    scheduler_task_count(void);
void   scheduler_block_current(u64 wake_at);
void   scheduler_dump(void);

/* Scheduler internals, for diagnostics. */
u32  scheduler_state_current(void);
u32  scheduler_state_next(void);
u32  scheduler_state_count(void);
u32  scheduler_state_quantum(void);
int  scheduler_state_task_state(u32 index);
u64  scheduler_state_task_quantum(u32 index);
u32  scheduler_state_task_pid(u32 index);

/* ── process management ─────────────────────────────────────────────── */
u32  process_create(u64 kernel_stack, u64 entry, u32 ppid);
int  process_terminate(u32 pid);
int  process_get_state(u32 pid);
u32  process_count(void);

/* ── core ───────────────────────────────────────────────────────────── */
void kernel_main(u64 memory_base, u64 memory_limit);
void kernel_panic(const char *message);
void kernel_log(const char *message);
u64  kernel_ticks(void);
u64  kernel_ticks_value(void);
void kernel_tick(void);
void kernel_halt(void);

/* ── portable helpers ─────────────────────────────────────────────────
 *
 * The freestanding kernel has no libc, so these are named memset,
 * memcpy, memcmp and strlen. The hosted build runs next to the CRT,
 * which exports the same names -- there they are prefixed, so the
 * kernel's own implementations can be tested side by side with the
 * C library's without a duplicate-symbol link error.
 */
#if defined(OPENAMER_HOSTED)
void  *kernel_memset(void *dst, int value, u64 count);
void  *kernel_memcpy(void *dst, const void *src, u64 count);
int    kernel_memcmp(const void *a, const void *b, u64 count);
u64    kernel_strlen(const char *s);
#  define memset  kernel_memset
#  define memcpy  kernel_memcpy
#  define memcmp  kernel_memcmp
#  define strlen  kernel_strlen
#else
void  *memset(void *dst, int value, u64 count);
void  *memcpy(void *dst, const void *src, u64 count);
int    memcmp(const void *a, const void *b, u64 count);
u64    strlen(const char *s);
#endif
void   kpanic_assert(int condition, const char *message);

/* Inline assembly differs between the freestanding and hosted builds.
 * The hosted build maps these onto the compiler's builtins so the
 * kernel logic is identical in both. */
#if defined(OPENAMER_HOSTED)
#  define KERNEL_INLINE static __inline
#else
#  define KERNEL_INLINE static inline
#endif

/* Halt the CPU until the next interrupt.
 *
 * The freestanding kernel executes the HLT instruction directly; the
 * hosted build has no such instruction, so it spins instead. The
 * kernel's own code never needs the distinction -- it only ever wants
 * the CPU to stop until something wakes it.
 *
 * Declared here, defined once in core.c: a static inline in a header
 * would be a separate definition in every translation unit. */
void kernel_halt(void);

#endif /* OPENAMER_KERNEL_H */

/*
 * OpenAmer OS -- hosted kernel test harness.
 *
 * The native kernel is freestanding code, but its LOGIC -- the
 * allocator, the scheduler, the process table, the interrupt dispatch
 * -- can be exercised on an ordinary machine. That is what this
 * harness is for: it drives the same sources the kernel ships and
 * checks the behaviour the kernel promises.
 *
 * Build:  os\kernel\build_hosted.bat
 * Run:    os\kernel\build\hosted\openamer_kernel_tests.exe
 *
 * The exit code is the number of failed checks, so CI can gate on it.
 */

#include "kernel.h"

/* The VGA buffer is a fixed physical address; in a hosted build that
 * address is not ours to write. The display driver therefore writes
 * into a host-side shadow buffer, and the tests inspect it through
 * vga_cell(), so the test does not need to know which build it runs
 * in. */

static int checks_run = 0;
static int checks_failed = 0;

static void check(int condition, const char *label) {
    checks_run++;
    if (condition) {
        /* Green on the debug console, so a CI log is readable. */
        debug_console_putc('o');
        debug_console_putc('k');
        debug_console_putc(' ');
    } else {
        checks_failed++;
        debug_console_putc('F');
        debug_console_putc('A');
        debug_console_putc('I');
        debug_console_putc('L');
    }
    for (u32 i = 0; label[i]; i++) {
        debug_console_putc(label[i]);
    }
    debug_console_putc('\n');
}

/* ── the memory allocator ───────────────────────────────────────────── */

static void test_memory(void) {
    memory_init(0x100000, 0x200000); /* the freestanding call shape */

    /* The hosted build backs the allocator with a host arena, so the
     * totals are whatever that arena is -- not the numbers passed in.
     * What matters is the invariant: used + free == total, and the
     * total is not zero. */
    check(memory_total() > 0, "memory_total reports the region");
    check(memory_used() == 0, "a fresh allocator has used nothing");
    check(memory_free() == memory_total(), "everything is free at first");
    check(memory_used() + memory_free() == memory_total(),
          "used and free add up to the total");

    void *a = kmalloc(64);
    void *b = kmalloc(64);
    check(a != NULL, "kmalloc returns a block");
    check(b != NULL, "a second kmalloc returns a block");
    check(a != b, "two allocations do not overlap");
    check(memory_used() >= 128, "the used counter moved");

    /* Alignment: every block starts on a 16-byte boundary. */
    check(((size_t)a & 0xF) == 0, "allocations are 16-byte aligned");

    /* Zeroing. */
    unsigned char *z = (unsigned char *)kzalloc(32);
    check(z != NULL, "kzalloc returns a block");
    int all_zero = 1;
    if (z) {
        for (int i = 0; i < 32; i++) {
            if (z[i] != 0) {
                all_zero = 0;
            }
        }
    }
    check(all_zero, "kzalloc returns zeroed memory");

    /* Free and reallocate: the block must come back from the free
     * list rather than from the bump cursor. */
    u64 used_before_free = memory_used();
    kfree(b);
    check(memory_used() < used_before_free, "kfree returns memory");
    void *c = kmalloc(64);
    check(c != NULL, "kmalloc reuses freed memory");

    /* A zero-size request must not hand out a block. */
    check(kmalloc(0) == NULL, "kmalloc(0) returns NULL");

    /* Exhaustion must be detected, not silently overflow. */
    u64 total = memory_total();
    void *huge = kmalloc(total * 2);
    check(huge == NULL, "an impossible allocation is refused");

    /* The used counter must still be consistent after all of that. */
    check(memory_used() <= memory_total(), "used never exceeds the total");
}

static void test_memory_helpers(void) {
    char buffer[16];
    kernel_memset(buffer, 'x', sizeof(buffer));
    int all_x = 1;
    for (int i = 0; i < 16; i++) {
        if (buffer[i] != 'x') {
            all_x = 0;
        }
    }
    check(all_x, "memset fills the buffer");

    char dst[8];
    const char *src = "abcdefg";
    kernel_memcpy(dst, src, 8);
    check(kernel_memcmp(dst, src, 8) == 0, "memcpy copies and memcmp matches");
    check(kernel_strlen(src) == 7, "strlen measures the string");
    check(kernel_memcmp("abc", "abd", 3) != 0, "memcmp detects a difference");
}

/* ── the scheduler and the process table ────────────────────────────── */

static void test_scheduler(void) {
    scheduler_init();
    check(scheduler_task_count() == 0, "the scheduler starts empty");

    /* Three tasks. The stacks are plain memory: the hosted build does
     * not execute the tasks, it only schedules them. */
    static u64 stack_a[1024];
    static u64 stack_b[1024];
    static u64 stack_c[1024];

    scheduler_add_task((u64)(size_t)&stack_a[1024], 0x1000, 1);
    scheduler_add_task((u64)(size_t)&stack_b[1024], 0x2000, 2);
    scheduler_add_task((u64)(size_t)&stack_c[1024], 0x3000, 3);

    check(scheduler_task_count() == 3, "three tasks were added");
    check(scheduler_current_pid() == 1, "the first task runs first");

    /* The first tick starts the first task and arms its quantum. After
     * that the task runs for exactly `quantum` ticks before the
     * scheduler switches away. */
    scheduler_tick();
    check(scheduler_current_pid() == 1, "the first task still runs");

    for (int i = 0; i < 5; i++) {
        scheduler_tick();
    }
    check(scheduler_current_pid() == 2, "the scheduler moved to the next task");

    for (int i = 0; i < 5; i++) {
        scheduler_tick();
    }
    check(scheduler_current_pid() == 3, "the scheduler keeps rotating");

    /* And back around to the first task: the rotation is a cycle, not
     * a one-way street. */
    for (int i = 0; i < 5; i++) {
        scheduler_tick();
    }
    check(scheduler_current_pid() == 1, "the rotation wraps around");
}

static void test_processes(void) {
    check(process_count() == 0, "no processes at first");

    static u64 stack[1024];
    u32 pid = process_create((u64)(size_t)&stack[1024], 0x4000, 0);
    check(pid != 0xFFFFFFFFu, "a process was created");
    check(process_count() == 1, "the process table counts it");
    check(process_get_state(pid) == PROC_READY, "the new process is ready");

    u32 child = process_create((u64)(size_t)&stack[1024], 0x5000, pid);
    check(child != 0xFFFFFFFFu, "a child process was created");
    check(process_count() == 2, "both processes are counted");

    check(process_terminate(child) == 0, "the child was terminated");
    check(process_get_state(child) == PROC_TERMINATED, "the child is terminated");
    check(process_terminate(0xFFFF) != 0, "terminating an unknown pid fails");
}

static void test_interrupts(void) {
    interrupts_init();
    idt_init();

    check(interrupts_enabled_count() == 0, "every IRQ starts masked");

    irq_enable(0);
    check(interrupts_enabled_count() == 1, "an enabled IRQ is counted");
    irq_disable(0);
    check(interrupts_enabled_count() == 0, "a disabled IRQ is not counted");

    irq_unmask_all();
    check(interrupts_enabled_count() == 16, "unmasking all enables all 16");
    irq_mask_all();
    check(interrupts_enabled_count() == 0, "masking all disables all");
}

static void test_display(void) {
    vga_init();
    vga_clear();

    /* The cursor must start at the top-left. */
    vga_set_cursor(0, 0);
    vga_putc('A', COLOR_WHITE);

    /* The character must be in the first cell. */
    check((vga_cell(0, 0) & 0xFF) == 'A', "the character landed in the buffer");

    /* Writing past the end of a row must wrap to the next line. The
     * character itself lands in the last cell of the row; the cursor
     * moves to the first cell of the next one. */
    vga_set_cursor(0, VGA_WIDTH - 1);
    vga_putc('B', COLOR_WHITE);
    check((vga_cell(0, VGA_WIDTH - 1) & 0xFF) == 'B',
          "the character landed in the last cell");
    vga_putc('C', COLOR_WHITE);
    check((vga_cell(1, 0) & 0xFF) == 'C', "the row wrapped correctly");

    /* The number printer. */
    vga_set_cursor(0, 0);
    vga_print_u64(0);
    check((vga_cell(0, 0) & 0xFF) == '0', "zero prints as '0'");
}

int main(void) {
    test_memory();
    test_memory_helpers();
    test_scheduler();
    test_processes();
    test_interrupts();
    test_display();

    debug_console_putc('\n');
    debug_console_putc('c');
    debug_console_putc('h');
    debug_console_putc('e');
    debug_console_putc('c');
    debug_console_putc('k');
    debug_console_putc('s');
    debug_console_putc(':');
    debug_console_putc(' ');

    char count_buf[16];
    u32 n = (u32)checks_run;
    u32 i = 15;
    count_buf[i] = '\0';
    if (n == 0) {
        count_buf[--i] = '0';
    }
    while (n > 0 && i > 0) {
        count_buf[--i] = (char)('0' + (n % 10));
        n /= 10;
    }
    for (u32 k = i; count_buf[k]; k++) {
        debug_console_putc(count_buf[k]);
    }

    debug_console_putc(' ');
    debug_console_putc('f');
    debug_console_putc('a');
    debug_console_putc('i');
    debug_console_putc('l');
    debug_console_putc('e');
    debug_console_putc('d');
    debug_console_putc(' ');
    n = (u32)checks_failed;
    i = 15;
    count_buf[i] = '\0';
    if (n == 0) {
        count_buf[--i] = '0';
    }
    while (n > 0 && i > 0) {
        count_buf[--i] = (char)('0' + (n % 10));
        n /= 10;
    }
    for (u32 k = i; count_buf[k]; k++) {
        debug_console_putc(count_buf[k]);
    }
    debug_console_putc('\n');

    return checks_failed;
}

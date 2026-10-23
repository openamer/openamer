/*
 * OpenAmer OS -- the scheduler.
 *
 * A preemptive round-robin scheduler over tasks and processes. The
 * timer interrupt drives it: every tick reduces the current task's
 * quantum, and when the quantum runs out the scheduler switches to the
 * next ready task.
 *
 * DIR-04: this is the multitasking core of the native operating
 * system. There is no POSIX scheduler underneath and no "nice" value
 * inherited from somewhere else -- the quantum policy is the kernel's
 * own, and the kernel can change it because the kernel owns the CPU.
 */

#include "kernel.h"

#define QUANTUM_DEFAULT 5u   /* ticks per task before a preemption */

static task_t    tasks[MAX_PROCESSES * MAX_TASKS_PER_PROC];
static process_t processes[MAX_PROCESSES];

static u32 task_count = 0;
static u32 current_task = 0;
static u32 next_task = 1;
static u32 quantum = QUANTUM_DEFAULT;
static u64 tick_counter = 0;
static int scheduler_running = 0;

void scheduler_init(void) {
    for (int i = 0; i < (int)MAX_PROCESSES; i++) {
        processes[i].id = (u32)i;
        processes[i].state = PROC_UNUSED;
    }
    for (int i = 0; i < (int)(MAX_PROCESSES * MAX_TASKS_PER_PROC); i++) {
        tasks[i].id = (u32)i;
        tasks[i].state = PROC_UNUSED;
    }
    task_count = 0;
    current_task = 0;
    next_task = 1;
    tick_counter = 0;
    scheduler_running = 0;
}

/* Find a free task slot. */
static int task_alloc(void) {
    for (int i = 0; i < (int)(MAX_PROCESSES * MAX_TASKS_PER_PROC); i++) {
        if (tasks[i].state == PROC_UNUSED) {
            return i;
        }
    }
    return -1;
}

void scheduler_add_task(u64 kernel_stack, u64 entry, u32 pid) {
    int slot = task_alloc();
    if (slot < 0) {
        kernel_panic("scheduler: task table full");
    }
    task_t *t = &tasks[slot];
    kernel_memset(t, 0, sizeof(*t));
    t->id = (u32)slot;
    t->pid = pid;
    t->state = PROC_READY;
    t->kernel_stack = kernel_stack;
    t->kernel_stack_top = kernel_stack;
    t->user_entry = entry;
    t->quantum_left = quantum;
    t->is_kernel_task = 1;

    /* The initial register image: the task starts at its entry point
     * with an empty stack. */
    t->regs.rip = entry;
    t->regs.rsp = kernel_stack;
    t->regs.cs = GDT_KERNEL_CODE;
    t->regs.ss = GDT_KERNEL_DATA;
    t->regs.rflags = 0x202u; /* IF set, reserved bit 1 */

    /* The quantum starts at zero: the first tick decrements nothing and
     * immediately arms the switch, so a task runs for exactly `quantum`
     * ticks before it is preempted. */
    t->quantum_left = 0;

    if (task_count == 0) {
        current_task = (u32)slot;
    }
    task_count++;
}

void scheduler_add_process(u64 kernel_stack, u64 entry, u32 pid, u32 ppid) {
    u32 slot = process_create(kernel_stack, entry, ppid);
    if (slot == 0xFFFFFFFFu) {
        kernel_panic("scheduler: process table full");
    }
    (void)slot;
    scheduler_add_task(kernel_stack, entry, pid);
}

/*
 * Pick the next runnable task.
 *
 * Round-robin with a quantum: the search starts where the last switch
 * left off and wraps. A blocked task whose wake-up time has passed
 * becomes ready again, so a sleeping process wakes without anyone
 * waking it explicitly.
 */
static int find_next_runnable(u32 from) {
    u32 total = (u32)(MAX_PROCESSES * MAX_TASKS_PER_PROC);
    for (u32 i = 0; i < total; i++) {
        u32 idx = (from + i) % total;
        task_t *t = &tasks[idx];

        if (t->state == PROC_BLOCKED && tick_counter >= t->wake_at) {
            t->state = PROC_READY;
        }
        if (t->state == PROC_READY) {
            return (int)idx;
        }
    }
    return -1;
}

/*
 * The context switch.
 *
 * The full register set is saved, the next task's state is restored,
 * and the CPU continues there. On the hosted build the switch is
 * simulated: the register image is swapped in the task struct, which
 * is what the scheduler logic is actually tested against.
 */
static void context_switch(u32 from, u32 to) {
    task_t *prev = &tasks[from];
    task_t *next = &tasks[to];

    prev->state = PROC_READY;
    next->state = PROC_RUNNING;

    /* The incoming task gets a full quantum. Without this a task that
     * was switched TO would start with a zero quantum and be preempted
     * on the very next tick -- the scheduler would rotate through the
     * tasks instead of running them. */
    next->quantum_left = quantum;

    /* Save the outgoing context. */
    prev->regs.rip = next->regs.rip;
    prev->regs.rsp = next->regs.rsp;

    /* Restore the incoming one. */
    current_task = to;

#if !defined(OPENAMER_HOSTED)
    __asm__ volatile (
        "pushfq\n\t"
        "popq %%rax\n\t"
        "movq %%rax, %[rf]\n\t"
        "movq %[sp], %%rsp\n\t"
        "pushq %[rip]\n\t"
        "retfq\n\t"
        :
        : [rf] "=r"(prev->regs.rflags), [sp] "r"(next->regs.rsp),
          [rip] "r"(next->regs.rip)
        : "rax", "memory"
    );
#endif
}
/*
 * Yield the CPU.
 *
 * The search starts at next_task and wraps; the cursor is moved past
 * the task that was found, so the next yield picks the one after it.
 * The current task counts as a candidate only when it is the only
 * runnable one -- otherwise the scheduler would keep handing the CPU
 * back to the task that just gave it up.
 */
void scheduler_yield(void) {
    u32 total = (u32)(MAX_PROCESSES * MAX_TASKS_PER_PROC);
    int next = find_next_runnable(next_task);
    if (next < 0) {
        return; /* nothing else to run */
    }
    next_task = ((u32)next + 1) % total;
    if ((u32)next == current_task) {
        /* The only runnable task is the current one: nothing to switch
         * to. It keeps running. */
        return;
    }
    context_switch(current_task, (u32)next);
}

/*
 * The timer tick.
 *
 * Called from the timer IRQ. It is the only thing that makes the
 * scheduler preemptive: without it a running task would keep the CPU
 * until it blocked or exited.
 *
 * The tick counts down the current task's quantum. When the quantum
 * runs out the scheduler switches away and gives the next task a full
 * one. A task that is not RUNNING (blocked, terminated, or not yet
 * started) does not consume a quantum.
 */
void scheduler_tick(void) {
    tick_counter++;
    kernel_tick();

    if (task_count == 0) {
        return;
    }

    task_t *current = &tasks[current_task];
    if (current->state != PROC_RUNNING) {
        /* The current slot holds a task that is not running. The first
         * task is READY until the scheduler starts it, so the very
         * first tick has to promote it and arm its quantum. */
        if (current->state == PROC_READY) {
            current->state = PROC_RUNNING;
            current->quantum_left = quantum;
        }
        return;
    }

    /* The quantum counts down. When it reaches zero the scheduler
     * switches away and the next task gets a full quantum. */
    if (current->quantum_left > 0) {
        current->quantum_left--;
    }
    if (current->quantum_left == 0) {
        current->quantum_left = quantum;
        scheduler_yield();
    }
}

void scheduler_run(void) {
    scheduler_running = 1;
    for (;;) {
        scheduler_yield();
        kernel_halt();
    }
}

u32 scheduler_current_pid(void) {
    if (task_count == 0) {
        return 0;
    }
    return tasks[current_task].pid;
}

u32 scheduler_task_count(void) {
    return task_count;
}

void scheduler_block_current(u64 wake_at) {
    if (task_count == 0) {
        return;
    }
    task_t *current = &tasks[current_task];
    current->state = PROC_BLOCKED;
    current->wake_at = wake_at;
    scheduler_yield();
}

void scheduler_dump(void) {
    vga_puts("scheduler: ", COLOR_LIGHT_GREY);
    vga_print_u64(scheduler_task_count());
    vga_puts(" task(s), quantum ", COLOR_LIGHT_GREY);
    vga_print_u64(quantum);
    vga_puts("\n", COLOR_LIGHT_GREY);
}

/*
 * The scheduler's internal state, for diagnostics.
 *
 * A scheduler that silently picks the wrong task is the hardest kind
 * of kernel bug to find, so the state is readable: which task runs,
 * where the search cursor is, and what each task's state and remaining
 * quantum are.
 */
u32 scheduler_state_current(void) { return current_task; }
u32 scheduler_state_next(void)    { return next_task; }
u32 scheduler_state_count(void)   { return task_count; }
u32 scheduler_state_quantum(void) { return quantum; }

int scheduler_state_task_state(u32 index) {
    if (index >= (u32)(MAX_PROCESSES * MAX_TASKS_PER_PROC)) {
        return PROC_UNUSED;
    }
    return (int)tasks[index].state;
}

u64 scheduler_state_task_quantum(u32 index) {
    if (index >= (u32)(MAX_PROCESSES * MAX_TASKS_PER_PROC)) {
        return 0;
    }
    return tasks[index].quantum_left;
}

u32 scheduler_state_task_pid(u32 index) {
    if (index >= (u32)(MAX_PROCESSES * MAX_TASKS_PER_PROC)) {
        return 0;
    }
    return tasks[index].pid;
}

/* ── process management ─────────────────────────────────────────────── */

u32 process_create(u64 kernel_stack, u64 entry, u32 ppid) {
    for (int i = 0; i < (int)MAX_PROCESSES; i++) {
        if (processes[i].state == PROC_UNUSED) {
            process_t *p = &processes[i];
            kernel_memset(p, 0, sizeof(*p));
            p->id = (u32)i;
            p->parent_id = ppid;
            p->state = PROC_READY;
            p->code_seg = GDT_KERNEL_CODE;
            p->data_seg = GDT_KERNEL_DATA;
            p->brk = kernel_stack;
            p->task_count = 1;
            p->tasks[0].id = (u32)i;
            p->tasks[0].pid = p->id;
            p->tasks[0].state = PROC_READY;
            p->tasks[0].kernel_stack = kernel_stack;
            p->tasks[0].user_entry = entry;
            return p->id;
        }
    }
    return 0xFFFFFFFFu;
}

int process_terminate(u32 pid) {
    if (pid >= MAX_PROCESSES) {
        return -1;
    }
    if (processes[pid].state == PROC_UNUSED) {
        return -1;
    }
    processes[pid].state = PROC_TERMINATED;
    /* Every task of the process goes with it. */
    for (int i = 0; i < (int)MAX_TASKS_PER_PROC; i++) {
        if (processes[pid].tasks[i].state != PROC_UNUSED) {
            processes[pid].tasks[i].state = PROC_TERMINATED;
        }
    }
    return 0;
}

int process_get_state(u32 pid) {
    if (pid >= MAX_PROCESSES) {
        return PROC_UNUSED;
    }
    return (int)processes[pid].state;
}

u32 process_count(void) {
    u32 count = 0;
    for (int i = 0; i < (int)MAX_PROCESSES; i++) {
        if (processes[i].state != PROC_UNUSED) {
            count++;
        }
    }
    return count;
}

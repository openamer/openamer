//! The scheduler.
//!
//! A preemptive round-robin scheduler over tasks. The timer interrupt
//! drives it: every tick reduces the current task's quantum, and when
//! the quantum runs out the scheduler switches to the next ready task.
//!
//! The C reference implementation (os/kernel/src/scheduler.c) proved
//! this design with 45 executed checks. The behaviour reproduced here
//! is the one those checks established:
//!
//!   * the first tick starts the first task and arms its quantum,
//!   * a task runs for exactly `quantum` ticks before it is preempted,
//!   * the task that is switched TO gets a full quantum -- without
//!     that the scheduler would rotate through the tasks instead of
//!     running them,
//!   * the rotation is a cycle: it wraps around.

use crate::cpu;

/// The number of task slots.
pub const MAX_TASKS: usize = 64;

/// How many ticks a task runs before it is preempted.
const QUANTUM: u32 = 5;

/// The state of a task.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum TaskState {
    /// The slot is free.
    Unused,
    /// The task can run.
    Ready,
    /// The task is running.
    Running,
    /// The task is waiting for a wake-up time.
    Blocked,
    /// The task is finished.
    Terminated,
}

/// A task.
#[derive(Clone, Copy)]
pub struct Task {
    pub id: u32,
    pub pid: u32,
    pub state: TaskState,
    pub kernel_stack: u64,
    pub user_entry: u64,
    pub quantum_left: u32,
    pub wake_at: u64,
}

impl Task {
    const fn empty() -> Self {
        Task {
            id: 0,
            pid: 0,
            state: TaskState::Unused,
            kernel_stack: 0,
            user_entry: 0,
            quantum_left: 0,
            wake_at: 0,
        }
    }
}

/// The scheduler's state.
struct SchedulerState {
    tasks: [Task; MAX_TASKS],
    task_count: u32,
    current: u32,
    next: u32,
    quantum: u32,
    ticks: u64,
    running: bool,
}

static mut STATE: SchedulerState = SchedulerState {
    tasks: [Task::empty(); MAX_TASKS],
    task_count: 0,
    current: 0,
    next: 1,
    quantum: QUANTUM,
    ticks: 0,
    running: false,
};

/// Set the scheduler up.
pub fn init() {
    unsafe {
        let state = &mut *core::ptr::addr_of_mut!(STATE);
        state.tasks = [Task::empty(); MAX_TASKS];
        state.task_count = 0;
        state.current = 0;
        state.next = 1;
        state.quantum = QUANTUM;
        state.ticks = 0;
        state.running = false;
    }
}

/// Add a task to the scheduler.
pub fn add_task(kernel_stack: u64, entry: u64, pid: u32) -> Option<u32> {
    unsafe {
        let state = &mut *core::ptr::addr_of_mut!(STATE);

        let slot = (0..MAX_TASKS).find(|&index| state.tasks[index].state == TaskState::Unused)?;
        let task = &mut state.tasks[slot];
        task.id = slot as u32;
        task.pid = pid;
        task.state = TaskState::Ready;
        task.kernel_stack = kernel_stack;
        task.user_entry = entry;
        // The quantum starts at zero: the first tick promotes the task
        // and arms it, so a task runs for exactly `quantum` ticks.
        task.quantum_left = 0;

        if state.task_count == 0 {
            state.current = slot as u32;
        }
        state.task_count += 1;
        Some(slot as u32)
    }
}

/// Find the next task that can run.
fn find_next_runnable(state: &mut SchedulerState, from: u32) -> Option<u32> {
    for offset in 0..MAX_TASKS as u32 {
        let index = ((from + offset) % MAX_TASKS as u32) as usize;
        let task = &mut state.tasks[index];

        if task.state == TaskState::Blocked && state.ticks >= task.wake_at {
            task.state = TaskState::Ready;
        }
        if task.state == TaskState::Ready {
            return Some(index as u32);
        }
    }
    None
}

/// The timer tick.
///
/// The only thing that makes the scheduler preemptive: without it a
/// running task would keep the CPU until it blocked or exited.
pub fn tick() {
    unsafe {
        let state = &mut *core::ptr::addr_of_mut!(STATE);
        state.ticks += 1;

        if state.task_count == 0 {
            return;
        }

        let current = state.current as usize;
        if state.tasks[current].state != TaskState::Running {
            // The current slot holds a task that is not running. The
            // first task is Ready until the scheduler starts it, so
            // the very first tick has to promote it.
            if state.tasks[current].state == TaskState::Ready {
                state.tasks[current].state = TaskState::Running;
                state.tasks[current].quantum_left = state.quantum;
            }
            return;
        }

        if state.tasks[current].quantum_left > 0 {
            state.tasks[current].quantum_left -= 1;
        }
        if state.tasks[current].quantum_left == 0 {
            state.tasks[current].quantum_left = state.quantum;
            yield_now(state);
        }
    }
}

/// Give the CPU to the next runnable task.
fn yield_now(state: &mut SchedulerState) {
    let next = match find_next_runnable(state, state.next) {
        Some(index) => index,
        None => return, // nothing else to run
    };
    state.next = (next + 1) % MAX_TASKS as u32;
    if next == state.current {
        // The only runnable task is the current one: it keeps running.
        return;
    }
    switch(state, next);
}

/// Switch to another task.
fn switch(state: &mut SchedulerState, next: u32) {
    let previous = state.current as usize;
    state.tasks[previous].state = TaskState::Ready;
    state.tasks[next as usize].state = TaskState::Running;
    // The incoming task gets a full quantum.
    state.tasks[next as usize].quantum_left = state.quantum;
    state.current = next;
}

/// Yield the CPU.
pub fn yield_cpu() {
    unsafe {
        let state = &mut *core::ptr::addr_of_mut!(STATE);
        yield_now(state);
    }
}

/// The scheduler's main loop.
pub fn run() -> ! {
    unsafe {
        let state = &mut *core::ptr::addr_of_mut!(STATE);
        state.running = true;
    }
    loop {
        yield_cpu();
        cpu::hlt();
    }
}

/// The pid of the running task.
pub fn current_pid() -> u32 {
    unsafe {
        let state = &*core::ptr::addr_of!(STATE);
        if state.task_count == 0 {
            return 0;
        }
        state.tasks[state.current as usize].pid
    }
}

/// How many tasks are known.
pub fn task_count() -> u32 {
    unsafe {
        let state = &*core::ptr::addr_of!(STATE);
        state.task_count
    }
}

/// The state of a task slot, for the diagnostics.
pub fn task_state(index: u32) -> TaskState {
    unsafe {
        let state = &*core::ptr::addr_of!(STATE);
        if index as usize >= MAX_TASKS {
            return TaskState::Unused;
        }
        state.tasks[index as usize].state
    }
}

/// The remaining quantum of a task slot, for the diagnostics.
pub fn task_quantum(index: u32) -> u32 {
    unsafe {
        let state = &*core::ptr::addr_of!(STATE);
        if index as usize >= MAX_TASKS {
            return 0;
        }
        state.tasks[index as usize].quantum_left
    }
}

/// The task slot the scheduler is looking at next.
pub fn next_slot() -> u32 {
    unsafe {
        let state = &*core::ptr::addr_of!(STATE);
        state.next
    }
}

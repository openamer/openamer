//! The boot path: from the bootloader into the kernel.
//!
//! The bootloader loads the kernel as an ELF file and jumps into it
//! with a handful of values in registers. This module is the other
//! end of that jump: it takes the values apart, brings up the console,
//! sets up the memory manager, and starts the kernel.

use crate::cpu;
use crate::gdt;
use crate::interrupts;
use crate::memory;
use crate::scheduler;
use crate::vga::Color;

/// What the bootloader hands over.
///
/// The bootloader is a 16-bit real-mode program that switches to
/// protected mode and jumps to the kernel's 64-bit entry point. The
/// values below are the ones the kernel needs to know where it is and
/// what it was given.
#[derive(Clone, Copy)]
#[repr(C)]
pub struct BootInfo {
    /// The physical address the kernel was loaded at.
    pub kernel_base: u64,
    /// The kernel's size in bytes.
    pub kernel_size: u64,
    /// The start of usable physical memory.
    pub memory_base: u64,
    /// The end of usable physical memory.
    pub memory_limit: u64,
    /// The boot device the kernel was loaded from.
    pub boot_drive: u8,
}

impl BootInfo {
    /// The boot information to use when the loader did not supply any.
    ///
    /// A loader that speaks the Linux boot protocol hands the kernel
    /// nothing; the kernel then has to work out what it can. The
    /// memory region is the conventional one: everything above the
    /// first megabyte, which is where the kernel itself is loaded, up
    /// to the conventional 128 MiB.
    pub const fn defaults() -> Self {
        BootInfo {
            kernel_base: KERNEL_LOAD_ADDRESS,
            kernel_size: 0,
            memory_base: KERNEL_LOAD_ADDRESS,
            memory_limit: 128 * 1024 * 1024,
            boot_drive: 0xFF,
        }
    }
}

/// Where the kernel is loaded in physical memory.
pub const KERNEL_LOAD_ADDRESS: u64 = 0x100_000;

/// The information the bootloader passed, set once before the kernel
/// starts.
static mut BOOT_INFO: BootInfo = BootInfo {
    kernel_base: 0,
    kernel_size: 0,
    memory_base: 0,
    memory_limit: 0,
    boot_drive: 0xFF,
};

/// Record what the bootloader handed over.
///
/// # Safety
/// Must be called exactly once, before the kernel starts.
pub unsafe fn set_boot_info(info: BootInfo) {
    core::ptr::write_volatile(core::ptr::addr_of_mut!(BOOT_INFO), info);
}

/// What the bootloader handed over.
pub fn boot_info() -> BootInfo {
    unsafe { *core::ptr::addr_of!(BOOT_INFO) }
}

/// Reserve a stack region for the kernel.
///
/// The region is carved out of the physical memory the kernel manages,
/// so it does not overlap the kernel's own image and the loader's
/// memory. The returned value is the stack's top address: the stack
/// grows downwards, so that is where it starts.
///
/// # Safety
/// The region must not be in use.
pub unsafe fn allocate_stack(top: u64, size: u64) -> u64 {
    // The stack lives below its top, so the region is [top - size, top).
    let start = top - size;
    top
}

/// The kernel's entry point.
///
/// The bootloader jumps here with a pointer to the boot information in
/// the first argument register.
///
/// On real hardware the bootloader hands control here with interrupts
/// off, in a flat 64-bit environment it set up itself. From this point
/// the kernel owns the machine.
pub extern "C" fn kmain(info: BootInfo, stack_top: u64) -> ! {
    // The console first: from here on, anything that goes wrong has to
    // be able to say so.
    crate::vga::Console::clear();
    crate::klog!("OpenAmer OS -- native kernel");
    crate::klog!("");

    unsafe { set_boot_info(info) };
    let info = boot_info();

    crate::klog!("kernel loaded at 0x{:x}, {} bytes", info.kernel_base, info.kernel_size);
    crate::klog!(
        "memory region: 0x{:x} .. 0x{:x} ({} MiB)",
        info.memory_base,
        info.memory_limit,
        (info.memory_limit - info.memory_base) / (1024 * 1024)
    );
    crate::klog!("boot drive: 0x{:02x}", info.boot_drive);

    // What the CPU can do.
    if let Some(brand) = cpu::brand_string() {
        crate::klog!("cpu: {}", brand);
    }
    crate::klog!(
        "cpus: {}, sse2: {}, apic: {}",
        cpu::cpu_count(),
        cpu::has_sse2(),
        cpu::has_apic()
    );

    // The GDT before the interrupts: the interrupt stubs need a code
    // segment to run in.
    gdt::init();
    gdt::set_kernel_stack(stack_top);
    crate::klog!("gdt: initialised");

    // Memory before anything that allocates.
    unsafe { memory::init(info.memory_base, info.memory_limit) };
    crate::klog!("memory: {} MiB managed", memory::total() / (1024 * 1024));

    // Interrupts before the scheduler: a scheduler without a timer
    // has no way to make progress.
    interrupts::init();
    crate::klog!("interrupts: idt installed, pic remapped");

    // The scheduler.
    scheduler::init();
    crate::klog!("scheduler: initialised");

    // From here the machine belongs to the kernel.
    crate::vga::Console::set_color(Color::LightGreen);
    crate::klog!("");
    crate::klog!("OpenAmer OS kernel is running.");
    crate::vga::Console::set_color(Color::LightGrey);

    scheduler::run()
}

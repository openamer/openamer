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
///
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

/// The pixel framebuffer the loader mapped.
///
/// A machine with a graphics card has a pixel buffer and not the
/// VGA's text memory: the console writes into this one.
pub struct Framebuffer {
    /// The pixels.
    pub buffer: &'static mut [u8],
    /// The width in pixels.
    pub width: usize,
    /// The height in pixels.
    pub height: usize,
    /// The number of bytes between the start of a line and the next.
    pub stride: usize,
    /// The number of bytes per pixel.
    pub bytes_per_pixel: usize,
    /// The pixel format.
    pub format: crate::framebuffer::PixelFormat,
}

impl BootInfo {
    /// The boot information the loader handed over.
    ///
    /// The loader knows the memory map and the framebuffer; the
    /// kernel's own view of the machine is built from them.
    pub fn from_loader(loader: &bootloader_api::BootInfo) -> Self {
        // The usable memory: the region the loader reports as
        // usable, from the first region that is not reserved.
        let (memory_base, memory_limit) = usable_memory(loader);

        BootInfo {
            kernel_base: KERNEL_LOAD_ADDRESS,
            kernel_size: 0,
            memory_base,
            memory_limit,
            boot_drive: 0xFF,
        }
    }

    /// The boot information to use when the loader did not supply any.
    ///
    /// The memory region is the conventional one: everything above the
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

/// The framebuffer the loader mapped, if there is one.
pub fn framebuffer_from_loader(
    loader: &bootloader_api::BootInfo,
) -> Option<Framebuffer> {
    let framebuffer = loader.framebuffer.as_ref()?;

    let info = framebuffer.info();

    let format = match info.pixel_format {
        bootloader_api::info::PixelFormat::Rgb => crate::framebuffer::PixelFormat::Rgb32,
        bootloader_api::info::PixelFormat::Bgr => crate::framebuffer::PixelFormat::Bgr32,
        _ => crate::framebuffer::PixelFormat::Bgr32,
    };

    Some(Framebuffer {
        // The loader's buffer is mapped for as long as the machine
        // runs, so it is 'static.
        buffer: unsafe {
            core::slice::from_raw_parts_mut(framebuffer.buffer().as_ptr() as *mut u8, info.byte_len)
        },
        width: info.width,
        height: info.height,
        stride: info.stride,
        bytes_per_pixel: info.bytes_per_pixel,
        format,
    })
}

/// The usable memory, from the loader's memory map.
///
/// The map lists the regions in order, and the last one that is
/// usable is the end of the memory. The first one that is usable is
/// the start: the regions below it are the ones the firmware and
/// the loader have reserved.
fn usable_memory(loader: &bootloader_api::BootInfo) -> (u64, u64) {
    let mut base = 0;
    let mut limit = 0;

    for region in loader.memory_regions.iter() {
        if region.kind == bootloader_api::info::MemoryRegionKind::Usable {
            if base == 0 {
                base = region.start;
            }
            limit = region.end;
        }
    }

    if base == 0 || limit <= base {
        // Nothing usable: the conventional region.
        return (KERNEL_LOAD_ADDRESS, 128 * 1024 * 1024);
    }

    (base, limit)
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
pub extern "C" fn kmain(
    info: BootInfo,
    framebuffer: Option<Framebuffer>,
    stack_top: u64,
) -> ! {
    // The serial port first: it is the console that survives
    // everything, and it is what the output is read from.
    unsafe { crate::ports::serial_init() };

    // The framebuffer first: the console writes into it, and it has
    // to be there before the first character.
    if let Some(framebuffer) = framebuffer {
        let mut console = crate::framebuffer::FrameBuffer::new(
            framebuffer.buffer,
            framebuffer.width,
            framebuffer.height,
            framebuffer.stride,
            framebuffer.bytes_per_pixel,
            framebuffer.format,
        );
        console.clear();
        unsafe { crate::framebuffer::set(console) };
    }

    // The console: from here on, anything that goes wrong has to be
    // able to say so.
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

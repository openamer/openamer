//! CPU feature detection.
//!
//! The kernel asks the CPU what it can do before it uses anything:
//! the SSE level decides whether the memory copy can use the wide
//! registers, and the APIC is preferred over the legacy PIC when the
//! CPU has one.
//!
//! DIR-13: the CPU is interrogated directly, through its own
//! instruction, rather than through a library that hides the query.

use core::arch::x86_64::{__cpuid, __cpuid_count};

/// Whether the CPU supports SSE2.
pub fn has_sse2() -> bool {
    // CPUID leaf 1, EDX bit 26.
    let edx = unsafe { __cpuid(1) }.edx;
    (edx >> 26) & 1 == 1
}

/// Whether the CPU has a local APIC.
pub fn has_apic() -> bool {
    // CPUID leaf 1, EDX bit 9.
    let edx = unsafe { __cpuid(1) }.edx;
    (edx >> 9) & 1 == 1
}

/// Whether the CPU supports the 1GB pages.
pub fn has_1g_pages() -> bool {
    // CPUID leaf 0x80000001, EDX bit 26.
    let edx = unsafe { __cpuid(0x8000_0001) }.edx;
    (edx >> 26) & 1 == 1
}

/// The CPU's brand string, when it has one.
///
/// The string lives in a static buffer: the kernel has no allocator
/// yet at the time it asks the CPU what it is.
pub fn brand_string() -> Option<&'static str> {
    static mut BRAND: [u8; 48] = [0; 48];

    let leaf = unsafe { __cpuid(0x8000_0000) }.eax;
    if leaf < 0x8000_0004 {
        return None;
    }

    for chunk in 0..3usize {
        let value = unsafe { __cpuid_count(0x8000_0002 + chunk as u32, 0) };
        let base = chunk * 16;
        let buffer = unsafe { &mut *core::ptr::addr_of_mut!(BRAND) };
        buffer[base..base + 4].copy_from_slice(&value.eax.to_le_bytes());
        buffer[base + 4..base + 8].copy_from_slice(&value.edx.to_le_bytes());
        buffer[base + 8..base + 12].copy_from_slice(&value.ecx.to_le_bytes());
        buffer[base + 12..base + 16].copy_from_slice(&value.ebx.to_le_bytes());
    }

    let buffer = unsafe { &*core::ptr::addr_of!(BRAND) };
    let text = core::str::from_utf8(buffer).ok()?.trim();
    if text.is_empty() {
        None
    } else {
        Some(text)
    }
}

/// Read the time stamp counter.
///
/// The TSC counts cycles since the reset, and it is the kernel's most
/// precise clock source -- far better than the timer interrupt for
/// measuring how long something took.
pub fn rdtsc() -> u64 {
    let (low, high): (u32, u32);
    unsafe {
        core::arch::asm!(
            "rdtsc",
            out("eax") low,
            out("edx") high,
            options(nomem, nostack, preserves_flags)
        );
    }
    ((high as u64) << 32) | (low as u64)
}

/// The number of CPUs the CPU reports.
pub fn cpu_count() -> u32 {
    // CPUID leaf 1, EBX bits 23..16 hold the logical processor count
    // minus one.
    let ebx = unsafe { __cpuid(1) }.ebx;
    ((ebx >> 16) & 0xFF) + 1
}

/// Halt the CPU until the next interrupt.
///
/// The kernel's idle loop. The instruction is the only way to stop
/// the CPU without burning a cycle in a spin loop.
pub fn hlt() {
    unsafe {
        core::arch::asm!("hlt", options(nomem, nostack, preserves_flags));
    }
}

/// Disable interrupts and return the previous flag state.
///
/// The returned flag says whether the interrupts were enabled before
/// the call, so the caller can restore the previous state.
///
/// The assembly is in Intel syntax, which is what Rust's `asm!` uses:
/// the `q` suffixes (`popq`, `movq`) belong to AT&T syntax and are
/// rejected here.
pub fn interrupts_disable() -> bool {
    let mut flags: u64 = 0;
    let mut was_enabled: u8 = 0;
    let mask: u64 = 1u64 << 9;
    unsafe {
        // The interrupt flag is bit 9 of RFLAGS.
        //
        // The operands are named rather than numbered. Rust's assembler
        // matches a numbered operand to a mnemonic positionally, and
        // that mapping is easy to get subtly wrong -- `pop {0}` with
        // an `out(reg)` and an `out(reg_byte)` in the same list fails
        // to parse. Named operands say which register is meant.
        //
        // The test result is produced with `setne` into a fixed
        // register and then moved out, because a byte-sized `out`
        // operand cannot be the target of `setne` in this syntax.
        core::arch::asm!(
            "pushfq",
            "pop {flags}",
            "cli",
            "test {mask}, {flags}",
            "setne al",
            "movzx {was_enabled}, al",
            flags = out(reg) flags,
            mask = in(reg) mask,
            was_enabled = out(reg_byte) was_enabled,
            options(nomem, nostack)
        );
    }
    was_enabled != 0
}

/// Enable interrupts.
pub fn interrupts_enable() {
    unsafe {
        core::arch::asm!("sti", options(nomem, nostack, preserves_flags));
    }
}

/// Restore the interrupt flag state.
pub fn interrupts_restore(enabled: bool) {
    if enabled {
        interrupts_enable();
    } else {
        unsafe {
            core::arch::asm!("cli", options(nomem, nostack, preserves_flags));
        }
    }
}

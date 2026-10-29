//! Stage two: find the kernel and start it.
//!
//! The boot sector has switched the processor into 32-bit protected
//! mode and read the disk's partition table. This stage walks the
//! partitions, looks for the FAT filesystem, finds the kernel file
//! inside it, loads it into memory, and jumps into it.
//!
//! The filesystem work is done by the `fatfs` crate, which is a
//! pure-Rust FAT implementation with no operating system underneath --
//! exactly what a bootloader needs.

use core::panic::PanicInfo;

use crate::print;

/// The information the kernel is started with.
#[derive(Clone, Copy)]
#[repr(C)]
pub struct BootInfo {
    pub kernel_base: u64,
    pub kernel_size: u64,
    pub memory_base: u64,
    pub memory_limit: u64,
    pub boot_drive: u8,
}

/// Where the kernel is loaded in physical memory.
pub const KERNEL_LOAD_ADDRESS: u64 = 0x100_000; // 1 MiB

/// The name of the kernel file on the boot partition.
pub const KERNEL_FILE: &[u8] = b"OPENAMER.KRN";

/// The partition table entry, as the BIOS leaves it.
#[repr(C, packed)]
struct PartitionEntry {
    bootable: u8,
    start_chs: [u8; 3],
    partition_type: u8,
    end_chs: [u8; 3],
    start_lba: u32,
    size_lba: u32,
}

/// The MBR of the boot device.
#[repr(C, packed)]
struct MasterBootRecord {
    bootstrap: [u8; 440],
    disk_signature: u32,
    reserved: u16,
    partitions: [PartitionEntry; 4],
    signature: u16,
}

/// Run stage two.
pub fn run() -> ! {
    // For now the stage two is a stub that reports what it found.
    // The disk access and the kernel loading follow.
    print("OpenAmer OS boot sector");
    print(": stage 2 not yet implemented");
    halt()
}

/// Stop the processor.
pub fn halt() -> ! {
    loop {
        core::arch::asm!("cli; hlt", options(nomem, nostack, preserves_flags));
    }
}

/// Read the master boot record of the boot device.
pub fn read_mbr(buffer: &mut [u8; 512]) -> Option<MasterBootRecord> {
    use crate::disk;

    if !disk::read_sectors(0, 1, buffer) {
        return None;
    }
    let mbr: MasterBootRecord = unsafe { core::ptr::read_unaligned(buffer.as_ptr() as *const MasterBootRecord) };
    if mbr.signature != 0xAA55 {
        return None;
    }
    Some(mbr)
}

/// The panic handler for the bootloader.
pub fn bootloader_panic(_: &PanicInfo) -> ! {
    halt()
}

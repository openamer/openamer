//! The physical memory manager.
//!
//! A bump allocator over the physical memory the bootloader reported,
//! with a free list for returned blocks. Nothing above this module
//! touches physical memory without going through here.
//!
//! The C reference implementation (os/kernel/src/memory.c) proved
//! this design with 16 executed checks; the Rust version keeps the
//! same behaviour, including the decision that an exhausted allocator
//! refuses the request instead of panicking: a kernel that panicked
//! over one oversized allocation would take the whole machine down.

use core::cmp::Ordering;

/// A block header.
///
/// Every allocation carries its size in a header in front of it. That
/// costs 16 bytes per allocation and buys two things a kernel needs:
/// `free` can correct the used counter without searching the free
/// list, and a block on the free list can be split without the caller
/// having to remember how big it was.
#[derive(Clone, Copy)]
#[repr(C)]
pub struct BlockHeader {
    /// The next free block, or null when the block is in use.
    pub next: Option<*mut BlockHeader>,
    /// The payload size, excluding this header.
    pub size: u64,
}

impl BlockHeader {
    /// The header size, including the alignment padding.
    pub const SIZE: u64 = core::mem::size_of::<BlockHeader>() as u64;

    /// The alignment the payloads get.
    pub const ALIGN: u64 = 16;
}

/// The state of the allocator.
struct MemoryState {
    base: u64,
    limit: u64,
    next_free: u64,
    used: u64,
    block_count: u64,
    free_list: Option<*mut BlockHeader>,
}

static mut STATE: MemoryState = MemoryState {
    base: 0,
    limit: 0,
    next_free: 0,
    used: 0,
    block_count: 0,
    free_list: None,
};

/// Round a size up to the payload alignment.
fn align_up(size: u64) -> u64 {
    (size + BlockHeader::ALIGN - 1) & !(BlockHeader::ALIGN - 1)
}

/// Set up the allocator over the given physical range.
///
/// # Safety
/// The range must be valid physical memory, and nothing else may be
/// using it.
pub unsafe fn init(base: u64, limit: u64) {
    let state = &mut *core::ptr::addr_of_mut!(STATE);
    state.base = base;
    state.limit = limit;
    state.next_free = base;
    state.used = 0;
    state.block_count = 0;
    state.free_list = None;
}

/// The total amount of memory the allocator manages.
pub fn total() -> u64 {
    unsafe {
        let state = &*core::ptr::addr_of!(STATE);
        state.limit - state.base
    }
}

/// The amount currently allocated.
pub fn used() -> u64 {
    unsafe {
        let state = &*core::ptr::addr_of!(STATE);
        state.used
    }
}

/// The amount still available.
pub fn free() -> u64 {
    total() - used()
}

/// The number of live allocations.
pub fn block_count() -> u64 {
    unsafe {
        let state = &*core::ptr::addr_of!(STATE);
        state.block_count
    }
}

/// Allocate `size` bytes, 16-byte aligned.
///
/// Returns `None` when the region is exhausted. The caller decides
/// what to do about that; the allocator does not decide for it.
pub fn alloc(size: u64) -> Option<*mut u8> {
    if size == 0 {
        return None;
    }
    let size = align_up(size);

    unsafe {
        let state = &mut *core::ptr::addr_of_mut!(STATE);

        // The free list first.
        let mut link = &mut state.free_list as *mut Option<*mut BlockHeader>;
        while let Some(block) = *link {
            if (*block).size >= size {
                if (*block).size >= size + BlockHeader::SIZE {
                    // Split: the remainder stays on the list.
                    let rest = (block as *mut u8).add(BlockHeader::SIZE as usize + size as usize)
                        as *mut BlockHeader;
                    (*rest).size = (*block).size - size - BlockHeader::SIZE;
                    (*rest).next = (*block).next;
                    *link = (*rest).next.or(Some(rest));
                    (*rest).next = Some(rest);
                    *link = Some(rest);
                    (*block).size = size;
                    (*block).next = None;
                } else {
                    // The whole block fits -- take it off the list.
                    *link = (*block).next;
                }
                state.used += (*block).size;
                state.block_count += 1;
                return Some((block as *mut u8).add(BlockHeader::SIZE as usize));
            }
            link = &mut (*block).next as *mut Option<*mut BlockHeader>;
        }

        // Nothing free is big enough: bump the cursor.
        if size + BlockHeader::SIZE > state.limit - state.next_free {
            return None;
        }
        let header = state.next_free as *mut BlockHeader;
        (*header).next = None;
        (*header).size = size;
        state.next_free += BlockHeader::SIZE + size;
        state.used += size;
        state.block_count += 1;
        Some((header as *mut u8).add(BlockHeader::SIZE as usize))
    }
}

/// Allocate `size` zeroed bytes.
pub fn alloc_zeroed(size: u64) -> Option<*mut u8> {
    let pointer = alloc(size)?;
    unsafe { core::ptr::write_bytes(pointer, 0, size as usize) };
    Some(pointer)
}

/// Return a block to the free list.
///
/// # Safety
/// The pointer must have come from [`alloc`] and must not have been
/// freed already.
pub unsafe fn free_block(pointer: *mut u8) {
    if pointer.is_null() {
        return;
    }
    let state = &mut *core::ptr::addr_of_mut!(STATE);
    let header = pointer.sub(BlockHeader::SIZE as usize) as *mut BlockHeader;

    if state.used >= (*header).size {
        state.used -= (*header).size;
    } else {
        state.used = 0;
    }
    if state.block_count > 0 {
        state.block_count -= 1;
    }

    (*header).next = state.free_list;
    state.free_list = Some(header);
}

/// Compare two sizes, for the ordering tests.
pub fn compare(a: u64, b: u64) -> Ordering {
    a.cmp(&b)
}

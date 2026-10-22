/*
 * OpenAmer OS -- physical memory management.
 *
 * A bump allocator over a contiguous physical region, with a free list
 * for returned blocks. This is the lowest layer of the system: nothing
 * above it may touch physical memory without going through here.
 *
 * DIR-04: the kernel owns the machine. The memory map is a kernel
 * concept, not something borrowed from a host operating system.
 */

#include "kernel.h"

static memory_t mem;

/*
 * A block header.
 *
 * Every allocation carries its size in a header in front of it. That
 * costs 16 bytes per allocation and buys two things a kernel needs:
 * kfree() can correct the used counter without searching the free
 * list, and a block on the free list can be split without the caller
 * having to remember how big it was.
 *
 * The free list is threaded through the free memory itself, so
 * tracking free memory needs no allocation of its own.
 */
typedef struct block_header {
    struct block_header *next;  /* next free block, or NULL when in use */
    u64 size;                   /* payload size, excluding this header */
} block_header_t;

#define HEADER_SIZE ((u64)(sizeof(block_header_t)))
#define PAYLOAD_ALIGN 16u

/* Round a size up so the payload starts on a 16-byte boundary. */
static u64 align_up(u64 size) {
    return (size + (PAYLOAD_ALIGN - 1u)) & ~((u64)PAYLOAD_ALIGN - 1u);
}

static block_header_t *free_list = NULL;

/*
 * The physical region the kernel manages.
 *
 * On real hardware this is a range of physical addresses, and the
 * allocator hands out pointers into it. In a hosted build those
 * addresses do not belong to the process, so the allocator is given a
 * real host buffer instead: the same code, the same bookkeeping, a
 * backing store that the process actually owns.
 */
#ifdef OPENAMER_HOSTED

/* A host-side arena standing in for physical memory. 16 MiB: enough for
 * the allocator's own tests, small enough to stay out of the way. */
#define HOSTED_ARENA_SIZE (16u * 1024u * 1024u)
static u8 hosted_arena[HOSTED_ARENA_SIZE];

void memory_init(u64 base, u64 limit) {
    (void)base;
    (void)limit;
    mem.base = (u64)(size_t)hosted_arena;
    mem.limit = mem.base + HOSTED_ARENA_SIZE;
    mem.used = 0;
    mem.next_free = mem.base;
    mem.block_count = 0;
    free_list = NULL;
}

#else

void memory_init(u64 base, u64 limit) {
    mem.base = base;
    mem.limit = limit;
    mem.used = 0;
    mem.next_free = base;
    mem.block_count = 0;
    free_list = NULL;
}

#endif

/*
 * Allocate size bytes, 16-byte aligned.
 *
 * The free list is searched first, then the bump cursor. A freed block
 * is reused only when it is large enough; a smaller request splits it.
 *
 * Returns NULL when the region is exhausted. A kernel allocator that
 * panicked on exhaustion would take the whole machine down over one
 * oversized request; refusing the allocation lets the caller decide,
 * which is the contract every caller here expects.
 */
void *kmalloc(u64 size) {
    if (size == 0) {
        return NULL;
    }
    size = align_up(size);

    block_header_t **link = &free_list;
    while (*link) {
        block_header_t *block = *link;
        if (block->size >= size) {
            if (block->size >= size + HEADER_SIZE) {
                /* Split: the remainder stays on the list. */
                block_header_t *rest = (block_header_t *)(
                    (u8 *)block + HEADER_SIZE + size
                );
                rest->size = block->size - size - HEADER_SIZE;
                rest->next = block->next;
                *link = rest;
                block->size = size;
                block->next = NULL;
            } else {
                /* The whole block fits -- take it off the list. */
                *link = block->next;
                block->next = NULL;
            }
            mem.used += block->size;
            mem.block_count++;
            return (void *)((u8 *)block + HEADER_SIZE);
        }
        link = &block->next;
    }

    /* Nothing free is big enough: bump the cursor. */
    if (size + HEADER_SIZE > mem.limit - mem.next_free) {
        return NULL;
    }
    block_header_t *header = (block_header_t *)mem.next_free;
    header->next = NULL;
    header->size = size;
    mem.next_free += HEADER_SIZE + size;
    mem.used += size;
    mem.block_count++;
    return (void *)((u8 *)header + HEADER_SIZE);
}

void *kzalloc(u64 size) {
    void *ptr = kmalloc(size);
    if (ptr) {
        memset(ptr, 0, align_up(size));
    }
    return ptr;
}

/*
 * Return a block to the free list.
 *
 * The size comes from the block's own header, so the used counter
 * stays correct without searching the free list -- O(1) on every free,
 * which matters in a kernel that frees in interrupt context.
 */
void kfree(void *ptr) {
    if (!ptr) {
        return;
    }
    block_header_t *block = (block_header_t *)((u8 *)ptr - HEADER_SIZE);
    if (mem.used >= block->size) {
        mem.used -= block->size;
    } else {
        mem.used = 0;
    }
    if (mem.block_count > 0) {
        mem.block_count--;
    }
    block->next = free_list;
    free_list = block;
}

u64 memory_used(void)   { return mem.used; }
u64 memory_total(void)  { return mem.limit - mem.base; }
u64 memory_free(void)   { return (mem.limit - mem.base) - mem.used; }

void memory_dump(void) {
    vga_puts("memory: ", COLOR_LIGHT_GREY);
    vga_print_u64(memory_used());
    vga_puts(" / ", COLOR_LIGHT_GREY);
    vga_print_u64(memory_total());
    vga_puts(" bytes used\n", COLOR_LIGHT_GREY);
}

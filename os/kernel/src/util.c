/*
 * OpenAmer OS -- freestanding runtime helpers.
 *
 * The kernel has no libc: there is nothing to call kernel_memset() in. These
 * are the handful of primitives the kernel needs, written so the
 * compiler cannot turn them into a call to themselves -- which is the
 * classic way a freestanding memset ends up recursing forever.
 */

#include "kernel.h"

/*
 * The kernel's memory primitives.
 *
 * In the freestanding build they are named memset, memcpy, memcmp and
 * strlen -- the kernel has no libc, so these ARE the C library's
 * functions. In the hosted build they carry a prefix, because the CRT
 * exports the same names and the link would fail with a duplicate
 * symbol.
 *
 * Each is written so the compiler cannot turn it into a call to
 * itself, which is the classic way a freestanding memset ends up
 * recursing forever: the volatile pointer stops the optimizer from
 * recognising the loop.
 */
#if defined(OPENAMER_HOSTED)

void *kernel_memset(void *dst, int value, u64 count) {
    volatile u8 *p = (volatile u8 *)dst;
    for (u64 i = 0; i < count; i++) {
        p[i] = (u8)value;
    }
    return dst;
}

void *kernel_memcpy(void *dst, const void *src, u64 count) {
    volatile u8 *d = (volatile u8 *)dst;
    const volatile u8 *s = (const volatile u8 *)src;
    for (u64 i = 0; i < count; i++) {
        d[i] = s[i];
    }
    return dst;
}

int kernel_memcmp(const void *a, const void *b, u64 count) {
    const u8 *pa = (const u8 *)a;
    const u8 *pb = (const u8 *)b;
    for (u64 i = 0; i < count; i++) {
        if (pa[i] != pb[i]) {
            return (pa[i] < pb[i]) ? -1 : 1;
        }
    }
    return 0;
}

u64 kernel_strlen(const char *s) {
    if (!s) {
        return 0;
    }
    u64 length = 0;
    while (s[length]) {
        length++;
    }
    return length;
}

#else

void *memset(void *dst, int value, u64 count) {
    volatile u8 *p = (volatile u8 *)dst;
    for (u64 i = 0; i < count; i++) {
        p[i] = (u8)value;
    }
    return dst;
}

void *memcpy(void *dst, const void *src, u64 count) {
    volatile u8 *d = (volatile u8 *)dst;
    const volatile u8 *s = (const volatile u8 *)src;
    for (u64 i = 0; i < count; i++) {
        d[i] = s[i];
    }
    return dst;
}

int memcmp(const void *a, const void *b, u64 count) {
    const u8 *pa = (const u8 *)a;
    const u8 *pb = (const u8 *)b;
    for (u64 i = 0; i < count; i++) {
        if (pa[i] != pb[i]) {
            return (pa[i] < pb[i]) ? -1 : 1;
        }
    }
    return 0;
}

u64 strlen(const char *s) {
    if (!s) {
        return 0;
    }
    u64 length = 0;
    while (s[length]) {
        length++;
    }
    return length;
}

#endif

/*
 * The kernel's assertion.
 *
 * A failed assertion is a kernel panic: there is no way to continue
 * safely once an invariant is broken, and a kernel that limps on after
 * a broken invariant corrupts the machine silently.
 */
void kpanic_assert(int condition, const char *message) {
    if (!condition) {
        kernel_panic(message);
    }
}

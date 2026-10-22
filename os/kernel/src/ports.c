/*
 * OpenAmer OS -- port I/O.
 *
 * The x86 way of talking to hardware: a single instruction that reads
 * or writes a byte, word or dword to a port number. Everything the
 * kernel does with a device -- the PIC, the VGA controller, a disk
 * controller -- goes through here.
 *
 * DIR-13: operate directly on CPU patterns. This is the pattern: one
 * instruction, one port, no abstraction between the kernel and the
 * silicon.
 */

#include "kernel.h"

#if defined(OPENAMER_HOSTED)
#include <stdio.h>
#endif

/*
 * The debug console.
 *
 * On real hardware the debug console is the Bochs/QEMU debug port
 * 0xE9: a byte written to it appears on the emulated serial line, and
 * nothing else uses that port. It is how a bare-metal kernel says
 * something before the display driver is up.
 *
 * In the hosted build there is no port to write to, so the same calls
 * go to stdout. The test harness prints its results this way.
 */
#if defined(OPENAMER_HOSTED)
void debug_console_putc(char c) {
    fputc(c, stdout);
    fflush(stdout);
}
#else
void debug_console_putc(char c) {
    port_out_b(PORT_DEBUG, (u8)c);
}
#endif

void port_out_b(u16 port, u8 value) {
#if defined(OPENAMER_HOSTED)
    /* A port access is a privileged instruction; a userspace process
     * cannot perform one. In the hosted build the write is recorded
     * instead of executed -- the debug console (port 0xE9) is the
     * classic place for that, and it is where the test harness prints
     * its results. */
    if (port == PORT_DEBUG) {
        debug_console_putc((char)value);
    }
#else
    __asm__ volatile ("outb %0, %1" : : "a"(value), "Nd"(port));
#endif
}

void port_out_w(u16 port, u16 value) {
#if defined(OPENAMER_HOSTED)
    (void)port;
    (void)value;
#else
    __asm__ volatile ("outw %0, %1" : : "a"(value), "Nd"(port));
#endif
}

void port_out_d(u16 port, u32 value) {
#if defined(OPENAMER_HOSTED)
    (void)port;
    (void)value;
#else
    __asm__ volatile ("outl %0, %1" : : "a"(value), "Nd"(port));
#endif
}

u8 port_in_b(u16 port) {
#if defined(OPENAMER_HOSTED)
    (void)port;
    return 0;
#else
    u8 result;
    __asm__ volatile ("inb %1, %0" : "=a"(result) : "Nd"(port));
    return result;
#endif
}

u16 port_in_w(u16 port) {
#if defined(OPENAMER_HOSTED)
    (void)port;
    return 0;
#else
    u16 result;
    __asm__ volatile ("inw %1, %0" : "=a"(result) : "Nd"(port));
    return result;
#endif
}

u32 port_in_d(u16 port) {
#if defined(OPENAMER_HOSTED)
    (void)port;
    return 0;
#else
    u32 result;
    __asm__ volatile ("inl %1, %0" : "=a"(result) : "Nd"(port));
    return result;
#endif
}

/*
 * Wait for an I/O operation to complete.
 *
 * The legacy buses need a short delay between an output and the next
 * access. The canonical way to burn it is a write to the unused debug
 * port 0xE9 -- it exists precisely to be slow.
 */
void io_wait(void) {
    port_out_b(PORT_DEBUG, 0);
}

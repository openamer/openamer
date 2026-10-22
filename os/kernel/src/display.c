/*
 * OpenAmer OS -- display driver.
 *
 * A text-mode driver straight onto the VGA text buffer at 0xB8000, and
 * a cursor that is moved by writing the CRTC's index registers
 * directly.
 *
 * DIR-04: the display is the kernel's own driver, not a borrowed
 * framebuffer abstraction. The kernel knows where the character cells
 * are and how the cursor register works, because the kernel owns the
 * machine.
 */

#include "kernel.h"

/*
 * The character cells.
 *
 * On real hardware the text buffer is the VGA memory at 0xB8000 -- a
 * fixed physical address the CPU can write to directly. That address
 * does not exist in a hosted process, so the hosted build writes into a
 * shadow buffer instead: the same driver, the same code path, a
 * different backing store. The tests inspect the shadow buffer.
 */
#ifdef OPENAMER_HOSTED
static u16 vga_shadow[VGA_WIDTH * VGA_HEIGHT];
#define VGA_BUFFER (vga_shadow)
#else
#define VGA_BUFFER ((volatile u16 *)VGA_TEXT_BUFFER)
#endif
#define VGA_CELLS (VGA_WIDTH * VGA_HEIGHT)

static u32 cursor_row = 0;
static u32 cursor_col = 0;
static vga_color_t cursor_color = COLOR_LIGHT_GREY;

/* The attribute byte: background in the high nibble, foreground in
 * the low one. */
static inline u16 vga_attr(vga_color_t fg) {
    return (u16)(((u16)COLOR_BLACK << 4) | ((u16)fg & 0x0F));
}

/* A character cell: the character in the low byte, the attribute in
 * the high one. The two must not be OR-ed together -- the character
 * would bleed into the attribute bits. */
static inline u16 vga_cell_value(char c, vga_color_t fg) {
    return (u16)(((u16)(u8)c) | (u16)(vga_attr(fg) << 8));
}

void vga_init(void) {
    cursor_row = 0;
    cursor_col = 0;
    cursor_color = COLOR_LIGHT_GREY;
    vga_clear();
}

void vga_clear(void) {
    u16 blank = vga_cell_value(' ', COLOR_LIGHT_GREY);
    for (u32 i = 0; i < VGA_CELLS; i++) {
        VGA_BUFFER[i] = blank;
    }
    vga_set_cursor(0, 0);
}

void vga_set_cursor(u32 row, u32 col) {
    cursor_row = row;
    cursor_col = col;

    /* The cursor position is a character-cell index; the CRTC holds it
     * in two registers. */
    u32 offset = row * VGA_WIDTH + col;

#if !defined(OPENAMER_HOSTED)
    port_out_b(PORT_CRTC_ADDR, 14); /* high byte */
    port_out_b(PORT_CRTC_DATA, (u8)(offset >> 8));
    port_out_b(PORT_CRTC_ADDR, 15); /* low byte */
    port_out_b(PORT_CRTC_DATA, (u8)(offset & 0xFF));
#else
    (void)offset;
#endif
}

/* Scroll the text up by one line when the cursor leaves the screen. */
void vga_scroll(void) {
    for (u32 i = 1; i < VGA_CELLS; i++) {
        VGA_BUFFER[i - 1] = VGA_BUFFER[i];
    }
    for (u32 i = VGA_CELLS - VGA_WIDTH; i < VGA_CELLS; i++) {
        VGA_BUFFER[i] = vga_cell_value(' ', COLOR_LIGHT_GREY);
    }
    cursor_row = VGA_HEIGHT - 1;
}

void vga_putc(char c, vga_color_t fg) {
    if (c == '\n') {
        cursor_col = 0;
        cursor_row++;
    } else if (c == '\r') {
        cursor_col = 0;
    } else if (c == '\t') {
        cursor_col = (cursor_col + 4) & ~3u;
    } else {
        u32 cell = cursor_row * VGA_WIDTH + cursor_col;
        VGA_BUFFER[cell] = vga_cell_value(c, fg);
        cursor_col++;
    }

    if (cursor_col >= VGA_WIDTH) {
        cursor_col = 0;
        cursor_row++;
    }
    if (cursor_row >= VGA_HEIGHT) {
        vga_scroll();
    }
    vga_set_cursor(cursor_row, cursor_col);
}

void vga_puts(const char *s, vga_color_t fg) {
    if (!s) {
        return;
    }
    for (u32 i = 0; s[i]; i++) {
        vga_putc(s[i], fg);
    }
}

void vga_print(const char *s) {
    vga_puts(s, cursor_color);
}

void vga_print_u64(u64 value) {
    char buffer[21];
    u32 index = 20;
    buffer[20] = '\0';

    if (value == 0) {
        vga_putc('0', cursor_color);
        return;
    }
    while (value > 0 && index > 0) {
        buffer[--index] = (char)('0' + (value % 10));
        value /= 10;
    }
    vga_puts(&buffer[index], cursor_color);
}

/*
 * The character cell at a position: character in the low byte,
 * attribute in the high one.
 *
 * The hosted build reads from the shadow buffer, the freestanding one
 * from the VGA memory -- same answer either way, and the tests can
 * assert on it without knowing which build they are in.
 */
u16 vga_cell(u32 row, u32 col) {
    if (row >= VGA_HEIGHT || col >= VGA_WIDTH) {
        return 0;
    }
    return VGA_BUFFER[row * VGA_WIDTH + col];
}

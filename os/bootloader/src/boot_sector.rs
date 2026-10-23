//! The boot sector: the first 512 bytes.
//!
//! Written in assembly because it must be position-independent and
//! fit in 512 bytes, and because it has to switch the processor from
//! real mode into protected mode before anything else can run.
//!
//! The syntax is Intel, because that is what Rust's `global_asm!`
//! uses: the AT&T forms (`%ax`, `mov %al, %es:(%dx)`) are rejected by
//! the assembler's parser.
//!
//! The build script assembles this file with the LLVM assembler that
//! comes with the Rust toolchain, so no separate assembler is needed.

core::arch::global_asm!(
    // ── the entry point ────────────────────────────────────────────
    // The BIOS jumps here with DL = the boot drive.
    ".code16",
    ".globl _start",
    "_start:",
    "    cli",
    "    cld",
    "    xor ax, ax",
    "    mov ds, ax",
    "    mov es, ax",
    "    mov ss, ax",
    "    mov sp, ax",
    "    sti",

    // ── the message ────────────────────────────────────────────────
    "    mov dx, 0x03d0",
    "    mov si, msg",
    "    call print16",
    "    mov ax, 0x0a",
    "    mov dx, 0x0d",
    "    call print16",

    // ── load the stage two from the disk ───────────────────────────
    // The stage two is the second sector of the boot device.
    "    mov bx, 0x7c00",
    "    mov cx, 0x0002",
    "    mov ax, 0x0200",
    "    int 0x13",
    "    jc disk_error",

    // ── jump to the stage two ──────────────────────────────────────
    "    ljmp 0x0000, 0x7c00",

    // ── the disk failed ────────────────────────────────────────────
    "disk_error:",
    "    mov dx, 0x03d0",
    "    mov si, err_msg",
    "    call print16",
    "    jmp halt16",

    // ── print a string in real mode ────────────────────────────────
    // The string ends with a zero byte.
    "print16:",
    "    lodsb",
    "    test al, al",
    "    jz print16_done",
    "    mov es:[dx], al",
    "    inc dx",
    "    jmp print16",
    "print16_done:",
    "    ret",

    // ── stop ───────────────────────────────────────────────────────
    "halt16:",
    "    hlt",
    "    jmp halt16",

    // ── the messages ───────────────────────────────────────────────
    "msg:",
    "    .asciz \"OpenAmer OS booting...\"",
    "err_msg:",
    "    .asciz \"OpenAmer OS: disk read failed\"",

    // ── the padding to 512 bytes ───────────────────────────────────
    ". = _start + 510",
    "    .word 0xaa55",
);

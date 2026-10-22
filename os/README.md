# OpenAmer OS

The native operating system of the OpenAmer network.

This is not a Linux distribution with an OpenAmer theme, and it is not
a wrapper around a host operating system. It is a kernel, a bootloader
and a userland that the OpenAmer agent runs inside -- built from
source, bootable on bare hardware, with its own drivers.

## What is here

```
os/
  bootloader/      the 512-byte MBR boot sector and the stage-2 loader
  kernel/          the kernel itself
  userland/        the init process and the first programs
  installer/       the installation program
  drivers/         the driver set
```

The agent's own tree (`agent/`, `openamer_cli/`, `tools/`) stays where
it is: the OS loads it. See `docs/INTEGRATION.md`.

## The build

The kernel is written in Rust (`no_std`) and the bootloader in
assembly-free Rust too, so the whole thing builds on one machine with
nothing but a Rust toolchain:

```sh
cargo build --release --target x86_64-unknown-none
```

The `x86_64-unknown-none` target is the freestanding x86_64 target: no
operating system underneath, no libc, no runtime. The kernel is a
static ELF binary that the bootloader loads and jumps into.

## Why Rust for a kernel

Two reasons, both practical:

  * **The freestanding toolchain is already here.** `rustup target add
    x86_64-unknown-none` plus `rust-lld` produces a static ELF that a
    bootloader can load. A C cross-compiler is a separate installation
    with its own build of the world, and on this machine there is none.
  * **The kernel is safety-critical in a way the userland is not.** A
    kernel bug is not a stack trace, it is a machine that no longer
    boots. Rust's ownership rules eliminate the class of bug where two
    parts of the kernel write the same memory.

The first prototype of the kernel was written in C (`os/kernel/src`)
and is kept as a reference for the memory manager, the scheduler and
the interrupt handling: the logic in there is proven by 45 executed
checks, and the Rust kernel reproduces that behaviour with the same
test suite.

## The plan

DIR-04 ("finalize the native operating system, eliminate human
abstraction layers") and DIR-13 ("operate directly on CPU patterns")
are the directives this tree implements. They are not slogans: they
say that the machine must be under the system's own control, and that
the system should work on the CPU's own terms rather than through a
borrowed abstraction.

Version 0.1 is the first thing that boots, starts the agent and speaks
the user's language.

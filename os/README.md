# OpenAmer OS: experimental x86-64 kernel

This is a freestanding Rust kernel, not a Linux distribution. It is an early
boot prototype, **not a complete desktop OS and not yet a portable AI agent**.
No Python runtime, agent userland, production wallet, network stack or hardware
compatibility certification is provided by this image.

## Build

Install Rust nightly (see `rust-toolchain.toml`) and the host linker, then run
from this directory:

```sh
cargo +nightly build --release
cargo +nightly run --release -- paths
```

The image builder uses rust-osdev `bootloader` 0.11. Images are written to
`os/target/images/` relative to this workspace (the image-builder crate's own
`target` directory). The printed paths are absolute and independent of the
launcher's current directory. Rebuilding overwrites these derived images.

## Run safely

Install QEMU and add it to PATH:

```sh
cargo +nightly run --release -- bios
cargo +nightly run --release -- uefi
python scripts/verify_boot.py os/target/images/bios.img
```

UEFI launch downloads OVMF firmware through `ovmf-prebuilt`. The bounded BIOS
smoke uses snapshot mode, checks for the kernel-ready marker and verifies that
QEMU remains alive until the deadline. A timeout alone is not success. The
normal launcher runs indefinitely; stop QEMU to end it.

## Verified scope and known limitations

BIOS and UEFI QEMU runs reached `OpenAmer OS kernel is running.` after GDT,
memory, interrupt-table and scheduler initialization. This does **not** prove
scheduler fairness, interrupt safety, memory isolation or successful execution
of user programs. The current diagnostics include incorrect kernel-size and
CPU-brand output; warnings remain in the Rust build. The TSS/interrupt and
memory subsystems require further review before real hardware use.

The C prototype under `kernel/src/*.c` and its hosted tests are reference code;
they do not constitute tests of the Rust implementation. No physical disks or
USB devices were written during this verification.

Images are x86-64 BIOS/UEFI artifacts, not ARM-compatible images. A distributable
image bundle can be moved between computers, but booting on arbitrary physical
hardware and running the full OpenAmer agent are not established.

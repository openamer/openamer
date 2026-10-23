//! Build the OpenAmer OS disk images and run them in QEMU.
//!
//! The kernel is built by the artifact dependency, and the boot
//! loader turns it into a disk image -- one for BIOS, one for UEFI.
//! This program runs those images in QEMU.

use ovmf_prebuilt::{Arch, FileType, Prebuilt, Source};
use std::process::Command;

/// The path of the BIOS disk image, set by the build script.
const BIOS_PATH: &str = env!("BIOS_PATH");

/// The path of the UEFI disk image, set by the build script.
const UEFI_PATH: &str = env!("UEFI_PATH");

/// The QEMU binary. It is looked up in the path, so that the images
/// can be run without pinning a version.
const QEMU: &str = "qemu-system-x86_64";

fn main() {
    let argument = std::env::args().nth(1).unwrap_or_default();

    match argument.as_str() {
        "bios" => run(false),
        "uefi" => run(true),
        "paths" => {
            println!("the BIOS image:  {BIOS_PATH}");
            println!("the UEFI image:  {UEFI_PATH}");
        }
        other => {
            eprintln!("usage: openamer-os [bios|uefi|paths]");
            if !other.is_empty() {
                eprintln!("unknown argument: {other}");
                std::process::exit(2);
            }
        }
    }
}

/// Run the disk image in QEMU.
///
/// The UEFI image needs the firmware: the OVMF build that the
/// `ovmf-prebuilt` crate brings along, so that the image runs
/// without a firmware file that has to be installed.
fn run(uefi: bool) {
    let mut command = Command::new(QEMU);

    // The serial line, so that the kernel's output is visible.
    command.args(["-serial", "none", "-monitor", "none", "-debugcon", "stdio"]);
    // No video window: the serial line is the output.
    command.arg("-display").arg("none");
    // The guest can end QEMU: it writes to the debug exit port.
    command
        .arg("-device")
        .arg("isa-debug-exit,iobase=0xf4,iosize=0x04");

    if uefi {
        let prebuilt = Prebuilt::fetch(Source::LATEST, "target/ovmf")
            .expect("failed to fetch the UEFI firmware");

        let code = prebuilt.get_file(Arch::X64, FileType::Code);
        let vars = prebuilt.get_file(Arch::X64, FileType::Vars);

        command
            .arg("-drive")
            .arg(format!("format=raw,file={UEFI_PATH}"));
        command.arg("-drive").arg(format!(
            "if=pflash,format=raw,unit=0,file={},readonly=on",
            code.display()
        ));
        command.arg("-drive").arg(format!(
            "if=pflash,format=raw,unit=1,file={},snapshot=on",
            vars.display()
        ));
    } else {
        command
            .arg("-drive")
            .arg(format!("format=raw,file={BIOS_PATH}"));
    }

    let status = command
        .status()
        .expect("qemu-system-x86_64 not found -- is QEMU in the path?");

    // The debug exit port: 0x10 is success, 0x11 is failure.
    std::process::exit(match status.code() {
        Some(33) => 0, // QEMU encodes a guest write of 0x10 as (value << 1) | 1.
        Some(35) => 1,
        _ => 2,
    });
}

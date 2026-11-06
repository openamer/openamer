use std::path::PathBuf;

fn main() {
    // The images go into the target directory, and not into OUT_DIR:
    // Cargo treats OUT_DIR as a build artefact and removes it when
    // the build script is re-run, and the image is meant to be looked
    // at and written to a drive.
    let out_dir = PathBuf::from(std::env::var_os("CARGO_MANIFEST_DIR").unwrap())
        .join("target/images");
    std::fs::create_dir_all(&out_dir).expect("cannot create the image directory");

    // The kernel, built by the artifact dependency.
    let kernel = PathBuf::from(std::env::var_os("CARGO_BIN_FILE_KERNEL_kernel").unwrap());
    // The build script has to run again when the kernel's sources
    // change. Without this, the image in OUT_DIR stays the old one,
    // and the boot test measures a kernel that is not there any more.
    println!("cargo:rerun-if-changed=../kernel/src");
    println!("cargo:rerun-if-changed=../kernel/Cargo.toml");

    // The UEFI disk image.
    //
    // The UEFI one uses the FAT partition with an EFI system
    // partition, and it is the one that runs on a modern machine.
    let uefi_path = out_dir.join("uefi.img");
    bootloader::UefiBoot::new(&kernel)
        .create_disk_image(&uefi_path)
        .unwrap();

    // The BIOS disk image.
    let bios_path = out_dir.join("bios.img");
    bootloader::BiosBoot::new(&kernel)
        .create_disk_image(&bios_path)
        .unwrap();

    // The paths, so that main can find them.
    println!("cargo:rustc-env=UEFI_PATH={}", uefi_path.display());
    println!("cargo:rustc-env=BIOS_PATH={}", bios_path.display());
}

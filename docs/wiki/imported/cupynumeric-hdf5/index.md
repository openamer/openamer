---
title: cupynumeric-hdf5
description: Read and write large cuPyNumeric arrays to HDF5 with Legate's parallel, distributed HDF5 I/O (legate.io.hdf5: to_file, f
---

# cupynumeric-hdf5

**Description:** Read and write large cuPyNumeric arrays to HDF5 with Legate's parallel, distributed HDF5 I/O (legate.io.hdf5: to_file, from_file, from_file_batched). Use when a developer needs to save a cuPyNumeric array to an .h5/.hdf5 file, load an HDF5 dataset into a distributed cuPyNumeric array, read a large HDF5 dataset in chunks, hand arrays to an HPC pipeline as a single file, or accelerate HDF5 disk I/O with GPUDirect Storage (GDS). Do not use it for Parquet/cuDF/raw-binary or other sharded/custom layouts (see the cupynumeric-parallel-data-load skill), Zarr or object-store/S3 output, .npz or pickled archives, plain h5py without cuPyNumeric, or pure array compute such as FFT, matmul, or reductions.
**Lines:** 168 | **Code:** 33 | **Dir:** `cupynumeric-hdf5`

---

---
name: cupynumeric-hdf5
description: >-
  Read and write large cuPyNumeric arrays to HDF5 with Legate's parallel, distributed HDF5 I/O (legate.io.hdf5: to_file, from_file, from_file_batched). Use w...
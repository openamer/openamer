---
title: cupynumeric-parallel-data-load
description: Load a sharded, on-disk dataset (sharded .npy, Parquet/Arrow, raw binary, sharded HDF5, custom layouts) into a distribut
---

# cupynumeric-parallel-data-load

**Description:** Load a sharded, on-disk dataset (sharded .npy, Parquet/Arrow, raw binary, sharded HDF5, custom layouts) into a distributed cuPyNumeric ndarray via a manual partition + leaf @task launch with CPU/OMP/GPU variants. Use when no single-call loader fits, including when per-shard row counts differ across files. Prefer cupynumeric.load or legate.io.hdf5.from_file when they apply.
**Lines:** 430 | **Code:** 112 | **Dir:** `cupynumeric-parallel-data-load`

---

---
name: cupynumeric-parallel-data-load
description: Load a sharded, on-disk dataset (sharded .npy, Parquet/Arrow, raw binary, sharded HDF5, custom layouts) into a distributed cuPyNumeric ndarray via...
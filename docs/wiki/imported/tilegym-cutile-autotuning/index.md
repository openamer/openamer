---
title: tilegym-cutile-autotuning
description: Use when adding, modifying, optimizing, or debugging CuTile autotuning code. Trigger signals: `exhaustive_search` / `rep
---

# tilegym-cutile-autotuning

**Description:** Use when adding, modifying, optimizing, or debugging CuTile autotuning code. Trigger signals: `exhaustive_search` / `replace_hints` / `hints_fn` / `cuda.tile.tune` in code, `autotune` in filenames, or correctness/performance issues in autotuned CuTile kernels. Covers: tune-once/cache/launch pattern, per-architecture configs (sm80–sm120), parameter space design (tile sizes, occupancy, num_ctas), and 7 common pitfalls with solutions.
**Lines:** 241 | **Code:** 50 | **Dir:** `tilegym-cutile-autotuning`

---

---
name: tilegym-cutile-autotuning
description: "Use when adding, modifying, optimizing, or debugging CuTile autotuning code. Trigger signals: `exhaustive_search` / `replace_hints` / `hints_fn` / `cu...
---
title: cupynumeric-migration-readiness
description: Pre-migration readiness assessor for porting NumPy to cuPyNumeric. Use BEFORE substantial porting work begins when the u
---

# cupynumeric-migration-readiness

**Description:** Pre-migration readiness assessor for porting NumPy to cuPyNumeric. Use BEFORE substantial porting work begins when the user asks whether code will scale on GPU, whether they should migrate to cuPyNumeric, which NumPy patterns transfer cleanly, what must be refactored before porting, or mentions pre-port assessment, scaling analysis, or refactor planning. Inspect the user's source code, look up NumPy usage, cross-reference the cuPyNumeric API support manifest, and distinguish distributed-scaling-friendly patterns from blockers such as unsupported APIs, scalar synchronization, host round-trips, Python/object-heavy control flow, shape/data-dependent branching, and in-place mutation hazards. Produce a verdict of READY, LIGHT REFACTOR, SIGNIFICANT REFACTOR, or NOT RECOMMENDED, with concrete refactor pointers.
**Lines:** 194 | **Code:** 1 | **Dir:** `cupynumeric-migration-readiness`

---

---
name: cupynumeric-migration-readiness
description: Pre-migration readiness assessor for porting NumPy to cuPyNumeric. Use BEFORE substantial porting work begins when the user asks whether code wil...
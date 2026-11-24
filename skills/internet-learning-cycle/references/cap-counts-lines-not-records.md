# The cap counts PHYSICAL LINES, not records (measured 21.09.26)

Found while triaging a routine `rejected` cycle. The rejection itself was
**normal** (writer-side seed exhaustion — see below); the *finding* is a
separate, reproducible measurement about `enforce_cap`/`count` that silently
shrinks the training corpus. No gate was touched.

## What was measured

| metric | value |
|---|---|
| `online_buffer.jsonl` records | **152** |
| `buffer_store.count()` | **152** |
| `buffer_store.MAX_BUF` | **300** |
| `_is_duplicate(stored row)` | **True** (gate alive) |
| `_is_duplicate(novel row)` | **False** |
| rows lost vs the 09:57 backup (300 records) | **164** |
| of those 164, junk by `buffer_store.is_junk` | **0** |
| of those 164, junk by `internet_learner._is_junk` | **1** |
| learner-owned reason tail (400 rows) | `duplicate 170 / junk 133 / no-tech-signal 6` |

So the buffer is at **152 of a nominal 300** — 51 % full — while the learner
keeps logging `duplicate`. The obvious reading ("rotation exhaustion") is wrong
in its *cause*: `duplicate` fires because the **live set is half the intended
size**, not because the seed space is exhausted.

## The mechanism

`buffer_store.py`:

```python
def count(buffer=None):            # -> physikalische Zeilen, nicht Datensätze
    return sum(1 for _ in open(buf, encoding="utf-8"))

def enforce_cap(buffer=None, max_buf=None):
    lines = open(buf, encoding="utf-8").readlines()
    if len(lines) > cap:
        ...f.writelines(lines[-cap:])   # behält die letzten `cap` ZEILEN
```

Both operate on **physical lines**. The moment the store carries a blank
separator line per record (`\r\n\r\n`, the shape the 10:03 class-122 incident
left behind — 300 physical lines for 151 records,
`bak_corrupt20260921-100628`), the arithmetic inverts:

```
300 physical lines  ==  150 records + 150 blank lines
enforce_cap(cap=300) sees len(lines) == 300 , i.e. "== cap" , i.e. NO TRIM.
count() returns 300 to every caller.
```

The producer-facing contract is "300 records" — `test_buffer_store.py:84`
asserts exactly `bs.count(buf) == 300`, so 300 records *appears* to be the cap.
It is not. Once blank separators exist, the effective record cap is
`300 - blanks`, and every consumer that reports `n/MAX_BUF` (e.g.
`knowledge_to_action.experiment_tune_buffer`) reports a fill level that is half
of what the number claims.

Consequence on the live store: 164 rows were dropped without one of them being
junk. `clean_buffer.py` is **not** the culprit — its predicate
(`is_junk` / empty / echo-template / ordinal stub / <25 chars) drops
**0 of the 164**.

## What is still unexplained (do not paper over)

- **The surviving rows are not in their original order.** `live` is *not* an
  in-order subsequence of any backup (first divergence at live row 146–149),
  and the dropped set is spread across the whole file (head 100 / mid 62 /
  tail 2 of 300), not a `lines[-cap:]` prefix cut. So the loss is not *simply*
  `enforce_cap`; some **rewrite** also reordered the surviving rows. The writer
  that emits the doubled newline was never identified either (class-122 left
  the same open question).
- Therefore a cap fix alone would **not** have prevented this loss.

## Status: MEASURED-AND-DELIBERATELY-NOT-PATCHED

No production line changed. The upgrade path (`count()` and `enforce_cap()`
counting parsed records rather than lines) is scoped but **not applied**:

- `count()` is consumed by several modules and the test suite (15 tests in
  `scripts/training/test_buffer_store.py`, all green against the current
  semantics) — changing it is an interface change, not a one-liner.
- The reorder above means an unpatched rewrite path could re-create the loss
  anyway; fixing the symptom without the writer would be the same mistake the
  class-122 session already recorded as an honest gap.

Do NOT "fix" this on a single `duplicate` reject. Measure the FP set across all
rows first (same discipline as BF/BC/BE), and re-read `internet_learner.py`
before any apply (root cause T — the Darwin autopilot rewrites it under you).

## Reading a test summary in this tree (trap, 21.09.26)

`pytest.ini` sets `addopts = -q`. Passing `-q` on the command line *again*
double-quiets pytest and **suppresses the summary line entirely** — the output
ends at `[100%]` and you cannot tell 15 passed from 15 failed without scrolling.
Measured: `pytest <file> -q` → no summary; `pytest <file> -o addopts="" -q` →
`15 passed in 1.86s`. Always override (`-o addopts=""`) when you need a count, or
add `-v`/`--tb=short`.

Also: `testpaths = scripts/tests` (from `OPENAMER_HOME`), so a **bare** `pytest`
is the canonical full suite for this tree → `67 passed`. The
`scripts/training/test_*.py` files are standalone diagnostics and are
deliberately *not* collected; name them explicitly.

Control runs for a no-code-change verification (my finding changed no production
line): repo `tests/scripts/test_internet_learner_gate.py` → **128 passed**,
repo `tests/scripts` → **284 passed**, live `test_buffer_store.py` → **15
passed**, live `test_knowledge_to_action.py` → **5 passed**, bare live `pytest`
→ **67 passed**.

## Triage of the triggering cycle (normal outcome)`cycle_e_competitors: rejected, not trained (shallow + deep read both gated)`
— the rate half of the triage says **rotation noise, not a stall**:

```
rows: 2258   rejected: 634 (72% pass)   last 60: 43% pass
per-hour pass% swings 17%-67%  -> rotation noise
```

`gate_attribution_probe.py --section gate` ends in the honest verdict:

```
All junk rejects are WRITER-side and every leaf hit is pre-existing:
  => seed space exhausted, NOT a miscalibrated gate. Do not patch.
```

Leaf helpers all pre-existing (`_is_serp_snippet 71`, `_is_nav_chrome 47`,
`_is_arxiv_abstract_chrome 3`, …) — zero novel chrome shapes. So **two**
independent things are true at once and must not be conflated: the rejection is
ordinary rotation noise, *and* the buffer is half the size it claims to be.

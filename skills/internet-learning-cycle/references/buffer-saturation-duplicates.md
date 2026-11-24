# Buffer saturation vs. response-level duplicates (measured 21.09.26)

A rejection is not always a gate problem. In a **saturated buffer** (line count
== `MAX_BUF`, here 300) the dominant kill is `duplicate`, and `duplicate` is a
DIFFERENT failure mode from `junk`. Attribute before you touch any gate.

## The two reasons are distinguishable — use the audit file

`buffer_store.append()` refuses two ways and records which:

```python
if is_junk(assistant_text):          _audit(u, a, "junk");      return count(buf)
if _is_duplicate(rec, buf):          _audit(u, a, "duplicate"); return count(buf)
```
→ `scripts/training/buffer_junk.jsonl`, one JSON row per refusal:

```bash
tail -40 scripts/training/buffer_junk.jsonl | grep -o '"reason": *"[^"]*"' | sort | uniq -c
# measured 21.09.26:  20 "reason": "duplicate"      20 "reason": "junk"
```

Rule of thumb: `junk` → a **gate** shape regressed (triage
`references/rejection-triage.md`). `duplicate` → **saturation**, the buffer is
full and the learner keeps re-observing rows it already holds. Do NOT loosen a
gate for a `duplicate` reject; it is not a gate at all.

## Root cause — `_is_duplicate` compares the `(u, a)` TUPLE

`buffer_store.py`:

```python
def _is_duplicate(rec, buf):
    target = (rec.get("u", ""), rec.get("a", ""))
    ...  # exact tuple match only
```

So the **same answer under a different question** is NOT a duplicate and gets
appended. Live evidence from the tail:

```
row 298 u=Best practice from official docs: vLLM v2.12.0 kv_cache_prefill
row 299 u=What new agent architectures are trending on GitHub?
row 300 u=Best practice from official docs: vLLM v2.12.0 kv_cache_prefill_prefetch
        a=Multi-platform Support : Support for NVIDIA GPUs (CUDA), AMD GPUs (ROCm),
          Intel GPUs (XPU), TPUs (XLA), and CPUs vllm/platforms/__init__.
```

Three buffer rows, one identical 137-char answer, two different `u`s — all
three accepted. Rows 298–300 are a **doc-page chrome line** (vLLM platform
support list) that the deep-read picked as the "best" prose; class BC/AG
territory, but here it slipped through as a *duplicate-shaped* row rather than
being gated.

Measured scale over the whole buffer
(`scripts/buffer_answer_dup_probe.py`):

| metric | value |
|---|---|
| buffer rows | 300 (== `MAX_BUF`, saturated) |
| distinct answers | 284 |
| answers repeated ≥2× | 13 |
| redundant rows (extra copies) | 16 |
| duplicate share of buffer | **5.3 %** |

Repeats are not confined to chrome — real prose repeats too, e.g. the PEFT/LoRA
"May 28, 2026 LoRA & PEFT Fine-Tuning" block landed **3×** (rows 156/180/195,
all `u=Best practice from official docs: PEFT LoRA training best practices …`)
and a quantization table landed 2× under two different *paper* framings. So the
leak is systematic `(u, a)`-equality, not one bad source.

## Why rotation cannot clear it

`enforce_cap()` keeps the **newest** `cap` lines (`lines[-cap:]`). A row that is
re-observed every rotation is written again at the tail and therefore **never
ages out** — the same 137-char answer can hold a permanent slot while genuinely
novel rows are trimmed away. Saturation + tuple-dedupe = a stable, self-renewing
duplicate, not a transient.

## Status: MEASURED-AND-DELIBERATE-NON-FIX

No production line was changed for this in the session that measured it. The
upgrade path (answer-level / normalized-answer dedupe in `_is_duplicate`) was
scoped but **not applied**, because it needs its own FP measurement over all 300
rows first — a normalized-answer key (`a` lowercased/truncated to ~120 chars)
would collapse genuinely distinct rows that merely share an opening sentence.
Same discipline as the BF/BC/BE entries: **measure the FP set before the patch,
and re-read `internet_learner.py` before every apply** (root cause T — the
Darwin autopilot rewrites it under you). Do not "fix" this on a single
`duplicate` reject alone.

## Re-measured 22.09.26 (cron internet-learning cycle) — same ~5 % share, one family now at 4×

Reproduced with the packaged probe (`scripts/buffer_answer_dup_probe.py`), so this is
a re-measurement, not a re-derivation:

| metric | 21.09.26 (doc above) | 22.09.26 |
|---|---|---|
| buffer rows | 300 (== `MAX_BUF`, saturated) | **235** (below cap) |
| answers repeated ≥2× (exact `a`) | 13 | **8** |
| redundant rows (exact-`a` extra copies) | 16 | **10** |
| exact-`a` duplicate share | 5.3 % | **4.3 %** |

**Read the basis off the probe, not off this table.** `buffer_answer_dup_probe.py`
groups on the **exact** `a`, which is the right instrument for this leak. A
*prefix*-based near-duplicate scan (same `a` truncated to 160 chars) counts one group
more, because drifted wording splits off: it reports **9 groups / 12 redundant rows /
5.1 %**. Both are true; they answer different questions. Do not quote the 5.1 % as the
probe's output.

Two things this second sample settles:

- **The ~5 % share is a floor, not a cap artifact.** The buffer is *below* `MAX_BUF`
  here (235 < 300) and redundant rows persist — so `enforce_cap`'s FIFO trim is not
  what creates them, and the "pinned at 300" reading of the 21.09.26 numbers was
  incidental. Same mechanism, lower occupancy.
- **The LoRA/PEFT family grew 3× → 4×.** On 21.09.26 it was rows 156/180/195; today
  it is **rows 5, 29, 44, 234** of `online_buffer.jsonl`, and every copy is
  **byte-identical** (`a_len=228`), differing only in `u`:

  ```
  row   5  u=Best practice from official docs: PEFT LoRA training best practices limitations and failure modes
  row  29  u=Best practice from official docs: PEFT LoRA training best practices production case study
  row  44  u=Best practice from official docs: PEFT LoRA training best practices best practices 2026
  row 234  u=Best practice from official docs: PEFT LoRA training best practices common pitfalls
           a=May 28, 2026 LoRA & PEFT Fine-Tuning: Production Guide for 2026 Master LoRA and PEFT fine-tuning: …
  ```

  and the same 228-char answer appears in `internet_learn_log.jsonl` **5×** across
  7 days (15.09 04:47, 18.09 23:26, 20.09 08:36, 21.09 01:54, 22.09 03:41), always
  from `cycle_d_docs` and always ~33–62 s spent. The 22.09.26 03:41 run is row 234,
  i.e. **the cycle's `doc-learn:` accept was the 4th byte-identical copy of knowledge
  already held** — the answer is real prose (not a stub), but it teaches nothing the
  first copy did not.

  The exact-equality mechanism is confirmed rather than merely plausible: all four
  rows share one `a`, so `(u, a)` never matches. **No gate was touched** — status
  stays MEASURED-AND-DELIBERATE-NON-FIX, exactly as in the section above.

Re-measure with the packaged probe, not by hand:

```bash
python <OPENAMER_HOME>/skills/internet-learning-cycle/scripts/buffer_answer_dup_probe.py
```

## Downstream symptom: `auto_skill_creation` reports a bare "Total: 0"

Measured 21.09.26 (cron run of `scripts/training/auto_skill_creation.py`):
`Total: 0 new skills created` — exit 0, no other output. **That zero is not a
failure.** It is the same saturation seen one stage further down the pipeline,
and it looked identical to a broken script until the skip reasons were measured.

The script's two inputs are small windows, and both were fully duplicate:

| source | window | rows | outcome |
|---|---|---|---|
| `kta_log.jsonl` | `readlines()[-10:]` | 10 | 8 readable → **8 duplicate** (2 empty `insight_question`) |
| `online_buffer.jsonl` | `readlines()[-30:]` | 30 | 8 pass the keyword+`is_usable_text` filter → **8 duplicate** |

0 CREATE / 16 duplicate. `dedupe_check(name, …)` is a *name*-slug match against
`skills/auto-generated/` (104 dirs) + registry (`count` 104 == dirs 104), so a
saturated input window of already-slugged questions yields nothing forever — the
vLLM "Best practice from official docs" question alone slugs to the same
`auto-best-practice-from-official` every cycle.

Diagnosis rule: **count before you conclude.** Re-derive the verdict per row
(`is_usable_text` → `is_domain_relevant` → `dedupe_check`) and print why each was
dropped. Do not patch a gate for a 0 that is 100 % duplicates, and do not
"refresh" the registry (`auto_skills.json`) to force writes — that re-creates
already-promoted skills under new names.

Fixed (21.09.26): the script now prints `[auto-skill] skipped duplicate: <name>`
/ `skipped empty slug` per row and a closing line naming saturation vs.
unreadable, in `scripts/training/auto_skill_creation.py`. A later 0 therefore
carries its own explanation instead of needing this probe.

## Probe §4's "over-firing" line is a FALSE ALARM on a trimmed buffer (measured 21.09.26)

`gate_attribution_probe.py --section all` ends section 4 with:

```
buffer rows: 190 (MAX_BUF is typically 300)
duplicate rejects in slice: 171
  exact (u, a) already stored : 143
  same u, different a         : 21
  unattributable (novel?)     : 7
  => some duplicate rejects are NOT stored: the gate may be over-firing.
```

That `over-firing` conclusion was chased and **disproved** in the same cron
session. The check builds its `pairs`/`us` sets from the **live** buffer only, so
every refusal that was legitimately STORED and later removed — scrub, dedupe,
`clean_buffer`, or FIFO trim — re-appears as "not stored". It measures how much
buffer history was lost, not how often `_is_duplicate` misfires.

Measured re-check: the same 400-row slice yields **18** unattributable refusals
once the probe's foreign-row filter is dropped, and **18/18 were present in an
earlier same-day snapshot** of `online_buffer.jsonl` (searched all 127 `*.bak*`
files for each refusal's `u`). Zero evidence of over-firing.

Trigger condition: `buffer rows << MAX_BUF` (190 vs 300) **and** same-day scrub
backups (`bak.cls125`, `bak.kta…`, `bak.1789…`). Do NOT loosen `_is_duplicate`
on this line — attribute each refusal against the same-day backups first.

## Traps hit while measuring

- **`tail -3 online_buffer.jsonl` is not evidence.** mtime and last rows only
  prove *a* write happened. The duplicate is visible only by **grouping on
  `a`** — hence the packaged probe.
- **`tests/scripts/test_buffer_store.py` does NOT exist in the repo.** The
  buffer-store tests live at `scripts/training/test_buffer_store.py`. Running
  the wrong path yields `file or directory not found … no tests ran in 0.01s`,
  which is easy to misread as a green-ish "0 failures".
- **Repo ↔ live md5 equality is the gate's licence.** The repo copy and the
  live AppData copy of both training modules are byte-identical
  (`md5sum` → same hash for `scripts/training/internet_learner.py` and
  `buffer_store.py`), and `git status --porcelain -- scripts/` is empty ⇒ the
  repo test suite is a valid regression control for the *live* scripts. Re-check
  this equality before citing the suite as evidence for a live-path change.

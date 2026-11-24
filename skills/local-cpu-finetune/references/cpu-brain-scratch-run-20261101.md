# From-scratch CPU brain — measured run (2026-11-01)

Reference numbers for the 4.92M-param byte-level model in `openamer_brain/`
(from scratch, not LoRA). Use these to judge whether a new run is plausible.

## Corpus actually on disk

| Source | Records | Chars |
|---|---|---|
| `a2a/openamer-brain.jsonl` | 736 (32.79 MB) | 30,650,669 |
| `scripts/training/sft_openamer.jsonl` | 417 | 263,775 |
| `scripts/training/online_buffer.jsonl` | 300 | 63,910 |
| **Total** | **1,453** | **30,978,358** |

→ **31,227,816 byte tokens.** Model 4,922,625 params.

Shape warning: 736 records but 32.8 MB ≈ **43 KB per record** — each brain
record is a whole trajectory including tool output. Record count says nothing
about corpus size, and `brain_collect` regenerates the file, so the count
changes between runs.

## Loss curve

Steps 20–1000 validated on **one** chunk (noisy). Steps 1200+ average **8**
held-out offsets. The halves are not comparable: the apparent regression from
2.31 @800 to 2.58 @1000 is the *measurement* changing quality.

| Step | train | val | tok/s |
|---|---|---|---|
| untrained | 5.591 | — | — |
| 20 | 3.862 | 2.9379 (1 chunk) | 3,226 |
| 200 | 2.849 | 2.7506 (1) | 809 |
| 250 | 2.487 | 2.8703 (1) | 3,857 |
| 400 | 2.630 | 2.6615 (1) | 847 |
| 500 | 2.706 | 2.8072 (1) | 4,019 |
| 600 | 2.550 | 2.5068 (1) | 3,260 |
| 750 | 2.356 | 2.6610 (1) | 3,089 |
| 800 | 2.029 | 2.3093 (1) | 3,539 |
| 1000 | 2.214 | 2.5769 (1) | 3,785 |
| 1200 | 2.036 | **2.4531 (8 chunks)** | 675 |
| 1400 | 1.990 | **2.3395 (8 chunks)** | 1,595 |

Last-50 mean train loss at step 1400: **1.9400**.

The 1.99 / 2.34 train-val gap is **not** clean overfitting: the val split is
the **last 2% of the file**, and the corpus is roughly chronological, so the
held-out slice covers different topics. A random split is not available —
chunks overlap via stride 128, so random selection leaks.

## Throughput, with the cause of each collapse

| Condition | tok/s |
|---|---|
| Quiet box, batch 8, `--threads 8` | 3,800–5,160 |
| Desktop app + Defender + cron Python | 350–900 |
| `llama-server.exe` holding ~16 cores | 600–1,600 |

Diagnostic that identified it — sum, then **name the offender**:

```python
import psutil, time
ps = psutil.process_iter(['pid', 'name'])
live = [(p.pid, p.info['name'], sum(p.cpu_times()[:2])) for p in ps]
time.sleep(3)
for pid, name, t0 in live:
    p = psutil.Process(pid)
    print(f"{((sum(p.cpu_times()[:2]) - t0) / 3 * 100):7.1f}%  {name}")
```

`llama-server.exe` at 1,635% (a bench/cron job) was the cause — the trainer was
innocent. Summing to 2,116% on a 1,600%-capacity box is oversubscription, not a
slow model.

## Generation progression

| Step | Cache | tok/s | Sample after prompt |
|---|---|---|---|
| untrained | — | — | random bytes |
| 200 | no (padded) | 1.0 | `Ten  atin atoomer \| ` |
| 400 | yes | 6.9 | `chentieren fistin Ni` |
| 1000 | yes | 280 | `` \| **Crow \| `rodenenamion-py` \| \| \| ✅ `` |
| 1400 | yes | 29* | `1446 Aug 20 19 topents/skill-scheck-loch` |

\* measured while `llama-server.exe` held the cores; same code + checkpoint gave
280 tok/s on a quiet box.

The progression is the real signal: random bytes → word-shaped fragments →
learned corpus structure (markdown tables, `✅`, `<|role|>` markers, date
strings, repo paths). That is what ~0.07 epochs looks like — a working training
loop, not a usable assistant.

## Wall clock

| Work | Time |
|---|---|
| 1,000 steps fresh, quiet box | ~7 min |
| 1,000 steps with cron/Defender load | ~13 min |
| 400 steps resume, loaded box | ~9 min |
| Corpus load + tokenize (31 MB) | ~5 s per process start |

## Checkpoint size discrepancy (unexplained)

`openamer brain model` reported 59.16 MB at step 1000 and 19.72 MB at step
1400. 4.92M params × 4 bytes = 19.7 MB, so 19.72 MB is weights-only; the 59 MB
file evidently carried AdamW state. Why the later file lost it was not
investigated — check `"optimizer" in blob` before assuming resume preserves
optimizer momentum.

## Operational traps hit during this run

- **A `--steps 3` smoke run overwrote the step-1000 checkpoint.** The trainer
  now rotates the previous file to `*.prev.pt`, but before that the only copy of
  a 15-minute training run was gone. Never point a smoke test at the production
  checkpoint path.
- **Validation on one chunk swings 2.13 vs 2.58 at identical train loss.**
  Average several held-out offsets or the number is noise.
- **`check_brain.py`, not `test_causality.py`.** Any `test_*.py` is imported at
  pytest collection time, and this module runs its assertions at module level.
- **Subprocess stdout is dropped under MSYS/git-bash** when inherited: a plain
  `subprocess.call()` trained silently. Read the child stream via
  `Popen(stdout=PIPE)` and `print(..., flush=True)`.

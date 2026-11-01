# openamer_brain — the local CPU brain

A small decoder-only language model that trains and runs **on this machine's
CPU only**. No GPU, no API key, no network. It reads the corpus OpenAmer
already collects (`openamer a2a brain collect`) and turns it into weights.

```
openamer brain model                 # checkpoint, params, device, step, loss
openamer brain train --steps 1000    # train on the collected corpus
openamer brain train --steps 500 --resume
openamer brain say "OpenAmer is a"   # one offline thought
openamer brain stats                 # what the corpus contains
```

## Requirements

`torch` (CPU build) is the only third-party dependency:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

Without it every `openamer brain` command still works except `model`, `train`
and `say`, which print the exact install line instead of failing obscurely.

## Architecture

4.92M parameters at the default size (`d_model=256`, 6 layers, 4 heads,
byte-level vocab 256, context 256).

| Part | What it does |
|---|---|
| `SpectralMix` | Causal FIR kernel per channel (length 32), applied as a multiplication in the frequency domain via rFFT. Output `t` sees only inputs `<= t`. Starts as a delta so it is an identity at init. |
| `Attention` | Standard causal multi-head attention, `F.scaled_dot_product_attention`. |
| `ConceptBottleneck` | `d_model -> 64 -> d_model` with a sigmoid gate and a learned `gate_scale`. This is the memory-gate stabilization: the gate is ~0.5 at init and opens slowly during training (measured: 0.462 -> 0.522 over 1000 steps). |
| KV cache | `generate()` decodes one position at a time, reusing cached keys/values plus the FIR's last 31 inputs. Bit-identical to the full-recompute path (verified, max diff 2.7e-7). |

### Why the FIR is causal

The first version filtered the whole sequence with a learned complex FFT
filter. That leaked the future: untrained loss measured 2.24 instead of
`ln(256) = 5.545`, meaning the model could already predict its target. The
fix — a left-aligned FIR kernel evaluated per position — brought untrained
loss to 5.591. `test_causality.py` check [2] asserts that perturbing token `t`
never changes logits before `t`.

## Corpus curation (`corpus.py`)

The raw brain log is not a usable training corpus. Measured on this machine
(145 MB, 7,672 records, 60,345 messages):

| Property | Value |
|---|---|
| Duplicate messages | **59.7 %** — each trajectory re-writes the whole history |
| Role `tool` | 42 % of messages |
| Huge messages | 7.4 % of messages hold **81 %** of all characters (95.8 M of 117.7 M) |

Training on the raw log taught the model `ls` output (`"1446 Aug 20 19
topents/skill-scheck-loch"` was literally a generated sample). `corpus.py`
curates before training and reports what each stage removed:

| Variant | Tokens | Kept |
|---|---|---|
| raw, no filtering | 136.7 M | 100 % |
| dedupe only | 50.7 M | 36.9 % |
| dedupe + drop `tool` + 1200 cap | 14.3 M | 10.2 % |
| **dedupe + all roles + 800 cap (default)** | **20.5 M** | 14.7 % |

The single most valuable number here: the *unique* dialogue in the brain log is
**20.5 M tokens — 15 % of what the model used to see.** Before curation it was
mostly re-reading the same trajectories.

Flags: `--max-msg-chars`, `--drop-role`, `--keep-role`, `--no-dedupe`.
Over-long messages keep head **and** tail (tool output carries its meaning at
both ends).

## Comparing two checkpoints honestly

`score_checkpoints.py` evaluates any checkpoints against one identical held-out
slice of the curated corpus — training logs from different corpora are not
comparable:

```bash
python score_checkpoints.py ../../checkpoints/ckpt_a.pt ../../checkpoints/ckpt_b.pt
```

## Measured on this laptop (16-core, CPU only)

| Metric | Value |
|---|---|
| Corpus | 31.2M byte tokens (736 brain trajectories + 417 SFT + 300 online-buffer pairs) |
| Training throughput | 3,900–5,160 tok/s (batch 8, seq 256, 8 threads) |
| Loss, untrained | 5.591 (= uniform) |
| Loss after 1,000 steps | train 2.21, val 2.13 |
| Generation, no KV cache | 1.4 tok/s |
| Generation, KV cache | **280 tok/s** (40 tokens in 143 ms) |
| Checkpoint | 59.2 MB |

1,000 steps is ~0.07 epochs of the corpus, so output is still word-shaped
noise with learned structure (markdown tables, `✅`, `<|role|>` markers show
up). It is not a usable assistant yet — it is a working training loop with a
measurable loss curve.

**Throughput depends on system load.** With the desktop app, Defender and cron
Python processes running, the sum of process CPU time was 2,116% on a
1,600%-capacity box and throughput collapsed from 3,900 to ~350 tok/s. The
numbers above are from a quiet machine.

## Corpus sources

`openamer_train.py` reads, in this order:

1. `$OPENAMER_HOME/a2a/openamer-brain.jsonl` — chat/trajectory records (`messages`)
2. `$OPENAMER_HOME/scripts/training/sft_openamer.jsonl`
3. `$OPENAMER_HOME/scripts/training/online_buffer.jsonl` — `{"u": ..., "a": ...}` pairs
4. `~/.openamer/brain_data/*.{txt,jsonl,md}` — drop-in extra corpus

Record shapes are auto-detected (`messages`, `text`/`content`/`prompt`,
`u`/`a`, or a raw line). If nothing is found, a bootstrap corpus keeps the loop
alive instead of crashing.

## Files

| File | Role |
|---|---|
| `openamer_prototype.py` | The network: config, SpectralMix, Attention, ConceptBottleneck, generate, KV cache |
| `openamer_train.py` | Training loop, corpus loading, checkpoints (model + optimizer), `train_log.jsonl` |
| `brain_scan.py` | Evaluation: checkpoint state, corpus size, generation latency |
| `openamer_unified.py` | `OpenAmerBrainService` — `think()`, `remember()`, `recall()`, `heartbeat_tick()` |
| `test_causality.py` | No-leak proof, checkpoint round-trip, KV-cache parity, speed comparison |

All four run both as scripts (`python openamer_train.py`) and as package
modules (`python -m openamer_brain.openamer_train`).

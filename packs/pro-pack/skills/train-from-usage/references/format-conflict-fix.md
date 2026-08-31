# Format Conflict: daemon vs brain collect (pre-v1.3)

## The Bug

Two systems wrote to the same file (`~/.openamer/a2a/openamer-brain.jsonl`)
in **different formats**:

| System | Format | Has `_fingerprint`? | Write mode |
|---|---|---|---|
| `scripts/session_to_brain.py` (daemon) | **Rich** — `_fingerprint`, `_session_id`, `stats`, `messages` | ✅ Yes | Append |
| `openamer a2a brain collect` (via `braindata.build_dataset`) | **ChatML** — `messages`, `engine` only | ❌ No | Overwrite |

**Result:** Daemon appended 35 rich-format records → then `brain collect` ran
and **overwrote the entire file** with 21 minimal ChatML records. Data loss.

## The Root Cause

In commit 92ead087d, the daemon was changed to write directly to the brain
dataset file (instead of its own staging file under `trajectories/`). But
`braindata.build_dataset` also writes to the same file and **always opens it
with mode "w"** (truncate + overwrite). No coordination was added.

## The Fix (commit 77c34917f — v1.3)

**Two-stage architecture:**

1. Daemon writes to `~/.openamer/trajectories/daemon-trajectories.jsonl`
   (staging, rich format, append mode)
2. Every 5 cycles (~5 min), daemon spawns `openamer a2a brain collect`
   as a subprocess. This reads ALL trajectory files (including staging) +
   mesh memory and writes the canonical ChatML dataset.

## Format validation

The brain dataset (`openamer-brain.jsonl`) must NEVER contain `_fingerprint`.
If it does, the staging/consolidation pipeline is not working — the daemon
is writing directly to the wrong file.

```bash
# Quick format check:
python3 -c "
import json
with open(r'~/.openamer/a2a/openamer-brain.jsonl') as f:
    first = json.loads(f.readline())
    if '_fingerprint' in first:
        print('✗ WRONG: brain dataset has rich-format records')
        print('  Daemon is writing directly to brain dataset!')
    else:
        print('✓ OK: brain dataset is clean ChatML')
"
```

## Prevention

The `scripts/session_to_brain.py` function `_brain_dataset()` was renamed to
`_trajectory_file()` to make the staging path explicit. The function
`_run_brain_collect()` was added to the watch loop. The staging file path
(`~/.openamer/trajectories/daemon-trajectories.jsonl`) is picked up by
`brain collect` automatically because it scans for `*traject*.jsonl` files
under `~/.openamer/trajectories/`.
# Closing the GPU Loop: distil → GPU train → hot-swap

Verified live 2026-09-11 on the RTX 3060 Ti box.

## Why this matters

The gap that mattered most: the loop collected training data for weeks but the
target model was never fed it — *"data collection without training is hoarding,
not learning."* This is the end-to-end chain that closes it.

## 1. Distil real conversations, not buffer noise

`sft_openamer.jsonl` is built by `distill_sft.py` from
`~/.openamer/a2a/openamer-brain.jsonl` (real session trajectories), **not** from
`online_buffer.jsonl`. It is the better training set: 84 clean conversation
pairs vs. only 16 usable buffer rows. Prefer it.

## 2. The quality gate is load-bearing

A live audit found the distilled data carried exactly the failure modes the user
forbids — a student model would learn them as *fact*:

| class | example | count |
|---|---|---|
| hallucinated self-metrics | "Bin top. **DeepSeek V4 Flash**, 99 Tools, 281 Skills" | 5 |
| reasoning-trace leak | "Let me start by exploring the existing codebase…" | 4 |
| self-praise | "Bin top", "state of the art" | 2 |

Training on these makes the student assert invented numbers — a direct violation
of the user's hardest rule.

`distill_sft._answer_is_safe()` rejects all three before a pair is written:

```python
_BAD_ANSWER = _re.compile(
    r"(?:\b\d{2,4}\s*(?:tools|skills)\b"              # invented counts
    r"|\b(?:bin|ich bin)\s+(?:top|der beste|die nr)"   # self-praise
    r"|state[\s-]?of[\s-]?the[\s-]?art|weltklasse"
    r"|^\s*(?:we need|the user|let me|i need|i should|we have|we must))",
    _re.IGNORECASE | _re.MULTILINE,
)
```

Result: 143 raw → **84 safe pairs, 0 unsafe remaining**. Plus a
`MIN_EXPECTED_PAIRS = 10` guard so a collapsed (0-row) dataset ABORTS loudly
instead of overwriting the training file with nothing.

## 3. The buffer junk filter needed FOUR waves, not one

The original `buffer_store.is_junk` had 10 markers and reported
**"0 junk / 300 clean"** — while a hand audit found **266 of 300 rows
unusable**. Every wave was only found by manually reading the previous wave's
survivors.

| wave | class | removed | detector |
|---|---|---|---|
| 1 | trace markers + degenerate repeat | 103 | `_JUNK_MARKERS`, token-ratio |
| 2 | English planning-voice openers | 26 | `_TRACE_OPENER` regex |
| 3 | raw SERP snippets (search chrome) | 148 | `_is_serp_snippet` |
| 4 | periodic repeats, HTML entities, template/UI chrome | 45 | `_is_periodic_repeat`, `_is_nav_chrome` |

**Lesson: "0 junk" from a filter you wrote is not evidence — hand-audit the
survivors.** Final: 300 → 16 usable; all 266 removals archived to
`buffer_junk_archive.jsonl` (never silent, never destructive).

Notable detectors:

```python
# planning voice ("We need…", "We have…", "1. The user asks…")
_TRACE_OPENER = _re.compile(r"^\s*(?:\d+[.)]\s+)?(?:we need|we have|we must|"
    r"we should|i need|i should|i will|i'?ll |let me|the user|the question|"
    r"the prompt|first,? i|okay,? (?:so|let)|here'?s? (?:a|my) (?:thinking|reasoning|plan)|"
    r"thinking process|analy[sz]e the)", _re.IGNORECASE)

# SERP chrome: em-dash + German date + middle dot
_SERP_DATE = _re.compile(r"—\s*\d{1,2}\.\s*(?:Jan|Feb|Mär|Mrz|Apr|Mai|Jun|Jul|"
                         r"Aug|Sept?|Okt|Nov|Dez)\.?\s*\d{4}\s*·")

# periodic repetition: shortest unit repeated to fill the text
_REPEAT_UNIT = _re.compile(r"(.{3,40}?)\1{2,}", _re.DOTALL)
# + fallback: >=4 tokens drawn from <=3 distinct words, but >=4 distinct chars
```

## 4. Filter eagerness is a real risk — test BOTH directions

Several iterations broke legitimate data before they were right:

- `"a"*5000` **is** degenerate repetition (correctly refused) — so a
  `test_truncation_limits` fixture using it never reached the truncation branch.
  **Fix the fixture, not the filter.**
- `"a1"`/`q0` synthetic placeholders and real one-word answers ("Ja.", "Nein!")
  must survive. The fragment check needs a natural-language word:
  `^[A-Za-zÄÖÜäöüß]{2,}$`, not all-lowercase, no punctuation.
- `_is_duplicate` must compare a **tuple** `(u, a)` — a `set` treats swapped
  u/a as identical. And it must compare parsed JSON, not a `sort_keys=True`
  dump against an unsorted written line (that mismatch made the check a silent
  no-op, which is how it was caught).
- The token-ratio repetition floor had to drop from 6 to 4 (`Self`×4 slipped
  through).

Guard: 15 tests in `test_buffer_store.py` (was 11), including
`test_all_junk_wave_classes_are_rejected` (17 named cases) and
`test_real_answers_survive_the_junk_filter` (10 real answers must pass).

## 4.a A writer-side gate does NOT cover re-injection paths

Found live the same session, *after* the four waves were in place: four junk
rows were still in the buffer, every one of them already present in
`buffer_junk_archive.jsonl`. They were **not** new writes — `online_learning.py`'s
replay branch samples old buffer lines and pushes them back through
`buffer_store.append()` to reinforce retention, so a row predating the current
rules returns forever. The gate only guards the *first* write of a row.

Rule: when you add a quality gate at a write choke point, grep for every path
that **re-reads the store and writes it back** (replay, replay-buffer,
re-injection, compaction, migration, "restore from archive"). Each is a bypass.
Fix in the replay path by filtering the sampled rows *before* re-appending, and
only sampling from rows that still pass:

```python
ok_lines = []
for ln in buf_lines:
    try:
        rec = json.loads(ln)
    except json.JSONDecodeError:
        continue
    if not buffer_store.is_junk(rec.get("a", "")):
        ok_lines.append(rec)
picks = _r.sample(ok_lines, min(2, len(ok_lines))) if ok_lines else []
```

Verify by re-running the audit after a replay cycle, not just after a fresh
write. Diagnostic that pinned it: the offending rows were byte-identical to
archive entries — "in archive but in the live store" means re-injection, never a
new write.

## 4.b Two copies of the same module drift — sync BOTH

There are two `scripts/training/` trees on this box:
`AppData/Local/openamer-laptop/scripts/training/` (the RUNNING copy) and
`AppData/Local/openamer-laptop/openamer-agent/scripts/training/` (a clone), plus
the git SoT at `openamer-repo/scripts/training/`. After adding the detectors to
the running copy, the clone still had the OLD 2.3 KB module — and it is the kind
of drift that silently reverts a fix for whichever process imports the other
tree. Confirm which file is actually loaded before believing a fix is live:

```python
import buffer_store as bs; print(bs.__file__)   # the ONE that matters
```

then `cp` the fixed module into every other copy and re-grep for the new marker
in each.

## 5. VRAM contention blocks training — inference holds the card

The 4B frontier server pins **7.9 of 8 GB**. `schtasks /end` does NOT release it
(the python child keeps running).

```bash
nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader   # 7927 MiB
tasklist /FI "IMAGENAME eq python.exe" /FO CSV /NH   # find the ~1.2 GB one
taskkill /F /PID <pid>
nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader   # 143 MiB
```

Verify ~143 MiB used **before** launching training. Re-launch the frontier worker
afterwards (`schtasks /run /tn OpenAmerFrontier`).

**Kill by CommandLine match, never by "the big python".** Several python
processes coexist (gateway, session_to_brain, the trainer, the frontier). A
size-based or PID-guess kill can take out the training run. Match the target's
own command line and never touch the others:

```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*frontier_server*' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force; "killed PID $($_.ProcessId)" }
```

## 5.a Your own auto-restart watchdog will fight the training run

The most expensive self-inflicted failure of the session. A watchdog whose job
is "keep service X alive" re-launched the 4B frontier server **three times**
during a finetune, because from its point of view the worker was simply down —
and each restart stole VRAM back from the training run. Symptom: step time
degraded from ~8 s/it to ~27 s/it and the total run took 1232 s instead of the
expected ~500 s. Nothing crashed; it just silently ran 2.5× slower.

This is a general class: **an auto-restart watchdog and a long-running
resource-heavy job contend for the same resource, and the watchdog wins by
default because it only knows "is my service up?".** The watchdog needs an
explicit lock for the competing job.

```python
# in the watchdog: before restarting, check the competing job isn't active
def training_active():
    # primary: scheduled-task status (locale-dependent, and the SSH transport
    # can truncate it -> never trust it alone)
    # fallback: log mtime is fresh AND the completion marker is absent
    ...
    return (not done) and age_minutes < 20

def main():
    if probe() is not None:
        return 0                      # service up, nothing to do
    if training_active():
        print('{"ok": true, "action": "deferred: training holds the GPU"}')
        return 0                      # exit 0 — this is not an error
    restart()
```

Two details that matter: (a) deferring is a **success**, exit 0, otherwise the
cron goes red for the whole training window; (b) the scheduled-task status field
is locale-dependent ("Running" vs "Wird ausgeführt") *and* can be swallowed by
the transport — the dependable signal is the training log (completion marker
absent + mtime fresh).

Mitigation while the fix is in flight: `cronjob action=pause` the watchdog for
the duration of the run, then resume. Do that deliberately and note it, rather
than letting the two fight.

## 5.b Never assert resource state you have not just measured

The session opened with a confident "the RTX 3060 Ti is idle" that was **wrong**
— `nvidia-smi` showed 7917/8192 MiB used the whole time. The cause was the
inference worker this same session had just repaired 30 minutes earlier.

An idle/available resource claim is a measurement, not an inference. If it
hasn't been read in the current turn, it isn't known. This matters because the
whole plan (train now, VRAM is free) rests on it. Cost of the unmeasured claim:
the plan was built on a false premise and the first training attempt was starved.

Same rule for "the process is gone / the service is down / the file is old":
read it, then say it.

## 6. Full activation sequence

```bash
# 1. push the clean dataset
scp sft_openamer.jsonl damir@192.168.178.23:'C:/Users/damir/openamer-repo/scripts/training/sft_openamer.jsonl'
# 2. verify the remote line count
ssh ... 'find /c /v "" "...\scripts\training\sft_openamer.jsonl"'
# 3. free VRAM (section 5), pause any watchdog (5.a), then launch
ssh ... 'del /f /q C:\Users\damir\train.log & schtasks /run /tn OpenAmerTrain'
# 4. poll for the completion marker
ssh ... 'type C:\Users\damir\train.log'   # expect GPU_TRAINING_DONE then EXIT_CODE=0
```

Timing: 63 steps @ ~7–8 s/it ≈ 8–9 min for 3 epochs over 84 pairs at
batch=1/accum=4 (**without** VRAM contention — see 5.a; with contention it was
1232 s). `finetune_gpu.py` trains `Qwen/Qwen3.5-2B` (a 2B LoRA is comfortable on
8 GB); `lora_out_gpu/adapter` is the output.

Completion proof: `GPU_TRAINING_DONE` **and** `EXIT_CODE=0` in the log, plus a
fresh `LastWriteTime` on `lora_out_gpu/adapter/adapter_model.safetensors`.
Watch out — the adapter directory persists between runs, so an old timestamp
looks like success. Compare the timestamp against the run's start, don't just
check existence.

## 6.a tqdm progress bars look like a hung process over SSH

`finetune_gpu.py`'s progress bars write `\r`, not `\n`. Consequences that cost
real time to diagnose:

- `type train.log` and `Get-Content -Tail` show a **stale, frozen-looking** last
  line (the buffer hasn't flushed a newline). The run looks hung at "2/63".
- The GPU can read **0 %** at the sampling instant while the trainer is working,
  because a 1-second `nvidia-smi` sample can land between kernels.

Reliable liveness signals, in order: (1) **log file Size grows** between two
reads; (2) the training process's **CPU time increases** between two reads
(`Get-Process -Id <pid> | %{$_.CPU}`); (3) GPU utilization over several samples.
Normalise the log before reading it:

```powershell
$norm = (Get-Content $log -Raw -Encoding UTF8) -replace "`r", "`n"
$norm -split "`n" | Where-Object { $_.Trim() } | Select-Object -Last 8
```

## 6.b Verifying the hot-swap actually landed (three independent proofs)

The chain is only closed when the trained adapter is **live and measurably
better**. A swap that silently no-ops is the default failure mode, so prove it
three ways — none of which is "the POST returned OK":

**1. The server's own swap counter.** `tool_server.py` exposes `swaps` in
`/health`. Read it before and after:

```bash
curl -s http://127.0.0.1:8081/health          # {"status":"alive","tools":9,"swaps":6}
curl -s -X POST http://127.0.0.1:8081/admin/swap \
     -H "Content-Type: application/json" \
     -d '{"adapter":"C:/.../lora_out/adapter_gpu_20260911"}'
# → {"result": "OK: swap queued (#7) — applied on next request"}
curl -s http://127.0.0.1:8081/health          # swaps: 7  ⇒ loaded, not just queued
```

The swap is applied **on the next request**, so the counter only increments
after you actually send one. Always follow the POST with an inference call and
then re-read `/health` — a queued swap that never fires looks identical to a
successful one until you check.

**2. The adapter CONTENT differs, not just the path.** Fingerprint the first
tensor of old vs. new — same key names and shapes, different values proves the
GPU run produced new weights rather than copying the incumbent:

```python
from safetensors import safe_open
import hashlib
for p in [old_adapter, new_adapter]:
    with safe_open(p, framework="pt") as f:
        k = list(f.keys())[0]
        t = f.get_tensor(k)
        print(p, len(list(f.keys())), k, tuple(t.shape),
              hashlib.md5(t.float().numpy().tobytes()).hexdigest()[:12])
# → 48 tensors, same key/shape, fp 329688a4f0b3  vs  730a3b73379b  ⇒ genuinely new
```

**3. Before/after answer quality on the SAME prompt.** This is the honest
bottom line. Same question, incumbent vs. swapped:

```
before: "Wie viele Tage hat eine Woche?"  → "A"            (300 tokens burned, truncated)
after:  same prompt                        → "Eine Woche hat 7 Tage."
```

A one-word garbage answer that burned the entire token budget is the signature of
a broken/blank adapter; a correct short sentence is the signature of a working
one. Run 3–4 varied prompts (arithmetic, factual, open-ended) — a single lucky
answer is not evidence.

**LoRA-config compatibility is a precondition, not a detail.** All adapters must
share `r`, `lora_alpha`, and the exact `target_modules` set, or the swap crashes
with a size mismatch. Check before swapping:

```python
import json
for p in ["lora_out/adapter/adapter_config.json",
          "lora_out/adapter_rolling/adapter_config.json",
          "lora_out/adapter_gpu_20260911/adapter_config.json"]:
    d = json.load(open(p))
    print(p, d["r"], d["lora_alpha"], sorted(d["target_modules"]))
# all three: 16, 32, ['k_proj','o_proj','q_proj','v_proj']  — list ORDER may differ, the SET must not
```

Note `target_modules` order varies between files; compare `sorted()`, not the raw
list.

**Keep the incumbent until the swap is verified.** Unpack the new adapter under a
dated name (`adapter_gpu_20260911`) instead of overwriting `adapter/` — rollback
stays a one-line POST if the new one regresses.

## 6.c The batch and continual chains were DISCONNECTED — GPU work discarded

The deepest find of the session, and only visible *because* the swap counter was
watched after the fact. The `/health` `swaps` counter read **7** right after my
verified hot-swap, then **8** minutes later — although I had only requested one.
Something else had swapped the adapter out from under me.

Root cause, two halves that each looked reasonable alone:

1. `online_learning.py` hot-swaps every `SWAP_EVERY`(=6) mini-steps at
   `CYCLE_SECONDS`(=300 s) → **every ~30 minutes** it pushes
   `lora_out/adapter_rolling` into the live server.
2. `mini_step.py` seeded its training **only from `ROLLING`, else fresh from
   `BASE`** — never from a batch GPU adapter.

Combined: a 20-minute GPU run over the 84 curated distilled pairs produced a
strictly better adapter, it went live, and the next rolling swap replaced it with
a chain that had never seen those examples. **The GPU work was live for ~19
minutes and then silently discarded. Batch training was structurally unable to
survive one swap cycle.** Both loops ran, both reported success, and the product
of the expensive one evaporated.

The structural lesson: when a system has a *batch* path and a *continual* path
writing the same artifact, ask **explicitly** what the continual path starts
from. "It resumes its own last state" means every batch result is an orphan.

### Fix: seed from the best UNABSORBED adapter

```python
def pick_seed(lora_dir=None, rolling=None, mark=None):
    batches = sorted(lora_dir.glob("adapter_gpu*"), key=_adapter_mtime, reverse=True)
    absorbed = mark.read_text().strip() if mark.exists() else ""
    for d in batches:                       # unabsorbed batch outranks rolling
        if _adapter_mtime(d) and d.name != absorbed:
            return d
    if _adapter_mtime(rolling):
        return rolling
    return next((d for d in batches if _adapter_mtime(d)), None)
```

**Plain "newest file wins" is also wrong** — once the rolling chain writes, *it*
is the newest file and would hide the batch adapter forever. The `.rolling_seed`
marker is load-bearing: it records what the chain last absorbed, so a *second*
GPU run later is still picked up (`test_a_newer_batch_after_absorption_is_picked_up`).

Result accumulates instead of oscillating: `rolling = batch + subsequent mini-steps`.

Live proof:

```
$ mini_step.py
{"ok": true, "examples": 2, "avg_loss": 3.046, "fresh_adapter": false}
SEED_MARK=adapter_gpu_20260911
```

`fresh_adapter: false` is the whole evidence — it proves the chain started from a
trained adapter rather than from `BASE`. A *high* `avg_loss` (~3.0) on that first
step is expected and correct: 2 fresh examples on-saddle a stale adapter, and the
point is that it is *continuing*, not restarting.

### Diagnosing this class: watch the counter you did not move

The swap counter incremented without a request from me — that anomaly is what
exposed the whole bug. Generalise it: **when a service exposes a monotonic
counter, read it before and after your own action. A delta larger than your own
operations means another writer is active.** Same trick applies to buffer line
counts, log line counts, and job `run_count`. Silent overwrites are invisible
unless something counts.

## 7. Pitfalls

- `ssh` to Windows kills detached processes when the session ends — use
  `schtasks`, never `start /b`.
- The `run_gpu_train.bat` wrapper hardcodes a uv-python path; on THIS box the
  interpreter with CUDA torch is
  `C:\Users\damir\AppData\Local\Programs\Python\Python311\python.exe`
  (torch 2.5.1+cu121, cuda True). The uv python used by the .bat has torch too,
  but verify with a real `torch.cuda.is_available()` before trusting it.
- `finetune_gpu.py` reads `sft_openamer.jsonl` from **its own directory** — the
  scp target must be next to the script, not merely somewhere in the repo.
- PowerShell one-liners nested inside `ssh '...'` break on quote escaping
  (`unexpected EOF while looking for matching`). Write the script to a `.ps1`
  with `write_file`, `scp` it over, run it with `-ExecutionPolicy Bypass -File`.

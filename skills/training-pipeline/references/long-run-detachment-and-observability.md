# A retrain that outlives the agent, and that you can watch

Session detail, 2026-10-31. Measured numbers only.

## 1. The run that vanished

`auto_retrain.py` was started from a terminal session (background tool). Guards were green:

```
MARKER .last_retrain: 505.7 h alt        → MIN_INTERVAL_H=24 erfüllt
BRAIN: 7669 Zeilen, neuer als Marker     → MIN_NEW_PAIRS=10 erfüllt
RAM frei: 10.8 GB                        → Guard 8 GB erfüllt
```

Distillation produced 417 pairs, the trainer loaded Qwen3.5-2B in fp32 (8.2–10.2 GB RSS,
~5.8–7.4 cores), and then — during a host/agent restart — the process disappeared:

```
Trainer-Prozess:        beendet
lora_out/adapter:       10.10 04:43   (unverändert → nichts gespeichert)
.last_retrain:          10.10 04:43   (nicht vorgerückt → auto_retrain war ehrlich)
```

`auto_retrain` behaved correctly: the 24 h marker only advances after the artifact
changed. The loss was the training itself, not a broken guard.

## 2. Detached launcher

`scripts/training/start_retrain_detached.py`:

```python
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000

kwargs = {"stdout": log, "stderr": subprocess.STDOUT, "cwd": str(TRAINING),
          "env": env, "close_fds": True}
kwargs["creationflags"] = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
proc = subprocess.Popen([python_that_owns_torch, str(TRAINING / "auto_retrain.py")], **kwargs)
PIDFILE.write_text(str(proc.pid))
```

- `--status` verifies the pid with `tasklist /FI "PID eq <pid>"`, so a stale pid file never
  blocks the next night.
- `tasklist` must be decoded with `encoding="utf-8", errors="replace"`: its output carries
  console-codepage bytes (0x81 on a German Windows) that raise `UnicodeDecodeError`
  otherwise — inside pytest that surfaced as a `PytestUnhandledThreadExceptionWarning`
  turned into a failure.
- The interpreter must be the training venv (`<home>/venv/Scripts/python.exe`), not the
  agent venv: `openamer-agent/venv` has no torch.

### Proving detachment without a 3-hour job

Parent spawns a detached child, writes nothing, exits; the child sleeps 6 s and writes a
result file. Observed:

```
parent gestartet kind 21228
Elternprozess beendet.
nach 7s: child finished after parent died
```

## 3. Observability

`finetune_cpu.py` attaches a callback; without it stdout stayed empty for hours because
tqdm carriage-returns are buffered when stdout is not a TTY.

```python
class _ProgressLog(TrainerCallback):
    def on_log(self, args, state, control, logs=None, **kwargs):
        logs = logs or {}
        PROGRESS_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(PROGRESS_LOG, "a", encoding="utf-8") as fh:
            fh.write(f"{time.strftime('%H:%M:%S')} step={state.global_step}/{state.max_steps} "
                     f"({100.0*state.global_step/max(state.max_steps,1):.1f}%) "
                     f"epoch={logs.get('epoch')} loss={logs.get('loss')}\n")
            fh.flush()
```

Live sample while training:

```
17:59:04 step=13/315 (4.1%) epoch=0.125 loss=2.3839
18:04:25 step=21/315 (6.7%) epoch=0.201 loss=1.7256
18:05:22 step=22/315 (7.0%) epoch=0.211 loss=2.4844
```

`logging_steps=1` is part of the fix: at 5 the file stays silent for 20+ minutes on a slow
CPU run.

## 4. The scheduler was off as well

```
mini-openamer-retrain  id=df7a5df9f745  schedule="0 4 * * *"
  enabled=false  state=paused  paused_at=2026-10-14T10:22:36  paused_reason=null
  last_run_at=2026-10-13T05:08  last_status=ok  repeat.completed=39
```

`paused_reason: null` means it was paused programmatically, not by the curator and not with
a human reason. `openamer cron resume df7a5df9f745` → `enabled=True, state=scheduled,
next=2026-11-01T04:00`. Then re-point the prompt at the detached launcher so the 04:00 run
survives a gateway restart.

## 5. Test surface

```
pytest scripts/tests/            → exit 0 (≈300 tests)
pytest scripts/tests/test_retrain_detached.py  → 5 passed
pytest scripts/tests/test_finetune_progress.py → 3 passed
npm run test                     → research suite 91 passed, 0 failed
```

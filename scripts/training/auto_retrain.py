#!/usr/bin/env python3
"""Auto-retrain pipeline (nightly cron): if new brain data -> redistill -> retrain -> hot-swap adapter.

Watchdog-style: stays silent (exit 0) unless it actually retrained, or an error occurs.
Guards: >= 10 NEW pairs, RAM check, min 24h between runs (marker file).
"""
import datetime
import json
import os
import pathlib
import shutil
import subprocess
import sys
from pathlib import Path

HOME = Path(
    os.environ.get("OPENAMER_HOME", str(Path.home() / "AppData" / "Local" / "openamer-laptop"))
)
T = HOME / "scripts" / "training"
# brain_collect writes HERE, not to ~/.openamer/a2a — that was a stale Sep-24
# copy, so `new = brain_ct - last_ct` was always <= 0 and the nightly retrain
# stayed silent forever: the 2B model never learned from new sessions.
BRAIN = HOME / "a2a" / "openamer-brain.jsonl"
MARKER = T / ".last_retrain"
MIN_INTERVAL_H = 24
MIN_NEW_PAIRS = 10

def _train_python():
    """Return the interpreter that owns the training deps (torch/transformers/peft).

    The cron wrapper runs under the AGENT venv (openamer-agent/venv), whose
    huggingface-hub (1.2.3) is too old for its transformers build — training
    children must use the dedicated training venv (hub 1.30.0), which lives at
    ``$OPENAMER_HOME/venv`` next to the scripts tree.
    """
    env_py = os.environ.get("OPENAMER_TRAIN_PYTHON")
    if env_py and Path(env_py).exists():
        return env_py
    home = Path(os.environ.get("OPENAMER_HOME", str(Path.home() / "AppData" / "Local" / "openamer-laptop")))
    for cand in (home / "venv" / "Scripts" / "python.exe",
                 T.parent / "venv" / "Scripts" / "python.exe",
                 home / "openamer-agent" / "venv" / "Scripts" / "python.exe"):
        if cand.exists():
            return str(cand)
    return sys.executable

PY = _train_python()


def sh(cmd, timeout=7200):
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)  # agent-shell PYTHONPATH shadows the training venv
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace", env=env)
    if r.returncode != 0:
        raise RuntimeError(f"cmd failed: {cmd}\n{r.stdout[-500:]}\n{r.stderr[-500:]}")
    return r.stdout

def main():
    if MARKER.exists():
        age_h = (datetime.datetime.now() - datetime.datetime.fromtimestamp(MARKER.stat().st_mtime)).total_seconds() / 3600
        if age_h < MIN_INTERVAL_H:
            return  # silent: too soon

    # New data since the last retrain. brain_collect REGENERATES the file (it
    # does not append), so counts are not monotonic and `count - last_count`
    # goes negative whenever the dataset shrinks. Compare against the file's
    # own mtime vs. the last-retrain marker instead: only train on data that is
    # genuinely newer than the last run, and require a real minimum size.
    state = T / ".brain_count"
    if not BRAIN.exists():
        return  # silent: no dataset yet
    last_retrain_ts = MARKER.stat().st_mtime if MARKER.exists() else 0.0
    if BRAIN.stat().st_mtime <= last_retrain_ts:
        return  # silent: no freshly collected data since the last retrain
    with open(BRAIN, encoding="utf-8") as fh:
        brain_ct = sum(1 for _ in fh)
    if brain_ct < MIN_NEW_PAIRS:
        return  # silent: dataset too small to train on
    new = brain_ct  # informational: records available in the fresh dataset

    # RAM guard: need ~8GB free of 22GB
    import ctypes
    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    m = MEMORYSTATUSEX(); m.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    if m.ullAvailPhys < 8 * 1024**3:
        print(f"SKIP: only {m.ullAvailPhys//1024**3}GB RAM free (need 8GB)")
        sys.exit(1)

    print(f"RETRAIN: {new} new brain records ({brain_ct} total)")
    out = sh([PY, str(T / "distill_sft.py")], timeout=600)
    print(out.strip())
    with open(T / "sft_openamer.jsonl", encoding="utf-8") as fh:
        pairs = sum(1 for _ in fh)
    if pairs < 20:
        print(f"ABORT: only {pairs} distilled pairs")
        sys.exit(1)

    # snapshot the CURRENT adapter BEFORE training overwrites it, so a bad
    # retrain stays rollback-able. (The old code backed up AFTER finetune, i.e.
    # it copied the freshly-trained adapter over the backup — no rollback.)
    adapter = T / "lora_out" / "adapter"
    backup = T / "adapter_backup"
    if backup.exists():
        shutil.rmtree(backup)
    if adapter.exists():
        shutil.copytree(adapter, backup)

    print(f"[auto_retrain] using train interpreter: {PY}", flush=True)
    out = sh([PY, str(T / "finetune_cpu.py")], timeout=7200)
    print(out.strip()[-800:])

    # hot-swap: tell the LIVE server (dolphin architecture) to load the new
    # adapter at runtime — zero downtime, no restart.
    state.write_text(str(brain_ct))
    MARKER.write_text(datetime.datetime.now().isoformat())

    # signal the LIVE server to hot-swap (best-effort: if it's down, the next
    # manual/cron start of serve_live.py picks up the new adapter anyway)
    try:
        import urllib.request
        req = urllib.request.Request(
            "http://localhost:8081/admin/swap",
            data=json.dumps({"adapter": str(adapter)}).encode(),
            headers={"Content-Type": "application/json"})
        resp = json.load(urllib.request.urlopen(req, timeout=120))
        print("HOT_SWAPPED:", resp.get("result"))
    except Exception as e:
        print(f"live server not reachable ({e}) — new adapter activates on next start")

    print("RETRAIN_OK adapter updated")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Auto-retrain pipeline (nightly cron): if new brain data -> redistill -> retrain -> hot-swap adapter.

Watchdog-style: stays silent (exit 0) unless it actually retrained, or an error occurs.
Guards: >= 10 NEW pairs, RAM check, min 24h between runs (marker file).
"""
import json, os, subprocess, sys, datetime, pathlib, shutil

T = pathlib.Path(r"C:/Users/damir/AppData/Local/openamer-laptop/scripts/training")
BRAIN = pathlib.Path(r"C:/Users/damir/.openamer/a2a/openamer-brain.jsonl")
MARKER = T / ".last_retrain"
MIN_INTERVAL_H = 24
MIN_NEW_PAIRS = 10

def sh(cmd, timeout=7200):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"cmd failed: {cmd}\n{r.stdout[-500:]}\n{r.stderr[-500:]}")
    return r.stdout

def main():
    if MARKER.exists():
        age_h = (datetime.datetime.now() - datetime.datetime.fromtimestamp(MARKER.stat().st_mtime)).total_seconds() / 3600
        if age_h < MIN_INTERVAL_H:
            return  # silent: too soon

    # count new brain records since marker
    brain_ct = sum(1 for _ in open(BRAIN, encoding="utf-8"))
    last_ct = 0
    state = T / ".brain_count"
    if state.exists():
        last_ct = int(state.read_text().strip() or 0)
    new = brain_ct - last_ct
    if new < MIN_NEW_PAIRS:
        return  # silent: not enough new data

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
    out = sh([sys.executable, str(T / "distill_sft.py")], timeout=600)
    print(out.strip())
    pairs = sum(1 for _ in open(T / "sft_openamer.jsonl", encoding="utf-8"))
    if pairs < 20:
        print(f"ABORT: only {pairs} distilled pairs")
        sys.exit(1)

    out = sh([sys.executable, str(T / "finetune_cpu.py")], timeout=7200)
    print(out.strip()[-800:])

    # hot-swap: backup old adapter, move new one in, then tell the LIVE server
    # (dolphin architecture) to load it at runtime — zero downtime, no restart.
    adapter = T / "lora_out" / "adapter"
    backup = T / "adapter_backup"
    if backup.exists():
        shutil.rmtree(backup)
    if adapter.exists():
        shutil.copytree(adapter, backup)
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

#!/usr/bin/env python3
"""Online Learning Loop — sleepless learning for OpenAmer.

Replaces the nightly 35-min batch with continuous micro-updates:

  - Experience buffer: collects (prompt, answer) pairs continuously from
    the brain daemon trajectories (new records since last marker).
  - Every N minutes a background thread trains 1-2 mini-steps on the
    newest examples (LoRA, CPU, ~5s per step) and saves a rolling adapter.
  - The LIVE server keeps running; every M mini-steps the rolling adapter
    is hot-swapped into the live process via POST /admin/swap.

The night-batch (auto_retrain.py) stays as a slower "deep consolidation"
pass, but the system no longer DEPENDS on it for learning.

CLI:
  python online_learning.py --loop          # continuous mode (daemon)
  python online_learning.py --step-once     # single mini-step (test)
  python online_learning.py --stats
"""
import os
import json, os, sys, time, threading, subprocess, argparse, datetime, pathlib
from pathlib import Path

_HOME = pathlib.Path(os.environ.get(
    "OPENAMER_HOME",
    pathlib.Path.home() / "AppData" / "Local" / "openamer-laptop"
))
T = _HOME / "scripts" / "training"
BRAIN = _HOME / "a2a" / "openamer-brain.jsonl"
BUFFER = T / "online_buffer.jsonl"
MARKER = T / ".online_marker"
LIVE_SWAP_URL = "http://localhost:8081/admin/swap"
LIVE_SWAP_TIMEOUT = 120
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import buffer_store  # single source of truth for buffer writes + cap

MINI_STEP_SCRIPT = T / "mini_step.py"          # trains 1-2 steps on a few examples
STEPS_PER_CYCLE = 3                             # examples per mini-step
CYCLE_SECONDS = 300  # every 5 min
SWAP_EVERY = 6                                  # hot-swap after 8 mini-steps (~2h)

def _brain_count():
    try:
        return sum(1 for _ in open(BRAIN, encoding="utf-8"))
    except FileNotFoundError:
        return 0

def _marker():
    try:
        return int(MARKER.read_text().strip())
    except Exception:
        return 0

def collect_new(max_new=50):
    """Pull newest brain records into the experience buffer (dedup by marker)."""
    last = _marker()
    total = _brain_count()
    if total <= last:
        return 0
    new = 0
    for i, line in enumerate(open(BRAIN, encoding="utf-8")):
        if i < last:
            continue
        if new >= max_new:
            break
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        # extract one (user, assistant) pair per record (first clean pair)
        lu = None
        for m in d.get("messages", []):
            r = m.get("role")
            if r == "user":
                lu = (m.get("content") or "").strip()
            elif r == "assistant" and lu:
                ac = (m.get("content") or "").strip()
                ok = (30 <= len(ac) <= 4000 and 3 <= len(lu) <= 4000
                      and not lu.startswith("[IMPORTANT:")
                      and not lu.startswith("[System note:"))
                if ok:
                    # write through the store: cap enforced on EVERY append
                    buffer_store.append(lu, ac, buffer=str(BUFFER))
                    new += 1
                lu = None
                break
    MARKER.write_text(str(min(total, last + max_new)))
    return new


def mini_step():
    """Run ONE mini training step on the newest buffer examples (isolated proc)."""
    if not MINI_STEP_SCRIPT.exists():
        return {"error": f"mini_step.py missing at {MINI_STEP_SCRIPT}"}
    r = subprocess.run([sys.executable, str(MINI_STEP_SCRIPT)],
                       capture_output=True, text=True, timeout=600,
                       encoding="utf-8", errors="replace")
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        return {"raw": (r.stdout or r.stderr)[-300:], "rc": r.returncode}

def hot_swap():
    """Tell the LIVE server to reload the rolling adapter. Best-effort."""
    try:
        import urllib.request
        rolling = str(T / "lora_out" / "adapter_rolling")
        req = urllib.request.Request(LIVE_SWAP_URL,
            data=json.dumps({"adapter": rolling}).encode(),
            headers={"Content-Type": "application/json"})
        resp = json.load(urllib.request.urlopen(req, timeout=LIVE_SWAP_TIMEOUT))
        return resp.get("result", "no-result")
    except Exception as e:
        return f"live-not-reachable ({str(e)[:80]}) — rolling adapter activates next start"

def loop():
    print(f"[online-learning] loop started: cycle={CYCLE_SECONDS}s, "
          f"steps/cycle={STEPS_PER_CYCLE}, swap-every={SWAP_EVERY}, "
          f"replay-mode=on", flush=True)
    steps_since_swap = 0
    while True:
        try:
            new = collect_new()
            if new:
                print(f"[online-learning] +{new} new buffer examples", flush=True)
            else:
                # REPLAY MODE: no new data — re-inject 2 random old episodes so
                # the 24/7 loop never starves. Like human memory rehearsal:
                # repeating old knowledge strengthens it (no downtime needed).
                try:
                    # cap the buffer: training on unbounded duplicates degrades
                    # the loss (gradient noise). Keep a fixed window instead.
                    n_before = buffer_store.enforce_cap(str(BUFFER))
                    if n_before == buffer_store.MAX_BUF:
                        print(f"[online-learning] buffer trimmed to {buffer_store.MAX_BUF}",
                              flush=True)
                    if n_before >= 4:
                        import random as _r
                        buf_lines = open(BUFFER, encoding="utf-8").readlines()
                        picks = _r.sample(buf_lines, 2)
                        for pk in picks:
                            try:
                                rec = json.loads(pk)
                                buffer_store.append(rec.get("u", ""), rec.get("a", ""),
                                                    buffer=str(BUFFER))
                            except json.JSONDecodeError:
                                continue
                        print(f"[online-learning] replay: +2 old episodes re-injected "
                              f"(buffer={buffer_store.count(str(BUFFER))})", flush=True)
                except Exception as e:
                    print(f"[online-learning] replay skip: {e}", flush=True)
            for i in range(STEPS_PER_CYCLE):
                res = mini_step()
                steps_since_swap += 1
                print(f"[online-learning] mini-step {i+1}/{STEPS_PER_CYCLE}: {res}", flush=True)
            # META-LEARNING: measure and adapt how we learn (Stage 4)
            try:
                import meta_learn
                meta_learn.meta_cycle()
            except Exception as me:
                print(f"[online-learning] meta-learn skip: {me}", flush=True)
            # cross-domain transfer: skeletonize 1 episode per cycle (best-effort)
            try:
                r = subprocess.run([sys.executable, str(T / "analogy_engine.py"), "extract-batch"],
                    capture_output=True, text=True, timeout=600,
                    encoding="utf-8", errors="replace")
                print(f"[online-learning] analogy extraction: {r.stdout.strip()[-60:]}", flush=True)
            except Exception as e:
                print(f"[online-learning] analogy skip: {e}", flush=True)
            # world-model auto-feed: extract cause->effect from recent dreams
            try:
                import world_model
                dreams_file = os.path.join(os.environ.get("OPENAMER_HOME", str(Path.home() / "AppData" / "Local" / "openamer")), "dreams.json")
                if os.path.exists(dreams_file):
                    dreams = json.load(open(dreams_file, encoding="utf-8"))
                    known_causes = {e.get("cause", "")[:100] for e in world_model._load()}
                    added = 0
                    for dream in dreams:
                        for ins in dream.get("insights", []):
                            cause = f"{ins.get('motif','')} error occurred"
                            effect = "agent needs to fix root cause to prevent recurrence"
                            if cause[:100] not in known_causes and added < 3:
                                world_model.observe(cause, effect)
                                known_causes.add(cause[:100])
                                added += 1
                    if added:
                        print(f"[online-learning] world-model: +{added} new edges", flush=True)
            except Exception as e:
                print(f"[online-learning] world-model skip: {e}", flush=True)
            if steps_since_swap >= SWAP_EVERY:
                msg = hot_swap()
                steps_since_swap = 0
                print(f"[online-learning] hot-swap: {msg}", flush=True)
        except Exception as e:
            print(f"[online-learning] cycle error (continuing): {e}", flush=True)
        time.sleep(CYCLE_SECONDS)

def stats():
    buf = sum(1 for _ in open(BUFFER, encoding="utf-8")) if BUFFER.exists() else 0
    return {"buffer_examples": buf, "brain_records": _brain_count(),
            "marker": _marker(), "pending": max(0, _brain_count() - _marker())}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--step-once", action="store_true")
    ap.add_argument("--collect", action="store_true")
    ap.add_argument("--stats", action="store_true")
    a = ap.parse_args()
    if a.loop:
        loop()
    elif a.step_once:
        print(json.dumps(mini_step()))
    elif a.collect:
        print(json.dumps({"collected": collect_new()}))
    else:
        print(json.dumps(stats(), indent=1))

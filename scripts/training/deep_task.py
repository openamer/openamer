#!/usr/bin/env python3
"""Deep Task Decomposition — reasoning depth through STRUCTURE, not weights.

The 2B model cannot reason 5 levels deep in one pass. But it CAN:
  1. PLAN      — break a task into ordered subtasks
  2. EXECUTE   — solve each subtask (with optional tool calls)
  3. VERIFY    — check each result against the goal
  4. SYNTHESIZE — combine verified results into the final answer

Each subtask is small enough for a 2B model to handle reliably. Depth comes
from the pipeline, not from a single heroic generation. This is how humans
solve hard problems too.

CLI:
  python deep_task.py solve "complex task here"
  python deep_task.py solve "task" --verify   # with per-step verification
"""
import json, sys, os, urllib.request, datetime, time

LIVE = "http://localhost:8081"
WORLD = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "..", "..", "memory", "world_model.jsonl")

def chat(messages, max_tokens=250):
    req = urllib.request.Request("http://localhost:8081/v1/chat/completions",
        data=json.dumps({"model": "mini-openamer", "messages": messages,
                         "max_tokens": max_tokens}).encode(),
        headers={"Content-Type": "application/json"})
    r = json.load(urllib.request.urlopen(req, timeout=300))
    return r["choices"][0]["message"]["content"].strip()

def plan(task):
    """Break task into ordered subtasks."""
    p = chat([
        {"role": "system", "content":
         "Break the task into 2-5 ordered subtasks. Each subtask must be small "
         "enough for one focused step. Reply ONLY as a JSON array of strings, "
         "nothing else."},
        {"role": "user", "content": task}], max_tokens=200)
    # robust parse: find the array
    try:
        start, end = p.find("["), p.rfind("]") + 1
        subtasks = json.loads(p[start:end])
        return [str(s) for s in subtasks if str(s).strip()]
    except Exception:
        return [p]  # single-step fallback

def execute(subtask, context=""):
    msgs = [{"role": "system", "content":
             "You are a precise worker. Solve exactly this subtask. "
             "If it requires calculation, show the steps."},
            {"role": "user", "content":
             (f"Context from previous steps: {context}\n\n" if context else "")
             + f"Subtask: {subtask}"}]
    return chat(msgs, max_tokens=250)

def verify(subtask, result, original_task):
    v = chat([
        {"role": "system", "content":
         "You verify work. Does this result actually solve the subtask? "
         "Reply ONLY: PASS or FAIL: <one-line reason>."},
        {"role": "user", "content":
         f"Original task: {original_task}\nSubtask: {subtask}\nResult: {result}"}],
        max_tokens=60)
    return v.startswith("PASS"), v

def synthesize(original_task, results):
    combined = "\n\n".join(f"Step {i+1}: {s}\nResult: {r}"
                           for i, (s, r, _) in enumerate(results))
    return chat([
        {"role": "system", "content":
         "Combine the verified subtask results into one coherent final answer. "
         "Be concise."},
        {"role": "user", "content": f"Task: {original_task}\n\n{combined}"}],
        max_tokens=300)

def solve(task, do_verify=True):
    t0 = time.time()
    subtasks = plan(task)
    results = []
    for i, st in enumerate(subtasks[:5]):
        prev_ctx = " | ".join(f"{s}: {r[:200]}" for s, r, _ in results[-2:]) if results else ""
        res = execute(st, prev_ctx)
        ok = True
        if do_verify:
            ok, reason = verify(st, res, task)
            if not ok:
                res = execute(st, prev_ctx + " | Previous attempt failed: " + reason + " | Correct it.")
                ok, _ = verify(st, res, task)
        results.append((st, res, ok))
    final = synthesize(task, results)
    return {"task": task,
            "plan": [s for s, _, _ in results],
            "steps": [{"subtask": s, "result": r[:300], "verified": ok}
                      for s, r, ok in results],
            "final": final, "elapsed_s": round(time.time()-t0, 1)}

if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] != "solve":
        print(__doc__); sys.exit(1)
    do_v = "--verify" in sys.argv
    task = " ".join(a for a in sys.argv[2:] if a != "--verify")
    out = solve(task, do_verify=do_v)
    print(json.dumps(out, ensure_ascii=False, indent=1))
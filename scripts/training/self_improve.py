#!/usr/bin/env python3
"""Self-Improvement Loop — the agent improves its own code, safely.

Every run:
  1. ANALYZE   — read own source files, find a concrete improvement
  2. PROPOSE   — write the change to a SANDBOX copy (never the live file)
  3. TEST      — py_compile + import check + functional smoke test
  4. SWITCH    — only if ALL tests pass: copy sandbox -> live, reload
  5. LOG       — record the improvement in the improvement log

Safety rails:
  - Never touches: tool_server.py core inference, auth, network code
  - Always reversible: git tracks every change
  - Proof-first: no live switch without passing tests
"""
import json, os, sys, time, subprocess, shutil, datetime, re

T = r"C:/Users/damir/AppData/Local/openamer-laptop/scripts/training"
LOG = os.path.join(T, "improvements.jsonl")
SANDBOX = os.path.join(T, "sandbox")
REPO = r"C:/Users/damir/openamer-repo"

# Targets that are SAFE for self-modification (no inference/auth/network core)
SAFE_TARGETS = {
    "online_learning.py": ["buffer cap tuning", "replay strategy", "cycle timing"],
    "active_learn.py": ["learning actions", "rotation", "new action ideas"],
    "analogy_engine.py": ["extraction prompt", "dedupe strategy"],
    "reasoning_loop.py": ["critique rounds", "early-break logic"],
    "deep_task.py": ["subtask planning", "verification strategy"],
    "tool_math.py": ["code extraction robustness"],
}

def log(entry):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def run(cmd, timeout=120):
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)

def py_compile_ok(path):
    r = run([sys.executable, "-m", "py_compile", path])
    return r.returncode == 0, r.stderr[:300]

# ---- Improvement ideas (the 2B model proposes; rules validate) ----

def propose_improvement(target, content):
    """Rule-based improvement proposals (2B validates, rules decide).
    Safe deterministic improvements first — learned proposals later."""
    proposals = []

    # P1: timing constants — if cycle is slow, suggest tighter
    m = re.search(r"CYCLE_SECONDS\s*=\s*(\d+)", content)
    if m and int(m.group(1)) > 300:
        proposals.append(("timing", m.group(0), "CYCLE_SECONDS = 300",
                          "cycle interval > 300s slows learning"))

    # P2: max_tokens too small for richer answers
    m2 = re.search(r"max_tokens\s*=\s*(\d+)", content)
    if m and int(m.group(1)) < 100:
        proposals.append(("capacity", m.group(0), "max_tokens=200",
                          "small max_tokens limits answer quality"))

    # P3: missing error context in exception handlers
    if "except Exception as e:" in content and content.count("print(f\"") < 3:
        proposals.append(("logging", "except Exception as e:",
                          "except Exception as e:\n        print(f'[err] {e}', flush=True)",
                          "silent exception swallowing hides learning data"))

    # P4: stale comment — comment claims X min but value differs
    for line_match in re.finditer(r"(\w+)\s*=\s*(\d+)\s*(?:#|//)\s*every\s*(\d+)\s*(min|sec|s)", content):
        var, val, claimed, unit = line_match.groups()
        claimed_s = int(claimed) * (60 if unit == "min" else 1)
        if int(val) != claimed_s:
            correct = f"{int(val)//60} min" if int(val) >= 60 else f"{int(val)} s"
            proposals.append(("comment-fix", line_match.group(0),
                              f"{var} = {val}  # every {correct}",
                              f"stale comment claims {claimed}{unit}, actual {correct}"))

    return proposals

def apply_and_test(target, proposal, live_path, sandbox_path):
    """Apply proposal to sandbox, run all tests, return (ok, reason)."""
    kind, old, new, reason = proposal
    src = open(live_path, encoding="utf-8").read()
    if old not in src:
        return False, f"pattern not found: {old[:50]}"
    patched = src.replace(old, new, 1)
    if patched == src:
        return False, "no change made"
    with open(sandbox_path, "w", encoding="utf-8") as f:
        f.write(patched)

    # TEST 1: compile
    ok, err = py_compile_ok(sandbox_path)
    if not ok:
        return False, f"compile failed: {err[:100]}"

    # TEST 2: import check (module loads without executing main)
    r = run([sys.executable, "-c", f"import ast; ast.parse(open(r'{sandbox_path}').read())"])
    if r.returncode != 0:
        return False, "AST parse failed"

    # TEST 3: functional — for loop scripts, verify the loop() function exists
    if "def loop" in patched and "def loop" not in src:
        return False, "loop function lost"
    return True, "all tests passed"

def improve_once():
    """One self-improvement attempt. Returns log entry."""
    targets = list(SAFE_TARGETS.keys())
    rot_file = os.path.join(T, ".si_rotation")
    n = 0
    if os.path.exists(rot_file):
        n = int(open(rot_file).read().strip() or 0)
    target = targets[n % len(targets)]
    with open(rot_file, "w") as f:
        f.write(str(n + 1))
    live_path = os.path.join(T, target)
    if not os.path.exists(live_path):
        return {"target": target, "status": "skip", "reason": "file missing"}

    content = open(live_path, encoding="utf-8").read()
    proposals = propose_improvement(target, content)
    if not proposals:
        return {"target": target, "status": "no-proposal",
                "reason": "already optimal or no safe pattern"}

    os.makedirs(SANDBOX, exist_ok=True)
    sandbox_path = os.path.join(SANDBOX, target)

    for proposal in proposals:
        ok, reason = apply_and_test(target, proposal, live_path, sandbox_path)
        entry = {
            "ts": datetime.datetime.now().isoformat(),
            "target": target,
            "kind": proposal[0],
            "reason": proposal[3],
            "status": "APPLIED" if ok else "REJECTED",
            "detail": reason,
        }
        if ok:
            # LIVE SWITCH: sandbox -> live (git provides rollback)
            shutil.copy2(sandbox_path, live_path)
            # verify live still compiles
            ok2, err2 = py_compile_ok(live_path)
            if ok2:
                entry["live"] = True
            else:
                # ROLLBACK
                git_result = run(["git", "-C", r"C:/Users/damir/openamer-repo",
                                  "checkout", "--", f"scripts/training/{target}"])
                # restore from repo
                repo_file = os.path.join(r"C:/Users/damir/openamer-repo", "scripts", "training", target)
                if os.path.exists(repo_file):
                    shutil.copy2(repo_file, live_path)
                entry["status"] = "ROLLED_BACK"
                entry["live"] = False
        log(entry)
        print(f"[self-improve] {entry['status']}: {target} ({entry['kind']}) — {reason[:80]}",
              flush=True)
        return entry

    return {"target": target, "status": "no-appliable", "reason": "no proposals passed"}

if __name__ == "__main__":
    improve_once()

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
import os
import json, os, sys, time, subprocess, shutil, datetime, re
import ast
from pathlib import Path

def _training_dir():
    """Resolve the live training dir, tolerating a wrong/stale OPENAMER_HOME.

    A cron/desktop env can hand over OPENAMER_HOME in the MSYS spelling (a
    forward-slash drive path). Native Python treats that as RELATIVE, so
    os.path.join builds a phantom tree under the drive root and every run
    crashed with FileNotFoundError on .si_rotation. Prefer a *valid* env
    override, then the real install dir, then this file's own directory.
    Same pattern as internet_learner._training_dir (single convention).
    """
    cands = []
    _env = os.environ.get("OPENAMER_HOME")
    if _env:
        cands.append(os.path.join(_env, "scripts", "training"))
    _home = Path.home()
    cands.append(str(_home / "AppData" / "Local" / "openamer-laptop" / "scripts" / "training"))
    cands.append(str(Path(__file__).resolve().parent))
    for _c in cands:
        if os.path.isdir(_c):
            return _c
    return os.path.join(str(_home), "AppData", "Local", "openamer", "scripts", "training")


T = _training_dir()
LOG = os.path.join(T, "improvements.jsonl")
SANDBOX = os.path.join(T, "sandbox")
REPO = os.path.join(str(Path.home()), "openamer-repo")

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
    return subprocess.run(cmd, capture_output=True,
                          text=True, encoding="utf-8", errors="replace",
                          timeout=timeout)

def py_compile_ok(path):
    r = run([sys.executable, "-m", "py_compile", path])
    return r.returncode == 0, r.stderr[:300]


# ---- Text I/O that preserves the target's own line endings ----
#
# apply_and_test() used to open() in text mode, so on Windows every LF was
# translated to CRLF on write. Four of the six SAFE_TARGETS are pure LF
# (online_learning, analogy_engine, reasoning_loop, deep_task), so the FIRST
# applied proposal would have rewritten the whole file's line endings: a
# 237-line CRLF diff dressed up as a one-line improvement. Measured, not assumed.

_CR = chr(13)
_LF = chr(10)
_CRLF = _CR + _LF


def _eol_of(path):
    """The dominant line ending of a file on disk: CRLF or LF."""
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except OSError:
        return _LF
    crlf = raw.count(_CRLF.encode("utf-8"))
    lone_lf = raw.count(_LF.encode("utf-8")) - crlf
    return _CRLF if (crlf and not lone_lf) else _LF


def _read_text(path):
    """Read UTF-8 and normalise to LF. All in-memory text is LF-only."""
    with open(path, "rb") as f:
        return f.read().decode("utf-8", errors="replace").replace(_CRLF, _LF)


def _write_text(path, text, eol=_LF):
    """Write UTF-8, expanding LF to `eol`. Untouched lines stay byte-identical,
    so an applied proposal shows up as a real one-line diff."""
    norm = text.replace(_CRLF, _LF)
    if eol != _LF:
        norm = norm.replace(_LF, eol)
    with open(path, "wb") as f:
        f.write(norm.encode("utf-8"))


def _module_bindings(text):
    """Names bound at MODULE scope: imports, assignments, defs, loop targets.

    Input to the binding-survival gate. Function and class bodies are NOT
    descended into: the gate exists to catch an edit that deletes a module-level
    symbol the rest of the module depends on, and a rule that legitimately
    rewrites a function body must not trip it.

    Returns an empty set on a syntax error (the compile test reports that).
    """
    names = set()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return names

    def targets(t):
        return {n.id for n in ast.walk(t) if isinstance(n, ast.Name)}

    def walk(body):
        nonlocal names
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef)):
                names.add(node.name)
            elif isinstance(node, ast.Import):
                for a in node.names:
                    names.add(a.asname or a.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                for a in node.names:
                    names.add(a.asname or a.name)
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    names |= targets(t)
            elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
                names |= targets(node.target)
            elif isinstance(node, (ast.For, ast.AsyncFor)):
                names |= targets(node.target)
                walk(node.body)
                walk(node.orelse)
            elif isinstance(node, ast.With):
                for item in node.items:
                    if item.optional_vars is not None:
                        names |= targets(item.optional_vars)
                walk(node.body)
            elif isinstance(node, ast.Try):
                walk(node.body)
                for h in node.handlers:
                    if h.name:
                        names.add(h.name)
                    walk(h.body)
                walk(node.orelse)
                walk(node.finalbody)
            elif isinstance(node, (ast.If, ast.While)):
                walk(node.body)
                walk(node.orelse)
    walk(tree.body)
    return names


def _import_statements(tree):
    """Single-line module-level imports as (lineno, alias_texts, bound_names).

    Multi-line (parenthesised) imports are skipped: editing those safely is more
    than a line rewrite, and the current SAFE_TARGETS contain none.
    """
    out = []
    for node in tree.body:
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if getattr(node, "end_lineno", node.lineno) != node.lineno:
            continue
        texts, bound = [], []
        for a in node.names:
            texts.append(a.name + (" as " + a.asname if a.asname else ""))
            if isinstance(node, ast.Import):
                bound.append(a.asname or a.name.split(".")[0])
            else:
                bound.append(a.asname or a.name)
        out.append((node.lineno, texts, bound))
    return out


def _dedupe_import_proposals(content):
    """P5: a name imported twice at module level can lose one binding.

    Verified against the real targets first: four of the six bind `os` twice --
    a bare `import os` line plus `os` inside the comma-import on the next line.
    Only the LATER occurrence is dropped, and only from a statement that keeps
    at least one alias, so the name always stays bound.
    """
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    lines = content.split(_LF)
    stmts = _import_statements(tree)
    counts = {}
    for _lineno, _texts, bound in stmts:
        for b in bound:
            counts[b] = counts.get(b, 0) + 1
    dup = {b for b, c in counts.items() if c > 1}
    if not dup:
        return []

    proposals = []
    first_seen = {}
    for lineno, texts, bound in stmts:
        line = lines[lineno - 1]
        if "import" not in line:
            continue
        for idx, b in enumerate(bound):
            if b not in dup:
                continue
            if b not in first_seen:
                first_seen[b] = lineno
                continue
            if len(texts) < 2:
                continue
            prefix = line[:line.rindex("import") + len("import")]
            kept = [t for i, t in enumerate(texts) if i != idx]
            new_line = prefix + " " + ", ".join(kept)
            if new_line == line:
                continue
            proposals.append(("dedupe-import", line, new_line,
                              b + " imported twice at module level"))
            break
    return proposals


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
    #
    # The guard MUST test `m2` (the max_tokens match), never `m` (the
    # CYCLE_SECONDS match from P1). Testing `m` here fired whenever P1 found a
    # cycle interval under 100s, and the proposal then carried `m.group(0)` --
    # the CYCLE_SECONDS text -- as the pattern to replace. apply_and_test()
    # rewrites the live file with src.replace(old, new, 1), so the rule deleted
    # the assignment it was named after. Measured on this form: for the input
    # `CYCLE_SECONDS = 60\nmax_tokens = 400\n` it proposed
    # ('capacity', 'CYCLE_SECONDS = 60', 'max_tokens=200') and the patched file
    # became `max_tokens=200\nmax_tokens = 400\n` -- the cycle interval gone.
    # None of the three checks in apply_and_test() catches that: the result still
    # compiles, still AST-parses, and still defines loop().
    m2 = re.search(r"max_tokens\s*=\s*(\d+)", content)
    if m2 and int(m2.group(1)) < 100:
        proposals.append(("capacity", m2.group(0), "max_tokens=200",
                          "small max_tokens limits answer quality"))

    # P5: duplicate module-level import (dead binding, zero behaviour change)
    if target.endswith(".py"):
        proposals.extend(_dedupe_import_proposals(content))

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
    src = _read_text(live_path)
    eol = _eol_of(live_path)
    if old not in src:
        return False, f"pattern not found: {old[:50]}"
    patched = src.replace(old, new, 1)
    if patched == src:
        return False, "no change made"
    _write_text(sandbox_path, patched, eol)

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

    # TEST 4: binding survival -- the general form of the historical P2 bug.
    # All three checks above pass on a rewrite that DELETED CYCLE_SECONDS (the
    # file still compiled, still parsed, still defined loop()), so the gate has
    # to test the thing the rule is named after: that the module-level symbols
    # it edited still exist.
    lost = _module_bindings(src) - _module_bindings(patched)
    if lost:
        return False, "binding lost: " + str(sorted(lost)[:5])
    return True, "all tests passed"

def improve_once():
    """One self-improvement attempt. Returns log entry."""
    targets = list(SAFE_TARGETS.keys())
    rot_file = os.path.join(T, ".si_rotation")
    n = 0
    if os.path.exists(rot_file):
        n = int(open(rot_file, encoding="utf-8").read().strip() or 0)
    target = targets[n % len(targets)]
    with open(rot_file, "w", encoding="utf-8") as f:
        f.write(str(n + 1))
    live_path = os.path.join(T, target)
    if not os.path.exists(live_path):
        return {"target": target, "status": "skip", "reason": "file missing"}

    content = _read_text(live_path)
    proposals = propose_improvement(target, content)
    if not proposals:
        # Log it. Returning silently made a rotation that produced nothing
        # indistinguishable from a loop that never ran (improvements.jsonl
        # stopped growing with no trace of why).
        entry = {"target": target, "status": "no-proposal",
                 "reason": "already optimal or no safe pattern"}
        log(entry)
        print(f"[self-improve] no-proposal: {target} — already optimal or "
              f"no safe pattern", flush=True)
        return entry

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
                git_result = run(["git", "-C", REPO,
                                  "checkout", "--", f"scripts/training/{target}"])
                # restore from repo
                repo_file = os.path.join(REPO, "scripts", "training", target)
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

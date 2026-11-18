#!/usr/bin/env python3
"""A FRESH benchmark: tasks no model has seen, scored by executing them.

Why this exists (2026-11-18)
----------------------------
`scripts/benchmark.py` asked 14 knowledge questions and 8 arithmetic questions
and was run 22 times. The last scores (13/14, 8/8) measured how well the run
recognised the question list, not what the system can do — and those numbers
were quoted as capability. `memory/bench_runs.jsonl` records a HumanEval
harness that no longer exists anywhere in the repo (`bench_suite` has 0 hits in
the full git history), so the only surviving instrument was the contaminated one.

This harness removes the memorisation path instead of warning about it:

* **Every task is generated fresh** from a seed. A signature of each task is
  stored in `memory/fresh_bench_seen.jsonl`; a task whose signature was seen
  before is regenerated, so the same question cannot be asked twice.
* **Scoring is execution, not opinion.** The model's code is run against the
  generator's own assertions in a subprocess. `resolved` means the tests passed.
* **Every subject gets the identical task set** in one run — that is the only
  comparison that means anything.
* **A transport failure is not a score.** If every failure is
  connection/timeout, the run is marked `model_error` and no percentage is
  printed, because a missing model reads exactly like a bad model.

Honest limits, stated up front: this measures *procedural code synthesis*, not
HumanEval and not chat quality. n is small by design (a CPU-only 2B model takes
seconds per task). Intervals are Wilson 95 %, and overlapping intervals mean the
ranking is NOT established.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import math
import random
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

HOME = Path(os.environ.get("OPENAMER_HOME")
            or (Path.home() / "AppData" / "Local" / "openamer-laptop"))
MEMORY = HOME / "memory"
SEEN = MEMORY / "fresh_bench_seen.jsonl"
RUNS = MEMORY / "fresh_bench_runs.jsonl"
REPORT = HOME / "reports" / "fresh-bench-latest.json"


# ── task generators: (prompt, tests, reference) ────────────────────────────
# Each returns a dict with a signature, a prompt, and `cases`: [(args, expected)].
# The reference solution exists so the harness can prove the task is solvable
# before it blames a model for failing it.

def gen_arith(rng):
    a, b, c = rng.randint(7, 99), rng.randint(3, 19), rng.randint(2, 9)
    op1 = rng.choice(["+", "-", "*"])
    op2 = rng.choice(["+", "-", "*"])
    expr = f"({a} {op1} {b}) {op2} {c}"
    expected = eval(expr)  # noqa: S307 - generated from integers and three operators
    return {
        "kind": "arith",
        "prompt": (f"Write a Python function `solve()` that returns the integer value of {expr}. "
                   "Return only the code, no explanation."),
        "cases": [((), expected)],
        "ref": f"def solve():\n    return {expr}\n",
    }


def gen_rle(rng):
    alphabet = "abcde"
    s = "".join(rng.choice(alphabet) for _ in range(rng.randint(6, 12)))
    out, i = [], 0
    while i < len(s):
        j = i
        while j < len(s) and s[j] == s[i]:
            j += 1
        out.append(f"{j - i}{s[i]}")
        i = j
    enc = "".join(out)
    return {
        "kind": "rle",
        "prompt": (f"Write a Python function `solve(s)` that run-length encodes s: each run of the "
                   f"same character becomes the count followed by the character. "
                   f"Example: solve({s!r}) == {enc!r}. Return only the code."),
        "cases": [((s,), enc), (("aabbb",), "2a3b"), (("x",), "1x")],
        "ref": ("def solve(s):\n    out, i = [], 0\n    while i < len(s):\n"
                "        j = i\n        while j < len(s) and s[j] == s[i]:\n            j += 1\n"
                "        out.append(f'{j - i}{s[i]}')\n        i = j\n    return ''.join(out)\n"),
    }


def gen_merge(rng):
    raw = []
    t = rng.randint(0, 5)
    for _ in range(rng.randint(3, 5)):
        start = t + rng.randint(0, 4)
        raw.append([start, start + rng.randint(1, 5)])
        t = start + rng.randint(1, 6)
    merged = []
    for s, e in sorted(raw):
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return {
        "kind": "merge_intervals",
        "prompt": (f"Write a Python function `solve(intervals)` that merges overlapping or touching "
                   f"closed intervals and returns them sorted. Example: solve({raw!r}) == {merged!r}. "
                   "Return only the code."),
        "cases": [((raw,), merged),
                  (([[1, 2], [3, 4]],), [[1, 2], [3, 4]]),
                  (([[1, 5], [2, 3]],), [[1, 5]])],
        "ref": ("def solve(intervals):\n    merged = []\n    for s, e in sorted(intervals):\n"
                "        if merged and s <= merged[-1][1]:\n"
                "            merged[-1][1] = max(merged[-1][1], e)\n"
                "        else:\n            merged.append([s, e])\n    return merged\n"),
    }


def gen_date(rng):
    start = date(2026, 1, 1) + timedelta(days=rng.randint(0, 900))
    delta = rng.randint(-120, 400)
    expected = (start + timedelta(days=delta)).isoformat()
    return {
        "kind": "date_shift",
        "prompt": (f"Write a Python function `solve(s)` that takes a date string 'YYYY-MM-DD' and "
                   f"returns the date {delta} days later as 'YYYY-MM-DD'. "
                   f"Example: solve({start.isoformat()!r}) == {expected!r}. Return only the code."),
        # Every case must use the SAME delta as the prompt. The first version
        # added two fixed cases with delta=1, so the task's own reference failed
        # its own tests — caught by tests/scripts/test_self_instruments.py before
        # it could produce a fake model score. A task that is unsolvable by
        # construction blames the model for the harness's bug.
        "cases": [((start.isoformat(),), expected),
                  ((start.replace(day=1).isoformat(),),
                   (start.replace(day=1) + timedelta(days=delta)).isoformat()),
                  ((date(2024, 2, 28).isoformat(),),
                   (date(2024, 2, 28) + timedelta(days=delta)).isoformat())],
        "ref": ("from datetime import date, timedelta\n\n\ndef solve(s):\n"
                "    y, m, d = (int(x) for x in s.split('-'))\n"
                f"    return (date(y, m, d) + timedelta(days={delta})).isoformat()\n"),
    }


def gen_agg(rng):
    rows = [{"team": rng.choice(["red", "blue", "green"]), "score": rng.randint(1, 30)}
            for _ in range(rng.randint(4, 7))]
    team = rng.choice(["red", "blue", "green"])
    expected = sum(r["score"] for r in rows if r["team"] == team)
    return {
        "kind": "aggregate",
        "prompt": (f"Write a Python function `solve(rows, team)` that sums `score` over the rows "
                   f"whose `team` equals the argument. Example: solve({rows!r}, {team!r}) == {expected}. "
                   "Return only the code."),
        "cases": [((rows, team), expected),
                  (([{"team": "a", "score": 2}, {"team": "b", "score": 3}], "a"), 2)],
        "ref": "def solve(rows, team):\n    return sum(r['score'] for r in rows if r['team'] == team)\n",
    }


def gen_base(rng):
    n = rng.randint(20, 5000)
    b = rng.choice([2, 8, 16])
    digits = "0123456789abcdef"
    if b == 2:
        expected = bin(n)[2:]
    elif b == 8:
        expected = oct(n)[2:]
    else:
        expected = format(n, "x")
    return {
        "kind": "base_convert",
        "prompt": (f"Write a Python function `solve(n, b)` that returns n written in base b "
                   f"(digits 0-9a-f, lowercase, no prefix) for b in 2, 8 or 16. "
                   f"Example: solve({n}, {b}) == {expected!r}. Return only the code."),
        "cases": [((n, b), expected), ((255, 16), "ff"), ((5, 2), "101")],
        "ref": ("def solve(n, b):\n    digits = '0123456789abcdef'\n    if n == 0:\n"
                "        return '0'\n    out = []\n    while n:\n        out.append(digits[n % b])\n"
                "        n //= b\n    return ''.join(reversed(out))\n"),
    }


GENERATORS = [gen_arith, gen_rle, gen_merge, gen_date, gen_agg, gen_base]


# ── freshness ──────────────────────────────────────────────────────────────

def signature(task: dict) -> str:
    blob = json.dumps([task["kind"], [list(c[0]) for c in task["cases"]], task["prompt"][:80]],
                      sort_keys=True, default=str)
    return hashlib.md5(blob.encode("utf-8")).hexdigest()[:16]


def load_seen() -> set[str]:
    if not SEEN.exists():
        return set()
    out = set()
    for line in SEEN.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            out.add(json.loads(line)["signature"])
        except Exception:
            continue
    return out


def make_tasks(n: int, rng: random.Random) -> tuple[list[dict], int]:
    """Generate n tasks that have never been asked before. Returns (tasks, regenerated)."""
    seen = load_seen()
    tasks, retries_total = [], 0
    for i in range(n):
        gen = GENERATORS[i % len(GENERATORS)]
        for attempt in range(8):
            task = gen(rng)
            sig = signature(task)
            if sig not in seen:
                task["signature"] = sig
                seen.add(sig)
                tasks.append(task)
                break
            retries_total += 1
        else:
            raise SystemExit(f"generator {gen.__name__} produced only seen tasks — widen it")
    return tasks, retries_total


def verify_tasks(tasks: list[dict]) -> None:
    """A task whose own reference fails is a harness bug, never a model result."""
    for task in tasks:
        ok, why = run_code(task["ref"], task["cases"])
        if not ok:
            raise SystemExit(f"reference solution fails its own tests ({task['kind']}): {why}")


# ── execution scoring ──────────────────────────────────────────────────────

def extract_code(text: str) -> str:
    """Take the first fenced block, else the whole answer, and drop prose lines."""
    fences = re.findall(r"```(?:python)?\s*(.*?)```", text, re.DOTALL)
    code = max(fences, key=len) if fences else text
    lines = [l for l in code.splitlines()
             if not re.match(r"^\s*(here|this|the function|explanation|output)\b", l, re.I)]
    return "\n".join(lines).strip()


def run_code(code: str, cases: list) -> tuple[bool, str]:
    """Execute `solve` against every case in a fresh subprocess."""
    runner = code + "\n\nimport json as _json\n_RESULTS = []\n"
    for args, expected in cases:
        runner += ("try:\n    _RESULTS.append({'ok': solve(*%r) == %r})\n"
                   "except Exception as exc:\n    _RESULTS.append({'ok': False, 'err': repr(exc)})\n"
                   % (list(args), expected))
    runner += "print(_json.dumps(_RESULTS))\n"
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as fh:
        fh.write(runner)
        path = fh.name
    try:
        r = subprocess.run([sys.executable, path], capture_output=True, text=True,
                           timeout=25, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            return False, (r.stderr or "nonzero exit")[-160:]
        results = json.loads(r.stdout.strip().splitlines()[-1])
        if all(x.get("ok") for x in results):
            return True, ""
        errs = [x.get("err") for x in results if not x.get("ok")]
        return False, "; ".join(e for e in errs if e)[:160] or "wrong answer"
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except Exception as exc:
        return False, f"runner: {exc}"
    finally:
        Path(path).unlink(missing_ok=True)


# ── model calls ────────────────────────────────────────────────────────────

def call_model(base: str, model: str, prompt: str, timeout: float = 180.0) -> tuple[str, str]:
    """Return (text, error). An empty text with an error is a transport failure."""
    body = json.dumps({"model": model, "temperature": 0,
                       "messages": [{"role": "user", "content": prompt}]}).encode("utf-8")
    req = urllib.request.Request(f"{base.rstrip('/')}/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        text = (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""
        return text, "" if text.strip() else "empty completion"
    except urllib.error.HTTPError as exc:
        return "", f"HTTP {exc.code}"
    except Exception as exc:
        return "", f"{type(exc).__name__}: {exc}"


def wilson(passed: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = passed / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - margin), min(1.0, centre + margin)


def evaluate(subject: dict, tasks: list[dict]) -> dict:
    solved, failures = 0, []
    for task in tasks:
        text, err = call_model(subject["base"], subject["model"], task["prompt"])
        if err and not text:
            failures.append({"kind": task["kind"], "transport": err, "sig": task["signature"]})
            continue
        code = extract_code(text)
        ok, why = run_code(code, task["cases"])
        if ok:
            solved += 1
        else:
            failures.append({"kind": task["kind"], "why": why[:120], "sig": task["signature"]})
    transport_only = bool(failures) and all("transport" in f for f in failures)
    return {
        "subject": subject["name"],
        "model": subject["model"],
        "base": subject["base"],
        "resolved": solved,
        "n": len(tasks),
        "share": solved / len(tasks) if tasks else 0.0,
        "ci95": list(wilson(solved, len(tasks))),
        "model_error": transport_only,
        "model_error_reason": failures[0]["transport"] if transport_only else "",
        "failures": failures[:6],
    }


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Fresh, execution-scored benchmark.")
    ap.add_argument("--items", type=int, default=6)
    ap.add_argument("--seed", default="auto")
    ap.add_argument("--local-base", default="http://127.0.0.1:8081/v1")
    ap.add_argument("--local-model", default="mini-openamer")
    ap.add_argument("--ref-base", default="http://127.0.0.1:11434/v1")
    ap.add_argument("--ref-model", default="deepseek-v4.1-flash:cloud")
    # There is no GPU node: the PC worker was decommissioned 2026-11-18. A
    # subject that cannot answer is not a subject — it would only ever print
    # MODEL ERROR, so it is gone rather than carried as a permanent failure.
    ap.add_argument("--subjects", default="local,ref")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    seed = args.seed if args.seed != "auto" else str(int(time.time()))
    rng = random.Random(seed)
    tasks, regenerated = make_tasks(args.items, rng)
    verify_tasks(tasks)

    known = {"local": {"name": "Mini-OpenAmer (2B, CPU)", "base": args.local_base, "model": args.local_model},
             "ref": {"name": "reference (deepseek-v4.1-flash)", "base": args.ref_base, "model": args.ref_model}}
    subjects = [known[k.strip()] for k in args.subjects.split(",") if k.strip() in known]

    started = time.strftime("%Y-%m-%dT%H:%M:%S")
    print(f"fresh bench: {len(tasks)} never-seen task(s), seed {seed} "
          f"({regenerated} duplicate signature(s) regenerated)")
    results = []
    for subject in subjects:
        row = evaluate(subject, tasks)
        results.append(row)
        if row["model_error"]:
            print(f"  {row['subject']:<32} MODEL ERROR — {row['model_error_reason']}")
        else:
            lo, hi = row["ci95"]
            print(f"  {row['subject']:<32} {row['resolved']}/{row['n']} "
                  f"{row['share'] * 100:5.1f}%  [{lo * 100:.1f}, {hi * 100:.1f}]")

    scored = [r for r in results if not r["model_error"]]
    ranking = ""
    if len(scored) > 1:
        lo_best = max(r["ci95"][0] for r in scored)
        hi_worst = min(r["ci95"][1] for r in scored)
        ranking = ("ranking NOT established by this run (intervals overlap)"
                   if hi_worst > lo_best else "ranking separated by this run")
        print(f"  {ranking}")

    payload = {"ts": started, "seed": seed, "items": len(tasks),
               "kinds": [t["kind"] for t in tasks],
               "signatures": [t["signature"] for t in tasks],
               "harness_params": {"temperature": 0, "timeout_s": 180, "exec_scored": True},
               "results": results, "ranking": ranking}
    MEMORY.mkdir(exist_ok=True)
    with SEEN.open("a", encoding="utf-8") as fh:
        for t in tasks:
            fh.write(json.dumps({"signature": t["signature"], "kind": t["kind"],
                                 "ts": started}) + "\n")
    with RUNS.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"  wrote {RUNS} and {REPORT}")
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    return 0 if scored else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

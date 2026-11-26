#!/usr/bin/env python3
"""Beyond Bench — OpenAmer's own reproducible capability measurement.

Design rules (these are the point, not decoration):
  * A pass is computed by a verifier in tasks.py, never asserted by prose.
  * Identical catalog, identical verifiers, identical grading for every subject,
    so local and remote models are compared on the same ruler.
  * Transport failures are recorded as ``error``, never silently scored as a
    wrong answer: a dead provider must not look like a stupid model.
  * Every run writes a timestamped JSON on disk. A number that is not in a file
    does not exist.

Usage:
    python scripts/bench/run.py --subjects npu,ollama:qwen2.5-coder:1.5b
    python scripts/bench/run.py --list-subjects
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tasks import TASKS  # noqa: E402

HOME = Path(os.environ.get("OPENAMER_HOME", Path.home() / "AppData" / "Local" / "openamer-laptop"))
OUT_DIR = HOME / "reports" / "beyond-bench"
OLLAMA = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")


def catalog_signature() -> str:
    h = hashlib.sha256()
    for t in TASKS:
        h.update(t["id"].encode())
        h.update(t["prompt"].encode())
    return h.hexdigest()[:16]


# --------------------------------------------------------------------------- #
# subjects
# --------------------------------------------------------------------------- #

def subject_npu() -> dict:
    """Local NPU model through the Mini-OpenAmer backend (no HTTP hop needed)."""
    training = str(HOME / "scripts" / "training")
    if training not in sys.path:
        sys.path.insert(0, training)
    import mini_backend  # noqa: E402

    return {
        "name": "local-npu-qwen3.5-4b",
        "label": "Mini-OpenAmer / NPU (Qwen3.5-4B, local)",
        "call": lambda prompt: _mini_call(mini_backend, prompt),
    }


def _mini_call(mini_backend, prompt: str) -> dict:
    t0 = time.time()
    r = mini_backend.chat(
        [{"role": "user", "content": prompt}],
        max_tokens=512,
        temperature=0.0,
        enable_thinking=False,
    )
    return {
        "text": r.get("content") or "",
        "latency_s": round(time.time() - t0, 3),
        "tokens_out": r.get("completion_tokens", 0),
        "tok_per_s": r.get("tok_per_s", 0),
        "model": r.get("model", "mini"),
    }


def subject_ollama(model: str) -> dict:
    def call(prompt: str) -> dict:
        t0 = time.time()
        body = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "stream": False,
            # num_ctx is explicit and small on purpose. Ollama otherwise honours the
            # model's own context window -- qwen3.5:9b declares 262144, which made it
            # resident at 15.9 GB for a 6.6 GB model and aborted the run on a 21.8 GB
            # laptop. The catalogue's longest prompt is well under 2000 tokens, so a
            # 4096 window is generous and makes the measurement about capability
            # instead of about how much memory the default allocation ate.
            "options": {"temperature": 0, "num_predict": 700,
                        "num_ctx": int(os.environ.get("BENCH_NUM_CTX", "4096"))},
        }).encode()
        req = urllib.request.Request(
            f"{OLLAMA}/v1/chat/completions",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=300) as resp:
            d = json.loads(resp.read())
        text = (d["choices"][0]["message"].get("content") or "")
        usage = d.get("usage") or {}
        eval_count = usage.get("completion_tokens", 0)
        dur = max(time.time() - t0, 0.001)
        return {
            "text": text,
            "latency_s": round(dur, 3),
            "tokens_out": eval_count,
            "tok_per_s": round(eval_count / dur, 2) if eval_count else 0,
            "model": model,
        }

    return {"name": f"ollama:{model}", "label": f"Ollama {model}", "call": call}


def resolve_subjects(spec: str) -> list:
    out = []
    for raw in [s.strip() for s in spec.split(",") if s.strip()]:
        if raw == "npu":
            out.append(subject_npu())
        elif raw.startswith("ollama:"):
            out.append(subject_ollama(raw[len("ollama:"):]))
        else:
            raise SystemExit(f"unknown subject: {raw}")
    return out


def list_subjects() -> None:
    print("built-in subjects:")
    print("  npu                        local NPU Qwen3.5-4B via mini_backend")
    print("  ollama:<model>             any model Ollama exposes (local or :cloud)")
    print("\nmodels currently available in Ollama:")
    try:
        with urllib.request.urlopen(f"{OLLAMA}/api/tags", timeout=8) as r:
            for m in json.loads(r.read()).get("models", []):
                print(f"  ollama:{m['name']}")
    except Exception as exc:
        print(f"  (unavailable: {exc})")


# --------------------------------------------------------------------------- #
# run
# --------------------------------------------------------------------------- #

def run_task(task: dict, subject: dict) -> dict:
    row = {
        "task": task["id"],
        "kind": task["kind"],
        "subject": subject["name"],
    }
    try:
        res = subject["call"](task["prompt"])
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, TimeoutError) as exc:
        row.update(status="error", error=f"{type(exc).__name__}: {exc}"[:300], passed=False)
        return row
    except Exception as exc:  # noqa: BLE001 - model backends raise freely
        row.update(status="error", error=f"{type(exc).__name__}: {exc}"[:300], passed=False)
        return row

    text = res.get("text", "")
    try:
        ok = bool(task["check"](text))
    except Exception as exc:  # noqa: BLE001 - a broken verifier must be visible
        row.update(status="verify_error", error=str(exc)[:200], passed=False, text=text[:400])
        return row

    row.update(
        status="ok",
        passed=ok,
        latency_s=res.get("latency_s"),
        tokens_out=res.get("tokens_out", 0),
        tok_per_s=res.get("tok_per_s", 0),
        model=res.get("model", ""),
        text=text[:400],
    )
    return row


def main() -> int:
    ap = argparse.ArgumentParser(description="Reproducible OpenAmer capability benchmark")
    ap.add_argument("--subjects", default="npu", help="comma list, e.g. npu,ollama:qwen3:8b")
    ap.add_argument("--tasks", default="", help="comma list of task ids (default: all)")
    ap.add_argument("--list-subjects", action="store_true")
    ap.add_argument("--tag", default="", help="free-form label stored in the result file")
    args = ap.parse_args()

    if args.list_subjects:
        list_subjects()
        return 0

    tasks = TASKS
    if args.tasks:
        wanted = {t.strip() for t in args.tasks.split(",") if t.strip()}
        tasks = [t for t in TASKS if t["id"] in wanted]
        missing = wanted - {t["id"] for t in tasks}
        if missing:
            raise SystemExit(f"unknown task ids: {sorted(missing)}")

    subjects = resolve_subjects(args.subjects)
    started = datetime.now(timezone.utc)
    rows = []

    for subject in subjects:
        print(f"\n=== {subject['label']} ===", flush=True)
        for task in tasks:
            row = run_task(task, subject)
            rows.append(row)
            if row["status"] == "ok":
                mark = "PASS" if row["passed"] else "FAIL"
                print(
                    f"  [{mark}] {task['id']:<28} {row.get('latency_s', 0):>6.2f}s "
                    f"{row.get('tok_per_s', 0):>6.1f} tok/s",
                    flush=True,
                )
            else:
                print(f"  [ERR ] {task['id']:<28} {row['error'][:90]}", flush=True)

    summary = []
    for subject in subjects:
        srows = [r for r in rows if r["subject"] == subject["name"]]
        scored = [r for r in srows if r["status"] == "ok"]
        errors = [r for r in srows if r["status"] != "ok"]
        passed = sum(1 for r in scored if r["passed"])
        lat = [r["latency_s"] for r in scored if r.get("latency_s")]
        summary.append({
            "subject": subject["name"],
            "label": subject["label"],
            "tasks": len(srows),
            "scored": len(scored),
            "errors": len(errors),
            "passed": passed,
            "pass_rate_of_scored": round(passed / len(scored), 4) if scored else None,
            "pass_rate_of_all": round(passed / len(srows), 4) if srows else None,
            "median_latency_s": round(sorted(lat)[len(lat) // 2], 3) if lat else None,
            "by_kind": _by_kind(srows),
        })

    result = {
        "harness": "beyond-bench",
        "version": 1,
        "tag": args.tag,
        "started_utc": started.isoformat(),
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "host": platform.node(),
        "catalog_signature": catalog_signature(),
        "catalog_tasks": [t["id"] for t in tasks],
        "temperature": 0,
        "summary": summary,
        "rows": rows,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = started.strftime("%Y%m%dT%H%M%SZ")
    path = OUT_DIR / f"beyond-bench-{stamp}.json"
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    latest = OUT_DIR / "latest.json"
    latest.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print("\n--- summary ---")
    for s in summary:
        pr = s["pass_rate_of_scored"]
        pr_s = "n/a" if pr is None else f"{pr * 100:.1f}%"
        print(
            f"{s['subject']:<32} {s['passed']}/{s['scored']} scored "
            f"({pr_s}) errors={s['errors']} median={s['median_latency_s']}s"
        )
    print(f"\nresult: {path}")
    return 0


def _by_kind(rows: list) -> dict:
    kinds: dict = {}
    for r in rows:
        k = r["kind"]
        slot = kinds.setdefault(k, {"tasks": 0, "scored": 0, "passed": 0})
        slot["tasks"] += 1
        if r["status"] == "ok":
            slot["scored"] += 1
            if r["passed"]:
                slot["passed"] += 1
    return kinds


if __name__ == "__main__":
    raise SystemExit(main())

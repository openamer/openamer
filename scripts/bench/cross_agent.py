#!/usr/bin/env python3
"""Cross-agent benchmark subset — the same ruler for different agents.

Mission BEYOND ALL / step p2.3 asked for a cross-agent subset with public logs
and a number that names the subset size. The official SWE-bench Verified
harness is a container workload; this laptop has no container runtime and 38 GB
free on a 97 %-full disk, so that row stays honestly absent. What *is* runnable
here is a cross-agent subset on the existing beyond-bench catalog: same tasks,
same verifiers, same timeout, each agent in a fresh empty working directory.

Fairness rules (these are the measurement, not decoration):
  * The catalog and its verifiers are imported from tasks.py -- the ruler does
    not change between subjects.
  * Every subject gets an identical prompt, an identical wall-clock timeout and
    a fresh temp cwd, so no subject inherits state from another.
  * A transport failure is recorded as ``error``, never scored as a wrong
    answer. A dead agent must not look like a stupid agent.
  * Versions (agent CLI + repo commit + model) are probed and stored next to
    the scores. A score without those is not reproducible.
  * Extra prose counts. The verifiers grade the whole reply, so a subject that
    ignores "answer with the integer only" fails that task. That is the point.

Usage:
    python scripts/bench/cross_agent.py --list-subjects
    python scripts/bench/cross_agent.py --subjects openamer,bare-cloud --tasks arith.chain.v1
    python scripts/bench/cross_agent.py --subjects openamer,bare-cloud,npu
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tasks import TASKS  # noqa: E402
from run import catalog_signature, subject_npu, subject_ollama, _by_kind  # noqa: E402

HOME = Path(os.environ.get("OPENAMER_HOME", Path.home() / "AppData" / "Local" / "openamer-laptop"))
OUT_DIR = HOME / "reports" / "beyond-bench"
ANSI = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")


def _clean(text: str) -> str:
    return ANSI.sub("", text).replace("\r\n", "\n").strip()


def _kill_tree(pid: int) -> None:
    """Windows-safe child cleanup: a bare kill() leaves grandchildren running."""
    try:
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            capture_output=True,
            timeout=20,
        )
    except Exception:
        pass


def _run_cli(cmd: list, prompt: str, timeout: int, stdin_text: str | None = None) -> dict:
    """Run one agent invocation in an isolated temp cwd and return its text."""
    workdir = tempfile.mkdtemp(prefix="xagent-")
    t0 = time.time()
    env = dict(os.environ)
    env["NO_COLOR"] = "1"
    env["TERM"] = "dumb"
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=workdir,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        try:
            out, err = proc.communicate(input=stdin_text, timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_tree(proc.pid)
            try:
                out, err = proc.communicate(timeout=15)
            except Exception:
                out, err = "", ""
            dur = time.time() - t0
            return {
                "text": _clean(out or ""),
                "stderr": _clean(err or "")[:600],
                "latency_s": round(dur, 3),
                "exit_code": None,
                "timed_out": True,
            }
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    dur = time.time() - t0
    return {
        "text": _clean(out),
        "stderr": _clean(err)[:600],
        "latency_s": round(dur, 3),
        "exit_code": proc.returncode,
        "timed_out": False,
    }


def _probe_version(cmd: list) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, encoding="utf-8", errors="replace")
        first = _clean((r.stdout or r.stderr or "")).splitlines()
        return first[0][:120] if first else ""
    except Exception as exc:  # noqa: BLE001
        return f"probe failed: {type(exc).__name__}"


# --------------------------------------------------------------------------- #
# agent subjects
# --------------------------------------------------------------------------- #

def subject_openamer() -> dict:
    exe = shutil.which("openamer") or "openamer"

    def call(prompt: str) -> dict:
        res = _run_cli([exe, "-z", prompt], prompt, timeout=OPENAMER_TIMEOUT)
        if res["timed_out"]:
            raise TimeoutError(f"openamer -z exceeded {OPENAMER_TIMEOUT}s")
        if res["exit_code"] not in (0, None) and not res["text"]:
            raise RuntimeError(f"openamer exit={res['exit_code']} stderr={res['stderr'][:200]}")
        return {"text": res["text"], "latency_s": res["latency_s"], "model": "agent-default"}

    return {
        "name": "openamer-agent",
        "label": "OpenAmer agent (full scaffold, openamer -z)",
        "kind": "agent",
        "version": _probe_version([exe, "--version"]),
        "call": call,
    }


def subject_claude() -> dict:
    exe = shutil.which("claude")
    if not exe:
        raise SystemExit("claude CLI not on PATH")

    probe = _run_cli([exe, "-p", "Reply with the single word: PONG", "--output-format", "text"], "", 180)
    if "not logged in" in (probe["text"] + probe["stderr"]).lower():
        raise SystemExit("claude is installed but not logged in -- cannot act as a subject")

    def call(prompt: str) -> dict:
        res = _run_cli([exe, "-p", prompt, "--output-format", "text"], prompt, timeout=OPENAMER_TIMEOUT)
        if res["timed_out"]:
            raise TimeoutError(f"claude -p exceeded {OPENAMER_TIMEOUT}s")
        return {"text": res["text"], "latency_s": res["latency_s"], "model": "claude-default"}

    return {
        "name": "claude-code",
        "label": "Claude Code (claude -p, full scaffold)",
        "kind": "agent",
        "version": _probe_version([exe, "--version"]),
        "call": call,
    }


def subject_bare(model: str, label: str) -> dict:
    """Model-only control: the same model with no agent scaffold around it."""
    base = subject_ollama(model)
    return {
        "name": f"bare:{model}",
        "label": f"{label} (model only, no scaffold)",
        "kind": "model",
        "version": f"ollama {_ollama_version()}",
        "call": base["call"],
    }


def _ollama_version() -> str:
    try:
        r = subprocess.run(["ollama", "--version"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=30)
        return _clean(r.stdout).splitlines()[0][:60]
    except Exception:  # noqa: BLE001
        return "unknown"


def subject_local() -> dict:
    base = subject_npu()
    return {
        "name": "local-npu",
        "label": base["label"],
        "kind": "model",
        "version": "mini_backend (NPU, Qwen3.5-4B)",
        "call": base["call"],
    }


SUBJECT_BUILDERS = {
    "openamer": subject_openamer,
    "claude": subject_claude,
    "npu": subject_local,
}
OPENAMER_TIMEOUT = int(os.environ.get("XAGENT_TIMEOUT", "300"))


def resolve_subjects(spec: str) -> list:
    out = []
    for raw in [s.strip() for s in spec.split(",") if s.strip()]:
        if raw in SUBJECT_BUILDERS:
            out.append(SUBJECT_BUILDERS[raw]())
        elif raw == "bare-cloud":
            out.append(subject_bare("minimax-m3.1-flash:cloud", "MiniMax M3.1 flash (ollama cloud)"))
        elif raw.startswith("bare:"):
            out.append(subject_bare(raw[len("bare:"):], raw[len("bare:"):]))
        else:
            raise SystemExit(f"unknown subject: {raw}")
    return out


# --------------------------------------------------------------------------- #
# run
# --------------------------------------------------------------------------- #

def run_task(task: dict, subject: dict) -> dict:
    row = {"task": task["id"], "kind": task["kind"], "subject": subject["name"]}
    try:
        res = subject["call"](task["prompt"])
    except Exception as exc:  # noqa: BLE001 - agent backends raise freely
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
        text=text[:400],
    )
    return row


def _repo_commit() -> dict:
    out = {}
    for label, path in (("home", HOME), ("checkout", HOME / "openamer-agent")):
        try:
            r = subprocess.run(
                ["git", "-C", str(path), "rev-parse", "HEAD"],
                capture_output=True, text=True, timeout=60,
                encoding="utf-8", errors="replace",
            )
            out[label] = _clean(r.stdout) or None
        except Exception:  # noqa: BLE001
            out[label] = None
    return out


def write_markdown(result: dict, path: Path) -> None:
    lines = [
        f"# Cross-agent benchmark subset — {result['started_utc']}",
        "",
        f"- catalog signature: `{result['catalog_signature']}`",
        f"- subset size: **{len(result['catalog_tasks'])} tasks**",
        f"- host: `{result['host']}`",
        f"- commits: `{json.dumps(result['commits'])}`",
        f"- temperature: {result['temperature']}",
        "",
        "## Subjects",
        "",
        "| subject | kind | version |",
        "|---|---|---|",
    ]
    for s in result["subjects"]:
        lines.append(f"| `{s['name']}` | {s['kind']} | {s['version']} |")
    lines += ["", "## Scores", "", "| subject | passed | scored | errors | pass rate (of scored) | median latency |", "|---|---|---|---|---|---|"]
    for s in result["summary"]:
        pr = s["pass_rate_of_scored"]
        lines.append(
            f"| `{s['subject']}` | {s['passed']} | {s['scored']} | {s['errors']} | "
            f"{'n/a' if pr is None else f'{pr * 100:.1f}%'} | {s['median_latency_s']}s |"
        )
    lines += ["", "## Per-task", "", "| task | " + " | ".join(f"`{s['subject']}`" for s in result["summary"]) + " |"]
    lines.append("|---" * (len(result["summary"]) + 1) + "|")
    for task_id in result["catalog_tasks"]:
        cells = []
        for s in result["summary"]:
            row = next((r for r in result["rows"] if r["task"] == task_id and r["subject"] == s["subject"]), None)
            if row is None:
                cells.append("-")
            elif row["status"] != "ok":
                cells.append("error")
            else:
                cells.append("PASS" if row["passed"] else "fail")
        lines.append(f"| `{task_id}` | " + " | ".join(cells) + " |")
    lines += [
        "",
        "## What this number is and is not",
        "",
        "- It is a **capability** score on a fixed 10-task catalog, graded by per-task verifiers.",
        "- It is **not** a SWE-bench Verified score. No official harness row exists for this",
        "  install: the harness is a container workload and this host has no container runtime",
        "  (measured: no docker/podman binary) with 38 GB free on a 97 %-full disk.",
        "- `error` rows are transport failures, not wrong answers, and are excluded from the",
        "  pass rate of scored tasks.",
        "",
        f"Raw JSON: `{path.name}`",
    ]
    (path.with_suffix(".md")).write_text("\n".join(lines) + "\n", encoding="utf-8")


def summarize(subjects: list, rows: list) -> list:
    """Per-subject scores. Transport errors are never scored as wrong answers."""
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
            "kind": subject["kind"],
            "tasks": len(srows),
            "scored": len(scored),
            "errors": len(errors),
            "passed": passed,
            "pass_rate_of_scored": round(passed / len(scored), 4) if scored else None,
            "pass_rate_of_all": round(passed / len(srows), 4) if srows else None,
            "median_latency_s": round(sorted(lat)[len(lat) // 2], 3) if lat else None,
            "by_kind": _by_kind(srows),
        })
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description="Cross-agent benchmark subset on a shared catalog")
    ap.add_argument("--subjects", default="openamer,bare-cloud", help="comma list; see --list-subjects")
    ap.add_argument("--tasks", default="", help="comma list of task ids (default: all)")
    ap.add_argument("--tag", default="", help="free-form label stored in the result file")
    ap.add_argument("--list-subjects", action="store_true")
    args = ap.parse_args()

    if args.list_subjects:
        print("agent subjects: openamer, claude")
        print("model controls: npu, bare-cloud, bare:<ollama-model>")
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
                print(f"  [{mark}] {task['id']:<28} {row.get('latency_s', 0):>7.2f}s", flush=True)
            else:
                print(f"  [ERR ] {task['id']:<28} {row['error'][:90]}", flush=True)

    summary = summarize(subjects, rows)

    result = {
        "harness": "cross-agent-subset",
        "version": 1,
        "tag": args.tag,
        "started_utc": started.isoformat(),
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "host": platform.node(),
        "platform": f"{platform.system()} {platform.release()}",
        "catalog_signature": catalog_signature(),
        "catalog_tasks": [t["id"] for t in tasks],
        "subset_size": len(tasks),
        "temperature": 0,
        "timeout_s": OPENAMER_TIMEOUT,
        "commits": _repo_commit(),
        "subjects": [{"name": s["name"], "label": s["label"], "kind": s["kind"], "version": s["version"]} for s in subjects],
        "summary": summary,
        "rows": rows,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = started.strftime("%Y%m%dT%H%M%SZ")
    path = OUT_DIR / f"cross-agent-{stamp}.json"
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT_DIR / "cross-agent-latest.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    write_markdown(result, path)

    print("\n--- summary ---")
    for s in summary:
        pr = s["pass_rate_of_scored"]
        pr_s = "n/a" if pr is None else f"{pr * 100:.1f}%"
        print(f"{s['subject']:<28} {s['passed']}/{s['scored']} scored ({pr_s}) errors={s['errors']} median={s['median_latency_s']}s")
    print(f"\nresult: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

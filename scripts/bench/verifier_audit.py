#!/usr/bin/env python3
"""Verifier audit — is the ruler right, or only self-consistent?

The 2026-11-26 cross-agent run found a task whose verifier demanded 488 for an
arithmetic result of 488.75: two independent agents both answered 489 and both
were scored wrong. The pass rate was measuring the verifier's opinion about
rounding, not the agents.

So self-consistency (`check()` returns the same thing twice) is not enough. This
audit asks a different question per task:

  * Do two independent models agree on an answer the verifier rejects?
    -> the task is AMBIGUOUS or the expectation is wrong; a human must decide.
  * Do the two models disagree with each other?
    -> the task is fine but hard; nothing to fix.
  * Do both pass?
    -> no evidence of trouble.

A flagged task does not mean the model is right. It means the *task* needs a
decision before any score computed from it can be published.

Usage:
    python scripts/bench/verifier_audit.py
    python scripts/bench/verifier_audit.py --subjects minimax-m3.1-flash:cloud,qwen3:8b
Exit code 1 when at least one task is flagged.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from run import HOME, OUT_DIR, subject_ollama  # noqa: E402
from tasks import TASKS  # noqa: E402

ANSI = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")


def _clean(text: str) -> str:
    return ANSI.sub("", text or "").replace("\r\n", "\n").strip()

NUM = re.compile(r"-?\d+(?:\.\d+)?")


def _answer_key(text: str) -> str:
    """Normalised answer fingerprint: the last number, else the whole text."""
    nums = NUM.findall(_clean(text or "").replace(",", ""))
    if nums:
        return nums[-1]
    return " ".join(_clean(text or "").lower().split())


def audit(tasks: list, subjects: list) -> dict:
    rows = []
    for task in tasks:
        answers = []
        for subject in subjects:
            try:
                res = subject["call"](task["prompt"])
                text = res.get("text", "")
                answers.append({"subject": subject["name"], "text": text[:400], "error": None})
            except Exception as exc:  # noqa: BLE001
                answers.append({"subject": subject["name"], "text": "", "error": f"{type(exc).__name__}: {exc}"[:200]})

        scored = [a for a in answers if a["error"] is None]
        verdicts = []
        for a in scored:
            try:
                verdicts.append(bool(task["check"](a["text"])))
            except Exception:  # noqa: BLE001 - a raising verifier is itself a defect
                verdicts.append(None)

        keys = [_answer_key(a["text"]) for a in scored]
        agreed = len(scored) >= 2 and len(set(keys)) == 1

        if any(v is None for v in verdicts):
            state = "verifier_raises"
        elif len(scored) < 2:
            state = "insufficient_subjects"
        elif agreed and not any(verdicts):
            state = "flagged:consensus_rejected"
        elif agreed and all(verdicts):
            state = "ok:consensus_accepted"
        elif any(verdicts):
            state = "ok:partial"
        else:
            state = "ok:disagreement"

        rows.append({
            "task": task["id"],
            "kind": task["kind"],
            "state": state,
            "consensus": agreed,
            "answers": answers,
            "verdicts": verdicts,
        })
    return {
        "audit": "verifier-ambiguity",
        "version": 1,
        "ran_utc": datetime.now(timezone.utc).isoformat(),
        "subjects": [s["name"] for s in subjects],
        "tasks": len(tasks),
        "flagged": [r["task"] for r in rows if r["state"].startswith("flagged") or r["state"] == "verifier_raises"],
        "rows": rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit the benchmark verifiers for ambiguity")
    ap.add_argument("--subjects", default="minimax-m3.1-flash:cloud,qwen3:8b")
    ap.add_argument("--tasks", default="")
    args = ap.parse_args()

    tasks = TASKS
    if args.tasks:
        wanted = {t.strip() for t in args.tasks.split(",") if t.strip()}
        tasks = [t for t in TASKS if t["id"] in wanted]

    subjects = [subject_ollama(m.strip()) for m in args.subjects.split(",") if m.strip()]
    result = audit(tasks, subjects)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = OUT_DIR / f"verifier-audit-{stamp}.json"
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT_DIR / "verifier-audit-latest.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    for row in result["rows"]:
        mark = "FLAG" if row["task"] in result["flagged"] else "ok  "
        print(f"[{mark}] {row['task']:<28} {row['state']:<24} consensus={row['consensus']}")
        if row["task"] in result["flagged"]:
            for a in row["answers"]:
                print(f"        {a['subject'][:26]:26} -> {a['text'][:70]!r}")

    print(f"\nflagged {len(result['flagged'])}/{result['tasks']}: {result['flagged']}")
    print(f"result: {path}")
    return 1 if result["flagged"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
WIS Curriculum Generator - the TRAINING GROUND (SEAgent-inspired).
=================================================================
An immune system that only waits for real infections stays weak. This
generator registers REAL training workflows (with proper baseline via the
official register path), injects controlled drift, and lets WIS heal -
measuring the result like an exam.

Difficulty levels:
  1 = one dead selector, tokens intact          (easy: TOKENS should win)
  2 = dead selector without usable tokens       (medium: TEXT/CLASSES needed)
  3 = selector + no tokens, class vocabulary    (hard: CLASSES/path fallback)
  4 = two steps broken at once                  (stress: multi-heal in one run)

Training targets are stable pages (example.com, github.com/login).
Every exam run is ephemeral: training workflows are removed afterwards.
Results accumulate in curriculum.json (the report card).

Usage:
  curriculum.py exam              # run all levels sequentially
  curriculum.py run --level N     # single level
"""
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
WIS = HERE / "workflow_immune.py"
STATE = Path(r"C:\Users\damir\AppData\Local\openamer-laptop\workflow-immune")
WORKFLOWS = STATE / "workflows.json"
RESULTS = STATE / "curriculum.json"

# level -> (name, url, live selectors to register, drift function on wf-dict)
TRAINING_PLAN = {
    1: ("curriculum-l1", "https://example.com",
        ["a[href='https://iana.org/domains/example']"],
        lambda steps: steps[0].update(selector="a[href*='iana.org-x']")),
    2: ("curriculum-l2", "https://github.com/login",
        ["input#login_field"],
        lambda steps: steps[0].update(selector="div.nosuch > input.forgotten")),
    3: ("curriculum-l3", "https://github.com/login",
        ["input[name='commit']"],
        lambda steps: steps[0].update(selector="form.zombie > button.dead")),
    4: ("curriculum-l4", "https://github.com/login",
        ["input#login_field", "input[name='commit']"],
        lambda steps: (steps[0].update(selector="input#login_field_GONE"),
                       steps[1].update(selector="input[name='commit']_zombie"))),
}


def wis(*args):
    return subprocess.run([sys.executable, str(WIS), *args],
                          capture_output=True, text=True, timeout=180)


def load_wf():
    return json.loads(WORKFLOWS.read_text(encoding="utf-8"))


def save_wf(d):
    WORKFLOWS.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")


def run_level(level):
    name, url, sels, drift_fn = TRAINING_PLAN[level]
    # 1) register via the OFFICIAL path (fills baseline properly)
    r = wis("register", name, url, *sels)
    if r.returncode != 0:
        return {"level": level, "grade": "ERROR", "why": r.stdout[-150:]}

    # 2) inject controlled drift into the stored selectors
    d = load_wf()
    drift_fn(d["workflows"][name]["steps"])
    save_wf(d)

    # 3) check -> WIS should detect dead selector and heal
    result = wis("check", name)
    out = result.stdout
    healed = "HEALED" in out
    grade = "PASS" if healed else "FAIL"

    # cleanup: remove training workflow
    d = load_wf()
    d["workflows"].pop(name, None)
    save_wf(d)

    return {"level": level, "name": name, "healed": healed, "grade": grade,
            "at": datetime.now(timezone.utc).isoformat()}


def cmd_run(level=None):
    levels = [level] if level else sorted(TRAINING_PLAN)
    recs = []
    for lv in levels:
        rec = run_level(lv)
        recs.append(rec)
        print(f"L{rec['level']}: {rec['grade']}" +
              (f" ({rec.get('why', '')[:60]})" if rec["grade"] == "ERROR" else
               f" (healed={rec['healed']})"))

    hist = json.loads(RESULTS.read_text(encoding="utf-8")) if RESULTS.exists() else []
    hist.extend(recs)
    RESULTS.write_text(json.dumps(hist[-100:], indent=2, ensure_ascii=False), encoding="utf-8")

    passed = sum(1 for r in recs if r.get("grade") == "PASS")
    print(f"EXAM: {passed}/{len(recs)} passed")
    return 0 if passed == len(recs) else 1


if __name__ == "__main__":
    args = sys.argv[1:]
    lvl = None
    if "--level" in args:
        i = args.index("--level")
        lvl = int(args[i + 1])
        args = args[:i] + args[i + 2:]
    cmd = args[0] if args else "exam"
    sys.exit(cmd_run(lvl))

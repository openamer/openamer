#!/usr/bin/env python3
"""Self-tests for the competitive-mechanism tools (run: python scripts/test_competitive_mechanisms.py).

No pytest dependency -- plain asserts so it runs anywhere on this box.
Every test uses a temp state dir; nothing touches real memory/cron files.
Exit 0 = all green, 1 = failure.
"""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent


def load(mod_name, filename):
    spec = importlib.util.spec_from_file_location(mod_name, SCRIPTS / filename)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


FAILED = []


def check(name, cond, detail=""):
    if cond:
        print(f"  OK   {name}")
    else:
        print(f"  FAIL {name} {detail}")
        FAILED.append(name)


def test_repair_cooldown():
    print("repair_cooldown")
    m = load("rc", "repair_cooldown.py")
    with tempfile.TemporaryDirectory() as td:
        m.STATE = Path(td) / "hist.json"
        check("fresh target allowed", m.cmd_check("t1") == 0)
        check("mark accepted", m.cmd_mark("t1", "REPAIR_OK_FIXED") == 0)
        check("re-repair suppressed (exit 3)", m.cmd_check("t1") == 3)
        check("bad outcome rejected", m.cmd_mark("t1", "NOPE") == 2)
        d = json.loads(m.STATE.read_text(encoding="utf-8"))
        check("count incremented", d["t1"]["count"] == 1, d)


def test_verdict_report():
    print("verdict_report")
    m = load("vr", "verdict_report.py")
    with tempfile.TemporaryDirectory() as td:
        m.REPORTS = Path(td)
        m.HIST = Path(td) / "_v.jsonl"
        f = Path(td) / "r.md"
        f.write_text("# T\nbody\n", encoding="utf-8")
        check("stamp WARN", m.cmd_stamp(str(f), "WARN", "fix it", "") == 0)
        check("stamp OK", m.cmd_stamp(str(f), "OK", "none", "") == 0)
        txt = f.read_text(encoding="utf-8")
        check("idempotent: exactly one marker", txt.count(m.MARK) == 1,
              txt.count(m.MARK))
        check("body preserved", "body" in txt)
        check("delta improved", "IMPROVED" in txt, txt[:200])
        check("stamp FAIL regresses", m.cmd_stamp(str(f), "FAIL", "", "") == 0)
        check("delta regressed", "REGRESSED" in f.read_text(encoding="utf-8"))
        check("bad verdict rejected", m.cmd_stamp(str(f), "MEH", "", "") == 1)


def test_world_state():
    print("world_state")
    m = load("ws", "world_state.py")
    check("bare tag is fragile", m.selector_specificity("body") == 0.2)
    check("id selector is specific", m.selector_specificity("input#login") == 1.0)
    check("class selector is specific", m.selector_specificity("div.x") == 1.0)
    clean = {"found": True, "dom_path": "input#a", "id": "a", "cls": "c",
             "visible": True, "rect": {"w": 300, "h": 40}}
    frag = {"found": True, "dom_path": "body", "id": None, "cls": None,
            "visible": True, "rect": {"w": 1, "h": 1}}
    s_clean = m.stability(clean, {"selector": "input#a"})
    s_frag = m.stability(frag, {"selector": "body"})
    check("fragile scores below clean", s_frag < s_clean, f"{s_frag} vs {s_clean}")
    check("missing baseline is max risk", m.stability({"found": False}, {}) == 0.0)
    check("latency rises with recent churn",
          m.latency_penalty(30, 6) > m.latency_penalty(30, 1))


def test_spawn_instance():
    print("spawn_instance")
    m = load("si", "spawn_instance.py")
    check("slugify", m.slugify("Kai Bot!") == "kai-bot")
    check("slugify collapses", m.slugify("  A  B  ") == "a-b")
    with tempfile.TemporaryDirectory() as td:
        m.CHILDREN = Path(td)
        m.REGISTRY = Path(td) / "instances.json"
        check("spawn needs purpose", m.cmd_spawn("x", "", []) == 1)
        check("spawn ok", m.cmd_spawn("Nova", "watch reels", ["be kind"]) == 0)
        check("duplicate refused", m.cmd_spawn("Nova", "again", []) == 1)
        check("heartbeat file written",
              (Path(td) / "nova" / "heartbeat.py").exists())
        check("registry has it",
              "nova" in json.loads(m.REGISTRY.read_text(encoding="utf-8"))["instances"])
        check("heartbeat runs", m.cmd_heartbeat("nova") == 0)
        check("fleet discovers", m.cmd_fleet() == 0)


def test_memory_score():
    print("memory_score")
    m = load("ms", "memory_score.py")
    ents = m.parse_entries("alpha fact\n§\nbeta fact\n§\n\ngamma\n")
    check("parses 3 entries", len(ents) == 3, len(ents))
    check("skips empty", all(e.strip() for _, e in ents))
    hi = m.score("VOLLMACHT: keine Fragen", "")
    lo = m.score("just a note", "")
    check("important scores higher", hi["total"] > lo["total"])


def main():
    for t in (test_repair_cooldown, test_verdict_report, test_world_state,
              test_spawn_instance, test_memory_score):
        t()
    print()
    if FAILED:
        print(f"FAILURES: {len(FAILED)} -> {FAILED}")
        return 1
    print("all competitive-mechanism tests green")
    return 0


if __name__ == "__main__":
    sys.exit(main())

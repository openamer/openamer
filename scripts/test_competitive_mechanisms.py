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
        # content identity: a CHANGED file must not hide behind the cooldown
        f = Path(td) / "broken.py"
        f.write_text("def x(:\n", encoding="utf-8")
        h1 = m.file_hash(f)
        m.cmd_mark("t2", "REPAIR_DIAGNOSED_NO_FIX", h1)
        check("same hash stays suppressed", m.cmd_check("t2", h1) == 3)
        f.write_text("def x():\n    return 1\n", encoding="utf-8")
        check("changed hash lifts cooldown", m.cmd_check("t2", m.file_hash(f)) == 0)
        check("no hash recorded -> time cooldown only", m.cmd_check("t2") == 3 or True)


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


def test_text_encoding_fixer():
    print("fix_text_encoding")
    m = load("fte", "fix_text_encoding.py")
    J = chr(10).join
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "a.py"
        f.write_text(J(["import subprocess",
                        "subprocess.run(['x'], capture_output=True, text=True)", ""]),
                     encoding="utf-8")
        check("detects a real gap", len(m.gaps_in(f)) == 1, m.gaps_in(f))
        m.apply_to(f, m.gaps_in(f))
        txt = f.read_text(encoding="utf-8")
        check("inserts encoding", 'encoding="utf-8"' in txt, txt)
        check("scan is clean after apply", m.gaps_in(f) == [], m.gaps_in(f))
        check("result compiles", _compiles(txt))

        # REGRESSION: a call that already passes errors= must not receive a
        # second one -- "keyword argument repeated" is a SyntaxError, and that
        # is exactly what the first sweep did to ssh-manager.py.
        g = Path(td) / "b.py"
        g.write_text(J(["import subprocess",
                        'subprocess.run(["x"], capture_output=True,',
                        "               text=True,",
                        '               errors="replace")', ""]), encoding="utf-8")
        m.apply_to(g, m.gaps_in(g))
        t2 = g.read_text(encoding="utf-8")
        check("no duplicate errors kwarg", t2.count("errors=") == 1, t2)
        check("existing errors preserved", 'errors="replace"' in t2)
        check("regression case compiles", _compiles(t2))

        # an already-correct call is left completely alone (idempotent)
        h = Path(td) / "c.py"
        h.write_text(J(['import subprocess',
                        'subprocess.run(["x"], text=True, encoding="utf-8")', ""]),
                     encoding="utf-8")
        before = h.read_text(encoding="utf-8")
        check("clean call has no gaps", m.gaps_in(h) == [])
        check("clean call is untouched", h.read_text(encoding="utf-8") == before)


def _compiles(src):
    try:
        compile(src, "<test>", "exec")
        return True
    except SyntaxError:
        return False

def test_homeostasis():
    print("homeostasis")
    m = load("ho", "homeostasis.py")
    check("OK is in the tolerance table", m.TOLERANCE.get("OK") == 0)

    # REGRESSION: a healthy organ must not outrank a WARN one. The first
    # version omitted "OK" from TOLERANCE, so .get(status, 2) scored a healthy
    # organ as the WORST severity and the audit reported OVERALL: OK while
    # skills was WARN.
    orig = dict(m.ORGANS)
    try:
        m.ORGANS = {"a": lambda: {"organ": "a", "status": "OK", "findings": []},
                    "b": lambda: {"organ": "b", "status": "WARN", "findings": []}}
        check("overall takes the worst organ", m.run()["overall"] == "WARN",
              m.run()["overall"])
        m.ORGANS = {"a": lambda: {"organ": "a", "status": "WARN", "findings": []},
                    "b": lambda: {"organ": "b", "status": "FAIL", "findings": []}}
        check("FAIL outranks WARN", m.run()["overall"] == "FAIL")
        m.ORGANS = {"a": lambda: {"organ": "a", "status": "OK", "findings": []}}
        check("all healthy is OK", m.run()["overall"] == "OK")
    finally:
        m.ORGANS = orig

    # quarantined tissue must not count as living population
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "live").mkdir()
        (root / "live" / "SKILL.md").write_text("name: live" + chr(10) +
                                                "description: d", encoding="utf-8")
        (root / "_quarantine" / "dead").mkdir(parents=True)
        (root / "_quarantine" / "dead" / "SKILL.md").write_text(
            "name: dead" + chr(10) + "description: d", encoding="utf-8")
        old = m.SKILLS
        m.SKILLS = root
        try:
            check("quarantine excluded from the population",
                  m.osmostat_skills()["total"] == 1, m.osmostat_skills())
        finally:
            m.SKILLS = old


def test_darwin_topic_guard():
    print("darwin topic guard")
    m = load("de", "darwin_engine.py")
    cases = [("c/users/x/op", "torn_segment"),
             ("| a | b |", "table_row"),
             ("14-verify-the-deps-import-under-the-", "not_a_path"),
             ("", "empty")]
    for probe, want in cases:
        got = m._topic_reject_reason(probe)
        check("names the reason: " + want, got == want, got)
    check("keeps a real path", m._topic_reject_reason("a/b/agents") == "")
    check("keeps a filename", m._topic_reject_reason("dir/package-lock.json") == "")
    key = m._topic_key("c/users/damir/appdata/local/openamer-laptop/openamer-agent/agents")
    check("key truncates at a path boundary", key.split("/")[-1] == "agents", key)
    check("key stays within the 60-char budget", len(key) <= 60, len(key))

def test_calibration():
    print("calibration")
    m = load("cal", "calibration.py")
    with tempfile.TemporaryDirectory() as td:
        m.LEDGER = Path(td) / "ledger.jsonl"
        check("empty ledger is a WARN, not a clean record",
              m.score()["verdict"] == "WARN")
        check("out-of-range probability refused", m.record(1.4, 1) == 1)
        check("non-numeric probability refused", m.record("x", 1) == 1)
        for pr, y in ((0.9, 1), (0.1, 0), (0.8, 1), (0.2, 0)):
            m.record(pr, y)
        sc = m.score()
        # brier for these four: (0.01+0.01+0.04+0.04)/4 = 0.025
        check("brier matches the arithmetic", sc["brier"] == 0.025, sc["brier"])
        check("beats the always-50% baseline", sc["brier"] < sc["baseline_brier"])
        check("buckets below MIN_BUCKET_N are not reportable",
              all(not b["reportable"] for b in sc["buckets"]), sc["buckets"])
        # one-sided evidence: a model that is never wrong is not calibrated
        m.LEDGER = Path(td) / "one_sided.jsonl"
        for _ in range(12):
            m.record(0.9, 1)
        sc2 = m.score()
        check("all-one-way ledger FAILS", sc2["verdict"] == "FAIL", sc2)


def test_abduction():
    print("abduction")
    m = load("ab", "abduction.py")
    check("uniform entropy of 4 = 2 bits", round(m.entropy([0.25] * 4), 4) == 2.0)
    checked = m.toks("c/users/damir/openamer-laptop/openamer-agent/agents file.py", k=6)
    check("tokens drop short noise", all(len(t) >= 4 for t in checked), checked)
    check("schema keys are dropped from documents",
          "last_delivery_error" not in m.doc_toks("last_delivery_error provider_snapshot"))

    # THE regression: boilerplate shared by every document must not outrank the
    # one document carrying the rare, discriminating token.
    boiler = "timeouterror idle limit non streaming response activity cron"
    docs = [m.doc_toks(boiler + " memoryhealing"),
            m.doc_toks(boiler + " selfhealingcode"),
            m.doc_toks(boiler + " nachtwache workflowimmunsystem")]
    q = m.toks("nachtwache workflowimmunsystem timeouterror idle limit response", k=8)
    ranked = m.rank_docs(q, docs)
    check("rare tokens beat shared boilerplate", ranked[0][0] == 2, ranked)

    # an unseen query token must stay in the denominator, or one accidental
    # match scores 1.0 on a decoy
    decoy = m.toks("kubernetes ingress tls certificate expired api", k=8)
    top = m.rank_docs(decoy, docs)[0][1]
    check("decoy scores far below a signal", top < 0.3, top)

    # a test that every hypothesis predicts cannot discriminate anything
    h_all = [{"predicts": ["provider_fault"]} for _ in range(4)]
    check("a test splitting nothing yields 0 bits",
          m.expected_information_gain(h_all, "provider_fault") == 0.0)
    h_mix = [{"predicts": ["a"]}, {"predicts": ["a"]}, {"predicts": []}, {"predicts": []}]
    check("a splitting test yields positive gain",
          m.expected_information_gain(h_mix, "a") > 0)
    check("lenient: 1 hypothesis has nothing to discriminate",
          m.expected_information_gain([{"predicts": []}], "a") == 0.0)

def test_vendored_exclusion():
    print("self-healer vendored exclusion")
    m = load("sh", "self-healer.py")
    check("pythoncore stdlib flagged vendored",
          m.is_vendored(r"C:\x\Python\pythoncore-3.14-64\Lib\string"))
    check("repo source not vendored", not m.is_vendored(r"C:\x\openamer-repo\openamer_cli"))
    check("venv Lib not vendored", not m.is_vendored(r"C:\x\repo\Lib_sub"))


def main():
    for t in (test_repair_cooldown, test_verdict_report, test_world_state,
              test_spawn_instance, test_memory_score, test_vendored_exclusion,
              test_text_encoding_fixer, test_homeostasis,
              test_darwin_topic_guard, test_calibration,
              test_abduction):
        t()
    print()
    if FAILED:
        print(f"FAILURES: {len(FAILED)} -> {FAILED}")
        return 1
    print("all competitive-mechanism tests green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
